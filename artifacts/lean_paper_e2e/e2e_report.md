# P0-01 — ICYQuant → LEAN Paper E2E

- **Gate: PARTIAL** (4 PASS / 0 FAIL / 4 PENDING of 8)
- Generated: `2026-09-17T05:54:15.281245+00:00`
- Project: `/Users/xuehairong/CodeBuddy/20260817155030/ICYQuant/integrations/lean/paper`
- Environment: LEAN CLI `UNAVAILABLE`, Docker `OK`
- Deploy command: `lean live deploy /Users/xuehairong/CodeBuddy/20260817155030/ICYQuant/integrations/lean/paper --brokerage Paper Trading --parameter strategy_contract strategy_contract.json --output /Users/xuehairong/CodeBuddy/20260817155030/ICYQuant/artifacts/lean_paper_e2e/live-results`

| Gate | Name | Status | Detail |
|---|---|---|---|
| G01 | StrategyContract 创建 | PASS | StrategyContract built, frozen, and serialisable |
| G02 | Contract validation | PASS | 2 valid inputs accepted, 21/21 invalid rejected |
| G03 | ICYQuant → JSON | PASS | contract written to strategy_contract.json (559 bytes) and re-read identical |
| G04 | LEAN Adapter health | PASS | LEAN CLI absent (expected on a fresh Mac) — the adapter still reports the environment correctly; Layer B stays PENDING; docker=OK |
| G05 | LEAN Algorithm 启动 | PENDING | algorithm assets validate offline (class + hooks + lean.json + contract); starting LEAN needs an installed CLI and a paid QuantConnect organisation |
| G06 | Paper Brokerage 接收订单 | PENDING | no LEAN events supplied — pass --events <log\|json> from a real paper deployment to grade this gate |
| G07 | OrderEvent / Fill 返回 | PENDING | no LEAN events supplied — G07 needs a real fill to grade |
| G08 | ICYQuant Ledger/Reconcile | PENDING | no LEAN events supplied — G08 needs a real fill to post and reconcile |

## Next action

Layer B (G05–G08) is gradable once LEAN CLI is available: pip install lean, run `lean init`, then `python -m apps.runtime lean-paper --deploy`, or grade an existing run with `--events <lean log or events.json>`.

> A gate that did not run reports PENDING, not PASS.
