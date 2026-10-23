//+------------------------------------------------------------------+
//|                                       ICYQuantBridge.mq5         |
//|                       B3.2 read-only probe — DO NOT USE FOR TRADE|
//|                                                                    |
//| Purpose: prove the Windows MT5 → Mac :9100 physical path works.   |
//|  - Reads token / host / port from EA inputs.                     |
//|  - GETs /healthz every N seconds via WebRequest().               |
//|  - Logs status to the Experts tab; never logs the token.          |
//|  - Fails closed: if request fails 3 times, logs CRITICAL.        |
//|                                                                    |
//| This is a probe, NOT the production EA. B3.3 will replace it.     |
//+------------------------------------------------------------------+
#property copyright "ICYQuant B3.2"
#property version   "0.1.0"
#property strict

// EA inputs. In the MT5 dialog, fill in the Mac Tailscale IP, port, token.
input string  InpHost       = "100.x.x.x";      // Mac Tailscale IP (FIXME)
input int     InpPort       = 9100;
input string  InpToken      = "";               // Bearer token (NEVER log this)
input int     InpPeriodSec  = 5;                // probe period (B3.2 uses 5s)

// Helpers --------------------------------------------------------------------

string HealthzURL() {
    return "http://" + InpHost + ":" + IntegerToString(InpPort) + "/healthz";
}

string MaskedToken() {
    // Show first 4 + length only, so the token itself never appears in logs.
    int n = StringLen(InpToken);
    if (n <= 4) return "***";
    return StringSubstr(InpToken, 0, 4) + "...(len=" + IntegerToString(n) + ")";
}

// OnInit / OnDeinit ----------------------------------------------------------

int OnInit() {
    if (InpToken == "") {
        Print("[FATAL] InpToken is empty. Aborting EA init.");
        return INIT_FAILED;
    }
    if (InpHost == "100.x.x.x" || InpHost == "") {
        Print("[FATAL] InpHost not configured. Aborting EA init.");
        return INIT_FAILED;
    }
    Print("[B3.2] init host=", InpHost, " port=", InpPort,
          " token=", MaskedToken(), " period=", InpPeriodSec, "s");
    EventSetTimer(InpPeriodSec);
    return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
    EventKillTimer();
    Print("[B3.2] deinit reason=", reason);
}

// Probe loop ----------------------------------------------------------------

int g_fail_streak = 0;

void OnTimer() {
    char   data[];
    char   result[];
    string headers = "Authorization: Bearer " + InpToken + "\r\n";
    string headers_out;
    int    timeout = 3000;  // 3 s

    int code = WebRequest(
        "GET",
        HealthzURL(),
        headers,
        timeout,
        data,
        result,
        headers_out
    );

    if (code == -1) {
        int err = GetLastError();
        g_fail_streak++;
        Print("[B3.2] WebRequest failed err=", err,
              " streak=", g_fail_streak);
        if (g_fail_streak >= 3) {
            Print("[B3.2][CRITICAL] 3 consecutive failures — check",
                  " Tailscale, Mac server, and MT5 → Tools → Options →",
                  " Expert Advisors → Allow WebRequest for ",
                  InpHost, ":", InpPort);
        }
        return;
    }

    g_fail_streak = 0;

    string body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
    Print("[B3.2] HTTP ", code, " body=", body);
}
//+------------------------------------------------------------------+
