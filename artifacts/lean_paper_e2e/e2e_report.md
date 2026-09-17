# P0-01 — ICYQuant → LEAN Paper E2E

- **Gate: PARTIAL** (4 PASS / 0 FAIL / 4 PENDING of 8)
- Generated: `2026-09-17T06:29:48.636748+00:00`
- Project: `/Users/xuehairong/CodeBuddy/20260817155030/ICYQuant/integrations/lean/paper`
- Environment: LEAN CLI `OK`, Docker `OK`
- Deploy command: `lean live deploy /Users/xuehairong/CodeBuddy/20260817155030/ICYQuant/integrations/lean/paper --brokerage Paper Trading --data-provider-live Custom data only --output /Users/xuehairong/CodeBuddy/20260817155030/ICYQuant/artifacts/lean_paper_e2e/live-results`

| Gate | Name | Status | Detail |
|---|---|---|---|
| G01 | StrategyContract 创建 | PASS | StrategyContract built, frozen, and serialisable |
| G02 | Contract validation | PASS | 2 valid inputs accepted, 21/21 invalid rejected |
| G03 | ICYQuant → JSON | PASS | contract written to strategy_contract.json (559 bytes) and re-read identical |
| G04 | LEAN Adapter health | PASS | LEAN CLI usable (lean 1.0.229); docker=OK |
| G05 | LEAN Algorithm 启动 | PENDING | LEAN CLI present; re-run with --deploy to start the paper deployment (long-running) |
| G06 | Paper Brokerage 接收订单 | PENDING | no LEAN events supplied — pass --events <log\|json> from a real paper deployment to grade this gate (the deployment itself needs the CLI logged into a QuantConnect organisation) |
| G07 | OrderEvent / Fill 返回 | PENDING | no LEAN events supplied — G07 needs a real fill to grade (requires a CLI deployment, which itself needs a logged-in QuantConnect organisation) |
| G08 | ICYQuant Ledger/Reconcile | PENDING | no LEAN events supplied — G08 needs a real fill to post and reconcile (requires a CLI deployment, which itself needs a logged-in QuantConnect organisation) |

## Next action

Layer B (G05–G08) is gradable once LEAN CLI is available: pip install lean, run `lean init`, then `python -m apps.runtime lean-paper --deploy`, or grade an existing run with `--events <lean log or events.json>`.

> A gate that did not run reports PENDING, not PASS.
