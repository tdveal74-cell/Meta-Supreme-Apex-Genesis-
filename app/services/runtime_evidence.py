"""Lease-bound result recording, deterministic verification and route telemetry."""
import json
import secrets
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.agent_runtime import AgentTaskRecord, AgentToolResultRecord, AgentVerificationRecord
from app.services.agent_effect_receipts import EffectFenceRefused, arguments_hash
from services.agent_benchmarks import RouteTrace, aggregate_routes, fingerprint
from services.agent_runtime.contracts import TaskState
from services.agent_runtime.verification import canonical, check_captured, digest, report


def _safe_metadata(value):
    if isinstance(value, dict):
        return {k: _safe_metadata(v) for k, v in value.items() if k not in {'approval_token', '_devon_approval'}}
    if isinstance(value, list):
        return [_safe_metadata(v) for v in value]
    return value


class RuntimeEvidenceRepository:
    async def _fence(self, db, *, owner_id, task_id, lease_token, generation):
        row = await db.scalar(select(AgentTaskRecord.id).where(
            AgentTaskRecord.id == task_id, AgentTaskRecord.owner_id == owner_id,
            AgentTaskRecord.lease_token == lease_token,
            AgentTaskRecord.execution_generation == generation,
            AgentTaskRecord.lease_expires_at > datetime.now(timezone.utc)))
        if row is None:
            raise EffectFenceRefused('runtime evidence refused: live lease required')

    async def record_result(self, db, *, owner_id, lease_token, generation, task, step, result, elapsed_ms):
        await self._fence(db, owner_id=owner_id, task_id=task.task_id, lease_token=lease_token, generation=generation)
        body = canonical({'schema_version': 1, 'tool': step.tool_call.name, 'step_id': step.step_id,
                          'arguments_hash': arguments_hash(step.tool_call.arguments),
                          'ok': result.ok, 'output': result.output, 'error': result.error,
                          'metadata': _safe_metadata(result.metadata or {}), 'elapsed_ms': elapsed_ms})
        if len(body.encode()) > 16 * 1024 * 1024:
            raise ValueError('tool evidence exceeds 16 MiB storage bound')
        result_id = 'RESULT-' + secrets.token_hex(12)
        row = AgentToolResultRecord(id=result_id, owner_id=owner_id, task_id=task.task_id,
                                    step_id=step.step_id, generation=generation,
                                    body=body, content_hash=digest(body))
        db.add(row)
        await db.flush()
        return {'id': result_id, 'sha256': row.content_hash, 'tool': step.tool_call.name,
                'step_id': step.step_id, 'schema_version': 1}

    async def get_result(self, db, *, owner_id, task_id, result_id):
        row = await db.scalar(select(AgentToolResultRecord).where(
            AgentToolResultRecord.id == result_id, AgentToolResultRecord.owner_id == owner_id,
            AgentToolResultRecord.task_id == task_id))
        if row is None:
            return None
        if digest(row.body) != row.content_hash:
            raise ValueError('durable result integrity check failed')
        return {'id': row.id, 'sha256': row.content_hash, 'step_id': row.step_id,
                'generation': row.generation, 'captured': json.loads(row.body)}

    async def verify(self, db, *, owner_id, lease_token, generation, task, latency_ms, max_steps=None):
        await self._fence(db, owner_id=owner_id, task_id=task.task_id, lease_token=lease_token, generation=generation)
        captured, refs = {}, {}
        for observation in task.observations:
            ref = observation.metadata.get('durable_result')
            if not isinstance(ref, dict):
                continue
            value = await self.get_result(db, owner_id=owner_id, task_id=task.task_id, result_id=ref.get('id'))
            if (value is None or value['sha256'] != ref.get('sha256') or value['step_id'] != observation.step_id):
                continue
            captured[observation.step_id] = value['captured']
            refs[observation.step_id] = value['id'] + ':' + value['sha256']
        results = [check_captured(check, captured.get(check['step_id']), refs.get(check['step_id'], ''))
                   for check in task.verification_requirements]
        verification = report(task.verification_requirements, results, plan_completed=task.state is TaskState.COMPLETED)
        profile = dict(task.context.get('_runtime_profile') or {})
        trace_id = 'VERIFY-' + secrets.token_hex(12)
        stop = ('approval_pause' if task.state is TaskState.WAITING_APPROVAL else
                'completed' if task.state is TaskState.COMPLETED else
                'error' if task.state in {TaskState.FAILED, TaskState.CANCELLED} else 'budget_exhausted')
        # A model's textual answer is not parsed into a truth claim. Only declared
        # checks are measured. All other claims remain outside verification scope.
        trace = RouteTrace(
            trace_id=trace_id, task_id=task.task_id, task_family=profile.get('task_family', 'unspecified'),
            task_hash=fingerprint({'goal': task.goal,
                'input_context_hash': profile.get('input_context_hash', fingerprint({k: v for k, v in task.context.items() if k != '_runtime_profile'})),
                'plan': {**task.plan.to_dict(), 'steps': [
                {'step_id': s.step_id, 'tool_call': s.tool_call.to_dict()} for s in task.plan.steps]},
                'checks': task.verification_requirements}),
            route_version=profile.get('route_version', 'legacy-unrecorded'),
            model_version=profile.get('model_version', 'unrecorded'),
            prompt_version=profile.get('prompt_version', 'unrecorded'),
            skill_version=profile.get('skill_version', 'unrecorded'),
            suite_version='runtime-checks-v1',
            config_fingerprint=fingerprint({'creation_config': profile.get('config_fingerprint', 'unrecorded'),
                                            'max_steps': max_steps}),
            treatment='baseline', stop_reason=stop, receipt_refs=tuple(refs.values()),
            required=len(results), unresolved=sum(r.verdict != 'VERIFIED' for r in results),
            evidenced=sum(r.verdict != 'UNVERIFIED' for r in results),
            investigated=any(v['tool'].endswith(('.read', '.inspect', '.search', '.query')) and v['ok'] for v in captured.values()),
            unsupported_answer=task.state is TaskState.COMPLETED and any(r.verdict != 'VERIFIED' for r in results),
            stopped_with_available_next_step=False, latency_ms=latency_ms, cost_usd=None)
        body = canonical({'verification': verification, 'trace': asdict(trace), 'classification': trace.classification,
                          'classification_scope': 'declared checks and observed tool use, not semantic answer quality'})
        row = AgentVerificationRecord(id=trace_id, owner_id=owner_id, task_id=task.task_id,
                                      generation=generation, body=body, content_hash=digest(body))
        db.add(row)
        await db.flush()
        task.verification = {**verification, 'receipt_id': trace_id, 'receipt_sha256': row.content_hash}

    async def list_verifications(self, db, *, owner_id, task_id=None, limit=100):
        query = select(AgentVerificationRecord).where(AgentVerificationRecord.owner_id == owner_id)
        if task_id is not None:
            query = query.where(AgentVerificationRecord.task_id == task_id)
        rows = (await db.scalars(query.order_by(AgentVerificationRecord.created_at.desc(), AgentVerificationRecord.id.desc()).limit(limit))).all()
        values = []
        for row in rows:
            if digest(row.body) != row.content_hash:
                raise ValueError('verification receipt integrity check failed')
            values.append({'id': row.id, 'sha256': row.content_hash, 'task_id': row.task_id,
                           'generation': row.generation, **json.loads(row.body)})
        return values

    async def route_profiles(self, db, *, owner_id, limit=100):
        receipts = await self.list_verifications(db, owner_id=owner_id, limit=limit)
        # Each generation is a separate run. Aggregate only the newest receipt for
        # each task so pauses/resumes cannot inflate independent task denominators.
        latest = {}
        for r in receipts:
            if 'trace' in r:
                latest.setdefault(r['task_id'], r)
        traces, seen = [], set()
        for r in latest.values():
            t = RouteTrace(**{**r['trace'], 'receipt_refs': tuple(r['trace']['receipt_refs'])})
            key = (t.route_version, t.model_version, t.prompt_version, t.skill_version,
                   t.suite_version, t.config_fingerprint, t.treatment, t.task_hash)
            if key not in seen:
                traces.append(t)
                seen.add(key)
        return {'scope': 'recorded runtime task routes only', 'receipt_limit': limit,
                'tasks': len(traces), 'duplicate_task_content_excluded': len(latest) - len(traces),
                'profiles': aggregate_routes(traces),
                'unmeasured_routes_are_not_classified': True}

    async def calibrate_receipts(self, db, *, owner_id, receipt_ids, votes, training_hashes):
        from services.agent_benchmarks import KnownAnswer, calibrate
        if not receipt_ids or len(receipt_ids) > 100 or len(set(receipt_ids)) != len(receipt_ids):
            raise ValueError('unique nonempty receipt suite required, at most 100 cases')
        if not isinstance(votes, dict) or not 2 <= len(votes) <= 8:
            raise ValueError('two to eight version-named evaluators required')
        rows = (await db.scalars(select(AgentVerificationRecord).where(
            AgentVerificationRecord.owner_id == owner_id, AgentVerificationRecord.id.in_(receipt_ids)))).all()
        by_id = {r.id: r for r in rows}
        if set(by_id) != set(receipt_ids):
            raise ValueError('all calibration receipts must exist and belong to this owner')
        answers = []
        for key in receipt_ids:
            row = by_id[key]
            if digest(row.body) != row.content_hash:
                raise ValueError('calibration source receipt integrity failure')
            body = json.loads(row.body)
            verification, trace = body.get('verification', {}), body.get('trace', {})
            if verification.get('checker_version') != 'runtime-checks-v1' or not trace:
                raise ValueError('compatible runtime verifier receipt required')
            answers.append(KnownAnswer(key, trace['task_hash'], verification['verdict'], key + ':' + row.content_hash))
        value = calibrate(answers, votes, training_hashes=training_hashes)
        receipt_id = 'CALIB-' + secrets.token_hex(12)
        body = canonical({'calibration': value, 'source_receipts': [vars(a) for a in answers],
                          'scope': 'agreement and correctness against deterministic declared-check receipts only',
                          'semantic_truth_or_judge_independence_established': False,
                          'suite_hash': fingerprint({'answers': [vars(a) for a in answers], 'training_hashes': training_hashes}),
                          'votes': votes})
        row = AgentVerificationRecord(id=receipt_id, owner_id=owner_id, task_id=by_id[receipt_ids[0]].task_id,
                                      generation=0, body=body, content_hash=digest(body))
        db.add(row)
        await db.flush()
        return {'receipt_id': receipt_id, 'sha256': row.content_hash, **json.loads(body)}
