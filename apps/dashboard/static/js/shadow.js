/* ==================================================================
 * ICYQuant Dashboard — Shadow Trading page (Commit 016)
 *
 * §22 — real market data, real decision chain, simulated fills only.
 * The front end talks to /api/shadow/* and nothing else; it has no
 * broker vocabulary in it because there is no broker order path to
 * name (§25).
 *
 * Rules encoded here rather than in each panel:
 *
 *   * **The §22 banner is verbatim.**  Every response carries
 *     ``mode: "SHADOW"`` / ``real_orders_enabled: false``; the page
 *     renders the last received values as-is, so the sentence can
 *     never be paraphrased away by a UI edit (same rule as the Paper
 *     disclaimer).
 *   * **A verdict is not a colour.**  Order-status and event-type
 *     tone mapping lives in the tables below.
 *   * **An absent number stays absent.**  ``null`` renders as "—",
 *     never as 0.
 *
 * Lifecycle (same contract as the Market Data page): the framework
 * mounts the shell, this module owns the DOM and a visibility-aware
 * 10s poll; leaving the route stops the poll.
 */
(function () {
  "use strict";

  var API = window.ICY_API;
  var POLL_MS = 10000;
  var DASH = "—";

  var S = {
    status: null,
    orders: [],
    fills: [],
    positions: null,      // { items, broker_comparison }
    pnl: null,
    events: [],
    banner: { mode: "SHADOW", real_orders_enabled: false }, // §22 verbatim
    error: null,
    loading: false,
    timer: null,
  };

  /* ── tone vocabulary (one mapping, not one per panel) ─────────── */

  var ORDER_TONE = {
    FILLED: "profit",
    PARTIALLY_FILLED: "info",
    PENDING: "info",
    SUBMITTED: "info",
    REJECTED: "loss",
    CANCELLED: "neutral",
    EXPIRED: "neutral",
  };

  var EVENT_VARIANT = {
    SESSION_STARTED: "info",
    SESSION_STOPPED: "neutral",
    SIGNAL: "info",
    RISK_DECISION: "warning",
    ORDER_INTENT: "neutral",
    ORDER_ACCEPTED: "info",
    ORDER_REJECTED: "loss",
    ORDER_CANCELLED: "neutral",
    FILL: "profit",
    POSITION_UPDATE: "purple",
    PNL_UPDATE: "purple",
  };

  var FEED_TONE = {
    READY: "profit",
    HEALTHY: "profit",
    DEGRADED: "warning",
    OFFLINE: "loss",
    BLOCKED: "loss",
    UNKNOWN: "neutral",
  };

  /* ── formatters — an absent number stays absent ───────────────── */

  function _num(v) {
    if (v === null || v === undefined || v === "") return null;
    var n = Number(v);
    return isFinite(n) ? n : null;
  }

  function esc(v) {
    return UI.esc(v == null ? "" : String(v));
  }

  function fmtNum(v, decimals) {
    var n = _num(v);
    if (n === null) return DASH;
    return n.toLocaleString("en-US", {
      minimumFractionDigits: decimals == null ? 2 : decimals,
      maximumFractionDigits: decimals == null ? 2 : decimals,
    });
  }

  function fmtSigned(v) {
    var n = _num(v);
    if (n === null) return DASH;
    return (n >= 0 ? "+" : "-") + fmtNum(Math.abs(n));
  }

  function fmtQty(v) {
    var n = _num(v);
    return n === null ? DASH : n.toLocaleString("en-US", { maximumFractionDigits: 0 });
  }

  function fmtBps(v) {
    var n = _num(v);
    return n === null ? DASH : n.toFixed(1) + " bps";
  }

  function fmtTime(iso) {
    if (!iso) return DASH;
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    var p = function (x) { return (x < 10 ? "0" : "") + x; };
    // plain text — every consumer (UI.table / statRows / timeline)
    // applies its own escaping
    return (
      d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) +
      " " + p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds())
    );
  }

  function orderBadge(status) {
    var key = String(status || "").toUpperCase();
    return UI.badge(key || "UNKNOWN", ORDER_TONE[key] || "neutral");
  }

  function feedBadge(state) {
    var key = String(state || "UNKNOWN").toUpperCase();
    return UI.badge(key, FEED_TONE[key] || "neutral");
  }

  /* ── §22 banner — rendered verbatim from the last response ────── */

  function bannerView() {
    var b = S.banner;
    var real = b.real_orders_enabled === true;
    return (
      '<div class="alert alert-warning" style="margin:0 0 var(--ds-space-md, 16px) 0">' +
      '<span class="alert-level">' + esc(b.mode || "SHADOW") + "</span>" +
      "<div>Real orders <b>" + (real ? "ENABLED" : "DISABLED") + "</b> — " +
      "real market data · real decision chain · simulated fills only / " +
      "真实行情 · 真实决策链 · 仅模拟成交</div></div>"
    );
  }

  /* ── Session Status card (§23) ────────────────────────────────── */

  function statusView() {
    var st = S.status || {};
    var feed = st.feed || {};
    var c = st.counts || {};
    return (
      UI.kpiGrid(
        UI.metricCard("Shadow Orders", fmtQty(c.orders), "", "") +
        UI.metricCard("Simulated Fills", fmtQty(c.fills), "", "pos") +
        UI.metricCard("Rejected", fmtQty(c.rejected), "", "neg") +
        UI.metricCard("Ledger Events", fmtQty(c.events), "", "")
      , 4) +
      UI.statRows([
        { label: "Session", value: st.running ? "RUNNING" : "STOPPED",
          variant: st.running ? "pos" : "default" },
        { label: "Started At", value: fmtTime(st.started_at) },
        { label: "Market Feed", value: String(feed.state || "UNKNOWN").toUpperCase() },
        { label: "Feed Source", value: String(feed.source || DASH).toUpperCase() },
        { label: "Poll Interval", value: (POLL_MS / 1000) + "s (visibility-aware)" },
      ])
    );
  }

  /* ── PnL card (§23) ───────────────────────────────────────────── */

  function pnlView() {
    var p = S.pnl || {};
    var daily = _num(p.daily_pnl);
    var total = _num(p.total_pnl);
    var dd = _num(p.drawdown);
    return (
      UI.kpiGrid(
        UI.metricCard("Equity", fmtNum(p.equity), "", "") +
        UI.metricCard("Daily PnL", fmtSigned(p.daily_pnl), "",
          daily == null ? "" : daily >= 0 ? "pos" : "neg") +
        UI.metricCard("Total PnL", fmtSigned(p.total_pnl), "",
          total == null ? "" : total >= 0 ? "pos" : "neg") +
        UI.metricCard("Drawdown", fmtNum(p.drawdown), "",
          dd == null || dd === 0 ? "" : "neg")
      , 4) +
      UI.statRows([
        { label: "Initial Capital", value: fmtNum(p.initial_capital), mono: true },
        { label: "Cash", value: fmtNum(p.cash), mono: true },
        { label: "Market Value", value: fmtNum(p.market_value), mono: true },
        { label: "Realized PnL", value: fmtSigned(p.realized_pnl), mono: true },
        { label: "Unrealized PnL", value: fmtSigned(p.unrealized_pnl), mono: true },
        { label: "Peak Equity", value: fmtNum(p.peak_equity), mono: true },
        { label: "Day", value: p.day || DASH },
      ])
    );
  }

  /* ── Positions card + §18 broker comparison ───────────────────── */

  function positionsView() {
    var d = S.positions || {};
    var items = d.items || [];
    if (!items.length) return UI.empty("No open positions", "Shadow fills will open positions here.");
    var rows = items.map(function (r) {
      return {
        symbol: r.symbol,
        quantity: fmtQty(r.quantity),
        avg_cost: fmtNum(r.avg_cost, 3),
        market_price: fmtNum(r.market_price, 3),
        market_value: fmtNum(r.market_value),
        unrealized: fmtSigned(r.unrealized_pnl),
      };
    });
    return UI.table({
      columns: [
        { key: "symbol", label: "Symbol" },
        { key: "quantity", label: "Qty", numeric: true },
        { key: "avg_cost", label: "Avg Cost", numeric: true },
        { key: "market_price", label: "Market Price", numeric: true },
        { key: "market_value", label: "Market Value", numeric: true },
        { key: "unrealized", label: "Unrealized PnL", numeric: true },
      ],
      rows: rows,
      sortable: false,
    });
  }

  function brokerComparisonView() {
    var cmp = (S.positions && S.positions.broker_comparison) || {};
    if (!Object.keys(cmp).length) return "";
    var rows = [];
    Object.keys(cmp).forEach(function (k) {
      rows.push({ label: k, value: String(cmp[k]) });
    });
    return UI.statRows(rows);
  }

  /* ── Orders card — newest first, status badge + reject reason ─── */

  function ordersView() {
    if (!S.orders.length) return UI.empty("No shadow orders", "The decision chain will place simulated orders here.");
    // API returns newest last; show newest first.
    var rows = S.orders.slice().reverse().map(function (o) {
      return {
        time: fmtTime(o.created_at),
        symbol: o.symbol,
        side: o.side,
        qty: fmtQty(o.quantity),
        type: o.order_type,
        strategy: o.strategy_id,
        status: orderBadge(o.status),
        reason: o.reason || DASH,
      };
    });
    return UI.table({
      columns: [
        { key: "time", label: "Time" },
        { key: "symbol", label: "Symbol" },
        { key: "side", label: "Side" },
        { key: "qty", label: "Qty", numeric: true },
        { key: "type", label: "Type" },
        { key: "strategy", label: "Strategy" },
        { key: "status", label: "Status",
          format: function (v) { return v; } },
        { key: "reason", label: "Reason" },
      ],
      rows: rows,
      sortable: false,
    });
  }

  /* ── Fills card (§7 field set) ────────────────────────────────── */

  function fillsView() {
    if (!S.fills.length) return UI.empty("No simulated fills", "Fills price against real quotes only.");
    var rows = S.fills.slice().reverse().map(function (f) {
      return {
        time: fmtTime(f.execution_timestamp || f.market_timestamp),
        symbol: f.symbol,
        side: f.side,
        qty: fmtQty(f.quantity),
        price: fmtNum(f.price, 3),
        source: f.price_source,
        slippage: fmtBps(f.slippage_bps),
        commission: fmtNum(f.commission),
      };
    });
    return UI.table({
      columns: [
        { key: "time", label: "Time" },
        { key: "symbol", label: "Symbol" },
        { key: "side", label: "Side" },
        { key: "qty", label: "Qty", numeric: true },
        { key: "price", label: "Fill Price", numeric: true },
        { key: "source", label: "Price Source" },
        { key: "slippage", label: "Slippage", numeric: true },
        { key: "commission", label: "Commission", numeric: true },
      ],
      rows: rows,
      sortable: false,
    });
  }

  /* ── Decision Trail (§19): signal → risk → order → fill → … ──── */

  function eventTitle(ev) {
    var p = ev.payload || {};
    var bits = [];
    if (p.symbol) bits.push(String(p.symbol));
    if (p.side) bits.push(String(p.side).toUpperCase());
    if (p.quantity != null) bits.push(fmtQty(p.quantity));
    return bits.join(" ");
  }

  function eventDesc(ev) {
    var p = ev.payload || {};
    var bits = [];
    if (p.strategy_id) bits.push("strategy " + p.strategy_id);
    if (p.reason) bits.push("reason " + p.reason);
    if (p.intent_id) bits.push("intent " + p.intent_id);
    if (p.order_id) bits.push("order " + p.order_id);
    if (p.status) bits.push("status " + p.status);
    return bits.join(" · ");
  }

  function eventsView() {
    if (!S.events.length) return UI.empty("No events yet", "The §19 decision trail will appear here.");
    var items = S.events.slice().reverse().slice(0, 40).map(function (ev) {
      var type = String(ev.type || "").toUpperCase();
      return {
        time: fmtTime(ev.timestamp),
        type: type,
        title: eventTitle(ev) || type,
        desc: eventDesc(ev),
        variant: EVENT_VARIANT[type] || "neutral",
      };
    });
    return UI.timeline(items);
  }

  /* ── data loading — every response re-asserts the §22 banner ──── */

  /*: The banner is derived from responses, not from local state, so a
   * mis-rendered "LIVE" can only ever come from the API itself. */
  function adoptBanner(resp) {
    if (!resp || typeof resp !== "object") return;
    if (resp.mode != null) S.banner.mode = String(resp.mode);
    if (resp.real_orders_enabled != null) {
      S.banner.real_orders_enabled = resp.real_orders_enabled === true;
    }
  }

  function loadAll() {
    if (S.loading) return Promise.resolve();
    S.loading = true;
    S.error = null;
    return Promise.all([
      API.get("/shadow/status"),
      API.get("/shadow/orders", { limit: 50 }),
      API.get("/shadow/fills", { limit: 50 }),
      API.get("/shadow/positions"),
      API.get("/shadow/pnl"),
      API.get("/shadow/events", { limit: 120 }),
    ]).then(function (rs) {
      adoptBanner(rs[0]);
      S.status = rs[0];
      S.orders = rs[1].items || [];
      S.fills = rs[2].items || [];
      S.positions = rs[3];
      S.pnl = rs[4];
      S.events = rs[5].items || [];
      S.loading = false;
      paint();
    }).catch(function (err) {
      S.loading = false;
      S.error = (err && err.message) || String(err);
      paint();
    });
  }

  /* Start/Stop need OPERATOR/ADMIN — a 403 arrives as a normal API
   * error and is shown in place, not swallowed. */
  function sessionAction(path) {
    return API.post(path).then(function (resp) {
      adoptBanner(resp);
      return loadAll();
    }).catch(function (err) {
      S.error = (err && err.message) || String(err);
      paint();
    });
  }

  /* ── page assembly ────────────────────────────────────────────── */

  function pageActions() {
    var st = S.status || {};
    var running = st.running === true;
    return (
      (running
        ? UI.button("Stop Session", "danger", { sm: true, id: "sh-stop" })
        : UI.button("Start Session", "primary", { sm: true, id: "sh-start" })) +
      UI.button("Refresh", "ghost", { sm: true, id: "sh-refresh" })
    );
  }

  function errorBlock() {
    return UI.stateError(
      "Failed to load shadow session",
      (S.error || "Unknown error") + " · Click Retry to re-attempt.",
      "Retry", "sh-retry"
    );
  }

  function pageBody() {
    if (S.error && !S.status) return errorBlock();
    var cmp = brokerComparisonView();
    return (
      bannerView() +
      UI.sectionHeading("Session Status") +
      UI.panel("Session", statusView(),
        { actions: feedBadge(((S.status || {}).feed || {}).state) }) +
      UI.sectionHeading("Shadow PnL") +
      UI.panel("PnL Card", pnlView()) +
      UI.sectionHeading("Shadow Positions") +
      UI.panel("Positions", positionsView()) +
      (cmp
        ? UI.sectionHeading("Broker Comparison (§18)") +
          UI.panel("Ledger vs Broker (read-only)", cmp)
        : "") +
      UI.sectionHeading("Shadow Orders") +
      UI.panel("Orders", ordersView()) +
      UI.sectionHeading("Simulated Fills") +
      UI.panel("Fills", fillsView()) +
      UI.sectionHeading("Decision Trail (§19)") +
      UI.panel("Event Ledger", eventsView())
    );
  }

  /* ── lifecycle: paint, bind, visibility-aware poll ────────────── */

  function paint() {
    var host = document.getElementById("sh-page");
    if (!host) return;         // route changed — poll will self-stop
    host.innerHTML =
      UI.pageHeader("Shadow Trading",
        "Real market · simulated fills / 影子交易", pageActions()) +
      pageBody();
    bind();
  }

  function bind() {
    var el;
    if ((el = document.getElementById("sh-refresh"))) {
      el.addEventListener("click", function () { loadAll(); });
    }
    if ((el = document.getElementById("sh-start"))) {
      el.addEventListener("click", function () { sessionAction("/shadow/start"); });
    }
    if ((el = document.getElementById("sh-stop"))) {
      el.addEventListener("click", function () { sessionAction("/shadow/stop"); });
    }
    if ((el = document.querySelector('[data-action="sh-retry"]'))) {
      el.addEventListener("click", function () { S.error = null; loadAll(); });
    }
  }

  function stopPoll() {
    if (S.timer) { clearInterval(S.timer); S.timer = null; }
  }

  function startPoll() {
    stopPoll();
    S.timer = setInterval(function () {
      // visibility-aware: skip hidden tabs and unmounted routes
      if (document.hidden) return;
      if (!document.getElementById("sh-page")) { stopPoll(); return; }
      loadAll();
    }, POLL_MS);
  }

  /* Framework contract (like system/data): return a shell immediately,
   * hydrate async, own the poll from there. */
  function render() {
    loadAll();
    startPoll();
    return (
      '<div id="sh-page">' +
      UI.pageHeader("Shadow Trading", "Real market · simulated fills / 影子交易") +
      UI.stateLoading("Loading shadow session", "Fetching status, PnL, orders and the decision trail…") +
      "</div>"
    );
  }

  window.ShadowTradingPage = { render: render, stop: stopPoll };
})();