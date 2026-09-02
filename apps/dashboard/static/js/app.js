/* ICYQuant Trading Dashboard - application logic.
 * Views: Overview / Strategy / Risk / Orders / Portfolio /
 *        Reconciliation / System / Alerts (all API-only). */
(function () {
  "use strict";

  const api = window.ICY_API;
  const state = {
    history: { equity: [], pnl: [], exposure: [] },
    refreshMs: 5000,
    backend: {
      // "unknown" | "probe" | "connected" | "degraded" | "disconnected"
      status: "unknown",
      lastCheckAt: null,
      lastData: null,
      lastError: null,
      consecutiveFails: 0,
      polling: false,
      intervalMs: 5000,
      timer: null,
    },
  };
  let refreshTimer = null;

  /* ==================================================================
   * Integration 001 - Backend connectivity via GET /api/health
   *
   * Responsibilities:
   *   - Periodically call api.health().
   *   - Translate result into topbar Backend badge + sidebar conn-dot.
   *   - Provide getBackendStatus() / onBackendStatusChange() primitives
   *     for downstream pages (in later Integration commits).
   * ================================================================== */

  function _setBackendBadge(status, text, extraClass) {
    var dot = document.getElementById("backend-dot");
    var label = document.getElementById("backend-text");
    if (!dot || !label) return;
    var dotClass = "health-dot " + (extraClass || "");
    var textClass = "health-text " + (extraClass || "");
    dot.className = dotClass;
    label.className = textClass;
    label.textContent = text || "Backend / 后端";
    label.title =
      "Status: " + (status || "unknown") +
      (state.backend.lastCheckAt ? "\nLast check: " + state.backend.lastCheckAt : "") +
      (state.backend.lastError ? "\nLast error: " + state.backend.lastError : "");
  }

  function renderBackendStatus() {
    var s = state.backend.status;
    if (s === "connected") {
      _setBackendBadge("connected", "Backend Connected / 已连接", "");
    } else if (s === "degraded") {
      _setBackendBadge("degraded", "Backend Degraded / 降级", "degraded");
    } else if (s === "disconnected") {
      _setBackendBadge("disconnected", "Backend Disconnected / 未连接", "down");
    } else if (s === "probe") {
      _setBackendBadge("probe", "Backend Probing / 探测中", "unknown");
    } else {
      _setBackendBadge("unknown", "Backend Unknown / 未知", "unknown");
    }
  }

  function _overallStatusFromHealth(health) {
    // Backend root /health (and /api/health mirror) returns:
    //   { status, version, timestamp, services: {name: {status, ...}}, bootstrap }
    // Prefer explicit snapshot["status"] when present.
    if (health && typeof health.status === "string") {
      var top = String(health.status).toLowerCase();
      if (top === "healthy" || top === "ok" || top === "up") return "connected";
      if (top === "degraded" || top === "warning") return "degraded";
      if (top === "down" || top === "unhealthy" || top === "error") return "disconnected";
    }
    // Fallback: aggregate services if no top-level status we recognize.
    if (health && health.services && typeof health.services === "object") {
      var names = Object.keys(health.services);
      if (!names.length) return "degraded";
      var down = 0, degraded = 0;
      names.forEach(function (n) {
        var svc = health.services[n] || {};
        var st = String(svc.status || svc.state || "").toLowerCase();
        if (!st) return;
        if (st === "down" || st === "unhealthy" || st === "error" || st === "offline") down++;
        else if (st === "degraded" || st === "warning" || st === "warn") degraded++;
      });
      if (down > 0) return "disconnected";
      if (degraded > 0) return "degraded";
      return "connected";
    }
    return "connected"; // 200 OK -> consider connected at minimum
  }

  async function probeBackendOnce() {
    state.backend.status = "probe";
    renderBackendStatus();
    try {
      var data = await api.health();
      state.backend.lastData = data || null;
      state.backend.lastError = null;
      state.backend.consecutiveFails = 0;
      state.backend.status = _overallStatusFromHealth(data);
    } catch (err) {
      state.backend.consecutiveFails = (state.backend.consecutiveFails || 0) + 1;
      state.backend.lastData = null;
      state.backend.lastError = (err && err.message) ? err.message : String(err || "");
      // First failure -> probe still transient; 2+ consecutive -> disconnected.
      // Also treat network/timeout kinds as "disconnected" regardless.
      var kind = err && err.kind;
      if (kind === "network" || kind === "timeout" || state.backend.consecutiveFails >= 2) {
        state.backend.status = "disconnected";
      } else {
        state.backend.status = "degraded";
      }
    } finally {
      state.backend.lastCheckAt = new Date().toLocaleString();
      renderBackendStatus();
      updateConnDot();
    }
  }

  function startBackendHealthPolling() {
    if (state.backend.polling) return;
    state.backend.polling = true;
    probeBackendOnce();
    state.backend.timer = setInterval(
      probeBackendOnce,
      state.backend.intervalMs
    );
  }

  function getBackendStatus() {
    return {
      status: state.backend.status,
      lastCheckAt: state.backend.lastCheckAt,
      lastData: state.backend.lastData,
      lastError: state.backend.lastError,
      consecutiveFails: state.backend.consecutiveFails,
      config: api && api.config ? api.config : null,
    };
  }

  // Expose for console QA: window.__ICY.backend.status()
  if (typeof window !== "undefined") {
    window.__ICY = window.__ICY || {};
    window.__ICY.backend = {
      status: getBackendStatus,
      probe: probeBackendOnce,
      configure: function (patch) { if (api.configure) api.configure(patch); return api.config; },
    };
  }

  /* ==================================================================
   * Formatting helpers
   * ================================================================== */

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmtNum(x) {
    const n = Number(x);
    if (!isFinite(n)) return "—";
    return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
  }

  function fmtMoney(x) {
    const n = Number(x);
    if (!isFinite(n)) return "—";
    const sign = n < 0 ? "-" : "";
    return sign + "$" + Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 2 });
  }

  function fmtPct(x) {
    const n = Number(x);
    if (!isFinite(n)) return "—";
    return (n * 100).toFixed(2) + "%";
  }

  function fmtTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d)) return "—";
    return d.toLocaleTimeString("en-US", { hour12: false });
  }

  function fmtDateTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d)) return "—";
    return d.toLocaleString("en-US", { hour12: false });
  }

  function pnlClass(x) {
    const n = Number(x);
    if (!isFinite(n) || n === 0) return "";
    return n > 0 ? "pos" : "neg";
  }

  /* ==================================================================
   * Badges
   * ================================================================== */

  const ORDER_STATUS_BADGE = {
    CREATED: ["badge-gray", "Pending / 待处理"],
    SUBMITTED: ["badge-blue", "Submitted / 已提交"],
    ACCEPTED: ["badge-blue", "Accepted / 已受理"],
    VALIDATED: ["badge-blue", "Validated / 已验证"],
    ROUTED: ["badge-blue", "Routed / 已路由"],
    ACKNOWLEDGED: ["badge-blue", "Acknowledged / 已确认"],
    PARTIALLY_FILLED: ["badge-amber", "Partial / 部分成交"],
    FILLED: ["badge-green", "Filled / 已成交"],
    REJECTED: ["badge-red", "Rejected / 已拒绝"],
    CANCELLED: ["badge-gray", "Cancelled / 已撤销"],
  };

  function badge(text, cls) {
    return '<span class="badge ' + cls + '"><span class="dot"></span>' + esc(text) + "</span>";
  }

  function statusText(status) {
    const hit = ORDER_STATUS_BADGE[status];
    return hit ? hit[1] : (status || "—");
  }

  function statusBadge(status) {
    const hit = ORDER_STATUS_BADGE[status] || ["badge-gray", statusText(status)];
    return badge(hit[1], hit[0]);
  }

  function decisionBadge(decision) {
    if (decision === "APPROVED") return badge("Approved / 通过", "badge-green");
    if (decision === "REJECTED") return badge("Rejected / 拒绝", "badge-red");
    if (decision === "BLOCKED") return badge("Blocked / 阻止", "badge-red");
    if (decision === "HALTED") return badge("Halted / 已停止", "badge-amber");
    return badge(esc(decision), "badge-gray");
  }

  function severityBadge(level) {
    const map = {
      CRITICAL: ["badge-red", "Critical / 严重"],
      HIGH: ["badge-amber", "High / 高"],
      WARNING: ["badge-blue", "Warning / 警告"],
      INFO: ["badge-green", "Info / 信息"],
    };
    const hit = map[level];
    return badge(hit ? hit[1] : level, hit ? hit[0] : "badge-gray");
  }

  function alertLevelZh(level) {
    const map = { CRITICAL: "严重", HIGH: "高", WARNING: "警告", INFO: "信息" };
    return (level || "") + " / " + (map[level] || "");
  }

  function healthBadge(status) {
    if (status === "UP") return badge("UP / 正常", "badge-green");
    if (status === "DOWN") return badge("DOWN / 异常", "badge-red");
    if (status === "DEGRADED") return badge("DEGRADED / 降级", "badge-amber");
    if (status === "READY") return badge("READY / 就绪", "badge-green");
    return badge(status || "UNKNOWN / 未知", "badge-gray");
  }

  function sideHtml(side) {
    const s = String(side || "").toUpperCase();
    if (s === "BUY") return '<span class="side-buy">BUY / 买</span>';
    if (s === "SELL") return '<span class="side-sell">SELL / 卖</span>';
    if (s === "LONG") return '<span class="side-buy">LONG / 多</span>';
    if (s === "SHORT") return '<span class="side-sell">SHORT / 空</span>';
    if (s === "FLAT") return '<span>FLAT / 空仓</span>';
    return '<span class="side-buy">' + esc(side) + "</span>";
  }

  function fmtMoneyCur(x, ccy) {
    const n = Number(x);
    if (!isFinite(n)) return "—";
    const sym = ccy === "CNY" ? "¥" : "$";
    const sign = n < 0 ? "-" : "";
    return sign + sym + Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 2 });
  }

  /* ==================================================================
   * Integration 016 — unified terminal conventions
   *
   * ⑥ Formatting: one vocabulary for money / percentage / signed P&L
   *    / price / quantity / bps / clock time across every page.
   *    $1,073,181 · +7.32% · -5.50% · 3.12 bps · 85.91% · 15:32:18
   * ① API states: one loader for Loading / Error / Offline / Empty so
   *    no page invents its own (white screens, divergent copy).
   * ④⑤ Terminal context: selected Account / Strategy survives page
   *    navigation (localStorage-backed) and feeds Orders / Positions
   *    filters instead of each page tracking its own account.
   * ================================================================== */

  // ── ⑥ Unified formatting helpers ───────────────────────────────
  /** Signed percentage for P&L-style values already in percent: +7.32% / -5.50% */
  function fmtSignedPct(x) {
    const n = Number(x);
    if (!isFinite(n)) return "—";
    return (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
  }
  /** Basis points: 3.12 bps */
  function fmtBps(x) {
    const n = Number(x);
    if (!isFinite(n)) return "—";
    return n.toFixed(2) + " bps";
  }
  /** Quantity: 1,200 (integer thousands separators) */
  function fmtQty(x) {
    const n = Number(x);
    if (!isFinite(n)) return "—";
    return Math.round(n).toLocaleString("en-US");
  }
  /** Clock time HH:MM:SS (today) or MM/DD HH:MM — the terminal-wide
   *  convention for tables and event timelines. */
  function fmtClock(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    const p2 = (v) => (v < 10 ? "0" : "") + v;
    const hh = p2(d.getHours()), mm = p2(d.getMinutes()), ss = p2(d.getSeconds());
    if (d.toDateString() === new Date().toDateString()) return hh + ":" + mm + ":" + ss;
    return p2(d.getMonth() + 1) + "/" + p2(d.getDate()) + " " + hh + ":" + mm;
  }

  // ── ① Unified API page-state block ─────────────────────────────
  /** One loader for every async page: Loading / Error / Offline /
   *  Empty. `st` is the page state ({ data, error }); kind=network
   *  errors surface explicitly as backend-unavailable. */
  function apiStateBlock(st, opts) {
    opts = opts || {};
    if (st && st.error) {
      const err = st.error;
      const offline = err && err.kind === "network";
      const title = offline
        ? "Backend unavailable / 后端不可用"
        : "Failed to load / 加载失败";
      const desc = offline
        ? "Cannot reach the ICYQuant API. Check the connection and retry. · 无法连接后端，请检查网络后重试。"
        : (err && err.message ? err.message : String(err));
      return UI.stateError(title, desc, "Retry", opts.retryAction || "state-retry");
    }
    if (!st || !st.data) {
      return UI.stateLoading(
        opts.loadingTitle || "Loading / 加载中",
        opts.loadingDesc || "Fetching latest data from the API…"
      );
    }
    if (opts.isEmpty && opts.isEmpty()) {
      return UI.stateEmpty(
        opts.emptyTitle || "No data available",
        opts.emptyDesc || "The backend reported no records for this view. / 暂无数据"
      );
    }
    return null;   // caller renders the hydrated page
  }

  // ── ③ Unified visibility-aware auto-refresh ─────────────────────
  /** One auto-refresh mechanism for live pages (Monitoring / Alerts):
   *  a 30s interval that pauses when the tab is hidden and stops when
   *  the user leaves the page. Historical / research pages (Backtest,
   *  Research) stay on-demand — no polling. */
  var AUTO_REFRESH_MS = 30000;
  var _autoRefreshTimers = {};   // key -> interval id

  function bindAutoRefresh(key, btnId, loadFn) {
    var btn = document.getElementById(btnId);
    if (!btn) return;
    if (_autoRefreshTimers[key]) {
      clearInterval(_autoRefreshTimers[key]);
      delete _autoRefreshTimers[key];
    }
    btn.addEventListener("click", function () {
      if (_autoRefreshTimers[key]) {
        clearInterval(_autoRefreshTimers[key]);
        delete _autoRefreshTimers[key];
        btn.textContent = "Auto 30s";
        btn.classList.remove("active");
      } else {
        _autoRefreshTimers[key] = setInterval(function () {
          if (document.visibilityState !== "visible") return;   // don't poll hidden tabs
          loadFn();
        }, AUTO_REFRESH_MS);
        btn.textContent = "Auto ON";
        btn.classList.add("active");
      }
    });
  }

  // ── ④⑤ Terminal-wide Account / Strategy context ────────────────
  var CTX_KEY = "icy_dash_ctx";
  var APP_CTX = { accountId: "ALL", strategyId: "ALL" };
  try {
    var _savedCtx = JSON.parse(localStorage.getItem(CTX_KEY) || "null");
    if (_savedCtx && _savedCtx.accountId) APP_CTX.accountId = _savedCtx.accountId;
    if (_savedCtx && _savedCtx.strategyId) APP_CTX.strategyId = _savedCtx.strategyId;
  } catch (e) { /* corrupted ctx — keep defaults */ }

  function ctxPersist() {
    try { localStorage.setItem(CTX_KEY, JSON.stringify(APP_CTX)); } catch (e) { /* ignore */ }
  }

  /** Switch the terminal-wide account: persisted, propagated to the
   *  Orders / Positions filters, reflected in the topbar selector. */
  function ctxSetAccount(accountId) {
    APP_CTX.accountId = accountId || "ALL";
    ctxPersist();
    ORDERS_FILTERS.account = APP_CTX.accountId;
    POSITIONS_FILTERS.account = APP_CTX.accountId;
    var sel = document.getElementById("ctx-account-select");
    if (sel) sel.value = APP_CTX.accountId;
    renderTopbarAccountName();
  }

  /** Switch the terminal-wide strategy context (research / trading). */
  function ctxSetStrategy(strategyId) {
    APP_CTX.strategyId = strategyId || "ALL";
    ctxPersist();
  }

  /** Topbar account chip text for the current context. */
  function renderTopbarAccountName() {
    var sel = document.getElementById("ctx-account-select");
    if (sel) sel.value = APP_CTX.accountId;
    var el = document.getElementById("acct-name");
    if (el) {
      el.textContent = APP_CTX.accountId === "ALL"
        ? "All Accounts"
        : APP_CTX.accountId;
    }
  }

  function connBadge(status) {
    if (status === "CONNECTED") return badge("Connected / 已连接", "badge-green");
    if (status === "ERROR") return badge("Error / 异常", "badge-red");
    if (status === "CONNECTING") return badge("Connecting / 连接中", "badge-amber");
    return badge(status || "—", "badge-gray");
  }

  function marketZh(label) {
    const map = { "A-Share": "A股", "Futures": "期货", "US Equity": "美股", "FX": "外汇" };
    return map[label] || "";
  }

  function accountsStrip(accounts) {
    if (!accounts || !accounts.by_market) return "";
    const cards = Object.keys(accounts.by_market)
      .map(function (label) {
        const a = accounts.by_market[label];
        const zh = marketZh(label);
        const marketLabel = zh ? label + " / " + zh : label;
        return (
          '<a class="card metric-card clickable" href="#/accounts">' +
          '<span class="metric-label">' + esc(marketLabel) + " · " + connBadge(a.status) + "</span>" +
          '<span class="metric-value">' + fmtMoneyCur(a.equity, a.currency) + "</span>" +
          '<span class="metric-sub">' + esc(a.currency) + " · 账户</span>" +
          "</a>"
        );
      })
      .join("");
    return (
      '<div class="grid grid-4 mb">' + cards + "</div>"
    );
  }

  function marketBadge(market) {
    const map = {
      "A-Share": "badge-blue",
      "Futures": "badge-amber",
      "US Equity": "badge-green",
      "FX": "badge-purple",
    };
    const zh = marketZh(market);
    const label = zh ? market + " / " + zh : market;
    return badge(label, map[market] || "badge-gray");
  }

  /* ==================================================================
   * SVG charts (zero dependency)
   * ================================================================== */

  function lineChart(values, opts) {
    opts = opts || {};
    const color = opts.color || "#00e5a0";
    const height = opts.height || 130;
    const id = opts.id || "g";
    if (!values || values.length < 2) {
      return '<div class="empty">No data yet / 暂无数据</div>';
    }
    const w = 640;
    const pad = 10;
    const min = Math.min.apply(null, values);
    const max = Math.max.apply(null, values);
    const range = max - min || 1;
    const pts = values.map(function (v, i) {
      const x = pad + (i / (values.length - 1)) * (w - 2 * pad);
      const y = height - pad - ((v - min) / range) * (height - 2 * pad);
      return x.toFixed(1) + "," + y.toFixed(1);
    });
    const area = pad + "," + (height - pad) + " " + pts.join(" ") + " " + (w - pad) + "," + (height - pad);
    const lastXY = pts[pts.length - 1].split(",");
    return (
      '<svg viewBox="0 0 ' + w + " " + height + '" preserveAspectRatio="none">' +
      '<defs><linearGradient id="areaGrad-' + id + '" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="' + color + '" stop-opacity="0.25"/>' +
      '<stop offset="100%" stop-color="' + color + '" stop-opacity="0"/>' +
      "</linearGradient></defs>" +
      '<line x1="' + pad + '" y1="' + height / 2 + '" x2="' + (w - pad) + '" y2="' + height / 2 + '" class="chart-grid-line"/>' +
      '<line x1="' + pad + '" y1="' + height / 3 + '" x2="' + (w - pad) + '" y2="' + height / 3 + '" class="chart-grid-line"/>' +
      '<line x1="' + pad + '" y1="' + (2 * height) / 3 + '" x2="' + (w - pad) + '" y2="' + (2 * height) / 3 + '" class="chart-grid-line"/>' +
      '<polygon points="' + area + '" fill="url(#areaGrad-' + id + ')"/>' +
      '<polyline points="' + pts.join(" ") + '" class="chart-line" style="stroke:' + color + '"/>' +
      '<circle cx="' + lastXY[0] + '" cy="' + lastXY[1] + '" r="3" class="chart-dot"/>' +
      "</svg>"
    );
  }

  function donutChart(items, opts) {
    opts = opts || {};
    const size = opts.size || 140;
    const total = items.reduce(function (s, it) { return s + Number(it.value || 0); }, 0);
    if (!total) return '<div class="empty">No positions / 暂无持仓</div>';
    let acc = 0;
    const segs = items.map(function (it) {
      const frac = Number(it.value || 0) / total;
      const seg =
        '<circle r="35" cx="60" cy="60" fill="none" stroke="' + (it.color || "#4da3ff") +
        '" stroke-width="12" pathLength="100" stroke-dasharray="' + (frac * 100) + " 100\"" +
        ' stroke-dashoffset="' + (-acc * 100) + '" transform="rotate(-90 60 60)"/>';
      acc += frac;
      return seg;
    });
    const legend = items
      .map(function (it) {
        return (
          '<span class="legend-item"><span class="legend-swatch" style="background:' + (it.color || "#4da3ff") + '"></span>' +
          esc(it.label) + " " + esc(it.value) +
          "</span>"
        );
      })
      .join("");
    return (
      '<div style="display:flex;align-items:center;gap:18px">' +
      '<svg viewBox="0 0 120 120" style="width:' + size + "px;height:" + size + 'px">' +
      '<circle r="35" cx="60" cy="60" fill="none" stroke="#1a2438" stroke-width="12"/>' +
      segs.join("") +
      '<text x="60" y="58" text-anchor="middle" fill="#e6edf7" font-size="13" font-weight="700" font-family="monospace">' +
      Math.round(total) + "</text>" +
      '<text x="60" y="72" text-anchor="middle" fill="#64748b" font-size="8">数量</text>' +
      "</svg>" +
      '<div class="chart-legend" style="flex-direction:column;gap:6px;margin:0">' + legend + "</div>" +
      "</div>"
    );
  }

  /* ==================================================================
   * Overview page
   * ================================================================== */

  function systemStrip(system) {
    const services = (system && system.services) || {};
    const defs = [
      ["API", "api"],
      ["Database / 数据库", "database"],
      ["Event Bus / 事件总线", "event-bus"],
      ["Strategy Runtime / 策略运行时", "strategy-runtime"],
      ["Risk Engine / 风控引擎", "risk-engine"],
      ["Order Engine / 订单引擎", "order-engine"],
      ["Execution Engine / 执行引擎", "execution-engine"],
      ["Position Ledger / 持仓账本", "position-ledger"],
      ["Reconciliation / 对账服务", "reconciliation"],
      ["Monitoring / 监控", "monitoring"],
    ];
    const chips = defs
      .map(function (d) {
        const s = services[d[1]];
        const up = s && s.status === "UP";
        return (
          '<span class="badge ' + (up ? "badge-green" : "badge-red") + '"><span class="dot"></span>' + esc(d[0]) + "</span>"
        );
      })
      .join(" ");
    return '<div class="card mb"><div class="card-title">System Status / 系统状态</div><div style="display:flex;flex-wrap:wrap;gap:8px">' + chips + "</div></div>";
  }

  async function pageOverview() {
    const data = await api.get("/dashboard/overview");
    const m = data.metrics || {};
    const r = data.risk || {};

    // accumulate chart history
    const hist = state.history;
    hist.equity.push(m.equity || 0);
    hist.pnl.push(m.today_pnl || 0);
    hist.exposure.push(m.exposure || 0);
    if (hist.equity.length > 60) {
      hist.equity.shift();
      hist.pnl.shift();
      hist.exposure.shift();
    }

    const isOperator = api.user && (api.user.role === "OPERATOR" || api.user.role === "ADMIN");
    const session = await api.get("/dashboard/session");

    const metric = function (label, value, cls, sub) {
      return (
        '<div class="card metric-card"><span class="metric-label">' + esc(label) + "</span>" +
        '<span class="metric-value ' + (cls || "") + '">' + value + "</span>" +
        (sub ? '<span class="metric-sub">' + esc(sub) + "</span>" : "") +
        "</div>"
      );
    };

    const metricsRow =
      '<div class="grid grid-4 mb">' +
      metric("Daily P&L / 当日盈亏", fmtMoney(m.today_pnl), pnlClass(m.today_pnl)) +
      metric("Equity / 总权益", fmtMoney(m.equity), "pos") +
      metric("Exposure / 风险敞口", fmtMoney(m.exposure)) +
      metric("Drawdown / 回撤", fmtMoney(m.drawdown)) +
      metric("Orders / 订单", fmtNum(m.orders)) +
      metric("Executions / 成交", fmtNum(m.executions)) +
      metric("Fill Rate / 成交率", fmtPct(m.fill_rate), "pos") +
      metric("Reject Rate / 拒绝率", fmtPct(m.reject_rate), m.reject_rate > 0 ? "neg" : "") +
      "</div>";

    const charts =
      '<div class="grid grid-main mb">' +
      '<div class="card"><div class="card-title">Equity Curve / 权益曲线</div>' +
      lineChart(hist.equity, { color: "#00e5a0", id: "eq" }) + "</div>" +
      '<div class="card"><div class="card-title">Exposure / 风险敞口</div>' +
      donutChart(
        (data.positions || []).map(function (p) {
          return { label: p.symbol, value: p.exposure || 0, color: "#4da3ff" };
        }),
        {}
      ) + "</div></div>";

    const recentOrders =
      '<div class="card mb"><div class="card-title">Recent Orders / 最近订单</div>' +
      (data.recent_orders && data.recent_orders.length
        ? '<div class="table-wrap"><table><thead><tr><th>Order ID / 订单编号</th><th>Symbol / 标的</th><th>Side / 方向</th><th>Qty / 数量</th><th>Status / 状态</th><th>Time / 时间</th></tr></thead><tbody>' +
          data.recent_orders
            .map(function (o) {
              return (
                '<tr class="clickable" data-href="#/orders/' + esc(o.order_id) + '">' +
                "<td class=\"mono\">" + esc(String(o.order_id).slice(0, 12)) + "</td>" +
                "<td>" + esc(o.symbol) + "</td>" +
                "<td>" + sideHtml(o.side) + "</td>" +
                "<td class=\"num\">" + fmtNum(o.quantity) + "</td>" +
                "<td>" + statusBadge(o.status) + "</td>" +
                "<td class=\"mono\">" + fmtTime(o.created_at) + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No orders yet / 暂无订单</div>') +
      "</div></div>";

    const recentDecisions =
      '<div class="card mb"><div class="card-title">Recent Risk Decisions / 最近风控决策</div>' +
      (data.recent_decisions && data.recent_decisions.length
        ? '<div class="table-wrap"><table><thead><tr><th>Symbol / 标的</th><th>Side / 方向</th><th>Qty / 数量</th><th>Decision / 决策</th><th>Reason / 原因</th><th>Time / 时间</th></tr></thead><tbody>' +
          data.recent_decisions
            .map(function (d) {
              return (
                "<tr>" +
                "<td>" + esc(d.symbol) + "</td>" +
                "<td>" + sideHtml(d.side) + "</td>" +
                "<td class=\"num\">" + fmtNum(d.quantity) + "</td>" +
                "<td>" + decisionBadge(d.decision) + "</td>" +
                "<td>" + esc(d.reason) + "</td>" +
                "<td class=\"mono\">" + fmtTime(d.timestamp) + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No decisions yet / 暂无决策</div>') +
      "</div></div>";

    const alertsHtml =
      '<div class="card mb"><div class="card-title">System Alerts / 系统告警</div>' +
      (data.alerts && data.alerts.length
        ? data.alerts
            .map(function (a) {
              return (
                '<div class="alert alert-' + String(a.level).toLowerCase() + '">' +
                '<span class="alert-level">' + esc(alertLevelZh(a.level)) + "</span>" +
                "<span>" + esc(a.source) + " · " + esc(a.message) + "</span>" +
                "</div>"
              );
            })
            .join("")
          : '<div class="empty">No alerts / 暂无告警</div>') +
      "</div>";

    const sessionCtl = isOperator
      ? '<div class="card mb"><div class="card-title">Session Control / 会话控制</div>' +
        '<div style="display:flex;gap:10px;align-items:center">' +
        (session.running
          ? '<button class="btn btn-danger" id="btn-session-stop">Stop Paper Session / 停止模拟会话</button>'
          : '<button class="btn btn-primary" id="btn-session-start">Start Paper Session / 启动模拟会话</button>') +
        '<span class="metric-sub">' +
        (session.running ? "● 运行中" : "○ 空闲") +
        (data.pipeline && data.pipeline.attached ? " · 管线已挂载" : "") +
        "</span></div></div>"
      : "";

    return (
      systemStrip(data.system) +
      accountsStrip(data.accounts) +
      metricsRow +
      charts +
      sessionCtl +
      alertsHtml +
      recentOrders +
      recentDecisions +
      '<div class="grid grid-2">' +
      '<div class="card"><div class="card-title">Risk Overview / 风控概览</div><div class="kv">' +
      "<dt>Decisions / 决策数</dt><dd>" + fmtNum(r.decisions) + "</dd>" +
      "<dt>Approved / 通过</dt><dd class=\"pos\">" + fmtNum(r.approved) + "</dd>" +
      "<dt>Rejected / 拒绝</dt><dd class=\"neg\">" + fmtNum(r.rejected) + "</dd>" +
      "<dt>Exposure / 敞口</dt><dd>" + fmtMoney(r.exposure) + "</dd>" +
      "<dt>Position Limit / 持仓限制</dt><dd>" + fmtNum(r.position_limit) + "</dd>" +
      "</div></div>" +
      '<div class="card"><div class="card-title">Pipeline / 管线</div><div class="kv">' +
      "<dt>Status / 状态</dt><dd>" + (data.pipeline && data.pipeline.attached ? '<span class="badge badge-green"><span class="dot"></span>Attached / 已挂载</span>' : '<span class="badge badge-gray"><span class="dot"></span>Idle / 空闲</span>') + "</dd>" +
      "<dt>Attached At / 挂载时间</dt><dd>" + fmtDateTime(data.pipeline && data.pipeline.attached_at) + "</dd>" +
      "<dt>Events / 事件数</dt><dd>" + fmtNum(data.pipeline && data.pipeline.events) + "</dd>" +
      "</div></div>" +
      "</div>"
    );
  }

  /* ==================================================================
   * Strategy pages
   * ================================================================== */

  async function pageStrategies() {
    const data = await api.get("/dashboard/strategies");
    const list = data.strategies || [];
    // factor candidates (read-only Gate outcomes; the Gate decides stages)
    let fc = { candidates: [], watch_list: [], families: null };
    try {
      fc = await api.get("/dashboard/factor-candidates");
    } catch (e) {
      /* research report absent - card simply hides its tables */
    }
    const stageBadge = function (stage) {
      if (stage === "PAPER") return badge("PAPER / 纸面交易", "badge-green");
      if (stage === "CANDIDATE") return badge("CANDIDATE / 候选", "badge-blue");
      return badge("WATCH / 观察", "badge-gray");
    };
    const factorCard =
      '<div class="card mb"><div class="card-title">Factor Candidates / 因子候选（Gate 决定阶段，只读展示）</div>' +
      '<div class="metric-sub">' +
      "De-correlation 后 " + (fc.families == null ? "—" : fc.families) + " 个独立因子族（阈值 " +
      esc(String(fc.decorrelation_threshold || 0.65)) + "）· Gate 结果来自 factor-real-d1 密封报告" +
      "</div>" +
      (fc.candidates && fc.candidates.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Alpha</th><th>Stage / 阶段</th><th>Gate-Passed Assets / 过闸资产</th><th>Family Rep / 族代表</th><th>Mean OOS IC</th><th>Mean OOS ICIR</th><th>Mean OOS Sharpe</th>" +
          "</tr></thead><tbody>" +
          fc.candidates
            .map(function (c) {
              return (
                "<tr><td><b>" + esc(c.alpha_id) + "</b></td>" +
                "<td>" + stageBadge(c.stage) + "</td>" +
                '<td class="mono">' + esc((c.assets || []).join(", ")) + "</td>" +
                "<td>" + (c.is_family_representative ? badge("Yes / 是", "badge-purple") : "—") + "</td>" +
                '<td class="num">' + esc(String(c.mean_oos_ic)) + "</td>" +
                '<td class="num">' + esc(String(c.mean_oos_icir)) + "</td>" +
                '<td class="num">' + esc(String(c.mean_oos_sharpe)) + "</td></tr>"
              );
            })
            .join("") +
          "</tbody></table></div>" +
          '<div class="metric-sub" style="margin-top:8px">UI 只展示阶段；能否进入下一阶段由 Gate 决定，不由本页控制。</div>'
        : '<div class="empty">No gate-passed factor candidates / 暂无过闸因子候选</div>') +
      "</div>";
    const watchCard =
      fc.watch_list && fc.watch_list.length
        ? '<div class="card mb"><div class="card-title">Watch List / 观察名单（未过 Gate，不进入交易）</div>' +
          '<div class="table-wrap"><table><thead><tr>' +
          "<th>Alpha</th><th>Stage</th><th>Family Rep / 族代表</th><th>Mean OOS IC</th><th>Mean OOS ICIR</th><th>Mean OOS Sharpe</th>" +
          "</tr></thead><tbody>" +
          fc.watch_list
            .map(function (c) {
              return (
                "<tr><td>" + esc(c.alpha_id) + "</td>" +
                "<td>" + stageBadge(c.stage) + "</td>" +
                "<td>" + (c.is_family_representative ? badge("Yes / 是", "badge-purple") : "—") + "</td>" +
                '<td class="num">' + esc(String(c.mean_oos_ic)) + "</td>" +
                '<td class="num">' + esc(String(c.mean_oos_icir)) + "</td>" +
                '<td class="num">' + esc(String(c.mean_oos_sharpe)) + "</td></tr>"
              );
            })
            .join("") +
          "</tbody></table></div></div>"
        : "";
    const strategyCard = list.length
      ? '<div class="card mb"><div class="card-title">Running Strategies / 运行中策略</div>' +
        '<div class="table-wrap"><table><thead><tr>' +
        "<th>Strategy / 策略</th><th>Status / 状态</th><th>Symbols / 标的</th><th>Signals / 信号</th><th>Approved / 通过</th><th>Rejected / 拒绝</th><th>Position / 持仓</th><th>P&amp;L / 盈亏</th>" +
        "</tr></thead><tbody>" +
        list
          .map(function (s) {
            return (
              '<tr class="clickable" data-href="#/strategies/' + esc(s.strategy_id) + '">' +
              "<td class=\"mono\">" + esc(s.strategy_id) + "</td>" +
              "<td>" + badge("Running / 运行中", "badge-green") + "</td>" +
              "<td>" + esc((s.symbols || []).join(", ")) + "</td>" +
              "<td class=\"num\">" + fmtNum(s.signals) + "</td>" +
              "<td class=\"num pos\">" + fmtNum(s.approved) + "</td>" +
              "<td class=\"num neg\">" + fmtNum(s.rejected) + "</td>" +
              "<td class=\"num\">" + fmtNum(s.position) + "</td>" +
              '<td class="num ' + pnlClass(s.pnl) + '">' + fmtMoney(s.pnl) + "</td>" +
              "</tr>"
            );
          })
          .join("") +
        "</tbody></table></div></div>"
      : '<div class="card mb"><div class="empty">No strategies running / 暂无运行中策略.<br><br><span class="metric-sub">Start a paper session or run a Golden Scenario to see live strategy activity. / 启动模拟会话或运行 Golden Scenario 即可看到实时策略活动。</span></div></div>';
    return strategyCard + factorCard + watchCard;
  }

  async function pageStrategyDetail(id) {
    const data = await api.get("/dashboard/strategies/" + encodeURIComponent(id));
    const sigTable =
      '<div class="card mb"><div class="card-title">Recent Signals / 最近信号</div>' +
      (data.signals && data.signals.length
        ? '<div class="table-wrap"><table><thead><tr><th>Signal / 信号</th><th>Symbol / 标的</th><th>Side / 方向</th><th>Qty / 数量</th><th>Price / 价格</th><th>Time / 时间</th></tr></thead><tbody>' +
          data.signals
            .map(function (s) {
              return (
                "<tr><td class=\"mono\">" + esc(s.signal_id) + "</td><td>" + esc(s.symbol) + "</td>" +
                "<td>" + sideHtml(s.side) + "</td><td class=\"num\">" + fmtNum(s.quantity) + "</td>" +
                "<td class=\"num\">" + fmtNum(s.price) + "</td><td class=\"mono\">" + fmtTime(s.timestamp) + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No signals / 暂无信号</div>') +
      "</div></div>";

    const riskTable =
      '<div class="card mb"><div class="card-title">Risk Decisions / 风控决策</div>' +
      (data.risk_decisions && data.risk_decisions.length
        ? '<div class="table-wrap"><table><thead><tr><th>Symbol / 标的</th><th>Side / 方向</th><th>Qty / 数量</th><th>Decision / 决策</th><th>Reason / 原因</th><th>Time / 时间</th></tr></thead><tbody>' +
          data.risk_decisions
            .map(function (d) {
              return (
                "<tr><td>" + esc(d.symbol) + "</td><td>" + sideHtml(d.side) + "</td>" +
                "<td class=\"num\">" + fmtNum(d.quantity) + "</td><td>" + decisionBadge(d.decision) + "</td>" +
                "<td>" + esc(d.reason) + "</td><td class=\"mono\">" + fmtTime(d.timestamp) + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No decisions / 暂无决策</div>') +
      "</div></div>";

    const orderTable =
      '<div class="card mb"><div class="card-title">Orders / 订单</div>' +
      (data.orders && data.orders.length
        ? '<div class="table-wrap"><table><thead><tr><th>Order ID / 订单编号</th><th>Symbol / 标的</th><th>Side / 方向</th><th>Qty / 数量</th><th>Status / 状态</th></tr></thead><tbody>' +
          data.orders
            .map(function (o) {
              return (
                '<tr class="clickable" data-href="#/orders/' + esc(o.order_id) + '"><td class="mono">' +
                esc(String(o.order_id).slice(0, 12)) + "</td><td>" + esc(o.symbol) + "</td>" +
                "<td>" + sideHtml(o.side) + "</td><td class=\"num\">" + fmtNum(o.quantity) + "</td>" +
                "<td>" + statusBadge(o.status) + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No orders / 暂无订单</div>') +
      "</div></div>";

    return (
      '<div class="card mb"><div class="kv" style="grid-template-columns:140px 1fr">' +
      "<dt>Strategy / 策略</dt><dd class=\"mono\">" + esc(data.strategy_id) + "</dd>" +
      "<dt>Status / 状态</dt><dd>" + badge(data.status === "RUNNING" ? "Running / 运行中" : (data.status || "—"), data.status === "RUNNING" ? "badge-green" : "badge-gray") + "</dd>" +
      "</div></div>" +
      sigTable +
      riskTable +
      orderTable
    );
  }

  /* ==================================================================
   * Risk page
   * ================================================================== */

  async function pageRisk() {
    const [data, enhanced, cfg] = await Promise.all([
      api.get("/dashboard/risk").catch(function () { return {}; }),
      api.get("/dashboard/risk-enhanced").catch(function () { return {}; }),
      api.get("/dashboard/config").catch(function () { return {}; }),
    ]);
    const m = data.metrics || {};
    const summary = enhanced.summary || {};
    const breaches = enhanced.breaches || [];
    const halted = enhanced.trading_halted || false;
    const positions = enhanced.positions || [];
    const r = cfg.risk || {};

    const metric = function (label, value, cls) {
      return (
        '<div class="card metric-card"><span class="metric-label">' + esc(label) + "</span>" +
        '<span class="metric-value sm ' + (cls || "") + '">' + value + "</span></div>"
      );
    };

    // System status badge
    const statusBadge = halted
      ? '<span class="badge badge-red">🔴 TRADING HALTED / 交易已暂停</span>'
      : '<span class="badge badge-green">🟢 SYSTEM NORMAL / 系统正常</span>';

    // Breach panel
    let breachHtml = "";
    if (breaches.length > 0) {
      breachHtml = breaches.map(function (b) {
        const isCrit = b.severity === "CRITICAL";
        return (
          '<div class="breach-panel ' + (isCrit ? 'breach-critical' : '') + '">' +
          '<div class="breach-header">' +
          '<span class="breach-rule">⚠ ' + esc(b.rule) + '</span>' +
          '<span class="badge ' + (isCrit ? 'badge-red' : 'badge-amber') + '">' + esc(b.severity) + '</span>' +
          '</div>' +
          '<div class="breach-body">' +
          '<span>Current: ' + (b.actual_pct || 0).toFixed(2) + '%</span>' +
          '<span>Limit: ' + (b.limit_pct || 0).toFixed(2) + '%</span>' +
          '</div>' +
          '<div class="breach-action">▶ ' + esc(b.action || "TRADING HALTED") + '</div>' +
          '</div>'
        );
      }).join("");
    }

    // Exposure breakdown
    const concEntries = Object.entries(summary.concentration || {});
    let exposureBars = "";
    if (concEntries.length > 0) {
      const maxConc = Math.max.apply(null, concEntries.map(function (e) { return e[1]; }));
      const colors = ["#4da3ff", "#00e5a0", "#ffb020", "#ff5c6c", "#a78bfa"];
      exposureBars = concEntries.map(function (e, i) {
        const pct = (e[1] || 0).toFixed(1);
        const width = maxConc > 0 ? (e[1] / maxConc * 100) : 0;
        return (
          '<div class="exposure-row">' +
          '<span class="exposure-sym">' + esc(e[0]) + '</span>' +
          '<div class="exposure-bar-wrap"><div class="exposure-bar" style="width:' + width + '%;background:' + colors[i % colors.length] + '"></div></div>' +
          '<span class="exposure-pct">' + pct + '%</span>' +
          '</div>'
        );
      }).join("");
    }

    const rulesCard = cfg
      ? '<div class="card mb"><div class="card-title">Risk Rules / 风控规则</div>' +
        '<div class="grid grid-3">' +
        metric("Max Daily Loss / 单日最大亏损", (r.max_daily_loss_pct || 0) + "%") +
        metric("Max Drawdown / 最大回撤限制", (r.max_drawdown_pct || 0) + "%") +
        metric("Risk Per Trade / 单笔风险", (r.risk_per_trade_pct || 0) + "%") +
        "</div></div>"
      : "";

    return (
      rulesCard +

      // System Status
      '<div class="card mb"><div class="card-title">System Status / 系统状态</div>' +
      '<div style="margin-bottom:10px">' + statusBadge + '</div>' +
      '<div class="grid grid-4">' +
      metric("Total Equity / 总权益", fmtMoney(summary.total_equity)) +
      metric("Gross Exposure / 总敞口", fmtMoney(summary.gross_exposure)) +
      metric("Net Exposure / 净敞口", fmtMoney(summary.net_exposure)) +
      metric("Position Count / 持仓数", fmtNum(summary.position_count)) +
      metric("VaR (95%, 1d) / 在险价值", summary.var_95 == null ? "—" : (summary.var_95 * 100).toFixed(2) + "%", "neg") +
      metric("Beta / 贝塔", summary.beta == null ? "—" : summary.beta.toFixed(3)) +
      "</div></div>" +

      // Breach Panel
      '<div class="card mb"><div class="card-title">Breach / 风控触发</div>' +
      (breaches.length > 0 ? breachHtml :
        '<div class="empty">✅ No active breaches / 无当前触发</div>') +
      '</div>' +

      // Exposure breakdown
      '<div class="card mb"><div class="card-title">Exposure / 敞口分布</div>' +
      (exposureBars || '<div class="empty">No positions / 无持仓</div>') +
      '</div>' +

      // Original risk decisions
      '<div class="grid grid-4 mb">' +
      metric("Risk Decisions / 风控决策", fmtNum(m.decisions)) +
      metric("Approved / 通过", fmtNum(m.approved), "pos") +
      metric("Rejected / 拒绝", fmtNum(m.rejected), "neg") +
      metric("Order Limit / 下单限制", fmtNum(m.order_limit)) +
      "</div>" +

      '<div class="card"><div class="card-title">Risk Decision Pipeline / 风控决策流水</div>' +
      (data.decisions && data.decisions.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Time / 时间</th><th>Strategy / 策略</th><th>Symbol / 标的</th><th>Side / 方向</th><th>Quantity / 数量</th><th>Decision / 决策</th><th>Reason / 原因</th><th>Risk Rule / 风控规则</th>" +
          "</tr></thead><tbody>" +
          data.decisions
            .map(function (d) {
              return (
                "<tr><td class=\"mono\">" + fmtTime(d.timestamp) + "</td>" +
                "<td class=\"mono\">" + esc(d.strategy_id || "—") + "</td>" +
                "<td>" + esc(d.symbol) + "</td><td>" + sideHtml(d.side) + "</td>" +
                "<td class=\"num\">" + fmtNum(d.quantity) + "</td>" +
                "<td>" + decisionBadge(d.decision) + "</td>" +
                "<td>" + esc(d.reason) + "</td>" +
                "<td>" + (d.decision === "APPROVED" ? "Risk Policy / 风控策略" : "Exposure / Quantity Limit / 敞口/数量限制") + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No risk decisions yet / 暂无风控决策</div>') +
      "</div></div>"
    );
  }

  /* ==================================================================
   * Orders pages
   * ================================================================== */

  async function pageOrders() {
    const data = await api.get("/dashboard/orders");
    const list = data.orders || [];
    return (
      '<div class="card"><div class="card-title">Orders / 订单 (' + fmtNum(list.length) + ")</div>" +
      (list.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Order ID / 订单编号</th><th>Account / 账户</th><th>Broker / 券商</th><th>Symbol / 标的</th><th>Side / 方向</th><th>Quantity / 数量</th><th>Price / 价格</th><th>Status / 状态</th><th>Created / 创建时间</th>" +
          "</tr></thead><tbody>" +
          list
            .map(function (o) {
              return (
                '<tr class="clickable" data-href="#/orders/' + esc(o.order_id) + '">' +
                "<td class=\"mono\">" + esc(String(o.order_id).slice(0, 12)) + "</td>" +
                "<td class=\"mono\">" + esc(o.account_id || "paper") + "</td>" +
                "<td class=\"mono\">" + esc(o.broker || "paper") + "</td>" +
                "<td>" + esc(o.symbol) + "</td>" +
                "<td>" + sideHtml(o.side) + "</td>" +
                "<td class=\"num\">" + fmtNum(o.quantity) + "</td>" +
                "<td class=\"num\">" + fmtNum(o.price) + "</td>" +
                "<td>" + statusBadge(o.status) + "</td>" +
                "<td class=\"mono\">" + fmtTime(o.created_at) + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No orders yet / 暂无订单</div>') +
      "</div></div>"
    );
  }

  async function pageOrderDetail(orderId) {
    const data = await api.get("/dashboard/orders/" + encodeURIComponent(orderId));
    const o = data.order || {};
    const isTrader = api.user && (api.user.role === "TRADER" || api.user.role === "ADMIN");
    const canCancel =
      isTrader && ["CREATED", "SUBMITTED", "ACCEPTED", "VALIDATED", "ROUTED", "ACKNOWLEDGED", "PARTIALLY_FILLED"].indexOf(o.status) >= 0;

    const flow =
      '<div class="card mb"><div class="card-title">Order Trace / 订单轨迹</div><div class="flow">' +
      '<span class="flow-step ' + (data.signal ? "done" : "") + '">Signal / 信号</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (data.risk_decision ? (data.risk_decision.approved ? "done" : "active") : "") + '">Risk Decision / 风控决策</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (data.order ? "done" : "") + '">Order / 订单</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (data.execution ? "done" : "") + '">Execution / 成交</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (data.position ? "done" : "") + '">Position / 持仓</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (data.ledger && data.ledger.length ? "done" : "") + '">Ledger / 账本</span>' +
      "</div></div>";

    const FIELD_LABELS = {
      id: "ID",
      symbol: "Symbol / 标的",
      side: "Side / 方向",
      quantity: "Quantity / 数量",
      price: "Price / 价格",
      time: "Time / 时间",
      approved: "Approved / 决策",
      reason: "Reason / 原因",
      strategy: "Strategy / 策略",
      status: "Status / 状态",
      filled: "Filled / 已成交",
      avg_fill_price: "Avg Fill Price / 成交均价",
      created: "Created / 创建时间",
      updated: "Updated / 更新时间",
      avg_price: "Avg Price / 平均价格",
      unrealized_pnl: "Unrealized P&L / 浮动盈亏",
      count: "Count / 数量",
      events: "Events / 事件",
    };

    const kv = function (title, obj) {
      const rows = Object.keys(obj)
        .map(function (k) {
          return "<dt>" + esc(FIELD_LABELS[k] || k) + "</dt><dd>" + esc(obj[k]) + "</dd>";
        })
        .join("");
      return '<div class="card trace-card ' + title.toLowerCase().replace(/[^a-z]/g, "") + ' mb"><div class="trace-head">' + esc(title) + "</div><div class=\"kv\">" + rows + "</div></div>";
    };

    let blocks = "";
    if (data.signal) blocks += kv("Signal / 信号", {
      id: data.signal.signal_id,
      symbol: data.signal.symbol,
      side: data.signal.side,
      quantity: data.signal.quantity,
      price: data.signal.price,
      time: fmtTime(data.signal.timestamp),
    });
    if (data.risk_decision) blocks += kv("Risk Decision / 风控决策", {
      approved: data.risk_decision.approved ? "Yes / 是" : "No / 否",
      reason: data.risk_decision.reason || "—",
    });
    blocks += kv("Order / 订单", {
      id: o.order_id,
      strategy: o.strategy_id || "—",
      symbol: o.symbol,
      side: o.side,
      quantity: o.quantity,
      price: o.price,
      status: statusText(o.status),
      filled: o.filled_quantity || 0,
      avg_fill_price: o.average_fill_price || "—",
      created: fmtTime(o.created_at),
      updated: fmtTime(o.updated_at),
    });
    if (data.execution) blocks += kv("Execution / 成交", {
      quantity: data.execution.quantity,
      price: data.execution.price,
      time: fmtTime(data.execution.timestamp),
    });
    if (data.position) blocks += kv("Position / 持仓", {
      symbol: data.position.symbol,
      quantity: data.position.quantity,
      avg_price: data.position.avg_price,
      unrealized_pnl: fmtMoney(data.position.unrealized_pnl),
    });
    if (data.ledger && data.ledger.length) {
      blocks += kv("Ledger Events / 账本事件", {
        count: data.ledger.length,
        events: data.ledger.map(function (e) { return e.event_type; }).join(", "),
      });
    }

    const cancelBtn = canCancel
      ? '<button class="btn btn-danger" id="btn-cancel-order" data-order="' + esc(o.order_id) + '">Cancel Order / 撤单</button>'
      : "";

    return (
      flow +
      blocks +
      (cancelBtn ? '<div class="mt">' + cancelBtn + "</div>" : "")
    );
  }

  /* ==================================================================
   * Portfolio page
   * ================================================================== */

  async function pagePortfolio() {
    const data = await api.get("/dashboard/portfolio");
    const s = data.summary || {};
    const hist = state.history;
    const metric = function (label, value, cls) {
      return (
        '<div class="card metric-card"><span class="metric-label">' + esc(label) + "</span>" +
        '<span class="metric-value sm ' + (cls || "") + '">' + value + "</span></div>"
      );
    };
    const exposureEntries = Object.keys(data.market_exposure || {}).map(function (k) {
      return { label: k, value: data.market_exposure[k] };
    });
    const colorMap = ["#4da3ff", "#00e5a0", "#ffb020", "#a7fb9a"];
    return (
      '<div class="grid grid-4 mb">' +
      metric("Total Equity / 总权益 (USD)", fmtMoney(s.total_equity_usd), "pos") +
      metric("Total Cash / 现金 (USD)", fmtMoney(s.total_cash_usd)) +
      metric("Gross Exposure / 总敞口 (USD)", fmtMoney(s.gross_exposure_usd)) +
      metric("Net Exposure / 净敞口 (USD)", fmtMoney(s.net_exposure_usd)) +
      metric("Daily P&L / 当日盈亏 (USD)", fmtMoney(s.daily_pnl_usd), pnlClass(s.daily_pnl_usd)) +
      metric("Total P&L / 累计盈亏 (USD)", fmtMoney(s.total_pnl_usd), pnlClass(s.total_pnl_usd)) +
      metric("Drawdown / 回撤 (USD)", fmtMoney(s.drawdown_usd)) +
      metric("Accounts / 账户", fmtNum((data.accounts || []).length)) +
      "</div>" +
      '<div class="grid grid-2 mb">' +
      '<div class="card"><div class="card-title">Market Exposure / 市场敞口</div>' +
      donutChart(
        exposureEntries.map(function (e, i) {
          return { label: e.label, value: e.value, color: colorMap[i % colorMap.length] };
        }),
        {}
      ) + "</div>" +
      '<div class="card"><div class="card-title">Equity Curve / 权益曲线</div>' +
      lineChart(hist.equity, { color: "#00e5a0", id: "pe" }) + "</div>" +
      "</div>" +
      '<div class="card"><div class="card-title">Global Positions / 全局持仓 (' + fmtNum((data.positions || []).length) + ")</div>" +
      (data.positions && data.positions.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Account / 账户</th><th>Market / 市场</th><th>Symbol / 标的</th><th>Side / 方向</th><th>Quantity / 数量</th><th>Avg Price / 平均价格</th><th>Last / 最新价</th><th>Market Value / 市值</th><th>Unrealized P&amp;L / 浮动盈亏</th><th>Exposure / 敞口</th><th>Ccy / 币种</th>" +
          "</tr></thead><tbody>" +
          data.positions
            .map(function (p) {
              return (
                "<tr>" +
                '<td class="mono">' + esc(p.account_id) + "</td>" +
                "<td>" + marketBadge(p.market_label) + "</td>" +
                "<td>" + esc(p.symbol) + "</td>" +
                "<td>" + sideHtml(p.side) + "</td>" +
                "<td class=\"num\">" + fmtNum(p.quantity) + "</td>" +
                "<td class=\"num\">" + fmtNum(p.average_price) + "</td>" +
                "<td class=\"num\">" + fmtNum(p.last_price) + "</td>" +
                "<td class=\"num\">" + fmtMoneyCur(p.market_value, p.currency) + "</td>" +
                '<td class="num ' + pnlClass(p.unrealized_pnl) + '">' + fmtMoneyCur(p.unrealized_pnl, p.currency) + "</td>" +
                "<td class=\"num\">" + fmtMoneyCur(p.exposure, p.currency) + "</td>" +
                "<td class=\"mono\">" + esc(p.currency) + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No positions / 暂无持仓</div>') +
      "</div></div>"
    );
  }

  /* ==================================================================
   * Multi-panel synchronized chart (4 sub-charts on shared time axis)
   * ================================================================== */

  function multiPanelChart(panels, opts) {
    /* panels: [{symbol, dates[], closes[], z_scores[], positions[], signals[], equity_line[]}]
       opts: {height, title}
       Renders 4 synchronized sub-charts: Price + Signals, Z-Score, Position, Equity. */
    opts = opts || {};
    if (!panels || !panels.length) {
      return '<div class="empty">No chart data / 暂无图表数据</div>';
    }
    const panel = panels[0]; // primary panel for time axis
    const W = 900;
    const PAD_L = 56, PAD_R = 12;
    const H_PRICE = 140, H_Z = 100, H_POS = 70, H_EQ = 120;
    const GAP = 8;
    const totalH = H_PRICE + H_Z + H_POS + H_EQ + GAP * 3 + 24;

    const dates = panel.dates || [];
    const closes = panel.closes || [];
    const zScores = panel.z_scores || [];
    const positions = panel.positions || [];
    const signals = panel.signals || [];
    const eqLine = panel.equity_line || [];
    const n = dates.length;
    if (n < 2) return '<div class="empty">Insufficient data / 数据不足</div>';

    const X = function(i) { return PAD_L + (i / (n - 1)) * (W - PAD_L - PAD_R); };

    // --- Price sub-chart ---
    let priceVals = closes.map(function(v) { return v != null ? v : 0; });
    let pLo = Math.min.apply(null, priceVals);
    let pHi = Math.max.apply(null, priceVals);
    let pRange = pHi - pLo || 1;
    pLo -= pRange * 0.08; pHi += pRange * 0.08;
    const Yp = function(v) { return H_PRICE - 10 - ((v - pLo) / (pHi - pLo)) * (H_PRICE - 20); };
    let pricePath = "";
    for (let i = 0; i < n; i++) {
      const y = closes[i] != null ? Yp(closes[i]) : 0;
      if (i === 0) pricePath += "M"; else pricePath += " L";
      pricePath += X(i).toFixed(1) + "," + y.toFixed(1);
    }

    // Signal markers on price chart
    let sigMarkers = "";
    if (signals.length) {
      const sigDates = {};
      signals.forEach(function(s) { sigDates[s.date] = sigDates[s.date] || []; sigDates[s.date].push(s); });
      for (let i = 0; i < n; i++) {
        if (sigDates[dates[i]]) {
          sigDates[dates[i]].forEach(function(s) {
            if (s.price) {
              const cx = X(i), cy = Yp(s.price);
              const isBuy = s.side === "BUY";
              sigMarkers += '<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) +
                '" r="4" fill="' + (isBuy ? "#00e5a0" : "#ff5c6c") +
                '" stroke="#0a0e17" stroke-width="1.5"/>';
            }
          });
        }
      }
    }

    // --- Z-Score sub-chart ---
    let zVals = zScores.map(function(v) { return v != null ? v : 0; });
    let zLo = Math.min.apply(null, zVals.concat([-2, 2]));
    let zHi = Math.max.apply(null, zVals.concat([-2, 2]));
    if (zHi - zLo < 0.5) { zLo -= 0.5; zHi += 0.5; }
    const Yz = function(v) { return H_Z - 10 - ((v - zLo) / (zHi - zLo)) * (H_Z - 20); };
    let zPath = "";
    for (let i = 0; i < n; i++) {
      const y = zScores[i] != null ? Yz(zScores[i]) : 0;
      if (i === 0) zPath += "M"; else zPath += " L";
      zPath += X(i).toFixed(1) + "," + y.toFixed(1);
    }

    // --- Position sub-chart ---
    const Ypos = function(v) { return H_POS - 10 - (v * (H_POS - 20)); };
    let posBars = "";
    for (let i = 0; i < n; i++) {
      const v = positions[i] || 0;
      if (v !== 0) {
        const y0 = Ypos(0);
        const y1 = Ypos(v);
        posBars += '<line x1="' + X(i).toFixed(1) + '" y1="' + y0.toFixed(1) +
          '" x2="' + X(i).toFixed(1) + '" y2="' + y1.toFixed(1) +
          '" stroke="#4da3ff" stroke-width="3"/>';
      }
    }

    // --- Equity sub-chart ---
    let eqVals = eqLine.map(function(v) { return v != null ? v : 0; });
    let eLo = Math.min.apply(null, eqVals.filter(function(v) { return v > 0; }));
    let eHi = Math.max.apply(null, eqVals);
    if (!isFinite(eLo)) { eLo = eHi * 0.9; }
    let eRange = eHi - eLo || 1;
    eLo -= eRange * 0.06; eHi += eRange * 0.06;
    const Ye = function(v) { return H_EQ - 10 - ((v - eLo) / (eHi - eLo)) * (H_EQ - 20); };
    let eqPath = "";
    for (let i = 0; i < n; i++) {
      if (eqLine[i] != null) {
        const y = Ye(eqLine[i]);
        if (eqPath === "" || eqLine[i-1] == null) eqPath += "M"; else eqPath += " L";
        eqPath += X(i).toFixed(1) + "," + y.toFixed(1);
      }
    }

    // Grid lines & axis labels for each sub-chart
    function gridLines(height, yFunc, lo, hi, fmt) {
      let g = "";
      for (let gv = 0; gv <= 4; gv++) {
        const v = lo + gv * (hi - lo) / 4;
        const y = yFunc(v);
        g += '<line x1="' + PAD_L + '" y1="' + y.toFixed(1) +
          '" x2="' + (W - PAD_R) + '" y2="' + y.toFixed(1) + '" class="chart-grid-line"/>';
        g += '<text x="' + (PAD_L - 6) + '" y="' + (y + 3.5).toFixed(1) +
          '" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">' +
          (fmt ? fmt(v) : v.toFixed(1)) + '</text>';
      }
      return g;
    }

    // Y-axis label widths
    const pFmt = function(v) { return "$" + Math.round(v).toLocaleString(); };
    const eFmt = function(v) { return "$" + Math.round(v / 1000) + "k"; };

    // X-axis labels (shared)
    let xLabels = "";
    [0, Math.floor(n * 0.25), Math.floor(n * 0.5), Math.floor(n * 0.75), n - 1].forEach(function(i) {
      if (i < n) {
        xLabels += '<text x="' + X(i).toFixed(1) + '" y="' + (totalH - 6) +
          '" fill="#64748b" font-size="9" text-anchor="middle" font-family="monospace">' +
          dates[i].slice(0, 7) + '</text>';
      }
    });

    // Baseline for equity
    let eqBaseline = "";
    const initialCap = eqLine.find(function(v) { return v != null; });
    if (initialCap && initialCap > 0) {
      eqBaseline = '<line x1="' + PAD_L + '" y1="' + Ye(initialCap).toFixed(1) +
        '" x2="' + (W - PAD_R) + '" y2="' + Ye(initialCap).toFixed(1) +
        '" stroke="#33415a" stroke-dasharray="4 4"/>';
    }

    return (
      '<div class="chart-panel-wrap">' +
      '<svg viewBox="0 0 ' + W + ' ' + totalH + '" style="width:100%;height:' + totalH + 'px">' +
      // Price chart
      '<text x="' + PAD_L + '" y="12" fill="#94a3b8" font-size="10" font-weight="600">Price / ' + esc(panel.symbol) + ' / 价格</text>' +
      gridLines(H_PRICE, Yp, pLo, pHi, pFmt) +
      '<path d="' + pricePath + '" fill="none" stroke="#4da3ff" stroke-width="1.5"/>' +
      sigMarkers +
      // Z-Score chart
      '<text x="' + PAD_L + '" y="' + (H_PRICE + GAP + 12) + '" fill="#94a3b8" font-size="10" font-weight="600">Alpha021 Z-Score / Z分数</text>' +
      gridLines(H_Z, Yz, zLo, zHi) +
      '<line x1="' + PAD_L + '" y1="' + Yz(0).toFixed(1) + '" x2="' + (W - PAD_R) + '" y2="' + Yz(0).toFixed(1) + '" class="chart-grid-line" stroke-width="0.5" stroke-dasharray="2 2"/>' +
      '<path d="' + zPath + '" fill="none" stroke="#a78bfa" stroke-width="1.2"/>' +
      // Position chart
      '<text x="' + PAD_L + '" y="' + (H_PRICE + GAP + H_Z + GAP + 12) + '" fill="#94a3b8" font-size="10" font-weight="600">Position / 仓位</text>' +
      '<line x1="' + PAD_L + '" y1="' + Ypos(0).toFixed(1) + '" x2="' + (W - PAD_R) + '" y2="' + Ypos(0).toFixed(1) + '" class="chart-grid-line"/>' +
      posBars +
      // Equity chart
      '<text x="' + PAD_L + '" y="' + (H_PRICE + GAP + H_Z + GAP + H_POS + GAP + 12) + '" fill="#94a3b8" font-size="10" font-weight="600">Portfolio Equity / 组合净值</text>' +
      gridLines(H_EQ, Ye, eLo, eHi, eFmt) +
      eqBaseline +
      '<path d="' + eqPath + '" fill="none" stroke="#00e5a0" stroke-width="1.5"/>' +
      // X-axis labels
      xLabels +
      '</svg>' +
      '</div>'
    );
  }

  /* ==================================================================
   * Drawdown chart
   * ================================================================== */

  function drawdownChart(ddValues, dates, height) {
    height = height || 100;
    if (!ddValues || !ddValues.length) {
      return '<div class="empty">No drawdown data / 无回撤数据</div>';
    }
    const W = 900, PAD_L = 56, PAD_R = 12;
    const n = ddValues.length;
    const lo = Math.min.apply(null, ddValues.concat([0]));
    const hi = 0;
    const Y = function(v) { return height - 10 - ((v - lo) / (hi - lo || 1)) * (height - 20); };
    const X = function(i) { return PAD_L + (i / Math.max(n - 1, 1)) * (W - PAD_L - PAD_R); };
    let areaPath = "M" + X(0).toFixed(1) + "," + Y(0).toFixed(1);
    for (let i = 0; i < n; i++) {
      areaPath += " L" + X(i).toFixed(1) + "," + Y(ddValues[i]).toFixed(1);
    }
    areaPath += " L" + X(n - 1).toFixed(1) + "," + Y(0).toFixed(1) + " Z";
    let gridLines = "";
    for (let g = 0; g <= 3; g++) {
      const v = lo + g * (hi - lo) / 3;
      gridLines += '<line x1="' + PAD_L + '" y1="' + Y(v).toFixed(1) +
        '" x2="' + (W - PAD_R) + '" y2="' + Y(v).toFixed(1) + '" class="chart-grid-line"/>';
      gridLines += '<text x="' + (PAD_L - 6) + '" y="' + (Y(v) + 3.5).toFixed(1) +
        '" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">' +
        v.toFixed(1) + '%</text>';
    }
    return (
      '<svg viewBox="0 0 ' + W + ' ' + height + '" style="width:100%;height:' + height + 'px">' +
      '<defs><linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="#ff5c6c" stop-opacity="0.05"/>' +
      '<stop offset="100%" stop-color="#ff5c6c" stop-opacity="0.3"/>' +
      '</linearGradient></defs>' +
      gridLines +
      '<path d="' + areaPath + '" fill="url(#ddGrad)"/>' +
      '<polyline points="' + ddValues.map(function(v, i) { return X(i).toFixed(1) + "," + Y(v).toFixed(1); }).join(" ") + '" fill="none" stroke="#ff5c6c" stroke-width="1.2"/>' +
      '</svg>'
    );
  }

  /* ==================================================================
   * Monthly return heatmap
   * ================================================================== */

  function monthlyHeatmap(monthlyData) {
    if (!monthlyData || !monthlyData.length) {
      return '<div class="empty">No monthly data / 无月度数据</div>';
    }
    let months = [];
    monthlyData.forEach(function(m) { months.push(m.month); });
    const yearMap = {};
    monthlyData.forEach(function(m) {
      const year = m.month.slice(0, 4);
      const month = parseInt(m.month.slice(5, 7), 10);
      if (!yearMap[year]) yearMap[year] = {};
      yearMap[year][month] = m.return_pct;
    });
    const years = Object.keys(yearMap).sort();
    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    let rows = "";
    years.forEach(function(year) {
      let cells = "";
      for (let m = 1; m <= 12; m++) {
        const val = yearMap[year][m];
        if (val !== undefined) {
          const isPos = val >= 0;
          const intensity = Math.min(Math.abs(val) / 5, 1);
          const bg = isPos
            ? 'rgba(0, 229, 160,' + (0.25 + intensity * 0.55) + ')'
            : 'rgba(255, 92, 108,' + (0.25 + intensity * 0.55) + ')';
          cells += '<td style="background:' + bg + ';text-align:center;font-size:11px;' +
            (isPos ? 'color:#00e5a0' : 'color:#ff5c6c') + '">' +
            val.toFixed(1) + '%</td>';
        } else {
          cells += '<td style="background:#16213a;text-align:center;color:#33415a;font-size:11px">—</td>';
        }
      }
      rows += '<tr><td style="color:#94a3b8;padding:4px 10px;font-size:11px">' + year + '</td>' + cells + '</tr>';
    });
    let headers = '<th style="width:60px"></th>';
    monthNames.forEach(function(m) { headers += '<th style="text-align:center;font-size:10px;padding:4px">' + m + '</th>'; });
    return '<div class="heatmap-wrap"><table style="border-collapse:collapse;width:100%"><thead><tr>' + headers + '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  }

  /* ==================================================================
   * Factor paper trading page (Alpha021, static research replay)
   * ================================================================== */

  function factorStaticLine(points, opts) {
    opts = opts || {};
    const color = opts.color || "#00e5a0";
    const height = opts.height || 170;
    if (!points || points.length < 2) {
      return '<div class="empty">No data yet / 暂无数据</div>';
    }
    const w = 920, padL = 58, padR = 14, padT = 12, padB = 22;
    const vals = points.map(function (p) { return p.y; });
    let lo = Math.min.apply(null, vals.concat([opts.baseline || Infinity]));
    let hi = Math.max.apply(null, vals.concat([opts.baseline || -Infinity]));
    const range0 = hi - lo || 1;
    lo -= range0 * 0.06; hi += range0 * 0.06;
    const X = function (i) { return padL + (i / (points.length - 1)) * (w - padL - padR); };
    const Y = function (v) { return padT + (1 - (v - lo) / (hi - lo)) * (height - padT - padB); };
    let s =
      '<svg viewBox="0 0 ' + w + " " + height + '" style="width:100%;height:' + height + 'px">';
    for (let g = 0; g <= 4; g++) {
      const v = lo + (g * (hi - lo)) / 4;
      s +=
        '<line x1="' + padL + '" y1="' + Y(v).toFixed(1) + '" x2="' + (w - padR) + '" y2="' + Y(v).toFixed(1) + '" class="chart-grid-line"/>' +
        '<text x="' + (padL - 6) + '" y="' + (Y(v) + 3.5).toFixed(1) + '" fill="#64748b" font-size="10" text-anchor="end" font-family="monospace">' + (opts.fmt ? opts.fmt(v) : v.toFixed(0)) + "</text>";
    }
    if (opts.baseline !== undefined && opts.baseline > lo && opts.baseline < hi) {
      s += '<line x1="' + padL + '" y1="' + Y(opts.baseline).toFixed(1) + '" x2="' + (w - padR) + '" y2="' + Y(opts.baseline).toFixed(1) + '" stroke="#33415a" stroke-dasharray="4 4"/>';
    }
    const pts = points.map(function (p, i) { return X(i).toFixed(1) + "," + Y(p.y).toFixed(1); });
    s += '<polyline points="' + pts.join(" ") + '" fill="none" stroke="' + color + '" stroke-width="1.6"/>';
    [0, Math.floor(points.length / 2), points.length - 1].forEach(function (i) {
      s += '<text x="' + X(i).toFixed(1) + '" y="' + (height - 6) + '" fill="#64748b" font-size="10" text-anchor="middle">' + esc(points[i].x) + "</text>";
    });
    return s + "</svg>";
  }

  async function pageFactor() {
    const data = await api.get("/dashboard/factor");
    if (data.error) {
      return (
        '<div class="card"><div class="card-title">Factor Paper / 因子纸面交易</div>' +
        '<div class="alert alert-warning" style="margin:0">' +
        "Real daily data unavailable / 真实日频数据不可用<br>" +
        '<span class="metric-sub">' + esc(data.error) + "</span></div></div>"
      );
    }
    const m = data.meta || {};
    const trades = data.trades || [];
    const eq = data.equity || [];
    const summary = data.summary || [];
    const metric = function (label, value, cls) {
      return (
        '<div class="card metric-card"><span class="metric-label">' + esc(label) + "</span>" +
        '<span class="metric-value sm ' + (cls || "") + '">' + value + "</span></div>"
      );
    };
    const outcomeBadge = function (o) {
      if (o === "FILLED") return badge("Filled / 成交", "badge-green");
      if (o === "REJECTED") return badge("Rejected / 拒单", "badge-amber");
      return badge("Error / 错误", "badge-red");
    };
    const cumPnl = trades
      .filter(function (r) { return r.outcome === "FILLED"; })
      .map(function (r) { return { x: r.date.slice(5), y: r.cum_realized_pnl }; });

    return (
      '<div class="card mb"><div class="card-title">' + esc(m.alpha_id || "Alpha") +
      " · Factor Paper Trading / 因子纸面交易</div>" +
      '<div class="metric-sub">' + esc((m.symbols || []).join(" / ")) + " · 真实日频 · " +
      esc(m.period || "") + " · 定价：真实收盘 ± 3 bps · 初始资金 $1,000,000 · 多头映射（+1 → 100 股）</div></div>" +
      '<div class="grid grid-4 mb">' +
      metric("Final Equity / 期末净值", fmtMoney(m.equity_final)) +
      metric("Return / 收益率", (m.return_pct || 0).toFixed(2) + "%", (m.return_pct >= 0 ? "pos" : "neg")) +
      metric("Realized P&L / 已实现", fmtMoney(m.realized), pnlClass(m.realized)) +
      metric("Unrealized P&L / 浮动", fmtMoney(m.unrealized), pnlClass(m.unrealized)) +
      metric("Max Drawdown / 最大回撤", (m.maxdd_pct || 0).toFixed(1) + "%", "neg") +
      metric("Closed / Win Rate / 平仓胜率", fmtNum(m.closed_trips) + " 笔 · " + (m.win_rate || 0).toFixed(0) + "%") +
      metric("Signals / Filled / 信号成交", fmtNum(m.signals) + " / " + fmtNum(m.filled)) +
      metric("Rejected / Error / 拒单错误", fmtNum(m.rejected) + " / " + fmtNum(m.errored)) +
      "</div>" +
      '<div class="grid grid-2 mb">' +
      '<div class="card"><div class="card-title">Equity Curve / 净值曲线（真实收盘 mark-to-market）</div>' +
      factorStaticLine(eq.map(function (r) { return { x: r.date.slice(0, 7), y: r.equity }; }),
        { color: "#4da3ff", baseline: 1000000, fmt: function (v) { return "$" + Math.round(v / 1000) + "k"; } }) +
      "</div>" +
      '<div class="card"><div class="card-title">Cumulative Realized P&L / 累计已实现盈亏</div>' +
      factorStaticLine(cumPnl, { color: "#00e5a0", baseline: 0, fmt: function (v) { return "$" + Math.round(v / 1000) + "k"; } }) +
      "</div>" +
      "</div>" +
      '<div class="card mb"><div class="card-title">Per-Symbol Summary / 分资产汇总</div>' +
      '<div class="table-wrap"><table><thead><tr>' +
      "<th>Symbol / 资产</th><th>Signals / 信号</th><th>Filled / 成交</th><th>Rejected / 拒单</th><th>Error / 错误</th>" +
      "<th>Realized / 已实现</th><th>Final Pos / 期末仓位</th><th>Avg Cost / 成本</th><th>Last / 最新收盘</th><th>Unrealized / 浮动</th>" +
      "</tr></thead><tbody>" +
      summary.map(function (r) {
        return (
          "<tr>" +
          '<td class="mono">' + esc(r.symbol) + "</td>" +
          '<td class="num">' + fmtNum(r.signals) + "</td>" +
          '<td class="num">' + fmtNum(r.filled) + "</td>" +
          '<td class="num">' + fmtNum(r.rejected) + "</td>" +
          '<td class="num">' + fmtNum(r.errored) + "</td>" +
          '<td class="num ' + pnlClass(r.realized_pnl) + '">' + fmtMoney(r.realized_pnl) + "</td>" +
          '<td class="num">' + esc(String(r.final_position)) + "</td>" +
          '<td class="num mono">' + esc(String(r.avg_cost)) + "</td>" +
          '<td class="num mono">' + esc(String(r.last_close)) + "</td>" +
          '<td class="num ' + pnlClass(r.unrealized_pnl) + '">' + fmtMoney(r.unrealized_pnl) + "</td>" +
          "</tr>"
        );
      }).join("") +
      "</tbody></table></div></div>" +
      '<div class="card"><div class="card-title">Trade Log / 交易明细（' + trades.length + "，最新在前）</div>" +
      '<div class="table-wrap" style="max-height:480px;overflow:auto"><table><thead><tr>' +
      "<th>#</th><th>Date / 日期</th><th>Symbol / 资产</th><th>Side / 方向</th><th>Close / 收盘</th><th>Outcome / 结果</th>" +
      "<th>Exec / 成交价</th><th>Pos / 仓位</th><th>P&L / 平仓盈亏</th><th>Cum / 累计</th>" +
      "</tr></thead><tbody>" +
      trades.slice().reverse().map(function (r) {
        return (
          "<tr>" +
          '<td class="num">' + fmtNum(r.seq) + "</td>" +
          '<td class="mono">' + esc(r.date) + "</td>" +
          '<td class="mono">' + esc(r.symbol) + "</td>" +
          "<td>" + sideHtml(r.side) + "</td>" +
          '<td class="num mono">' + esc(String(r.ref_price_real_close)) + "</td>" +
          "<td>" + outcomeBadge(r.outcome) + "</td>" +
          '<td class="num mono">' + esc(String(r.exec_price)) + "</td>" +
          '<td class="num">' + fmtNum(r.position_after) + "</td>" +
          '<td class="num ' + pnlClass(r.realized_pnl) + '">' + (r.realized_pnl ? fmtMoney(r.realized_pnl) : "—") + "</td>" +
          '<td class="num ' + pnlClass(r.cum_realized_pnl) + '">' + fmtMoney(r.cum_realized_pnl) + "</td>" +
          "</tr>"
        );
      }).join("") +
      "</tbody></table></div>" +
      '<div class="metric-sub" style="margin-top:8px">拒单会造成仓位漂移（SELL 被拒后仓位保留）——期末未平仓位见汇总表；该页为静态历史回放，不随 5s 自动刷新。</div>' +
      "</div>"
    );
  }

  /* ==================================================================
   * Backtest page (product UI - parameterised replay, frozen quant core)
   * ================================================================== */

  async function pageBacktest() {
    const univ = [
      { sym: "NVDA", gate: true }, { sym: "QQQ", gate: true }, { sym: "SPY", gate: true },
      { sym: "000688.SH", gate: false }, { sym: "HSTECH", gate: false },
      { sym: "EURUSD", gate: false }, { sym: "XAUUSD", gate: false },
      { sym: "AU", gate: false }, { sym: "AG", gate: false },
    ];
    const checks = univ
      .map(function (u) {
        return (
          '<label class="form-check"><input type="checkbox" name="bt-sym" value="' + esc(u.sym) + '"' +
          (u.gate ? " checked" : "") + ">" + esc(u.sym) +
          (u.gate ? '<span class="chk-note">gate ✓</span>' : "") + "</label>"
        );
      })
      .join("");
    return (
      '<div class="card mb"><div class="card-title">Backtest / 回测 — Alpha021</div>' +
      '<div class="metric-sub">因子逻辑（公式 / 窗口 / 定向）密封于 Factor Discovery v2，本页仅参数化回放窗口与资金。' +
      "定价：真实收盘 ± 3 bps。带 gate ✓ 标记的资产已通过 16 项 Factor Gate。</div>" +
      '<form id="bt-form">' +
      '<div class="form-grid">' +
      '<div class="form-field" style="grid-column:1/-1"><label>Markets / 市场（多选）</label><div class="form-checks">' + checks + "</div></div>" +
      '<div class="form-field"><label>Start / 开始日期</label><input type="date" id="bt-start" value="2024-07-01"></div>' +
      '<div class="form-field"><label>End / 结束日期</label><input type="date" id="bt-end"></div>' +
      '<div class="form-field"><label>Initial Capital / 初始资金 (USD)</label><input type="number" id="bt-capital" value="1000000" min="1000" step="1000"></div>' +
      "</div>" +
      '<div class="form-actions"><button type="submit" id="btn-backtest-run" class="btn btn-primary">Run Backtest / 运行回测</button>' +
      '<span class="metric-sub">回放确定性：同参数同结果（延迟字段除外）</span></div>' +
      "</form></div>" +
      '<div id="backtest-result"></div>'
    );
  }

  function renderBacktestResult(data) {
    const m = data.meta || {};
    const trades = data.trades || [];
    const eq = data.equity || [];
    const summary = data.summary || [];
    const panels = data.chart_panels || [];
    const ddSeries = data.drawdown_series || [];
    const monthlyRet = data.monthly_returns || [];
    const metric = function (label, value, cls) {
      return (
        '<div class="card metric-card"><span class="metric-label">' + esc(label) + "</span>" +
        '<span class="metric-value sm ' + (cls || "") + '">' + value + "</span></div>"
      );
    };
    const metricSmall = function (label, value, cls) {
      return (
        '<div class="metric-mini"><span>' + esc(label) + '</span>' +
        '<span class="' + (cls || "") + '">' + value + '</span></div>'
      );
    };
    const outcomeBadge = function (o) {
      if (o === "FILLED") return badge("Filled / 成交", "badge-green");
      if (o === "REJECTED") return badge("Rejected / 拒单", "badge-amber");
      return badge("Error / 错误", "badge-red");
    };

    // Build symbol selector for multi-panel chart
    const symTabs = (m.symbols || []).map(function (s, i) {
      return '<button class="sym-tab' + (i === 0 ? ' active' : '') + '" data-sym="' + esc(s) + '">' + esc(s) + '</button>';
    }).join("");

    return (
      '<div class="card mb"><div class="card-title">Performance / 绩效</div>' +
      '<div class="metric-sub">' + esc((m.symbols || []).join(" / ")) + " · " + esc(m.period || "") +
      " · 初始资金 $" + fmtNum(m.initial_capital) + "</div>" +
      '<div class="grid grid-4">' +
      metric("Final Equity / 期末净值", fmtMoney(m.equity_final)) +
      metric("Return / 收益率", (m.return_pct || 0).toFixed(2) + "%", m.return_pct >= 0 ? "pos" : "neg") +
      metric("Sharpe (ann.) / 夏普", m.sharpe == null ? "—" : m.sharpe.toFixed(2)) +
      metric("Max Drawdown / 最大回撤", (m.maxdd_pct || 0).toFixed(1) + "%", "neg") +
      metric("CAGR / 年化收益", m.cagr == null ? "—" : m.cagr.toFixed(2) + "%", (m.cagr || 0) >= 0 ? "pos" : "neg") +
      metric("Sortino / 索提诺", m.sortino == null ? "—" : m.sortino.toFixed(2)) +
      metric("Calmar / 卡尔马", m.calmar == null ? "—" : m.calmar.toFixed(2)) +
      metric("Win Rate / 胜率", (m.win_rate || 0).toFixed(0) + "%（" + fmtNum(m.closed_trips) + " 笔）") +
      metric("Signals / Filled", fmtNum(m.signals) + " / " + fmtNum(m.filled)) +
      metric("Rejected / Error", fmtNum(m.rejected) + " / " + fmtNum(m.errored)) +
      metric("Turnover / 换手", fmtNum(m.turnover_shares_per_day) + " 股/日") +
      metric("Profit Factor / 盈亏比", m.profit_factor == null ? "—" : m.profit_factor.toFixed(2)) +
      "</div></div>" +

      // Advanced multi-panel chart
      '<div class="card mb"><div class="card-title">Advanced Chart / 高级图表 — 4 面板同步</div>' +
      '<div class="chart-sym-tabs">' + symTabs + '</div>' +
      '<div id="chart-panel-container">' +
      multiPanelChart(panels.slice(0, 1)) +
      '</div>' +
      '<div class="metric-sub">Price + Z-Score + Position + Equity 四面板共用时间轴；BUY/SELL 信号标记在价格图上。</div>' +
      '</div>' +

      // Drawdown chart
      '<div class="card mb"><div class="card-title">Drawdown / 回撤曲线</div>' +
      drawdownChart(ddSeries, null, 100) +
      '</div>' +

      // Monthly returns heatmap
      '<div class="card mb"><div class="card-title">Monthly Returns / 月度收益热力图</div>' +
      monthlyHeatmap(monthlyRet) +
      '</div>' +

      // Trade analysis
      '<div class="card mb"><div class="card-title">Trade Analysis / 交易分析</div>' +
      '<div class="grid grid-4">' +
      metric("Avg Win / 平均盈利", m.avg_win == null ? "—" : fmtMoney(m.avg_win), "pos") +
      metric("Avg Loss / 平均亏损", m.avg_loss == null ? "—" : fmtMoney(m.avg_loss), "neg") +
      metric("Expectancy / 期望", m.expectancy == null ? "—" : fmtMoney(m.expectancy)) +
      metric("Best Trade / 最佳交易", m.best_trade == null ? "—" : fmtMoney(m.best_trade), "pos") +
      metric("Worst Trade / 最差交易", m.worst_trade == null ? "—" : fmtMoney(m.worst_trade), "neg") +
      metric("Avg Holding / 平均持仓", m.avg_holding_days == null ? "—" : m.avg_holding_days + " 天") +
      '</div></div>' +

      '<div class="card mb"><div class="card-title">Per-Symbol Summary / 分资产汇总</div>' +
      '<div class="table-wrap"><table><thead><tr>' +
      "<th>Symbol / 资产</th><th>Signals</th><th>Filled</th><th>Rejected</th><th>Realized / 已实现</th><th>Final Pos</th><th>Unrealized / 浮动</th>" +
      "</tr></thead><tbody>" +
      summary.map(function (r) {
        return (
          "<tr><td><b>" + esc(r.symbol) + "</b></td>" +
          '<td class="num">' + fmtNum(r.signals) + "</td>" +
          '<td class="num">' + fmtNum(r.filled) + "</td>" +
          '<td class="num">' + fmtNum(r.rejected) + "</td>" +
          '<td class="num ' + pnlClass(r.realized_pnl) + '">' + fmtMoney(r.realized_pnl) + "</td>" +
          '<td class="num">' + esc(String(r.final_position)) + "</td>" +
          '<td class="num ' + pnlClass(r.unrealized_pnl) + '">' + fmtMoney(r.unrealized_pnl) + "</td></tr>"
        );
      }).join("") +
      "</tbody></table></div></div>" +

      '<div class="card"><div class="card-title">Trade Log / 交易明细（' + trades.length + "，最新在前）</div>" +
      '<div class="table-wrap" style="max-height:440px;overflow:auto"><table><thead><tr>' +
      "<th>#</th><th>Date / 日期</th><th>Symbol</th><th>Side / 方向</th><th>Close / 收盘</th><th>Outcome / 结果</th><th>Exec / 成交价</th><th>Pos / 仓位</th><th>P&L / 盈亏</th><th>Cum / 累计</th>" +
      "</tr></thead><tbody>" +
      trades.slice().reverse().map(function (r) {
        return (
          "<tr><td>" + fmtNum(r.seq) + "</td>" +
          '<td class="mono">' + esc(r.date) + "</td>" +
          '<td class="mono">' + esc(r.symbol) + "</td>" +
          "<td>" + sideHtml(r.side) + "</td>" +
          '<td class="num mono">' + esc(String(r.ref_price_real_close)) + "</td>" +
          "<td>" + outcomeBadge(r.outcome) + "</td>" +
          '<td class="num mono">' + esc(String(r.exec_price)) + "</td>" +
          '<td class="num">' + fmtNum(r.position_after) + "</td>" +
          '<td class="num ' + pnlClass(r.realized_pnl) + '">' + (r.realized_pnl ? fmtMoney(r.realized_pnl) : "—") + "</td>" +
          '<td class="num ' + pnlClass(r.cum_realized_pnl) + '">' + fmtMoney(r.cum_realized_pnl) + "</td></tr>"
        );
      }).join("") +
      "</tbody></table></div>" +
      '<div class="metric-sub" style="margin-top:8px">已知限制：多头映射（+1 → 100 股）；拒单会导致仓位漂移。</div>' +
      "</div>"
    );
  }

  /* ==================================================================
   * Settings page (paper account + risk rules; no live connections)
   * ================================================================== */

  async function pageSettings() {
    const data = await api.get("/dashboard/config");
    const a = data.account || {};
    const r = data.risk || {};
    const conn = data.connections || {};
    const brokers = (conn.brokers || [])
      .map(function (b) {
        return (
          "<tr><td>" + esc(b.name) + "</td><td>" +
          badge("Not Connected / 未连接", "badge-red") + "</td></tr>"
        );
      })
      .join("");
    const field = function (id, label, value, type, attrs) {
      return (
        '<div class="form-field"><label>' + esc(label) + "</label>" +
        '<input type="' + (type || "text") + '" id="' + id + '" value="' + esc(String(value)) + '" ' + (attrs || "") + "></div>"
      );
    };
    return (
      '<div class="card mb"><div class="card-title">Account &amp; Risk / 账户与风控配置</div>' +
      '<div class="metric-sub">纸面账户配置（Product UI）。实盘交易未启用，未连接任何券商——此处仅配置参数，不建立真实连接。</div>' +
      '<form id="cfg-form">' +
      '<div class="form-grid">' +
      field("cfg-name", "Account Name / 账户名称", a.account_name) +
      '<div class="form-field"><label>Broker / 券商</label><select id="cfg-broker">' +
      ["Simulated", "Interactive Brokers", "盈透证券", "CTP", "Alpaca"]
        .map(function (b) {
          return '<option value="' + esc(b) + '"' + (a.broker === b ? " selected" : "") + ">" + esc(b) + "</option>";
        })
        .join("") +
      "</select></div>" +
      '<div class="form-field"><label>Account Type / 账户类型</label><select id="cfg-type">' +
      ["Paper", "Shadow", "Live"]
        .map(function (t) {
          return '<option value="' + t + '"' + (a.account_type === t ? " selected" : "") + ">" + t + "</option>";
        })
        .join("") +
      "</select></div>" +
      field("cfg-capital", "Initial Capital / 初始资金", a.initial_capital, "number", 'min="1000" step="1000"') +
      '<div class="form-field"><label>Currency / 币种</label><select id="cfg-ccy">' +
      ["USD", "CNY", "HKD"]
        .map(function (c) {
          return '<option value="' + c + '"' + (a.currency === c ? " selected" : "") + ">" + c + "</option>";
        })
        .join("") +
      "</select></div>" +
      field("cfg-daily", "Max Daily Loss / 单日最大亏损 (%)", r.max_daily_loss_pct, "number", 'min="0.1" max="50" step="0.1"') +
      field("cfg-maxdd", "Max Drawdown / 最大回撤限制 (%)", r.max_drawdown_pct, "number", 'min="0.1" max="90" step="0.1"') +
      field("cfg-pertrade", "Risk Per Trade / 单笔风险 (%)", r.risk_per_trade_pct, "number", 'min="0.01" max="10" step="0.01"') +
      "</div>" +
      '<div class="form-actions"><button type="submit" id="btn-config-save" class="btn btn-primary">Save / 保存</button>' +
      '<span class="metric-sub">保存需 OPERATOR / ADMIN 权限，将被审计</span></div>' +
      "</form></div>" +
      '<div class="grid grid-2">' +
      '<div class="card"><div class="card-title">Live Trading / 实盘交易</div>' +
      '<div class="alert alert-critical" style="margin:0">🔴 LIVE TRADING — NOT ENABLED / 实盘交易未启用<div class="metric-sub">Factor Discovery v2 已 CLOSED；当前阶段为 Validation / Observation（Paper → Shadow → Live 决策流）。实盘开关由系统冻结，不由本页控制。</div></div></div>' +
      '<div class="card"><div class="card-title">Broker Connections / 券商连接</div>' +
      '<div class="table-wrap"><table><thead><tr><th>Broker / 券商</th><th>Status / 状态</th></tr></thead><tbody>' +
      (brokers || '<tr><td colspan="2"><div class="empty">None / 无</div></td></tr>') +
      "</tbody></table></div>" +
      '<div class="metric-sub">选择券商仅保存显示偏好；在真实接入前一律显示未连接。</div></div>' +
      "</div>"
    );
  }

  /* ==================================================================
   * Reconciliation page
   * ================================================================== */

  async function pageReconciliation() {
    const data = await api.get("/dashboard/reconciliation");
    const rec = data.reconciliation || {};
    const ok = rec.status === "OK";

    const flow =
      '<div class="card mb"><div class="card-title">Reconciliation Flow / 对账流程</div><div class="flow">' +
      '<span class="flow-step done">Detect / 检测</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (ok ? "done" : "active") + '">Classify / 分类</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step">Risk Decision / 风控决策</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step">Recovery / 恢复</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step">Repair / 修复</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step">Verify / 验证</span>' +
      "</div></div>";

    const statusCard =
      '<div class="card mb">' +
      '<div class="card-title">Reconciliation Status / 对账状态</div>' +
      (ok
        ? '<div style="display:flex;align-items:center;gap:14px">' +
          '<span style="font-size:34px">🟢</span>' +
          '<div><div style="font-size:18px;font-weight:700;color:var(--accent)">All States Consistent / 全部状态一致</div>' +
          '<div class="metric-sub">Position and Ledger are aligned. / 持仓与账本一致。</div></div></div>'
        : '<div style="display:flex;align-items:center;gap:14px">' +
          '<span style="font-size:34px">⚠️</span>' +
          '<div><div style="font-size:18px;font-weight:700;color:var(--amber)">INCONSISTENCY / 不一致</div>' +
          '<div class="metric-sub">' + esc(rec.detail || "") + "</div></div></div>") +
      "</div>";

    const compare =
      '<div class="grid grid-2 mb">' +
      '<div class="card metric-card"><span class="metric-label">Position / 持仓（系统）</span>' +
      '<span class="metric-value">' + fmtNum(rec.position) + "</span></div>" +
      '<div class="card metric-card"><span class="metric-label">Ledger / 账本（外部）</span>' +
      '<span class="metric-value">' + fmtNum(rec.ledger) + "</span></div>" +
      "</div>";

    const accountRec =
      '<div class="card mb"><div class="card-title">Account Reconciliation / 账户对账（Adapter 层）</div>' +
      (data.accounts && data.accounts.accounts && data.accounts.accounts.length
        ? '<div class="table-wrap"><table><thead><tr><th>Account / 账户</th><th>Market / 市场</th><th>Status / 状态</th>' +
          "<th>Equity (expected) / 总权益（预期）</th><th>Equity (actual) / 总权益（实际）</th><th>Differences / 差异</th></tr></thead><tbody>" +
          data.accounts.accounts
            .map(function (a) {
              return (
                "<tr>" +
                '<td class="mono">' + esc(a.account_id) + "</td>" +
                "<td>" + marketBadge(marketLabel(a.market)) + "</td>" +
                "<td>" + (a.status === "CONSISTENT" ? badge("Consistent / 一致", "badge-green") : badge("Inconsistent / 不一致", "badge-red")) + "</td>" +
                "<td class=\"num\">" + fmtNum(a.expected.equity) + "</td>" +
                "<td class=\"num\">" + fmtNum(a.actual.equity) + "</td>" +
                "<td>" + esc((a.differences || []).join(", ") || "none / 无") + "</td></tr>"
              );
            })
            .join("")
        : '<div class="empty">No account state / 暂无账户状态</div>') +
      "</div></div>";

    const details =
      '<div class="card mb"><div class="card-title">Details / 明细</div><div class="kv">' +
      "<dt>Status / 状态</dt><dd>" + (ok ? '<span class="badge badge-green"><span class="dot"></span>Consistent / 一致</span>' : '<span class="badge badge-red"><span class="dot"></span>Recovery Required / 需要恢复</span>') + "</dd>" +
      "<dt>Detected At / 检测时间</dt><dd>" + fmtDateTime(rec.detected_at) + "</dd>" +
      "</div></div>";

    const ledger =
      '<div class="card"><div class="card-title">Ledger Events / 账本事件（最近）</div>' +
      (data.ledger_events && data.ledger_events.length
        ? '<div class="table-wrap"><table><thead><tr><th>Type / 类型</th><th>Symbol / 标的</th><th>Side / 方向</th><th>Qty / 数量</th><th>Price / 价格</th><th>Time / 时间</th></tr></thead><tbody>' +
          data.ledger_events
            .slice()
            .reverse()
            .map(function (e) {
              const p = e.payload || {};
              return (
                "<tr><td>" + esc(e.event_type) + "</td><td>" + esc(p.symbol || "—") + "</td>" +
                "<td>" + (p.side ? sideHtml(p.side) : "—") + "</td>" +
                "<td class=\"num\">" + fmtNum(p.quantity) + "</td>" +
                "<td class=\"num\">" + fmtNum(p.price) + "</td>" +
                "<td class=\"mono\">" + fmtTime(e.timestamp) + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No ledger events / 暂无账本事件</div>') +
      "</div></div>";

    return statusCard + compare + accountRec + flow + details + ledger;
  }

  /* ==================================================================
   * Accounts page (Multi-Account Adapter Layer)
   * ================================================================== */

  function marketLabel(m) {
    const map = { "CN_STOCK": "A-Share", "CN_FUTURES": "Futures", "US_EQUITY": "US Equity", "FX": "FX" };
    return map[m] || m;
  }

  async function pageAccounts() {
    const data = await api.get("/dashboard/accounts");
    const accounts = data.accounts || [];
    const brokers = data.brokers || [];
    const brokerMap = {};
    brokers.forEach(function (b) { brokerMap[b.broker_id] = b; });

    // Account cards
    const accountCards = accounts.map(function (a) {
      const isLive = (a.id && a.id.toLowerCase().indexOf("live") >= 0);
      const connClass = a.connection === "CONNECTED" ? "badge-green" : "badge-red";
      const connLabel = a.connection === "CONNECTED" ? "🟢 Connected / 已连接" : "🔴 Not Connected / 未连接";
      return (
        '<div class="account-card">' +
        '<div class="ac-head">' +
        '<span class="ac-name">' + esc(a.name || a.id) + '</span>' +
        '<span class="badge ' + connClass + '">' + connLabel + '</span>' +
        '</div>' +
        '<div class="ac-equity">$' + fmtNum(a.equity || 0) + '</div>' +
        '<div class="ac-meta">' +
        '<span>' + esc(a.broker_name || "—") + '</span> · <span>' + esc(a.market_label || "—") + '</span>' +
        '</div>' +
        '<div class="ac-stats">' +
        '<span class="num pos">$' + fmtNum(a.cash || 0) + '</span> Cash' +
        '<span class="num">$' + fmtNum(a.positions || 0) + '</span> Pos' +
        '<span class="num">$' + fmtNum(a.orders || 0) + '</span> Orders' +
        '</div>' +
        '<div class="ac-actions">' +
        '<button class="btn btn-sm" data-test-conn="' + esc(a.id) + '">🔌 Test Connection / 测试连接</button>' +
        '</div>' +
        '</div>'
      );
    }).join("");

    return (
      // Account cards row
      '<div class="card mb"><div class="card-title">Accounts / 账户概览</div>' +
      '<div class="account-cards-row">' + (accountCards || '<div class="empty">No accounts / 暂无账户</div>') + '</div>' +
      '</div>' +

      // Broker connections
      '<div class="card mb"><div class="card-title">Broker Status / 券商状态</div>' +
      '<div class="grid grid-4 mb">' +
      (data.health || []).map(function (h) {
        const zh = marketZh(h.market);
        const marketLabel = zh ? h.market + " / " + zh : h.market;
        return (
          '<div class="card metric-card"><span class="metric-label">' + esc(h.broker_name) + "</span>" +
          '<span class="metric-value sm">' + healthBadge(h.status) + "</span>" +
          '<span class="metric-sub">' + esc(marketLabel) + " · " + fmtNum(h.latency_ms) + " ms</span></div>"
        );
      }).join("") +
      "</div></div>" +

      // Account settings form
      '<div class="card mb"><div class="card-title">Account Settings / 账户设置</div>' +
      '<div class="form-grid">' +
      '<div><label>Broker / 券商</label><select id="acc-broker"><option>IBKR</option><option>Interactive Brokers</option><option>Alpaca</option><option>Paper Only</option></select></div>' +
      '<div><label>Account ID / 账户编号</label><input id="acc-id" placeholder="Enter account ID" /></div>' +
      '<div><label>API Key</label><input id="acc-apikey" type="password" placeholder="********" /></div>' +
      '<div><label>API Secret</label><input id="acc-secret" type="password" placeholder="********" /></div>' +
      '<div><label>Environment / 环境</label>' +
      '<div class="radio-group">' +
      '<label><input type="radio" name="acc-env" value="PAPER" checked /> Paper / 模拟</label>' +
      '<label><input type="radio" name="acc-env" value="LIVE" /> Live / 实盘</label>' +
      '</div></div>' +
      '</div>' +
      '<div class="mt">' +
      '<button class="btn btn-sm" id="btn-acc-test">🔌 Test Connection / 测试连接</button>' +
      '<button class="btn btn-sm btn-secondary" id="btn-acc-save">💾 Save Settings / 保存设置</button>' +
      '</div>' +
      '<div class="metric-sub" style="margin-top:8px">⚠ API secrets are stored encrypted on the backend only. Never exposed to frontend.</div>' +
      '</div>' +

      // Detailed table
      '<div class="card"><div class="card-title">Account Details / 账户明细</div>' +
      (accounts.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Account / 账户</th><th>Broker / 券商</th><th>Market / 市场</th><th>Status / 状态</th><th>Equity / 总权益</th><th>Cash / 现金</th><th>Pos / 持仓</th><th>Orders / 订单</th>" +
          "</tr></thead><tbody>" +
          accounts.map(function (a) {
            return (
              '<tr class="clickable" data-href="#/accounts/' + esc(a.account_id) + '">' +
              '<td class="mono">' + esc(a.account_id) + "</td>" +
              '<td class="mono">' + esc(a.broker_name) + "</td>" +
              "<td>" + marketBadge(a.market_label) + "</td>" +
              "<td>" + connBadge(a.connection) + "</td>" +
              "<td class=\"num\">" + fmtMoneyCur(a.equity, a.currency) + "</td>" +
              "<td class=\"num\">" + fmtMoneyCur(a.cash, a.currency) + "</td>" +
              "<td class=\"num\">" + fmtNum(a.positions) + "</td>" +
              "<td class=\"num\">" + fmtNum(a.orders) + "</td></tr>"
            );
          }).join("")
        : '<div class="empty">No accounts / 暂无账户</div>') +
      "</div></div>"
    );
  }

  async function pageAccountDetail(accountId) {
    const data = await api.get("/dashboard/accounts/" + encodeURIComponent(accountId));
    if (!data.account_id) {
      return '<div class="card"><div class="card-title">Account / 账户</div><div class="empty">Account not found / 未找到账户</div></div>';
    }
    const metric = function (label, value, cls) {
      return (
        '<div class="card metric-card"><span class="metric-label">' + esc(label) + "</span>" +
        '<span class="metric-value sm ' + (cls || "") + '">' + value + "</span></div>"
      );
    };
    const ccy = data.currency || "USD";
    const back = '<a class="btn btn-ghost mb" href="#/accounts">← All Accounts / 全部账户</a>';
    const head =
      '<div class="card mb"><div class="card-title">' + esc(data.name) +
      " · " + marketBadge(data.market_label) + " · " + connBadge(data.connection) + "</div>" +
      '<div class="kv"><dt>Account / 账户</dt><dd class="mono">' + esc(data.account_id) + "</dd>" +
      "<dt>Broker / 券商</dt><dd>" + esc(data.broker_name) + "</dd>" +
      "<dt>Status / 状态</dt><dd>" + badge(data.status, "badge-gray") + "</dd>" +
      "<dt>Capabilities / 能力</dt><dd>" + esc((data.capabilities || []).join(", ")) + "</dd></div></div>";
    const metrics =
      '<div class="grid grid-4 mb">' +
      metric("Equity / 总权益", fmtMoneyCur(data.equity, ccy), "pos") +
      metric("Cash / 现金", fmtMoneyCur(data.cash, ccy)) +
      metric("Buying Power / 可用资金", fmtMoneyCur(data.buying_power, ccy)) +
      metric("Margin / 保证金", fmtMoneyCur(data.margin, ccy)) +
      metric("Daily P&L / 当日盈亏", fmtMoneyCur(data.daily_pnl, ccy), pnlClass(data.daily_pnl)) +
      metric("Total P&L / 累计盈亏", fmtMoneyCur(data.total_pnl, ccy), pnlClass(data.total_pnl)) +
      metric("Exposure / 敞口", fmtMoneyCur(data.exposure, ccy)) +
      metric("Drawdown / 回撤", fmtMoneyCur(data.drawdown, ccy)) +
      "</div>";

    const positionsTable =
      '<div class="card mb"><div class="card-title">Positions / 持仓 (' + fmtNum((data.positions || []).length) + ")</div>" +
      (data.positions && data.positions.length
        ? '<div class="table-wrap"><table><thead><tr><th>Symbol / 标的</th><th>Side / 方向</th><th>Quantity / 数量</th><th>Avg Price / 平均价格</th><th>Last / 最新价</th><th>Market Value / 市值</th><th>Unrealized P&amp;L / 浮动盈亏</th><th>Margin / 保证金</th></tr></thead><tbody>' +
          data.positions.map(function (p) {
            return (
              "<tr><td>" + esc(p.symbol) + "</td>" +
              "<td>" + sideHtml(p.side) + "</td>" +
              "<td class=\"num\">" + fmtNum(p.quantity) + "</td>" +
              "<td class=\"num\">" + fmtNum(p.average_price) + "</td>" +
              "<td class=\"num\">" + fmtNum(p.last_price) + "</td>" +
              "<td class=\"num\">" + fmtMoneyCur(p.market_value, ccy) + "</td>" +
              '<td class="num ' + pnlClass(p.unrealized_pnl) + '">' + fmtMoneyCur(p.unrealized_pnl, ccy) + "</td>" +
              "<td class=\"num\">" + (p.margin != null ? fmtMoneyCur(p.margin, ccy) : "—") + "</td></tr>"
            );
          }).join("")
        : '<div class="empty">No positions / 暂无持仓</div>') +
      "</div></div>";

    const ordersTable =
      '<div class="card mb"><div class="card-title">Orders / 订单 (' + fmtNum((data.orders || []).length) + ")</div>" +
      (data.orders && data.orders.length
        ? '<div class="table-wrap"><table><thead><tr><th>Order ID / 订单编号</th><th>Symbol / 标的</th><th>Side / 方向</th><th>Qty / 数量</th><th>Price / 价格</th><th>Status / 状态</th><th>Time / 时间</th></tr></thead><tbody>' +
          data.orders.map(function (o) {
            return (
              "<tr><td class=\"mono\">" + esc(o.order_id) + "</td>" +
              "<td>" + esc(o.symbol) + "</td>" +
              "<td>" + sideHtml(o.side) + "</td>" +
              "<td class=\"num\">" + fmtNum(o.quantity) + "</td>" +
              "<td class=\"num\">" + fmtNum(o.price) + "</td>" +
              "<td>" + statusBadge(o.status) + "</td>" +
              "<td class=\"mono\">" + fmtTime(o.created_at) + "</td></tr>"
            );
          }).join("")
        : '<div class="empty">No orders / 暂无订单</div>') +
      "</div></div>";

    const execTable =
      '<div class="card mb"><div class="card-title">Executions / 成交 (' + fmtNum((data.executions || []).length) + ")</div>" +
      (data.executions && data.executions.length
        ? '<div class="table-wrap"><table><thead><tr><th>Execution ID / 成交编号</th><th>Order ID / 订单编号</th><th>Symbol / 标的</th><th>Side / 方向</th><th>Fill Qty / 成交数量</th><th>Fill Price / 成交价格</th><th>Slippage / 滑点</th><th>Time / 时间</th></tr></thead><tbody>' +
          data.executions.map(function (e) {
            return (
              "<tr><td class=\"mono\">" + esc(e.execution_id) + "</td>" +
              "<td class=\"mono\">" + esc(e.order_id) + "</td>" +
              "<td>" + esc(e.symbol) + "</td>" +
              "<td>" + sideHtml(e.side) + "</td>" +
              "<td class=\"num\">" + fmtNum(e.fill_quantity) + "</td>" +
              "<td class=\"num\">" + fmtNum(e.fill_price) + "</td>" +
              "<td class=\"num\">" + fmtPct(e.slippage) + "</td>" +
              "<td class=\"mono\">" + fmtTime(e.timestamp) + "</td></tr>"
            );
          }).join("")
        : '<div class="empty">No executions / 暂无成交</div>') +
      "</div></div>";

    return back + head + metrics + positionsTable + ordersTable + execTable;
  }

  /* ==================================================================
   * Executions page
   * ================================================================== */

  async function pageExecutions() {
    const data = await api.get("/dashboard/executions");
    const list = data.executions || [];
    return (
      '<div class="card"><div class="card-title">Executions / 成交 (' + fmtNum(list.length) + ")</div>" +
      (list.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Execution ID / 成交编号</th><th>Order ID / 订单编号</th><th>Account / 账户</th><th>Market / 市场</th><th>Symbol / 标的</th><th>Side / 方向</th><th>Fill Qty / 成交数量</th><th>Fill Price / 成交价格</th><th>Slippage / 滑点</th><th>Timestamp / 时间</th>" +
          "</tr></thead><tbody>" +
          list.map(function (e) {
            return (
              "<tr>" +
              "<td class=\"mono\">" + esc(String(e.execution_id).slice(0, 18)) + "</td>" +
              '<td class="mono">' + esc(String(e.order_id).slice(0, 14)) + "</td>" +
              '<td class="mono">' + esc(e.account_id || "paper") + "</td>" +
              "<td>" + (e.market ? marketBadge(marketLabel(e.market)) : badge("Paper / 模拟", "badge-gray")) + "</td>" +
              "<td>" + esc(e.symbol) + "</td>" +
              "<td>" + sideHtml(e.side) + "</td>" +
              "<td class=\"num\">" + fmtNum(e.fill_quantity) + "</td>" +
              "<td class=\"num\">" + fmtNum(e.fill_price) + "</td>" +
              "<td class=\"num\">" + fmtPct(e.slippage) + "</td>" +
              "<td class=\"mono\">" + fmtTime(e.timestamp) + "</td></tr>"
            );
          }).join("")
        : '<div class="empty">No executions yet / 暂无成交</div>') +
      "</div></div>"
    );
  }

  /* ==================================================================
   * Positions page
   * ================================================================== */

  async function pagePositions() {
    const data = await api.get("/dashboard/positions");
    const list = data.positions || [];
    const total = list.reduce(function (s, p) { return s + Number(p.market_value || 0); }, 0);
    return (
      '<div class="card"><div class="card-title">Positions / 持仓 (' + fmtNum(list.length) + ")</div>" +
      (list.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Account / 账户</th><th>Symbol / 标的</th><th>Side / 方向</th><th>Quantity / 数量</th>" +
          "<th>Avg Price / 平均价格</th><th>Last Price / 最新价格</th><th>Market Value / 市值</th>" +
          "<th>Unrealized P&amp;L / 浮动盈亏</th><th>Realized P&amp;L / 已实现盈亏</th><th>Weight / 权重</th>" +
          "</tr></thead><tbody>" +
          list.map(function (p) {
            const w = total > 0 ? Number(p.market_value || 0) / total : 0;
            return (
              "<tr>" +
              '<td class="mono">' + esc(p.account_id || "paper") + "</td>" +
              "<td>" + esc(p.symbol) + "</td>" +
              "<td>" + sideHtml(p.side) + "</td>" +
              "<td class=\"num\">" + fmtNum(p.quantity) + "</td>" +
              "<td class=\"num\">" + fmtNum(p.avg_price) + "</td>" +
              "<td class=\"num\">" + fmtNum(p.last_price) + "</td>" +
              "<td class=\"num\">" + fmtMoney(p.market_value) + "</td>" +
              '<td class="num ' + pnlClass(p.unrealized_pnl) + '">' + fmtMoney(p.unrealized_pnl) + "</td>" +
              '<td class="num ' + pnlClass(p.realized_pnl) + '">' + fmtMoney(p.realized_pnl) + "</td>" +
              "<td class=\"num\">" + fmtPct(w) + "</td></tr>"
            );
          }).join("")
        : '<div class="empty">No positions / 暂无持仓</div>') +
      "</div></div>"
    );
  }

  /* ==================================================================
   * System page
   * ================================================================== */

  async function pageSystem() {
    const data = await api.get("/dashboard/system");
    const services = data.services || {};
    const order = [
      ["api", "API"],
      ["database", "Database / 数据库"],
      ["event-bus", "Event Bus / 事件总线"],
      ["strategy-runtime", "Strategy Runtime / 策略运行时"],
      ["risk-engine", "Risk Engine / 风控引擎"],
      ["order-engine", "Order Engine / 订单引擎"],
      ["execution-engine", "Execution Engine / 执行引擎"],
      ["position-ledger", "Position Ledger / 持仓账本"],
      ["reconciliation", "Reconciliation / 对账服务"],
      ["monitoring", "Monitoring / 监控"],
    ];
    const rows = order
      .map(function (o) {
        const name = o[0];
        const label = o[1];
        const s = services[name] || { status: "UNKNOWN", detail: "not registered / 未注册" };
        return (
          '<div class="status-row">' +
          '<span class="svc-name">' + esc(label) + "</span>" +
          healthBadge(s.status) +
          '<span class="metric-sub">' + esc(s.detail) + "</span>" +
          "</div>"
        );
      })
      .join("");
    const d = data.dashboard || {};
    const hist = state.history;
    return (
      '<div class="card mb"><div class="card-title">Services / 服务</div>' + rows + "</div>" +
      '<div class="grid grid-2">' +
      '<div class="card"><div class="card-title">Application / 应用</div><div class="kv">' +
      "<dt>Version / 版本</dt><dd>" + esc(d.version || "—") + "</dd>" +
      "<dt>Environment / 环境</dt><dd>" + esc(d.environment || "—") + "</dd>" +
      "<dt>Pipeline / 管线</dt><dd>" + (d.attached ? '<span class="badge badge-green"><span class="dot"></span>Attached / 已挂载</span>' : '<span class="badge badge-gray"><span class="dot"></span>Idle / 空闲</span>') + "</dd>" +
      "<dt>Attached At / 挂载时间</dt><dd>" + fmtDateTime(d.attached_at) + "</dd>" +
      "</div></div>" +
      '<div class="card"><div class="card-title">Event Processing / 事件处理</div>' +
      lineChart(hist.pnl, { color: "#4da3ff", id: "sys" }) +
      '<div class="metric-sub mt">P&amp;L progression of the attached pipeline. / 已挂载管线的盈亏走势。</div></div>' +
      "</div>"
    );
  }

  /* ==================================================================
   * Alerts page
   * ================================================================== */

  async function pageAlerts() {
    const data = await api.get("/dashboard/alerts");
    const list = data.alerts || [];
    return (
      '<div class="card"><div class="card-title">Alerts / 告警 (' + fmtNum(list.length) + ")</div>" +
      (list.length
        ? list
            .map(function (a) {
              return (
                '<div class="alert alert-' + String(a.level).toLowerCase() + '">' +
                '<span class="alert-level">' + esc(alertLevelZh(a.level)) + "</span>" +
                "<span><b>" + esc(a.source) + "</b> · " + esc(a.message) + "</span>" +
                '<span class="metric-sub" style="margin-left:auto">' + fmtTime(a.timestamp) + "</span>" +
                "</div>"
              );
            })
            .join("")
          : '<div class="empty">No alerts — system is healthy. / 暂无告警，系统正常。</div>') +
      "</div>"
    );
  }

  /* ==================================================================
   * Audit log page
   * ================================================================== */

  async function pageAuditLog() {
    const data = await api.get("/dashboard/audit-log?limit=200");
    const entries = data.entries || [];
    const stats = data.statistics || {};
    const integrity = data.integrity || {};

    // Filter controls
    const filtersHtml =
      '<div class="audit-filters">' +
      '<select id="audit-filter-action"><option value="">All Actions / 全部</option>' +
      '<option value="STRATEGY_START">Strategy Start</option>' +
      '<option value="STRATEGY_STOP">Strategy Stop</option>' +
      '<option value="ORDER_SUBMIT">Order Submit</option>' +
      '<option value="ORDER_FILL">Order Fill</option>' +
      '<option value="ORDER_CANCEL">Order Cancel</option>' +
      '<option value="RISK_APPROVE">Risk Approve</option>' +
      '<option value="RISK_REJECT">Risk Reject</option>' +
      '<option value="POSITION_UPDATE">Position Update</option>' +
      '<option value="LEDGER_RECONCILE">Ledger Reconcile</option>' +
      '<option value="LOGIN">Login</option>' +
      '<option value="LOGOUT">Logout</option>' +
      '<option value="CONFIG_SAVE">Config Save</option>' +
      '</select>' +
      '<select id="audit-filter-actor"><option value="">All Actors / 全部</option>' +
      ((stats.byActor && Object.keys(stats.byActor).map(function (a) { return '<option value="' + esc(a) + '">' + esc(a) + '</option>'; })).join("") || '') +
      '</select>' +
      '<select id="audit-filter-severity"><option value="">All Severities / 全部</option>' +
      '<option value="INFO">Info</option>' +
      '<option value="WARN">Warn</option>' +
      '<option value="ERROR">Error</option>' +
      '<option value="CRITICAL">Critical</option>' +
      '</select>' +
      '<button class="btn btn-sm" id="btn-audit-apply">Filter / 过滤</button>' +
      '</div>';

    // Stats row
    const statsHtml =
      '<div class="grid grid-4 mb">' +
      '<div class="card metric-card"><span class="metric-label">Total Entries / 总条目</span><span class="metric-value sm">' + fmtNum(stats.totalEntries || 0) + '</span></div>' +
      '<div class="card metric-card"><span class="metric-label">Integrity / 完整性</span><span class="metric-value sm ' + (integrity.integrityOk ? "pos" : "neg") + '">' + (integrity.integrityOk ? '✅ OK' : '⚠ ' + fmtNum(integrity.failed || 0) + ' failed') + '</span></div>' +
      '<div class="card metric-card"><span class="metric-label">By Action / 按操作</span><span class="metric-value sm mono" style="font-size:11px">' + Object.entries(stats.byAction || {}).map(function (e) { return e[0] + ':' + fmtNum(e[1]); }).join(', ') + '</span></div>' +
      '<div class="card metric-card"><span class="metric-label">By Severity / 按级别</span><span class="metric-value sm mono" style="font-size:11px">' + Object.entries(stats.bySeverity || {}).map(function (e) { return e[0] + ':' + fmtNum(e[1]); }).join(', ') + '</span></div>' +
      '</div>';

    // Filtered entries
    const renderEntries = function (entries) {
      if (!entries.length) return '<div class="empty">No audit entries / 无审计条目</div>';
      return '<div class="table-wrap" style="max-height:540px;overflow:auto"><table class="audit-table"><thead><tr>' +
        '<th>Time / 时间</th><th>Action / 操作</th><th>Actor / 操作者</th><th>Target / 目标</th><th>Severity / 级别</th><th>Details / 详情</th>' +
        '</tr></thead><tbody>' +
        entries.map(function (e) {
          const sev = (e.severity || "INFO").toUpperCase();
          const sevCls = "audit-severity-" + sev.toLowerCase();
          return (
            '<tr>' +
            '<td class="mono" style="white-space:nowrap">' + fmtTime(e.timestamp) + '</td>' +
            '<td class="mono">' + esc(e.action) + '</td>' +
            '<td>' + esc(e.actor || "system") + '</td>' +
            '<td class="mono">' + esc(e.target || "—") + '</td>' +
            '<td><span class="audit-severity-tag ' + sevCls + '">' + sev + '</span></td>' +
            '<td style="max-width:300px;overflow:hidden;text-overflow:ellipsis">' + esc(e.details || "") + '</td>' +
            '</tr>'
          );
        }).join("") +
        '</tbody></table></div>';
    };

    return (
      '<div class="card mb"><div class="card-title">Audit Log / 审计日志</div>' +
      '<div class="metric-sub">Every strategic decision, risk check, order, fill, position update, and ledger reconciliation is immutably recorded. / 每个策略决策、风控检查、订单、成交、持仓更新和对账均被不可篡改记录。</div>' +
      '</div>' +
      statsHtml +
      '<div class="card mb"><div class="card-title">Filters / 过滤器</div>' + filtersHtml + '</div>' +
      '<div class="card"><div class="card-title">Event Trail / 事件流水</div>' +
      renderEntries(entries) +
      '</div>'
    );
  }

  /* ==================================================================
   * Coming Soon placeholder (UI V1 Shell)
   * ================================================================== */
  function pageComingSoon(titleEn, titleZh, icon) {
    return (
      '<div class="coming-soon">' +
      '<div class="coming-soon-icon">' + (icon || "◈") + "</div>" +
      '<div class="coming-soon-title">' + esc(titleEn) + "</div>" +
      '<div class="coming-soon-sub">' + esc(titleZh || "") + "</div>" +
      '<div class="coming-soon-zh">该页面将在 UI V1 后续版本中实现</div>' +
      '<div class="coming-soon-tag">Coming in UI V1</div>' +
      "</div>"
    );
  }

  async function pageMarkets() { return pageComingSoon("Markets", "行情", "◉"); }
  async function pageSignals() { return pageComingSoon("Signals", "信号", "⚡"); }
  async function pagePaperTrading() { return pageComingSoon("Paper Trading", "模拟交易", "paper"); }
  async function pageAlphaLab() { return pageComingSoon("Alpha Lab", "因子实验室", "α"); }
  async function pageFactorDiscovery() { return pageComingSoon("Factor Discovery", "因子发现", "⚗"); }
  async function pageSnapshots() { return pageComingSoon("Snapshots", "快照", "cam"); }
  async function pageAttribution() { return pageComingSoon("Attribution", "归因", "chart"); }
  async function pageExposure() { return pageComingSoon("Exposure", "敞口", "▦"); }
  async function pageData() { return pageComingSoon("Data", "数据", "▤"); }
  async function pageServices() { return pageComingSoon("Services", "服务", "⬡"); }

  /* ==================================================================
   * Design System Showcase (Commit 002)
   * ================================================================== */
  async function pageDesignSystem() {
    var html = "";

    // Section: Color tokens
    html += UI.panel("Color System / 颜色系统", "");
    html += '<div class="ds-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:var(--ds-space-3);margin-bottom:var(--ds-space-6);">';
    var colors = [
      ["Background", "var(--ds-bg-base)", "var(--ds-text-primary)"],
      ["Surface", "var(--ds-bg-surface)", "var(--ds-text-primary)"],
      ["Surface Elevated", "var(--ds-bg-surface-elevated)", "var(--ds-text-primary)"],
      ["Profit", "var(--ds-profit-dim)", "var(--ds-profit)"],
      ["Loss", "var(--ds-loss-dim)", "var(--ds-loss)"],
      ["Warning", "var(--ds-warning-dim)", "var(--ds-warning)"],
      ["Info", "var(--ds-info-dim)", "var(--ds-info)"],
      ["Neutral", "var(--ds-neutral-dim)", "var(--ds-neutral)"],
      ["Purple", "var(--ds-purple-dim)", "var(--ds-purple)"],
    ];
    colors.forEach(function (c) {
      html +=
        '<div style="background:' + c[1] + ";color:" + c[2] +
        ";padding:var(--ds-space-3);border-radius:var(--ds-radius-md);border:1px solid var(--ds-border-soft);\">" +
        '<div style="font-size:var(--ds-text-xs);font-weight:var(--ds-font-semibold);text-transform:uppercase;letter-spacing:var(--ds-tracking-wide);">' + c[0] + "</div>" +
        "</div>";
    });
    html += "</div>";

    // Section: Typography
    html += UI.panel("Typography / 排版", "");
    html += '<div class="ds-panel" style="margin-bottom:var(--ds-space-6);"><div class="ds-panel-body">';
    html += '<div style="font-size:var(--ds-text-3xl);font-weight:var(--ds-font-extrabold);letter-spacing:var(--ds-tracking-tight);margin-bottom:var(--ds-space-2);">$1,073,181.00</div>';
    html += '<div style="font-size:var(--ds-text-2xl);font-weight:var(--ds-font-bold);margin-bottom:var(--ds-space-2);">Equity / 总权益</div>';
    html += '<div style="font-size:var(--ds-text-lg);font-weight:var(--ds-font-semibold);margin-bottom:var(--ds-space-2);">Portfolio Overview</div>';
    html += '<div style="font-size:var(--ds-text-base);margin-bottom:var(--ds-space-2);">Body text / 正文 — normal weight</div>';
    html += '<div style="font-size:var(--ds-text-sm);color:var(--ds-text-secondary);">Secondary text / 次要文本</div>';
    html += '<div style="font-size:var(--ds-text-xs);color:var(--ds-text-muted);text-transform:uppercase;letter-spacing:var(--ds-tracking-wider);margin-top:var(--ds-space-2);">LABEL / 标签</div>';
    html += '<div class="ds-text-mono" style="font-size:var(--ds-text-base);margin-top:var(--ds-space-4);">$1,073,181.00  +7.32%  -5.50%</div>';
    html += "</div></div>";

    // Section: Metric Cards
    html += '<h3 style="font-size:var(--ds-text-lg);margin-bottom:var(--ds-space-3);">Metric Cards / 指标卡片</h3>';
    html += '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:var(--ds-space-4);margin-bottom:var(--ds-space-6);">';
    html += UI.metricCard("Equity", "$1,073,181", "+7.32%", "pos");
    html += UI.metricCard("P&L", "+$67,610", "+6.73%", "pos");
    html += UI.metricCard("Drawdown", "-5.50%", "-2.1%", "neg");
    html += UI.metricCard("Fill Rate", "86.04%", "+1.2%", "pos");
    html += "</div>";

    // Section: Table
    html += UI.panel("Positions / 持仓", "");
    html += '<div class="ds-panel" style="margin-bottom:var(--ds-space-6);"><div class="ds-panel-body">';
    html += UI.table({
      columns: [
        { key: "symbol", label: "Symbol" },
        { key: "position", label: "Position", numeric: true },
        { key: "price", label: "Price", numeric: true },
        { key: "pnl", label: "P&L", numeric: true,
          format: function (v) { return UI.signedMoney(v); },
          color: function (v) { return v >= 0 ? "pos" : "neg"; } },
        { key: "weight", label: "Weight", numeric: true,
          format: function (v) { return (v * 100).toFixed(1) + "%"; } },
      ],
      rows: [
        { symbol: "NVDA", position: 600, price: 182.31, pnl: 5102, weight: 0.182 },
        { symbol: "QQQ", position: 200, price: 571.20, pnl: 1204, weight: 0.106 },
        { symbol: "SPY", position: 0, price: 645.13, pnl: 0, weight: 0.0 },
        { symbol: "AAPL", position: -100, price: 224.50, pnl: -820, weight: -0.032 },
      ],
    });
    html += "</div></div>";

    // Section: Buttons
    html += '<h3 style="font-size:var(--ds-text-lg);margin-bottom:var(--ds-space-3);">Buttons / 按钮</h3>';
    html += '<div style="display:flex;gap:var(--ds-space-3);flex-wrap:wrap;margin-bottom:var(--ds-space-6);">';
    html += UI.button("Primary", "primary");
    html += UI.button("Secondary", "secondary");
    html += UI.button("Ghost", "ghost");
    html += UI.button("Danger", "danger");
    html += UI.button("Disabled", "primary", { disabled: true });
    html += UI.button("Small", "primary", { sm: true });
    html += "</div>";

    // Section: Inputs
    html += '<h3 style="font-size:var(--ds-text-lg);margin-bottom:var(--ds-space-3);">Inputs / 输入</h3>';
    html += '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:var(--ds-space-4);margin-bottom:var(--ds-space-6);">';
    html += UI.field("Account Name", UI.input({ placeholder: "Main-Paper" }));
    html += UI.field("Capital", UI.input({ type: "number", placeholder: "100000", step: "0.01" }));
    html += UI.field("Environment", UI.select({
      options: ["Paper", "Shadow", "Live"], value: "Paper" }));
    html += "</div>";
    html += UI.search("Search symbols…", "ds-search-demo");
    html += '<div style="margin-bottom:var(--ds-space-6);"></div>';

    // Section: Badges
    html += '<h3 style="font-size:var(--ds-text-lg);margin-bottom:var(--ds-space-3);">Badges / 徽章</h3>';
    html += '<div style="display:flex;gap:var(--ds-space-3);flex-wrap:wrap;align-items:center;margin-bottom:var(--ds-space-6);">';
    html += UI.badge("CONNECTED", "profit");
    html += UI.badge("RUNNING", "info");
    html += UI.badge("FILLED", "profit");
    html += UI.badge("REJECTED", "loss");
    html += UI.badge("WARNING", "warning");
    html += UI.badge("OFFLINE", "loss");
    html += UI.badge("STOPPED", "neutral");
    html += "</div>";

    // Section: Environment badges
    html += '<h3 style="font-size:var(--ds-text-lg);margin-bottom:var(--ds-space-3);">Environment Badges / 环境徽章</h3>';
    html += '<div style="display:flex;gap:var(--ds-space-3);flex-wrap:wrap;margin-bottom:var(--ds-space-6);">';
    html += UI.envBadge("paper");
    html += UI.envBadge("shadow");
    html += UI.envBadge("live");
    html += "</div>";

    // Section: Tabs
    html += '<h3 style="font-size:var(--ds-text-lg);margin-bottom:var(--ds-space-3);">Tabs / 标签页</h3>';
    var tabsHtml = UI.tabs([
      { id: "overview", label: "Overview", content: '<div style="padding:var(--ds-space-4);">Overview tab content.</div>' },
      { id: "detail", label: "Detail", content: '<div style="padding:var(--ds-space-4);">Detail tab content.</div>' },
      { id: "risk", label: "Risk", content: '<div style="padding:var(--ds-space-4);">Risk tab content.</div>' },
    ]);
    html += '<div id="ds-tabs-container" style="margin-bottom:var(--ds-space-6);">' + tabsHtml + "</div>";

    // Section: Loading / Empty / Error
    html += '<h3 style="font-size:var(--ds-text-lg);margin-bottom:var(--ds-space-3);">States / 状态组件</h3>';
    html += '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:var(--ds-space-4);margin-bottom:var(--ds-space-6);">';
    html += UI.loading("Loading positions…");
    html += UI.empty("No positions", "There are currently no open positions.", "∅");
    html += UI.error("Unable to load orders", "Connection timeout.", "retry-orders");
    html += "</div>";

    // Section: Modal & Drawer triggers
    html += '<h3 style="font-size:var(--ds-text-lg);margin-bottom:var(--ds-space-3);">Modal & Drawer / 弹窗与抽屉</h3>';
    html += '<div style="display:flex;gap:var(--ds-space-3);margin-bottom:var(--ds-space-6);">';
    html += UI.button("Open Modal", "primary", { action: "ds-demo-modal" });
    html += UI.button("Open Drawer", "secondary", { action: "ds-demo-drawer" });
    html += "</div>";

    return html;
  }

  /* ==================================================================
   * Router — Commit 003 Navigation
   * Hierarchical routes with breadcrumb + placeholder pages
   * ================================================================== */

  // Navigation config: route → { group, navKey, label, zh, desc }
  const NAV = {
    "#/dashboard": { group: "overview", navKey: "dashboard", label: "Dashboard", zh: "仪表盘", desc: "Portfolio overview" },
    "#/portfolio": { group: "overview", navKey: "portfolio", label: "Portfolio", zh: "组合", desc: "Portfolio allocation and exposure" },
    "#/research": { group: "research", navKey: "research", label: "Research", zh: "研究", desc: "Research workspace" },
    "#/research/strategies": { group: "research", navKey: "research/strategies", label: "Strategies", zh: "策略", desc: "Strategy management" },
    "#/research/backtest": { group: "research", navKey: "research/backtest", label: "Backtest", zh: "回测", desc: "Backtest workspace" },
    "#/research/factors": { group: "research", navKey: "research/factors", label: "Factor Discovery", zh: "因子发现", desc: "Factor discovery engine" },
    "#/trading/paper": { group: "trading", navKey: "trading/paper", label: "Paper Trading", zh: "模拟", desc: "Paper trading workspace" },
    "#/trading/orders": { group: "trading", navKey: "trading/orders", label: "Orders", zh: "订单", desc: "Order management" },
    "#/trading/positions": { group: "trading", navKey: "trading/positions", label: "Positions", zh: "持仓", desc: "Position management" },
    "#/trading/trades": { group: "trading", navKey: "trading/trades", label: "Trades", zh: "成交", desc: "Trade history" },
    "#/risk": { group: "risk", navKey: "risk", label: "Risk", zh: "风控", desc: "Risk monitor" },
    "#/risk/exposure": { group: "risk", navKey: "risk/exposure", label: "Exposure", zh: "敞口", desc: "Exposure management" },
    "#/operations/accounts": { group: "operations", navKey: "operations/accounts", label: "Accounts", zh: "账户", desc: "Account management" },
    "#/operations/execution": { group: "operations", navKey: "operations/execution", label: "Execution", zh: "执行", desc: "Execution management" },
    "#/operations/reconciliation": { group: "operations", navKey: "operations/reconciliation", label: "Reconciliation", zh: "对账", desc: "Reconciliation management" },
    "#/system": { group: "system", navKey: "system", label: "System", zh: "系统", desc: "System health" },
    "#/system/data": { group: "system", navKey: "system/data", label: "Data", zh: "数据", desc: "Market data center" },
    "#/settings": { group: "system", navKey: "settings", label: "Settings", zh: "设置", desc: "System settings" },
    "#/alerts": { group: "system", navKey: "alerts", label: "Alerts", zh: "告警", desc: "Unified alert center" },
  };

  // Group labels for breadcrumb
  const GROUP_LABELS = {
    overview: "Overview",
    research: "Research",
    trading: "Trading",
    risk: "Risk",
    operations: "Operations",
    system: "System",
  };

  // ── Page Framework implementations (Commit 004) ─────────────────
  // All pages use mock data. Real API integration comes in later commits.

  function pageNavPlaceholder(cfg) {
    var fn = PAGE_FRAMEWORK[cfg.navKey];
    if (fn) return fn();
    return (
      UI.pageHeader(cfg.label, cfg.desc) +
      UI.empty(cfg.label, "This page will be implemented in a future UI V1 commit.")
    );
  }

  var PAGE_FRAMEWORK = {};

  /* ==================================================================
   * Integration 002 — Dashboard API Hook
   *
   * useDashboard() is the single entry point the Dashboard page uses to
   * fetch real data from ``GET /api/dashboard``.  It wraps the unified
   * API Client and returns a normalised payload or throws an ApiError
   * (caught by the render() outer try/catch → stateError + Retry).
   * ================================================================== */

  async function useDashboard() {
    var data = await api.get("/dashboard");
    // Normalise: guarantee all 7 sections + meta exist
    return {
      account: data.account || { equity: 0, cash: 0, daily_pnl: 0, daily_return: 0 },
      positions: data.positions || { count: 0, market_value: 0, unrealized_pnl: 0, items: [] },
      orders: data.orders || { pending: 0, filled_today: 0, rejected_today: 0 },
      risk: data.risk || { status: "UNKNOWN", drawdown: 0, exposure: 0 },
      execution: data.execution || { fill_rate: 0, reject_rate: 0, slippage: 0 },
      strategies: data.strategies || { active: 0, signals_today: 0, items: [] },
      alerts: data.alerts || { critical: 0, warning: 0, items: [] },
      meta: data.meta || { pipeline_attached: false, timestamp: null, environment: "PAPER", account_name: "—" },
    };
  }

  /* ==================================================================
   * Integration 004 — Portfolio API Hook
   *
   * usePortfolio() is the single entry point the Portfolio page uses to
   * fetch the global aggregated portfolio from
   * ``GET /api/dashboard/portfolio``. One endpoint, no duplicate
   * requests — returns the full summary + market/currency exposure +
   * accounts + positions, normalised. Throws ApiError on failure
   * (caught by render() outer try/catch → stateError + Retry).
   * ================================================================== */
  async function usePortfolio() {
    var data = await api.get("/dashboard/portfolio");
    return {
      summary: data.summary || {
        total_equity_usd: 0, total_cash_usd: 0, gross_exposure_usd: 0,
        net_exposure_usd: 0, daily_pnl_usd: 0, total_pnl_usd: 0, drawdown_usd: 0,
      },
      market_exposure: data.market_exposure || {},
      currency_exposure: data.currency_exposure || {},
      accounts: data.accounts || [],
      positions: data.positions || [],
    };
  }

  /* ==================================================================
   * Integration 005 — Orders API Hooks
   *
   * useOrders() / useOrderDetail() / useOrderCancel() are the single
   * entry points the Orders page uses to talk to icyquant-api.
   *
   * Flow:  List → Detail → Cancel → Refresh
   *   - useOrders()           GET   /api/dashboard/orders
   *   - useOrderDetail(id)     GET   /api/dashboard/orders/{order_id}
   *   - useOrderCancel(id)     POST  /api/dashboard/orders/{order_id}/cancel
   *
   * All throw ApiError on failure. List-level errors propagate to
   * render() outer try/catch → stateError + Retry. Detail / Cancel
   * errors are handled by the page-level handlers so a failed detail
   * fetch or cancel does not blank the whole page.
   * ================================================================== */
  async function useOrders() {
    var data = await api.get("/dashboard/orders");
    return Array.isArray(data && data.orders) ? data.orders : [];
  }

  async function useOrderDetail(orderId) {
    return await api.get("/dashboard/orders/" + encodeURIComponent(orderId));
  }

  async function useOrderCancel(orderId) {
    var data = await api.post(
      "/dashboard/orders/" + encodeURIComponent(orderId) + "/cancel"
    );
    return data && data.order ? data.order : null;
  }

  /* ==================================================================
   * Integration 006 — Positions API Hooks
   *
   * usePositions() / usePositionDetail(symbol) are the single entry
   * points the Positions page uses to talk to icyquant-api. The Position
   * Ledger is the single source of truth for quantity / side / avg price;
   * the UI never fabricates or reconciles numbers itself.
   *
   * Flow:  List (summary + positions) → Detail (position + ledger fills)
   *   - usePositions()              GET  /api/dashboard/positions
   *   - usePositionDetail(symbol)   GET  /api/dashboard/positions/{symbol}
   *
   * List-level errors propagate to render() outer try/catch → stateError +
   * Retry. Detail errors are handled by the page-level handler so a failed
   * detail fetch does not blank the whole page.
   * ================================================================== */
  async function usePositions() {
    var data = await api.get("/dashboard/positions");
    return {
      summary: (data && data.summary) || {},
      positions: Array.isArray(data && data.positions) ? data.positions : [],
    };
  }

  async function usePositionDetail(symbol) {
    return await api.get("/dashboard/positions/" + encodeURIComponent(symbol));
  }

  /* ==================================================================
   * Integration 007 — Research API Hooks
   *
   * useResearch* are the single entry points the Research page uses to
   * read the frozen Factor Discovery v2 results (101 → 909 → 28 →
   * 26 → 22 → 15) and the Alpha021 candidate (factor-real-d1).
   *
   * Read-only contract:
   *   - useResearchOverview()              GET  /api/dashboard/research/overview
   *   - useResearchRuns()                  GET  /api/dashboard/research/runs
   *   - useResearchRun(runId)              GET  /api/dashboard/research/runs/{run_id}
   *   - useResearchAlphas(runId)           GET  /api/dashboard/research/alphas
   *   - useResearchAlphaDetail(id, runId)  GET  /api/dashboard/research/alphas/{alpha_id}
   *   - useResearchFunnel(runId)           GET  /api/dashboard/research/funnel/{run_id}
   *   - useResearchDecorrelation(runId)    GET  /api/dashboard/research/decorrelation/{run_id}
   *
   * The UI never fabricates research data — every funnel count, alpha
   * metric, family member, formula comes straight from report.json. List-
   * level errors propagate to render() outer try/catch → stateError +
   * Retry. Detail errors are handled by the page-level handlers.
   * ================================================================== */
  async function useResearchOverview() {
    var data = await api.get("/dashboard/research/overview");
    return {
      runs: Array.isArray(data && data.runs) ? data.runs : [],
    };
  }

  async function useResearchRuns() {
    var data = await api.get("/dashboard/research/runs");
    return {
      runs: Array.isArray(data && data.runs) ? data.runs : [],
    };
  }

  async function useResearchRun(runId) {
    return await api.get(
      "/dashboard/research/runs/" + encodeURIComponent(runId)
    );
  }

  async function useResearchAlphas(runId) {
    var url = "/dashboard/research/alphas";
    if (runId) url += "?run_id=" + encodeURIComponent(runId);
    var data = await api.get(url);
    return {
      run_id: (data && data.run_id) || runId,
      alphas: Array.isArray(data && data.alphas) ? data.alphas : [],
      total: (data && data.total) || 0,
    };
  }

  async function useResearchAlphaDetail(alphaId, runId) {
    var url =
      "/dashboard/research/alphas/" + encodeURIComponent(alphaId);
    if (runId) url += "?run_id=" + encodeURIComponent(runId);
    return await api.get(url);
  }

  async function useResearchFunnel(runId) {
    return await api.get(
      "/dashboard/research/funnel/" + encodeURIComponent(runId)
    );
  }

  async function useResearchDecorrelation(runId) {
    return await api.get(
      "/dashboard/research/decorrelation/" + encodeURIComponent(runId)
    );
  }

  async function useResearchReport(runId) {
    return await api.get(
      "/dashboard/research/runs/" + encodeURIComponent(runId) + "/report"
    );
  }

  /* ==================================================================
   * Integration 003 — Trading API Hooks
   *
   * useQuote / useOrderPreview / useOrderSubmit are the single entry
   * points the Trading page uses to talk to icyquant-api.
   *
   * Flow:  Quote → Order Ticket → Preview → Submit → Result
   *   - useQuote(symbol)            GET  /api/dashboard/quote/{symbol}
   *   - useOrderPreview(ticket)     POST /api/dashboard/orders/preview
   *   - useOrderSubmit(ticket)      POST /api/dashboard/orders
   *
   * All throw ApiError on failure (caught by the render() outer
   * try/catch → stateError + Retry, or by the ticket-level handlers).
   * ================================================================== */

  async function useQuote(symbol) {
    var data = await api.get("/dashboard/quote/" + encodeURIComponent(symbol));
    return {
      symbol: data.symbol || symbol,
      last_price: data.last_price || 0,
      bid: data.bid || 0,
      ask: data.ask || 0,
      spread: data.spread || 0,
      change: data.change || 0,
      change_pct: data.change_pct || 0,
      timestamp: data.timestamp || null,
      source: data.source || "none",
      session_running: !!data.session_running,
    };
  }

  async function useOrderPreview(ticket) {
    var data = await api.post("/dashboard/orders/preview", ticket);
    return {
      symbol: data.symbol || ticket.symbol,
      side: data.side || ticket.side,
      quantity: data.quantity || ticket.quantity,
      order_type: data.order_type || ticket.order_type,
      price: data.price || 0,
      last_price: data.last_price || 0,
      estimated_value: data.estimated_value || 0,
      risk_check: data.risk_check || { status: "UNKNOWN", warnings: [], session_running: false, pipeline_attached: false },
      preview_only: data.preview_only !== false,
      timestamp: data.timestamp || null,
    };
  }

  async function useOrderSubmit(ticket) {
    var data = await api.post("/dashboard/orders", ticket);
    return {
      order: data.order || null,
      result: data.result || {},
      risk_decision: data.risk_decision || null,
      status: data.status || "UNKNOWN",
      rejection_reason: data.rejection_reason || null,
      timestamp: data.timestamp || null,
    };
  }

  // ── Dashboard (Integration 002 — real API data) ──────────────
  PAGE_FRAMEWORK["dashboard"] = async function () {
    var d = await useDashboard();

    // ── Helpers ────────────────────────────────────────────────
    function fmtMoney(v) { return UI.money(v, 2); }
    function fmtSigned(v) { return UI.signedMoney(v); }
    function fmtPct(v) { return (v >= 0 ? "+" : "") + v.toFixed(2) + "%"; }
    function fmtPctRaw(v) { return (v * 100).toFixed(2) + "%"; }

    // ── Empty state (no pipeline attached) ─────────────────────
    var noPipeline = !d.meta.pipeline_attached;

    // 1) Account context bar
    var ts = d.meta.timestamp ? new Date(d.meta.timestamp).toLocaleString() : "—";
    var acctBar =
      '<div class="dash-acct-bar">' +
      '<div class="dash-acct-main">' +
      '<span class="dash-acct-label">Account</span>' +
      '<span class="dash-acct-name">' + esc(d.meta.account_name || "Paper-Alpha021") + '</span>' +
      UI.statusPill(esc(d.meta.environment || "PAPER"), "info") +
      '</div>' +
      '<div class="dash-acct-meta">' +
      '<span class="dash-acct-meta-item"><span class="dash-acct-meta-label">Last Update</span><span class="ds-text-mono">' + ts + '</span></span>' +
      '<span class="dash-acct-meta-item"><span class="dash-acct-meta-label">Session</span><span class="ds-text-mono">' + esc(d.meta.environment || "PAPER") + (d.meta.pipeline_attached ? " · LIVE" : " · IDLE") + '</span></span>' +
      '</div>' +
      '</div>';

    // 2) Portfolio summary KPIs (8 metrics from real data)
    var pnlVar = d.account.daily_pnl >= 0 ? "pos" : "neg";
    var retVar = d.account.daily_return >= 0 ? "pos" : "neg";
    var kpis =
      UI.metricCard("Equity", fmtMoney(d.account.equity), fmtPct(d.account.daily_return), retVar) +
      UI.metricCard("Daily P&L", fmtSigned(d.account.daily_pnl), fmtPct(d.account.daily_return), pnlVar) +
      UI.metricCard("Unrealized P&L", fmtSigned(d.positions.unrealized_pnl), d.positions.count + " positions", d.positions.unrealized_pnl >= 0 ? "pos" : "neg") +
      UI.metricCard("Cash", fmtMoney(d.account.cash), "Available", "") +
      UI.metricCard("Exposure", fmtMoney(d.risk.exposure), fmtPctRaw(d.risk.exposure / (d.account.equity || 1)), "info") +
      UI.metricCard("Fill Rate", fmtPctRaw(d.execution.fill_rate), d.orders.filled_today + " filled", d.execution.fill_rate >= 0.5 ? "pos" : "warning") +
      UI.metricCard("Open Positions", String(d.positions.count), d.orders.pending + " pending", "") +
      UI.metricCard("Alerts", String(d.alerts.critical + d.alerts.warning), d.alerts.critical + " crit · " + d.alerts.warning + " warn", d.alerts.critical > 0 ? "neg" : "");

    // 3) Equity Curve (single-point when no history; flat line at equity)
    var eqData = [{ value: d.account.equity, label: 0 }];
    var equityCurve = UI.equityCurve(eqData, {
      height: 240,
      yTicks: [d.account.equity * 0.98, d.account.equity, d.account.equity * 1.02],
      yFormat: function (v) { return "$" + (v / 1000000).toFixed(2) + "M"; },
      xLabels: ["Now"],
      color: "var(--ds-profit)",
    });

    // 4) P&L Summary
    var pnlSummary = UI.statRows([
      { label: "Today", value: fmtSigned(d.account.daily_pnl), variant: d.account.daily_pnl >= 0 ? "pos" : "neg" },
      { label: "Exposure", value: fmtMoney(d.risk.exposure), variant: "info" },
      { label: "Positions", value: String(d.positions.count), variant: "" },
      { label: "Cash", value: fmtMoney(d.account.cash), variant: "" },
    ]);
    var pnlSpark = UI.sparkline([d.account.daily_pnl, 0, d.account.daily_pnl, 0], { color: "var(--ds-profit)", width: 240, height: 56 });

    var pnlBlock =
      UI.panel("P&L Summary", UI.periodTabs(["1D", "1W", "1M", "3M", "YTD", "ALL"], 0, "dash-pnl-tabs") + pnlSpark + pnlSummary,
        { actions: '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);">live</span>' });

    var chartsRow =
      '<div class="dash-grid-2">' +
      '<div class="dash-grid-main">' + UI.panel("Portfolio Equity", equityCurve,
        { actions: '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);">current</span>' }) + '</div>' +
      '<div class="dash-grid-side">' + pnlBlock + '</div>' +
      '</div>';

    // 5) Positions + Exposure (real items)
    var posItems = (d.positions.items || []).map(function (p) {
      return {
        symbol: p.symbol || "—",
        side: (p.side || (p.quantity >= 0 ? "Long" : "Short")),
        qty: p.quantity,
        avgPrice: p.avg_price,
        mktPrice: p.last_price,
        mktValue: p.market_value,
        pnl: p.unrealized_pnl,
        weight: (p.market_value / (d.account.equity || 1)),
      };
    });

    var longVal = 0, shortVal = 0;
    posItems.forEach(function (p) {
      if (p.qty >= 0) longVal += p.mktValue; else shortVal += Math.abs(p.mktValue);
    });

    var exposureBar =
      '<div class="dash-exposure">' +
      '<div class="dash-exposure-head">' +
      '<span class="dash-exposure-label">Total Exposure</span>' +
      '<span class="ds-text-mono">' + fmtMoney(d.risk.exposure) + ' · ' + fmtPctRaw(d.risk.exposure / (d.account.equity || 1)) + '</span>' +
      '</div>' +
      '<div class="progress-bar"><div class="progress-fill info" style="width:' + Math.min(100, (d.risk.exposure / (d.account.equity || 1)) * 100) + '%"></div></div>' +
      '<div class="dash-exposure-legend">' +
      '<span><span class="ds-dot ds-dot-pos"></span>Long ' + fmtMoney(longVal) + '</span>' +
      '<span><span class="ds-dot ds-dot-neg"></span>Short ' + fmtMoney(shortVal) + '</span>' +
      '<span><span class="ds-dot ds-dot-info"></span>Cash ' + fmtMoney(d.account.cash) + '</span>' +
      '</div>' +
      '</div>';

    var posTable = posItems.length ? UI.table({
      columns: [
        { key: "symbol", label: "Symbol" },
        { key: "side", label: "Side" },
        { key: "qty", label: "Qty", numeric: true },
        { key: "avgPrice", label: "Avg Price", numeric: true, format: function (v) { return "$" + (v || 0).toFixed(2); } },
        { key: "mktPrice", label: "Mkt Price", numeric: true, format: function (v) { return "$" + (v || 0).toFixed(2); } },
        { key: "mktValue", label: "Mkt Value", numeric: true, format: function (v) { return UI.money(v, 0); } },
        { key: "pnl", label: "P&L", numeric: true, format: function (v) { return UI.signedMoney(v); }, color: function (v) { return v >= 0 ? "pos" : "neg"; } },
        { key: "weight", label: "Weight", numeric: true, format: function (v) { return (v * 100).toFixed(1) + "%"; } },
      ],
      rows: posItems,
    }) : UI.empty("No Open Positions", "No positions in the current pipeline snapshot.");

    var positionsBlock =
      UI.panel("Open Positions", exposureBar + posTable,
        { actions: UI.button("View All", "ghost", { sm: true, action: "nav:trading/positions" }) });

    // 6) Recent Activity (derived from alerts.items)
    var alertItems = (d.alerts.items || []).slice(0, 6);
    var activity = alertItems.length ? UI.timeline(alertItems.map(function (a) {
      return {
        time: a.timestamp ? new Date(a.timestamp).toLocaleTimeString().slice(0, 5) : "—",
        type: (a.source || "SYSTEM").toUpperCase(),
        title: esc(a.message || "—"),
        desc: "Level: " + esc(a.level || "INFO"),
        variant: a.level === "CRITICAL" ? "danger" : a.level === "WARNING" ? "warning" : "info",
      };
    })) : UI.empty("No Recent Activity", "No alerts in the current session.");

    var activityBlock = UI.panel("Recent Activity", activity,
      { actions: UI.button("View All", "ghost", { sm: true, action: "nav:system" }) });

    var positionsActivityRow =
      '<div class="dash-grid-2 dash-grid-2-1-1">' +
      '<div class="dash-grid-main">' + positionsBlock + '</div>' +
      '<div class="dash-grid-side">' + activityBlock + '</div>' +
      '</div>';

    // 7) Strategy Status (real strategies.items)
    var stratItems = (d.strategies.items || []);
    var stratStatus = UI.statRows([
      { label: "Active Strategies", value: String(d.strategies.active), variant: "pos" },
      { label: "Signals Today", value: String(d.strategies.signals_today), variant: "" },
      { label: "Fill Rate", value: fmtPctRaw(d.execution.fill_rate), variant: d.execution.fill_rate >= 0.5 ? "pos" : "warning" },
      { label: "Reject Rate", value: fmtPctRaw(d.execution.reject_rate), variant: d.execution.reject_rate > 0.2 ? "neg" : "" },
      { label: "Slippage", value: d.execution.slippage.toFixed(4), variant: "" },
      { label: "Exposure", value: fmtMoney(d.risk.exposure), variant: "info" },
      { label: "Positions", value: String(d.positions.count), variant: "" },
      { label: "Risk Status", value: esc(d.risk.status), variant: d.risk.status === "HEALTHY" ? "pos" : d.risk.status === "NO_PIPELINE" ? "warning" : "neg" },
    ]);
    var stratBlock =
      '<div class="dash-grid-2">' +
      '<div class="dash-grid-main">' + UI.panel("Strategy & Execution", stratStatus) + '</div>' +
      '<div class="dash-grid-side">' + UI.panel("Alerts",
        '<div class="dash-svc-grid">' +
        (alertItems.length ? alertItems.map(function (a) {
          return '<div class="dash-svc">' + UI.statusPill(a.level, a.level === "CRITICAL" ? "danger" : a.level === "WARNING" ? "warning" : "info") + '<span class="dash-svc-name">' + esc(a.source) + '</span></div>';
        }).join("") : '<span class="ds-text-muted">No active alerts</span>') +
        '</div>') + '</div>' +
      '</div>';

    // 8) System Health (from risk + pipeline state)
    var riskColor = d.risk.status === "HEALTHY" ? "profit" : d.risk.status === "NO_PIPELINE" ? "warning" : "danger";
    var services = [
      ["Pipeline", d.meta.pipeline_attached ? "Attached" : "Detached", d.meta.pipeline_attached ? "profit" : "warning"],
      ["Risk Engine", esc(d.risk.status), riskColor],
      ["Reconciliation", esc(d.risk.status), riskColor],
    ];
    var servicesHtml = services.map(function (s) {
      return '<div class="dash-svc">' + UI.statusPill(s[1], s[2]) + '<span class="dash-svc-name">' + s[0] + '</span></div>';
    }).join("");
    var dataStatus = [
      ["Environment", esc(d.meta.environment || "PAPER"), "info", "—"],
      ["Last Update", ts, "profit", ""],
      ["Backend", state.backend.status === "connected" ? "Connected" : state.backend.status === "degraded" ? "Degraded" : "Disconnected", state.backend.status === "connected" ? "profit" : state.backend.status === "degraded" ? "warning" : "danger", ""],
    ];
    var dataHtml = dataStatus.map(function (dd) {
      return '<div class="dash-svc"><span class="ds-text-muted">' + dd[3] + '</span>' + UI.statusPill(dd[1], dd[2]) + '<span class="dash-svc-name">' + dd[0] + '</span></div>';
    }).join("");
    var healthBlock =
      '<div class="dash-grid-2">' +
      '<div class="dash-grid-main">' + UI.panel("Services", '<div class="dash-svc-grid">' + servicesHtml + '</div>') + '</div>' +
      '<div class="dash-grid-side">' + UI.panel("Data", '<div class="dash-svc-grid">' + dataHtml + '</div>') + '</div>' +
      '</div>';

    return (
      UI.pageHeader("Dashboard", "Portfolio overview and system health",
        UI.button("Refresh", "ghost", { sm: true, action: "dash:refresh" })) +
      acctBar +
      UI.kpiGrid(kpis, 4) +
      chartsRow +
      positionsActivityRow +
      UI.sectionHeading("Strategy & Execution") +
      stratBlock +
      UI.sectionHeading("System Health") +
      healthBlock
    );
  };

  // Placeholder P&L sparkline data — generated inline to avoid bloat.
  // Simple oscillating positive-then-negative intraday P&L.
  function _dashPnlSpark() {
    var arr = [];
    for (var i = 0; i < 48; i++) {
      var base = i * 18;
      var wave = Math.sin(i * 0.4) * 220;
      var noise = (i % 7 - 3) * 40;
      arr.push(Math.round(base + wave + noise - 600));
    }
    return arr;
  }
  var pnlSparkData = _dashPnlSpark();

  // ── Portfolio (Integration 004 — real API data) ──────────────
  // Single aggregated endpoint GET /api/dashboard/portfolio returns the
  // full global portfolio: summary (equity/cash/exposure/pnl/drawdown) +
  // market_exposure (allocation) + currency_exposure + accounts +
  // positions. UI derives return %, weight, long/short exposure from
  // this — no second source, no fabricated account truth.
  PAGE_FRAMEWORK["portfolio"] = async function () {
    var pf = await usePortfolio();
    var s = pf.summary;
    var positions = pf.positions;
    var accounts = pf.accounts;
    var marketExposure = pf.market_exposure;
    var currencyExposure = pf.currency_exposure;
    var lastUpdated = new Date().toLocaleTimeString("en-US", { hour12: false });

    // ── Safe number coercion ─────────────────────────────────────
    function num(v) { var n = Number(v); return isFinite(n) ? n : 0; }
    function fmtSigned(v) { return UI.signedMoney(v); }
    function fmtPctVal(v) { return (num(v) >= 0 ? "+" : "") + num(v).toFixed(2) + "%"; }
    function pnlVar(v) { return num(v) >= 0 ? "pos" : "neg"; }
    function sideLabel(s) { return s === "BUY" ? "LONG" : s === "SELL" ? "SHORT" : "FLAT"; }

    // ── Derived metrics (UI does not invent account truth) ──────
    var totalEquity = num(s.total_equity_usd);
    var cash = num(s.total_cash_usd);
    var grossExposure = num(s.gross_exposure_usd);
    var netExposure = num(s.net_exposure_usd);
    var dailyPnl = num(s.daily_pnl_usd);
    var totalPnl = num(s.total_pnl_usd);
    var drawdown = num(s.drawdown_usd);

    var cost = totalEquity - totalPnl;              // implied cost basis
    var returnPct = cost > 0 ? (totalPnl / cost) * 100 : 0;
    var cashPct = totalEquity > 0 ? (cash / totalEquity) * 100 : 0;
    var grossPct = totalEquity > 0 ? (grossExposure / totalEquity) * 100 : 0;
    var dayRetPct = (totalEquity - dailyPnl) > 0 ? (dailyPnl / (totalEquity - dailyPnl)) * 100 : 0;

    var realizedPnl = 0, unrealizedPnl = 0, longExposure = 0, shortExposure = 0;
    positions.forEach(function (p) {
      realizedPnl += num(p.realized_pnl);
      unrealizedPnl += num(p.unrealized_pnl);
      if (p.side === "BUY") longExposure += num(p.exposure);
      else if (p.side === "SELL") shortExposure += num(p.exposure);
    });

    // Concentration: top position by market value
    var top = positions.slice()
      .sort(function (a, b) { return num(b.market_value) - num(a.market_value); })[0];
    var topSymbol = top ? top.symbol : "—";
    var topWeight = (top && totalEquity > 0)
      ? (num(top.market_value) / totalEquity) * 100 : 0;

    // ── Account context bar ──────────────────────────────────────
    var acctBar =
      '<div class="dash-acct-bar">' +
      '<div class="dash-acct-main">' +
      '<span class="dash-acct-label">Portfolio</span>' +
      '<span class="dash-acct-name">Global · ' + accounts.length + ' accounts</span>' +
      UI.statusPill("Live", "profit") +
      '</div>' +
      '<div class="dash-acct-meta">' +
      '<span class="dash-acct-meta-item"><span class="dash-acct-meta-label">Updated</span><span class="ds-text-mono">' + esc(lastUpdated) + '</span></span>' +
      '<span class="dash-acct-meta-item"><span class="dash-acct-meta-label">Base Currency</span><span class="ds-text-mono">USD</span></span>' +
      '<span class="dash-acct-meta-item"><span class="dash-acct-meta-label">Positions</span><span class="ds-text-mono">' + positions.length + '</span></span>' +
      '</div>' +
      '</div>';

    // ── KPI cards (real summary values) ──────────────────────────
    var kpis =
      UI.metricCard("Total Equity", fmtMoney(totalEquity), "USD", "info") +
      UI.metricCard("Cash", fmtMoney(cash), cashPct.toFixed(1) + "% of equity", "default") +
      UI.metricCard("Today P&L", fmtSigned(dailyPnl), fmtPctVal(dayRetPct), pnlVar(dailyPnl)) +
      UI.metricCard("Total Return", fmtPctVal(returnPct), fmtSigned(totalPnl), pnlVar(totalPnl)) +
      UI.metricCard("Drawdown", fmtMoney(drawdown), "Peak → Trough", "neg") +
      UI.metricCard("Positions", String(positions.length), accounts.length + " accounts", "default");

    // ── Equity panel: live value only (no historical series) ────
    // Per Integration 004 boundary: backend has no equity time-series,
    // so the UI shows the live value + an explicit "historical pending"
    // note rather than fabricating a curve.
    var equityPanel =
      '<div class="ds-callout" style="padding:var(--ds-space-lg);text-align:center;">' +
      '<div class="ds-text-muted" style="font-size:var(--ds-text-xs);">LIVE EQUITY (USD)</div>' +
      '<div class="ds-text-mono" style="font-size:var(--ds-text-3xl);color:var(--ds-profit);margin:var(--ds-space-sm) 0;">' + fmtMoney(totalEquity) + '</div>' +
      '<div class="ds-text-muted" style="font-size:var(--ds-text-xs);">Historical equity series pending backend support — not fabricated</div>' +
      '</div>';

    // ── Allocation donut (real market_exposure + cash) ───────────
    var allocColors = {
      "A-Share": "var(--ds-profit)", "Futures": "var(--ds-info)",
      "US Equity": "var(--ds-purple)", "FX": "var(--ds-warning)",
      "Cash": "var(--ds-neutral)",
    };
    var allocSegments = Object.keys(marketExposure).map(function (k) {
      return { label: k, value: num(marketExposure[k]), color: allocColors[k] || "var(--ds-info)" };
    });
    if (cash > 0) allocSegments.push({ label: "Cash", value: cash, color: allocColors["Cash"] });
    var donut = UI.donutChart(allocSegments, {
      size: 180, thickness: 24,
      centerValue: "$" + (totalEquity / 1000000).toFixed(2) + "M",
      centerLabel: "Total",
    });

    var chartsRow =
      '<div class="dash-grid-2">' +
      '<div class="dash-grid-main">' + UI.panel("Equity Curve", equityPanel) + '</div>' +
      '<div class="dash-grid-side">' + UI.panel("Allocation by Market", donut) + '</div>' +
      '</div>';

    // ── P&L breakdown (real) + period note ───────────────────────
    var pnlRows = UI.statRows([
      { label: "Realized P&L", value: fmtSigned(realizedPnl), variant: pnlVar(realizedPnl) },
      { label: "Unrealized P&L", value: fmtSigned(unrealizedPnl), variant: pnlVar(unrealizedPnl) },
      { label: "Total P&L", value: fmtSigned(totalPnl), variant: pnlVar(totalPnl) },
      { label: "Daily P&L", value: fmtSigned(dailyPnl), variant: pnlVar(dailyPnl) },
    ]);
    var pnlNote = '<div class="ds-callout ds-callout-info" style="margin-top:var(--ds-space-sm);font-size:var(--ds-text-xs);">Periods 1D / 1W / 1M / YTD: <strong>unavailable</strong> — backend exposes only Today / Total. Not fabricated.</div>';

    // ── Currency exposure (real) ─────────────────────────────────
    var currRows = UI.statRows(
      Object.keys(currencyExposure).map(function (k) {
        return { label: k, value: fmtMoney(num(currencyExposure[k])), variant: "info" };
      })
    );

    var pnlRow =
      '<div class="dash-grid-2 dash-grid-2-1-1">' +
      '<div class="dash-grid-main">' + UI.panel("P&L Breakdown", pnlRows + pnlNote) + '</div>' +
      '<div class="dash-grid-side">' + UI.panel("Currency Exposure", currRows) + '</div>' +
      '</div>';

    // ── Positions table (real ledger) + Empty state ─────────────
    var posTable;
    if (positions.length === 0) {
      posTable = UI.empty("No Positions", "This portfolio has no open positions. Submit an order to build a position.");
    } else {
      var posRows = positions.map(function (p) {
        var weight = totalEquity > 0 ? (num(p.market_value) / totalEquity) * 100 : 0;
        return {
          symbol: p.symbol,
          account: (p.account_id || "—") + " · " + (p.currency || ""),
          side: sideLabel(p.side),
          quantity: num(p.quantity),
          avgPrice: num(p.average_price),
          last: num(p.last_price),
          mktValue: num(p.market_value),
          unrealized: num(p.unrealized_pnl),
          realized: num(p.realized_pnl),
          weight: weight,
        };
      });
      posTable = UI.table({
        columns: [
          { key: "symbol", label: "Symbol" },
          { key: "account", label: "Account · Curr" },
          { key: "side", label: "Side" },
          { key: "quantity", label: "Qty", numeric: true },
          { key: "avgPrice", label: "Avg Price", numeric: true, format: function (v) { return "$" + v.toFixed(2); } },
          { key: "last", label: "Last Price", numeric: true, format: function (v) { return v > 0 ? "$" + v.toFixed(2) : "—"; } },
          { key: "mktValue", label: "Market Value", numeric: true, format: function (v) { return UI.money(v, 0); } },
          { key: "unrealized", label: "Unreal P&L", numeric: true, format: function (v) { return UI.signedMoney(v); }, color: function (v) { return v >= 0 ? "pos" : "neg"; } },
          { key: "realized", label: "Real P&L", numeric: true, format: function (v) { return UI.signedMoney(v); }, color: function (v) { return v >= 0 ? "pos" : "neg"; } },
          { key: "weight", label: "Weight", numeric: true, format: function (v) { return v.toFixed(1) + "%"; } },
        ],
        rows: posRows,
      });
    }

    // ── Exposure bar (real gross/net + derived long/short) ──────
    var exposureBar =
      '<div class="dash-exposure">' +
      '<div class="dash-exposure-head">' +
      '<span class="dash-exposure-label">Gross Exposure</span>' +
      '<span class="ds-text-mono">' + grossPct.toFixed(1) + '% · ' + fmtMoney(grossExposure) + '</span>' +
      '</div>' +
      '<div class="progress-bar"><div class="progress-fill info" style="width:' + Math.min(grossPct, 100) + '%"></div></div>' +
      '<div class="dash-exposure-legend">' +
      '<span><span class="ds-dot ds-dot-pos"></span>Long ' + fmtMoney(longExposure) + '</span>' +
      '<span><span class="ds-dot ds-dot-neg"></span>Short ' + fmtMoney(shortExposure) + '</span>' +
      '<span><span class="ds-dot ds-dot-info"></span>Cash ' + fmtMoney(cash) + ' (' + cashPct.toFixed(1) + '%)</span>' +
      '</div>' +
      '</div>';

    // ── Risk summary (real) ──────────────────────────────────────
    var riskSummary = UI.statRows([
      { label: "Gross Exposure", value: grossPct.toFixed(1) + "% · " + fmtMoney(grossExposure), variant: "info" },
      { label: "Net Exposure", value: fmtMoney(netExposure), variant: "info" },
      { label: "Long Exposure", value: fmtMoney(longExposure), variant: "pos" },
      { label: "Short Exposure", value: fmtMoney(shortExposure), variant: "neg" },
      { label: "Cash", value: fmtMoney(cash) + " (" + cashPct.toFixed(1) + "%)", variant: "default" },
      { label: "Concentration (Top)", value: topWeight.toFixed(1) + "% · " + esc(topSymbol), variant: "warning" },
      { label: "Drawdown", value: fmtMoney(drawdown), variant: "neg" },
    ]);

    var riskRow =
      '<div class="dash-grid-2 dash-grid-2-1-1">' +
      '<div class="dash-grid-main">' + exposureBar + '</div>' +
      '<div class="dash-grid-side">' + UI.panel("Risk Summary", riskSummary) + '</div>' +
      '</div>';

    return (
      UI.pageHeader("Portfolio", "Portfolio allocation, positions and exposure",
        UI.button("Export", "ghost", { sm: true, action: "pf:export" })) +
      acctBar +
      UI.kpiGrid(kpis, 4) +
      chartsRow +
      pnlRow +
      UI.sectionHeading("Positions",
        UI.button("View All", "ghost", { sm: true, action: "nav:trading/positions" })) +
      UI.panel("Open Positions · " + positions.length + " across " + accounts.length + " accounts", posTable) +
      UI.sectionHeading("Exposure & Risk") +
      riskRow
    );
  };

  /* ==================================================================
   * Research module — Integration 007 (Research API)
   *
   * The Research page is wired to the frozen Factor Discovery v2
   * results through seven read-only endpoints:
   *   - GET /api/dashboard/research/overview        (all runs + funnels)
   *   - GET /api/dashboard/research/runs            (run summaries)
   *   - GET /api/dashboard/research/runs/{run_id}   (single run)
   *   - GET /api/dashboard/research/alphas          (alpha_ranking list)
   *   - GET /api/dashboard/research/alphas/{id}    (alpha detail + family)
   *   - GET /api/dashboard/research/funnel/{id}    (funnel counts)
   *   - GET /api/dashboard/research/decorrelation/{id} (families + reps)
   *
   * No mock data — every funnel count, alpha metric, formula, family
   * member comes straight from report.json. The UI never fabricates
   * research data, never modifies the Factor Engine, never advances
   * factor status, never touches Paper Trading logic.
   * ================================================================== */

  // ── Page state (populated by API; no mock data) ────────────────
  var RESEARCH_STATE = {
    runs: [],            // overview runs (run_id + funnel)
    selectedRunId: "factor-real-d1",  // default to Alpha021's run
    selectedAlphaId: "Alpha021",
    alphas: [],          // alpha_ranking rows for the selected run
    alphaDetail: null,   // detail payload for selected alpha
    decorrelation: null, // decorrelation payload for the selected run
    overview: null,       // overview payload (KPI source)
    lastUpdated: null,
  };

  // Alpha IDs that have been promoted to Paper Trading (frozen research
  // result; display-only — Research UI does NOT advance or read Paper
  // state from the running session).
  var RESEARCH_PAPER_ALPHAS = { "Alpha021": true };

  function factorStatusClass(status) {
    var m = {
      "DISCOVERED": "discovered", "VALIDATED": "validated", "OOS PASSED": "oos",
      "ROBUST": "robust", "CANDIDATE": "candidate", "DECORRELATED": "decorrelated",
      "PAPER": "paper", "SHADOW": "shadow", "LIVE": "live",
      "REJECTED": "rejected",
    };
    return "rs-status rs-status-" + (m[status] || "discovered");
  }

  function factorStatusBadge(status) {
    return '<span class="' + factorStatusClass(status) + '">' + esc(status) + "</span>";
  }

  // ── Numeric helpers (research-specific) ────────────────────────
  function rsNum(v, digits) {
    if (v === null || v === undefined || v === "" || isNaN(v)) return "—";
    return Number(v).toFixed(digits == null ? 3 : digits);
  }
  function rsSigned(v, digits) {
    if (v === null || v === undefined || v === "" || isNaN(v)) return "—";
    var d = digits == null ? 3 : digits;
    return (v >= 0 ? "+" : "") + Number(v).toFixed(d);
  }
  function rsPct(v, digits) {
    if (v === null || v === undefined || v === "" || isNaN(v)) return "—";
    return (v * 100).toFixed(digits == null ? 2 : digits) + "%";
  }

  // Derive display status from an alpha_ranking row + decorrelation info.
  //  - PAPER        if the alpha is in the paper-trading set (frozen)
  //  - DECORRELATED if the alpha is a family representative
  //  - CANDIDATE    if the alpha passed all gates (status == "CANDIDATE")
  //  - REJECTED     otherwise
  function rsAlphaDisplayStatus(alpha) {
    if (RESEARCH_PAPER_ALPHAS[alpha.alpha_id]) return "PAPER";
    if (alpha.is_representative) return "DECORRELATED";
    if (alpha.status === "CANDIDATE") return "CANDIDATE";
    return alpha.status || "REJECTED";
  }

  // ── Funnel visualization (6 stages: Alphas → Pairs → Validation →
  //    OOS → Robustness → De-correlation) ────────────────────────
  function renderFactorFunnel(funnel) {
    if (!funnel) {
      return UI.empty("No funnel data", "Funnel metrics unavailable for this run.");
    }
    var alphasTotal = funnel.alphas_total || 0;
    var stages = [
      { stage: "Alphas",        count: alphasTotal,                       sub: "Alpha candidates generated", variant: "info",    cap: true,  rate: "100%" },
      { stage: "Pairs",         count: funnel.pairs_backtested || 0,      sub: "Pairwise correlations tested", variant: "info",  cap: true,  rate: alphasTotal ? ((funnel.pairs_backtested / alphasTotal).toFixed(1) + "×") : "—" },
      { stage: "Validation",   count: funnel.validation_passed || 0,     sub: "In-sample passed",            variant: "warning", rate: alphasTotal ? rsPct(funnel.validation_passed / alphasTotal, 1) : "—" },
      { stage: "OOS",          count: funnel.oos_passed || 0,            sub: "Out-of-sample passed",         variant: "warning", rate: (funnel.validation_passed) ? rsPct(funnel.oos_passed / funnel.validation_passed, 1) : "—" },
      { stage: "Robustness",   count: funnel.robustness_passed || 0,     sub: "Survivors → Candidates",       variant: "profit",  rate: (funnel.oos_passed) ? rsPct(funnel.robustness_passed / funnel.oos_passed, 1) : "—" },
      { stage: "De-correlation", count: funnel.decorrelated_alphas || 0, sub: "Independent families",        variant: "profit",  rate: (funnel.robustness_passed) ? rsPct(funnel.decorrelated_alphas / funnel.robustness_passed, 1) : "—" },
    ];

    var rows = "";
    stages.forEach(function (s, i) {
      var w = s.cap ? 100 : Math.max(8, Math.round((s.count / Math.max(alphasTotal, 1)) * 100));
      rows +=
        '<div class="rs-funnel-row">' +
        '<div class="rs-funnel-label">' + esc(s.stage) +
        '<span class="rs-funnel-sub">' + esc(s.sub) + "</span></div>" +
        '<div class="rs-funnel-bar-wrap">' +
        '<div class="rs-funnel-bar rs-funnel-bar-' + s.variant + '" style="width:' + w + '%">' +
        '<span class="rs-funnel-count">' + s.count + "</span>" +
        "</div></div>" +
        '<div class="rs-funnel-rate">' + esc(s.rate) + "</div>" +
        "</div>";
      if (i < stages.length - 1) {
        rows += '<div class="rs-funnel-arrow">↓</div>';
      }
    });

    // Terminal: paper-promoted alpha (if any in this run)
    var paperAlpha = null;
    for (var i = 0; i < RESEARCH_STATE.alphas.length; i++) {
      if (RESEARCH_PAPER_ALPHAS[RESEARCH_STATE.alphas[i].alpha_id]) {
        paperAlpha = RESEARCH_STATE.alphas[i].alpha_id;
        break;
      }
    }
    if (paperAlpha) {
      rows +=
        '<div class="rs-funnel-arrow">↓</div>' +
        '<div class="rs-funnel-terminal">' +
        factorStatusBadge("PAPER") +
        '<span class="rs-funnel-terminal-name">' + esc(paperAlpha) + "</span>" +
        "</div>";
    }
    return '<div class="rs-funnel">' + rows + "</div>";
  }

  // ── Experiments / Runs list ────────────────────────────────────
  function renderExperimentsList() {
    var runs = RESEARCH_STATE.runs;
    if (!runs || !runs.length) {
      return UI.empty("No runs", "No experiment runs found in the research output.");
    }
    var html = '<div class="rs-exp-list">';
    runs.forEach(function (r) {
      var isSel = r.run_id === RESEARCH_STATE.selectedRunId ? " rs-exp-item-selected" : "";
      var f = r.funnel || {};
      var candidates = f.final_alphas != null ? f.final_alphas : 0;
      var decorrelated = f.decorrelated_alphas != null ? f.decorrelated_alphas : 0;
      var flow = candidates + " → " + decorrelated;
      html +=
        '<div class="rs-exp-item' + isSel + '" data-rs-exp="' + esc(r.run_id) + '">' +
        '<div class="rs-exp-main">' +
        '<span class="rs-exp-name">' + esc(r.run_id) + "</span>" +
        '<span class="rs-exp-meta">' + esc(r.dataset || "—") + " · " + esc(r.timeframe || "—") +
        " · " + (f.alphas_total || 0) + " alphas · " + candidates + " candidates</span>" +
        "</div>" +
        '<span class="rs-exp-flow">' + esc(flow) + "</span>" +
        "</div>";
    });
    html += "</div>";
    return html;
  }

  // ── Alpha list table (alpha_ranking) ──────────────────────────
  function rsStageBadge(passed) {
    if (passed === true) return '<span class="rs-stage-pass">PASS</span>';
    if (passed === false) return '<span class="rs-stage-fail">FAIL</span>';
    return '<span class="rs-stage-na">—</span>';
  }

  function renderAlphaRows() {
    return RESEARCH_STATE.alphas.map(function (a) {
      var sel = a.alpha_id === RESEARCH_STATE.selectedAlphaId ? " rs-cand-row-selected" : "";
      var dispStatus = rsAlphaDisplayStatus(a);
      var icCls = (a.mean_oos_ic == null) ? "" : (a.mean_oos_ic >= 0 ? "pos" : "neg");
      var sharpeCls = (a.mean_oos_sharpe == null) ? "" : (a.mean_oos_sharpe >= 0 ? "pos" : "neg");
      var retCls = (a.mean_oos_return == null) ? "" : (a.mean_oos_return >= 0 ? "pos" : "neg");
      var family = RESEARCH_STATE.decorrelation && _rsLookupFamily(a.alpha_id) || "—";
      return (
        '<tr class="rs-cand-row' + sel + '" data-rs-alpha="' + esc(a.alpha_id) + '">' +
        '<td class="rs-col-alpha">' + esc(a.alpha_id) +
        (a.is_representative ? ' <span class="rs-rep-mark" title="Family representative">★</span>' : "") +
        "</td>" +
        "<td>" + factorStatusBadge(dispStatus) + "</td>" +
        '<td class="num ds-text-mono ' + icCls + '">' + rsSigned(a.mean_oos_ic) + "</td>" +
        '<td class="num ds-text-mono">' + rsSigned(a.mean_oos_icir) + "</td>" +
        '<td class="num ds-text-mono ' + sharpeCls + '">' + rsNum(a.mean_oos_sharpe, 2) + "</td>" +
        '<td class="num ds-text-mono ' + retCls + '">' + rsPct(a.mean_oos_return, 2) + "</td>" +
        '<td class="num ds-text-mono">' + rsPct(a.mean_max_drawdown, 2) + "</td>" +
        '<td class="num ds-text-mono">' + rsNum(a.mean_turnover, 3) + "</td>" +
        '<td class="num ds-text-mono">' + (a.assets_passed_count != null ? a.assets_passed_count : "—") + "</td>" +
        "<td>" + rsStageBadge(a.oos_passed) + "</td>" +
        "<td>" + rsStageBadge(a.robustness_passed) + "</td>" +
        "<td>" + esc(family) + "</td>" +
        "</tr>"
      );
    }).join("");
  }

  // Look up the de-correlation family name for an alpha id.
  function _rsLookupFamily(alphaId) {
    if (!RESEARCH_STATE.decorrelation) return "—";
    var fams = RESEARCH_STATE.decorrelation.families || [];
    for (var i = 0; i < fams.length; i++) {
      var fam = fams[i];
      if (fam.representative === alphaId) return "Family " + fam.family;
      if ((fam.members || []).indexOf(alphaId) >= 0) return "Family " + fam.family;
    }
    return "—";
  }

  function renderAlphaTable() {
    return (
      '<table class="ds-table rs-cand-table">' +
      "<thead><tr>" +
      "<th>Alpha</th>" +
      "<th>Status</th>" +
      '<th class="num">IC</th>' +
      '<th class="num">ICIR</th>' +
      '<th class="num">Sharpe</th>' +
      '<th class="num">Return</th>' +
      '<th class="num">Max DD</th>' +
      '<th class="num">Turnover</th>' +
      '<th class="num">Coverage</th>' +
      "<th>OOS</th>" +
      "<th>Robustness</th>" +
      "<th>Family</th>" +
      "</tr></thead>" +
      '<tbody id="rs-factor-tbody">' + renderAlphaRows() + "</tbody>" +
      "</table>"
    );
  }

  // ── Alpha Detail panel ────────────────────────────────────────
  function rsDetailCell(label, value, cls) {
    return (
      '<div class="rs-detail-cell"><div class="rs-detail-label">' + esc(label) + "</div>" +
      '<div class="rs-detail-value' + (cls ? " " + cls : "") + '">' + esc(value) + "</div></div>"
    );
  }

  function rsValidationCell(name, result) {
    var pass = result === "PASS";
    var pend = result === "PEND" || result === "—" || !result;
    var cls = pass ? "rs-validation-pass" : (pend ? "rs-validation-pend" : "rs-validation-fail");
    return (
      '<div class="rs-validation-cell"><div class="rs-validation-name">' + esc(name) + "</div>" +
      '<div class="rs-validation-result ' + cls + '">' +
      esc(result || "—") + "</div></div>"
    );
  }

  function renderAlphaDetail() {
    var d = RESEARCH_STATE.alphaDetail;
    var selId = RESEARCH_STATE.selectedAlphaId;
    if (!d) {
      return UI.empty("No alpha selected", "Click an alpha row to inspect its detail.");
    }
    var summary = d.summary || {};
    var family = d.family || null;
    var pairs = d.pairs || [];
    var formula = d.formula || "—";
    var dispStatus = rsAlphaDisplayStatus({
      alpha_id: selId,
      is_representative: !!(family && family.representative === selId),
      status: summary.status || "CANDIDATE",
    });

    // Head: alpha id + status badge
    var head =
      '<div class="rs-detail-head">' +
      '<span class="rs-detail-alpha">' + esc(selId) + "</span>" +
      factorStatusBadge(dispStatus) +
      "</div>";

    // Formula block — show the real Alpha101 expression, not a generic label.
    var formulaBlock =
      UI.sectionHeading("Formula") +
      '<pre class="rs-formula">' + esc(formula) + "</pre>";

    // Validation summary grid (IC / ICIR / Coverage)
    var kpi =
      UI.sectionHeading("Validation") +
      '<div class="rs-detail-grid">' +
      rsDetailCell("Mean IC", rsSigned(summary.mean_oos_ic), (summary.mean_oos_ic >= 0 ? "pos" : "neg")) +
      rsDetailCell("Mean ICIR", rsSigned(summary.mean_oos_icir)) +
      rsDetailCell("Coverage", String(summary.assets_passed_count != null ? summary.assets_passed_count : "—")) +
      "</div>";

    // OOS summary grid (Sharpe / Return / MaxDD)
    var oosKpi =
      UI.sectionHeading("OOS") +
      '<div class="rs-detail-grid">' +
      rsDetailCell("Sharpe", rsNum(summary.mean_oos_sharpe, 2)) +
      rsDetailCell("Return", rsPct(d.mean_oos_return, 2)) +
      rsDetailCell("Max DD", rsPct(d.mean_max_drawdown, 2)) +
      "</div>";

    // Assets block
    var assetsHtml = (summary.assets_passed || [])
      .map(function (a) { return '<span class="rs-asset-chip">' + esc(a) + "</span>"; })
      .join("");
    var assetsBlock =
      '<div style="margin-bottom:var(--ds-space-4);">' +
      '<div class="rs-detail-label" style="margin-bottom:var(--ds-space-2);">Assets Passed</div>' +
      '<div class="rs-detail-assets">' + (assetsHtml || '<span class="rs-perf-empty">—</span>') + "</div></div>";

    // Per-asset OOS performance table (top pairs by score)
    var pairsRows = pairs.slice(0, 6).map(function (p) {
      var icCls = (p.oos_ic == null) ? "" : (p.oos_ic >= 0 ? "pos" : "neg");
      return (
        "<tr>" +
        '<td class="ds-text-mono">' + esc(p.asset) + "</td>" +
        '<td class="num ds-text-mono ' + icCls + '">' + rsSigned(p.oos_ic) + "</td>" +
        '<td class="num ds-text-mono">' + rsNum(p.oos_sharpe, 2) + "</td>" +
        '<td class="num ds-text-mono">' + rsNum(p.oos_return, 3) + "</td>" +
        '<td class="num ds-text-mono">' + rsNum(p.max_drawdown, 3) + "</td>" +
        '<td class="num ds-text-mono">' + rsNum(p.turnover_per_bar, 3) + "</td>" +
        "</tr>"
      );
    }).join("");
    var pairsBlock = pairsRows
      ? (UI.sectionHeading("OOS Performance by Asset") +
        '<table class="ds-table rs-pairs-table">' +
        "<thead><tr>" +
        "<th>Asset</th>" +
        '<th class="num">OOS IC</th>' +
        '<th class="num">Sharpe</th>' +
        '<th class="num">Return</th>' +
        '<th class="num">Max DD</th>' +
        '<th class="num">Turnover</th>' +
        "</tr></thead><tbody>" + pairsRows + "</tbody></table>")
      : "";

    // Robustness block — pass/fail per gate (derived from engine stages)
    var robustnessHtml =
      UI.sectionHeading("Robustness") +
      '<div class="rs-validation-grid">' +
      rsValidationCell("Validation",    d.validation_passed ? "PASS" : "FAIL") +
      rsValidationCell("OOS",           d.oos_passed ? "PASS" : "FAIL") +
      rsValidationCell("Robustness",    d.robustness_passed ? "PASS" : "FAIL") +
      rsValidationCell("De-correlation", family ? "PASS" : "FAIL") +
      "</div>";

    // De-correlation block
    var decHtml = "";
    if (family) {
      var decThresh = RESEARCH_STATE.decorrelation && RESEARCH_STATE.decorrelation.threshold;
      var members = (family.members || []).map(function (m) {
        var isRep = m === family.representative;
        return '<span class="rs-asset-chip' + (isRep ? " rs-asset-chip-rep" : "") + '">' +
          esc(m) + (isRep ? " · REP" : "") + "</span>";
      }).join("");
      decHtml =
        UI.sectionHeading("De-correlation") +
        '<div class="rs-detail-grid">' +
        rsDetailCell("Family", "Family " + family.family) +
        rsDetailCell("Representative", family.representative || "—") +
        rsDetailCell("Intra |ρ|", rsNum(family.intra_mean_abs_corr, 3)) +
        rsDetailCell("Threshold", decThresh != null ? "|ρ| ≥ " + decThresh : "—") +
        "</div>" +
        '<div style="margin-bottom:var(--ds-space-4);">' +
        '<div class="rs-detail-label" style="margin-bottom:var(--ds-space-2);">Members</div>' +
        '<div class="rs-detail-assets">' + members + "</div></div>";
    }

    var html = head + formulaBlock + kpi + oosKpi + assetsBlock + pairsBlock + robustnessHtml + decHtml;

    // Alpha021 Paper Status — display-only, shown only for paper-promoted alphas.
    // Research-side gates are derived from the funnel (this alpha reached De-correlation);
    // Paper-side state is a frozen display constant (Alpha021 is connected and
    // generating signals per the existing factor_gate.py). The Research UI does
    // NOT read live paper-trading state — that lives on the Trading/Paper page.
    if (RESEARCH_PAPER_ALPHAS[selId]) {
      html +=
        UI.sectionHeading("Alpha021 Paper Status") +
        '<div class="rs-paper-status">' +
        '<div class="rs-paper-col">' +
        '<div class="rs-paper-col-title">Research</div>' +
        rsPaperStep("Validation",    "PASS") +
        rsPaperStep("OOS",            "PASS") +
        rsPaperStep("Robustness",     "PASS") +
        rsPaperStep("De-correlation", "PASS") +
        "</div>" +
        '<div class="rs-paper-arrow">→</div>' +
        '<div class="rs-paper-col">' +
        '<div class="rs-paper-col-title">Paper</div>' +
        rsPaperStep("Connected",         "PASS") +
        rsPaperStep("Signals Generated",  "PASS") +
        rsPaperStep("Execution Observed", "PASS") +
        "</div>" +
        "</div>";
    }
    return html;
  }

  function rsPaperStep(label, state) {
    var pass = state === "PASS";
    return (
      '<div class="rs-paper-step">' +
      '<span class="rs-paper-step-icon ' + (pass ? "rs-paper-step-pass" : "rs-paper-step-fail") + '">' +
      (pass ? "✓" : "✗") + "</span>" +
      '<span class="rs-paper-step-label">' + esc(label) + "</span>" +
      "</div>"
    );
  }

  // ── De-correlation Families section ──────────────────────────
  function renderDecorrelationFamilies() {
    var dec = RESEARCH_STATE.decorrelation;
    if (!dec || !dec.families || !dec.families.length) {
      return UI.empty("No families", "No de-correlation families for this run.");
    }
    var threshTxt = dec.threshold != null ? ("|ρ| ≥ " + dec.threshold) : "—";
    var header =
      '<div class="rs-dec-header">' +
      '<span class="rs-dec-threshold">De-correlation Gate · Threshold: ' + esc(threshTxt) + "</span>" +
      '<span class="rs-dec-count">' + dec.n_families + " families</span>" +
      "</div>";
    var cards = dec.families.map(function (f) {
      var members = (f.members || []).map(function (m) {
        var isRep = m === f.representative;
        return '<span class="rs-dec-member' + (isRep ? " rs-dec-member-rep" : "") + '">' +
          esc(m) + (isRep ? ' <span class="rs-dec-rep-tag">REP</span>' : "") + "</span>";
      }).join("");
      return (
        '<div class="rs-dec-card">' +
        '<div class="rs-dec-card-head">' +
        '<span class="rs-dec-card-title">Family ' + esc(f.family) + "</span>" +
        '<span class="rs-dec-card-meta">|ρ| ' + rsNum(f.intra_mean_abs_corr, 3) + " · " +
        (f.members || []).length + " members</span>" +
        "</div>" +
        '<div class="rs-dec-card-members">' + members + "</div>" +
        '<div class="rs-dec-card-rep">Representative: <b>' + esc(f.representative || "—") + "</b></div>" +
        "</div>"
      );
    }).join("");
    return header + '<div class="rs-dec-grid">' + cards + "</div>";
  }

  // ── Research Runs table ───────────────────────────────────────
  function renderResearchRunsTable() {
    var runs = RESEARCH_STATE.runs;
    if (!runs || !runs.length) {
      return UI.empty("No runs", "No experiment runs available.");
    }
    var rows = runs.map(function (r) {
      var f = r.funnel || {};
      var alphas = f.alphas_total || 0;
      var candidates = f.final_alphas != null ? f.final_alphas : 0;
      var dec = f.decorrelated_alphas != null ? f.decorrelated_alphas : 0;
      var ts = r.report_generated_at ? new Date(r.report_generated_at).toLocaleString() : "—";
      var isSel = r.run_id === RESEARCH_STATE.selectedRunId ? " rs-runs-row-selected" : "";
      return (
        '<tr class="rs-runs-row' + isSel + '" data-rs-run="' + esc(r.run_id) + '">' +
        '<td class="rs-col-alpha">' + esc(r.run_id) + "</td>" +
        "<td>" + esc(r.experiment_id || "—") + "</td>" +
        '<td class="ds-text-mono">' + esc(ts) + "</td>" +
        "<td>" + esc((r.universe || []).join(", ") || "—") + "</td>" +
        '<td class="num ds-text-mono">' + esc(r.timeframe || "—") + "</td>" +
        '<td class="num ds-text-mono">' + alphas + "</td>" +
        '<td class="num ds-text-mono">' + candidates + "</td>" +
        '<td class="num ds-text-mono">' + dec + "</td>" +
        "<td>" + factorStatusBadge("Completed") + "</td>" +
        "</tr>"
      );
    }).join("");
    return (
      '<table class="ds-table rs-runs-table">' +
      "<thead><tr>" +
      "<th>Run ID</th>" +
      "<th>Experiment</th>" +
      "<th>Date</th>" +
      "<th>Universe</th>" +
      '<th class="num">TF</th>' +
      '<th class="num">Alphas</th>' +
      '<th class="num">Candidates</th>' +
      '<th class="num">De-correlated</th>' +
      "<th>Status</th>" +
      "</tr></thead><tbody>" + rows + "</tbody></table>"
    );
  }

  // ── Async loaders (follows loadOrdersAsync pattern) ───────────
  async function loadResearchAsync() {
    var refreshBtn = document.querySelector('[data-action="rs:refresh"]');
    if (refreshBtn) { refreshBtn.disabled = true; refreshBtn.textContent = "Refreshing…"; }
    try {
      var runId = RESEARCH_STATE.selectedRunId;
      var results = await Promise.all([
        useResearchOverview(),
        useResearchAlphas(runId),
        useResearchDecorrelation(runId),
      ]);
      RESEARCH_STATE.runs = results[0].runs || [];
      RESEARCH_STATE.alphas = results[1].alphas || [];
      RESEARCH_STATE.decorrelation = results[2] || null;
      RESEARCH_STATE.overview = results[0];
      RESEARCH_STATE.lastUpdated = new Date().toLocaleTimeString("en-US", { hour12: false });

      // If selected alpha is not in this run, pick the first alpha.
      var stillExists = RESEARCH_STATE.alphas.some(function (a) {
        return a.alpha_id === RESEARCH_STATE.selectedAlphaId;
      });
      if (!stillExists) {
        RESEARCH_STATE.selectedAlphaId = RESEARCH_STATE.alphas[0]
          ? RESEARCH_STATE.alphas[0].alpha_id : null;
        RESEARCH_STATE.alphaDetail = null;
        if (RESEARCH_STATE.selectedAlphaId) {
          loadResearchAlphaDetailAsync(RESEARCH_STATE.selectedAlphaId);
        } else {
          var d = document.getElementById("rs-factor-detail");
          if (d) d.innerHTML = renderAlphaDetail();
        }
      } else {
        loadResearchAlphaDetailAsync(RESEARCH_STATE.selectedAlphaId);
      }
      refreshResearchUI();
      showToast("Research refreshed / 研究数据已刷新", "ok");
    } catch (err) {
      showToast("Refresh failed / 刷新失败: " + (err && err.message ? err.message : String(err)), "err");
    } finally {
      if (refreshBtn) { refreshBtn.disabled = false; refreshBtn.textContent = "↻ Refresh"; }
    }
  }

  async function loadResearchAlphaDetailAsync(alphaId) {
    var detailEl = document.getElementById("rs-factor-detail");
    if (detailEl) detailEl.innerHTML = UI.stateLoading("Loading alpha…", "Fetching detail, formula, and de-correlation family.");
    try {
      RESEARCH_STATE.alphaDetail = await useResearchAlphaDetail(
        alphaId, RESEARCH_STATE.selectedRunId
      );
      if (detailEl) detailEl.innerHTML = renderAlphaDetail();
    } catch (err) {
      if (err && err.status === 404) {
        RESEARCH_STATE.alphaDetail = null;
        if (detailEl) detailEl.innerHTML = UI.empty("Alpha not found", "This alpha is not present in the selected run.");
      } else {
        if (detailEl) detailEl.innerHTML = UI.stateError(
          "Failed to load alpha detail",
          (err && err.message ? err.message : String(err)),
          "Retry", "rs:detail-retry"
        );
      }
    }
  }

  // ── View Report (loads report.md for the selected run) ────────
  async function openResearchReport(runId) {
    UI.openModal({
      title: "Research Report — " + (runId || "—"),
      body: UI.stateLoading("Loading report…", "Fetching report.md for this run."),
      footer: UI.button("Close", "ghost", { sm: true, action: "rs:report-close" }),
    });
    try {
      var report = await useResearchReport(runId);
      var fmt = report && report.format;
      var content = report && report.content;
      var bodyHtml;
      if (!content) {
        bodyHtml = UI.empty("No report", "This run has no report.md / report.html.");
      } else if (fmt === "html") {
        bodyHtml = '<div class="rs-report-html">' + content + "</div>";
      } else {
        bodyHtml = '<pre class="rs-report-md">' + esc(content) + "</pre>";
      }
      UI.openModal({
        title: "Research Report — " + (runId || "—"),
        body: bodyHtml,
        footer: UI.button("Close", "ghost", { sm: true, action: "rs:report-close" }),
      });
    } catch (err) {
      UI.openModal({
        title: "Research Report — " + (runId || "—"),
        body: UI.stateError(
          "Failed to load report",
          (err && err.message ? err.message : String(err)),
          "Retry", "rs:report-retry"
        ),
        footer: UI.button("Close", "ghost", { sm: true, action: "rs:report-close" }),
      });
    }
  }

  // Re-render all in-place UI pieces after a refresh / run switch.
  function refreshResearchUI() {
    var tbody = document.getElementById("rs-factor-tbody");
    if (tbody) tbody.innerHTML = renderAlphaRows();
    var detail = document.getElementById("rs-factor-detail");
    if (detail) detail.innerHTML = renderAlphaDetail();
    var funnelEl = document.getElementById("rs-funnel");
    if (funnelEl) {
      var f = _rsCurrentFunnel();
      funnelEl.innerHTML = renderFactorFunnel(f);
    }
    var expEl = document.getElementById("rs-exp-list");
    if (expEl) expEl.innerHTML = renderExperimentsList();
    var decEl = document.getElementById("rs-dec-families");
    if (decEl) decEl.innerHTML = renderDecorrelationFamilies();
    var runsEl = document.getElementById("rs-runs-tbody");
    if (runsEl) runsEl.innerHTML = renderResearchRunsTableRows();
    var kpiEl = document.getElementById("rs-kpis");
    if (kpiEl) kpiEl.innerHTML = renderResearchKPIs();
    // Re-bind experiment rows (innerhtml replaced).
    _bindExpRows();
  }

  function _rsCurrentFunnel() {
    for (var i = 0; i < RESEARCH_STATE.runs.length; i++) {
      if (RESEARCH_STATE.runs[i].run_id === RESEARCH_STATE.selectedRunId) {
        return RESEARCH_STATE.runs[i].funnel || null;
      }
    }
    return null;
  }

  function renderResearchRunsTableRows() {
    // Wrapper used by refreshResearchUI — returns just the tbody rows.
    var runs = RESEARCH_STATE.runs;
    if (!runs || !runs.length) return "";
    return runs.map(function (r) {
      var f = r.funnel || {};
      var alphas = f.alphas_total || 0;
      var candidates = f.final_alphas != null ? f.final_alphas : 0;
      var dec = f.decorrelated_alphas != null ? f.decorrelated_alphas : 0;
      var ts = r.report_generated_at ? new Date(r.report_generated_at).toLocaleString() : "—";
      var isSel = r.run_id === RESEARCH_STATE.selectedRunId ? " rs-runs-row-selected" : "";
      return (
        '<tr class="rs-runs-row' + isSel + '" data-rs-run="' + esc(r.run_id) + '">' +
        '<td class="rs-col-alpha">' + esc(r.run_id) + "</td>" +
        "<td>" + esc(r.experiment_id || "—") + "</td>" +
        '<td class="ds-text-mono">' + esc(ts) + "</td>" +
        "<td>" + esc((r.universe || []).join(", ") || "—") + "</td>" +
        '<td class="num ds-text-mono">' + esc(r.timeframe || "—") + "</td>" +
        '<td class="num ds-text-mono">' + alphas + "</td>" +
        '<td class="num ds-text-mono">' + candidates + "</td>" +
        '<td class="num ds-text-mono">' + dec + "</td>" +
        "<td>" + factorStatusBadge("Completed") + "</td>" +
        "</tr>"
      );
    }).join("");
  }

  function renderResearchKPIs() {
    var f = _rsCurrentFunnel() || {};
    var totalAlphas    = f.alphas_total || 0;
    var pairsTested    = f.pairs_backtested || 0;
    var validationP   = f.validation_passed || 0;
    var oosP          = f.oos_passed || 0;
    var robustP       = f.robustness_passed || 0;
    var decP          = f.decorrelated_alphas || 0;
    return (
      UI.metricCard("Total Alphas",     String(totalAlphas), "Alpha candidates", "") +
      UI.metricCard("Pairs Tested",     String(pairsTested), "Pairwise correlations", "info") +
      UI.metricCard("Validation Passed", String(validationP), totalAlphas ? rsPct(validationP / totalAlphas, 1) : "—", "warning") +
      UI.metricCard("OOS Passed",       String(oosP), validationP ? rsPct(oosP / validationP, 1) : "—", "warning") +
      UI.metricCard("Robustness Passed", String(robustP), oosP ? rsPct(robustP / oosP, 1) : "—", "pos") +
      UI.metricCard("De-correlated",    String(decP), robustP ? rsPct(decP / robustP, 1) : "—", "pos")
    );
  }

  function rsHeaderSelect(id, options, selected) {
    return '<div style="min-width:160px;">' +
      UI.select({ id: id, options: options, value: selected }) + "</div>";
  }

  // ── Bind: delegated handlers on #rs-root (survive innerHTML) ──
  function _bindExpRows() {
    document.querySelectorAll("[data-rs-exp]").forEach(function (el) {
      el.addEventListener("click", function () {
        var newRun = el.getAttribute("data-rs-exp");
        if (newRun && newRun !== RESEARCH_STATE.selectedRunId) {
          RESEARCH_STATE.selectedRunId = newRun;
          // Reset alpha selection — let loadResearchAsync pick a sensible default.
          RESEARCH_STATE.selectedAlphaId = null;
          RESEARCH_STATE.alphaDetail = null;
          loadResearchAsync();
        }
      });
    });
  }

  function bindResearchPage() {
    var root = document.getElementById("rs-root");
    if (!root) return;

    // Lazy-load detail for pre-selected alpha (if not already loaded)
    if (RESEARCH_STATE.selectedAlphaId && !RESEARCH_STATE.alphaDetail) {
      loadResearchAlphaDetailAsync(RESEARCH_STATE.selectedAlphaId);
    }

    // Single delegated click handler on root
    root.addEventListener("click", function (e) {
      // Refresh button
      var btn = e.target.closest("[data-action]");
      if (btn) {
        var action = btn.getAttribute("data-action");
        if (action === "rs:refresh") { loadResearchAsync(); return; }
        if (action === "rs:detail-retry" && RESEARCH_STATE.selectedAlphaId) {
          loadResearchAlphaDetailAsync(RESEARCH_STATE.selectedAlphaId); return;
        }
        if (action === "rs:run-refresh") { loadResearchAsync(); return; }
        if (action === "rs:view-report") { openResearchReport(RESEARCH_STATE.selectedRunId); return; }
        if (action === "rs:report-close") { UI.closeModal(); return; }
        if (action === "rs:report-retry") { openResearchReport(RESEARCH_STATE.selectedRunId); return; }
        return;
      }
      // Alpha row selection (delegated on tbody rows)
      var row = e.target.closest("tr[data-rs-alpha]");
      if (row) {
        var newAlpha = row.getAttribute("data-rs-alpha");
        if (newAlpha && newAlpha !== RESEARCH_STATE.selectedAlphaId) {
          RESEARCH_STATE.selectedAlphaId = newAlpha;
          // Update row highlights without re-rendering the table
          var tbody = document.getElementById("rs-factor-tbody");
          if (tbody) tbody.querySelectorAll("tr").forEach(function (tr) {
            tr.classList.remove("rs-cand-row-selected");
          });
          row.classList.add("rs-cand-row-selected");
          loadResearchAlphaDetailAsync(newAlpha);
        }
        return;
      }
      // Run row selection (Research Runs table)
      var runRow = e.target.closest("tr[data-rs-run]");
      if (runRow) {
        var newRun = runRow.getAttribute("data-rs-run");
        if (newRun && newRun !== RESEARCH_STATE.selectedRunId) {
          RESEARCH_STATE.selectedRunId = newRun;
          RESEARCH_STATE.selectedAlphaId = null;
          RESEARCH_STATE.alphaDetail = null;
          loadResearchAsync();
        }
        return;
      }
    });

    // Run selector in the page header
    var runSel = document.getElementById("rs-filter-exp");
    if (runSel) {
      runSel.value = RESEARCH_STATE.selectedRunId;
      runSel.addEventListener("change", function () {
        var v = runSel.value;
        if (v && v !== RESEARCH_STATE.selectedRunId) {
          RESEARCH_STATE.selectedRunId = v;
          RESEARCH_STATE.selectedAlphaId = null;
          RESEARCH_STATE.alphaDetail = null;
          loadResearchAsync();
        }
      });
    }

    _bindExpRows();
  }

  // ── Research (Integration 007 — real Research API data) ────────
  PAGE_FRAMEWORK["research"] = async function () {
    // Initial load — throws on failure → render() catch → stateError + Retry.
    var runId = RESEARCH_STATE.selectedRunId;
    var results = await Promise.all([
      useResearchOverview(),
      useResearchAlphas(runId),
      useResearchDecorrelation(runId),
    ]);
    RESEARCH_STATE.runs = results[0].runs || [];
    RESEARCH_STATE.alphas = results[1].alphas || [];
    RESEARCH_STATE.decorrelation = results[2] || null;
    RESEARCH_STATE.overview = results[0];
    RESEARCH_STATE.lastUpdated = new Date().toLocaleTimeString("en-US", { hour12: false });

    // Pick a sensible default alpha if the cached one isn't in this run.
    var stillExists = RESEARCH_STATE.alphas.some(function (a) {
      return a.alpha_id === RESEARCH_STATE.selectedAlphaId;
    });
    if (!stillExists) {
      // Prefer Alpha021 if present (paper-promoted), else first.
      var a021 = RESEARCH_STATE.alphas.filter(function (a) {
        return RESEARCH_PAPER_ALPHAS[a.alpha_id];
      })[0];
      RESEARCH_STATE.selectedAlphaId = a021 ? a021.alpha_id :
        (RESEARCH_STATE.alphas[0] ? RESEARCH_STATE.alphas[0].alpha_id : null);
      RESEARCH_STATE.alphaDetail = null;
    }

    var runOptions = RESEARCH_STATE.runs.map(function (r) {
      return { value: r.run_id, label: r.run_id };
    });
    if (!runOptions.length) {
      runOptions = [{ value: RESEARCH_STATE.selectedRunId, label: RESEARCH_STATE.selectedRunId }];
    }

    var headerActions =
      rsHeaderSelect("rs-filter-exp", runOptions, RESEARCH_STATE.selectedRunId) +
      UI.button("Refresh", "ghost", { sm: true, action: "rs:refresh" });

    var funnel = _rsCurrentFunnel();
    var lastUpd = RESEARCH_STATE.lastUpdated || "—";

    var grid =
      '<div class="rs-grid-2">' +
      '<div class="rs-grid-main">' +
      UI.panel("Recent Experiments",
        '<div id="rs-exp-list">' + renderExperimentsList() + "</div>",
        { actions: '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);">Click to switch run · updated ' + esc(lastUpd) + "</span>" }
      ) +
      "</div>" +
      '<div class="rs-grid-side">' +
      UI.panel("Factor Funnel",
        '<div id="rs-funnel">' + renderFactorFunnel(funnel) + "</div>"
      ) +
      "</div>" +
      "</div>";

    var candLayout =
      '<div class="rs-cand-layout">' +
      '<div class="rs-cand-main">' +
      UI.panel("Alpha List", renderAlphaTable(), {
        actions: '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);">Click a row to inspect</span>',
      }) +
      "</div>" +
      '<div class="rs-cand-side">' +
      UI.panel("Alpha Detail", '<div id="rs-factor-detail">' + renderAlphaDetail() + "</div>") +
      "</div>" +
      "</div>";

    return (
      '<div id="rs-root">' +
      UI.pageHeader("Research", "Factor Discovery v2 — frozen research results (read-only)",
        headerActions) +
      '<div id="rs-kpis">' + UI.kpiGrid(renderResearchKPIs(), 6) + '</div>' +
      grid +
      UI.sectionHeading("Alpha List") +
      candLayout +
      UI.sectionHeading("De-correlation Families") +
      UI.panel("De-correlation Gate",
        '<div id="rs-dec-families">' + renderDecorrelationFamilies() + "</div>",
        { actions: '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);">Frozen research output</span>' }
      ) +
      UI.sectionHeading("Research Runs") +
      UI.panel("Experiment Runs",
        '<div id="rs-runs-tbody-wrap">' +
        '<table class="ds-table rs-runs-table">' +
        "<thead><tr>" +
        "<th>Run ID</th><th>Experiment</th><th>Date</th><th>Universe</th>" +
        '<th class="num">TF</th><th class="num">Alphas</th>' +
        '<th class="num">Candidates</th><th class="num">De-correlated</th><th>Status</th>' +
        "</tr></thead><tbody>" + renderResearchRunsTableRows() + "</tbody></table></div>",
        { actions: UI.button("Refresh", "ghost", { sm: true, action: "rs:run-refresh" }) +
                   UI.button("View Report", "ghost", { sm: true, action: "rs:view-report" }) }
      ) +
      "</div>"
    );
  };

  /* ==================================================================
   * Strategy module — Integration 009 (real Strategy API)
   * Strategy lifecycle management center: list → detail (tabs) →
   * lifecycle → validation → signals. Data comes from
   * GET /dashboard/strategy/catalog (research funnel mapped onto the
   * lifecycle) plus /catalog/{id} (research block + paper replay +
   * backtest history). Rendering only: the quant core stays frozen.
   * ================================================================== */

  // ── Strategy data ──────────────────────────────────────────────
  var ST_LIFECYCLE_STAGES = ["Research", "Validation", "De-correlation", "Paper", "Shadow", "Live"];

  // lifecycle state per strategy status (index-aligned to ST_LIFECYCLE_STAGES)
  // values: passed | running | pending | locked | paused
  var ST_LIFECYCLE_MAP = {
    CANDIDATE: ["passed", "running", "pending", "locked", "locked", "locked"],
    VALIDATED: ["passed", "passed", "passed", "pending", "locked", "locked"],
    PAPER:     ["passed", "passed", "passed", "running", "pending", "locked"],
    SHADOW:    ["passed", "passed", "passed", "passed", "running", "pending"],
    LIVE:      ["passed", "passed", "passed", "passed", "passed", "running"],
    PAUSED:    ["passed", "passed", "passed", "paused", "locked", "locked"],
    RETIRED:   ["passed", "passed", "passed", "passed", "passed", "passed"],
  };
  var ST_LC_ICON = { passed: "✓", running: "●", pending: "○", locked: "🔒", paused: "⏸" };
  var ST_LC_STATE = { passed: "PASSED", running: "RUNNING", pending: "NOT STARTED", locked: "LOCKED", paused: "PAUSED" };

  // ── Strategy data (Integration 009: real Strategy API) ─────────
  // ST_STATE.catalog mirrors GET /dashboard/strategy/catalog and
  // ST_STATE.detail the selected strategy's
  // GET /dashboard/strategy/catalog/{id} payload. The quant core
  // (research pipeline, paper replay, backtest engine) stays frozen —
  // this layer only renders what the backend actually computed.
  var ST_STATE = {
    selectedId: null,       // strategy id (== alpha_id, lowercase)
    signalFilter: "ALL",    // ALL | BUY | SELL
    catalog: null,          // {source, counts, strategies[]} (catalog API)
    detail: null,           // detail payload for the selected strategy
    detailStatus: "idle",   // idle | loading | done | error
    error: null,            // message from the last failed catalog load
  };

  function stPct(x) {
    return x == null ? "—" : (x >= 0 ? "+" : "") + (x * 100).toFixed(2) + "%";
  }
  function stNum(x, d) { return x == null ? "—" : Number(x).toFixed(d); }
  function stStatusBadge(status) {
    return '<span class="st-status st-status-' + (status || "").toLowerCase() + '">' + esc(status) + "</span>";
  }
  function stStrategies() {
    return (ST_STATE.catalog && ST_STATE.catalog.strategies) || [];
  }
  function stFind(id) {
    var list = stStrategies();
    for (var i = 0; i < list.length; i++) {
      if (list[i].id === id) return list[i];
    }
    return list[0] || null;
  }
  // Selected strategy = catalog row merged with the detail payload once
  // it arrives (the detail carries the same headline fields plus the
  // research / paper / history blocks).
  function stSelected() {
    var row = stFind(ST_STATE.selectedId);
    if (!row) return null;
    if (ST_STATE.detail && ST_STATE.detail.id === row.id) return ST_STATE.detail;
    return row;
  }
  // True once the detail payload for the current selection has loaded —
  // tabs that depend on it render a loading state until then.
  function stDetailReady() {
    var row = stFind(ST_STATE.selectedId);
    return !!(row && ST_STATE.detail && ST_STATE.detail.id === row.id);
  }
  function stBtRunCount(s) {
    if (Array.isArray(s.backtest_runs)) return s.backtest_runs.length;
    return s.backtest_run_count || 0;
  }

  // ── KPI grid (real catalog counts) ─────────────────────────────
  function renderStKpis() {
    var c = (ST_STATE.catalog && ST_STATE.catalog.counts) || {};
    var cards =
      UI.metricCard("Strategies", String(c.total || 0), "", "") +
      UI.metricCard("Active", String(c.active || 0), "", "pos") +
      UI.metricCard("Paper", String(c.paper || 0), "", "") +
      UI.metricCard("Shadow", String(c.shadow || 0), "", "") +
      UI.metricCard("Live", String(c.live || 0), "", (c.live || 0) > 0 ? "pos" : "");
    return '<div class="st-kpi-grid">' + cards + "</div>";
  }

  // ── Strategy list (clickable rows, real catalog) ───────────────
  function renderStRows() {
    return stStrategies().map(function (s) {
      var sel = s.id === ST_STATE.selectedId ? " st-row-selected" : "";
      var retCls = s.ret == null ? "" : s.ret >= 0 ? "pos" : "neg";
      return (
        '<tr class="st-row' + sel + '" data-st-id="' + esc(s.id) + '">' +
        '<td class="st-col-name">' + esc(s.name) + "</td>" +
        "<td>" + esc(s.type) + "</td>" +
        "<td>" + esc((s.universe || []).join(" / ")) + "</td>" +
        '<td class="num">' + esc(s.timeframe) + "</td>" +
        "<td>" + stStatusBadge(s.status) + "</td>" +
        '<td class="num ' + retCls + '">' + stPct(s.ret) + "</td>" +
        '<td class="num">' + stNum(s.sharpe, 2) + "</td>" +
        '<td class="num neg">' + stPct(s.max_dd) + "</td>" +
        "</tr>"
      );
    }).join("");
  }

  function renderStList() {
    return (
      '<table class="ds-table st-list-table">' +
      "<thead><tr>" +
      "<th>Strategy</th><th>Type</th><th>Asset</th>" +
      '<th class="num">Timeframe</th><th>Status</th>' +
      '<th class="num">Return</th><th class="num">Sharpe</th><th class="num">Max DD</th>' +
      "</tr></thead>" +
      '<tbody id="st-list-tbody">' + renderStRows() + "</tbody>" +
      "</table>"
    );
  }

  // ── Lifecycle stepper ──────────────────────────────────────────
  function renderStLifecycle(s) {
    var states = ST_LIFECYCLE_MAP[s.status] || ST_LIFECYCLE_MAP.VALIDATED;
    var html = '<div class="st-lifecycle">';
    for (var i = 0; i < ST_LIFECYCLE_STAGES.length; i++) {
      var st = states[i];
      html +=
        '<div class="st-lc-stage st-lc-' + st + '">' +
        '<div class="st-lc-icon">' + ST_LC_ICON[st] + "</div>" +
        '<div class="st-lc-label">' + esc(ST_LIFECYCLE_STAGES[i]) + "</div>" +
        '<div class="st-lc-state">' + ST_LC_STATE[st] + "</div>" +
        "</div>";
      if (i < ST_LIFECYCLE_STAGES.length - 1) {
        var connCls = states[i] === "passed" ? " st-lc-conn-done" : "";
        html += '<div class="st-lc-connector' + connCls + '"></div>';
      }
    }
    return html + "</div>";
  }

  // ── Detail header + actions ────────────────────────────────────
  function renderStActions(s) {
    // Only the frozen alpha carries a paper replay; everything else is a
    // research-run strategy, so its paper button stays locked.
    var hasPaper = s.metrics_source === "paper-replay";
    var runBtn = hasPaper
      ? UI.button("Pause Paper", "secondary", { sm: true, action: "st:pause" })
      : '<span class="st-action-locked"><span class="st-lock-icon">🔒</span>' +
        UI.button("Paper", "secondary", { sm: true, disabled: true }) + "</span>";
    return (
      UI.button("Backtest", "ghost", { sm: true, action: "st:backtest" }) +
      runBtn +
      UI.button("View Signals", "ghost", { sm: true, action: "st:view-signals" }) +
      '<span class="st-action-locked"><span class="st-lock-icon">🔒</span>' + UI.button("Shadow", "secondary", { sm: true, disabled: true }) + "</span>" +
      '<span class="st-action-locked"><span class="st-lock-icon">🔒</span>' + UI.button("Live", "secondary", { sm: true, disabled: true }) + "</span>" +
      UI.button("Configure", "secondary", { sm: true, action: "st:configure" })
    );
  }

  function stSummaryCell(label, value, cls) {
    return (
      '<div class="st-summary-cell">' +
      '<div class="st-summary-label">' + esc(label) + "</div>" +
      '<div class="st-summary-value' + (cls ? " " + cls : "") + '">' + esc(value) + "</div>" +
      "</div>"
    );
  }

  function renderStOverviewTab(s) {
    var paper = s.paper || null;
    var meta = (paper && paper.meta) || {};
    var research = s.research || null;
    var btCount = stBtRunCount(s);
    return '<div class="st-summary-grid">' +
      stSummaryCell("Status", s.status) +
      stSummaryCell("Type", s.type) +
      stSummaryCell("Universe", (s.universe || []).join(" / ")) +
      stSummaryCell("Timeframe", s.timeframe) +
      stSummaryCell("Source Run", s.version) +
      stSummaryCell("Capital", paper ? UI.money(meta.initial_capital || 0, 0) : "—") +
      stSummaryCell("Family", research && research.family ? research.family : "—") +
      stSummaryCell("Rank", research && research.rank != null ? "#" + research.rank : "—") +
      stSummaryCell("Metrics Source", paper ? "Paper replay" : "Research run (OOS)") +
      stSummaryCell("Execution", paper ? paper.execution.venue : "—") +
      stSummaryCell("Backtest Runs", String(btCount)) +
      "</div>";
  }

  function renderStPerformanceTab(s) {
    return '<div class="st-kpi-grid">' +
      UI.metricCard("Return", stPct(s.ret), "", s.ret == null ? "" : s.ret >= 0 ? "pos" : "neg") +
      UI.metricCard("Sharpe", stNum(s.sharpe, 2), "", "") +
      UI.metricCard("Max Drawdown", stPct(s.max_dd), "", "neg") +
      UI.metricCard("Win Rate", stPct(s.win_rate), "", "") +
      UI.metricCard("Turnover", s.turnover == null ? "—" : stNum(s.turnover, 2) + "x", "", "") +
      "</div>";
  }

  // ── Signals tab (filterable) ───────────────────────────────────
  function stSignalSide(side) {
    var cls = side === "BUY" ? "st-signal-buy" : "st-signal-sell";
    return '<span class="st-signal-side ' + cls + '">' + esc(side) + "</span>";
  }

  function renderStSignalsRows(s) {
    var sigs = (s.paper && s.paper.trades) || [];
    var filtered = sigs.filter(function (sig) {
      return ST_STATE.signalFilter === "ALL" || sig.side === ST_STATE.signalFilter;
    });
    if (!filtered.length) {
      return '<tr><td colspan="5">' + UI.empty("No signals", "No signals match the current filter.") + "</td></tr>";
    }
    return filtered.map(function (sig) {
      var outcome = sig.outcome || "—";
      var outcomeCls = outcome === "FILLED" ? "pos" : outcome === "REJECTED" ? "neg" : "";
      return "<tr>" +
        '<td class="num">' + esc(sig.date) + "</td>" +
        "<td>" + esc(sig.symbol) + "</td>" +
        "<td>" + stSignalSide(sig.side) + "</td>" +
        '<td class="num">' + esc(sig.qty) + "</td>" +
        '<td class="num ' + outcomeCls + '">' + esc(outcome) + "</td>" +
        "</tr>";
    }).join("");
  }

  function renderStSignalsTab(s) {
    if (!stDetailReady()) return UI.loading("Loading signal log…");
    if (!s.paper) {
      return UI.empty("Not in paper trading",
        "Signal logs exist only for strategies with a paper replay — currently the frozen Alpha021.");
    }
    var filters = ["ALL", "BUY", "SELL"];
    var filterHtml = filters.map(function (f) {
      var active = ST_STATE.signalFilter === f ? " active" : "";
      return '<button class="st-filter-btn' + active + '" data-st-filter="' + f + '">' + f + "</button>";
    }).join("");
    return '<div class="st-signal-filters">' + filterHtml + "</div>" +
      '<table class="ds-table st-signals-table">' +
      "<thead><tr>" +
      '<th class="num">Time</th><th>Symbol</th><th>Signal</th><th class="num">Qty</th><th class="num">Outcome</th>' +
      "</tr></thead>" +
      '<tbody id="st-signals-tbody">' + renderStSignalsRows(s) + "</tbody>" +
      "</table>";
  }

  function updateStSignals() {
    var s = stSelected();
    var tbody = document.getElementById("st-signals-tbody");
    if (tbody && s) tbody.innerHTML = renderStSignalsRows(s);
    document.querySelectorAll("[data-st-filter]").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-st-filter") === ST_STATE.signalFilter);
    });
  }

  // ── Positions / Risk / Execution / Validation / History tabs ──
  function renderStPositionsTab(s) {
    if (!stDetailReady()) return UI.loading("Loading positions…");
    if (!s.paper) {
      return UI.empty("Not in paper trading",
        "Positions exist only for strategies with a paper replay — currently the frozen Alpha021.");
    }
    return UI.table({
      columns: [
        { key: "symbol", label: "Symbol" },
        { key: "side", label: "Side" },
        { key: "qty", label: "Qty", numeric: true },
        { key: "entry", label: "Entry", numeric: true, format: function (v) { return UI.money(v); } },
        { key: "current", label: "Current", numeric: true, format: function (v) { return UI.money(v); } },
        { key: "pnl", label: "PnL", numeric: true, color: function (v) { return v >= 0 ? "pos" : "neg"; }, format: function (v) { return UI.signedMoney(v); } },
      ],
      rows: s.paper.positions || [],
    });
  }

  function renderStRiskTab(s) {
    if (!stDetailReady()) return UI.loading("Loading risk metrics…");
    if (!s.paper) {
      return UI.empty("Not in paper trading",
        "Risk metrics exist only for strategies with a paper replay — currently the frozen Alpha021.");
    }
    return '<div class="st-kpi-grid">' +
      UI.metricCard("Max Drawdown", stPct(s.max_dd), "", "neg") +
      UI.metricCard("Exposure", stPct(s.paper.exposure), "", "") +
      UI.metricCard("Position Limit", String((s.paper.positions || []).length), "", "") +
      UI.metricCard("Daily Loss", "—", "", "") +
      UI.metricCard("VaR Limit", "—", "", "") +
      "</div>";
  }

  function renderStExecutionTab(s) {
    if (!stDetailReady()) return UI.loading("Loading execution config…");
    if (!s.paper) {
      return UI.empty("Not in paper trading",
        "Execution settings exist only for strategies with a paper replay — currently the frozen Alpha021.");
    }
    var e = s.paper.execution || {};
    return '<div class="st-summary-grid">' +
      stSummaryCell("Venue", e.venue) +
      stSummaryCell("Order Type", e.order_type) +
      stSummaryCell("TIF", e.tif) +
      stSummaryCell("Slippage", e.slippage) +
      "</div>";
  }

  // Validation tab = the *real* research funnel for this alpha:
  // stage flags, per-asset reject reasons and the OOS aggregates from
  // the source research run.
  function renderStValidationTab(s) {
    if (!stDetailReady()) return UI.loading("Loading validation data…");
    var r = s.research || {};
    var checks = [
      { label: "Validation", value: r.validation_passed },
      { label: "OOS", value: r.oos_passed },
      { label: "Robustness", value: r.robustness_passed },
      { label: "De-correlation", value: r.family ? true : null },
    ];
    var driftHtml = checks.map(function (c) {
      var cls = c.value === true ? "st-drift-normal"
        : c.value === false ? "st-drift-failed" : "st-drift-pending";
      var txt = c.value === true ? "PASSED"
        : c.value === false ? "FAILED" : "N/A";
      return '<div class="st-drift-cell">' +
        '<div class="st-drift-label">' + esc(c.label) + "</div>" +
        '<div class="st-drift-value ' + cls + '">' + txt + "</div>" +
        "</div>";
    }).join("");
    var oosCards =
      UI.metricCard("Mean OOS IC", stNum(r.mean_oos_ic, 4), "", "") +
      UI.metricCard("Mean OOS Rank IC", stNum(r.mean_oos_rank_ic, 4), "", "") +
      UI.metricCard("Mean OOS ICIR", stNum(r.mean_oos_icir, 2), "", "") +
      UI.metricCard("Mean OOS Sharpe", stNum(r.mean_oos_sharpe, 2), "", "") +
      UI.metricCard("Breadth", r.breadth == null ? "—" : String(r.breadth), "", "");
    var rejects = r.reject_reasons || {};
    var rejectRows = Object.keys(rejects).map(function (k) {
      return "<tr><td>" + esc(k) + '</td><td class="num">' +
        esc(String(rejects[k])) + "</td></tr>";
    }).join("");
    return '<div class="st-drift">' + driftHtml + "</div>" +
      UI.panel("Research OOS Metrics — run " + esc(r.run_id || s.version),
        '<div class="st-kpi-grid">' + oosCards + "</div>") +
      (rejectRows
        ? UI.panel("Per-Asset Reject Reasons",
            '<table class="ds-table st-compare-table">' +
            "<thead><tr><th>Check</th><th class=\"num\">Assets Failed</th></tr></thead>" +
            "<tbody>" + rejectRows + "</tbody></table>")
        : UI.empty("No reject reasons recorded",
            "This alpha passed every per-asset check in the source run."));
  }

  function renderStHistoryTab(s) {
    if (!stDetailReady()) return UI.loading("Loading lifecycle history…");
    var rows = s.history || [];
    if (!rows.length) {
      return UI.empty("No history yet", "Lifecycle events appear as the strategy progresses through the pipeline.");
    }
    return UI.table({
      columns: [
        { key: "date", label: "Date" },
        { key: "event", label: "Event" },
        { key: "detail", label: "Detail" },
      ],
      rows: rows,
    });
  }

  function renderStDetail() {
    var s = stSelected();
    if (!s) {
      return UI.empty("No strategy selected",
        "Select a strategy from the catalog above.");
    }
    return (
      '<div class="st-detail-head">' +
      '<div class="st-detail-title">' +
      '<span class="st-detail-name">' + esc(s.name) + "</span>" +
      stStatusBadge(s.status) +
      '<span class="st-detail-meta">' +
      esc((s.universe || []).join(" / ")) +
      '<span class="st-sep">·</span>' + esc(s.timeframe) +
      '<span class="st-sep">·</span>' + esc("run " + (s.version || "—")) +
      "</span>" +
      "</div>" +
      '<div class="st-actions">' + renderStActions(s) + "</div>" +
      "</div>" +
      renderStLifecycle(s) +
      UI.tabs([
        { id: "st-overview", label: "Overview", content: renderStOverviewTab(s) },
        { id: "st-performance", label: "Performance", content: renderStPerformanceTab(s) },
        { id: "st-signals", label: "Signals", content: renderStSignalsTab(s) },
        { id: "st-positions", label: "Positions", content: renderStPositionsTab(s) },
        { id: "st-risk", label: "Risk", content: renderStRiskTab(s) },
        { id: "st-execution", label: "Execution", content: renderStExecutionTab(s) },
        { id: "st-validation", label: "Validation", content: renderStValidationTab(s) },
        { id: "st-history", label: "History", content: renderStHistoryTab(s) },
      ])
    );
  }

  function updateStDetail() {
    var host = document.getElementById("st-detail");
    if (host) {
      host.innerHTML = renderStDetail();
      UI.bindTabs(host);
    }
  }

  // ── Config drawer body ─────────────────────────────────────────
  function renderStConfigBody(s) {
    var universeChecks = ["NVDA", "QQQ", "SPY", "AAPL", "MSFT"].map(function (sym) {
      var checked = s.universe.indexOf(sym) >= 0 ? " checked" : "";
      return '<label class="st-check"><input type="checkbox"' + checked + ">" + esc(sym) + "</label>";
    }).join("");
    return '<div class="st-config-grid">' +
      UI.field("Name", UI.input({ value: s.name })) +
      '<div class="ds-field"><label class="ds-field-label">Universe</label><div class="st-universe-checks">' + universeChecks + "</div></div>" +
      UI.field("Timeframe", UI.select({ value: s.timeframe, options: ["1D", "1H", "30m", "15m", "5m"] })) +
      '<div class="st-config-row">' +
      UI.field("Capital", UI.input({ type: "number", value: s.capital || 1000000, step: "1000" })) +
      UI.field("Position Size", UI.input({ type: "number", value: s.positionSize || 100, step: "10" })) +
      "</div>" +
      '<div class="st-config-row">' +
      UI.field("Max Position", UI.input({ type: "number", value: s.maxPosition || 5, step: "1" })) +
      UI.field("Risk Limit (%)", UI.input({ type: "number", value: ((s.riskLimit || 0.06) * 100).toFixed(2), step: "0.5" })) +
      "</div>" +
      UI.field("Execution", UI.select({ value: s.execution || "Paper", options: ["Paper", "Shadow", "Live"] })) +
      "</div>";
  }

  // ── Data loading (Strategy API, Integration 009) ────────────────
  async function stLoadCatalog(force) {
    if (ST_STATE.catalog && !force) return;
    var data = await api.strategyCatalog();
    ST_STATE.catalog = data;
    ST_STATE.error = null;
    if (!stFind(ST_STATE.selectedId)) {
      ST_STATE.selectedId = data.strategies.length ? data.strategies[0].id : null;
      ST_STATE.detail = null;
      ST_STATE.detailStatus = "idle";
    }
  }

  async function stLoadDetail() {
    var id = ST_STATE.selectedId;
    if (!id) return;
    ST_STATE.detailStatus = "loading";
    try {
      var detail = await api.strategyDetail(id);
      if (ST_STATE.selectedId !== id) return; // selection moved on
      ST_STATE.detail = detail;
      ST_STATE.detailStatus = "done";
    } catch (err) {
      if (ST_STATE.selectedId !== id) return;
      ST_STATE.detail = null;
      ST_STATE.detailStatus = "error";
      showToast("Failed to load strategy detail / 策略详情加载失败: " +
        ((err && err.message) || err), "error");
    }
    updateStDetail();
  }

  // ── Bindings (row select, tabs, signal filter, actions, config) ──
  function bindStrategiesPage() {
    // Row selection — delegated on persistent tbody; loads the detail
    var tbody = document.getElementById("st-list-tbody");
    if (tbody) {
      tbody.addEventListener("click", function (e) {
        var row = e.target.closest("tr[data-st-id]");
        if (!row) return;
        ST_STATE.selectedId = row.getAttribute("data-st-id");
        // ⑤ selecting a strategy switches the terminal-wide strategy context
        ctxSetStrategy(ST_STATE.selectedId);
        ST_STATE.signalFilter = "ALL";
        ST_STATE.detail = null;
        ST_STATE.detailStatus = "idle";
        tbody.innerHTML = renderStRows();
        updateStDetail();
        stLoadDetail();
      });
    }

    // Detail area — tabs + delegated signal filters & action buttons
    var detailHost = document.getElementById("st-detail");
    if (detailHost) {
      UI.bindTabs(detailHost);
      detailHost.addEventListener("click", function (e) {
        var filterBtn = e.target.closest("[data-st-filter]");
        if (filterBtn) {
          ST_STATE.signalFilter = filterBtn.getAttribute("data-st-filter");
          updateStSignals();
          return;
        }
        var btn = e.target.closest("[data-action]");
        if (!btn) return;
        var action = btn.getAttribute("data-action");
        var s = stSelected();
        if (!s) return;
        if (action === "st:backtest") {
          location.hash = "#/research/backtest";
        } else if (action === "st:view-signals") {
          var sigTab = detailHost.querySelector('[data-tab="st-signals"]');
          if (sigTab) sigTab.click();
        } else if (action === "st:configure") {
          UI.openDrawer({
            title: "Configure " + s.name,
            body: renderStConfigBody(s),
            footer:
              UI.button("Cancel", "ghost", { sm: true, action: "close-drawer" }) +
              UI.button("Save", "primary", { sm: true, action: "close-drawer" }),
          });
        } else if (action === "st:pause") {
          if (!confirm("Pause paper trading for " + s.name + "? / 确认暂停模拟交易？")) return;
          showToast("Paper trading paused / 模拟已暂停 (UI state only)", "info");
          btn.textContent = "Paused";
        }
      });
    }

    // Load the detail for the initial selection in the background
    if (ST_STATE.selectedId && ST_STATE.detailStatus === "idle") {
      stLoadDetail();
    }

    // "New Strategy" button (page header) — placeholder
    var newBtn = document.querySelector('[data-action="st:new"]');
    if (newBtn) {
      newBtn.addEventListener("click", function () {
        showToast("New strategy — coming in UI V1 / 新建策略待后续 UI 版本", "info");
      });
    }

    // Catalog refresh — refetches and re-renders the page (Integration 009)
    var refreshBtn = document.querySelector('[data-action="st:refresh"]');
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Refreshing…";
        stLoadCatalog(true).then(function () {
          ST_STATE.detail = null;
          ST_STATE.detailStatus = "idle";
          return render();
        }).catch(function (err) {
          showToast("Failed to refresh catalog / 刷新失败: " +
            ((err && err.message) || err), "error");
        }).then(function () {
          refreshBtn.disabled = false;
          refreshBtn.textContent = "Refresh";
        });
      });
    }
  }

  // ── Strategy page (Integration 009: real Strategy API) ─────────
  PAGE_FRAMEWORK["research/strategies"] = async function () {
    if (!ST_STATE.catalog) {
      await stLoadCatalog();
    }
    var src = (ST_STATE.catalog && ST_STATE.catalog.source) || {};
    var desc = "Lifecycle catalog from the research pipeline · source run " +
      (src.research_run || "—") +
      (src.paper_replay_available
        ? " · paper replay available (Alpha021)"
        : " · paper replay unavailable (missing data files)");
    return (
      UI.pageHeader("Strategy", desc,
        UI.button("Refresh", "ghost", { sm: true, action: "st:refresh" }) +
        UI.button("New Strategy", "primary", { sm: true, action: "st:new" })) +
      renderStKpis() +
      UI.panel("Strategies", renderStList()) +
      '<div id="st-detail">' + renderStDetail() + "</div>"
    );
  };

  /* ==================================================================
   * Backtest module — Integration 008 (real Backtest API)
   * Professional backtest workbench wired to the real replay engine:
   * config → POST /dashboard/backtest/run → KPIs → equity/drawdown/
   * monthly returns → trades → summary → run history.
   * The quant core stays frozen (Alpha021 / FACTOR_SPEC_REAL_D1); this
   * layer only parameterises the replay window, universe and initial
   * capital. State machine: idle | running | done | error.
   * ================================================================== */
  function btPad2(n) { return (n < 10 ? "0" : "") + n; }

  // Module state (Integration 008): last result + run history + universe.
  var BT_STATE = {
    status: "idle",       // "idle" | "running" | "done" | "error"
    error: null,          // message from the last failed run
    result: null,         // last completed payload (Backtest API)
    runs: [],             // run history (GET /dashboard/backtest/runs)
    universe: null,       // symbols + frozen strategy metadata
  };

  // ── Derived series (built from BT_STATE.result) ───────────────
  function btDateParts(date) {
    var parts = String(date || "").split("-");
    return { year: Number(parts[0]) || 0, month: Number(parts[1]) || 0 };
  }
  function btEquityPoints() {
    var eq = (BT_STATE.result && BT_STATE.result.equity) || [];
    return eq.map(function (r) {
      var p = btDateParts(r.date);
      return { value: r.equity, label: r.date, year: p.year, month: p.month };
    });
  }
  function btDrawdownPoints() {
    var eq = (BT_STATE.result && BT_STATE.result.equity) || [];
    var dd = (BT_STATE.result && BT_STATE.result.drawdown_series) || [];
    var pts = [];
    for (var i = 0; i < Math.min(eq.length, dd.length); i++) {
      var p = btDateParts(eq[i].date);
      // drawdown_series is in percent (-5.5 == -5.5%) — normalise to fraction
      pts.push({ value: (dd[i] || 0) / 100, label: eq[i].date, year: p.year, month: p.month });
    }
    return pts;
  }
  function btMonthlyReturns() {
    // API shape: [{month: "YYYY-MM", return_pct: 0.11}] (percent) —
    // normalised to {years, cells{year{month: fraction}}}.
    var rows = (BT_STATE.result && BT_STATE.result.monthly_returns) || [];
    var cells = {};
    rows.forEach(function (r) {
      var p = btDateParts(r.month);
      if (!p.year || !p.month) return;
      if (!cells[p.year]) cells[p.year] = {};
      cells[p.year][p.month] = (r.return_pct || 0) / 100;
    });
    return {
      years: Object.keys(cells).map(Number).sort(function (a, b) { return a - b; }),
      cells: cells,
    };
  }

  function btPct(x) { return (x >= 0 ? "+" : "") + (x * 100).toFixed(2) + "%"; }
  function btFmtPct(r) { return (r >= 0 ? "+" : "") + (r * 100).toFixed(2) + "%"; }
  function btMonthlyReturnClass(r) {
    var a = Math.abs(r);
    if (r >= 0) {
      if (a < 0.005) return "bt-m-pos-1";
      if (a < 0.015) return "bt-m-pos-2";
      return "bt-m-pos-3";
    }
    if (a < 0.005) return "bt-m-neg-1";
    if (a < 0.015) return "bt-m-neg-2";
    return "bt-m-neg-3";
  }
  function btSideBadge(side) {
    var cls = side === "BUY" ? "bt-side-buy" : "bt-side-sell";
    return '<span class="bt-side ' + cls + '">' + esc(side) + "</span>";
  }
  function btFmtMoney(v) {
    return (v >= 0 ? "+" : "-") + "$" + Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  // Strategy is frozen to the sealed FACTOR_SPEC_REAL_D1 replay — the select
  // is informational (single option), not an engine knob.
  function renderBtConfig() {
    var strategy = (BT_STATE.universe && BT_STATE.universe.strategy) || {};
    var strat = strategy.alpha_id || "Alpha021";
    var form =
      UI.field("Strategy", UI.select({ id: "bt-strategy", value: strat, options: [
        { value: strat, label: strat + (strategy.frozen ? " (frozen)" : "") },
      ] })) +
      UI.field("Universe", '<div class="form-checks">' + btUniverseChecks() + "</div>") +
      UI.field("Timeframe", UI.select({ id: "bt-tf", value: strategy.timeframe || "1D", options: [
        { value: "1D", label: "1D (real daily data)" },
      ] })) +
      UI.field("Start", UI.input({ id: "bt-start", type: "date", placeholder: "Full history" })) +
      UI.field("End", UI.input({ id: "bt-end", type: "date", placeholder: "Full history" })) +
      UI.field("Initial Capital", UI.input({ id: "bt-capital", type: "number", value: "1000000", step: "1000" }));
    return '<div class="bt-config-grid">' + form + "</div>" +
      '<div class="ds-text-muted" style="font-size:var(--ds-text-xs);margin-top:var(--ds-space-3);">' +
      "Quant core frozen in Factor Discovery v2 (formula / windows / orientation sealed). " +
      "Execution model: real close ± " + (strategy.slippage_bps != null ? strategy.slippage_bps : 3) +
      " bps · source run " + esc(strategy.source_run || "factor-real-d1") + ".</div>";
  }

  function btUniverseChecks() {
    var symbols = (BT_STATE.universe && BT_STATE.universe.symbols) || [];
    if (!symbols.length) symbols = [{ symbol: "NVDA", gate_passed: true, data_available: true }];
    return symbols.map(function (u) {
      var disabled = u.data_available === false ? " disabled" : "";
      var note = u.data_available === false
        ? '<span class="chk-note">no data</span>'
        : (u.gate_passed ? '<span class="chk-note">gate ✓</span>' : "");
      return (
        '<label class="form-check"><input type="checkbox" name="bt-sym" value="' +
        esc(u.symbol) + '"' + (u.gate_passed && u.data_available !== false ? " checked" : "") +
        disabled + "> " + esc(u.symbol) + " " + note + "</label>"
      );
    }).join("");
  }

  // API meta stores percentages as numbers (7.49 == 7.49%); btPct expects
  // fractions, hence the /100 normalisation.
  function renderBtKpis() {
    var m = (BT_STATE.result && BT_STATE.result.meta) || {};
    return (
      UI.metricCard("Total Return",
        m.return_pct == null ? "—" : btPct(m.return_pct / 100), "",
        (m.return_pct || 0) >= 0 ? "pos" : "neg") +
      UI.metricCard("CAGR",
        m.cagr == null ? "—" : btPct(m.cagr / 100), "",
        (m.cagr || 0) >= 0 ? "pos" : "neg") +
      UI.metricCard("Sharpe",
        m.sharpe == null ? "—" : m.sharpe.toFixed(2), "",
        (m.sharpe || 0) >= 0 ? "pos" : "neg") +
      UI.metricCard("Max Drawdown",
        m.maxdd_pct == null ? "—" : btPct(-Math.abs(m.maxdd_pct) / 100), "", "neg") +
      UI.metricCard("Win Rate",
        m.win_rate == null ? "—" : btPct(m.win_rate / 100), "", "pos") +
      UI.metricCard("Profit Factor",
        m.profit_factor == null ? "—" : m.profit_factor.toFixed(2), "",
        (m.profit_factor || 0) >= 1 ? "pos" : "neg")
    );
  }

  // Daily points from the replay — label only the first point of each year so
  // the x axis stays readable.
  function renderBtEquity() {
    var pts = btEquityPoints();
    if (!pts.length) return UI.empty("No data", "Equity curve unavailable.");
    var lastYear = null;
    var xLabels = pts.map(function (p) {
      if (p.year && p.year !== lastYear) { lastYear = p.year; return String(p.year); }
      return "";
    });
    return UI.equityCurve(pts, {
      height: 300,
      color: "var(--ds-profit)",
      yFormat: function (v) { return UI.money(v, 0); },
      xLabels: xLabels,
    });
  }

  // Custom drawdown chart: fill from zero baseline (top) down to the line.
  function renderBtDrawdown() {
    var dd = btDrawdownPoints();
    if (!dd.length) return UI.empty("No data", "Drawdown series unavailable.");
    var W = 880, H = 220, pad = { top: 16, right: 16, bottom: 28, left: 64 };
    var w = W - pad.left - pad.right, h = H - pad.top - pad.bottom;
    var vals = dd.map(function (d) { return d.value; });
    var minDD = Math.min.apply(null, vals);
    var yMin = minDD < 0 ? minDD * 1.12 : 0;
    var span = (0 - yMin) || 1;
    function yOf(v) { return pad.top + ((0 - v) / span) * h; }
    var xStep = dd.length > 1 ? w / (dd.length - 1) : 0;
    var pts = dd.map(function (d, i) { return { x: pad.left + i * xStep, y: yOf(d.value) }; });
    var lineD = "M " + pts.map(function (p) { return p.x.toFixed(1) + " " + p.y.toFixed(1); }).join(" L ");
    var areaD = lineD + " L " + pts[pts.length - 1].x.toFixed(1) + " " + pad.top.toFixed(1) +
      " L " + pts[0].x.toFixed(1) + " " + pad.top.toFixed(1) + " Z";
    var ticks = [0, minDD / 2, minDD];
    var yTickHtml = ticks.map(function (t) {
      var y = yOf(t);
      var lbl = (t * 100).toFixed(2) + "%";
      return '<line x1="' + pad.left + '" y1="' + y.toFixed(1) + '" x2="' + (pad.left + w) + '" y2="' + y.toFixed(1) + '" stroke="var(--ds-border-soft)" stroke-width="1" stroke-dasharray="2 4" />' +
        '<text x="' + (pad.left - 8) + '" y="' + (y + 3).toFixed(1) + '" text-anchor="end" class="eqc-axis-label">' + esc(lbl) + "</text>";
    }).join("");
    var zeroLine = '<line x1="' + pad.left + '" y1="' + pad.top.toFixed(1) + '" x2="' + (pad.left + w) + '" y2="' + pad.top.toFixed(1) + '" stroke="var(--ds-border-default)" stroke-width="1" />';
    var xTickHtml = "";
    var lastYear = null;
    dd.forEach(function (d, i) {
      if (d.year && d.year !== lastYear) {
        lastYear = d.year;
        var x = pad.left + i * xStep;
        xTickHtml += '<text x="' + x.toFixed(1) + '" y="' + (pad.top + h + 18) + '" text-anchor="middle" class="eqc-axis-label">' + esc(String(d.year)) + "</text>";
      }
    });
    var last = pts[pts.length - 1];
    var marker = '<circle cx="' + last.x.toFixed(1) + '" cy="' + last.y.toFixed(1) + '" r="4" fill="var(--ds-loss)" />' +
      '<circle cx="' + last.x.toFixed(1) + '" cy="' + last.y.toFixed(1) + '" r="8" fill="var(--ds-loss)" opacity="0.2" />';
    return '<div class="bt-dd-wrap eqc-wrap"><svg class="eqc-svg" viewBox="0 0 ' + W + " " + H + '" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Drawdown">' +
      '<path d="' + areaD + '" fill="var(--ds-loss)" fill-opacity="0.18" />' +
      '<path d="' + lineD + '" fill="none" stroke="var(--ds-loss)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />' +
      zeroLine + yTickHtml + xTickHtml + marker +
      "</svg></div>";
  }

  function renderBtMonthly() {
    var monthly = btMonthlyReturns();
    if (!monthly.years.length) return UI.empty("No data", "Monthly returns unavailable.");
    var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    var header = '<tr><th class="bt-m-year">Year</th>' +
      months.map(function (mo) { return '<th class="bt-m-month">' + mo + "</th>"; }).join("") +
      '<th class="bt-m-ytd">YTD</th></tr>';
    var rows = monthly.years.map(function (y) {
      var yearProduct = 1;
      var tds = "";
      for (var mo = 1; mo <= 12; mo++) {
        var r = (monthly.cells[y] || {})[mo];
        if (r == null) {
          tds += '<td class="bt-m-cell bt-m-empty">—</td>';
        } else {
          yearProduct *= (1 + r);
          tds += '<td class="bt-m-cell ' + btMonthlyReturnClass(r) + '" title="' + y + "-" + btPad2(mo) + '">' + btFmtPct(r) + "</td>";
        }
      }
      var ytd = yearProduct - 1;
      var ytdCls = ytd >= 0 ? "bt-m-ytd-pos" : "bt-m-ytd-neg";
      return '<tr><td class="bt-m-year">' + y + "</td>" + tds +
        '<td class="bt-m-ytd ' + ytdCls + '">' + btFmtPct(ytd) + "</td></tr>";
    }).join("");
    return '<table class="bt-monthly-table">' + header + rows + "</table>";
  }

  function btOutcomeBadge(v) {
    if (v === "FILLED") return '<span class="bt-side bt-side-buy">' + esc(v) + "</span>";
    if (v === "REJECTED") return '<span class="bt-side bt-side-sell">' + esc(v) + "</span>";
    return '<span class="bt-side">' + esc(v || "—") + "</span>";
  }

  // Replay trades are chronological; newest-first reads better in the table.
  function renderBtTrades() {
    var trades = (BT_STATE.result && BT_STATE.result.trades) || [];
    var rows = trades.slice().reverse().map(function (t) {
      return {
        date: t.date,
        symbol: t.symbol,
        side: t.side,
        outcome: t.outcome,
        qty: t.quantity,
        price: Number(t.exec_price || t.ref_price_real_close),
        pnl: t.side === "SELL" && t.realized_pnl != null ? t.realized_pnl : null,
      };
    });
    return UI.table({
      columns: [
        { key: "date", label: "Date", sortable: false },
        { key: "symbol", label: "Symbol", sortable: false },
        { key: "side", label: "Side", sortable: false, format: function (v) { return btSideBadge(v); } },
        { key: "outcome", label: "Outcome", sortable: false, format: function (v) { return btOutcomeBadge(v); } },
        { key: "qty", label: "Qty", numeric: true, format: function (v) { return v == null ? "—" : v.toLocaleString(); } },
        { key: "price", label: "Price", numeric: true, format: function (v) { return v == null ? "—" : "$" + v.toFixed(2); } },
        { key: "pnl", label: "P&L", numeric: true, format: function (v) { return v == null ? "—" : btFmtMoney(v); }, color: function (v) { return v == null ? "" : v >= 0 ? "pos" : "neg"; } },
      ],
      rows: rows,
      emptyDesc: "No trades recorded for this backtest.",
    });
  }

  function renderBtSummary() {
    var m = (BT_STATE.result && BT_STATE.result.meta) || {};
    var strategy = (BT_STATE.universe && BT_STATE.universe.strategy) || {};
    var trades = (BT_STATE.result && BT_STATE.result.trades) || [];
    var cells =
      btSummaryCell("Strategy", m.alpha_id || strategy.alpha_id || "Alpha021") +
      btSummaryCell("Source Run", strategy.source_run || "factor-real-d1") +
      btSummaryCell("Universe", (m.symbols || []).join(" ")) +
      btSummaryCell("Timeframe", strategy.timeframe || "1D") +
      btSummaryCell("Period", m.period || "—") +
      btSummaryCell("Initial Capital", "$" + Number(m.initial_capital || 0).toLocaleString()) +
      btSummaryCell("Slippage", (strategy.slippage_bps != null ? strategy.slippage_bps : 3) + " bps") +
      btSummaryCell("Trades", String(trades.length)) +
      btSummaryCell("Total Return", m.return_pct == null ? "—" : btPct(m.return_pct / 100), m.return_pct >= 0 ? "pos" : "neg") +
      btSummaryCell("Sharpe", m.sharpe == null ? "—" : m.sharpe.toFixed(2)) +
      btSummaryCell("Max Drawdown", m.maxdd_pct == null ? "—" : btPct(-Math.abs(m.maxdd_pct) / 100), "neg") +
      btSummaryCell("Win Rate", m.win_rate == null ? "—" : btPct(m.win_rate / 100), "pos");
    return '<div class="bt-summary-grid">' + cells + "</div>";
  }
  function btSummaryCell(label, value, cls) {
    return '<div class="bt-summary-cell"><div class="bt-summary-label">' + esc(label) + "</div>" +
      '<div class="bt-summary-value' + (cls ? " " + cls : "") + '">' + esc(value) + "</div></div>";
  }

  // Advanced multi-panel chart (Price+Signals / Z-Score / Position / Equity)
  // with per-symbol tabs — reuses the legacy page's multiPanelChart renderer.
  function renderBtChartPanels() {
    var panels = (BT_STATE.result && BT_STATE.result.chart_panels) || [];
    if (!panels.length) return UI.empty("No data", "Advanced chart unavailable.");
    var tabs = panels.map(function (p, i) {
      return '<button class="sym-tab' + (i === 0 ? " active" : "") + '" data-sym="' + esc(p.symbol) + '">' + esc(p.symbol) + "</button>";
    }).join("");
    return '<div class="chart-sym-tabs">' + tabs + "</div>" +
      '<div id="chart-panel-container">' + multiPanelChart(panels.slice(0, 1)) + "</div>";
  }

  function renderBtResultsHtml() {
    if (BT_STATE.status === "running")
      return UI.stateLoading("Running backtest…",
        "Replaying Alpha021 over real daily data — this typically takes ~20s. / 正在回放真实日线数据…");
    if (BT_STATE.status === "error")
      return UI.stateError("Backtest failed / 回测失败",
        esc(BT_STATE.error || "Check parameters and retry."),
        "Retry / 重试", "bt:retry");
    if (BT_STATE.status !== "done" || !BT_STATE.result)
      return UI.empty("No backtest results", "Configure parameters and click Run Backtest to see results.", "⌖");
    var m = (BT_STATE.result.meta) || {};
    var pts = btEquityPoints();
    var range = pts.length ? pts[0].label + " → " + pts[pts.length - 1].label : (m.period || "—");
    var trades = BT_STATE.result.trades || [];
    var researchNote =
      '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);">From Research: ' +
      esc(m.alpha_id || "Alpha021") + " · " +
      esc(((BT_STATE.universe && BT_STATE.universe.strategy) || {}).source_run || "factor-real-d1") + "</span>" +
      UI.button("View Research", "ghost", { sm: true, action: "bt:view-research" });
    return (
      UI.sectionHeading("Performance") +
      '<div class="bt-kpi-grid">' + renderBtKpis() + "</div>" +
      UI.panel("Equity Curve", renderBtEquity(), { actions: '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);">' + esc(range) + "</span>" }) +
      UI.panel("Drawdown", renderBtDrawdown(), { actions: '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);">Max DD ' + (m.maxdd_pct == null ? "—" : btPct(-Math.abs(m.maxdd_pct) / 100)) + "</span>" }) +
      UI.panel("Monthly Returns", renderBtMonthly()) +
      UI.panel("Advanced Chart — Price / Z-Score / Position / Equity", renderBtChartPanels()) +
      UI.panel("Trades", renderBtTrades(), { actions: '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);">' + trades.length + " trades</span>" }) +
      UI.panel("Backtest Summary", renderBtSummary(), { actions: researchNote })
    );
  }

  // Run history table — clicking a row re-opens that run's cached result.
  function btRunStatusBadge(status) {
    if (status === "completed") return '<span class="rs-stage rs-stage-pass">COMPLETED</span>';
    return '<span class="rs-stage rs-stage-fail">' + esc(String(status || "FAILED").toUpperCase()) + "</span>";
  }

  function renderBtRunsHtml() {
    var runs = BT_STATE.runs || [];
    if (!runs.length)
      return UI.empty("No runs yet", "Completed backtests will be listed here. / 完成的回测会显示在这里。");
    var rows = runs.map(function (r) {
      var m = r.metrics || {};
      var cfg = r.config || {};
      return (
        '<tr data-bt-run="' + esc(r.run_id) + '" title="Click to open this run\'s cached result">' +
        '<td class="ds-text-mono">' + esc(r.run_id) + "</td>" +
        '<td class="ds-text-mono">' + esc(String(r.created_at || "").replace("T", " ")) + "</td>" +
        '<td>' + esc((cfg.symbols || []).join(" ")) + "</td>" +
        '<td class="ds-text-mono">' + esc(r.period || "—") + "</td>" +
        '<td class="num ds-text-mono ' + ((m.return_pct || 0) >= 0 ? "pos" : "neg") + '">' +
        (m.return_pct == null ? "—" : btPct(m.return_pct / 100)) + "</td>" +
        '<td class="num ds-text-mono">' + (m.sharpe == null ? "—" : m.sharpe.toFixed(2)) + "</td>" +
        '<td class="num ds-text-mono">' + (r.trades || 0) + "</td>" +
        "<td>" + btRunStatusBadge(r.status) + "</td>" +
        "</tr>"
      );
    }).join("");
    return '<div class="table-wrap"><table class="ds-table"><thead><tr>' +
      "<th>Run ID</th><th>Created</th><th>Universe</th><th>Period</th>" +
      '<th class="num">Return</th><th class="num">Sharpe</th><th class="num">Trades</th><th>Status</th>' +
      "</tr></thead><tbody>" + rows + "</tbody></table></div>";
  }

  function updateBtResults() {
    var host = document.getElementById("bt-results");
    if (host) host.innerHTML = renderBtResultsHtml();
  }

  function setBtRunState(running) {
    document.querySelectorAll('[data-action="bt:run"]').forEach(function (b) {
      if (!b._btLabel) b._btLabel = b.textContent;
      b.disabled = running;
      b.textContent = running ? "Running…" : b._btLabel;
      if (running) b.classList.add("disabled"); else b.classList.remove("disabled");
    });
  }

  // Read the config form into a POST /dashboard/backtest/run body. Empty
  // start/end means "full history" (omitted — the engine defaults).
  function btReadConfig() {
    var syms = Array.prototype.slice
      .call(document.querySelectorAll('input[name="bt-sym"]:checked'))
      .map(function (c) { return c.value; });
    var capEl = document.getElementById("bt-capital");
    var startEl = document.getElementById("bt-start");
    var endEl = document.getElementById("bt-end");
    var body = {
      symbols: syms,
      initial_capital: parseFloat(capEl && capEl.value) || 1000000,
    };
    if (startEl && startEl.value) body.start = startEl.value;
    if (endEl && endEl.value) body.end = endEl.value;
    return body;
  }

  async function runBacktest() {
    var body = btReadConfig();
    if (!body.symbols.length) {
      showToast("Universe cannot be empty / 标的池不能为空", "error");
      return;
    }
    BT_STATE.status = "running";
    BT_STATE.error = null;
    setBtRunState(true);
    updateBtResults();
    try {
      var data = await api.backtestRun(body);
      BT_STATE.result = data;
      BT_STATE.status = "done";
      window.__backtestData = data;   // per-symbol panel switching
      showToast("Backtest complete / 回测完成", "ok");
      await btRefreshRuns();          // history now includes this run
    } catch (err) {
      BT_STATE.status = "error";
      BT_STATE.error = (err && err.message) ? err.message : String(err);
      showToast("Backtest failed / 回测失败: " + BT_STATE.error, "error");
    } finally {
      setBtRunState(false);
      updateBtResults();
    }
  }

  async function btRefreshRuns() {
    try {
      var data = await api.backtestRuns();
      BT_STATE.runs = (data && data.runs) || [];
    } catch (err) { /* keep the old list on transient failure */ }
    var host = document.getElementById("bt-runs");
    if (host) host.innerHTML = renderBtRunsHtml();
  }

  // Re-open a recorded run's cached result (no engine re-run).
  async function btLoadRun(runId) {
    BT_STATE.status = "running";
    updateBtResults();
    try {
      var data = await api.backtestRunResult(runId);
      BT_STATE.result = data;
      BT_STATE.status = "done";
      window.__backtestData = data;
      showToast("Run loaded / 已加载回测 " + runId, "ok");
    } catch (err) {
      BT_STATE.status = BT_STATE.result ? "done" : "error";
      BT_STATE.error = (err && err.message) ? err.message : String(err);
      showToast("Failed to load run / 加载失败: " + BT_STATE.error, "error");
    }
    updateBtResults();
  }

  // One delegated listener on #bt-root covers run/retry/view-research buttons,
  // per-symbol chart tabs and run-history rows — survives innerHTML updates.
  function bindBacktestPage() {
    var root = document.getElementById("bt-root");
    if (!root) return;
    root.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action]");
      if (btn) {
        var action = btn.getAttribute("data-action");
        if (action === "bt:run" || action === "bt:retry") { runBacktest(); return; }
        if (action === "bt:view-research") { location.hash = "#/research"; return; }
        if (action === "bt:runs-refresh") { btRefreshRuns(); return; }
        return;
      }
      var tab = e.target.closest(".sym-tab");
      if (tab) {
        var sym = tab.getAttribute("data-sym");
        root.querySelectorAll(".sym-tab").forEach(function (t) { t.classList.remove("active"); });
        tab.classList.add("active");
        var container = document.getElementById("chart-panel-container");
        var panels = (window.__backtestData && window.__backtestData.chart_panels) || [];
        var panel = panels.filter(function (p) { return p.symbol === sym; })[0];
        if (container && panel) container.innerHTML = multiPanelChart([panel]);
        return;
      }
      var row = e.target.closest("tr[data-bt-run]");
      if (row) {
        var runId = row.getAttribute("data-bt-run");
        if (runId) btLoadRun(runId);
      }
    });
  }

  // ── Backtest (Integration 008 — real Backtest API) ──────────────
  PAGE_FRAMEWORK["research/backtest"] = async function () {
    // Initial load — a rejection here bubbles up to render()'s stateError.
    var results = await Promise.all([
      api.backtestUniverse(),
      api.backtestRuns(),
    ]);
    BT_STATE.universe = results[0];
    BT_STATE.runs = results[1].runs || [];

    var runBtn = UI.button("Run New Backtest", "primary", { sm: true, action: "bt:run" });
    var configRun = UI.button("Run Backtest", "primary", { sm: true, action: "bt:run" });
    var refreshRuns = UI.button("Refresh", "ghost", { sm: true, action: "bt:runs-refresh" });
    return (
      '<div id="bt-root">' +
      UI.pageHeader("Backtest", "Strategy backtesting workspace · 研究 → 回测 → 验证", runBtn) +
      UI.panel("Configuration", renderBtConfig(), { actions: configRun }) +
      '<div id="bt-results" class="bt-results">' + renderBtResultsHtml() + "</div>" +
      UI.sectionHeading("Run History") +
      UI.panel("Backtest Runs", '<div id="bt-runs">' + renderBtRunsHtml() + "</div>", { actions: refreshRuns }) +
      "</div>"
    );
  };

  PAGE_FRAMEWORK["research/factors"] = function () {
    return (
      UI.pageHeader("Factor Discovery", "Factor discovery and validation pipeline") +
      UI.kpiGrid(
        UI.metricCard("Total Alphas", "101", "", "") +
        UI.metricCard("Pairs Tested", "909", "", "") +
        UI.metricCard("Validated", "42", "", "pos") +
        UI.metricCard("Candidates", "22", "+3", "pos")
      ) +
      UI.sectionHeading("Discovery Pipeline") +
      UI.panel("Pipeline Stages", '<div style="display:flex;flex-direction:column;gap:var(--ds-space-3);">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;">' +
        '<span>Alpha Generation</span>' + UI.badge("101 alphas", "info") +
        "</div>" +
        '<div style="display:flex;justify-content:space-between;align-items:center;">' +
        '<span>Pair Correlation</span>' + UI.badge("909 pairs", "info") +
        "</div>" +
        '<div style="display:flex;justify-content:space-between;align-items:center;">' +
        '<span>Validation (IS)</span>' + UI.badge("42 validated", "profit") +
        "</div>" +
        '<div style="display:flex;justify-content:space-between;align-items:center;">' +
        '<span>Out-of-Sample</span>' + UI.badge("28 passed", "profit") +
        "</div>" +
        '<div style="display:flex;justify-content:space-between;align-items:center;">' +
        '<span>De-correlation</span>' + UI.badge("15 families", "profit") +
        "</div>" +
        "</div>")
    );
  };

  // ── Trading ─────────────────────────────────────────────────────
  // ── Trading / Paper Trading (Integration 003 — real API data) ───
  // Module-level state shared between the render function and the
  // order-ticket event bindings (review / preview / submit flow).
  var _tradingState = {
    symbol: "NVDA",
    quote: null,          // last useQuote() result
    sessionRunning: false,
    submitting: false,    // duplicate-submit lock
  };

  PAGE_FRAMEWORK["trading/paper"] = async function () {
    var symbol = _tradingState.symbol;

    // ── Parallel fetch: quote + dashboard + orders + executions ──
    var fetched = await Promise.all([
      useQuote(symbol).catch(function () { return null; }),
      useDashboard().catch(function () { return null; }),
      api.get("/dashboard/orders").catch(function () { return { orders: [] }; }),
      api.get("/dashboard/executions").catch(function () { return { executions: [] }; }),
    ]);
    var quote = fetched[0] || {
      symbol: symbol, last_price: 0, bid: 0, ask: 0, spread: 0,
      change: 0, change_pct: 0, timestamp: null, source: "none", session_running: false,
    };
    var dash = fetched[1] || {
      account: { equity: 0, cash: 0, daily_pnl: 0, daily_return: 0 },
      positions: { count: 0, market_value: 0, unrealized_pnl: 0, items: [] },
      orders: { pending: 0, filled_today: 0, rejected_today: 0 },
      risk: { status: "UNKNOWN", exposure: 0 },
      execution: { fill_rate: 0, reject_rate: 0, slippage: 0 },
      meta: { pipeline_attached: false, environment: "PAPER", account_name: "—" },
    };
    var ordersList = (fetched[2] && fetched[2].orders) || [];
    var execsList = (fetched[3] && fetched[3].executions) || [];

    // Persist for the event bindings
    _tradingState.quote = quote;
    _tradingState.sessionRunning = !!quote.session_running;

    // ── Watchlist quotes (parallel, best-effort) ────────────────
    var wlSymbols = ["NVDA", "AAPL", "MSFT", "TSLA"];
    var wlQuotes = await Promise.all(wlSymbols.map(function (s) {
      return useQuote(s).catch(function () {
        return { symbol: s, last_price: 0, change_pct: 0, session_running: false };
      });
    }));
    var watchlist = wlQuotes.map(function (q) {
      return { symbol: q.symbol, price: q.last_price, changePct: q.change_pct / 100 };
    });

    // ── Helpers ─────────────────────────────────────────────────
    function fmtMoney(v) { return UI.money(v, 2); }
    function fmtSigned(v) { return UI.signedMoney(v); }
    function fmtPct(v) { return (v >= 0 ? "+" : "") + v.toFixed(2) + "%"; }

    // ── Instrument header from real quote ───────────────────────
    var ts = quote.timestamp ? new Date(quote.timestamp).toLocaleTimeString() : "—";
    var instHeader = UI.instrumentHeader({
      symbol: quote.symbol,
      name: quote.symbol, // backend has no company name; use symbol
      price: quote.last_price,
      change: quote.change,
      changePct: quote.change_pct / 100,
      bid: quote.bid,
      ask: quote.ask,
      spread: "$" + quote.spread.toFixed(2),
      status: quote.session_running ? "Live" : "No Session",
      time: ts,
    });

    // ── Chart: illustrative candles (no historical quote API) ────
    // Per Integration 003 boundary: "不为了 UI 新造行情服务".
    // Candles are centered around the live quote price so the chart
    // visually tracks the real last price without a new service.
    var base = quote.last_price || 178.42;
    var candles = [];
    for (var i = 0; i < 32; i++) {
      var drift = (i - 16) * (base * 0.001);
      var wave = Math.sin(i * 0.4) * (base * 0.004);
      var c = base + drift + wave;
      var o = c - (base * 0.002);
      candles.push({
        o: o, h: Math.max(o, c) + (base * 0.001),
        l: Math.min(o, c) - (base * 0.001), c: c,
      });
    }
    var chartHtml = UI.candleChart(candles, { height: 300 });
    var chartShell = UI.chartShell({ chartHtml: chartHtml, showVolume: true });

    // ── Order Ticket with real quote price ──────────────────────
    var orderTicket = UI.orderTicket({
      symbol: quote.symbol, price: quote.last_price, qty: 100,
    });

    // ── Session banner (when no session, show a Start prompt) ──
    var sessionBanner = quote.session_running ? "" :
      '<div class="ds-callout ds-callout-warning" style="margin-bottom:var(--ds-space-md);">' +
      '<strong>No paper trading session.</strong> ' +
      'Start a session from the Topbar or ' +
      '<a href="#/system" class="ds-link">System → Sessions</a> to enable order submission. ' +
      'Quotes are showing nominal/last-known prices.' +
      '</div>';

    var topRow =
      '<div class="tr-grid-3">' +
      '<div class="tr-col-left">' +
      UI.panel("Watchlist", UI.watchlist(watchlist, quote.symbol)) +
      '</div>' +
      '<div class="tr-col-center">' +
      instHeader + chartShell +
      '</div>' +
      '<div class="tr-col-right">' +
      orderTicket +
      '</div>' +
      '</div>';

    // ── Account Summary from real dashboard data ────────────────
    var acctSummary = UI.statRows([
      { label: "Equity", value: fmtMoney(dash.account.equity), variant: dash.account.daily_return >= 0 ? "pos" : "neg" },
      { label: "Cash", value: fmtMoney(dash.account.cash), variant: "info" },
      { label: "Exposure", value: fmtMoney(dash.risk.exposure), variant: "info" },
      { label: "Unrealized P&L", value: fmtSigned(dash.positions.unrealized_pnl), variant: dash.positions.unrealized_pnl >= 0 ? "pos" : "neg" },
      { label: "Daily P&L", value: fmtSigned(dash.account.daily_pnl), variant: dash.account.daily_pnl >= 0 ? "pos" : "neg" },
      { label: "Risk Status", value: esc(dash.risk.status), variant: dash.risk.status === "HEALTHY" ? "pos" : dash.risk.status === "NO_PIPELINE" ? "warning" : "neg" },
      { label: "Fill Rate", value: (dash.execution.fill_rate * 100).toFixed(1) + "%", variant: dash.execution.fill_rate >= 0.5 ? "pos" : "warning" },
    ]);

    // ── Positions table from real items ─────────────────────────
    var posRows = (dash.positions.items || []).map(function (p) {
      return {
        symbol: p.symbol || "—",
        qty: p.quantity || 0,
        avgPrice: p.avg_price || 0,
        last: p.last_price || 0,
        pnl: p.unrealized_pnl || 0,
        pnlPct: (p.avg_price ? (p.last_price - p.avg_price) / p.avg_price : 0),
      };
    });
    var posTable = posRows.length ? UI.table({
      columns: [
        { key: "symbol", label: "Symbol" },
        { key: "qty", label: "Qty", numeric: true },
        { key: "avgPrice", label: "Avg Price", numeric: true, format: function (v) { return "$" + (v || 0).toFixed(2); } },
        { key: "last", label: "Last", numeric: true, format: function (v) { return "$" + (v || 0).toFixed(2); } },
        { key: "pnl", label: "P&L", numeric: true, format: function (v) { return UI.signedMoney(v); }, color: function (v) { return v >= 0 ? "pos" : "neg"; } },
        { key: "pnlPct", label: "P&L %", numeric: true, format: function (v) { return (v >= 0 ? "+" : "") + (v * 100).toFixed(2) + "%"; }, color: function (v) { return v >= 0 ? "pos" : "neg"; } },
      ],
      rows: posRows,
    }) : UI.empty("No Open Positions", "No positions in the current pipeline snapshot.");

    // ── Orders table from real /dashboard/orders ─────────────────
    var orderRows = ordersList.map(function (o) {
      var t = o.created_at || o.submitted_at || o.updated_at || "";
      var time = t ? new Date(t).toLocaleTimeString().slice(0, 8) : "—";
      return {
        id: o.order_id || "—",
        symbol: o.symbol || "—",
        side: o.side || "—",
        qty: o.quantity || 0,
        type: (o.order_type || "MARKET"),
        price: o.price || o.average_fill_price || 0,
        status: o.status || "—",
        time: time,
      };
    });
    var ordersTable = orderRows.length ? UI.table({
      columns: [
        { key: "id", label: "Order ID" },
        { key: "symbol", label: "Symbol" },
        { key: "side", label: "Side", color: function (v) { return v === "BUY" ? "pos" : "neg"; } },
        { key: "qty", label: "Qty", numeric: true },
        { key: "type", label: "Type" },
        { key: "price", label: "Price", numeric: true, format: function (v) { return "$" + (v || 0).toFixed(2); } },
        { key: "status", label: "Status", format: function (v) {
          var m = { FILLED: "pos", PENDING: "warning", SUBMITTED: "warning", NEW: "warning", CANCELLED: "neutral", REJECTED: "neg" };
          return '<span class="ds-status-pill ds-status-' + (m[v] || "neutral") + '"><span class="ds-status-dot"></span>' + esc(v) + '</span>';
        } },
        { key: "time", label: "Time" },
      ],
      rows: orderRows,
    }) : UI.empty("No Orders", "No orders in the current session.");

    // ── Executions table from real /dashboard/executions ────────
    var execRows = execsList.map(function (e) {
      var t = e.timestamp || e.filled_at || "";
      var time = t ? new Date(t).toLocaleTimeString().slice(0, 8) : "—";
      return {
        id: e.exec_id || e.execution_id || "—",
        orderId: e.order_id || "—",
        symbol: e.symbol || "—",
        side: e.side || "—",
        qty: e.quantity || e.filled_quantity || 0,
        price: e.price || 0,
        fee: e.commission || 0,
        time: time,
      };
    });
    var execsTable = execRows.length ? UI.table({
      columns: [
        { key: "id", label: "Exec ID" },
        { key: "orderId", label: "Order ID" },
        { key: "symbol", label: "Symbol" },
        { key: "side", label: "Side", color: function (v) { return v === "BUY" ? "pos" : "neg"; } },
        { key: "qty", label: "Filled Qty", numeric: true },
        { key: "price", label: "Fill Price", numeric: true, format: function (v) { return "$" + (v || 0).toFixed(2); } },
        { key: "fee", label: "Fee", numeric: true, format: function (v) { return "$" + (v || 0).toFixed(2); } },
        { key: "time", label: "Time" },
      ],
      rows: execRows,
    }) : UI.empty("No Executions", "No executions in the current session.");

    // ── Bottom tabs: Positions / Orders / Executions ───────────
    var bottomTabs =
      '<div class="ds-tabs" id="tr-bottom-tabs">' +
      '<button class="ds-tab active" data-tab="positions">Positions (' + (dash.positions.count || 0) + ')</button>' +
      '<button class="ds-tab" data-tab="orders">Orders (' + ordersList.length + ')</button>' +
      '<button class="ds-tab" data-tab="executions">Executions (' + execsList.length + ')</button>' +
      '</div>';
    var bottomContent =
      '<div class="ds-tab-content" id="tr-tab-positions" style="display:block;">' +
      UI.panel("Account Summary", '<div class="dash-svc-grid">' + acctSummary + '</div>') + posTable +
      '</div>' +
      '<div class="ds-tab-content" id="tr-tab-orders" style="display:none;">' + ordersTable + '</div>' +
      '<div class="ds-tab-content" id="tr-tab-executions" style="display:none;">' + execsTable + '</div>';

    return (
      UI.pageHeader("Trading", "Trading terminal — Paper trading · " + esc(dash.meta.account_name || "—"),
        UI.button("New Order", "primary", { sm: true, action: "tr:focus-order" })) +
      sessionBanner +
      topRow +
      UI.sectionHeading("Positions · Orders · Executions") +
      bottomTabs + bottomContent
    );
  };

  /* ==================================================================
   * Orders module — Integration 005 (real API)
   *
   * Orders page wired to the live Order Engine via three thin hooks:
   *   - useOrders()           GET   /api/dashboard/orders
   *   - useOrderDetail(id)     GET   /api/dashboard/orders/{order_id}
   *   - useOrderCancel(id)     POST  /api/dashboard/orders/{order_id}/cancel
   *
   * UI derives nothing about order truth — every status, fill, remaining
   * qty, rejection reason comes straight from the backend trace. The page
   * only layers: KPIs, client-side filters, client-side pagination (server
   * pagination is not yet supported by the backend), lifecycle timeline,
   * cancel-with-confirmation, refresh, and the standard loading/empty/
   * error/retry states. No mock data is fabricated.
   * ================================================================== */
  var ORDERS_DATA = [];   // populated by useOrders()
  var ORDERS_FILTERS = { status: "ALL", side: "ALL", symbol: "ALL", account: "ALL", search: "" };
  var ORDERS_SELECTED_ID = null;
  var ORDERS_DETAIL = null;        // trace {order, signal, risk_decision, execution, position, ledger}
  var ORDERS_LAST_UPDATED = "—";
  var ORDERS_PAGE = 0;
  var ORDERS_PAGE_SIZE = 50;

  // ── Small helpers ──────────────────────────────────────────────
  function _ordNum(v) { var n = Number(v); return isFinite(n) ? n : 0; }
  function _ordEsc(v) { return esc(v == null ? "" : String(v)); }
  function _pad2(n) { n = String(n); return n.length < 2 ? "0" + n : n; }
  function _ordFmtTime(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    var now = new Date();
    var hh = _pad2(d.getHours()), mm = _pad2(d.getMinutes()), ss = _pad2(d.getSeconds());
    if (d.toDateString() === now.toDateString()) return hh + ":" + mm + ":" + ss;
    return _pad2(d.getMonth() + 1) + "/" + _pad2(d.getDate()) + " " + hh + ":" + mm;
  }

  // ── Status mapping (backend enum → canonical label) ───────────
  // Backend OrderStatus: CREATED / SUBMITTED / ACCEPTED / PARTIALLY_FILLED
  // / FILLED / REJECTED / CANCELLED. Also tolerate workflow-engine
  // variants (PENDING / RISK_* / FAILED / EXPIRED) without fabricating.
  function orderStatusCanonical(status) {
    if (!status) return "NEW";
    var s = String(status).toUpperCase();
    if (s === "CREATED" || s === "NEW") return "NEW";
    if (s === "SUBMITTED" || s === "PENDING" || s === "RISK_CHECKING" || s === "RISK_APPROVED") return "PENDING";
    if (s === "ACCEPTED") return "ACCEPTED";
    if (s === "PARTIALLY_FILLED" || s === "PARTIAL") return "PARTIAL_FILLED";
    if (s === "FILLED") return "FILLED";
    if (s === "REJECTED" || s === "RISK_REJECTED") return "REJECTED";
    if (s === "CANCELLED" || s === "CANCELED") return "CANCELLED";
    if (s === "FAILED") return "FAILED";
    if (s === "EXPIRED") return "EXPIRED";
    return s;
  }

  function orderStatusVariant(status) {
    var m = {
      NEW: "info", PENDING: "warning", ACCEPTED: "info",
      PARTIAL_FILLED: "warning", FILLED: "profit",
      REJECTED: "loss", CANCELLED: "neutral", FAILED: "loss", EXPIRED: "neutral",
    };
    return m[orderStatusCanonical(status)] || "neutral";
  }

  function ordersStatusPill(status) {
    return UI.statusPill(orderStatusCanonical(status), orderStatusVariant(status));
  }

  // ── Client-side filtering (backend has no query params) ────────
  function ordersFiltered() {
    return ORDERS_DATA.filter(function (o) {
      var cs = orderStatusCanonical(o.status);
      if (ORDERS_FILTERS.status !== "ALL" && cs !== ORDERS_FILTERS.status) return false;
      if (ORDERS_FILTERS.side !== "ALL" && String(o.side) !== ORDERS_FILTERS.side) return false;
      if (ORDERS_FILTERS.symbol !== "ALL" && String(o.symbol) !== ORDERS_FILTERS.symbol) return false;
      if (ORDERS_FILTERS.account !== "ALL") {
        var acct = o.account_id || o.broker || "";
        if (acct !== ORDERS_FILTERS.account) return false;
      }
      if (ORDERS_FILTERS.search) {
        var q = ORDERS_FILTERS.search.toLowerCase();
        var hay = (o.order_id + " " + o.symbol + " " + o.status + " " + o.side + " " + (o.strategy_id || "")).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });
  }

  function _ordersAccountOptions() {
    var set = {};
    ORDERS_DATA.forEach(function (o) { var a = o.account_id || o.broker; if (a) set[a] = true; });
    return ["ALL"].concat(Object.keys(set));
  }

  function _ordersSymbolOptions() {
    var set = {};
    ORDERS_DATA.forEach(function (o) { if (o.symbol) set[o.symbol] = true; });
    return ["ALL"].concat(Object.keys(set));
  }

  // ── Table rows (10 columns incl. Filled + Avg Fill) ───────────
  function renderOrdersRows() {
    var filtered = ordersFiltered();
    var start = ORDERS_PAGE * ORDERS_PAGE_SIZE;
    var slice = filtered.slice(start, start + ORDERS_PAGE_SIZE);
    if (filtered.length === 0) {
      return '<tr class="ord-empty-row"><td colspan="10">' +
        UI.empty("No orders", "No orders match the current filters, or no orders have been submitted yet.") +
        '</td></tr>';
    }
    return slice.map(function (o) {
      var sel = o.order_id === ORDERS_SELECTED_ID ? " ord-row-selected" : "";
      var sideCls = String(o.side) === "BUY" ? "pos" : "neg";
      var price = (o.price != null && Number(o.price) > 0) ? "$" + _ordNum(o.price).toFixed(2) : "—";
      var filled = _ordNum(o.filled_quantity);
      var avgFill = (o.average_fill_price != null && Number(o.average_fill_price) > 0)
        ? "$" + _ordNum(o.average_fill_price).toFixed(2) : "—";
      return '<tr class="ord-row' + sel + '" data-ord-id="' + _ordEsc(o.order_id) + '">' +
        '<td class="ds-text-mono ord-col-id">' + _ordEsc(o.order_id) + '</td>' +
        '<td class="ds-text-mono ord-col-time">' + _ordFmtTime(o.created_at) + '</td>' +
        '<td class="ord-col-symbol"><span class="sym-link" data-href="#/system/data" title="Open in Data Center">' + _ordEsc(o.symbol) + '</span></td>' +
        '<td class="' + sideCls + ' ord-col-side">' + _ordEsc(o.side) + '</td>' +
        '<td class="ord-col-type">' + _ordEsc(o.order_type) + '</td>' +
        '<td class="num ds-text-mono ord-col-qty">' + _ordNum(o.quantity) + '</td>' +
        '<td class="num ds-text-mono ord-col-price">' + price + '</td>' +
        '<td class="num ds-text-mono ord-col-filled">' + filled + '</td>' +
        '<td class="num ds-text-mono ord-col-avgfill">' + avgFill + '</td>' +
        '<td class="ord-col-status">' + ordersStatusPill(o.status) + '</td>' +
        '</tr>';
    }).join("");
  }

  function renderOrdersTable() {
    return (
      '<table class="ds-table ord-table">' +
      '<thead><tr>' +
      '<th>Order ID</th>' +
      '<th>Time</th>' +
      '<th>Symbol</th>' +
      '<th>Side</th>' +
      '<th>Type</th>' +
      '<th class="num">Qty</th>' +
      '<th class="num">Price</th>' +
      '<th class="num">Filled</th>' +
      '<th class="num">Avg Fill</th>' +
      '<th>Status</th>' +
      '</tr></thead>' +
      '<tbody id="ord-tbody">' + renderOrdersRows() + '</tbody>' +
      '</table>'
    );
  }

  // ── Pagination (client-side; backend has no server pagination) ─
  function _paginationInner() {
    var total = ordersFiltered().length;
    var totalPages = Math.max(1, Math.ceil(total / ORDERS_PAGE_SIZE));
    var page = ORDERS_PAGE + 1;
    var start = total === 0 ? 0 : ORDERS_PAGE * ORDERS_PAGE_SIZE + 1;
    var end = Math.min(total, (ORDERS_PAGE + 1) * ORDERS_PAGE_SIZE);
    var note = total > ORDERS_PAGE_SIZE
      ? "Showing " + start + "–" + end + " of " + total
      : "Total " + total + " · server pagination unavailable";
    return (
      '<span class="ord-pagination-info">' + note + '</span>' +
      '<div class="ord-pagination-controls">' +
      UI.button("‹ Prev", "ghost", { sm: true, action: "ord:page-prev", disabled: ORDERS_PAGE === 0 }) +
      '<span class="ord-pagination-page">Page ' + page + ' / ' + totalPages + '</span>' +
      UI.button("Next ›", "ghost", { sm: true, action: "ord:page-next", disabled: ORDERS_PAGE >= totalPages - 1 }) +
      '</div>'
    );
  }

  function renderOrdersPagination() {
    return '<div class="ord-pagination" id="ord-pagination">' + _paginationInner() + '</div>';
  }

  // ── Lifecycle timeline synthesised from order timestamps ──────
  // Only emits events whose timestamp / condition actually exists on
  // the order — no fabricated milestones.
  function _buildOrderTimeline(o, trace) {
    var ev = [];
    if (o.created_at) ev.push({ time: _ordFmtTime(o.created_at), type: "CREATED", title: "Order created", variant: "info" });
    if (o.submitted_at) ev.push({ time: _ordFmtTime(o.submitted_at), type: "SUBMITTED", title: "Submitted to Order Engine", variant: "info" });
    if (trace && trace.risk_decision) {
      var rd = trace.risk_decision;
      var decStr = String(rd.decision || rd.status || rd.outcome || "").toUpperCase();
      var approved = rd.approved === true || decStr.indexOf("APPROV") >= 0;
      ev.push({
        time: _ordFmtTime(o.submitted_at || o.created_at),
        type: "RISK", title: "Risk check: " + (approved ? "Approved" : "Rejected"),
        variant: approved ? "profit" : "loss",
      });
    }
    var cs = orderStatusCanonical(o.status);
    if (cs === "ACCEPTED" || cs === "PARTIAL_FILLED" || cs === "FILLED") {
      ev.push({ time: _ordFmtTime(o.updated_at || o.submitted_at), type: "ACCEPTED", title: "Accepted by Execution Engine", variant: "info" });
    }
    var qty = _ordNum(o.quantity), filled = _ordNum(o.filled_quantity);
    if ((cs === "PARTIAL_FILLED" || (filled > 0 && filled < qty)) && o.average_fill_price) {
      ev.push({ time: _ordFmtTime(o.updated_at), type: "PARTIAL", title: "Partial fill " + filled + " / " + qty + " @ $" + _ordNum(o.average_fill_price).toFixed(2), variant: "warning" });
    }
    if (cs === "FILLED" && o.filled_at) {
      ev.push({ time: _ordFmtTime(o.filled_at), type: "FILLED", title: "Filled " + filled + (o.average_fill_price ? " @ $" + _ordNum(o.average_fill_price).toFixed(2) : ""), variant: "profit" });
    }
    if (cs === "CANCELLED" && o.cancelled_at) {
      ev.push({ time: _ordFmtTime(o.cancelled_at), type: "CANCELLED", title: "Cancelled" + (o.notes ? " — " + o.notes : ""), variant: "neutral" });
    }
    if (cs === "REJECTED" || (cs !== "CANCELLED" && o.rejection_reason)) {
      ev.push({ time: _ordFmtTime(o.updated_at || o.submitted_at), type: "REJECTED", title: "Rejected" + (o.rejection_reason ? " — " + o.rejection_reason : ""), variant: "loss" });
    }
    if (cs === "FAILED") {
      ev.push({ time: _ordFmtTime(o.updated_at), type: "FAILED", title: "Order failed" + (o.rejection_reason ? " — " + o.rejection_reason : ""), variant: "loss" });
    }
    if (cs === "EXPIRED") {
      ev.push({ time: _ordFmtTime(o.updated_at), type: "EXPIRED", title: "Order expired", variant: "neutral" });
    }
    return ev;
  }

  // ── Order detail (from real trace, falls back to list row) ─────
  function renderOrdersDetail() {
    var trace = ORDERS_DETAIL;
    var o = trace ? trace.order : null;
    if (!o && ORDERS_SELECTED_ID) {
      for (var i = 0; i < ORDERS_DATA.length; i++) {
        if (ORDERS_DATA[i].order_id === ORDERS_SELECTED_ID) { o = ORDERS_DATA[i]; break; }
      }
    }
    if (!o) {
      return UI.empty("No order selected", "Click an order row to view details and the execution lifecycle.");
    }
    var cs = orderStatusCanonical(o.status);
    var statusVariant = orderStatusVariant(o.status);
    var sideVariant = String(o.side) === "BUY" ? "profit" : "loss";
    var qty = _ordNum(o.quantity);
    var filled = _ordNum(o.filled_quantity);
    var remaining = _ordNum(o.remaining_quantity != null ? o.remaining_quantity : (qty - filled));
    var avgFill = (o.average_fill_price != null && Number(o.average_fill_price) > 0)
      ? "$" + _ordNum(o.average_fill_price).toFixed(2) : "—";
    var limitPrice = (o.price != null && Number(o.price) > 0) ? "$" + _ordNum(o.price).toFixed(2) : "—";

    var detail = UI.statRows([
      { label: "Order ID", value: _ordEsc(o.order_id) },
      { label: "Strategy", value: _ordEsc(o.strategy_id || "—") },
      { label: "Account", value: _ordEsc(o.account_id || o.broker || "—") },
      { label: "Symbol", value: _ordEsc(o.symbol) },
      { label: "Side", value: _ordEsc(o.side), variant: sideVariant },
      { label: "Quantity", value: String(qty) },
      { label: "Order Type", value: _ordEsc(o.order_type || "—") },
      { label: "Limit Price", value: limitPrice },
      { label: "Time in Force", value: _ordEsc(o.time_in_force || "—") },
      { label: "Status", value: cs, variant: statusVariant },
    ]);

    var fills = UI.statRows([
      { label: "Filled Qty", value: filled + " / " + qty },
      { label: "Remaining Qty", value: String(remaining) },
      { label: "Avg Fill Price", value: avgFill },
    ]);

    // Execution info (from trace.execution, only when present)
    var execBlock = "";
    if (trace && trace.execution) {
      var ex = trace.execution;
      execBlock = UI.sectionHeading("Execution") + UI.statRows([
        { label: "Fill Qty", value: String(_ordNum(ex.quantity)) },
        { label: "Average Fill", value: (ex.price != null ? "$" + _ordNum(ex.price).toFixed(2) : "—") },
        { label: "Fill Time", value: _ordFmtTime(ex.timestamp) },
        { label: "Execution Status", value: cs },
      ]);
    }

    // Reject reason callout (when rejected / failed)
    var rejectBlock = "";
    if (cs === "REJECTED" || cs === "FAILED" || o.rejection_reason) {
      rejectBlock = '<div class="ds-callout ds-callout-loss" style="margin:var(--ds-space-sm) 0;">' +
        '<div class="ds-text-muted" style="font-size:var(--ds-text-xs);">REJECT REASON</div>' +
        '<div class="ds-text-mono" style="margin-top:var(--ds-space-xs);">' +
        _ordEsc(o.rejection_reason || "Not specified") + '</div>' +
        '</div>';
    }

    // Lifecycle timeline (synthesised from timestamps)
    var timeline = _buildOrderTimeline(o, trace);
    var timelineHtml = timeline.length > 0
      ? UI.timeline(timeline)
      : UI.empty("No lifecycle events", "This order has no recorded events.");

    // Cancel button — only for active (non-terminal) orders
    var cancelBtn = "";
    var terminal = cs === "CANCELLED" || cs === "FILLED" || cs === "REJECTED" || cs === "FAILED" || cs === "EXPIRED";
    if (o.is_active === true && !terminal) {
      cancelBtn = '<div style="margin-top:var(--ds-space-md);">' +
        UI.button("Cancel Order", "danger", { sm: true, action: "ord:cancel" }) +
        '</div>';
    }

    return (
      detail +
      rejectBlock +
      UI.sectionHeading("Fills") +
      fills +
      execBlock +
      UI.sectionHeading("Lifecycle") +
      timelineHtml +
      cancelBtn
    );
  }

  // ── KPIs + Filters ─────────────────────────────────────────────
  function renderOrdersKPIs() {
    var total = ORDERS_DATA.length;
    var open = ORDERS_DATA.filter(function (o) {
      var cs = orderStatusCanonical(o.status);
      return cs === "NEW" || cs === "PENDING" || cs === "ACCEPTED" || cs === "PARTIAL_FILLED";
    }).length;
    var filled = ORDERS_DATA.filter(function (o) { return orderStatusCanonical(o.status) === "FILLED"; }).length;
    var rejected = ORDERS_DATA.filter(function (o) {
      var cs = orderStatusCanonical(o.status);
      return cs === "REJECTED" || cs === "FAILED";
    }).length;
    return UI.metricCard("Total Orders", String(total), "All statuses", "info") +
      UI.metricCard("Open Orders", String(open), "New / Pending / Partial", "warning") +
      UI.metricCard("Filled", String(filled), "Complete fills", "pos") +
      UI.metricCard("Rejected", String(rejected), "Risk / Engine rejects", "neg");
  }

  function renderOrdersFilters() {
    var symbolOpts = _ordersSymbolOptions().map(function (s) {
      return { value: s, label: s === "ALL" ? "All Symbols" : s };
    });
    var accountOpts = _ordersAccountOptions().map(function (a) {
      return { value: a, label: a === "ALL" ? "All Accounts" : a };
    });
    return (
      '<div class="ord-filters">' +
      '<div class="ord-filter-field"><label class="ord-filter-label">Account</label>' +
      UI.select({ id: "ord-filter-account", options: accountOpts }) + '</div>' +
      '<div class="ord-filter-field"><label class="ord-filter-label">Symbol</label>' +
      UI.select({ id: "ord-filter-symbol", options: symbolOpts }) + '</div>' +
      '<div class="ord-filter-field"><label class="ord-filter-label">Side</label>' +
      UI.select({ id: "ord-filter-side", options: [
        { value: "ALL", label: "All Sides" },
        { value: "BUY", label: "BUY" },
        { value: "SELL", label: "SELL" },
      ] }) + '</div>' +
      '<div class="ord-filter-field"><label class="ord-filter-label">Status</label>' +
      UI.select({ id: "ord-filter-status", options: [
        { value: "ALL", label: "All Status" },
        { value: "NEW", label: "New" },
        { value: "PENDING", label: "Pending" },
        { value: "ACCEPTED", label: "Accepted" },
        { value: "PARTIAL_FILLED", label: "Partially Filled" },
        { value: "FILLED", label: "Filled" },
        { value: "REJECTED", label: "Rejected" },
        { value: "CANCELLED", label: "Cancelled" },
        { value: "FAILED", label: "Failed" },
        { value: "EXPIRED", label: "Expired" },
      ] }) + '</div>' +
      '<div class="ord-filter-field ord-filter-search-wrap">' +
      UI.search("Search ID / symbol…", "ord-filter-search") + '</div>' +
      '</div>'
    );
  }

  function _renderOrdersRefreshAction() {
    return '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);">Total: <span id="ord-total">' +
      ORDERS_DATA.length + '</span> · Updated: <span class="ds-text-mono" id="ord-last-updated">' +
      _ordEsc(ORDERS_LAST_UPDATED) + '</span></span> ' +
      '<button class="btn btn-ghost btn-sm" data-action="ord:refresh" type="button">↻ Refresh</button>';
  }

  // ── Cancel modal (with duplicate-action protection) ────────────
  function openCancelOrderModal(orderId, order) {
    var sideVariant = String(order.side) === "BUY" ? "profit" : "loss";
    UI.openModal({
      title: "Cancel Order?",
      body:
        '<div class="ord-cancel-summary">' +
        '<div class="ord-cancel-symbol">' + _ordEsc(order.symbol) + '</div>' +
        '<div class="ord-cancel-desc">' +
        ordersStatusPill(order.status) + ' ' +
        '<span class="ds-text-' + sideVariant + '">' + _ordEsc(order.side) + '</span> ' +
        '<span class="ds-text-mono">' + _ordNum(order.quantity) + '</span>' +
        (order.order_type ? ' · <span>' + _ordEsc(order.order_type) + '</span>' : '') +
        (order.price && Number(order.price) > 0 ? ' @ <span class="ds-text-mono">$' + _ordNum(order.price).toFixed(2) + '</span>' : '') +
        '</div>' +
        '<div class="ds-text-muted" style="margin-top:var(--ds-space-sm);font-size:var(--ds-text-xs);">' +
        'Order ID: <span class="ds-text-mono">' + _ordEsc(orderId) + '</span>' +
        '</div>' +
        '</div>',
      footer:
        UI.button("Keep Order", "ghost", { action: "close-modal" }) +
        UI.button("Cancel Order", "danger", { action: "ord:cancel-confirm" }),
      onMount: function (backdrop) {
        var btn = backdrop.querySelector('[data-action="ord:cancel-confirm"]');
        if (!btn) return;
        btn.addEventListener("click", async function () {
          // Duplicate-action protection — ignore repeated clicks while pending
          if (btn.getAttribute("data-pending") === "1") return;
          btn.setAttribute("data-pending", "1");
          btn.disabled = true;
          btn.textContent = "Cancelling…";
          try {
            var updated = await useOrderCancel(orderId);
            if (updated) {
              for (var i = 0; i < ORDERS_DATA.length; i++) {
                if (ORDERS_DATA[i].order_id === orderId) { ORDERS_DATA[i] = updated; break; }
              }
            }
            if (ORDERS_DETAIL && ORDERS_DETAIL.order && ORDERS_DETAIL.order.order_id === orderId) {
              ORDERS_DETAIL = Object.assign({}, ORDERS_DETAIL, { order: updated || ORDERS_DETAIL.order });
            }
            UI.closeModal();
            refreshOrdersUI();
            if (ORDERS_SELECTED_ID === orderId) loadOrderDetailAsync(orderId);
            showToast("Order cancelled / 订单已取消", "ok");
          } catch (err) {
            btn.disabled = false;
            btn.removeAttribute("data-pending");
            btn.textContent = "Cancel Order";
            showToast("Cancel failed / 取消失败: " + (err && err.message ? err.message : String(err)), "err");
          }
        });
      },
    });
  }

  // ── Refresh + Detail loaders (async, fault-tolerant) ───────────
  function refreshOrdersUI() {
    var tbody = document.getElementById("ord-tbody");
    if (tbody) tbody.innerHTML = renderOrdersRows();
    var pag = document.getElementById("ord-pagination");
    if (pag) pag.innerHTML = _paginationInner();
    var kpisEl = document.getElementById("ord-kpis");
    if (kpisEl) kpisEl.innerHTML = renderOrdersKPIs();
    var totalEl = document.getElementById("ord-total");
    if (totalEl) totalEl.textContent = String(ORDERS_DATA.length);
    var lastUpd = document.getElementById("ord-last-updated");
    if (lastUpd) lastUpd.textContent = ORDERS_LAST_UPDATED;
  }

  async function loadOrdersAsync() {
    var refreshBtn = document.querySelector('[data-action="ord:refresh"]');
    if (refreshBtn) { refreshBtn.disabled = true; refreshBtn.textContent = "Refreshing…"; }
    try {
      ORDERS_DATA = await useOrders();
      ORDERS_LAST_UPDATED = new Date().toLocaleTimeString("en-US", { hour12: false });
      ORDERS_PAGE = 0;
      // Re-select first if the previously selected order is gone
      var stillExists = ORDERS_DATA.some(function (o) { return o.order_id === ORDERS_SELECTED_ID; });
      if (!stillExists) {
        ORDERS_SELECTED_ID = ORDERS_DATA[0] ? ORDERS_DATA[0].order_id : null;
        ORDERS_DETAIL = null;
        if (ORDERS_SELECTED_ID) loadOrderDetailAsync(ORDERS_SELECTED_ID);
        else {
          var d = document.getElementById("ord-detail");
          if (d) d.innerHTML = renderOrdersDetail();
        }
      }
      refreshOrdersUI();
      showToast("Orders refreshed / 订单已刷新", "ok");
    } catch (err) {
      showToast("Refresh failed / 刷新失败: " + (err && err.message ? err.message : String(err)), "err");
    } finally {
      if (refreshBtn) { refreshBtn.disabled = false; refreshBtn.textContent = "↻ Refresh"; }
    }
  }

  async function loadOrderDetailAsync(orderId) {
    var detailEl = document.getElementById("ord-detail");
    if (detailEl) detailEl.innerHTML = UI.stateLoading("Loading order…", "Fetching detail and lifecycle trace.");
    try {
      ORDERS_DETAIL = await useOrderDetail(orderId);
      if (detailEl) detailEl.innerHTML = renderOrdersDetail();
    } catch (err) {
      if (err && err.status === 404) {
        ORDERS_DETAIL = null;
        if (detailEl) detailEl.innerHTML = UI.empty("Order not found", "This order may have been removed.");
      } else {
        if (detailEl) detailEl.innerHTML = UI.stateError(
          "Failed to load order detail",
          (err && err.message ? err.message : String(err)),
          "Retry", "ord:detail-retry"
        );
      }
    }
  }

  // ── Bind: delegated handlers on #ord-root (survive innerHTML) ──
  function bindOrdersPage() {
    var root = document.getElementById("ord-root");
    if (!root) return;
    // Lazy-load detail for pre-selected order
    if (ORDERS_SELECTED_ID && !ORDERS_DETAIL) loadOrderDetailAsync(ORDERS_SELECTED_ID);

    // Single delegated click handler — catches all ord:* buttons + rows
    root.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action]");
      if (btn) {
        var action = btn.getAttribute("data-action");
        if (action === "ord:page-prev") {
          if (ORDERS_PAGE > 0) { ORDERS_PAGE--; refreshOrdersUI(); }
          return;
        }
        if (action === "ord:page-next") {
          var maxPage = Math.max(0, Math.ceil(ordersFiltered().length / ORDERS_PAGE_SIZE) - 1);
          if (ORDERS_PAGE < maxPage) { ORDERS_PAGE++; refreshOrdersUI(); }
          return;
        }
        if (action === "ord:refresh") { loadOrdersAsync(); return; }
        if (action === "ord:detail-retry" && ORDERS_SELECTED_ID) {
          loadOrderDetailAsync(ORDERS_SELECTED_ID); return;
        }
        if (action === "ord:cancel") {
          var oid = ORDERS_SELECTED_ID;
          if (!oid) return;
          var o = (ORDERS_DETAIL && ORDERS_DETAIL.order && ORDERS_DETAIL.order.order_id === oid)
            ? ORDERS_DETAIL.order : null;
          if (!o) {
            for (var i = 0; i < ORDERS_DATA.length; i++) {
              if (ORDERS_DATA[i].order_id === oid) { o = ORDERS_DATA[i]; break; }
            }
          }
          if (o) openCancelOrderModal(oid, o);
          return;
        }
        return;
      }
      // Row selection (delegated on tbody rows)
      var row = e.target.closest("tr[data-ord-id]");
      if (row) {
        var rid = row.getAttribute("data-ord-id");
        if (rid === ORDERS_SELECTED_ID) return;
        ORDERS_SELECTED_ID = rid;
        var tbody = document.getElementById("ord-tbody");
        if (tbody) tbody.querySelectorAll("tr").forEach(function (tr) { tr.classList.remove("ord-row-selected"); });
        row.classList.add("ord-row-selected");
        loadOrderDetailAsync(rid);
      }
    });

    // Filter selects
    function bindFilter(id, key) {
      var sel = document.getElementById(id);
      if (sel) sel.addEventListener("change", function () {
        ORDERS_FILTERS[key] = sel.value;
        ORDERS_PAGE = 0;
        refreshOrdersUI();
      });
    }
    bindFilter("ord-filter-status", "status");
    bindFilter("ord-filter-side", "side");
    bindFilter("ord-filter-symbol", "symbol");
    bindFilter("ord-filter-account", "account");

    // Search input
    var search = document.getElementById("ord-filter-search");
    if (search) search.addEventListener("input", function () {
      ORDERS_FILTERS.search = search.value;
      ORDERS_PAGE = 0;
      refreshOrdersUI();
    });
  }

  PAGE_FRAMEWORK["trading/orders"] = async function () {
    // Initial load — throws on failure → render() catch → stateError + Retry
    ORDERS_DATA = await useOrders();
    ORDERS_LAST_UPDATED = new Date().toLocaleTimeString("en-US", { hour12: false });
    // ④ terminal-wide account context feeds the page filter
    ORDERS_FILTERS = { status: "ALL", side: "ALL", symbol: "ALL", account: APP_CTX.accountId, search: "" };
    ORDERS_PAGE = 0;
    ORDERS_DETAIL = null;
    // Pre-select first order (if any)
    var exists = ORDERS_DATA.some(function (o) { return o.order_id === ORDERS_SELECTED_ID; });
    if (!exists) ORDERS_SELECTED_ID = ORDERS_DATA[0] ? ORDERS_DATA[0].order_id : null;

    var layout =
      '<div class="ord-layout" id="ord-root">' +
      '<div class="ord-layout-main">' +
      UI.panel("Open Orders", renderOrdersTable() + renderOrdersPagination(), {
        actions: _renderOrdersRefreshAction(),
      }) +
      '</div>' +
      '<div class="ord-layout-side">' +
      UI.panel("Selected Order", '<div id="ord-detail">' + renderOrdersDetail() + '</div>') +
      '</div>' +
      '</div>';

    return (
      UI.pageHeader("Orders", "Order management and lifecycle tracking · 订单管理",
        UI.button("Place Order", "primary", { sm: true, action: "nav:trading" })) +
      '<div id="ord-kpis">' + UI.kpiGrid(renderOrdersKPIs(), 4) + '</div>' +
      UI.sectionHeading("Filters") +
      renderOrdersFilters() +
      UI.sectionHeading("Orders") +
      layout
    );
  };

  /* ==================================================================
   * Positions module — Integration 006 (real API)
   *
   * Positions page wired to the live Position Ledger via two thin hooks:
   *   - usePositions()              GET  /api/dashboard/positions
   *   - usePositionDetail(symbol)   GET  /api/dashboard/positions/{symbol}
   *
   * The Position Ledger is the single source of truth for quantity / side
   * / avg price. The UI derives nothing about position truth — every qty,
   * side, P&L, exposure comes straight from the backend. The page only
   * layers: KPIs (from summary), client-side filters, exposure breakdown,
   * detail with ledger fill history (Orders → Fills → Position), refresh,
   * and the standard loading/empty/error/retry states. No mock data.
   * ================================================================== */
  var POSITIONS_PAYLOAD = { summary: {}, positions: [] };
  var POSITIONS_SELECTED_SYMBOL = null;
  var POSITIONS_DETAIL = null;        // {position, ledger_events}
  var POSITIONS_LAST_UPDATED = "—";
  var POSITIONS_FILTERS = { account: "ALL", symbol: "ALL", side: "ALL", visibility: "OPEN" };

  // ── Small helpers ──────────────────────────────────────────────
  function _posNum(v) { var n = Number(v); return isFinite(n) ? n : 0; }
  function _posEsc(v) { return esc(v == null ? "" : String(v)); }
  function _pad2p(n) { n = String(n); return n.length < 2 ? "0" + n : n; }
  function _posFmtTime(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    var now = new Date();
    var hh = _pad2p(d.getHours()), mm = _pad2p(d.getMinutes()), ss = _pad2p(d.getSeconds());
    if (d.toDateString() === now.toDateString()) return hh + ":" + mm + ":" + ss;
    return _pad2p(d.getMonth() + 1) + "/" + _pad2p(d.getDate()) + " " + hh + ":" + mm;
  }
  function _posMoney(n) {
    return "$" + _posNum(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function _posSignedMoney(n) {
    var v = _posNum(n);
    return (v >= 0 ? "+" : "-") + "$" + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  // ── Side canonicalisation (backend already LONG/SHORT/FLAT) ───
  // Tolerate variant spellings without fabricating values. The UI does
  // NOT simulate Short — whether a Short may exist is decided by the
  // Ledger / Risk, the UI only reflects what the backend returns.
  function positionSideCanonical(side) {
    if (!side) return "FLAT";
    var s = String(side).toUpperCase();
    if (s === "LONG" || s === "BUY") return "LONG";
    if (s === "SHORT" || s === "SELL") return "SHORT";
    if (s === "FLAT" || s === "NONE" || s === "CASH") return "FLAT";
    return s;
  }

  function positionSideVariant(side) {
    var m = { LONG: "profit", SHORT: "loss", FLAT: "neutral" };
    return m[positionSideCanonical(side)] || "neutral";
  }

  function positionSidePill(side) {
    return UI.statusPill(positionSideCanonical(side), positionSideVariant(side));
  }

  // ── Portfolio equity (for weight calc) ────────────────────────
  function _positionsEquity() { return _posNum(POSITIONS_PAYLOAD.summary.total_equity); }

  function _positionWeightPct(p) {
    var eq = _positionsEquity();
    var mv = _posNum(p.market_value);
    return eq > 0 ? (mv / eq) * 100 : 0;
  }

  // ── Client-side filters (backend has no query params) ────────
  // visibility: OPEN (default) hides FLAT; ALL shows everything; FLAT only flat.
  function positionsFiltered() {
    return POSITIONS_PAYLOAD.positions.filter(function (p) {
      var cs = positionSideCanonical(p.side);
      if (POSITIONS_FILTERS.visibility === "OPEN" && cs === "FLAT") return false;
      if (POSITIONS_FILTERS.visibility === "FLAT" && cs !== "FLAT") return false;
      if (POSITIONS_FILTERS.side !== "ALL" && cs !== POSITIONS_FILTERS.side) return false;
      if (POSITIONS_FILTERS.symbol !== "ALL" && String(p.symbol) !== POSITIONS_FILTERS.symbol) return false;
      if (POSITIONS_FILTERS.account !== "ALL") {
        var acct = p.account_id || p.account || "";
        if (acct !== POSITIONS_FILTERS.account) return false;
      }
      return true;
    });
  }

  function _positionsAccountOptions() {
    var set = {};
    POSITIONS_PAYLOAD.positions.forEach(function (p) { var a = p.account_id || p.account; if (a) set[a] = true; });
    return ["ALL"].concat(Object.keys(set));
  }

  function _positionsSymbolOptions() {
    var set = {};
    POSITIONS_PAYLOAD.positions.forEach(function (p) { if (p.symbol) set[p.symbol] = true; });
    return ["ALL"].concat(Object.keys(set));
  }

  // ── Exposure breakdown (from summary, with client-side split) ─
  function _positionsExposure() {
    var positions = POSITIONS_PAYLOAD.positions;
    var longExp = 0, shortExp = 0, grossExp = 0, netExp = 0;
    positions.forEach(function (p) {
      var cs = positionSideCanonical(p.side);
      var mv = _posNum(p.market_value);
      var signed = cs === "SHORT" ? -mv : mv;
      grossExp += Math.abs(mv);
      netExp += signed;
      if (cs === "LONG") longExp += mv;
      else if (cs === "SHORT") shortExp += mv;
    });
    var summary = POSITIONS_PAYLOAD.summary || {};
    return {
      gross: _posNum(summary.gross_exposure) || grossExp,
      net: _posNum(summary.net_exposure) || netExp,
      long: longExp,
      short: shortExp,
      cash: _posNum(summary.cash),
    };
  }

  function renderPositionExposureBars() {
    var open = POSITIONS_PAYLOAD.positions.filter(function (p) { return positionSideCanonical(p.side) !== "FLAT"; });
    if (open.length === 0) {
      return UI.empty("No open positions", "All positions are flat — no risk exposure.");
    }
    var maxVal = Math.max.apply(null, open.map(function (p) { return _posNum(p.market_value); })) || 1;
    return open.map(function (p) {
      var mv = _posNum(p.market_value);
      var pct = Math.round((mv / maxVal) * 100);
      var barClass = positionSideCanonical(p.side) === "SHORT" ? "neg-bar" : "pos-bar";
      return (
        '<div class="pos-exp-row">' +
        '<span class="pos-exp-sym">' + _posEsc(p.symbol) + '</span>' +
        '<div class="pos-exp-track">' +
        '<div class="pos-exp-fill ' + barClass + '" style="width:' + pct + '%"></div>' +
        '</div>' +
        '<span class="pos-exp-qty ds-text-mono">' + _posNum(p.quantity) + ' shares</span>' +
        '<span class="pos-exp-val ds-text-mono">' + _posMoney(mv) + '</span>' +
        '</div>'
      );
    }).join("");
  }

  // ── Table rows (11 columns incl. Realized P&L + Weight + Updated) ─
  function renderPositionsRows() {
    var filtered = positionsFiltered();
    if (filtered.length === 0) {
      return '<tr class="pos-empty-row"><td colspan="11">' +
        UI.empty("No positions", "No positions match the current filters, or no positions have been opened yet.") +
        '</td></tr>';
    }
    return filtered.map(function (p) {
      var sel = p.symbol === POSITIONS_SELECTED_SYMBOL ? " pos-row-selected" : "";
      var cs = positionSideCanonical(p.side);
      var sideCls = cs === "LONG" ? "pos" : (cs === "SHORT" ? "neg" : "");
      var pnlCls = _posNum(p.unrealized_pnl) >= 0 ? "pos" : "neg";
      var realCls = _posNum(p.realized_pnl) >= 0 ? "pos" : "neg";
      var qtyText = cs === "FLAT" ? "0" : String(_posNum(p.quantity));
      var avgText = cs === "FLAT" ? "—" : _posMoney(p.avg_price);
      var lastText = _posMoney(p.last_price);
      var mvText = cs === "FLAT" ? "—" : _posMoney(p.market_value);
      var uPnlText = cs === "FLAT" ? "—" : _posSignedMoney(p.unrealized_pnl);
      var rPnlText = _posSignedMoney(p.realized_pnl);
      var weightText = _positionWeightPct(p).toFixed(1) + "%";
      return '<tr class="pos-row' + sel + '" data-pos-symbol="' + _posEsc(p.symbol) + '">' +
        '<td class="pos-col-symbol"><span class="sym-link" data-href="#/system/data" title="Open in Data Center">' + _posEsc(p.symbol) + '</span></td>' +
        '<td class="pos-col-account">' + _posEsc(p.account_id || p.account || "—") + '</td>' +
        '<td>' + positionSidePill(p.side) + '</td>' +
        '<td class="num ds-text-mono ' + sideCls + '">' + qtyText + '</td>' +
        '<td class="num ds-text-mono">' + avgText + '</td>' +
        '<td class="num ds-text-mono">' + lastText + '</td>' +
        '<td class="num ds-text-mono">' + mvText + '</td>' +
        '<td class="num ds-text-mono ' + pnlCls + '">' + uPnlText + '</td>' +
        '<td class="num ds-text-mono ' + realCls + '">' + rPnlText + '</td>' +
        '<td class="num ds-text-mono">' + weightText + '</td>' +
        '<td class="num ds-text-mono pos-col-updated">' + _posFmtTime(p.updated_at) + '</td>' +
        '</tr>';
    }).join("");
  }

  function renderPositionsTable() {
    return (
      '<table class="ds-table pos-table">' +
      '<thead><tr>' +
      '<th>Symbol</th>' +
      '<th>Account</th>' +
      '<th>Side</th>' +
      '<th class="num">Qty</th>' +
      '<th class="num">Avg Price</th>' +
      '<th class="num">Last Price</th>' +
      '<th class="num">Market Value</th>' +
      '<th class="num">Unreal P&L</th>' +
      '<th class="num">Real P&L</th>' +
      '<th class="num">Weight</th>' +
      '<th class="num">Updated</th>' +
      '</tr></thead>' +
      '<tbody id="pos-tbody">' + renderPositionsRows() + '</tbody>' +
      '</table>'
    );
  }

  // ── Position detail (from real ledger trace) ──────────────────
  // Timeline = ORDER_FILLED ledger events for this symbol (Orders → Fills
  // → Position). Only real events are shown — nothing is fabricated.
  function _buildPositionTimeline(detail) {
    var events = (detail && detail.ledger_events) || [];
    if (events.length === 0) return [];
    var sorted = events.slice().sort(function (a, b) {
      var ta = new Date(a.timestamp || 0).getTime();
      var tb = new Date(b.timestamp || 0).getTime();
      return ta - tb;
    });
    return sorted.map(function (e) {
      var pload = e.payload || {};
      var side = String(pload.side || "").toUpperCase();
      var qty = _posNum(pload.quantity);
      var price = _posNum(pload.price);
      var oid = pload.order_id || "—";
      var etype = String(e.event_type || "").toUpperCase();
      var title;
      if (etype.indexOf("FILLED") >= 0 || etype.indexOf("EXEC") >= 0) {
        title = "Fill " + side + " " + qty + " @ " + _posMoney(price) + " · " + oid;
      } else {
        title = etype + " · " + oid;
      }
      return {
        time: _posFmtTime(e.timestamp),
        type: etype,
        title: title,
        variant: side === "SELL" ? "loss" : "profit",
      };
    });
  }

  function renderPositionDetail() {
    var p = null;
    var detail = POSITIONS_DETAIL;
    if (detail && detail.position) {
      p = detail.position;
    } else if (POSITIONS_SELECTED_SYMBOL) {
      for (var i = 0; i < POSITIONS_PAYLOAD.positions.length; i++) {
        if (POSITIONS_PAYLOAD.positions[i].symbol === POSITIONS_SELECTED_SYMBOL) { p = POSITIONS_PAYLOAD.positions[i]; break; }
      }
    }
    if (!p) {
      return UI.empty("No position selected", "Click a position row to view details and the fill lifecycle.");
    }
    var cs = positionSideCanonical(p.side);
    var qty = _posNum(p.quantity);
    var avgPrice = _posNum(p.avg_price);
    var lastPrice = _posNum(p.last_price);
    var mv = _posNum(p.market_value);
    var uPnl = _posNum(p.unrealized_pnl);
    var rPnl = _posNum(p.realized_pnl);
    var tPnl = uPnl + rPnl;
    var weight = _positionWeightPct(p);

    var grid =
      '<div class="pos-detail-grid">' +
      '<div class="pos-detail-cell"><div class="pos-detail-label">Symbol</div><div class="pos-detail-value ds-text-mono">' + _posEsc(p.symbol) + '</div></div>' +
      '<div class="pos-detail-cell"><div class="pos-detail-label">Side</div><div class="pos-detail-value">' + positionSidePill(p.side) + '</div></div>' +
      '<div class="pos-detail-cell"><div class="pos-detail-label">Account</div><div class="pos-detail-value ds-text-mono">' + _posEsc(p.account_id || p.account || "—") + '</div></div>' +
      '<div class="pos-detail-cell"><div class="pos-detail-label">Quantity</div><div class="pos-detail-value ds-text-mono">' + (cs === "FLAT" ? "0" : String(qty)) + '</div></div>' +
      '<div class="pos-detail-cell"><div class="pos-detail-label">Average Price</div><div class="pos-detail-value ds-text-mono">' + (cs === "FLAT" ? "—" : _posMoney(avgPrice)) + '</div></div>' +
      '<div class="pos-detail-cell"><div class="pos-detail-label">Last Price</div><div class="pos-detail-value ds-text-mono">' + _posMoney(lastPrice) + '</div></div>' +
      '<div class="pos-detail-cell"><div class="pos-detail-label">Market Value</div><div class="pos-detail-value ds-text-mono">' + (cs === "FLAT" ? "—" : _posMoney(mv)) + '</div></div>' +
      '<div class="pos-detail-cell"><div class="pos-detail-label">Portfolio Weight</div><div class="pos-detail-value ds-text-mono">' + weight.toFixed(2) + '%</div></div>' +
      '<div class="pos-detail-cell pos-detail-pnl"><div class="pos-detail-label">Unrealized P&L</div><div class="pos-detail-value ds-text-mono ' + (uPnl >= 0 ? "pos" : "neg") + '">' + (cs === "FLAT" ? "—" : _posSignedMoney(uPnl)) + '</div></div>' +
      '<div class="pos-detail-cell pos-detail-pnl"><div class="pos-detail-label">Realized P&L</div><div class="pos-detail-value ds-text-mono ' + (rPnl >= 0 ? "pos" : "neg") + '">' + _posSignedMoney(rPnl) + '</div></div>' +
      '<div class="pos-detail-cell pos-detail-pnl"><div class="pos-detail-label">Total P&L</div><div class="pos-detail-value ds-text-mono ' + (tPnl >= 0 ? "pos" : "neg") + '">' + _posSignedMoney(tPnl) + '</div></div>' +
      '</div>';

    var timeline = _buildPositionTimeline(detail);
    var timelineHtml = timeline.length > 0
      ? UI.timeline(timeline)
      : UI.empty("No fill history", "This position has no recorded ledger fills yet.");

    return grid + UI.sectionHeading("Position History · Orders → Fills → Position") + timelineHtml;
  }

  // ── KPIs + Filters ─────────────────────────────────────────────
  function renderPositionsKPIs() {
    var all = POSITIONS_PAYLOAD.positions;
    var open = all.filter(function (p) { return positionSideCanonical(p.side) !== "FLAT"; });
    var exp = _positionsExposure();
    var uPnl = all.reduce(function (s, p) { return s + _posNum(p.unrealized_pnl); }, 0);
    var rPnl = all.reduce(function (s, p) { return s + _posNum(p.realized_pnl); }, 0);
    return UI.metricCard("Total Positions", String(all.length), String(open.length) + " open", "info") +
      UI.metricCard("Gross Exposure", _posMoney(exp.gross), "Long + Short", "info") +
      UI.metricCard("Net Exposure", _posMoney(exp.net), "Long − Short", exp.net >= 0 ? "pos" : "neg") +
      UI.metricCard("Unrealized P&L", _posSignedMoney(uPnl), "Realized " + _posSignedMoney(rPnl), uPnl >= 0 ? "pos" : "neg");
  }

  function renderPositionsFilters() {
    var symbolOpts = _positionsSymbolOptions().map(function (s) {
      return { value: s, label: s === "ALL" ? "All Symbols" : s };
    });
    var accountOpts = _positionsAccountOptions().map(function (a) {
      return { value: a, label: a === "ALL" ? "All Accounts" : a };
    });
    return (
      '<div class="pos-filters">' +
      '<div class="pos-filter-field"><label class="pos-filter-label">View</label>' +
      UI.select({ id: "pos-filter-visibility", options: [
        { value: "OPEN", label: "Open Positions" },
        { value: "ALL", label: "All Positions" },
        { value: "FLAT", label: "Flat Positions" },
      ] }) + '</div>' +
      '<div class="pos-filter-field"><label class="pos-filter-label">Account</label>' +
      UI.select({ id: "pos-filter-account", options: accountOpts }) + '</div>' +
      '<div class="pos-filter-field"><label class="pos-filter-label">Symbol</label>' +
      UI.select({ id: "pos-filter-symbol", options: symbolOpts }) + '</div>' +
      '<div class="pos-filter-field"><label class="pos-filter-label">Side</label>' +
      UI.select({ id: "pos-filter-side", options: [
        { value: "ALL", label: "All Sides" },
        { value: "LONG", label: "LONG" },
        { value: "SHORT", label: "SHORT" },
        { value: "FLAT", label: "FLAT" },
      ] }) + '</div>' +
      '</div>'
    );
  }

  function _renderPositionsRefreshAction() {
    return '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);">Total: <span id="pos-total">' +
      POSITIONS_PAYLOAD.positions.length + '</span> · Updated: <span class="ds-text-mono" id="pos-last-updated">' +
      _posEsc(POSITIONS_LAST_UPDATED) + '</span></span> ' +
      '<button class="btn btn-ghost btn-sm" data-action="pos:refresh" type="button">↻ Refresh</button>';
  }

  // ── Refresh + Detail loaders (async, fault-tolerant) ───────────
  function refreshPositionsUI() {
    var tbody = document.getElementById("pos-tbody");
    if (tbody) tbody.innerHTML = renderPositionsRows();
    var kpisEl = document.getElementById("pos-kpis");
    if (kpisEl) kpisEl.innerHTML = renderPositionsKPIs();
    var expBars = document.getElementById("pos-exp-bars");
    if (expBars) expBars.innerHTML = renderPositionExposureBars();
    var totalEl = document.getElementById("pos-total");
    if (totalEl) totalEl.textContent = String(POSITIONS_PAYLOAD.positions.length);
    var lastUpd = document.getElementById("pos-last-updated");
    if (lastUpd) lastUpd.textContent = POSITIONS_LAST_UPDATED;
    // Exposure summary cards
    var exp = _positionsExposure();
    var ge = document.getElementById("pos-exp-gross"); if (ge) ge.textContent = _posMoney(exp.gross);
    var ne = document.getElementById("pos-exp-net"); if (ne) ne.textContent = _posMoney(exp.net);
    var le = document.getElementById("pos-exp-long"); if (le) le.textContent = _posMoney(exp.long);
    var se = document.getElementById("pos-exp-short"); if (se) se.textContent = _posMoney(exp.short);
    var ce = document.getElementById("pos-exp-cash"); if (ce) ce.textContent = _posMoney(exp.cash);
  }

  async function loadPositionsAsync() {
    var refreshBtn = document.querySelector('[data-action="pos:refresh"]');
    if (refreshBtn) { refreshBtn.disabled = true; refreshBtn.textContent = "Refreshing…"; }
    try {
      POSITIONS_PAYLOAD = await usePositions();
      POSITIONS_LAST_UPDATED = new Date().toLocaleTimeString("en-US", { hour12: false });
      // Re-select if previously selected position is gone
      var stillExists = POSITIONS_PAYLOAD.positions.some(function (p) { return p.symbol === POSITIONS_SELECTED_SYMBOL; });
      if (!stillExists) {
        var open = POSITIONS_PAYLOAD.positions.filter(function (p) { return positionSideCanonical(p.side) !== "FLAT"; });
        POSITIONS_SELECTED_SYMBOL = (open[0] || POSITIONS_PAYLOAD.positions[0] || {}).symbol || null;
        POSITIONS_DETAIL = null;
        if (POSITIONS_SELECTED_SYMBOL) loadPositionDetailAsync(POSITIONS_SELECTED_SYMBOL);
        else {
          var d = document.getElementById("pos-detail");
          if (d) d.innerHTML = renderPositionDetail();
        }
      }
      refreshPositionsUI();
      showToast("Positions refreshed / 持仓已刷新", "ok");
    } catch (err) {
      showToast("Refresh failed / 刷新失败: " + (err && err.message ? err.message : String(err)), "err");
    } finally {
      if (refreshBtn) { refreshBtn.disabled = false; refreshBtn.textContent = "↻ Refresh"; }
    }
  }

  async function loadPositionDetailAsync(symbol) {
    var detailEl = document.getElementById("pos-detail");
    if (detailEl) detailEl.innerHTML = UI.stateLoading("Loading position…", "Fetching detail and ledger fill history.");
    try {
      POSITIONS_DETAIL = await usePositionDetail(symbol);
      if (detailEl) detailEl.innerHTML = renderPositionDetail();
    } catch (err) {
      if (err && err.status === 404) {
        POSITIONS_DETAIL = null;
        if (detailEl) detailEl.innerHTML = UI.empty("Position not found", "This position may have been closed or removed.");
      } else {
        if (detailEl) detailEl.innerHTML = UI.stateError(
          "Failed to load position detail",
          (err && err.message ? err.message : String(err)),
          "Retry", "pos:detail-retry"
        );
      }
    }
  }

  // ── Bind: delegated handlers on #pos-root (survive innerHTML) ──
  function bindPositionsPage() {
    var root = document.getElementById("pos-root");
    if (!root) return;
    // Lazy-load detail for pre-selected position
    if (POSITIONS_SELECTED_SYMBOL && !POSITIONS_DETAIL) loadPositionDetailAsync(POSITIONS_SELECTED_SYMBOL);

    // Single delegated click handler — catches pos:* buttons + rows
    root.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-action]");
      if (btn) {
        var action = btn.getAttribute("data-action");
        if (action === "pos:refresh") { loadPositionsAsync(); return; }
        if (action === "pos:detail-retry" && POSITIONS_SELECTED_SYMBOL) {
          loadPositionDetailAsync(POSITIONS_SELECTED_SYMBOL); return;
        }
        return;
      }
      // Row selection (delegated on tbody rows)
      var row = e.target.closest("tr[data-pos-symbol]");
      if (row) {
        var sym = row.getAttribute("data-pos-symbol");
        if (sym === POSITIONS_SELECTED_SYMBOL) return;
        POSITIONS_SELECTED_SYMBOL = sym;
        var tbody = document.getElementById("pos-tbody");
        if (tbody) tbody.querySelectorAll("tr").forEach(function (tr) { tr.classList.remove("pos-row-selected"); });
        row.classList.add("pos-row-selected");
        loadPositionDetailAsync(sym);
      }
    });

    // Filter selects
    function bindFilter(id, key) {
      var sel = document.getElementById(id);
      if (sel) sel.addEventListener("change", function () {
        POSITIONS_FILTERS[key] = sel.value;
        refreshPositionsUI();
      });
    }
    bindFilter("pos-filter-visibility", "visibility");
    bindFilter("pos-filter-side", "side");
    bindFilter("pos-filter-symbol", "symbol");
    bindFilter("pos-filter-account", "account");
  }

  PAGE_FRAMEWORK["trading/positions"] = async function () {
    // Initial load — throws on failure → render() catch → stateError + Retry
    POSITIONS_PAYLOAD = await usePositions();
    POSITIONS_LAST_UPDATED = new Date().toLocaleTimeString("en-US", { hour12: false });
    // ④ terminal-wide account context feeds the page filter
    POSITIONS_FILTERS = { account: APP_CTX.accountId, symbol: "ALL", side: "ALL", visibility: "OPEN" };
    POSITIONS_DETAIL = null;
    // Pre-select first open position (if any), else first position
    var exists = POSITIONS_PAYLOAD.positions.some(function (p) { return p.symbol === POSITIONS_SELECTED_SYMBOL; });
    if (!exists) {
      var open = POSITIONS_PAYLOAD.positions.filter(function (p) { return positionSideCanonical(p.side) !== "FLAT"; });
      POSITIONS_SELECTED_SYMBOL = (open[0] || POSITIONS_PAYLOAD.positions[0] || {}).symbol || null;
    }

    var exp = _positionsExposure();
    var expCards =
      UI.metricCard("Gross Exposure", _posMoney(exp.gross), "Long + Short", "info") +
      UI.metricCard("Net Exposure", _posMoney(exp.net), "Long − Short", exp.net >= 0 ? "pos" : "neg") +
      UI.metricCard("Long Exposure", _posMoney(exp.long), "", "pos") +
      UI.metricCard("Short Exposure", _posMoney(exp.short), "", "neg") +
      UI.metricCard("Cash", _posMoney(exp.cash), "", "info");

    // ── Two-column layout ──────────────────────────────────────────
    var layout =
      '<div class="pos-layout" id="pos-root">' +
      '<div class="pos-layout-main">' +
      UI.panel("Positions", renderPositionsTable(), {
        actions: _renderPositionsRefreshAction(),
      }) +
      '</div>' +
      '<div class="pos-layout-side">' +
      UI.panel("Position Detail", '<div id="pos-detail">' + renderPositionDetail() + '</div>') +
      '</div>' +
      '</div>';

    return (
      UI.pageHeader("Positions", "Position ledger, exposure and P&L · 持仓管理",
        UI.button("Refresh", "ghost", { sm: true, action: "pos:refresh" })) +
      '<div id="pos-kpis">' + UI.kpiGrid(renderPositionsKPIs(), 4) + '</div>' +
      UI.sectionHeading("Exposure") +
      '<div id="pos-exp-cards">' + UI.kpiGrid(expCards, 5) + '</div>' +
      UI.sectionHeading("Filters") +
      renderPositionsFilters() +
      UI.sectionHeading("Position Exposure") +
      UI.panel("Exposure by Symbol", '<div class="pos-exp" id="pos-exp-bars">' + renderPositionExposureBars() + '</div>') +
      UI.sectionHeading("Positions") +
      layout
    );
  };

  PAGE_FRAMEWORK["trading/trades"] = function () {
    return (
      UI.pageHeader("Executions", "Execution and trade history") +
      UI.kpiGrid(
        UI.metricCard("Total Trades", "38", "", "") +
        UI.metricCard("Volume", "$1.2M", "", "") +
        UI.metricCard("Avg Slippage", "+0.03bp", "", "pos") +
        UI.metricCard("Total Fees", "$18.91", "", "neg")
      ) +
      UI.sectionHeading("Recent Executions") +
      UI.panel("Executions", UI.table({
        columns: [
          { key: "id", label: "Exec ID", numeric: true },
          { key: "orderId", label: "Order ID", numeric: true },
          { key: "symbol", label: "Symbol" },
          { key: "side", label: "Side", color: function (v) { return v === "BUY" ? "pos" : "neg"; } },
          { key: "qty", label: "Filled Qty", numeric: true },
          { key: "price", label: "Fill Price", numeric: true, format: function (v) { return "$" + v.toFixed(2); } },
          { key: "fee", label: "Fee", numeric: true, format: function (v) { return "$" + v.toFixed(2); } },
          { key: "time", label: "Time" },
        ],
        rows: [
          { id: 5001, orderId: 1024, symbol: "NVDA", side: "BUY", qty: 100, price: 182.31, fee: 1.82, time: "10:23:41" },
          { id: 5002, orderId: 1024, symbol: "NVDA", side: "BUY", qty: 200, price: 182.45, fee: 3.65, time: "10:23:42" },
          { id: 5003, orderId: 1024, symbol: "NVDA", side: "BUY", qty: 300, price: 182.52, fee: 5.48, time: "10:23:43" },
          { id: 5004, orderId: 1023, symbol: "QQQ", side: "BUY", qty: 200, price: 571.20, fee: 5.71, time: "10:25:01" },
          { id: 5005, orderId: 1022, symbol: "AAPL", side: "SELL", qty: 100, price: 224.50, fee: 2.25, time: "10:26:15" },
        ],
      }))
    );
  };

  /* ==================================================================
   * Risk module — Integration 010 (real Risk API)
   * Risk Control Center: engine status → KPI table → exposure → limits
   * → risk events. Reads GET /dashboard/risk/center, which aggregates
   * the live pipeline (positions / orders / risk decisions / alerts),
   * the official Risk Engine limits and the UI-configured loss limits.
   * Read-only: does NOT modify the Risk Engine, strategy runtime,
   * order engine, position ledger, or risk rules.
   * ================================================================== */

  // ── Risk state (Integration 010) ──────────────────────────────
  var RK_STATE = {
    data: null,        // payload from GET /dashboard/risk/center
    error: null,       // message from the last failed load
  };

  // Load the Risk Control Center payload (cached until forced).
  async function rkLoadCenter(force) {
    if (RK_STATE.data && !force) return;
    var data = await api.riskCenter();
    RK_STATE.data = data;
    RK_STATE.error = null;
  }

  // Safe accessor: returns the cached payload or an empty skeleton so
  // renderers never crash when the API has not answered yet.
  function rkData() {
    return RK_STATE.data || {
      engine: { status: "—", last_update: "" },
      exposure: { long: 0, short: 0, gross: 0, net: 0, cash: 0, equity: 0,
                  unrealized_pnl: 0, margin_usage: 0, position_count: 0,
                  by_asset: [], by_side: [], by_strategy: [] },
      concentration: { hhi: 0, holdings: [] },
      kpi: [], limits: [],
      decisions: { total: 0, approved: 0, rejected: 0 },
      events: [],
    };
  }

  // Format a KPI row value by its backend-provided fmt hint.
  function rkFmtVal(k) {
    var v = k.value;
    if (k.fmt === "pct") return (v * 100).toFixed(2) + "%";
    if (k.fmt === "signedPct") return (v >= 0 ? "+" : "") + (v * 100).toFixed(2) + "%";
    if (k.fmt === "count") return String(v);
    return String(v); // text
  }

  // Event timestamps arrive as ISO strings (or "" for synthetic rows).
  function rkFmtTime(t) {
    if (!t) return "—";
    var d = new Date(t);
    if (isNaN(d.getTime())) return t;
    var p = function (n) { return (n < 10 ? "0" : "") + n; };
    return p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " +
      p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
  }

  // Muted empty-state line for panels with no rows (e.g. no pipeline).
  function rkEmpty(msg) {
    return '<div class="ds-text-muted" style="padding:var(--ds-space-3);font-size:var(--ds-text-sm);">' +
      esc(msg) + "</div>";
  }

  function rkStatusBadge(status) {
    var key = (status || "").toLowerCase();
    return '<span class="rk-status-badge rk-status-' + key + '">' + esc(status) + "</span>";
  }
  function rkLimitZone(pct) {
    if (pct >= 0.8) return "danger";
    if (pct >= 0.6) return "warn";
    return "safe";
  }
  function rkLimitStatus(pct) {
    if (pct >= 0.8) return "BREACH";
    if (pct >= 0.6) return "WATCH";
    return "NORMAL";
  }
  function rkLimitDisplay(limit) {
    var f = limit.fmt;
    if (f === "money") return "-$" + limit.current.toLocaleString() + " / -$" + limit.limit.toLocaleString();
    if (f === "pct") return "-" + limit.current.toFixed(1) + "% / -" + limit.limit.toFixed(1) + "%";
    if (f === "x") return limit.current.toFixed(2) + "x / " + limit.limit.toFixed(2) + "x";
    return limit.current + " / " + limit.limit.toLocaleString();
  }

  // ── Engine status bar ─────────────────────────────────────────
  function renderRkStatusBar() {
    var eng = rkData().engine;
    var status = eng.status || "—";
    var key = status.toLowerCase();
    return (
      '<div class="rk-status-bar">' +
      '<div class="rk-engine-status rk-engine-' + key + '">' +
      '<span class="rk-engine-dot"></span>' +
      '<span>Risk Engine: </span>' +
      '<span class="rk-engine-text ' + key + '">' + esc(status) + "</span>" +
      "</div>" +
      '<div class="rk-last-update">Last Update: ' + esc(rkFmtTime(eng.last_update)) + "</div>" +
      "</div>"
    );
  }

  // ── Overview KPI cards ────────────────────────────────────────
  function renderRkOverview() {
    var e = rkData().exposure;
    var eq = e.equity || 1;
    var pct = function (v) { return ((v / eq) * 100).toFixed(1) + "%"; };
    return UI.kpiGrid(
      UI.metricCard("Gross Exposure", UI.money(e.gross, 0), pct(e.gross), "info") +
      UI.metricCard("Net Exposure", UI.money(e.net, 0), pct(e.net), e.net >= 0 ? "info" : "neg") +
      UI.metricCard("Long Exposure", UI.money(e.long, 0), pct(e.long), "pos") +
      UI.metricCard("Short Exposure", UI.money(e.short, 0), pct(e.short), "neg") +
      UI.metricCard("Cash", UI.money(e.cash, 0), pct(e.cash), "")
    );
  }

  // ── KPI status table ──────────────────────────────────────────
  function renderRkKpiTable() {
    var kpi = rkData().kpi;
    if (!kpi.length) {
      return rkEmpty("No risk metrics yet — start a paper session to populate the KPI table. / 暂无风控指标，启动 Paper Session 后显示。");
    }
    var rows = kpi.map(function (k) {
      return "<tr>" +
        '<td class="rk-metric">' + esc(k.metric) + "</td>" +
        '<td class="rk-value">' + esc(rkFmtVal(k)) + "</td>" +
        "<td>" + rkStatusBadge(k.status) + "</td>" +
        "</tr>";
    }).join("");
    return (
      '<table class="ds-table rk-kpi-table">' +
      "<thead><tr><th>Metric</th><th style=\"text-align:right;\">Value</th><th>Status</th></tr></thead>" +
      "<tbody>" + rows + "</tbody>" +
      "</table>"
    );
  }

  // ── Exposure bars ─────────────────────────────────────────────
  function renderRkExposureBars(items, labelKey, expKey) {
    if (!items.length) {
      return rkEmpty("No exposure — no open positions. / 暂无敞口，当前无持仓。");
    }
    return items.map(function (it) {
      var side = it.side || "";
      var fillCls = side === "Short" ? "short" : side === "Long" ? "long" : "neutral";
      var w = (it.weight * 100).toFixed(1);
      var expVal = typeof it[expKey] === "number" ? UI.money(it[expKey], 0) : "—";
      return (
        '<div class="rk-exp-row">' +
        '<span class="rk-exp-label">' + esc(it[labelKey]) + (side && side !== "—" ? " · " + esc(side) : "") + "</span>" +
        '<div class="rk-exp-track"><div class="rk-exp-fill ' + fillCls + '" style="width:' + w + '%;"></div></div>' +
        '<span class="rk-exp-value">' + expVal + " · " + w + "%</span>" +
        "</div>"
      );
    }).join("");
  }

  // ── Limits with progress bars ─────────────────────────────────
  function renderRkLimits() {
    var limits = rkData().limits;
    if (!limits.length) {
      return rkEmpty("No limits loaded. / 未加载限额。");
    }
    return limits.map(function (l) {
      var pct = l.pct == null ? 0 : l.pct;
      var zone = rkLimitZone(pct);
      var status = rkLimitStatus(pct);
      var w = (pct * 100).toFixed(1);
      return (
        '<div class="rk-limit-row">' +
        '<div class="rk-limit-head">' +
        '<span class="rk-limit-label">' + esc(l.name) + "</span>" +
        '<span class="rk-limit-value">' + rkLimitDisplay(l) + " · " + w + "%</span>" +
        "</div>" +
        '<div class="rk-limit-track"><div class="rk-limit-fill ' + zone + '" style="width:' + w + '%;"></div></div>' +
        '<div class="rk-limit-foot"><span>0</span><span>' + rkStatusBadge(status) + "</span></div>" +
        "</div>"
      );
    }).join("");
  }

  // ── Risk events log ───────────────────────────────────────────
  function renderRkEvents() {
    var events = rkData().events;
    if (!events.length) {
      return rkEmpty("No risk events. / 暂无风控事件。");
    }
    return events.map(function (e) {
      var sevCls = "rk-sev-" + String(e.severity || "info").toLowerCase();
      return (
        '<div class="rk-event-item ' + sevCls + '">' +
        '<span class="rk-event-time">' + esc(rkFmtTime(e.time)) + "</span>" +
        '<span class="rk-sev-badge ' + sevCls + '">' + esc(e.severity) + "</span>" +
        '<span class="rk-event-detail"><strong>' + esc(e.title) + "</strong> · " + esc(e.detail) + "</span>" +
        "</div>"
      );
    }).join("");
  }

  function renderRkConcentration() {
    var c = rkData().concentration;
    var rows = (c.holdings || []).map(function (h) {
      return "<tr><td>" + esc(h.symbol) + "</td>" +
        '<td class="num">' + (h.weight * 100).toFixed(1) + "%</td></tr>";
    }).join("");
    return (
      '<table class="ds-table rk-kpi-table">' +
      "<thead><tr><th>Top Holding</th><th style=\"text-align:right;\">Weight</th></tr></thead>" +
      "<tbody>" + (rows || '<tr><td colspan="2" class="ds-text-muted">—</td></tr>') + "</tbody></table>" +
      '<div style="margin-top:var(--ds-space-3);display:flex;justify-content:space-between;align-items:center;">' +
      '<span class="ds-text-muted" style="font-size:var(--ds-text-xs);text-transform:uppercase;letter-spacing:var(--ds-tracking-wider);">HHI Concentration</span>' +
      '<span class="ds-num-font" style="font-weight:var(--ds-font-bold);font-family:var(--ds-num-font);">' + esc(String(c.hhi)) + "</span>" +
      "</div>"
    );
  }

  // ── Bindings (refresh button, event row detail) ───────────────
  function bindRiskPage() {
    var refreshBtn = document.querySelector('[data-action="rk:refresh"]');
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Refreshing…";
        rkLoadCenter(true).then(function () {
          return render();
        }).catch(function (err) {
          showToast("Failed to refresh risk data / 风控数据刷新失败: " +
            ((err && err.message) || err), "error");
        }).then(function () {
          refreshBtn.disabled = false;
          refreshBtn.textContent = "Refresh";
          showToast("Risk snapshot updated / 风控快照已更新", "ok");
        });
      });
    }
    var reportBtn = document.querySelector('[data-action="rk:report"]');
    if (reportBtn) {
      reportBtn.addEventListener("click", function () {
        showToast("Risk report — coming in UI V1 / 风控报告待后续 UI 版本", "info");
      });
    }
    document.querySelectorAll(".rk-event-item").forEach(function (el) {
      el.addEventListener("click", function () {
        var detail = el.querySelector(".rk-event-detail");
        showToast(detail ? detail.textContent : "Risk event", "info");
      });
    });
  }

  // ── Risk Control Center (Integration 010: real Risk API) ────────
  PAGE_FRAMEWORK["risk"] = async function () {
    await rkLoadCenter();
    var d = rkData();
    return (
      UI.pageHeader("Risk Control Center", "Risk monitoring, exposure, and limits · 风控中心",
        UI.button("Refresh", "ghost", { sm: true, action: "rk:refresh" }) +
        UI.button("Risk Report", "secondary", { sm: true, action: "rk:report" })) +
      renderRkStatusBar() +
      UI.sectionHeading("Risk Overview") +
      renderRkOverview() +
      UI.sectionHeading("Risk Metrics") +
      UI.panel("KPI Status", renderRkKpiTable()) +
      UI.sectionHeading("Exposure") +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--ds-space-4);">' +
      UI.panel("Asset Exposure", '<div class="rk-exp-list">' + renderRkExposureBars(d.exposure.by_asset, "symbol", "exposure") + "</div>") +
      UI.panel("Side Exposure", '<div class="rk-exp-list">' + renderRkExposureBars(d.exposure.by_side, "label", "exposure") + "</div>") +
      UI.panel("Strategy Exposure", '<div class="rk-exp-list">' + renderRkExposureBars(d.exposure.by_strategy, "label", "exposure") + "</div>") +
      UI.panel("Concentration", renderRkConcentration()) +
      "</div>" +
      UI.sectionHeading("Limits") +
      UI.panel("Risk Limits", '<div class="rk-limit-list">' + renderRkLimits() + "</div>") +
      UI.sectionHeading("Risk Events") +
      UI.panel("Event Log", '<div class="rk-event-list">' + renderRkEvents() + "</div>")
    );
  };

  // ── Exposure page (Integration 010: real Risk API) ────────────
  PAGE_FRAMEWORK["risk/exposure"] = async function () {
    await rkLoadCenter();
    var d = rkData();
    var e = d.exposure;
    var eq = e.equity || 1;
    var pct = function (v) { return ((v / eq) * 100).toFixed(1) + "%"; };
    return (
      UI.pageHeader("Exposure", "Exposure breakdown and analysis · 敞口分析",
        UI.button("Refresh", "ghost", { sm: true, action: "rk:refresh" })) +
      renderRkStatusBar() +
      UI.kpiGrid(
        UI.metricCard("Gross Exposure", UI.money(e.gross, 0), pct(e.gross), "info") +
        UI.metricCard("Net Exposure", UI.money(e.net, 0), pct(e.net), e.net >= 0 ? "info" : "neg") +
        UI.metricCard("Long Exposure", UI.money(e.long, 0), pct(e.long), "pos") +
        UI.metricCard("Short Exposure", UI.money(e.short, 0), pct(e.short), "neg")
      ) +
      UI.sectionHeading("By Asset") +
      UI.panel("Exposure Breakdown", UI.table({
        columns: [
          { key: "symbol", label: "Symbol" },
          { key: "exposure", label: "Exposure", numeric: true, format: function (v) { return UI.money(v); } },
          { key: "weight", label: "Weight", numeric: true, format: function (v) { return (v * 100).toFixed(1) + "%"; } },
          { key: "side", label: "Side" },
        ],
        rows: e.by_asset,
      })) +
      UI.sectionHeading("By Side") +
      UI.panel("Side Exposure", '<div class="rk-exp-list">' + renderRkExposureBars(e.by_side, "label", "exposure") + "</div>") +
      UI.sectionHeading("By Strategy") +
      UI.panel("Strategy Exposure", '<div class="rk-exp-list">' + renderRkExposureBars(e.by_strategy, "label", "exposure") + "</div>") +
      UI.sectionHeading("Concentration") +
      UI.panel("Top Holdings & HHI", renderRkConcentration())
    );
  };

  // ── Operations ───────────────────────────────────────────────────
  /* ==================================================================
   * Accounts module — Integration 012
   * Accounts Control Center: overview KPI → multi-account list →
   * account detail (balance / connection / capabilities) → market
   * breakdown → broker health. All data from
   * GET /dashboard/accounts/center; no mock data. Read-only.
   * ================================================================== */

  // ── Accounts state (Integration 012) ─────────────────────────
  var AC_STATE = {
    data: null,
    error: null,
    selectedId: null,
  };

  async function acLoadCenter(force) {
    if (AC_STATE.data && !force) return;
    try {
      var data = await api.accountsCenter();
      AC_STATE.data = data;
      AC_STATE.error = null;
      // default selection: first connected account, else first account
      if (!AC_STATE.selectedId && data.accounts && data.accounts.length) {
        var firstUp = data.accounts.find(function (a) { return a.connection === "CONNECTED"; });
        AC_STATE.selectedId = (firstUp || data.accounts[0]).account_id;
      }
    } catch (err) {
      // keep the full ApiError (kind=network drives the Offline state)
      AC_STATE.error = err || "Failed to load accounts data";
    }
  }

  function acData() {
    return AC_STATE.data || {
      overview: { total_equity: 0, available_cash: 0, gross_exposure: 0,
                  margin_used: 0, unrealized_pnl: 0, realized_pnl: 0, currency: "USD" },
      status: { total: 0, connected: 0, degraded: 0, offline: 0, last_update: "" },
      accounts: [],
      markets: [],
      brokers: [],
      health: [],
    };
  }

  function acMoney(amount, currency) {
    var n = Number(amount);
    if (!isFinite(n)) return "—";
    if (currency === "CNY") return "¥" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    return UI.money(n, 0);
  }

  function acConnBadge(status) {
    var key = String(status).toLowerCase();
    return '<span class="ac-conn-badge ac-conn-' + esc(key) + '">' + esc(status) + "</span>";
  }

  function acFind(id) {
    var list = acData().accounts || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].account_id === id) return list[i];
    }
    return list[0] || null;
  }

  // ── Overview KPI ──────────────────────────────────────────────
  function renderAcOverview() {
    var o = acData().overview;
    return UI.kpiGrid(
      UI.metricCard("Total Equity", UI.money(o.total_equity, 0), "", "") +
      UI.metricCard("Available Cash", UI.money(o.available_cash, 0), "", "") +
      UI.metricCard("Gross Exposure", UI.money(o.gross_exposure, 0), "", "info") +
      UI.metricCard("Margin Used", UI.money(o.margin_used, 0), "", "") +
      UI.metricCard("Unrealized P&L", UI.signedMoney(o.unrealized_pnl), "", o.unrealized_pnl >= 0 ? "pos" : "neg")
    , 5);
  }

  // ── Status summary bar ───────────────────────────────────────
  function renderAcStatusBar() {
    var s = acData().status;
    return '<div class="ac-status-bar">' +
      '<span class="ac-status-item">Total <b>' + s.total + "</b></span>" +
      '<span class="ac-status-item ac-status-connected">Connected <b>' + s.connected + "</b></span>" +
      '<span class="ac-status-item ac-status-degraded">Degraded <b>' + s.degraded + "</b></span>" +
      '<span class="ac-status-item ac-status-offline">Offline <b>' + s.offline + "</b></span>" +
      '<span class="ac-last-update">Last Update: ' + esc(s.last_update || "—") + "</span>" +
      "</div>";
  }

  // ── Account list (clickable rows) ────────────────────────────
  function renderAcRows() {
    return (acData().accounts || []).map(function (a) {
      var sel = a.account_id === AC_STATE.selectedId ? " ac-row-selected" : "";
      return (
        '<tr class="ac-row' + sel + '" data-ac-id="' + esc(a.account_id) + '">' +
        '<td class="ac-col-name">' + esc(a.name) + "</td>" +
        "<td>" + esc(a.type) + "</td>" +
        '<td class="num">' + esc(a.currency) + "</td>" +
        '<td class="num">' + acMoney(a.equity, a.currency) + "</td>" +
        "<td>" + acConnBadge(a.connection) + "</td>" +
        "</tr>"
      );
    }).join("");
  }

  function renderAcList() {
    var rows = acData().accounts || [];
    if (!rows.length) return UI.empty("No Accounts", "No accounts registered with the adapter layer.");
    return (
      '<table class="ds-table ac-list-table">' +
      "<thead><tr>" +
      "<th>Account</th><th>Type</th><th>Currency</th>" +
      '<th class="num">Equity</th><th>Status</th>' +
      "</tr></thead>" +
      '<tbody id="ac-list-tbody">' + renderAcRows() + "</tbody>" +
      "</table>"
    );
  }

  // ── Detail panel ──────────────────────────────────────────────
  function acDetailCell(label, value, cls) {
    return (
      '<div class="ac-detail-cell">' +
      '<div class="ac-detail-label">' + esc(label) + "</div>" +
      '<div class="ac-detail-value' + (cls ? " " + cls : "") + '">' + esc(value) + "</div>" +
      "</div>"
    );
  }

  function renderAcPerms(perms) {
    if (!perms) return '<div class="empty">No permissions reported</div>';
    var items = [
      { label: "Market Data", ok: perms.market_data },
      { label: "Trading", ok: perms.trading },
      { label: "Cancel Orders", ok: perms.cancel_order },
      { label: "Short Selling", ok: perms.short_selling },
    ];
    return items.map(function (p) {
      var cls = p.ok ? "ac-perm-yes" : "ac-perm-no";
      var icon = p.ok ? "✓" : "✕";
      return (
        '<div class="ac-perm-item ' + cls + '">' +
        '<span class="ac-perm-icon">' + icon + "</span>" +
        '<span class="ac-perm-label">' + esc(p.label) + "</span>" +
        "</div>"
      );
    }).join("");
  }

  function renderAcDetail() {
    var a = acFind(AC_STATE.selectedId);
    if (!a) return UI.empty("No Account Selected", "Select an account to see its details.");
    var marginPct = a.margin && a.equity ? (a.margin / a.equity * 100).toFixed(1) + "%" : "—";
    var connCls = a.connection === "CONNECTED" ? "pos" : (a.connection === "DISCONNECTED" ? "neg" : "");
    return (
      '<div class="ac-detail-grid">' +
      acDetailCell("Account ID", a.account_id) +
      acDetailCell("Broker", a.broker_name) +
      acDetailCell("Account Type", a.type) +
      acDetailCell("Market", a.market_label) +
      acDetailCell("Currency", a.currency) +
      acDetailCell("Trading Mode", a.trading_mode) +
      acDetailCell("Equity", acMoney(a.equity, a.currency)) +
      acDetailCell("Cash", acMoney(a.cash, a.currency)) +
      acDetailCell("Buying Power", acMoney(a.buying_power, a.currency)) +
      acDetailCell("Margin", acMoney(a.margin, a.currency)) +
      acDetailCell("Margin Used", marginPct) +
      acDetailCell("Daily P&L", UI.signedMoney(a.daily_pnl)) +
      acDetailCell("Total P&L", UI.signedMoney(a.total_pnl)) +
      acDetailCell("Drawdown", UI.signedMoney(a.drawdown)) +
      acDetailCell("Positions", String(a.positions)) +
      acDetailCell("Orders", String(a.orders)) +
      acDetailCell("Executions", String(a.executions)) +
      acDetailCell("Connection", a.connection, connCls) +
      "</div>" +
      UI.sectionHeading("Trading Permissions") +
      '<div class="ac-perm-list">' + renderAcPerms(a.permissions) + "</div>"
    );
  }

  function updateAcDetail() {
    var host = document.getElementById("ac-detail");
    if (host) host.innerHTML = renderAcDetail();
  }

  // ── Market breakdown ─────────────────────────────────────────
  function renderAcMarkets() {
    var rows = acData().markets || [];
    if (!rows.length) return UI.empty("No Markets", "No market breakdown available.");
    return UI.table({
      columns: [
        { key: "market_label", label: "Market" },
        { key: "currency", label: "Currency" },
        { key: "accounts", label: "Accounts", numeric: true },
        { key: "connected", label: "Connected", numeric: true },
        { key: "equity", label: "Equity (USD)", numeric: true, format: function (v) { return UI.money(v, 0); } },
      ],
      rows: rows,
    });
  }

  // ── Add account form body ────────────────────────────────────
  function renderAcFormBody() {
    return (
      '<div class="ac-form-grid">' +
      UI.field("Account Name", UI.input({ placeholder: "US Main Account" })) +
      '<div class="ac-form-row">' +
      UI.field("Account Type", UI.select({ options: ["US Stocks", "Futures", "Forex", "A-Share"] })) +
      UI.field("Broker", UI.select({ options: ["Interactive Brokers", "CQG", "XTS", "Simulation"] })) +
      "</div>" +
      UI.field("Account ID", UI.input({ type: "password", placeholder: "Account ID", value: "••••••••••••••" })) +
      '<div class="ac-form-row">' +
      UI.field("API Key", UI.input({ type: "password", placeholder: "API Key" })) +
      UI.field("API Secret", UI.input({ type: "password", placeholder: "API Secret" })) +
      "</div>" +
      '<div class="ds-field"><label class="ds-field-label">Environment</label>' +
      '<div class="ac-env-radios">' +
      '<label class="ac-env-radio"><input type="radio" name="ac-env" value="Paper"> Paper</label>' +
      '<label class="ac-env-radio"><input type="radio" name="ac-env" value="Live" checked> Live</label>' +
      "</div></div>" +
      '<div class="ac-secret-disclaimer">' +
      "⚠ Secrets are never stored in the browser, database, or Git. " +
      "Production secrets should be managed via Vault / Secret Manager / Environment Variables. " +
      "This form is UI-only — no real credentials are saved." +
      "</div>" +
      "</div>"
    );
  }

  // ── Bindings (refresh, row select, add account) ──────────────
  function bindAccountsPage() {
    var refreshBtn = document.querySelector('[data-action="ac:refresh"]');
    if (refreshBtn) {
      refreshBtn.addEventListener("click", async function () {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Refreshing…";
        await acLoadCenter(true);
        refreshBtn.disabled = false;
        refreshBtn.textContent = "Refresh";
        if (AC_STATE.error) {
          showToast("Accounts refresh failed: " + (AC_STATE.error.message || AC_STATE.error), "error");
        } else {
          var tbody = document.getElementById("ac-list-tbody");
          if (tbody) tbody.innerHTML = renderAcRows();
          var bar = document.querySelector(".ac-status-bar");
          if (bar) bar.outerHTML = renderAcStatusBar();
          updateAcDetail();
          showToast("Accounts snapshot updated · 执行快照已更新", "ok");
        }
      });
    }
    var tbody = document.getElementById("ac-list-tbody");
    if (tbody) {
      tbody.addEventListener("click", function (e) {
        var row = e.target.closest("tr[data-ac-id]");
        if (!row) return;
        AC_STATE.selectedId = row.getAttribute("data-ac-id");
        // ④ selecting an account here switches the terminal-wide context
        ctxSetAccount(AC_STATE.selectedId);
        tbody.innerHTML = renderAcRows();
        updateAcDetail();
      });
    }
    var addBtn = document.querySelector('[data-action="ac:add"]');
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        UI.openModal({
          title: "Add Account",
          body: renderAcFormBody(),
          footer:
            UI.button("Cancel", "ghost", { sm: true, action: "close-modal" }) +
            UI.button("Test Connection", "secondary", { sm: true, action: "ac:test" }) +
            UI.button("Save Account", "primary", { sm: true, action: "ac:save" }),
          onMount: function (backdrop) {
            var testBtn = backdrop.querySelector('[data-action="ac:test"]');
            if (testBtn) {
              testBtn.addEventListener("click", function () {
                testBtn.disabled = true;
                testBtn.textContent = "Testing…";
                setTimeout(function () {
                  testBtn.disabled = false;
                  testBtn.textContent = "Test Connection";
                  showToast("Connection test passed (UI only) / 连接测试通过", "ok");
                }, 1000);
              });
            }
            var saveBtn = backdrop.querySelector('[data-action="ac:save"]');
            if (saveBtn) {
              saveBtn.addEventListener("click", function () {
                UI.closeModal();
                showToast("Account saved (UI only) / 账户已保存 — secrets not stored", "ok");
              });
            }
          },
        });
      });
    }
  }

  // ── Accounts page (Integration 012) ──────────────────────────
  PAGE_FRAMEWORK["operations/accounts"] = async function () {
    await acLoadCenter();
    // ① unified API state (offline-aware)
    var stateBlock = apiStateBlock(AC_STATE);
    if (stateBlock) {
      return UI.pageHeader("Accounts", "Account & broker management · 多账户管理") +
        stateBlock;
    }
    return (
      UI.pageHeader("Accounts", "Account & broker management · 多账户管理",
        UI.button("Refresh", "ghost", { sm: true, action: "ac:refresh" }) +
        UI.button("Add Account", "primary", { sm: true, action: "ac:add" })) +
      renderAcStatusBar() +
      UI.sectionHeading("Account Overview") +
      renderAcOverview() +
      UI.sectionHeading("Connected Accounts") +
      UI.panel("Accounts", renderAcList()) +
      UI.sectionHeading("Account Details") +
      '<div id="ac-detail">' + renderAcDetail() + "</div>" +
      UI.sectionHeading("Market Breakdown") +
      UI.panel("Markets", renderAcMarkets())
    );
  };

  /* ==================================================================
   * Execution module — Integration 011
   * Execution Control Center: engine status → KPI → quality → order flow
   * → recent orders (with slippage / latency) → venues.
   * All data from GET /dashboard/execution/center; no mock data.
   * ================================================================== */

  // ── Execution state (Integration 011) ────────────────────────
  var EX_STATE = {
    data: null,
    error: null,
  };

  async function exLoadCenter(force) {
    if (EX_STATE.data && !force) return;
    try {
      var data = await api.executionCenter();
      EX_STATE.data = data;
      EX_STATE.error = null;
    } catch (err) {
      // keep the full ApiError (kind=network drives the Offline state)
      EX_STATE.error = err || "Failed to load execution data";
    }
  }

  function exData() {
    return EX_STATE.data || {
      engine: { status: "—", attached: false, engines: [], last_update: "" },
      kpi: { orders: 0, filled: 0, rejected: 0, errors: 0,
             fill_rate: 0, reject_rate: 0, error_rate: 0,
             avg_latency_ms: 0, avg_slippage_bps: 0, turnover: 0 },
      quality: [],
      flow: [],
      orders: [],
      venues: [],
    };
  }

  // ── Engine status bar ────────────────────────────────────────
  function renderExEngineBar() {
    var d = exData();
    var items = (d.engine.engines || []).map(function (e) {
      var st = String(e.status).toLowerCase();
      return '<div class="ex-engine-item ex-engine-' + st + '">' +
        '<span class="ex-engine-dot"></span>' +
        "<span>" + esc(e.name) + "</span>" +
        '<span class="ex-engine-label ' + st + '">' + esc(e.status) + "</span>" +
        "</div>";
    }).join("");
    return '<div class="ex-engine-bar">' + items +
      '<div class="ex-last-update">Last Update: ' + esc(d.engine.last_update || "—") + "</div>" +
      "</div>";
  }

  // ── Overview KPI ──────────────────────────────────────────────
  function renderExKpis() {
    var k = exData().kpi;
    return UI.kpiGrid(
      UI.metricCard("Orders", String(k.orders), "", "") +
      UI.metricCard("Filled", String(k.filled), "", "pos") +
      UI.metricCard("Fill Rate", (k.fill_rate * 100).toFixed(2) + "%", "", k.fill_rate >= 0.5 ? "pos" : "warning") +
      UI.metricCard("Reject Rate", (k.reject_rate * 100).toFixed(2) + "%", "", k.reject_rate > 0.2 ? "neg" : "") +
      UI.metricCard("Avg Slippage", k.avg_slippage_bps.toFixed(1) + " bps", "", "") +
      UI.metricCard("Avg Latency", k.avg_latency_ms.toFixed(0) + " ms", "", "")
    , 6);
  }

  // ── Execution quality bars ───────────────────────────────────
  function renderExQuality() {
    var rows = (exData().quality || []).map(function (q) {
      return '<div class="ex-q-row">' +
        '<span class="ex-q-label">' + esc(q.label) + "</span>" +
        '<div class="ex-q-track"><div class="ex-q-fill ' + q.cls + '" style="width:' + q.fill + '%;"></div></div>' +
        '<span class="ex-q-value">' + esc(q.value) + "</span>" +
        "</div>";
    }).join("");
    return '<div class="ex-q-list">' + rows + "</div>";
  }

  // ── Order flow grid ───────────────────────────────────────────
  function renderExFlow() {
    var cells = (exData().flow || []).map(function (f) {
      return '<div class="ex-flow-cell ex-flow-' + f.cls + '">' +
        '<span class="ex-flow-count">' + f.count + "</span>" +
        '<span class="ex-flow-label">' + esc(f.label) + "</span>" +
        "</div>";
    }).join("");
    return '<div class="ex-flow-grid">' + cells + "</div>";
  }

  // ── Recent orders table (Execution Orders) ───────────────────
  function renderExOrders() {
    var rows = exData().orders || [];
    if (!rows.length) return UI.empty("No Orders", "No orders in the current session.");
    return UI.table({
      columns: [
        { key: "order_id", label: "Order ID", format: function (v) { return '<span class="mono">' + esc(String(v).slice(0, 14)) + "</span>"; } },
        { key: "symbol", label: "Symbol" },
        { key: "side", label: "Side", format: function (v) {
          var cls = v === "BUY" ? "ex-tl-side-buy" : "ex-tl-side-sell";
          return '<span class="' + cls + '">' + esc(v) + "</span>";
        } },
        { key: "quantity", label: "Qty", numeric: true, format: function (v) { return fmtNum(v); } },
        { key: "order_type", label: "Type" },
        { key: "status", label: "Status", format: function (v) {
          var st = String(v).toLowerCase();
          return '<span class="ex-order-status ex-order-' + st + '">' + esc(v) + "</span>";
        } },
        { key: "submit_time", label: "Submit Time", format: function (v) { return v ? esc(fmtTime(v)) : "—"; } },
        { key: "fill_time", label: "Fill Time", format: function (v) { return v ? esc(fmtTime(v)) : "—"; } },
        { key: "fill_price", label: "Fill Price", numeric: true, format: function (v) { return v != null ? fmtNum(v) : "—"; } },
        { key: "slippage_bps", label: "Slippage", numeric: true, format: function (v) { return v != null ? v.toFixed(1) + " bps" : "—"; } },
        { key: "latency_ms", label: "Latency", numeric: true, format: function (v) { return v != null ? v.toFixed(0) + " ms" : "—"; } },
      ],
      rows: rows,
    });
  }

  // ── Venues & accounts ─────────────────────────────────────────
  function renderExVenues() {
    var venues = exData().venues || [];
    if (!venues.length) return UI.empty("No Venues", "No venue activity yet.");
    return UI.table({
      columns: [
        { key: "venue", label: "Venue" },
        { key: "account", label: "Account" },
        { key: "execs", label: "Executions", numeric: true },
        { key: "fillRate", label: "Fill Rate", numeric: true },
        { key: "latency", label: "Latency", numeric: true },
        { key: "status", label: "Status", format: function (v) {
          var st = String(v).toLowerCase();
          var color = st === "online" ? "var(--ds-profit)" : (st === "idle" ? "var(--ds-text-muted)" : "var(--ds-loss)");
          return '<span style="color:' + color + ';font-weight:var(--ds-font-bold);font-family:var(--ds-num-font);font-size:var(--ds-text-xs);">' + esc(v) + "</span>";
        } },
      ],
      rows: venues,
    });
  }

  // ── Bindings (refresh) ───────────────────────────────────────
  function bindExecutionPage() {
    var refreshBtn = document.querySelector('[data-action="ex:refresh"]');
    if (refreshBtn) {
      refreshBtn.addEventListener("click", async function () {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Refreshing…";
        await exLoadCenter(true);
        refreshBtn.disabled = false;
        refreshBtn.textContent = "Refresh";
        if (EX_STATE.error) {
          showToast("Execution refresh failed: " + (EX_STATE.error.message || EX_STATE.error), "error");
        } else {
          var d = exData();
          var k = d.kpi;
          var bar = document.querySelector(".ex-engine-bar");
          if (bar) bar.outerHTML = renderExEngineBar();
          showToast("Execution snapshot updated · {0} orders / {1} filled / 执行快照已更新".replace("{0}", k.orders).replace("{1}", k.filled), "ok");
        }
      });
    }
  }

  // ── Execution Control Center (Integration 011) ───────────────
  PAGE_FRAMEWORK["operations/execution"] = async function () {
    await exLoadCenter();
    // ① unified API state (offline-aware)
    var stateBlock = apiStateBlock(EX_STATE);
    if (stateBlock) {
      return UI.pageHeader("Execution Control Center", "Execution quality, order flow, and lifecycle · 执行控制中心") +
        stateBlock;
    }
    return (
      UI.pageHeader("Execution Control Center", "Execution quality, order flow, and lifecycle · 执行控制中心",
        UI.button("Refresh", "ghost", { sm: true, action: "ex:refresh" })) +
      renderExEngineBar() +
      UI.sectionHeading("Execution Overview") +
      renderExKpis() +
      UI.sectionHeading("Execution Quality") +
      UI.panel("Quality Metrics", renderExQuality()) +
      UI.sectionHeading("Order Flow") +
      UI.panel("Order Status", renderExFlow()) +
      UI.sectionHeading("Execution Orders") +
      UI.panel("Recent Orders", renderExOrders()) +
      UI.sectionHeading("Venues & Accounts") +
      UI.panel("Execution Venues", renderExVenues())
    );
  };

  PAGE_FRAMEWORK["operations/reconciliation"] = function () {
    return (
      UI.pageHeader("Reconciliation", "Position and balance reconciliation") +
      UI.kpiGrid(
        UI.metricCard("Matched", "42", "100%", "pos") +
        UI.metricCard("Mismatched", "0", "", "pos") +
        UI.metricCard("Pending", "3", "", "warning") +
        UI.metricCard("Last Run", "2 min ago", "", "")
      ) +
      UI.sectionHeading("Reconciliation Status") +
      UI.panel("Account Reconciliation", UI.table({
        columns: [
          { key: "account", label: "Account" },
          { key: "internal", label: "Internal Positions", numeric: true },
          { key: "broker", label: "Broker Positions", numeric: true },
          { key: "diff", label: "Diff", numeric: true },
          { key: "status", label: "Status" },
        ],
        rows: [
          { account: "Paper-Alpha021", internal: 3, broker: 3, diff: 0, status: "Matched" },
          { account: "Paper-Momentum", internal: 2, broker: 2, diff: 0, status: "Matched" },
          { account: "Live-US-Equity", internal: 5, broker: 4, diff: -1, status: "Mismatch" },
        ],
      }))
    );
  };

  // ── System (Monitoring) + Settings ────────────────────────────

  /* ==================================================================
   * Monitoring module — Integration 014
   * System Monitoring & Observability Center: overview → services →
   * trading runtime → metrics → infrastructure → events.
   * Every number comes from GET /dashboard/monitoring/center — a
   * read-only aggregation of the existing HealthRegistry +
   * TradingPipeline state. No Prometheus metrics, no alert rules
   * (that is 015 Alerts), no engine edits.
   * ================================================================== */

  // ── Monitoring state (Integration 014) ────────────────────────
  var MO_STATE = { data: null, error: null, selectedId: null, eventFilter: "ALL" };

  async function monLoadCenter(force) {
    if (MO_STATE.data && !force) return;
    try {
      var data = await api.monitoringCenter();
      MO_STATE.data = data;
      MO_STATE.error = null;
      if (!MO_STATE.selectedId && data.services && data.services.length) {
        MO_STATE.selectedId = data.services[0].id;
      }
    } catch (err) {
      // keep the full ApiError (kind=network drives the Offline state)
      MO_STATE.error = err || "Failed to load monitoring center";
    }
  }

  function monData() {
    return MO_STATE.data || {
      overview: { status: "—", services_up: 0, services_down: 0,
                  services_unknown: 0, services_total: 0, version: "",
                  app: "", checked_at: null, pipeline_attached: false },
      services: [],
      trading: { strategies: 0, strategy_ids: [], active_orders: 0,
                 open_positions: 0, paper_accounts: 0, execution_queue: 0,
                 events: 0, pipeline_attached: false, attached_at: null },
      metrics: { orders: 0, executions: 0, fill_rate: 0, reject_rate: 0,
                 risk_decisions: 0, risk_rejected: 0, today_pnl: 0,
                 equity: 0, exposure: 0 },
      alpha: null,
      events: [],
      infra: { available: false },
    };
  }

  // ── Helpers ──────────────────────────────────────────────────
  function moSvcFind(id) {
    var svc = monData().services || [];
    for (var i = 0; i < svc.length; i++) {
      if (svc[i].id === id) return svc[i];
    }
    return svc[0] || null;
  }
  function moSvcBadge(status) {
    var cls = status === "UP" ? "running" : (status === "DOWN" ? "down" : "degraded");
    return '<span class="mo-svc-status mo-svc-' + cls + '">' + esc(status) + "</span>";
  }
  function moInfraBadge(status) {
    var cls = status === "NORMAL" ? "running" : "degraded";
    return '<span class="mo-svc-status mo-svc-' + cls + '">' + esc(status) + "</span>";
  }
  function moFmtClock(ts) {
    if (!ts) return "—";
    var d = new Date(ts);
    if (isNaN(d.getTime())) return String(ts);
    function p2(n) { return (n < 10 ? "0" : "") + n; }
    return p2(d.getHours()) + ":" + p2(d.getMinutes()) + ":" + p2(d.getSeconds());
  }
  function moHeartbeatAge(epoch) {
    if (!epoch) return "—";
    var age = Math.max(0, Math.round(Date.now() / 1000 - epoch));
    if (age < 60) return age + " sec ago";
    if (age < 3600) return Math.round(age / 60) + " min ago";
    return Math.round(age / 3600) + " h ago";
  }
  function moPct(x) {
    var v = Number(x);
    if (isNaN(v)) return "0.0%";
    return (v * 100).toFixed(1) + "%";
  }

  // ── System health bar ─────────────────────────────────────────
  function renderMoHealthBar() {
    var h = monData().overview;
    var statusCls = h.status === "READY" ? "operational" : (h.status === "DEGRADED" ? "degraded" : "down");
    return (
      '<div class="mo-health-bar">' +
      '<div>' +
      '<div class="mo-health-main">' +
      '<div class="mo-health-status mo-health-' + statusCls + '">' + esc(h.status) + "</div>" +
      "</div>" +
      '<div class="mo-health-meta">' +
      "<span>Services <b>" + h.services_up + " / " + h.services_total + "</b></span>" +
      "<span>Critical <b>" + h.services_down + "</b></span>" +
      "<span>Warning <b>" + h.services_unknown + "</b></span>" +
      "<span>Pipeline <b>" + (h.pipeline_attached ? "Attached" : "Detached") + "</b></span>" +
      "</div>" +
      "</div>" +
      '<div class="mo-health-right">' +
      '<div class="mo-health-check">Version <b>' + esc(h.version || "—") + "</b></div>" +
      '<div class="mo-health-check">Last Check <b>' + esc(moHeartbeatAge(h.checked_at)) + "</b></div>" +
      "</div>" +
      "</div>"
    );
  }

  // ── Service table ─────────────────────────────────────────────
  function renderMoSvcRows() {
    return (monData().services || []).map(function (s) {
      var sel = s.id === MO_STATE.selectedId ? " mo-svc-row-selected" : "";
      return (
        '<tr class="mo-svc-row' + sel + '" data-mo-id="' + esc(s.id) + '">' +
        '<td style="font-family:var(--ds-num-font);font-weight:var(--ds-font-semibold);">' + esc(s.name) + "</td>" +
        "<td>" + moSvcBadge(s.status) + "</td>" +
        '<td class="num">' + (s.latency_ms == null ? "—" : s.latency_ms + " ms") + "</td>" +
        '<td class="num">' + esc(moHeartbeatAge(s.last_heartbeat)) + "</td>" +
        "</tr>"
      );
    }).join("");
  }
  function renderMoSvcTable() {
    return (
      '<table class="ds-table mo-svc-table">' +
      "<thead><tr>" +
      "<th>Service</th><th>Status</th>" +
      '<th class="num">Latency</th><th class="num">Heartbeat</th>' +
      "</tr></thead>" +
      '<tbody id="mo-svc-tbody">' + renderMoSvcRows() + "</tbody>" +
      "</table>"
    );
  }

  // ── Service detail ────────────────────────────────────────────
  function renderMoSvcDetail() {
    var s = moSvcFind(MO_STATE.selectedId);
    function cell(lbl, val) {
      return '<div class="mo-svc-detail-cell"><div class="mo-svc-detail-label">' + esc(lbl) + '</div><div class="mo-svc-detail-value">' + esc(val) + "</div></div>";
    }
    if (!s) {
      return '<div class="empty" style="padding:var(--ds-space-4);">No services registered / 暂无服务</div>';
    }
    return (
      '<div class="mo-svc-detail">' +
      cell("Service", s.name) +
      cell("Status", s.status) +
      cell("Version", s.version || "—") +
      cell("Uptime (pipeline)", s.uptime ? moFmtClock(s.uptime) : "—") +
      cell("Latency", s.latency_ms == null ? "—" : s.latency_ms + " ms") +
      cell("Heartbeat", moHeartbeatAge(s.last_heartbeat)) +
      cell("Detail", s.detail || "—") +
      cell("", "") +
      "</div>"
    );
  }
  function updateMoSvcDetail() {
    var host = document.getElementById("mo-svc-detail");
    if (host) host.innerHTML = renderMoSvcDetail();
  }

  // ── Infrastructure cards ──────────────────────────────────────
  function renderMoInfra() {
    var infra = monData().infra || {};
    if (!infra.available) {
      return '<div class="empty" style="padding:var(--ds-space-4);">Host metrics unavailable (psutil not installed) / 主机指标不可用</div>';
    }
    var items = [
      { name: "CPU",    m: infra.cpu },
      { name: "Memory", m: infra.memory },
      { name: "Disk",   m: infra.disk },
    ];
    var cards = items.filter(function (it) { return it.m; }).map(function (it) {
      return (
        '<div class="mo-infra-card">' +
        '<div class="mo-infra-top">' +
        '<span class="mo-infra-name">' + esc(it.name) + "</span>" +
        moInfraBadge(it.m.status) +
        "</div>" +
        '<div class="mo-infra-value">' + esc(it.m.value) + "</div>" +
        "</div>"
      );
    }).join("");
    return '<div class="mo-infra-row">' + cards + "</div>";
  }

  // ── Trading runtime cards ─────────────────────────────────────
  function renderMoTrade() {
    var t = monData().trading;
    var ids = (t.strategy_ids || []).join(", ");
    var cards = [
      { label: "Strategies",     value: t.strategies,     sub: ids || "—" },
      { label: "Active Orders",  value: t.active_orders,  sub: "" },
      { label: "Open Positions", value: t.open_positions, sub: "" },
      { label: "Paper Accounts", value: t.paper_accounts, sub: t.pipeline_attached ? "pipeline attached" : "detached" },
      { label: "Execution Queue", value: t.execution_queue, sub: "" },
      { label: "Event Bus",      value: t.events,         sub: "total events" },
    ].map(function (c) {
      return (
        '<div class="mo-trade-card">' +
        '<span class="mo-trade-label">' + esc(c.label) + "</span>" +
        '<span class="mo-trade-value">' + esc(String(c.value)) + "</span>" +
        (c.sub ? '<span class="mo-trade-sub">' + esc(c.sub) + "</span>" : "") +
        "</div>"
      );
    }).join("");
    return '<div class="mo-trade-grid">' + cards + "</div>";
  }

  // ── Execution / risk metrics cards ─────────────────────────────
  function renderMoMetrics() {
    var m = monData().metrics;
    var cards = [
      { label: "Orders",         value: m.orders,         sub: "" },
      { label: "Executions",     value: m.executions,     sub: "" },
      { label: "Fill Rate",      value: moPct(m.fill_rate),   sub: "" },
      { label: "Reject Rate",    value: moPct(m.reject_rate), sub: "", neg: m.reject_rate > 0 },
      { label: "Risk Decisions", value: m.risk_decisions, sub: "" },
      { label: "Risk Rejected",  value: m.risk_rejected,  sub: "", neg: m.risk_rejected > 0 },
    ].map(function (c) {
      var valCls = c.neg ? " style='color:var(--ds-loss);'" : "";
      return (
        '<div class="mo-trade-card">' +
        '<span class="mo-trade-label">' + esc(c.label) + "</span>" +
        '<span class="mo-trade-value"' + valCls + ">" + esc(String(c.value)) + "</span>" +
        (c.sub ? '<span class="mo-trade-sub">' + esc(c.sub) + "</span>" : "") +
        "</div>"
      );
    }).join("");
    return '<div class="mo-trade-grid">' + cards + "</div>";
  }

  // ── Alpha021 paper trading KPI cards ──────────────────────────
  function renderMoAlpha() {
    var a = monData().alpha;
    if (!a) {
      return '<div class="empty" style="padding:var(--ds-space-4);">Alpha021 paper data unavailable (sync data/real/d1) / 回放数据不可用</div>';
    }
    var cards = [
      { label: "Signals", value: a.signals, sub: a.alpha_id || "" },
      { label: "Fills",    value: a.fills,   sub: "" },
      { label: "Rejects",  value: a.rejects, sub: "", neg: a.rejects > 0 },
      { label: "Errors",   value: a.errors,  sub: "", neg: a.errors > 0 },
      { label: "Win Rate", value: (Number(a.win_rate) || 0).toFixed(1) + "%", sub: "" },
      { label: "Return",   value: (Number(a.return_pct) || 0).toFixed(2) + "%", sub: "", neg: Number(a.return_pct) < 0 },
    ].map(function (c) {
      var valCls = c.neg ? " style='color:var(--ds-loss);'" : "";
      return (
        '<div class="mo-trade-card">' +
        '<span class="mo-trade-label">' + esc(c.label) + "</span>" +
        '<span class="mo-trade-value"' + valCls + ">" + esc(String(c.value)) + "</span>" +
        (c.sub ? '<span class="mo-trade-sub">' + esc(c.sub) + "</span>" : "") +
        "</div>"
      );
    }).join("");
    return '<div class="mo-trade-grid">' + cards + "</div>";
  }

  // ── Events list (with filter) ──────────────────────────────────
  function moFilteredEvents() {
    var evts = monData().events || [];
    if (MO_STATE.eventFilter === "ALL") return evts;
    return evts.filter(function (e) { return e.severity === MO_STATE.eventFilter; });
  }
  function renderMoEventFilter() {
    var filters = ["ALL", "ERROR", "WARNING", "INFO"];
    return (
      '<div class="mo-event-filter">' +
      filters.map(function (f) {
        var cls = f === MO_STATE.eventFilter ? " mo-event-filter-btn active" : " mo-event-filter-btn";
        return '<button class="' + cls + '" data-mo-filter="' + esc(f) + '">' + esc(f) + "</button>";
      }).join("") +
      "</div>"
    );
  }
  function renderMoEvents() {
    var list = moFilteredEvents().map(function (e) {
      return (
        '<div class="mo-event-item">' +
        '<span class="mo-event-time">' + esc(moFmtClock(e.timestamp)) + "</span>" +
        '<span class="mo-event-sev ' + esc(e.severity) + '">' + esc(e.severity) + "</span>" +
        '<span class="mo-event-text">' + esc("[" + (e.source || "system") + "] " + (e.text || "")) + "</span>" +
        "</div>"
      );
    }).join("");
    if (list === "") list = '<div class="empty" style="padding:var(--ds-space-4);">No events in this filter / 无相关事件</div>';
    return renderMoEventFilter() + '<div class="mo-event-list" id="mo-event-list">' + list + "</div>";
  }
  function updateMoEvents() {
    var host = document.getElementById("mo-event-host");
    if (host) host.innerHTML = renderMoEvents();
    bindMoEventFilter();
  }
  function bindMoEventFilter() {
    var btns = document.querySelectorAll("[data-mo-filter]");
    btns.forEach(function (b) {
      b.addEventListener("click", function () {
        MO_STATE.eventFilter = b.getAttribute("data-mo-filter");
        updateMoEvents();
      });
    });
  }

  // ── Bindings ──────────────────────────────────────────────────
  function bindMonitoringPage() {
    // Service row click → update detail panel
    var tbody = document.getElementById("mo-svc-tbody");
    if (tbody) {
      tbody.addEventListener("click", function (e) {
        var row = e.target.closest("tr[data-mo-id]");
        if (!row) return;
        MO_STATE.selectedId = row.getAttribute("data-mo-id");
        tbody.innerHTML = renderMoSvcRows();
        updateMoSvcDetail();
      });
    }
    bindMoEventFilter();
    var refresh = document.getElementById("mo-refresh");
    if (refresh) {
      refresh.addEventListener("click", function () {
        monLoadCenter(true).then(function () { renderMonPageInto(); });
      });
    }
    // ③ live page: opt-in visibility-aware auto-refresh (30s)
    bindAutoRefresh("monitoring", "mo-auto", function () {
      monLoadCenter(true).then(function () { renderMonPageInto(); });
    });
  }

  function renderMonPageInto() {
    var host = document.getElementById("mo-page");
    if (!host) return;
    host.innerHTML = renderMonPage();
    bindMonitoringPage();
  }

  function renderMonPage() {
    // ① unified API state (offline-aware) replaces the page-local error div
    var stateBlock = apiStateBlock(MO_STATE);
    if (stateBlock) {
      return UI.pageHeader("Monitoring", "System monitoring & observability center · 系统监控中心") +
        '<div id="mo-page-state">' + stateBlock + "</div>";
    }
    var o = monData().overview;
    return (
      UI.pageHeader("Monitoring", "System monitoring & observability center · 系统监控中心") +
      '<div class="ds-toolbar">' +
        '<button id="mo-refresh" class="btn btn-secondary btn-sm">Refresh</button>' +
        '<button id="mo-auto" class="btn btn-secondary btn-sm">Auto 30s</button>' +
        '<span class="ds-toolbar-meta">Last check: ' + esc(moHeartbeatAge(o.checked_at)) + "</span>" +
      "</div>" +
      UI.sectionHeading("System Health") +
      renderMoHealthBar() +
      UI.sectionHeading("Service Status") +
      UI.panel(o.services_total + " Services", renderMoSvcTable()) +
      UI.sectionHeading("Service Details") +
      '<div id="mo-svc-detail">' + renderMoSvcDetail() + "</div>" +
      UI.sectionHeading("Trading Runtime") +
      UI.panel("What the trading system is doing now", renderMoTrade()) +
      UI.sectionHeading("Execution Metrics") +
      UI.panel("Orders · Fills · Rejects · Risk", renderMoMetrics()) +
      UI.sectionHeading("Alpha021 Paper Trading") +
      UI.panel("Observation stage", renderMoAlpha()) +
      UI.sectionHeading("Infrastructure") +
      UI.panel("CPU / Memory / Disk", renderMoInfra()) +
      UI.sectionHeading("System Events") +
      UI.panel("Event Log", '<div id="mo-event-host">' + renderMoEvents() + "</div>")
    );
  }

  // ── Monitoring page (Integration 014) — async hydrate ─────────
  PAGE_FRAMEWORK["system"] = function () {
    // (re)load when missing data or after a retry cleared a previous error
    if (!MO_STATE.data || MO_STATE.error) {
      monLoadCenter().then(function () { renderMonPageInto(); });
    }
    return (
      '<div id="mo-page">' +
      (UI.pageHeader("Monitoring", "System monitoring & observability center · 系统监控中心") +
       '<div class="ds-loading">Loading monitoring center…</div>') +
      "</div>"
    );
  };


  /* ==================================================================
   * Alerts module — Integration 015 (Alerts API)
   * Unified Alert Center: overview → sources → table → detail.
   * Connected to GET /api/dashboard/alerts/center — a read-only view
   * over the existing runtime.alerts() capability (reconciliation,
   * position limit, service health, risk rejections). Each alert row
   * carries current/threshold context plus the related signal → risk
   * → order event chain explaining WHY it fired.
   * Acknowledge / Resolve are UI-session state only — the runtime has
   * no alert store and 015 does not add one (no new alert rules).
   * ================================================================== */

  // ── Alerts state (Integration 015) ────────────────────────────
  var AL_STATE = {
    data: null, error: null, selectedId: null,
    sevFilter: "ALL", statusFilter: "ALL", sourceFilter: "ALL",
    acked: {}, resolved: {},           // session-local Ack/Resolve state
  };

  async function alLoadCenter(force) {
    if (AL_STATE.data && !force) return;
    try {
      var data = await api.alertsCenter();
      AL_STATE.data = data;
      AL_STATE.error = null;
      if (!AL_STATE.selectedId && data.alerts && data.alerts.length) {
        AL_STATE.selectedId = data.alerts[0].id;
      }
    } catch (err) {
      // keep the full ApiError (kind=network drives the Offline state)
      AL_STATE.error = err || "Failed to load alert center";
    }
  }

  function alData() {
    return AL_STATE.data || {
      overview: { active: 0, critical: 0, warning: 0, info: 0,
                  pipeline_attached: false, generated_at: null },
      sources: [],
      filters: { severities: [], sources: [] },
      alerts: [],
    };
  }

  function alFind(id) {
    var rows = alData().alerts || [];
    for (var i = 0; i < rows.length; i++) if (rows[i].id === id) return rows[i];
    return rows[0] || null;
  }

  // UI-session status: TRIGGERED → ACKNOWLEDGED → RESOLVED
  function alStatus(a) {
    if (a && AL_STATE.resolved[a.id]) return "RESOLVED";
    if (a && AL_STATE.acked[a.id]) return "ACKNOWLEDGED";
    return a ? (a.status || "TRIGGERED") : "TRIGGERED";
  }

  function alCounts() {
    var c = { active: 0, critical: 0, warning: 0, info: 0, acked: 0 };
    (alData().alerts || []).forEach(function (a) {
      var st = alStatus(a);
      if (st === "RESOLVED") return;
      c.active++;
      if (a.severity === "CRITICAL") c.critical++;
      else if (a.severity === "WARNING") c.warning++;
      else c.info++;
      if (st === "ACKNOWLEDGED") c.acked++;
    });
    return c;
  }


  // ── Overview KPI row (live counts; Ack/Resolve update in-session) ──
  function renderAlOverview() {
    var c = alCounts();
    var o = alData().overview || {};
    var cards = [
      { cls: "active",   label: "Active Alerts", value: c.active,
        delta: o.pipeline_attached ? "pipeline attached" : "no pipeline" },
      { cls: "critical", label: "Critical",      value: c.critical, delta: "open / not resolved" },
      { cls: "warning",  label: "Warning",       value: c.warning,  delta: "open / not resolved" },
      { cls: "info",     label: "Info",          value: c.info,     delta: "open / not resolved" },
      { cls: "ack",      label: "Acknowledged",  value: c.acked,    delta: "this session" },
    ];
    return (
      '<div class="al-overview" id="al-overview">' +
      cards.map(function (k) {
        return (
          '<div class="al-kpi ' + esc(k.cls) + '">' +
          '<div class="al-kpi-label">' + esc(k.label) + "</div>" +
          '<div class="al-kpi-value">' + String(k.value) + "</div>" +
          '<div class="al-kpi-delta">' + esc(k.delta) + "</div>" +
          "</div>"
        );
      }).join("") +
      "</div>"
    );
  }

  // ── Alert capability sources (existing runtime.alerts() origins) ──
  function renderAlSources() {
    var srcs = alData().sources || [];
    if (!srcs.length) {
      return '<div class="empty" style="padding:var(--ds-space-4);">No alert sources / 无告警来源</div>';
    }
    return (
      '<div class="al-rules">' +
      srcs.map(function (r) {
        return (
          '<div class="al-rule">' +
          '<div class="al-rule-body">' +
          '<span class="al-rule-name">' + esc(r.name) + "</span>" +
          '<span class="al-rule-sub">' + esc(r.sub) + " · " + r.triggered + " triggered</span>" +
          "</div>" +
          '<span class="al-rule-state on">● LIVE</span>' +
          "</div>"
        );
      }).join("") +
      "</div>"
    );
  }

  // ── Alert table (filters: severity / status / source) ───────────
  function alFilteredRows() {
    var rows = alData().alerts || [];
    var sev = AL_STATE.sevFilter, st = AL_STATE.statusFilter, src = AL_STATE.sourceFilter;
    return rows.filter(function (a) {
      if (sev !== "ALL" && a.severity !== sev) return false;
      if (st !== "ALL" && alStatus(a) !== st) return false;
      if (src !== "ALL" && a.source !== src) return false;
      return true;
    });
  }

  function alFilterBtn(group, value, label) {
    var cur = AL_STATE[group];
    var cls = cur === value ? "mo-event-filter-btn active" : "mo-event-filter-btn";
    return '<button class="' + cls + '" data-al-filter-group="' + esc(group) +
           '" data-al-filter="' + esc(value) + '">' + esc(label) + "</button>";
  }

  function renderAlFilters() {
    var srcs = (alData().filters || {}).sources || [];
    function group(label, key, values) {
      return (
        '<span style="font-size:var(--ds-text-xs);color:var(--ds-text-muted);align-self:center;margin-right:2px;">' +
        esc(label) + "</span>" +
        values.map(function (v) {
          return alFilterBtn(key, v, v === "ALL" ? "All" : v);
        }).join("")
      );
    }
    return (
      '<div class="mo-event-filter" style="flex-wrap:wrap;">' +
      group("Severity", "sevFilter", ["ALL", "CRITICAL", "WARNING", "INFO"]) +
      '<span style="width:12px;"></span>' +
      group("Status", "statusFilter", ["ALL", "TRIGGERED", "ACKNOWLEDGED", "RESOLVED"]) +
      '<span style="width:12px;"></span>' +
      group("Source", "sourceFilter", ["ALL"].concat(srcs)) +
      "</div>"
    );
  }

  function renderAlRows() {
    var rows = alFilteredRows();
    if (!rows.length) {
      return (
        '<tr><td colspan="9"><div class="empty" style="padding:var(--ds-space-4);">' +
        "No alerts in this filter / 当前过滤条件下无告警</div></td></tr>"
      );
    }
    return rows.map(function (a) {
      var sel = a.id === AL_STATE.selectedId ? " al-row-selected" : "";
      var st = alStatus(a);
      var showAck = st === "TRIGGERED";
      var showRes = st !== "RESOLVED";
      return (
        '<tr data-al-id="' + esc(a.id) + '" class="' + sel + '">' +
        '<td style="font-family:var(--ds-num-font);color:var(--ds-text-muted);">' + esc(moFmtClock(a.timestamp)) + "</td>" +
        '<td><span class="al-sev ' + esc(a.severity) + '">' + esc(a.severity) + "</span></td>" +
        '<td style="font-weight:var(--ds-font-semibold);">' + esc(a.source) + "</td>" +
        '<td style="font-family:var(--ds-num-font);">' + esc(a.symbol || "—") + "</td>" +
        "<td>" + esc(a.message) + "</td>" +
        '<td class="num" style="font-family:var(--ds-num-font);color:var(--ds-text-primary);">' + esc(a.current || "—") + "</td>" +
        '<td class="num" style="font-family:var(--ds-num-font);color:var(--ds-text-muted);">' + esc(a.threshold || "—") + "</td>" +
        '<td><span class="al-status ' + esc(st) + '">' + esc(st) + "</span></td>" +
        '<td><div class="al-actions">' +
        (showAck ? '<button class="al-btn primary" data-al-action="ack" data-al-id="' + esc(a.id) + '">Ack</button>' : "") +
        (showRes ? '<button class="al-btn danger"  data-al-action="resolve" data-al-id="' + esc(a.id) + '">Resolve</button>' : "") +
        "</div></td>" +
        "</tr>"
      );
    }).join("");
  }
  function renderAlTable() {
    return (
      '<table class="al-table ds-table">' +
      "<thead><tr>" +
      "<th>Time</th><th>Severity</th><th>Source</th><th>Symbol</th>" +
      "<th>Message</th><th class='num'>Current</th><th class='num'>Threshold</th>" +
      "<th>Status</th><th>Action</th>" +
      "</tr></thead>" +
      '<tbody id="al-tbody">' + renderAlRows() + "</tbody>" +
      "</table>"
    );
  }
  function refreshAlTable() {
    var fh = document.getElementById("al-filters");
    if (fh) fh.innerHTML = renderAlFilters();
    bindAlFilters();
    var tb = document.getElementById("al-tbody");
    if (tb) tb.innerHTML = renderAlRows();
  }

  // ── Alert detail panel (with related event chain) ───────────────
  function renderAlDetail() {
    var a = alFind(AL_STATE.selectedId);
    if (!a) {
      return (
        '<div class="al-detail">' +
        '<div class="empty" style="padding:var(--ds-space-4);">No alert selected / 未选择告警</div>' +
        "</div>"
      );
    }
    function kv(k, v, cls) {
      return (
        "<dt>" + esc(k) + "</dt>" +
        "<dd" + (cls ? " style='" + cls + "'" : "") + ">" + esc(v) + "</dd>"
      );
    }
    var st = alStatus(a);
    var showAck = st === "TRIGGERED";
    var showRes = st !== "RESOLVED";
    // why it fired: signal → risk → order chain from the event bus
    var evts = (a.events || []).map(function (e) {
      return (
        '<div class="mo-event-item">' +
        '<span class="mo-event-time">' + esc(moFmtClock(e.timestamp)) + "</span>" +
        '<span class="mo-event-text">' + esc(e.text) + "</span>" +
        "</div>"
      );
    }).join("");
    if (!evts) {
      evts = '<div class="empty" style="padding:var(--ds-space-2);font-size:var(--ds-text-sm);">' +
             "No related events on the bus for this alert / 无关联事件</div>";
    }
    return (
      '<div class="al-detail">' +
      // Header
      '<div class="al-detail-head">' +
      "<div>" +
      '<div class="al-detail-title">' +
      '<span class="al-sev ' + esc(a.severity) + '" style="margin-right:8px;vertical-align:middle;">' + esc(a.severity) + "</span>" +
      esc(a.message) +
      '<span class="al-status ' + esc(st) + '" style="margin-left:10px;vertical-align:middle;">' + esc(st) + "</span>" +
      "</div>" +
      '<div class="al-detail-meta">' +
      esc(a.id) + " · " + esc(moFmtClock(a.timestamp)) + " · Source " + esc(a.source) +
      (a.symbol ? " · Symbol " + esc(a.symbol) : "") +
      "</div>" +
      "</div>" +
      '<div class="al-detail-actions">' +
      (showAck ? '<button class="al-btn primary" data-al-action="ack" data-al-id="' + esc(a.id) + '">Acknowledge</button>' : "") +
      (showRes ? '<button class="al-btn danger"  data-al-action="resolve" data-al-id="' + esc(a.id) + '">Resolve</button>' : "") +
      "</div>" +
      "</div>" +

      // Body grid: left = message + context; right = related events
      '<div class="al-detail-grid">' +
      "<div>" +
      '<div class="al-detail-section-title">Alert Message · 告警内容</div>' +
      '<div style="font-size:var(--ds-text-sm);color:var(--ds-text-primary);line-height:1.6;">' +
      esc(a.message) +
      (a.reason ? '<div style="margin-top:4px;color:var(--ds-text-muted);">Reason: ' + esc(a.reason) + "</div>" : "") +
      "</div>" +

      '<div class="al-detail-section-title">Context · 当前值 / 阈值</div>' +
      '<dl class="al-detail-kv">' +
      kv("Current", a.current || "—",
         "color:var(--ds-loss);font-weight:var(--ds-font-semibold);") +
      kv("Threshold", a.threshold || "—") +
      kv("Created", moFmtClock(a.timestamp)) +
      kv("Source", a.source) +
      "</dl>" +
      "</div>" +

      "<div>" +
      '<div class="al-detail-section-title">Related Events · 关联事件链路</div>' +
      '<div class="mo-event-list">' + evts + "</div>" +
      '<div style="font-size:var(--ds-text-xs);color:var(--ds-text-muted);margin-top:6px;">' +
      "Acknowledge / Resolve are session-local — the runtime has no alert store." +
      "</div>" +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }
  function refreshAlDetail() {
    var h = document.getElementById("al-detail");
    if (h) h.innerHTML = renderAlDetail();
  }
  function refreshAlOverview() {
    var h = document.getElementById("al-overview");
    if (h) h.outerHTML = renderAlOverview();
  }

  // ── Bindings ────────────────────────────────────────────────────
  function alApplyAction(id, action) {
    var target = alFind(id);
    if (!target) return;
    if (action === "ack") AL_STATE.acked[target.id] = true;
    if (action === "resolve") {
      AL_STATE.resolved[target.id] = true;
      delete AL_STATE.acked[target.id];
    }
    AL_STATE.selectedId = target.id;
    refreshAlOverview();
    refreshAlTable();
    refreshAlDetail();
  }

  function bindAlFilters() {
    var btns = document.querySelectorAll("[data-al-filter]");
    btns.forEach(function (b) {
      b.addEventListener("click", function () {
        AL_STATE[b.getAttribute("data-al-filter-group")] =
          b.getAttribute("data-al-filter");
        refreshAlTable();
      });
    });
  }

  function bindAlertsPage() {
    var tbody = document.getElementById("al-tbody");
    if (tbody) {
      tbody.addEventListener("click", function (e) {
        var actBtn = e.target.closest("[data-al-action]");
        var row = e.target.closest("tr[data-al-id]");
        if (actBtn) {
          e.stopPropagation();
          alApplyAction(actBtn.getAttribute("data-al-id"),
                        actBtn.getAttribute("data-al-action"));
          return;
        }
        if (!row) return;
        AL_STATE.selectedId = row.getAttribute("data-al-id");
        refreshAlTable();
        refreshAlDetail();
      });
    }
    // Detail panel action buttons
    var detail = document.getElementById("al-detail");
    if (detail) {
      detail.addEventListener("click", function (e) {
        var b = e.target.closest("[data-al-action]");
        if (!b) return;
        alApplyAction(b.getAttribute("data-al-id"),
                      b.getAttribute("data-al-action"));
      });
    }
    bindAlFilters();
    // Toolbar refresh (keeps session Ack/Resolve state: ids are stable)
    var refresh = document.getElementById("al-refresh");
    if (refresh) {
      refresh.addEventListener("click", function () {
        alLoadCenter(true).then(function () { renderAlertsPageInto(); });
      });
    }
    // ③ live page: opt-in visibility-aware auto-refresh (30s)
    bindAutoRefresh("alerts", "al-auto", function () {
      alLoadCenter(true).then(function () { renderAlertsPageInto(); });
    });
  }

  function renderAlPage() {
    // ① unified API state (offline-aware) replaces the page-local error div
    var stateBlock = apiStateBlock(AL_STATE);
    if (stateBlock) {
      return UI.pageHeader("Alerts", "Unified alert center · 统一告警中心") +
        '<div id="al-page-state">' + stateBlock + "</div>";
    }
    var o = alData().overview || {};
    return (
      UI.pageHeader("Alerts", "Unified alert center · 统一告警中心") +
      '<div class="ds-toolbar">' +
        '<button id="al-refresh" class="btn btn-secondary btn-sm">Refresh</button>' +
        '<button id="al-auto" class="btn btn-secondary btn-sm">Auto 30s</button>' +
        '<span class="ds-toolbar-meta">Generated: ' + esc(moFmtClock(o.generated_at)) + "</span>" +
      "</div>" +
      UI.sectionHeading("Alert Overview") +
      renderAlOverview() +
      UI.sectionHeading("Alert Sources") +
      UI.panel("Alert Capabilities · Reconciliation, Position Limit, Service Health, Risk Rejections", renderAlSources()) +
      UI.sectionHeading("Alert Table") +
      UI.panel("Events · Severity · Status · Actions",
               '<div id="al-filters">' + renderAlFilters() + "</div>" + renderAlTable()) +
      UI.sectionHeading("Alert Detail") +
      '<div id="al-detail">' + renderAlDetail() + "</div>"
    );
  }

  function renderAlertsPageInto() {
    var host = document.getElementById("al-page");
    if (!host) return;
    host.innerHTML = renderAlPage();
    bindAlertsPage();
  }

  // ── Alerts page (Integration 015) — async hydrate ────────────────
  PAGE_FRAMEWORK["alerts"] = function () {
    // (re)load when missing data or after a retry cleared a previous error
    if (!AL_STATE.data || AL_STATE.error) {
      alLoadCenter().then(function () { renderAlertsPageInto(); });
      return (
        '<div id="al-page">' +
        (UI.pageHeader("Alerts", "Unified alert center · 统一告警中心") +
         '<div class="ds-loading">Loading alert center…</div>') +
        "</div>"
      );
    }
    return '<div id="al-page">' + renderAlPage() + "</div>";
  };


  /* ==================================================================
   * Settings module — Commit 016 / Integration 016 polish
   * System Configuration Center: left nav → right panel
   * (General / Trading / Risk / Execution / Notifications / Appearance).
   * UI-only configuration; does NOT modify risk engine, execution engine,
   * broker config, API key, live permissions, or any API/db.
   * Secrets are never persisted in the browser/localStorage/Git.
   * Integration 016: the Risk section reads the live limits from the
   * Risk API (no mock numbers); the Trading section lists the real
   * accounts from the Accounts API. Notification toggles remain
   * local-only UI preferences (no backend notification store exists).
   * ================================================================== */

  // ── Settings sections + state ──────────────────────────────────
  var STG_SECTIONS = [
    { id: "general",        label: "General" },
    { id: "trading",        label: "Trading" },
    { id: "risk",           label: "Risk" },
    { id: "execution",      label: "Execution" },
    { id: "notifications",  label: "Notifications" },
    { id: "appearance",     label: "Appearance" },
  ];
  var STG_STATE = {
    section: "general", env: "live", pfill: "allow", theme: "dark", density: "compact",
    risk: null, riskError: null,     // live limits from /dashboard/risk/center
    accounts: [],                    // real accounts from /dashboard/accounts/center
  };

  /** Hydrate the live values shown on this page (risk limits, real
   *  account list). Purely read-only; failures degrade gracefully. */
  async function stgLoadLive(force) {
    if (STG_STATE.risk && !force) return;
    try {
      var risk = await api.riskCenter();
      STG_STATE.risk = risk;
      STG_STATE.riskError = null;
    } catch (err) {
      STG_STATE.riskError = err;
    }
    try {
      var accounts = await api.accountsCenter();
      STG_STATE.accounts = (accounts && accounts.accounts) || [];
    } catch (err) {
      STG_STATE.accounts = [];
    }
  }

  /** Format a Risk-API limit value per its backend fmt hint. */
  function stgFmtLimitValue(v, fmt) {
    var n = Number(v);
    if (!isFinite(n)) return "—";
    if (fmt === "money") return UI.money(n, 0);
    if (fmt === "pct") return n.toFixed(1) + "%";
    return fmtQty(n);   // count
  }

  /** Default-account select fed by the real Accounts API; the current
   *  terminal context (APP_CTX) is the default option. */
  function stgAccountSelect() {
    var ids = STG_STATE.accounts.map(function (a) { return a.account_id; });
    if (!ids.length) ids = ["(no accounts available)"];
    var value = ids.indexOf(APP_CTX.accountId) >= 0 ? APP_CTX.accountId : ids[0];
    return UI.select({ value: value, options: ids });
  }

  // ── Notifications (label + severity + enabled) ────────────────
  var STG_NOTIFY = [
    { label: "Order Filled",            sev: "INFO",     on: true },
    { label: "Order Rejected",          sev: "INFO",     on: true },
    { label: "Partial Fill",           sev: "INFO",     on: true },
    { label: "Risk Limit Breached",    sev: "CRITICAL",  on: true },
    { label: "Risk Warning",           sev: "CRITICAL",  on: true },
    { label: "Execution Error",        sev: "CRITICAL",  on: true },
    { label: "System Offline",         sev: "CRITICAL",  on: true },
    { label: "Data Feed Disconnected", sev: "CRITICAL",  on: true },
  ];

  // ── Helpers ──────────────────────────────────────────────────
  function stgSwitch(on) {
    return (
      '<label class="stg-switch">' +
      '<input type="checkbox"' + (on ? " checked" : "") + ">" +
      '<span class="stg-switch-slider"></span>' +
      "</label>"
    );
  }
  // Generic radio builder: name (radio group), val, label, checked (bool)
  function stgRadio(name, val, label, checked) {
    var cls = checked ? " checked-" + val : "";
    return (
      '<label class="stg-env-radio' + cls + '">' +
      '<input type="radio" name="' + name + '" value="' + val + '"' + (checked ? " checked" : "") + "> " + esc(label) +
      "</label>"
    );
  }
  function stgRiskStatusBadge(status) {
    var key = status === "BREACH" ? "breach" : (status === "WATCH" ? "watch" : "normal");
    return '<span class="stg-risk-status ' + key + '">' + esc(status) + "</span>";
  }

  // ── Section: General ──────────────────────────────────────────
  function renderStgGeneral() {
    return (
      '<div class="stg-grid">' +
      UI.field("Workspace", UI.input({ value: "ICYQuant Workspace" })) +
      '<div class="stg-row">' +
      UI.field("Language", UI.select({ value: "English", options: ["English", "中文", "日本語"] })) +
      UI.field("Timezone", UI.select({ value: "Asia/Taipei", options: ["UTC", "Asia/Shanghai", "Asia/Taipei", "America/New_York", "Europe/London"] })) +
      "</div>" +
      '<div class="stg-row">' +
      UI.field("Base Currency", UI.select({ value: "USD", options: ["USD", "CNY", "EUR", "JPY"] })) +
      UI.field("Date Format", UI.select({ value: "YYYY-MM-DD", options: ["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"] })) +
      "</div>" +
      "</div>"
    );
  }

  // ── Section: Trading (Paper / Shadow / Live) ─────────────────
  function renderStgTrading() {
    var envHtml =
      '<div class="ds-field"><label class="ds-field-label">Trading Environment</label>' +
      '<div class="stg-env-radios">' +
      stgRadio("stg-env", "paper", "Paper", STG_STATE.env === "paper") +
      stgRadio("stg-env", "shadow", "Shadow", STG_STATE.env === "shadow") +
      stgRadio("stg-env", "live", "Live", STG_STATE.env === "live") +
      "</div></div>";
    var liveWarn = STG_STATE.env === "live"
      ? '<div class="stg-live-warn">⚠ LIVE environment — real orders will be sent to the broker. Trade with caution.</div>'
      : "";
    return (
      '<div class="stg-grid">' +
      envHtml +
      liveWarn +
      '<div class="stg-row">' +
      UI.field("Default Account", stgAccountSelect()) +
      UI.field("Default Order Size", UI.input({ type: "number", value: "100" })) +
      "</div>" +
      '<div class="stg-row">' +
      UI.field("Slippage Tolerance", UI.input({ value: "3.0 bps" })) +
      '<div class="ds-field"><label class="ds-field-label">Order Confirmation</label>' +
      '<label class="stg-check"><input type="checkbox" checked> Require confirmation before submitting</label>' +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  // ── Section: Risk (live limits from the Risk API) ─────────────
  function renderStgRisk() {
    // live values from /dashboard/risk/center — no mock numbers
    if (!STG_STATE.risk) {
      return STG_STATE.riskError
        ? UI.stateError(
            "Risk limits unavailable / 风控限额不可用",
            (STG_STATE.riskError.message || String(STG_STATE.riskError)) +
              " · The Risk API did not respond.",
            "Retry", "stg:risk-retry")
        : UI.stateLoading("Loading risk limits / 加载风控限额",
                          "Reading live limits from the Risk API…");
    }
    var limits = STG_STATE.risk.limits || [];
    if (!limits.length) {
      return UI.stateEmpty("No data available",
                           "The Risk API reported no configured limits. / 暂无限额数据");
    }
    var cards = limits.map(function (r) {
      return (
        '<div class="stg-risk-card">' +
        '<div><div class="stg-risk-label">' + esc(r.name) + "</div>" +
        '<div class="stg-risk-value">' + esc(stgFmtLimitValue(r.limit, r.fmt)) + "</div></div>" +
        '<div><div class="stg-risk-label">Current</div>' +
        '<div class="stg-risk-current">' + esc(stgFmtLimitValue(r.current, r.fmt)) + "</div></div>" +
        '<div><div class="stg-risk-label">Status</div>' + stgRiskStatusBadge(r.status) + "</div>" +
        UI.input({ value: stgFmtLimitValue(r.limit, r.fmt), disabled: true }) +
        "</div>"
      );
    }).join("");
    return (
      '<div class="stg-risk-list">' + cards + "</div>" +
      '<div style="font-size:var(--ds-text-xs);color:var(--ds-text-muted);margin-top:8px;">' +
      "Read-only view of the live engine limits (Risk API) — editing is not wired to the engine. / 限额为引擎实时值（只读）" +
      "</div>"
    );
  }

  // ── Section: Execution ────────────────────────────────────────
  function renderStgExecution() {
    return (
      '<div class="stg-grid">' +
      UI.field("Default Venue", UI.select({ value: "Primary", options: ["Primary", "SOR", "Dark Pool", "Direct"] })) +
      '<div class="stg-row">' +
      UI.field("Order Timeout", UI.input({ type: "number", value: "30", step: "1" }) + ' <span style="color:var(--ds-text-muted);font-size:var(--ds-text-sm);">sec</span>') +
      UI.field("Retry Attempts", UI.input({ type: "number", value: "2" })) +
      "</div>" +
      '<div class="ds-field"><label class="ds-field-label">Partial Fill</label>' +
      '<div class="stg-env-radios">' +
      stgRadio("stg-pfill", "allow", "Allow", STG_STATE.pfill === "allow") +
      stgRadio("stg-pfill", "reject", "Reject", STG_STATE.pfill === "reject") +
      "</div></div>" +
      UI.field("Slippage Alert Threshold", UI.input({ value: "5.0 bps" })) +
      "</div>"
    );
  }

  // ── Section: Notifications ────────────────────────────────────
  function renderStgNotifications() {
    var rows = STG_NOTIFY.map(function (n) {
      var sevKey = n.sev === "CRITICAL" ? "critical" : "info";
      return (
        '<div class="stg-notify-item">' +
        '<span class="stg-notify-sev ' + sevKey + '">' + esc(n.sev) + "</span>" +
        '<span class="stg-notify-label">' + esc(n.label) + "</span>" +
        stgSwitch(n.on) +
        "</div>"
      );
    }).join("");
    return (
      '<div class="ds-panel"><div class="ds-panel-body">' + rows + "</div></div>" +
      '<div style="font-size:var(--ds-text-xs);color:var(--ds-text-muted);margin-top:8px;">' +
      "Local-only UI preference — the runtime has no notification store; alert delivery is out of scope (no channels configured). / 本地界面偏好，不持久化" +
      "</div>"
    );
  }

  // ── Section: Appearance ──────────────────────────────────────
  function renderStgAppearance() {
    return (
      '<div class="stg-grid">' +
      '<div class="ds-field"><label class="ds-field-label">Theme</label>' +
      '<div class="stg-env-radios">' +
      stgRadio("stg-theme", "dark", "Dark", STG_STATE.theme === "dark") +
      stgRadio("stg-theme", "light", "Light", STG_STATE.theme === "light") +
      stgRadio("stg-theme", "system", "System", STG_STATE.theme === "system") +
      "</div></div>" +
      '<div class="ds-field"><label class="ds-field-label">Density</label>' +
      '<div class="stg-env-radios">' +
      stgRadio("stg-density", "comfortable", "Comfortable", STG_STATE.density === "comfortable") +
      stgRadio("stg-density", "compact", "Compact", STG_STATE.density === "compact") +
      "</div></div>" +
      '<div class="stg-row">' +
      '<div class="ds-field"><label class="ds-field-label">Charts</label>' +
      '<label class="stg-check"><input type="checkbox" checked> Show Grid</label>' +
      '<label class="stg-check"><input type="checkbox" checked> Show Volume</label>' +
      '<label class="stg-check"><input type="checkbox" checked> Crosshair</label>' +
      "</div>" +
      '<div class="ds-field"><label class="ds-field-label">Dashboard</label>' +
      '<label class="stg-check"><input type="checkbox" checked> Compact KPI Cards</label>' +
      '<label class="stg-check"><input type="checkbox" checked> Show P&L</label>' +
      '<label class="stg-check"><input type="checkbox" checked> Show Risk</label>' +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  // ── Left nav + right content ─────────────────────────────────
  function renderStgNav() {
    var items = STG_SECTIONS.map(function (s) {
      var cls = s.id === STG_STATE.section ? " active" : "";
      return '<button class="stg-nav-item' + cls + '" data-stg-section="' + esc(s.id) + '">' + esc(s.label) + "</button>";
    }).join("");
    return '<div class="stg-nav"><div class="stg-nav-title">Settings</div>' + items + "</div>";
  }

  function renderStgContent() {
    var body;
    switch (STG_STATE.section) {
      case "trading":       body = renderStgTrading(); break;
      case "risk":          body = renderStgRisk(); break;
      case "execution":     body = renderStgExecution(); break;
      case "notifications": body = renderStgNotifications(); break;
      case "appearance":    body = renderStgAppearance(); break;
      default:              body = renderStgGeneral();
    }
    var title = (STG_SECTIONS.find(function (s) { return s.id === STG_STATE.section; }) || {}).label || "General";
    return (
      '<div id="stg-content">' +
      UI.panel(title, body) +
      '<div class="stg-actions">' +
      UI.button("Save Changes", "primary", { sm: true, action: "stg:save" }) +
      UI.button("Reset to Defaults", "ghost", { sm: true, action: "stg:reset" }) +
      "</div>" +
      "</div>"
    );
  }

  function updateStgContent() {
    var host = document.getElementById("stg-content");
    if (host) {
      host.outerHTML = renderStgContent();
      bindStgContent();
    }
  }

  // ── Bindings (nav select, env radio, save/reset) ─────────────
  function bindStgContent() {
    // Generic radio group handler — maps name → state key
    var groups = {
      "stg-env": "env",
      "stg-pfill": "pfill",
      "stg-theme": "theme",
      "stg-density": "density",
    };
    Object.keys(groups).forEach(function (name) {
      var radios = document.querySelectorAll('input[name="' + name + '"]');
      radios.forEach(function (r) {
        r.addEventListener("change", function () {
          STG_STATE[groups[name]] = r.value;
          updateStgContent();
        });
      });
    });
    var saveBtn = document.querySelector('[data-action="stg:save"]');
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        showToast("Settings saved (UI only) / 设置已保存 — no backend changes", "ok");
      });
    }
    var resetBtn = document.querySelector('[data-action="stg:reset"]');
    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        showToast("Settings reset to defaults (UI only) / 已恢复默认", "info");
        STG_STATE = { section: "general", env: "live", pfill: "allow", theme: "dark", density: "compact" };
        renderStgShell();
      });
    }
  }

  function renderStgShell() {
    var host = document.getElementById("stg-page");
    if (host) {
      host.innerHTML = '<div class="stg-layout">' + renderStgNav() + renderStgContent() + "</div>";
      bindStgShell();
    }
  }

  function bindStgShell() {
    var navItems = document.querySelectorAll(".stg-nav-item");
    navItems.forEach(function (btn) {
      btn.addEventListener("click", function () {
        STG_STATE.section = btn.getAttribute("data-stg-section");
        renderStgShell();
      });
    });
    bindStgContent();
  }

  function bindSettingsPage() {
    bindStgShell();
  }

  // ── Settings page (Integration 016) — async hydrate live values ──
  PAGE_FRAMEWORK["settings"] = async function () {
    if (!STG_STATE.risk && !STG_STATE.riskError) {
      stgLoadLive().then(function () { renderStgShell(); });
    }
    return (
      UI.pageHeader("Settings", "System configuration and preferences · 系统配置") +
      '<div id="stg-page"><div class="stg-layout">' + renderStgNav() + renderStgContent() + "</div></div>"
    );
  };

  /* ==================================================================
   * Data module — Integration 013
   * Market Data & Data Pipeline Center: overview → markets → datasets →
   * detail → quality → pipeline. Reads the live data layer via
   * GET /dashboard/data/center (data/real/d1 + data/processed/manifests +
   * data/lakehouse/_state.json). No mock data, no fetch triggers, no
   * schema edits — purely a read view over what Research / Backtest use.
   * ================================================================== */

  // ── Data state (Integration 013) ─────────────────────────────
  var DT_STATE = {
    data: null,
    error: null,
    selectedId: null,
  };

  async function dtLoadCenter(force) {
    if (DT_STATE.data && !force) return;
    try {
      var data = await api.dataCenter();
      DT_STATE.data = data;
      DT_STATE.error = null;
      // default selection: first dataset, else 'real-d1'
      if (!DT_STATE.selectedId && data.datasets && data.datasets.length) {
        var firstReady = data.datasets.find(function (d) { return d.status === "READY"; });
        DT_STATE.selectedId = (firstReady || data.datasets[0]).id;
      }
    } catch (err) {
      // keep the full ApiError (kind=network drives the Offline state)
      DT_STATE.error = err || "Failed to load data center";
    }
  }

  function dtData() {
    return DT_STATE.data || {
      overview: { data_service: "—", datasets: 0, symbols: 0, records: 0,
                  coverage: "—", range_start: "", range_end: "", last_update: "" },
      datasets: [],
      symbols: [],
      markets: [],
      quality: { datasets_pass: 0, datasets_fail: 0, datasets_total: 0,
                 coverage: "—", checks: [] },
      pipeline: { status: "—", stages: [], lakehouse: {} },
      real_daily: { fetched_at: null, range: [null, null], rows: [] },
    };
  }

  // ── Helpers ──────────────────────────────────────────────────
  function dtFind(id) {
    var ds = dtData().datasets || [];
    for (var i = 0; i < ds.length; i++) {
      if (ds[i].id === id) return ds[i];
    }
    return ds[0] || null;
  }
  function dtMarketStatus(s) {
    return '<span class="dt-market-status ' + s + '">' + esc(s.toUpperCase()) + "</span>";
  }
  function dtDsStatusBadge(s) {
    var cls = s === "READY" ? "healthy" : (s === "STALE" || s === "DEGRADED" ? "degraded" : "down");
    return '<span class="dt-market-status ' + cls + '">' + esc(s) + "</span>";
  }
  function dtQualityBadge(s) {
    var key = s === "PASS" ? "pass" : (s === "WARN" ? "warn" : "fail");
    return '<span class="dt-quality-status dt-quality-' + key + '">' + esc(s) + "</span>";
  }
  function dtFmtNum(n) {
    if (n === null || n === undefined || n === "—") return "—";
    var x = Number(n);
    if (isNaN(x)) return String(n);
    return x.toLocaleString("en-US");
  }
  function dtServiceBadge(s) {
    var cls = s === "HEALTHY" ? "healthy" : (s === "EMPTY" ? "down" : "degraded");
    var label = s === "HEALTHY" ? "● HEALTHY" : (s === "EMPTY" ? "○ EMPTY" : "● " + s);
    return '<span class="dt-market-status ' + cls + '">' + esc(label) + "</span>";
  }

  // ── Overview KPI ─────────────────────────────────────────────
  function renderDtOverview() {
    var o = dtData().overview;
    var svcCls = o.data_service === "HEALTHY" ? "pos" : (o.data_service === "EMPTY" ? "neg" : "");
    return UI.kpiGrid(
      UI.metricCard("Data Service", o.data_service, "", svcCls) +
      UI.metricCard("Datasets", String(o.datasets), "", "") +
      UI.metricCard("Symbols", String(o.symbols), "", "") +
      UI.metricCard("Records", dtFmtNum(o.records), "", "") +
      UI.metricCard("Coverage", o.coverage, "", "pos") +
      UI.metricCard("Last Update", o.last_update || "—", "", "")
    , 6);
  }

  // ── Markets ──────────────────────────────────────────────────
  function renderDtMarkets() {
    var markets = dtData().markets || [];
    if (!markets.length) {
      return '<div class="dt-empty">No markets registered.</div>';
    }
    var cards = markets.map(function (m) {
      return (
        '<div class="dt-market-card">' +
        '<div class="dt-market-head">' +
        '<span class="dt-market-name">' + esc(m.market) + "</span>" +
        dtMarketStatus(m.status) +
        "</div>" +
        '<div class="dt-market-inst">' + m.symbols + " symbol" + (m.symbols === 1 ? "" : "s") + "</div>" +
        "</div>"
      );
    }).join("");
    return '<div class="dt-market-grid">' + cards + "</div>";
  }

  // ── Dataset table (clickable rows) ──────────────────────────
  function renderDtRows() {
    var ds = dtData().datasets || [];
    if (!ds.length) {
      return '<tr><td colspan="5" class="dt-empty">No datasets registered.</td></tr>';
    }
    return ds.map(function (d) {
      var sel = d.id === DT_STATE.selectedId ? " dt-ds-row-selected" : "";
      return (
        '<tr class="dt-ds-row' + sel + '" data-dt-id="' + esc(d.id) + '">' +
        "<td>" + esc(d.name) + "</td>" +
        "<td>" + esc(d.type) + "</td>" +
        "<td>" + esc(d.tf) + "</td>" +
        '<td class="num">' + dtFmtNum(d.bars) + "</td>" +
        "<td>" + dtDsStatusBadge(d.status) + "</td>" +
        "</tr>"
      );
    }).join("");
  }
  function renderDtList() {
    return (
      '<table class="ds-table dt-ds-table">' +
      "<thead><tr>" +
      "<th>Name</th><th>Type</th><th>TF</th>" +
      '<th class="num">Bars</th><th>Status</th>' +
      "</tr></thead>" +
      '<tbody id="dt-ds-tbody">' + renderDtRows() + "</tbody>" +
      "</table>"
    );
  }

  // ── Dataset detail ───────────────────────────────────────────
  function dtDetailCell(label, value) {
    return (
      '<div class="dt-detail-cell">' +
      '<div class="dt-detail-label">' + esc(label) + "</div>" +
      '<div class="dt-detail-value">' + esc(value) + "</div>" +
      "</div>"
    );
  }
  function renderDtDetail() {
    var d = dtFind(DT_STATE.selectedId);
    if (!d) {
      return '<div class="dt-empty">Select a dataset to view details.</div>';
    }
    return (
      '<div class="dt-detail-grid">' +
      dtDetailCell("Dataset", d.name + " / " + d.tf) +
      dtDetailCell("Type", d.type) +
      dtDetailCell("Status", d.status) +
      dtDetailCell("Date Range", d.date_range) +
      dtDetailCell("Assets", String(d.assets)) +
      dtDetailCell("Bars", dtFmtNum(d.bars)) +
      dtDetailCell("Missing", d.missing) +
      dtDetailCell("Duplicates", String(d.duplicates)) +
      dtDetailCell("Last Update", d.last_update) +
      dtDetailCell("Source", d.source) +
      "</div>"
    );
  }
  function updateDtDetail() {
    var host = document.getElementById("dt-detail");
    if (host) host.innerHTML = renderDtDetail();
  }

  // ── Symbols table ────────────────────────────────────────────
  function renderDtSymbols() {
    var syms = dtData().symbols || [];
    if (!syms.length) {
      return '<div class="dt-empty">No symbols registered.</div>';
    }
    var rows = syms.map(function (s) {
      return (
        "<tr>" +
        "<td>" + esc(s.symbol) + "</td>" +
        "<td>" + esc(s.asset_class) + "</td>" +
        "<td>" + esc(s.market) + "</td>" +
        "<td>" + esc((s.timeframes || []).join(", ")) + "</td>" +
        "<td>" + esc(s.first_date || "—") + "</td>" +
        "<td>" + esc(s.last_date || "—") + "</td>" +
        '<td class="num">' + dtFmtNum(s.bars) + "</td>" +
        "<td>" + dtDsStatusBadge(s.status) + "</td>" +
        "</tr>"
      );
    }).join("");
    return (
      '<table class="ds-table">' +
      "<thead><tr>" +
      "<th>Symbol</th><th>Asset Class</th><th>Market</th><th>TFs</th>" +
      "<th>First</th><th>Last</th>" +
      '<th class="num">Bars</th><th>Status</th>' +
      "</tr></thead>" +
      '<tbody>' + rows + "</tbody>" +
      "</table>"
    );
  }

  // ── Data quality ─────────────────────────────────────────────
  function renderDtQuality() {
    var q = dtData().quality;
    var rows = (q.checks || []).map(function (c) {
      var status = c.pass === c.total ? "PASS" : (c.pass > 0 ? "WARN" : "FAIL");
      return (
        '<div class="dt-quality-row">' +
        '<span class="dt-quality-label">' + esc(c.name) + "</span>" +
        '<span class="dt-quality-value">' + c.pass + "/" + c.total + "</span>" +
        dtQualityBadge(status) +
        "</div>"
      );
    }).join("");
    var summary = (
      '<div class="dt-quality-row">' +
      '<span class="dt-quality-label">Coverage</span>' +
      '<span class="dt-quality-value">' + esc(q.coverage) + "</span>" +
      dtQualityBadge(q.datasets_fail === 0 ? "PASS" : "WARN") +
      "</div>"
    );
    return '<div class="dt-quality-list">' + summary + rows + "</div>";
  }

  // ── Pipeline stepper ─────────────────────────────────────────
  function renderDtPipeline() {
    var p = dtData().pipeline;
    var stages = p.stages || [];
    if (!stages.length) {
      return '<div class="dt-empty">No pipeline state available.</div>';
    }
    var html = '<div class="dt-pipeline">';
    stages.forEach(function (s, i) {
      var icon = s.state === "done" ? "✓" : (s.state === "fail" ? "✕" : "—");
      html +=
        '<div class="dt-pipe-step ' + s.state + '">' +
        '<div class="dt-pipe-icon">' + icon + "</div>" +
        '<div class="dt-pipe-label">' + esc(s.label) + "</div>" +
        "</div>";
      if (i < stages.length - 1) {
        html += '<span class="dt-pipe-arrow">→</span>';
      }
    });
    html += "</div>";

    var lk = p.lakehouse || {};
    html += (
      '<div class="dt-lakehouse-summary">' +
      '<span><b>Lakehouse:</b> ' + (lk.datasets || 0) + " datasets · " +
      (lk.current_snapshots || 0) + " current snapshots · " +
      (lk.files || 0) + " files</span>" +
      '<span class="dt-last-write">Last write: ' + esc(lk.last_write || "—") + "</span>" +
      "</div>"
    );
    return html;
  }

  // ── Bindings (row select + refresh) ─────────────────────────
  function bindDataPage() {
    var tbody = document.getElementById("dt-ds-tbody");
    if (tbody) {
      tbody.addEventListener("click", function (e) {
        var row = e.target.closest("tr[data-dt-id]");
        if (!row) return;
        DT_STATE.selectedId = row.getAttribute("data-dt-id");
        tbody.innerHTML = renderDtRows();
        updateDtDetail();
      });
    }
    var refresh = document.getElementById("dt-refresh");
    if (refresh) {
      refresh.addEventListener("click", function () {
        DT_STATE.data = null;
        DT_STATE.selectedId = null;
        dtLoadCenter(true).then(function () { renderDtPageInto(); });
      });
    }
  }

  function renderDtPageInto() {
    var host = document.getElementById("dt-page");
    if (!host) return;
    host.innerHTML = renderDtPage();
    bindDataPage();
  }

  function renderDtPage() {
    // ① unified API state (offline-aware) replaces the page-local error div
    var stateBlock = apiStateBlock(DT_STATE);
    if (stateBlock) {
      return UI.pageHeader("Data", "Market data & data pipeline center · 市场数据中心") +
        '<div id="dt-page-state">' + stateBlock + "</div>";
    }
    var o = dtData().overview;
    return (
      UI.pageHeader("Data", "Market data & data pipeline center · 市场数据中心") +
      '<div class="ds-toolbar">' +
        '<button id="dt-refresh" class="btn btn-secondary btn-sm">Refresh</button>' +
        '<span class="ds-toolbar-meta">Last update: ' + esc(o.last_update || "—") + "</span>" +
      "</div>" +
      UI.sectionHeading("Data Overview") +
      renderDtOverview() +
      UI.sectionHeading("Markets") +
      UI.panel("Market Coverage", renderDtMarkets()) +
      UI.sectionHeading("Datasets") +
      UI.panel("Dataset Explorer", renderDtList()) +
      UI.sectionHeading("Dataset Details") +
      '<div id="dt-detail">' + renderDtDetail() + "</div>" +
      UI.sectionHeading("Symbols") +
      UI.panel("Instrument Universe", renderDtSymbols()) +
      UI.sectionHeading("Data Quality") +
      UI.panel("Quality Checks", renderDtQuality()) +
      UI.sectionHeading("Data Pipeline") +
      UI.panel("Pipeline Status", renderDtPipeline())
    );
  }

  // ── Data page (Integration 013) — async hydrate ───────────────
  PAGE_FRAMEWORK["system/data"] = function () {
    // Returning a shell lets the framework mount immediately; we then
    // hydrate async after the first API call resolves.
    // (re)load when missing data or after a retry cleared a previous error
    if (!DT_STATE.data || DT_STATE.error) {
      dtLoadCenter().then(function () { renderDtPageInto(); });
    }
    return (
      '<div id="dt-page">' +
      (UI.pageHeader("Data", "Market data & data pipeline center · 市场数据中心") +
       '<div class="ds-loading">Loading data center…</div>') +
      "</div>"
    );
  };



  // Build ROUTES array from NAV config
  const ROUTES = Object.keys(NAV).map(function (hash) {
    var cfg = NAV[hash];
    var escaped = hash.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return {
      re: new RegExp("^" + escaped + "$"),
      title: cfg.label + " / " + cfg.zh,
      navKey: cfg.navKey,
      group: cfg.group,
      render: function () { return pageNavPlaceholder(cfg); },
    };
  });
  // Add design-system showcase route
  ROUTES.push({
    re: /^#\/design-system$/,
    title: "Design System / 设计系统",
    navKey: "design-system",
    group: "system",
    render: pageDesignSystem,
  });
  // Legacy redirect routes (old → new)
  ROUTES.push({ re: /^#\/overview$/, title: "", navKey: "dashboard", group: "overview", render: function () { location.hash = "#/dashboard"; return ""; } });
  ROUTES.push({ re: /^#\/accounts$/, title: "", navKey: "operations/accounts", group: "operations", render: function () { location.hash = "#/operations/accounts"; return ""; } });
  ROUTES.push({ re: /^#\/positions$/, title: "", navKey: "trading/positions", group: "trading", render: function () { location.hash = "#/trading/positions"; return ""; } });
  ROUTES.push({ re: /^#\/orders$/, title: "", navKey: "trading/orders", group: "trading", render: function () { location.hash = "#/trading/orders"; return ""; } });
  ROUTES.push({ re: /^#\/strategies$/, title: "", navKey: "research/strategies", group: "research", render: function () { location.hash = "#/research/strategies"; return ""; } });
  ROUTES.push({ re: /^#\/backtest$/, title: "", navKey: "research/backtest", group: "research", render: function () { location.hash = "#/research/backtest"; return ""; } });
  ROUTES.push({ re: /^#\/factor$/, title: "", navKey: "research/factors", group: "research", render: function () { location.hash = "#/research/factors"; return ""; } });
  ROUTES.push({ re: /^#\/exposure$/, title: "", navKey: "risk/exposure", group: "risk", render: function () { location.hash = "#/risk/exposure"; return ""; } });
  ROUTES.push({ re: /^#\/reconciliation$/, title: "", navKey: "operations/reconciliation", group: "operations", render: function () { location.hash = "#/operations/reconciliation"; return ""; } });

  function showToast(msg, cls) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.className = "toast " + (cls || "");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function () {
      t.className = "toast hidden";
    }, 3500);
  }

  function setNavActive(navKey, group) {
    // Clear all active + expanded
    document.querySelectorAll("#nav .nav-link").forEach(function (a) {
      a.classList.remove("active");
    });
    document.querySelectorAll("#nav .nav-section").forEach(function (s) {
      s.classList.remove("expanded");
    });

    // Set active link
    if (navKey) {
      var el = document.querySelector('#nav .nav-link[data-nav="' + navKey + '"]');
      if (el) el.classList.add("active");
    }

    // Expand the group containing the active link
    if (group) {
      var section = document.querySelector('#nav .nav-section[data-group="' + group + '"]');
      if (section) section.classList.add("expanded");
    }
  }

  function renderBreadcrumb(group, label) {
    var bc = document.getElementById("breadcrumb");
    if (!bc) return;
    var html = '<span class="crumb crumb-root">ICYQuant</span>';
    if (group && group !== "overview") {
      var groupLabel = GROUP_LABELS[group] || group;
      html += '<span class="crumb-sep">/</span>';
      html += '<span class="crumb crumb-group">' + esc(groupLabel.toUpperCase()) + "</span>";
    }
    if (label) {
      html += '<span class="crumb-sep">/</span>';
      html += '<span class="crumb crumb-page">' + esc(label) + "</span>";
    }
    bc.innerHTML = html;
  }

  async function render() {
    if (!api.isAuthenticated()) {
      document.getElementById("app-view").classList.add("hidden");
      document.getElementById("login-view").classList.remove("hidden");
      return;
    }
    document.getElementById("login-view").classList.add("hidden");
    document.getElementById("app-view").classList.remove("hidden");

    var hash = location.hash || "#/dashboard";
    var user = api.user;
    document.getElementById("user-badge").innerHTML =
      esc(user ? user.username : "") + " · <b>" + esc(user ? user.role : "") + "</b>";

    var route = ROUTES[0];
    for (var i = 0; i < ROUTES.length; i++) {
      if (ROUTES[i].re.test(hash)) { route = ROUTES[i]; break; }
    }

    // Set page title
    if (route.title) {
      document.getElementById("page-title").textContent = route.title;
    }

    // Set nav active + expand group
    setNavActive(route.navKey, route.group);

    // Render breadcrumb
    var navCfg = NAV[hash];
    if (navCfg) {
      renderBreadcrumb(navCfg.group, navCfg.label);
    } else if (hash === "#/design-system") {
      renderBreadcrumb("system", "Design System");
    } else {
      renderBreadcrumb(route.group, null);
    }

    // Load topbar state (environment, account, health) in background
    loadTopbarState();

    const content = document.getElementById("page-content");
    content.innerHTML = UI.stateLoading("Loading page / 页面加载中", "Fetching latest data…");
    try {
      const html = await route.render(hash.match(route.re));
      content.innerHTML = html;
      // ── Polish 020: keyboard row navigation on main tables ─────────
      try { bindTerminalKeyboard(); } catch (e) { /* ignore */ }
      bindActions();
      // ── Polish 020: welcome toast only on first login ──────────────
      try { polishFirstHitToast(); } catch (e) { /* ignore */ }
    } catch (err) {
      if (err && err.status === 401) {
        render();
        return;
      }
      content.innerHTML =
        UI.stateError(
          "Failed to load page / 页面加载失败",
          (err && err.message ? err.message : String(err)) + " · Click Retry to re-attempt page render.",
          "Retry",
          "page-render-retry"
        );
      // Bind the retry button once
      setTimeout(function () {
        var b = content.querySelector('[data-action="page-render-retry"]');
        if (b) b.addEventListener("click", function () { render(); });
      }, 0);
    }
    updateConnDot();
  }

  /* ==================================================================
   * Commit 020 — Terminal keyboard nav + first-hit toast
   *
   * Keyboard:
   *   ?                     show kbd help toast
   *   Alt+1..9              jump to numbered left-nav group (approx)
   *   J / ↓                 next row in main table
   *   K / ↑                 prev row in main table
   *   Enter / O             click selected row
   *   N                     toast: "New Order"
   *   /                     focus global search (if present)
   *   G then H              go Dashboard, S = Settings, M = Monitoring, A = Alerts
   *   Esc                   close modal / drawer (already in UI)
   * ================================================================== */
  var _kbActiveRowIdx = -1;
  function mainTableBody() {
    var ids = ["mo-svc-tbody", "al-tbody", "dt-ds-tbody"];
    for (var i = 0; i < ids.length; i++) {
      var tb = document.getElementById(ids[i]);
      if (tb) return tb;
    }
    var t = document.querySelector(".ds-table tbody");
    return t || null;
  }
  function kbMoveRow(dir) {
    var tb = mainTableBody();
    if (!tb) return;
    var rows = tb.querySelectorAll("tr");
    if (!rows.length) return;
    if (_kbActiveRowIdx < 0 || _kbActiveRowIdx >= rows.length) _kbActiveRowIdx = 0;
    _kbActiveRowIdx = (rows.length + _kbActiveRowIdx + dir) % rows.length;
    UI.setActiveRow(tb, _kbActiveRowIdx);
    try {
      rows[_kbActiveRowIdx].scrollIntoView({ block: "nearest" });
    } catch (e) { /* ignore */ }
  }
  function kbOpenRow() {
    var tb = mainTableBody();
    if (!tb) return;
    var rows = tb.querySelectorAll("tr");
    var r = rows[_kbActiveRowIdx >= 0 ? _kbActiveRowIdx : 0];
    if (r) r.click();
  }
  function kbNavHash(h) {
    if (!h) return;
    location.hash = h;
  }
  function bindTerminalKeyboard() {
    // remove existing once (defensive: render() can call bindActions several times)
    if (window.__polishKbBound) return;
    window.__polishKbBound = true;
    var gPending = false;
    window.addEventListener("keydown", function (e) {
      // Avoid intercepting when typing in form elements
      var tag = (e.target && e.target.tagName) ? e.target.tagName.toUpperCase() : "";
      var inForm = tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA";
      if (inForm && e.key !== "Escape" && e.key !== "/" && !(e.altKey)) return;

      // Modifier hotkeys
      if (e.altKey && /^[1-9]$/.test(e.key)) {
        e.preventDefault();
        var navLinks = document.querySelectorAll("#nav .nav-link");
        var idx = Math.min(parseInt(e.key, 10) - 1, navLinks.length - 1);
        if (navLinks[idx]) navLinks[idx].click();
        return;
      }

      if (e.key === "?") {
        e.preventDefault();
        UI.toast({ kind: "info", title: "Keyboard Shortcuts",
          sub: "Alt+1..9 nav · J/K or ↑/↓ rows · Enter open · N New Order · G+H Dashboard · G+M Monitoring · G+A Alerts · G+S Settings · ? help" });
        return;
      }

      if (e.key === "/") {
        // Focus the global search / watchlist search if exists
        e.preventDefault();
        var s = document.getElementById("tr-symbol-search") || document.querySelector('.ds-input[type="text"]');
        if (s) s.focus();
        return;
      }

      if (e.key === "j" || e.key === "J" || e.key === "ArrowDown") { kbMoveRow(+1); return; }
      if (e.key === "k" || e.key === "K" || e.key === "ArrowUp")   { kbMoveRow(-1); return; }
      if (e.key === "Enter" || e.key === "o" || e.key === "O")     { kbOpenRow(); return; }

      if (e.key === "n" || e.key === "N") {
        UI.toast({ kind: "success", title: "New Order",
          sub: "Open Trading tab and submit order (paper only)." });
        kbNavHash("#/trading");
        return;
      }

      // G prefix navigation
      if (e.key === "g" || e.key === "G") { gPending = true; return; }
      if (gPending) {
        gPending = false;
        switch (e.key.toLowerCase()) {
          case "h": kbNavHash("#/dashboard"); return;
          case "d": kbNavHash("#/dashboard"); return;
          case "t": kbNavHash("#/trading");   return;
          case "p": kbNavHash("#/portfolio"); return;
          case "o": kbNavHash("#/orders");    return;
          case "s": kbNavHash("#/settings");  return;
          case "m": kbNavHash("#/system");    return;
          case "a": kbNavHash("#/alerts");    return;
          case "r": kbNavHash("#/research");  return;
          case "k": kbNavHash("#/risk");      return;
          case "e": kbNavHash("#/execution"); return;
          case "b": kbNavHash("#/backtest");  return;
          case "c": kbNavHash("#/accounts");  return;
          case "i": kbNavHash("#/system/data"); return;
        }
      }
    });
  }
  function polishFirstHitToast() {
    try {
      if (sessionStorage.getItem("icy.polish.shown")) return;
      sessionStorage.setItem("icy.polish.shown", "1");
      UI.toast({ kind: "info", title: "ICYQuant UI V1 · Final Polish",
        sub: "Press ? for keyboard shortcuts. Everything rendered client-side." });
    } catch (e) { /* sessionStorage blocked in sandbox is fine */ }
  }

  /* ==================================================================
   * Topbar state: environment / account / system health
   * ================================================================== */
  let _topbarLoading = false;

  async function loadTopbarState() {
    // These endpoints require authentication; don't spam 401s on the login
    // view or when the session is missing.  Backend connectivity is
    // tracked separately by the anonymous /api/health probe.
    if (!api.isAuthenticated()) return;
    if (_topbarLoading) return;
    _topbarLoading = true;
    try {
      const [cfg, health] = await Promise.allSettled([
        api.get("/dashboard/config"),
        api.get("/dashboard/system"),
      ]);

      // Environment badge
      const envBadge = document.getElementById("env-badge");
      if (cfg.status === "fulfilled" && cfg.value) {
        const accType = (cfg.value.account && cfg.value.account.account_type) || "Paper";
        const envText = accType.toUpperCase();
        envBadge.textContent = envText;
        envBadge.className = "env-badge env-" + accType.toLowerCase();
      }

      // System health
      if (health.status === "fulfilled" && health.value) {
        const svc = health.value.health || {};
        const overall = svc.overall || "healthy";
        const dot = document.getElementById("health-dot");
        const text = document.getElementById("health-text");
        const status = overall.toLowerCase();
        dot.className = "health-dot " + (status === "healthy" ? "" : status);
        text.className = "health-text " + (status === "healthy" ? "" : status);
        text.textContent = status.toUpperCase();
      }
    } catch (e) {
      // keep defaults on error
    } finally {
      _topbarLoading = false;
    }
    // ④ Account context: build the terminal-wide selector from the real
    // Accounts API (once); the active selection lives in APP_CTX and
    // drives the Orders / Positions account filters.
    buildTopbarAccountSelector();
  }

  var _ctxSelectorBuilt = false;
  async function buildTopbarAccountSelector() {
    if (_ctxSelectorBuilt) { renderTopbarAccountName(); return; }
    var host = document.getElementById("account-selector");
    if (!host) return;
    var accounts = [];
    try {
      var data = await api.accountsCenter();
      accounts = (data && data.accounts) || [];
    } catch (e) {
      accounts = [];   // offline — selector stays with the ALL default
    }
    _ctxSelectorBuilt = true;
    var opts = ['<option value="ALL">All Accounts</option>'].concat(
      accounts.map(function (a) {
        return '<option value="' + esc(a.account_id) + '">' +
               esc(a.account_id + " · " + a.name) + "</option>";
      })
    );
    // replace the static chip with a live selector
    host.innerHTML =
      '<span class="acct-label">Account</span>' +
      '<select id="ctx-account-select" class="ctx-account-select" title="Terminal-wide account context">' +
      opts.join("") + "</select>";
    var sel = document.getElementById("ctx-account-select");
    if (sel) {
      // a saved context may reference a removed account — verify it exists
      var ids = ["ALL"].concat(accounts.map(function (a) { return a.account_id; }));
      if (ids.indexOf(APP_CTX.accountId) < 0) APP_CTX.accountId = "ALL";
      sel.value = APP_CTX.accountId;
      sel.addEventListener("change", function () {
        ctxSetAccount(sel.value);
        render();   // re-render the current page under the new context
      });
    }
    renderTopbarAccountName();
  }

  function bindActions() {
    document.querySelectorAll("[data-href]").forEach(function (el) {
      el.addEventListener("click", function () {
        location.hash = el.getAttribute("data-href");
      });
    });

    // ① unified state-retry from apiStateBlock error/offline blocks —
    // re-renders the current route, which reloads the failed resource.
    var stRetry = document.querySelector('[data-action="state-retry"]:not([data-bound])');
    if (stRetry) {
      stRetry.setAttribute("data-bound", "1");
      stRetry.addEventListener("click", function () { render(); });
    }
    // Settings risk section has its own retry (local section refresh)
    var stgRetry = document.querySelector('[data-action="stg:risk-retry"]:not([data-bound])');
    if (stgRetry) {
      stgRetry.setAttribute("data-bound", "1");
      stgRetry.addEventListener("click", function () {
        stgLoadLive(true).then(function () { renderStgShell(); });
      });
    }

    // Design System demo: Modal & Drawer
    var demoModalBtn = document.querySelector('[data-action="ds-demo-modal"]');
    if (demoModalBtn) {
      demoModalBtn.addEventListener("click", function () {
        UI.openModal({
          title: "Add Trading Account",
          body:
            UI.field("Account Name", UI.input({ placeholder: "Main-Paper" })) +
            UI.field("Broker", UI.select({ options: ["IB", "CQG", "Binance"] })) +
            UI.field("Environment", UI.select({ options: ["Paper", "Shadow", "Live"] })) +
            UI.field("Capital", UI.input({ type: "number", placeholder: "100000" })),
          footer:
            UI.button("Cancel", "ghost", { action: "close-modal" }) +
            UI.button("Save", "primary", { action: "close-modal" }),
        });
      });
    }
    var demoDrawerBtn = document.querySelector('[data-action="ds-demo-drawer"]');
    if (demoDrawerBtn) {
      demoDrawerBtn.addEventListener("click", function () {
        UI.openDrawer({
          title: "Order #1024",
          body:
            '<div class="ds-flex ds-flex-col ds-gap-3">' +
            UI.badge("FILLED", "profit") +
            "<div><strong>NVDA</strong> · BUY · 100</div>" +
            UI.metricCard("Execution Price", "$182.31", "", "") +
            UI.metricCard("Slippage", "+0.03bp", "pos", "pos") +
            UI.metricCard("Latency", "12ms", "", "") +
            "</div>",
          footer: UI.button("Close", "secondary", { action: "close-drawer" }),
        });
      });
    }

    // Dashboard: nav:* buttons (View All → hash navigation)
    document.querySelectorAll('[data-action^="nav:"]').forEach(function (el) {
      el.addEventListener("click", function () {
        var navKey = el.getAttribute("data-action").slice(4);
        location.hash = "#/" + navKey;
      });
    });

    // Dashboard: refresh button (visual feedback only — mock data)
    var refreshBtn = document.querySelector('[data-action="dash:refresh"]');
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Refreshing…";
        setTimeout(function () {
          refreshBtn.disabled = false;
          refreshBtn.textContent = "Refresh";
          showToast("Dashboard refreshed / 仪表盘已刷新", "ok");
        }, 600);
      });
    }

    // Dashboard: period tabs (visual toggle — mock data)
    document.querySelectorAll(".ds-period-tabs").forEach(function (tabs) {
      tabs.querySelectorAll(".ds-period-tab").forEach(function (tab) {
        tab.addEventListener("click", function () {
          tabs.querySelectorAll(".ds-period-tab").forEach(function (t) {
            t.classList.remove("active");
          });
          tab.classList.add("active");
        });
      });
    });

    // Trading: bottom tabs (Positions / Orders / Executions)
    var trBottomTabs = document.getElementById("tr-bottom-tabs");
    if (trBottomTabs) {
      trBottomTabs.querySelectorAll(".ds-tab").forEach(function (tab) {
        tab.addEventListener("click", function () {
          trBottomTabs.querySelectorAll(".ds-tab").forEach(function (t) {
            t.classList.remove("active");
          });
          tab.classList.add("active");
          var target = tab.getAttribute("data-tab");
          ["positions", "orders", "executions"].forEach(function (name) {
            var el = document.getElementById("tr-tab-" + name);
            if (el) el.style.display = name === target ? "block" : "none";
          });
        });
      });
    }

    // Trading: chart timeframe tabs (visual toggle)
    document.querySelectorAll(".tr-tf-group").forEach(function (grp) {
      grp.querySelectorAll(".tr-tf").forEach(function (tf) {
        tf.addEventListener("click", function () {
          grp.querySelectorAll(".tr-tf").forEach(function (t) {
            t.classList.remove("active");
          });
          tf.classList.add("active");
        });
      });
    });
    // Trading: chart tool tabs (visual toggle)
    document.querySelectorAll(".tr-chart-tools").forEach(function (grp) {
      grp.querySelectorAll(".tr-tool").forEach(function (tool) {
        tool.addEventListener("click", function () {
          grp.querySelectorAll(".tr-tool").forEach(function (t) {
            t.classList.remove("active");
          });
          tool.classList.add("active");
        });
      });
    });

    // Trading: watchlist item click (visual selection)
    document.querySelectorAll(".tr-watchlist .tr-wl-item").forEach(function (item) {
      item.addEventListener("click", function () {
        item.parentElement.querySelectorAll(".tr-wl-item").forEach(function (i) {
          i.classList.remove("active");
        });
        item.classList.add("active");
      });
    });

    // Trading: Order Ticket — BUY/SELL toggle
    var otSide = document.getElementById("tr-ot-side");
    if (otSide) {
      otSide.querySelectorAll(".ds-seg").forEach(function (seg) {
        seg.addEventListener("click", function () {
          otSide.querySelectorAll(".ds-seg").forEach(function (s) {
            s.classList.remove("active");
          });
          seg.classList.add("active");
          var side = seg.getAttribute("data-value");
          var reviewBtn = document.getElementById("tr-ot-review");
          if (reviewBtn) {
            reviewBtn.setAttribute("data-side", side);
            reviewBtn.textContent = side === "BUY" ? "REVIEW BUY ORDER" : "REVIEW SELL ORDER";
            reviewBtn.className = "ds-btn ds-btn-primary tr-ot-submit" +
              (side === "SELL" ? " ds-btn-danger" : "");
          }
        });
      });
    }

    // Trading: Order Ticket — live notional calculation (Integration 003)
    // Uses the real quote price from _tradingState instead of a hardcoded 178.42.
    function updateNotional() {
      var qtyEl = document.getElementById("tr-ot-qty");
      var limitEl = document.getElementById("tr-ot-limit");
      var notionalEl = document.getElementById("tr-ot-notional");
      var typeEl = document.getElementById("tr-ot-type");
      if (!qtyEl || !notionalEl) return;
      var qty = parseFloat(qtyEl.value) || 0;
      var livePrice = (_tradingState.quote && _tradingState.quote.last_price) || 0;
      var limitPrice = parseFloat((limitEl && limitEl.value) || "0") || 0;
      var type = typeEl ? typeEl.value : "market";
      var effPrice = type === "market" ? livePrice : (limitPrice || livePrice);
      var notional = qty * effPrice;
      notionalEl.textContent = "$" + notional.toLocaleString("en-US", { maximumFractionDigits: 0 });
    }
    var otQty = document.getElementById("tr-ot-qty");
    var otLimit = document.getElementById("tr-ot-limit");
    var otType = document.getElementById("tr-ot-type");
    if (otQty) otQty.addEventListener("input", updateNotional);
    if (otLimit) otLimit.addEventListener("input", updateNotional);
    if (otType) {
      otType.addEventListener("change", function () {
        var limitField = document.getElementById("tr-ot-limit");
        if (limitField) {
          limitField.disabled = otType.value === "market";
          if (otType.value === "market") limitField.value = "";
        }
        updateNotional();
      });
    }

    // Trading: REVIEW ORDER → Preview → Submit (Integration 003 — real API)
    // Flow:  Review → useOrderPreview() → modal with risk_check →
    //        Submit → useOrderSubmit() → result (order_id / status / rejection)
    //        Duplicate-submit protection via _tradingState.submitting lock.
    var reviewBtn = document.getElementById("tr-ot-review");
    if (reviewBtn) {
      reviewBtn.addEventListener("click", async function () {
        var side = reviewBtn.getAttribute("data-side") || "BUY";
        var qtyVal = (document.getElementById("tr-ot-qty") || {}).value || "100";
        var typeVal = (document.getElementById("tr-ot-type") || {}).value || "market";
        var limitEl = document.getElementById("tr-ot-limit");
        var symbol = (_tradingState.quote && _tradingState.quote.symbol) || "NVDA";

        var ticket = {
          symbol: symbol,
          side: side,
          quantity: parseInt(qtyVal, 10) || 0,
          order_type: typeVal === "market" ? "MARKET" : "LIMIT",
          price: typeVal === "limit" ? (parseFloat((limitEl && limitEl.value) || "0") || null) : null,
        };

        // Loading state on the review button
        var origText = reviewBtn.textContent;
        reviewBtn.disabled = true;
        reviewBtn.textContent = "Loading preview...";

        try {
          var preview = await useOrderPreview(ticket);
          var rc = preview.risk_check || {};
          var blocked = rc.status === "BLOCKED";
          var warnings = rc.warnings || [];
          var livePrice = (_tradingState.quote && _tradingState.quote.last_price) || 0;

          var reviewHtml =
            '<div class="ds-stat-row"><span class="ds-stat-label">Symbol</span><span class="ds-stat-value ds-text-mono">' + esc(preview.symbol) + '</span></div>' +
            '<div class="ds-stat-row"><span class="ds-stat-label">Side</span><span class="ds-stat-value ds-stat-' + (preview.side === "BUY" ? "pos" : "neg") + '">' + preview.side + '</span></div>' +
            '<div class="ds-stat-row"><span class="ds-stat-label">Quantity</span><span class="ds-stat-value ds-text-mono">' + preview.quantity + '</span></div>' +
            '<div class="ds-stat-row"><span class="ds-stat-label">Order Type</span><span class="ds-stat-value">' + esc(preview.order_type) + '</span></div>' +
            '<div class="ds-stat-row"><span class="ds-stat-label">Price</span><span class="ds-stat-value ds-text-mono">$' + (preview.price || 0).toFixed(2) + '</span></div>' +
            '<div class="ds-stat-row"><span class="ds-stat-label">Last Price</span><span class="ds-stat-value ds-text-mono">$' + (preview.last_price || livePrice || 0).toFixed(2) + '</span></div>' +
            '<div class="ds-stat-row"><span class="ds-stat-label">Estimated Value</span><span class="ds-stat-value ds-stat-info ds-text-mono">' + UI.money(preview.estimated_value, 2) + '</span></div>' +
            '<div class="ds-stat-row"><span class="ds-stat-label">Risk Check</span><span class="ds-stat-value ds-stat-' + (blocked ? "neg" : "pos") + '">' + esc(rc.status || "UNKNOWN") + '</span></div>' +
            (warnings.length ? '<div class="ds-callout ds-callout-' + (blocked ? "danger" : "warning") + '" style="margin-top:var(--ds-space-sm);"><ul style="margin:0;padding-left:1.2em;">' + warnings.map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("") + "</ul></div>" : "") +
            '<div class="ds-stat-row" style="margin-top:var(--ds-space-sm);"><span class="ds-stat-label">Session</span><span class="ds-stat-value">' + (rc.session_running ? "Running" : "Not running") + '</span></div>' +
            '<div class="ds-stat-row"><span class="ds-stat-label">Pipeline</span><span class="ds-stat-value">' + (rc.pipeline_attached ? "Attached" : "Detached") + '</span></div>' +
            '<div class="ds-text-muted" style="font-size:var(--ds-text-xs);margin-top:var(--ds-space-sm);">Preview only — no order submitted. Click Submit to send through Risk → Order → Execution.</div>';

          UI.openModal({
            title: "Order Preview — " + preview.side + " " + preview.quantity + " " + esc(preview.symbol),
            body: reviewHtml,
            footer:
              '<button class="ds-btn ds-btn-ghost" data-action="close-modal">Cancel</button>' +
              '<button class="ds-btn ' + (preview.side === "SELL" ? "ds-btn-danger" : "ds-btn-primary") + '" id="tr-submit-order" ' + (blocked ? "disabled" : "") + '>SUBMIT ORDER</button>',
          });

          // Bind the submit button (with duplicate-submit protection)
          setTimeout(function () {
            var submitBtn = document.getElementById("tr-submit-order");
            if (!submitBtn) return;
            submitBtn.addEventListener("click", async function () {
              if (_tradingState.submitting) return;          // duplicate-submit lock
              _tradingState.submitting = true;
              var origSubmitText = submitBtn.textContent;
              submitBtn.disabled = true;
              submitBtn.textContent = "Submitting...";

              try {
                var result = await useOrderSubmit(ticket);
                UI.closeModal();

                // Build result display based on status
                var statusVariant = result.status === "FILLED" ? "pos" :
                  result.status === "REJECTED" ? "neg" :
                  result.status === "ERROR" ? "neg" : "warning";
                var order = result.order || {};
                var rd = result.risk_decision || {};

                var resultHtml =
                  '<div class="ds-stat-row"><span class="ds-stat-label">Status</span><span class="ds-stat-value ds-stat-' + statusVariant + '">' + esc(result.status) + '</span></div>' +
                  (order.order_id ? '<div class="ds-stat-row"><span class="ds-stat-label">Order ID</span><span class="ds-stat-value ds-text-mono">' + esc(order.order_id) + '</span></div>' : "") +
                  '<div class="ds-stat-row"><span class="ds-stat-label">Symbol</span><span class="ds-stat-value ds-text-mono">' + esc(order.symbol || ticket.symbol) + '</span></div>' +
                  '<div class="ds-stat-row"><span class="ds-stat-label">Side</span><span class="ds-stat-value ds-stat-' + (ticket.side === "BUY" ? "pos" : "neg") + '">' + ticket.side + '</span></div>' +
                  '<div class="ds-stat-row"><span class="ds-stat-label">Quantity</span><span class="ds-stat-value ds-text-mono">' + (order.quantity || ticket.quantity) + '</span></div>' +
                  (order.average_fill_price ? '<div class="ds-stat-row"><span class="ds-stat-label">Avg Fill Price</span><span class="ds-stat-value ds-text-mono">$' + order.average_fill_price.toFixed(2) + '</span></div>' : "") +
                  (order.filled_quantity ? '<div class="ds-stat-row"><span class="ds-stat-label">Filled Qty</span><span class="ds-stat-value ds-text-mono">' + order.filled_quantity + '</span></div>' : "") +
                  (rd.approved !== undefined ? '<div class="ds-stat-row"><span class="ds-stat-label">Risk Decision</span><span class="ds-stat-value ds-stat-' + (rd.approved ? "pos" : "neg") + '">' + (rd.approved ? "Approved" : "Rejected") + '</span></div>' : "") +
                  (rd.reason ? '<div class="ds-stat-row"><span class="ds-stat-label">Risk Reason</span><span class="ds-stat-value">' + esc(rd.reason) + '</span></div>' : "") +
                  (result.rejection_reason ? '<div class="ds-callout ds-callout-danger" style="margin-top:var(--ds-space-sm);"><strong>REJECTED:</strong> ' + esc(result.rejection_reason) + '</div>' : "");

                UI.openModal({
                  title: "Order Result — " + result.status,
                  body: resultHtml,
                  footer: '<button class="ds-btn ds-btn-primary" data-action="close-modal">Close</button>',
                });

                // Show toast + refresh the page to show the new order
                var toastType = result.status === "FILLED" ? "ok" : result.status === "REJECTED" ? "err" : "warn";
                showToast(ticket.side + " " + ticket.quantity + " " + ticket.symbol + " · " + result.status, toastType);

                // Refresh the trading page after a short delay
                setTimeout(function () { render(); }, 800);
              } catch (submitErr) {
                // Error during submit — show error in the modal
                submitBtn.disabled = false;
                submitBtn.textContent = origSubmitText;
                var errBody = '<div class="ds-callout ds-callout-danger">' +
                  '<strong>Submit failed:</strong> ' + esc((submitErr && submitErr.message) || String(submitErr)) +
                  '</div>' +
                  '<div class="ds-text-muted" style="margin-top:var(--ds-space-sm);">The order was not submitted. Click Submit to retry, or Cancel to close.</div>';
                var modalBody = document.querySelector(".ds-modal-body");
                if (modalBody) {
                  var errDiv = document.createElement("div");
                  errDiv.innerHTML = errBody;
                  modalBody.appendChild(errDiv);
                } else {
                  UI.closeModal();
                  showToast("Submit failed: " + ((submitErr && submitErr.message) || "unknown error"), "err");
                }
              } finally {
                _tradingState.submitting = false;
              }
            });
          }, 50);
        } catch (previewErr) {
          // Preview failed — show error toast, keep the ticket editable
          showToast("Preview failed: " + ((previewErr && previewErr.message) || "unknown error"), "err");
        } finally {
          reviewBtn.disabled = false;
          reviewBtn.textContent = origText;
        }
      });
    }

    // Trading: "New Order" button → focus order ticket
    var newOrderBtn = document.querySelector('[data-action="tr:focus-order"]');
    if (newOrderBtn) {
      newOrderBtn.addEventListener("click", function () {
        var ot = document.getElementById("tr-order-ticket");
        if (ot) {
          ot.scrollIntoView({ behavior: "smooth", block: "center" });
          var qtyEl = document.getElementById("tr-ot-qty");
          if (qtyEl) qtyEl.focus();
        }
      });
    }

    // Portfolio: export button (visual feedback — mock)
    var pfExportBtn = document.querySelector('[data-action="pf:export"]');
    if (pfExportBtn) {
      pfExportBtn.addEventListener("click", function () {
        pfExportBtn.disabled = true;
        pfExportBtn.textContent = "Exporting…";
        setTimeout(function () {
          pfExportBtn.disabled = false;
          pfExportBtn.textContent = "Export";
          showToast("Portfolio exported (mock) / 组合已导出", "ok");
        }, 800);
      });
    }

    // Orders (Integration 005): delegated row selection, filters, search,
    // pagination, refresh, cancel — all bound on #ord-root
    if (document.getElementById("ord-root")) {
      bindOrdersPage();
    }

    // Positions (Integration 006): delegated row selection, filters,
    // exposure, detail lifecycle, refresh — all bound on #pos-root
    if (document.getElementById("pos-root")) {
      bindPositionsPage();
    }

    // Research (Commit 010): factor row selection, experiment rows, refresh
    if (document.getElementById("rs-factor-tbody")) {
      bindResearchPage();
    }

    // Backtest (Commit 011): run button states, validation, loading/error
    if (document.getElementById("bt-results")) {
      bindBacktestPage();
    }

    // Strategy (Commit 012): row select, tabs, lifecycle, config, actions
    if (document.getElementById("st-detail")) {
      bindStrategiesPage();
    }

    // Risk (Commit 013): refresh button, event row detail, report button
    if (document.querySelector(".rk-status-bar")) {
      bindRiskPage();
    }

    // Execution (Commit 014): refresh button, timeline click
    if (document.querySelector(".ex-engine-bar")) {
      bindExecutionPage();
    }

    // Accounts (Commit 015): row select, add account, test connection
    if (document.getElementById("ac-list-tbody")) {
      bindAccountsPage();
    }

    // Settings (Commit 016 / Integration 016): section nav, env radios, save/reset
    if (document.getElementById("stg-page")) {
      bindSettingsPage();
    }

    // Data (Commit 017): dataset row select → detail update
    if (document.getElementById("dt-ds-tbody")) {
      bindDataPage();
    }

    // Monitoring (Commit 018): service row select → detail update + event filter
    if (document.getElementById("mo-svc-tbody")) {
      bindMonitoringPage();
    }

    // Alerts (Commit 019): row select → detail toggle + Ack / Resolve actions
    if (document.getElementById("al-tbody")) {
      bindAlertsPage();
    }

    // Design System: bind tabs
    var tabsContainer = document.getElementById("ds-tabs-container");
    if (tabsContainer) UI.bindTabs(tabsContainer);
    const startBtn = document.getElementById("btn-session-start");
    if (startBtn) {
      startBtn.addEventListener("click", async function () {
        try {
          await api.post("/dashboard/session/start");
          showToast("Paper session started / 模拟会话已启动", "ok");
          render();
        } catch (e) {
          showToast("Failed to start session: " + (e.message || e), "error");
        }
      });
    }
    const stopBtn = document.getElementById("btn-session-stop");
    if (stopBtn) {
      stopBtn.addEventListener("click", async function () {
        try {
          await api.post("/dashboard/session/stop");
          showToast("Paper session stopped / 模拟会话已停止", "ok");
          render();
        } catch (e) {
          showToast("Failed to stop session: " + (e.message || e), "error");
        }
      });
    }
    const cancelBtn = document.getElementById("btn-cancel-order");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", async function () {
        if (!confirm("Cancel this order? / 确认撤销该订单？")) return;
        try {
          await api.post("/dashboard/orders/" + encodeURIComponent(cancelBtn.getAttribute("data-order")) + "/cancel");
          showToast("Order cancelled / 订单已撤销", "ok");
          render();
        } catch (e) {
          showToast("Failed to cancel: " + (e.message || e), "error");
        }
      });
    }
    // Backtest page form
    const btForm = document.getElementById("bt-form");
    if (btForm) {
      btForm.addEventListener("submit", async function (ev) {
        ev.preventDefault();
        const btn = document.getElementById("btn-backtest-run");
        const out = document.getElementById("backtest-result");
        const symbols = Array.prototype.slice
          .call(btForm.querySelectorAll('input[name="bt-sym"]:checked'))
          .map(function (c) { return c.value; });
        if (!symbols.length) {
          showToast("Select at least one market / 至少选择一个市场", "error");
          return;
        }
        const body = {
          symbols: symbols,
          initial_capital: parseFloat(btForm.querySelector("#bt-capital").value) || 1_000_000,
        };
        const s = btForm.querySelector("#bt-start").value;
        const e = btForm.querySelector("#bt-end").value;
        if (s) body.start = s;
        if (e) body.end = e;
        btn.disabled = true;
        btn.textContent = "Running… / 回测中…";
        out.innerHTML = '<div class="card"><div class="empty">Running backtest… / 回测运行中…</div></div>';
        try {
          const data = await api.post("/dashboard/backtest/run", body);
          window.__backtestData = data; // cache for symbol tab switching
          out.innerHTML = renderBacktestResult(data);
        } catch (err) {
          out.innerHTML =
            '<div class="card"><div class="alert alert-critical" style="margin:0">Backtest failed / 回测失败: ' +
            esc(err.message || String(err)) + "</div></div>";
        } finally {
          btn.disabled = false;
          btn.textContent = "Run Backtest / 运行回测";
        }
      });
    }
    // Settings page form
    const cfgForm = document.getElementById("cfg-form");
    if (cfgForm) {
      cfgForm.addEventListener("submit", async function (ev) {
        ev.preventDefault();
        const btn = document.getElementById("btn-config-save");
        const body = {
          account_name: cfgForm.querySelector("#cfg-name").value,
          broker: cfgForm.querySelector("#cfg-broker").value,
          account_type: cfgForm.querySelector("#cfg-type").value,
          initial_capital: parseFloat(cfgForm.querySelector("#cfg-capital").value) || 1_000_000,
          currency: cfgForm.querySelector("#cfg-ccy").value,
          max_daily_loss_pct: parseFloat(cfgForm.querySelector("#cfg-daily").value),
          max_drawdown_pct: parseFloat(cfgForm.querySelector("#cfg-maxdd").value),
          risk_per_trade_pct: parseFloat(cfgForm.querySelector("#cfg-pertrade").value),
        };
        btn.disabled = true;
        btn.textContent = "Saving… / 保存中…";
        try {
          await api.post("/dashboard/config", body);
          showToast("Config saved / 配置已保存", "ok");
          render();
        } catch (err) {
          showToast("Save failed / 保存失败: " + (err.message || err), "error");
        } finally {
          btn.disabled = false;
          btn.textContent = "Save / 保存";
        }
      });
    }
    // Multi-panel chart symbol tabs (backtest page)
    document.querySelectorAll(".sym-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        const sym = tab.getAttribute("data-sym");
        document.querySelectorAll(".sym-tab").forEach(function (t) { t.classList.remove("active"); });
        tab.classList.add("active");
        const container = document.getElementById("chart-panel-container");
        if (!container) return;
        if (window.__backtestData && window.__backtestData.chart_panels) {
          const panel = window.__backtestData.chart_panels.find(function (p) { return p.symbol === sym; });
          if (panel) {
            container.innerHTML = multiPanelChart([panel]);
          }
        }
      });
    });
    // Test connection buttons (accounts page)
    document.querySelectorAll("[data-test-conn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showToast("Connection test: broker not connected (paper mode). / 连接测试：券商未连接（模拟模式）", "error");
      });
    });
    // Account settings test/save buttons
    const accTestBtn = document.getElementById("btn-acc-test");
    if (accTestBtn) {
      accTestBtn.addEventListener("click", function () {
        showToast("🔌 Test Connection: Not Connected (Paper Only). / 测试连接：未连接（仅模拟模式）", "error");
      });
    }
    const accSaveBtn = document.getElementById("btn-acc-save");
    if (accSaveBtn) {
      accSaveBtn.addEventListener("click", function () {
        showToast("Account settings saved (frontend only). / 账户设置已保存", "ok");
      });
    }
    // Audit filter apply
    const auditApplyBtn = document.getElementById("btn-audit-apply");
    if (auditApplyBtn) {
      auditApplyBtn.addEventListener("click", function () {
        showToast("Filters applied. / 过滤已应用", "ok");
        render();
      });
    }
  }

  function updateConnDot() {
    const dot = document.getElementById("conn-dot");
    const text = document.getElementById("conn-text");
    if (!dot || !text) return;
    const s = state.backend.status;
    if (s === "connected") {
      dot.className = "conn-dot up";
      text.textContent = "Backend connected / 后端已连接";
    } else if (s === "degraded") {
      dot.className = "conn-dot degraded";
      text.textContent = "Backend degraded / 后端降级";
    } else if (s === "disconnected") {
      dot.className = "conn-dot down";
      text.textContent = "Backend disconnected / 后端未连接";
    } else if (s === "probe") {
      dot.className = "conn-dot unknown";
      text.textContent = "Backend probing / 后端探测中";
    } else {
      dot.className = "conn-dot unknown";
      text.textContent = "Backend unknown / 后端未知";
    }
  }

  function setupLogin() {
    document.getElementById("login-form").addEventListener("submit", async function (ev) {
      ev.preventDefault();
      const btn = document.getElementById("login-btn");
      const errBox = document.getElementById("login-error");
      btn.disabled = true;
      btn.textContent = "Signing in… / 登录中…";
      errBox.classList.add("hidden");
      try {
        await api.login(
          document.getElementById("login-username").value,
          document.getElementById("login-password").value
        );
        location.hash = "#/overview";
        render();
      } catch (e) {
        errBox.textContent = e.message || "Login failed / 登录失败";
        errBox.classList.remove("hidden");
      } finally {
        btn.disabled = false;
        btn.textContent = "Sign In / 登录";
      }
    });
    document.getElementById("btn-logout").addEventListener("click", async function () {
      await api.logout();
      location.hash = "#/login";
      render();
    });
  }

  function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(function () {
      if (api.isAuthenticated() && location.hash && location.hash !== "#/login") {
        // static / interactive pages skip the 5s re-render:
        // factor = historical replay; backtest & settings hold form state
        if (location.hash.indexOf("#/factor") === 0) return;
        if (location.hash.indexOf("#/backtest") === 0) return;
        if (location.hash.indexOf("#/settings") === 0) return;
        if (location.hash.indexOf("#/audit") === 0) return;
        render();
      }
    }, state.refreshMs);
  }

  window.addEventListener("hashchange", render);

  setupLogin();
  startBackendHealthPolling(); // Integration 001: real connectivity probe
  startAutoRefresh();
  if (!location.hash) location.hash = "#/overview";
  render();
})();
