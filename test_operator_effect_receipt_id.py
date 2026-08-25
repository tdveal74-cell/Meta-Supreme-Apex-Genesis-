"""Operator adapter always surfaces a local provider_receipt_id."""

from services.operator.agent_adapter import OperatorCapabilityAdapter


def test_operator_tool_result_sets_synthetic_receipt_id() -> None:
    result = OperatorCapabilityAdapter._tool_result(
        {
            "returncode": 0,
            "stdout": "hello",
            "stderr": "",
            "command": "echo hello",
        }
    )
    assert result.ok
    assert result.metadata is not None
    assert result.metadata["provider_receipt_id"].startswith("op-0-")
    assert result.metadata["provider_idempotency"] == "local-synthetic"


def test_operator_failed_command_still_has_receipt_id() -> None:
    result = OperatorCapabilityAdapter._tool_result(
        {
            "returncode": 1,
            "stdout": "",
            "stderr": "boom",
            "command": "false",
        }
    )
    assert not result.ok
    assert result.metadata is not None
    assert result.metadata["provider_receipt_id"].startswith("op-1-")
