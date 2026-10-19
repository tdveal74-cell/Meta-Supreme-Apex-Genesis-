"""Deterministic checks over recorded tool results, not model verdicts.

VERIFIED means only that the caller's declared checks matched captured bytes.
It does not establish semantic truth, visual quality, or completeness of a goal.
"""
import base64
import hashlib
import json
import math
import struct
import zlib
from typing import Any

from services.agent_evaluation import CheckResult, outcome_verdict

KINDS = {'tool_succeeded', 'output_sha256', 'json_schema', 'artifact_properties'}
SCHEMA_KEYS = {'type', 'properties', 'required', 'additionalProperties', 'items', 'enum', 'minLength', 'maxLength', 'minimum', 'maximum'}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def validate_schema(schema, depth=0):
    if depth > 12 or not isinstance(schema, dict) or set(schema) - SCHEMA_KEYS:
        raise ValueError('unsupported or overly deep schema')
    if schema.get('type') not in ('object', 'array', 'string', 'number', 'integer', 'boolean', 'null'):
        raise ValueError('schema requires a supported type')
    by_type = {'object': {'properties', 'required', 'additionalProperties'}, 'array': {'items'},
               'string': {'minLength', 'maxLength'}, 'number': {'minimum', 'maximum'}, 'integer': {'minimum', 'maximum'},
               'boolean': set(), 'null': set()}
    if set(schema) - {'type', 'enum'} - by_type[schema['type']]:
        raise ValueError('schema keyword does not apply to declared type')
    props = schema.get('properties', {})
    if not isinstance(props, dict) or len(props) > 100:
        raise ValueError('invalid properties')
    if 'additionalProperties' in schema and type(schema['additionalProperties']) is not bool:
        raise ValueError('additionalProperties must be boolean')
    required = schema.get('required', [])
    if not isinstance(required, list) or any(not isinstance(x, str) for x in required) or len(set(required)) != len(required):
        raise ValueError('invalid required fields')
    for value in props.values():
        validate_schema(value, depth + 1)
    if 'items' in schema:
        validate_schema(schema['items'], depth + 1)
    if 'enum' in schema and (not isinstance(schema['enum'], list) or not schema['enum']):
        raise ValueError('nonempty enum required')
    for key in ('minLength', 'maxLength'):
        if key in schema and (type(schema[key]) is not int or schema[key] < 0):
            raise ValueError('nonnegative length required')
    for key in ('minimum', 'maximum'):
        if key in schema and (isinstance(schema[key], bool) or not isinstance(schema[key], (int, float)) or not math.isfinite(schema[key])):
            raise ValueError('finite bound required')
    canonical(schema)


def validate_requirements(checks, step_ids):
    if not isinstance(checks, list) or len(checks) > 50:
        raise ValueError('at most 50 verification checks')
    ids = set()
    for item in checks:
        if not isinstance(item, dict) or set(item) != {'id', 'step_id', 'kind', 'expected'}:
            raise ValueError('check requires id, step_id, kind and expected only')
        if not isinstance(item['id'], str) or not item['id'].strip() or len(item['id']) > 100 or item['id'] in ids:
            raise ValueError('check IDs must be unique nonempty strings')
        ids.add(item['id'])
        if (not isinstance(item['step_id'], str) or not isinstance(item['kind'], str)
                or item['step_id'] not in step_ids or item['kind'] not in KINDS
                or not isinstance(item['expected'], dict)):
            raise ValueError('unknown step, checker, or expectation')
        expected = item['expected']
        if item['kind'] == 'json_schema':
            validate_schema(expected)
        elif item['kind'] == 'tool_succeeded' and expected:
            raise ValueError('tool_succeeded takes empty expectations')
        elif item['kind'] == 'output_sha256':
            if set(expected) != {'sha256'}:
                raise ValueError('sha256 required')
        elif item['kind'] == 'artifact_properties':
            if not expected or set(expected) - {'sha256', 'byte_length', 'png_width', 'png_height'}:
                raise ValueError('unsupported artifact property')
            for key, value in expected.items():
                if key != 'sha256' and (type(value) is not int or value < 0):
                    raise ValueError('artifact dimensions and size must be nonnegative integers')
        if 'sha256' in expected and (not isinstance(expected['sha256'], str) or len(expected['sha256']) != 64 or any(c not in '0123456789abcdef' for c in expected['sha256'])):
            raise ValueError('invalid SHA256')
    canonical(checks)
    return json.loads(canonical(checks))


def schema_matches(value: Any, schema: dict) -> bool:
    kind = schema['type']
    valid = {'object': isinstance(value, dict), 'array': isinstance(value, list), 'string': isinstance(value, str),
             'number': type(value) in (int, float) and math.isfinite(value), 'integer': type(value) is int,
             'boolean': type(value) is bool, 'null': value is None}[kind]
    if not valid:
        return False
    if 'enum' in schema and all(canonical(value) != canonical(v) for v in schema['enum']):
        return False
    if kind == 'object':
        props = schema.get('properties', {})
        if any(k not in value for k in schema.get('required', [])):
            return False
        if schema.get('additionalProperties') is False and set(value) - set(props):
            return False
        return all(schema_matches(value[k], child) for k, child in props.items() if k in value)
    if kind == 'array':
        return 'items' not in schema or all(schema_matches(v, schema['items']) for v in value)
    if kind == 'string':
        return schema.get('minLength', 0) <= len(value) <= schema.get('maxLength', len(value))
    if kind in ('number', 'integer'):
        return schema.get('minimum', value) <= value <= schema.get('maximum', value)
    return True


def _reject_json_constant(value):
    raise ValueError('non-finite JSON constant: ' + value)


def _strict_json(output):
    value = json.loads(output, parse_constant=_reject_json_constant)
    # JSON numbers such as 1e999 overflow the float parser without invoking
    # parse_constant. Check every value, including undeclared schema fields.
    canonical(value)
    return value


def check_captured(requirement, captured, evidence_ref):
    """Captured values must come from the trusted recorder, never request data."""
    if captured is None:
        return CheckResult(requirement['id'], 'UNVERIFIED', '')
    passed = captured['ok'] is True
    try:
        kind, expected, output = requirement['kind'], requirement['expected'], captured['output']
        if kind == 'output_sha256':
            passed = passed and digest(output) == expected['sha256']
        elif kind == 'json_schema':
            passed = passed and schema_matches(_strict_json(output), expected)
        elif kind == 'artifact_properties':
            # Inspect captured bytes only. No user-specified filesystem paths or URLs.
            obj = _strict_json(output)
            data = base64.b64decode(obj['artifact_base64'], validate=True)
            actual = {'byte_length': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            if 'png_width' in expected or 'png_height' in expected:
                if len(data) < 33 or data[:8] != b'\x89PNG\r\n\x1a\n' or data[8:16] != b'\0\0\0\rIHDR':
                    passed = False
                elif zlib.crc32(data[12:29]) & 0xffffffff != struct.unpack('>I', data[29:33])[0]:
                    passed = False
                else:
                    actual['png_width'], actual['png_height'] = struct.unpack('>II', data[16:24])
            passed = passed and all(actual.get(k) == v for k, v in expected.items())
        elif kind != 'tool_succeeded':
            return CheckResult(requirement['id'], 'UNVERIFIED', '')
    except (ValueError, TypeError, KeyError, struct.error, OverflowError, RecursionError):
        passed = False
    return CheckResult(requirement['id'], 'VERIFIED' if passed else 'FAILED', evidence_ref)


def report(checks, results, *, plan_completed):
    verdict = outcome_verdict([x['id'] for x in checks], results) if checks else 'UNVERIFIED'
    if not plan_completed and verdict == 'VERIFIED':
        verdict = 'UNVERIFIED'
    return {'verdict': verdict, 'scope': 'declared_checks_only', 'checker_version': 'runtime-checks-v1',
            'plan_completed': plan_completed, 'checks': [vars(x) for x in results],
            'reason': 'no declared checks' if not checks else ''}
