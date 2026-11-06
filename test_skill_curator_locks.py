"""Curated runtime skills refuse edits until a separate operator unlock."""
import pytest

from services.agent_runtime.expansion import SkillProposal, SkillProposalState
from services.agent_runtime.learning import InMemoryLearningStore
from services.agent_runtime.skill_promotion import promote_approved_skill


def test_curator_lock_preserves_bytes_and_stale_unlock_refuses():
    store = InMemoryLearningStore()
    original = store.upsert_skill('Proof Skill', 'canon', 'Keep this exact wording')
    locked = store.set_curator_lock('proof skill', locked=True, expected_version=1)
    assert locked.version == 2 and locked.curator_locked
    assert locked.instructions == original.instructions
    for provenance in ['operator', 'proposal:trusted', 'operator:rollback']:
        with pytest.raises(ValueError, match='locked'):
            store.upsert_skill('proof skill', 'replacement', 'changed', provenance=provenance)
    with pytest.raises(ValueError, match='version'):
        store.set_curator_lock('proof-skill', locked=False, expected_version=1)
    assert store.get_skill('proof-skill') == locked
    unlocked = store.set_curator_lock('proof-skill', locked=False, expected_version=2)
    assert unlocked.version == 3 and not unlocked.curator_locked
    edited = store.upsert_skill('proof skill', 'replacement', 'changed')
    assert edited.version == 4
    assert store.set_curator_lock('proof-skill', locked=False, expected_version=4) == edited


def test_approved_proposal_cannot_bypass_curator_lock():
    store = InMemoryLearningStore()
    store.upsert_skill('proof', 'canon', 'fixed')
    locked = store.set_curator_lock('proof', locked=True, expected_version=1)
    proposal = SkillProposal(proposal_id='p', name='proof', description='new',
        instructions='changed', source_task_id='t', state=SkillProposalState.APPROVED)
    with pytest.raises(ValueError, match='locked'):
        promote_approved_skill(store, proposal)
    assert store.get_skill('proof') == locked


def test_isolated_stores_and_invalid_lock_values():
    a, b = InMemoryLearningStore(), InMemoryLearningStore()
    a.upsert_skill('proof', 'a', 'a')
    b.upsert_skill('proof', 'b', 'b')
    a.set_curator_lock('proof', locked=True, expected_version=1)
    assert b.upsert_skill('proof', 'b', 'new').version == 2
    for invalid in ['false', None, 0, 1]:
        with pytest.raises(ValueError, match='boolean'):
            a.set_curator_lock('proof', locked=invalid, expected_version=2)
    with pytest.raises(KeyError):
        a.set_curator_lock('missing', locked=True, expected_version=1)
