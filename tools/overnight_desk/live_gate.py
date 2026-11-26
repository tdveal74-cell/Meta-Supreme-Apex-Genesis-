"""The paper to live gate.

Source line 80 sets the conditions before any live trading: a number of full
paper nights, passed acceptance tests and the owner typing the word live.
SPEC.md adds the per-order approval and the existence of a live executor,
which this build does not contain. Pure function: it returns every blocker, in
a fixed order, and an empty tuple means the gate is open. The first three
blockers follow source line 80, and the acceptance tests it names are the
STEP 15 the source never defines (STEPS.md). The last two, that a live
executor exists and that per-order approval exists, are INVENTED.
"""
from __future__ import annotations

from .settings import Settings


def live_gate_blockers(
    paper_nights_completed: int,
    acceptance_tests_passed: bool,
    owner_typed_live: bool,
    live_executor_exists: bool,
    per_order_approval_exists: bool,
    settings: Settings,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if paper_nights_completed < settings.paper_nights_required:
        blockers.append("paper_nights_short")
    if acceptance_tests_passed is not True:
        blockers.append("acceptance_tests_not_passed")
    if owner_typed_live is not True:
        blockers.append("owner_has_not_typed_live")
    if live_executor_exists is not True:
        blockers.append("no_live_executor")
    if per_order_approval_exists is not True:
        blockers.append("no_per_order_approval")
    return tuple(blockers)
