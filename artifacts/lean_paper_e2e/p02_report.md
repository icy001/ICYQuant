# P0-02 — LEAN Paper Command / Contract Acceptance

- **Gate: PARTIAL** (7 PASS / 0 FAIL / 1 PENDING of 8)
- Generated: `2026-09-17T07:37:53.840332+00:00`
- Project: `/Users/xuehairong/CodeBuddy/20260817155030/ICYQuant/integrations/lean/paper`

| Gate | Name | Status | Detail |
|---|---|---|---|
| P02-G01 | deploy_paper 不再 TypeError | PASS | deploy_paper built and dispatched a legal live deploy argv |
| P02-G02 | live command 无 --parameter | PASS | live command contains no --parameter flag |
| P02-G03 | live command data-provider 合法 | PASS | live data provider='Custom data only' |
| P02-G04 | contract filename protocol | PASS | adapter / runtime / algorithm all name 'strategy_contract.json' |
| P02-G05 | lean.json 无 fake contract field | PASS | lean.json holds only LEAN project-level fields; no fake contract parameter |
| P02-G06 | lean.json 无 user-specific local-id | PASS | no local-id / cloud-id / organization-id committed |
| P02-G07 | main.py 从磁盘读取 contract | PASS | _load_contract() resolves the contract from the project directory |
| P02-G08 | Order → Fill → Ledger | PENDING | real LEAN paper Order → Fill → Ledger evidence required; P0-02 does not fabricate an offline fill |

## Next action

P02-G08 (real Order → Fill → Ledger) needs a real LEAN paper deployment: pip install lean, `lean init`, then `python -m apps.runtime lean-paper --deploy`, or grade an existing run with `--events <lean log or events.json>`.

> P02-G08 stays PENDING until a real deployment produces Order/Fill.
