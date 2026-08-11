# Meta Supreme Apex Genesis — v0 Complete (offline flagship)

## Done without Postgres / monorepo restore

- 9-agent Council registry
- Mock deliberation (`simulated: true` always)
- Billing plans + limit checks
- Workflow definition validation (effects pause)
- System charter / non-negotiables
- Offline tests: `make test-offline`
- API: `make standalone` → http://localhost:8000/docs

## Not in this mirror alone

- Live provider calls against DB
- Full `make test` (148) without `app.*` / `services.*` restore
- Stripe / Teams / SSO

v0 offline Intelligence OS surface is complete and testable.
