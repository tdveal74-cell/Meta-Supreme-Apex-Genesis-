"""
Intelligence services — the Council, its executive controller, and synthesis.

Framework-free: no FastAPI, no database. The application-layer bridge that binds
this to persistence lives at `app.services.intelligence`; keeping the two apart
is what lets the deliberation logic be tested with no infrastructure at all.

The Council names resolve lazily, on attribute access, rather than being imported
when this package loads. `executive_controller` and `synthesizer` both depend on
`services.agents.executor`, which is absent from this partial restore — and an
eager import here would let that one missing module take down every unrelated
package underneath `services.intelligence`, `providers` included, which needs
nothing from the Council at all. Resolved lazily, the failure lands on the line
that actually asked for the Council and names the module that is missing.
"""

from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:  # pragma: no cover - type checkers resolve the real modules
    from services.intelligence.executive_controller import (
        AgentContribution,
        ContextPacket,
        CouncilExecutionError,
        ExecutiveController,
        IntentCategory,
        SynthesisResult,
    )
    from services.intelligence.synthesizer import SynthesisOutput, Synthesizer

_CONTROLLER_EXPORTS = {
    "AgentContribution",
    "ContextPacket",
    "CouncilExecutionError",
    "ExecutiveController",
    "IntentCategory",
    "SynthesisResult",
}
_SYNTHESIZER_EXPORTS = {"SynthesisOutput", "Synthesizer"}

__all__ = sorted(_CONTROLLER_EXPORTS | _SYNTHESIZER_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve a Council export on first use (PEP 562)."""
    if name in _CONTROLLER_EXPORTS:
        from services.intelligence import executive_controller as module
    elif name in _SYNTHESIZER_EXPORTS:
        from services.intelligence import synthesizer as module
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(module, name)


def __dir__() -> List[str]:
    return sorted(set(globals()) | set(__all__))
