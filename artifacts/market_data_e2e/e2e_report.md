# Commit 017 — End-to-End Validation: A-Share Market Data Track

**Gate: PASS** — 20/20 gates PASS

* suite: `market-data`
* virtual session: 2026-09-08 10:31 (CONTINUOUS_AM)
* generated: 2026-09-17T02:41:51.675683+00:00 (provenance only — no wall clock enters the decision path)

## Reproducibility

* decision digest: `62578348273351400cbc85658096ad9e81a9a54b4cf3a03da8dc2c44774a2cde` (G19)
* vendor stream digest: `89bf6f2fd0359065bfa6de5a1114828caff9a1d0c4d642f26cc05e1299649d71`
* reproduced: every gate verdict and its detail
* reproduced: shadow decisions: orders, fills, positions, pnl, events (ids normalised)
* reproduced: the simulated vendor stream (seeded)
* **not** reproducible by design — order / fill / intent ids: uuid4 — uniqueness is the requirement, not repeatability (G19: declared namespace shape, and no id shared between runs)
* **not** reproducible by design — account-sync latency: it measures the real broker round trip, i.e. wall time, which a replay cannot pin (G12: the sync is nevertheless fresh and reconciled)

## Gates

| Gate | Name | Verdict | ms | Detail |
| --- | --- | --- | --- | --- |
| G1 | Architecture | PASS | 5223.2 | dependency direction clean; no Shadow→broker-order edge |
| G2 | Instrument Master | PASS | 0.1 | 11/11 instruments loaded, mapping correct |
| G3 | Realtime Quote | PASS | 4.4 | quote coverage 11/11; all fields valid |
| G4 | Trading Session | PASS | 0.1 | phases, weekend, holiday and makeup days all correct; lunch break is a phase, not a data gap |
| G5 | Quality Gate | PASS | 1.3 | 7/7 anomaly classes refused at the gate or the validator; 1 flagged STALE (in the stream, not tradable); clean quote still tradable |
| G6 | Redis Cache | PASS | 1.0 | quote/bar/session/quality cached; failure → DEGRADED + blocked; recovery → rehydrate → HEALTHY |
| G7 | Historical Merge | PASS | 9.3 | cold start seamless across UTC/CST; realtime owns the junction; closed conflict → revision; lunch ≠ gap; holes stay holes |
| G8 | Paper Trading | PASS | 1.4 | BUY@ask / SELL@bid simulated from real quotes; lot size enforced; no quote → no fill; PAPER disclaimer present |
| G9 | Replay | PASS | 250.1 | deterministic replay: identical event sequence at 1x/10x/100x and across repeated manual runs |
| G10 | Monitoring | PASS | 235.0 | 14/14 metrics declared by their exported names; sync path never raises; HEALTHY/DEGRADED/BLOCKED/OFFLINE vocabulary intact |
| G11 | Broker Adapter | PASS | 1.4 | connect → subscribe → stream; disconnect → reconnect → RESUBSCRIBE → quotes resumed |
| G12 | Account Sync | PASS | 5.4 | balance fields + latency captured; 3 snapshots retained in order; disconnect → ERROR → orders blocked |
| G13 | Position Sync | PASS | 1.4 | 3 positions synced; quantity/available/frozen/cost present; T+1 20000/0/20000 preserved; valuation only from real prices |
| G14 | Reconciliation | PASS | 4.1 | 10000/10000 → RECONCILED; 10000/8000 → MISMATCH + orders blocked; neither side auto-edited; restore → RECONCILED |
| G15 | Shadow | PASS | 7.0 | signal → intent → gate → simulated fill @ask → shadow position → PnL; broker read-only; 4 block codes reachable |
| G16 | Dashboard | PASS | 3900.4 | 20 dashboard endpoints present; PAPER / SHADOW banners rendered |
| G17 | Security | PASS | 170.1 | 0 broker order calls; SHD-/SHDF-/SHIN- namespaces; gate refuses LIVE/PAPER; CLI refuses --live |
| G18 | Failure Recovery | PASS | 16.8 | 4 injected faults (broker link / cache / account sync / reconciliation) each blocked new shadow orders and each recovered |
| G19 | Determinism | PASS | 18.1 | 3 shadow sessions → 1 digest; 2 seeded provider walks → 1 digest; unique id namespaces; no wall clock in the decision path |
| G20 | Final E2E | PASS | 11.5 | the full chain ran end to end — 10/10 stages, equity 1000000.00000 |

## Failure-injection matrix

Quote-level injections have no order to block (shown as `—`);
their refusal is the finding. Order-level injections state
whether the order was actually blocked.

| Scenario | Expected | Observed | Order blocked |
| --- | --- | --- | --- |
| G5/INVALID_PRICE | quality-gate | quality gate rejected 159852: INVALID (INVALID_PRICE) | — |
| G5/FUTURE_TIMESTAMP | quality-gate | quality gate rejected 159852: INVALID (FUTURE_TIMESTAMP) | — |
| G5/TIMESTAMP_REGRESSION | quality-gate | quality gate rejected 159852: INVALID (TIMESTAMP_REGRESSION) | — |
| G5/DUPLICATE | quality-gate | quality gate rejected 159852: INVALID (DUPLICATE) | — |
| G5/INVALID_BID_ASK | quality-gate | quality gate rejected 159852: INVALID (CROSSED_BOOK) | — |
| G5/INVALID_VOLUME | quality-gate | quality gate rejected 159852: INVALID (INVALID_VOLUME) | — |
| G5/UNKNOWN_SYMBOL | validator | cannot infer exchange for code '999999' (expected 15/16/50/51 prefix) | — |
| G5/STALE | accepted-then-not-tradable | STALE | — |
| G6/cache-unavailable | DEGRADED + trading blocked | DEGRADED | True |
| G12/adapter-disconnect | sync ERROR + orders blocked | ERROR | True |
| G14/position-mismatch | MISMATCH + new orders blocked | MISMATCH | True |
| G15/EXCESS_NOTIONAL | shadow order blocked | SHADOW_EXCESS_NOTIONAL | True |
| G15/INSUFFICIENT_CASH | shadow order blocked | SHADOW_INSUFFICIENT_CASH | True |
| G15/SESSION_CLOSED | shadow order blocked | SHADOW_FEED_NOT_READY | True |
| G15/SHORT_SELL | shadow order blocked | SHADOW_SHORT_SELL_BLOCKED | True |
| G18-A/broker-link-down | FEED_NOT_READY | SHADOW_FEED_NOT_READY | True |
| G18-B/cache-down (feed=DEGRADED) | FEED_NOT_READY | SHADOW_FEED_NOT_READY | True |
| G18-C/account-sync-error | SHADOW_ACCOUNT_SYNC_BLOCKED | SHADOW_ACCOUNT_SYNC_BLOCKED | True |
| G18-D/reconciliation-MISMATCH | SHADOW_ACCOUNT_SYNC_BLOCKED | SHADOW_ACCOUNT_SYNC_BLOCKED | True |

* order-level injections: 11 — all blocked: True
* quote-level injections: 8 — refused before an order could exist

## Reconciliation evidence (G14)

* **reconciled**: RECONCILED — matched 6, mismatch 0
* **mismatch**: MISMATCH — matched 4, mismatch 2
* **restored**: RECONCILED — matched 6, mismatch 0
* orders blocked while mismatched: True
* ledger quantity after the reconciler ran: 8000.000000 (never auto-corrected)

## Shadow safety matrix (G17)

* verdict: **PASS**
* broker order API calls: 0
* broker modules defining orders: []
* broker adapter order surface: []
* shadow → broker imports: []
* shadow order symbols: []
* gate mode: SHADOW (refused: ['LIVE', 'PAPER'])
* CLI flags refused: ['--live', '--real-order', '--broker-order']
* id namespaces: {'intent': 'SHIN-5B63E5644C8F', 'order': 'SHD-20260908-000001', 'fill': 'SHDF-20260908-000002'}
* real orders enabled: False

## Final chain (G20)

| Stage | OK | Evidence |
| --- | --- | --- |
| 1 provider→adapter→quote | yes | {'instruments': 11, 'state': 'STREAMING', 'subscription': 'SUBSCRIBED'} |
| 2 quote→quality gate | yes | {'ingested': 11, 'fresh': 11} |
| 3 quality→cache | yes | {'writes': 11, 'hits': 11} |
| 4 merged bars | yes | {'bars': 30, 'counts': {'historical': 29, 'realtime': 1, 'total': 30, 'overlaps': 0}, 'origins': ['HISTORICAL', 'REALTIME'], 'gaps': 0, 'jun |
| 5 paper order decision | yes | {'allowed': True, 'fill_price': '1.0500', 'price_source': 'ASK'} |
| 6 shadow execution | yes | {'order_id': 'SHD-20260908-000001', 'fill_id': 'SHDF-20260908-000002', 'fill_price': '1.05000'} |
| 6b fill price = paper price | yes | {'shadow': '1.05000', 'paper': '1.0500'} |
| 7 position & PnL | yes | {'quantity': 200, 'cash': '999790.00000', 'equity': '1000000.00000', 'total_pnl': '0.00000', 'unrealized': '0.00000'} |
| 8 account sync & reconcile | yes | {'positions': 3, 't1_available': '0.000000', 'reconcile': 'RECONCILED'} |
| 9 dashboard read-back | yes | {'status': 'LIVE', 'api_ask': '1.05', 'fill_price': '1.0500'} |
