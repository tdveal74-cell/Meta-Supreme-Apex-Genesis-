"""Readback harness must default offline and emit only bounded provenance."""
import pytest

from scripts.verify_graphify_readback import QUESTION, check


@pytest.mark.asyncio
@pytest.mark.parametrize('live,reviewed,configured', [(False, False, False), (False, True, True), (True, False, True), (True, True, False)])
async def test_no_query_without_all_live_prerequisites(monkeypatch, live, reviewed, configured):
    monkeypatch.setenv('DEVON_GRAPHIFY_ENABLED', 'true' if configured else 'false')
    monkeypatch.setenv('DEVON_GRAPHIFY_ACCESS_TOKEN', 'fake-secret')
    def never():
        raise AssertionError('must not construct network client')
    status, receipt = await check(live=live, no_capture_reviewed=reviewed, client_factory=never)
    assert status == (2 if live else 0)
    assert receipt['adapter_query_attempted'] is False
    assert receipt['remote_nonmutation_verified'] is False
    assert 'fake-secret' not in str(receipt)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['success', 'error', 'missing_commit', 'missing_path', 'credential_in_path'])
async def test_one_query_and_sanitized_receipt(monkeypatch, mode):
    monkeypatch.setenv('DEVON_GRAPHIFY_ENABLED', 'true')
    monkeypatch.setenv('DEVON_GRAPHIFY_ACCESS_TOKEN', 'fake-secret')
    calls = []
    class Fake:
        async def query_graph(self, question):
            calls.append(question)
            if mode == 'error':
                raise RuntimeError('fake-secret')
            return {'context': 'fake-secret ' + ('no paths' if mode == 'missing_path' else 'services/fake-secret.py' if mode == 'credential_in_path' else 'services/devon/approval.py'),
                    'commit': '' if mode == 'missing_commit' else 'abcdef1'}
    status, receipt = await check(live=True, no_capture_reviewed=True, client_factory=Fake)
    assert calls == [QUESTION]
    assert 'fake-secret' not in str(receipt)
    assert receipt['remote_nonmutation_verified'] is False
    assert receipt['authenticated_readback_verified'] is (mode == 'success')
    assert status == (0 if mode == 'success' else 3 if mode == 'error' else 4)
