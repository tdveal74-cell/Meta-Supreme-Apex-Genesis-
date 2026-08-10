"""Phase 6 billing scaffold — pure unit tests, no database."""

from billing import (
    PlanId,
    UsageSnapshot,
    all_plans,
    check_council_run,
    check_knowledge_item,
    check_token_budget,
    check_workflow_run,
    get_plan,
    plan_summary,
)


def test_catalog_has_three_plans():
    plans = all_plans()
    assert len(plans) == 3
    ids = {p["id"] for p in plans}
    assert ids == {"free", "professional", "enterprise"}


def test_free_is_default_on_unknown():
    plan = get_plan("not-a-real-plan")
    assert plan.id == PlanId.FREE


def test_council_limit_blocks_at_ceiling():
    plan = get_plan(PlanId.FREE)
    usage = UsageSnapshot(council_runs=plan.limits.council_runs)
    result = check_council_run(plan, usage)
    assert result.allowed is False
    assert result.limit == plan.limits.council_runs


def test_council_limit_allows_under_ceiling():
    plan = get_plan(PlanId.FREE)
    usage = UsageSnapshot(council_runs=0)
    result = check_council_run(plan, usage)
    assert result.allowed is True


def test_enterprise_tokens_unlimited():
    plan = get_plan(PlanId.ENTERPRISE)
    usage = UsageSnapshot(tokens=10_000_000)
    result = check_token_budget(plan, usage, additional=1)
    assert result.allowed is True
    assert result.limit is None


def test_workflow_and_knowledge_limits():
    plan = get_plan(PlanId.PROFESSIONAL)
    assert check_workflow_run(plan, UsageSnapshot(workflow_runs=0)).allowed is True
    assert check_knowledge_item(
        plan, UsageSnapshot(knowledge_items=plan.limits.knowledge_items)
    ).allowed is False


def test_plan_summary_shape():
    card = plan_summary(PlanId.FREE)
    assert card["name"] == "Free"
    assert card["price_usd_monthly"] == 0
    assert "council_runs" in card["limits"]
    assert isinstance(card["features"], list)
