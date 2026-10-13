# B3.2 — Windows MT5 → Mac :9100 Physical Path Probe

**Status:** validation only. B3.3 (real bridge) starts only after B3.2 PASS.

## Goal

Prove that an MQL5 EA running in a **Windows MT5 Terminal** can reach a
**Mac-side `/healthz` endpoint** over **Tailscale**, authenticated by a
**Bearer token**, with no leak of the token to logs or responses.

```
[Windows] MT5 Terminal (Phillip demo, 101053)
   └─ EA: scripts/b3_validation/ea/ICYQuantBridge.mq5
        └─ WebRequest("GET", "http://<tailscale-ip>:9100/healthz", ...)
              └─ [Tailscale tunnel]
                    └─ [Mac] python3 healthz_server.py  (this dir)
```

When this is green, B3.3 (the real bridge) can be written. If it stays
red after step 7, **stop** and report — do not invent a workaround.

---

## Frozen contract (B3.1)

- Poll period: **2 s** (B3.2 uses **5 s** for the probe; tighten in B3.3)
- VPN: **Tailscale** (free for personal use, auto NAT traversal)
- MT5 runtime: **your always-on Windows machine** (Phillip demo already logged in)
- Auth: `Authorization: Bearer $ICYQUANT_MT5_TOKEN`, server refuses to start without it
- Idempotency key: `signal_id` (not used in B3.2; introduced in B3.3)
- **No** writing to `services/integrations/mt5_bridge/` yet
- **No** changes to ICYQuant core

---

## One-time setup

### A. Mac (this box)

1. Install Tailscale (signed-in to your account):
   ```
   brew install --cask tailscale
   # or: https://tailscale.com/download/mac
   ```
   Note the assigned IP, e.g. `100.x.y.z`. You will paste this into the EA.

2. Generate a token (≥ 32 random chars, e.g.):
   ```
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Save it in your password manager. Do **not** commit it.

3. From the project root, run the Mac-side smoke test:
   ```
   export ICYQUANT_MT5_TOKEN="<paste the token>"
   bash scripts/b3_validation/smoke_test.sh
   ```
   Expect the final line: `B3.2 healthz server smoke test: PASS`.

### B. Windows (your always-on box)

1. Install Tailscale on Windows, sign in to the **same account** as the Mac.
   Confirm `tailscale status` shows both machines.

2. Install MT5 from Phillip (if not already):
   ```
   https://www.poems.com.sg/  (or the Phillip installer you have)
   ```
   Log in to **PhillipNova-Demo** as `101053` (this is the EA's host process).

3. MT5 must allow `WebRequest` to the Mac Tailscale IP:
   - Tools → Options → Expert Advisors
   - Tick **Allow WebRequest for listed URL**
   - Add: `http://100.x.y.z:9100`
     (use the Mac Tailscale IP from step A.1)

4. Compile and attach the probe EA:
   - File → Open Data Folder → `MQL5/Experts`
   - Create folder `ICYQuant`, drop `ICYQuantBridge.mq5` from
     `scripts/b3_validation/ea/` into it.
   - In MetaEditor (F4), open the file, **Compile** (F7).
   - Back in MT5, Navigator → Expert Advisors → `ICYQuantBridge`
   - Drag onto any chart (e.g. EURUSD H1, demo is fine).
   - In the dialog, set:
     - `InpHost`       = Mac Tailscale IP
     - `InpPort`       = `9100`
     - `InpToken`      = the token from step A.2
     - `InpPeriodSec`  = `5`  (B3.2 probe; B3.3 will be `2`)
   - Make sure **AutoTrading** button in the toolbar is **green**.
   - Make sure the chart face shows a **smiley** (not a frown).

---

## Run the probe

1. On the Mac, start the healthz server:
   ```
   export ICYQUANT_MT5_TOKEN="<token>"
   bash scripts/b3_validation/run_server.sh
   ```
   Leave it running.

2. On Windows, the EA starts probing within `InpPeriodSec` seconds.
   Open the **Experts** tab in MT5. Expect lines like:
   ```
   [B3.2] init host=100.x.y.z port=9100 token=abcd... len=43 period=5s
   [B3.2] HTTP 200 body={"status":"ok","ea_seen":true,"last_seen":...}
   ```

3. On the Mac server log, expect a corresponding access line (no token).

---

## Pass criteria

| Check | How | Pass |
|---|---|---|
| Server boots without `ICYQUANT_MT5_TOKEN` set | `unset ICYQUANT_MT5_TOKEN && bash run_server.sh` | refuses to start, exit 2 |
| Server refuses bad token | `curl -H "Authorization: Bearer wrong" ...` | HTTP 401 |
| Server accepts good token | `smoke_test.sh` | all 5 cases PASS |
| **No token in any server log** | `grep "$ICYQUANT_MT5_TOKEN" /tmp/b3_server.log` | empty |
| **No token in EA logs** | Experts tab → search for token prefix | not found |
| **EA reaches Mac over Tailscale** | Experts tab shows `HTTP 200` | one line per probe |
| Failed requests log clearly | Stop Mac server, observe EA Experts | `[B3.2] WebRequest failed err=... streak=N` |

If every row passes: **B3.2 = PASS**. Tell me, and B3.3 starts.
If any row fails: stop, paste the exact symptom, do not start B3.3.

---

## What B3.2 is **not**

- Not the production EA. The probe EA has no signal / order / fill logic.
- Not `services/integrations/mt5_bridge/`. That comes in B3.3, gated on B3.2.
- Not a change to ICYQuant core. Nothing in `apps/` or `services/` is touched.
