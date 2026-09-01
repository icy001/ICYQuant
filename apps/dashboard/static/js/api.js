/* ICYQuant Dashboard - API client (Integration 001).
 *
 * Unified HTTP layer between the UI V1 shell and icyquant-api.
 *
 * Scope of this file:
 *   - Configurable base URL:  VITE_API_BASE_URL  (import.meta env)
 *                             ICY_API_BASE_URL    (window.__ICY_* fallback)
 *                             Defaults to "" which resolves via the
 *                             same-origin mount (dashboard SPA lives at
 *                             /dashboard and calls /api/*).
 *   - Timeout (default 5000ms).
 *   - Standard verbs: get / post / put / del.
 *   - Normalized error shape:  { message, status, code, kind, url, body }
 *         kind ∈ ["http" | "network" | "timeout" | "parse" | "abort"]
 *   - Backward compatibility with existing login / logout / isAuthenticated
 *     flows used by app.js.
 *
 * Out of scope for Integration 001:
 *   - Business endpoints (orders / positions / portfolio / risk / ...).
 *   - Retry policies, circuit breakers, interceptors, WS, SSE.
 */
(function (global) {
  "use strict";

  const TOKEN_KEY = "icy_dash_token";
  const USER_KEY = "icy_dash_user";

  /* ------------------------------------------------------------------
   * Config
   * ------------------------------------------------------------------ */

  function _readEnv(name, fallback) {
    // 1) import.meta.env (Vite-style)
    try {
      if (
        typeof globalThis !== "undefined" &&
        globalThis.import &&
        typeof globalThis.import.meta !== "undefined" &&
        globalThis.import.meta.env &&
        typeof globalThis.import.meta.env[name] === "string"
      ) {
        return globalThis.import.meta.env[name];
      }
    } catch (e) { /* environments without import.meta */ }

    // 2) window / process.env fallbacks
    try {
      var w = typeof window !== "undefined" ? window : {};
      var winKey = "__ICY_" + name;
      if (typeof w[winKey] === "string") return w[winKey];
      if (w.__ICY_CONFIG__ && typeof w.__ICY_CONFIG__[name] === "string") {
        return w.__ICY_CONFIG__[name];
      }
    } catch (e) { /* ignore */ }

    try {
      if (
        typeof process !== "undefined" &&
        process &&
        process.env &&
        typeof process.env[name] === "string"
      ) {
        return process.env[name];
      }
    } catch (e) { /* ignore */ }

    return fallback;
  }

  function _normalizeBase(raw) {
    if (!raw) return "";
    // strip trailing slash
    var s = String(raw).replace(/\/+$/, "");
    return s;
  }

  function _readInt(name, fallback) {
    var raw = _readEnv(name, null);
    if (raw === null) return fallback;
    var n = parseInt(raw, 10);
    return isFinite(n) && n > 0 ? n : fallback;
  }

  var CONFIG = {
    baseUrl: _normalizeBase(_readEnv("VITE_API_BASE_URL", "")),
    apiPrefix: "/api",
    timeoutMs: _readInt("VITE_API_TIMEOUT_MS", 5000),
  };

  /* ------------------------------------------------------------------
   * Error model
   * ------------------------------------------------------------------ */

  function ApiError(opts) {
    opts = opts || {};
    var msg = opts.message || "API request failed";
    var err = new Error(msg);
    err.name = "ApiError";
    err.status = opts.status || 0;          // HTTP status (0 for non-HTTP)
    err.code = opts.code || "API_ERROR";    // machine-readable code
    err.kind = opts.kind || "http";         // http | network | timeout | parse | abort
    err.url = opts.url || null;
    err.body = opts.body || null;           // parsed JSON body of an error response
    err.response = opts.response || null;   // raw Response object (if any)
    return err;
  }

  /* ------------------------------------------------------------------
   * State
   * ------------------------------------------------------------------ */

  var API = {
    _token: localStorage.getItem(TOKEN_KEY) || null,
    _user: null,

    /** Immutable snapshot of the active client config. */
    get config() {
      return {
        baseUrl: CONFIG.baseUrl,
        apiPrefix: CONFIG.apiPrefix,
        timeoutMs: CONFIG.timeoutMs,
        apiBaseUrl: CONFIG.baseUrl + CONFIG.apiPrefix,
      };
    },

    /** Runtime override (useful for dev / QA harnesses, not for env config). */
    configure: function (patch) {
      if (!patch) return;
      if (typeof patch.baseUrl !== "undefined") {
        CONFIG.baseUrl = _normalizeBase(patch.baseUrl);
      }
      if (typeof patch.apiPrefix !== "undefined") {
        CONFIG.apiPrefix = String(patch.apiPrefix).replace(/\/+$/, "");
      }
      if (typeof patch.timeoutMs !== "undefined" && isFinite(patch.timeoutMs) && patch.timeoutMs > 0) {
        CONFIG.timeoutMs = patch.timeoutMs;
      }
    },

    get user() {
      if (!this._user) {
        try {
          this._user = JSON.parse(localStorage.getItem(USER_KEY) || "null");
        } catch (e) {
          this._user = null;
        }
      }
      return this._user;
    },

    isAuthenticated: function () {
      return !!this._token;
    },

    _save: function (token, user) {
      this._token = token;
      this._user = user;
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
      if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
      else localStorage.removeItem(USER_KEY);
    },

    _buildUrl: function (path, opts) {
      opts = opts || {};
      var usePrefix = opts.skipPrefix !== true;
      var root = opts.absoluteBaseUrl
        ? _normalizeBase(opts.absoluteBaseUrl)
        : CONFIG.baseUrl;
      var prefix = usePrefix ? CONFIG.apiPrefix : "";
      var full = root + prefix + (path || "");
      if (opts.params) {
        var qs = [];
        Object.keys(opts.params).forEach(function (k) {
          var v = opts.params[k];
          if (v === undefined || v === null) return;
          qs.push(encodeURIComponent(k) + "=" + encodeURIComponent(v));
        });
        if (qs.length) full += (full.indexOf("?") >= 0 ? "&" : "?") + qs.join("&");
      }
      return full;
    },

    /** Core request primitive.
     *
     *  opts: { method, body, params, headers, timeoutMs, skipAuth, skipPrefix,
     *          absoluteBaseUrl, signal }
     *
     *  Resolves with the parsed JSON body (or null for empty responses).
     *  Rejects with a normalized ApiError (see above).
     */
    request: async function (path, opts) {
      opts = opts || {};
      var method = (opts.method || "GET").toUpperCase();
      var timeout = opts.timeoutMs && opts.timeoutMs > 0 ? opts.timeoutMs : CONFIG.timeoutMs;

      var headers = {};
      // default Content-Type only when we send JSON body (allows callers to
      // override, e.g. for multipart/form-data later).
      var hasBody = opts.body !== undefined && opts.body !== null;
      if (hasBody) headers["Content-Type"] = "application/json";
      if (opts.headers) {
        Object.keys(opts.headers).forEach(function (k) {
          headers[k] = opts.headers[k];
        });
      }
      if (!opts.skipAuth && this._token && !headers["Authorization"]) {
        headers["Authorization"] = "Bearer " + this._token;
      }

      var url = this._buildUrl(path, opts);
      var userCtrl = !!(opts.signal && typeof opts.signal.addEventListener === "function");
      var ctrl = userCtrl ? null : (typeof AbortController !== "undefined" ? new AbortController() : null);
      var timeoutId = null;
      if (ctrl && !userCtrl) {
        timeoutId = setTimeout(function () { ctrl.abort(); }, timeout);
      }

      var fetchOpts = {
        method: method,
        headers: headers,
        signal: userCtrl ? opts.signal : (ctrl ? ctrl.signal : undefined),
      };
      if (hasBody) {
        fetchOpts.body = headers["Content-Type"] === "application/json"
          ? JSON.stringify(opts.body)
          : opts.body;
      }

      var response = null;
      try {
        response = await fetch(url, fetchOpts);
      } catch (err) {
        if (timeoutId) clearTimeout(timeoutId);
        var isAbort = !!(err && (err.name === "AbortError" || err.code === 20));
        var timedOut = isAbort && !userCtrl && ctrl && ctrl.signal && ctrl.signal.aborted;
        if (timedOut) {
          throw ApiError({
            message: "Request timed out after " + timeout + "ms",
            status: 0,
            code: "TIMEOUT",
            kind: "timeout",
            url: url,
          });
        }
        if (isAbort) {
          throw ApiError({
            message: (err && err.message) || "Request aborted",
            status: 0,
            code: "ABORTED",
            kind: "abort",
            url: url,
          });
        }
        throw ApiError({
          message: (err && err.message) ? err.message : "Network error / Backend unreachable",
          status: 0,
          code: "NETWORK_ERROR",
          kind: "network",
          url: url,
        });
      } finally {
        if (timeoutId) clearTimeout(timeoutId);
      }

      // Auto handle 401 globally: drop stale token so UI can redirect to login.
      if (response.status === 401 && !opts.skipAuth) {
        this._save(null, null);
      }

      // Parse body (JSON first, fallback to empty)
      var data = null;
      try {
        // sniff content-type to avoid trying to JSON.parse HTML error pages
        var ct = response.headers && response.headers.get ? response.headers.get("content-type") : "";
        if (ct && ct.indexOf("application/json") !== -1) {
          var text = await response.text();
          if (text && text.length) data = JSON.parse(text);
        } else {
          // consume body anyway to release connection
          try { await response.arrayBuffer(); } catch (_e) { /* ignore */ }
        }
      } catch (parseErr) {
        if (!response.ok) {
          // surface HTTP error below, parse error is secondary
        } else {
          throw ApiError({
            message: "Invalid JSON in response",
            status: response.status,
            code: "PARSE_ERROR",
            kind: "parse",
            url: url,
            response: response,
          });
        }
      }

      if (!response.ok) {
        var detail = "Request failed";
        if (data && typeof data.detail === "string") detail = data.detail;
        else if (data && typeof data.message === "string") detail = data.message;
        else if (response.statusText) detail = response.statusText;
        if (response.status === 401) detail = detail || "Unauthorized";
        throw ApiError({
          message: detail,
          status: response.status,
          code: (data && data.code) || "HTTP_" + response.status,
          kind: "http",
          url: url,
          body: data,
          response: response,
        });
      }

      return data;
    },

    /* ---- Standard verb helpers --------------------------------------- */

    get: function (path, params, opts) {
      opts = opts || {};
      if (params) opts.params = params;
      return this.request(path, opts);
    },
    post: function (path, body, opts) {
      opts = opts || {};
      return this.request(path, Object.assign({}, opts, { method: "POST", body: body }));
    },
    put: function (path, body, opts) {
      opts = opts || {};
      return this.request(path, Object.assign({}, opts, { method: "PUT", body: body }));
    },
    del: function (path, opts) {
      opts = opts || {};
      return this.request(path, Object.assign({}, opts, { method: "DELETE" }));
    },

    /* ---- Session ------------------------------------------------------ */

    login: async function (username, password) {
      var data = await this.request("/auth/login", {
        method: "POST",
        body: { username: username, password: password },
      });
      this._save(data.token, data.user);
      return data;
    },

    logout: async function () {
      try {
        await this.request("/auth/logout", { method: "POST" });
      } catch (e) {
        /* ignore network / server errors on logout */
      }
      this._save(null, null);
    },

    /* ---- Integration 001: first real endpoint ------------------------ */

    /** Probe backend connectivity via ``GET /api/health``.
     *
     *  The endpoint is intentionally anonymous (auth optional), so the UI
     *  can surface "Backend Connected / Disconnected" before login and
     *  without leaking tokens to a probe endpoint.
     *
     *  Returns the raw health snapshot ``{status, version, timestamp,
     *  services, bootstrap}``.
     */
    // ── Research API (Integration 007) ──────────────────────────
    /** Research overview: all experiment runs with their funnels. */
    researchOverview: async function () {
      return this.get("/dashboard/research/overview");
    },

    /** List of experiment runs (summary). */
    researchRuns: async function () {
      return this.get("/dashboard/research/runs");
    },

    /** Single run detail (spec + split + funnel). */
    researchRun: async function (runId) {
      return this.get("/dashboard/research/runs/" + encodeURIComponent(runId));
    },

    /** Alpha list from a run (alpha_ranking). */
    researchAlphas: async function (runId) {
      return this.get("/dashboard/research/alphas",
                      { run_id: runId || "factor-real-d1" });
    },

    /** Alpha detail: summary + ranked pairs + decorrelation family. */
    researchAlphaDetail: async function (alphaId, runId) {
      var params = runId ? { run_id: runId } : null;
      return this.get("/dashboard/research/alphas/" + encodeURIComponent(alphaId),
                      params);
    },

    /** Funnel for a specific run. */
    researchFunnel: async function (runId) {
      return this.get("/dashboard/research/funnel/" + encodeURIComponent(runId));
    },

    /** De-correlation families for a run. */
    researchDecorrelation: async function (runId) {
      return this.get("/dashboard/research/decorrelation/" + encodeURIComponent(runId));
    },

    /** Raw research report for a run (report.md — View Report source). */
    researchReport: async function (runId) {
      return this.get("/dashboard/research/runs/" + encodeURIComponent(runId)
                      + "/report");
    },

    // ── Backtest API (Integration 008) ──────────────────────────
    /** Available instruments + frozen strategy metadata (config form). */
    backtestUniverse: async function () {
      return this.get("/dashboard/backtest/universe");
    },

    /** Submit a backtest. Replays take ~20s on real data, so the default
     *  5s timeout is raised — the request is the run's "running" state. */
    backtestRun: async function (body) {
      return this.post("/dashboard/backtest/run", body, { timeoutMs: 180000 });
    },

    /** Backtest run history (newest first). */
    backtestRuns: async function () {
      return this.get("/dashboard/backtest/runs");
    },

    /** Cached result payload for a recorded run. */
    backtestRunResult: async function (runId) {
      return this.get("/dashboard/backtest/runs/" + encodeURIComponent(runId));
    },

    // ── Strategy API (Integration 009) ─────────────────────────
    /** Strategy catalog: research funnel mapped onto the lifecycle. */
    strategyCatalog: async function () {
      return this.get("/dashboard/strategy/catalog");
    },

    /** Strategy detail: research + paper replay + backtest history.
     *  The paper replay is computed on first call, so the timeout is
     *  raised like the backtest run (same replay engine). */
    strategyDetail: async function (strategyId) {
      return this.get("/dashboard/strategy/catalog/" + encodeURIComponent(strategyId),
                      null, { timeoutMs: 180000 });
    },

    // ── Risk API (Integration 010) ──────────────────────────────
    /** Risk Control Center: live exposure + limits + event log. */
    riskCenter: async function () {
      return this.get("/dashboard/risk/center");
    },

    // ── Execution API (Integration 011) ─────────────────────────
    /** Execution Control Center: live engine status, KPI, order flow,
     *  quality, recent orders with slippage / latency, and venues. */
    executionCenter: async function () {
      return this.get("/dashboard/execution/center");
    },

    // ── Accounts API (Integration 012) ──────────────────────────
    /** Accounts Control Center: overview KPI (USD-normalised),
     *  multi-account list with balances / connection / capabilities,
     *  market breakdown, and adapter health. Read-only. */
    accountsCenter: async function () {
      return this.get("/dashboard/accounts/center");
    },

    health: async function () {
      // skipPrefix=false (default)  ->  <baseUrl>/api + "/health"  = /api/health
      // skipAuth=true to avoid sending token for a probe that works anonymously.
      return this.request("/health", { skipAuth: true });
    },
  };

  API.ApiError = ApiError;

  global.ICY_API = API;
})(window);
