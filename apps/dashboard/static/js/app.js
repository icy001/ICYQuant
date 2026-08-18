/* ICYQuant Trading Dashboard - application logic.
 * Views: Overview / Strategy / Risk / Orders / Portfolio /
 *        Reconciliation / System / Alerts (all API-only). */
(function () {
  "use strict";

  const api = window.ICY_API;
  const state = {
    history: { equity: [], pnl: [], exposure: [] },
    refreshMs: 5000,
  };
  let refreshTimer = null;

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
    CREATED: ["badge-gray", "CREATED"],
    SUBMITTED: ["badge-blue", "SUBMITTED"],
    ACCEPTED: ["badge-blue", "ACCEPTED"],
    VALIDATED: ["badge-blue", "VALIDATED"],
    ROUTED: ["badge-blue", "ROUTED"],
    ACKNOWLEDGED: ["badge-blue", "ACKNOWLEDGED"],
    PARTIALLY_FILLED: ["badge-amber", "PARTIAL"],
    FILLED: ["badge-green", "FILLED"],
    REJECTED: ["badge-red", "REJECTED"],
    CANCELLED: ["badge-gray", "CANCELLED"],
  };

  function badge(text, cls) {
    return '<span class="badge ' + cls + '"><span class="dot"></span>' + esc(text) + "</span>";
  }

  function statusBadge(status) {
    const hit = ORDER_STATUS_BADGE[status] || ["badge-gray", status];
    return badge(hit[1], hit[0]);
  }

  function decisionBadge(decision) {
    if (decision === "APPROVED") return badge("APPROVED", "badge-green");
    if (decision === "REJECTED") return badge("REJECTED", "badge-red");
    return badge(esc(decision), "badge-gray");
  }

  function severityBadge(level) {
    const map = {
      CRITICAL: "badge-red",
      HIGH: "badge-amber",
      WARNING: "badge-blue",
      INFO: "badge-green",
    };
    return badge(level, map[level] || "badge-gray");
  }

  function healthBadge(status) {
    if (status === "UP") return badge("UP", "badge-green");
    if (status === "DOWN") return badge("DOWN", "badge-red");
    if (status === "DEGRADED") return badge("DEGRADED", "badge-amber");
    return badge(status || "UNKNOWN", "badge-gray");
  }

  function sideHtml(side) {
    const s = String(side || "").toUpperCase();
    return '<span class="' + (s === "BUY" ? "side-buy" : "side-sell") + '">' + esc(side) + "</span>";
  }

  function fmtMoneyCur(x, ccy) {
    const n = Number(x);
    if (!isFinite(n)) return "—";
    const sym = ccy === "CNY" ? "¥" : "$";
    const sign = n < 0 ? "-" : "";
    return sign + sym + Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 2 });
  }

  function connBadge(status) {
    if (status === "CONNECTED") return badge("CONNECTED", "badge-green");
    if (status === "ERROR") return badge("ERROR", "badge-red");
    if (status === "CONNECTING") return badge("CONNECTING", "badge-amber");
    return badge(status || "—", "badge-gray");
  }

  function accountsStrip(accounts) {
    if (!accounts || !accounts.by_market) return "";
    const cards = Object.keys(accounts.by_market)
      .map(function (label) {
        const a = accounts.by_market[label];
        return (
          '<a class="card metric-card clickable" href="#/accounts">' +
          '<span class="metric-label">' + esc(label) + " · " + connBadge(a.status) + "</span>" +
          '<span class="metric-value">' + fmtMoneyCur(a.equity, a.currency) + "</span>" +
          '<span class="metric-sub">' + esc(a.currency) + " account</span>" +
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
    return badge(market, map[market] || "badge-gray");
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
      return '<div class="empty">No data yet</div>';
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
    if (!total) return '<div class="empty">No positions</div>';
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
      '<text x="60" y="72" text-anchor="middle" fill="#64748b" font-size="8">QTY</text>' +
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
      ["Database", "database"],
      ["Event Bus", "event-bus"],
      ["Strategy Runtime", "strategy-runtime"],
      ["Risk Engine", "risk-engine"],
      ["Order Engine", "order-engine"],
      ["Execution Engine", "execution-engine"],
      ["Position / Ledger", "position-ledger"],
      ["Reconciliation", "reconciliation"],
      ["Monitoring", "monitoring"],
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
    return '<div class="card mb"><div class="card-title">System Status</div><div style="display:flex;flex-wrap:wrap;gap:8px">' + chips + "</div></div>";
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
      metric("Today's P&L", fmtMoney(m.today_pnl), pnlClass(m.today_pnl)) +
      metric("Equity", fmtMoney(m.equity), "pos") +
      metric("Exposure", fmtMoney(m.exposure)) +
      metric("Drawdown", fmtMoney(m.drawdown)) +
      metric("Orders", fmtNum(m.orders)) +
      metric("Executions", fmtNum(m.executions)) +
      metric("Fill Rate", fmtPct(m.fill_rate), "pos") +
      metric("Reject Rate", fmtPct(m.reject_rate), m.reject_rate > 0 ? "neg" : "") +
      "</div>";

    const charts =
      '<div class="grid grid-main mb">' +
      '<div class="card"><div class="card-title">Equity Curve</div>' +
      lineChart(hist.equity, { color: "#00e5a0", id: "eq" }) + "</div>" +
      '<div class="card"><div class="card-title">Exposure</div>' +
      donutChart(
        (data.positions || []).map(function (p) {
          return { label: p.symbol, value: p.exposure || 0, color: "#4da3ff" };
        }),
        {}
      ) + "</div></div>";

    const recentOrders =
      '<div class="card mb"><div class="card-title">Recent Orders</div>' +
      (data.recent_orders && data.recent_orders.length
        ? '<div class="table-wrap"><table><thead><tr><th>Order ID</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Status</th><th>Time</th></tr></thead><tbody>' +
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
          : '<div class="empty">No orders yet</div>') +
      "</div></div>";

    const recentDecisions =
      '<div class="card mb"><div class="card-title">Recent Risk Decisions</div>' +
      (data.recent_decisions && data.recent_decisions.length
        ? '<div class="table-wrap"><table><thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Decision</th><th>Reason</th><th>Time</th></tr></thead><tbody>' +
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
          : '<div class="empty">No decisions yet</div>') +
      "</div></div>";

    const alertsHtml =
      '<div class="card mb"><div class="card-title">System Alerts</div>' +
      (data.alerts && data.alerts.length
        ? data.alerts
            .map(function (a) {
              return (
                '<div class="alert alert-' + String(a.level).toLowerCase() + '">' +
                '<span class="alert-level">' + esc(a.level) + "</span>" +
                "<span>" + esc(a.source) + " · " + esc(a.message) + "</span>" +
                "</div>"
              );
            })
            .join("")
          : '<div class="empty">No alerts</div>') +
      "</div>";

    const sessionCtl = isOperator
      ? '<div class="card mb"><div class="card-title">Session Control</div>' +
        '<div style="display:flex;gap:10px;align-items:center">' +
        (session.running
          ? '<button class="btn btn-danger" id="btn-session-stop">Stop Paper Session</button>'
          : '<button class="btn btn-primary" id="btn-session-start">Start Paper Session</button>') +
        '<span class="metric-sub">' +
        (session.running ? "● running" : "○ idle") +
        (data.pipeline && data.pipeline.attached ? " · pipeline attached" : "") +
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
      '<div class="card"><div class="card-title">Risk Overview</div><div class="kv">' +
      "<dt>Decisions</dt><dd>" + fmtNum(r.decisions) + "</dd>" +
      "<dt>Approved</dt><dd class=\"pos\">" + fmtNum(r.approved) + "</dd>" +
      "<dt>Rejected</dt><dd class=\"neg\">" + fmtNum(r.rejected) + "</dd>" +
      "<dt>Exposure</dt><dd>" + fmtMoney(r.exposure) + "</dd>" +
      "<dt>Position Limit</dt><dd>" + fmtNum(r.position_limit) + "</dd>" +
      "</div></div>" +
      '<div class="card"><div class="card-title">Pipeline</div><div class="kv">' +
      "<dt>Status</dt><dd>" + (data.pipeline && data.pipeline.attached ? '<span class="badge badge-green"><span class="dot"></span>ATTACHED</span>' : '<span class="badge badge-gray"><span class="dot"></span>IDLE</span>') + "</dd>" +
      "<dt>Attached At</dt><dd>" + fmtDateTime(data.pipeline && data.pipeline.attached_at) + "</dd>" +
      "<dt>Events</dt><dd>" + fmtNum(data.pipeline && data.pipeline.events) + "</dd>" +
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
    if (!list.length) {
      return '<div class="card"><div class="empty">No strategies running.<br><br><span class="metric-sub">Start a paper session or run a Golden Scenario to see live strategy activity.</span></div></div>';
    }
    return (
      '<div class="card"><div class="card-title">Running Strategies</div>' +
      '<div class="table-wrap"><table><thead><tr>' +
      "<th>Strategy</th><th>Status</th><th>Symbols</th><th>Signals</th><th>Approved</th><th>Rejected</th><th>Position</th><th>P&amp;L</th>" +
      "</tr></thead><tbody>" +
      list
        .map(function (s) {
          return (
            '<tr class="clickable" data-href="#/strategies/' + esc(s.strategy_id) + '">' +
            "<td class=\"mono\">" + esc(s.strategy_id) + "</td>" +
            "<td>" + badge("RUNNING", "badge-green") + "</td>" +
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
    );
  }

  async function pageStrategyDetail(id) {
    const data = await api.get("/dashboard/strategies/" + encodeURIComponent(id));
    const sigTable =
      '<div class="card mb"><div class="card-title">Recent Signals</div>' +
      (data.signals && data.signals.length
        ? '<div class="table-wrap"><table><thead><tr><th>Signal</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Time</th></tr></thead><tbody>' +
          data.signals
            .map(function (s) {
              return (
                "<tr><td class=\"mono\">" + esc(s.signal_id) + "</td><td>" + esc(s.symbol) + "</td>" +
                "<td>" + sideHtml(s.side) + "</td><td class=\"num\">" + fmtNum(s.quantity) + "</td>" +
                "<td class=\"num\">" + fmtNum(s.price) + "</td><td class=\"mono\">" + fmtTime(s.timestamp) + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No signals</div>') +
      "</div></div>";

    const riskTable =
      '<div class="card mb"><div class="card-title">Risk Decisions</div>' +
      (data.risk_decisions && data.risk_decisions.length
        ? '<div class="table-wrap"><table><thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Decision</th><th>Reason</th><th>Time</th></tr></thead><tbody>' +
          data.risk_decisions
            .map(function (d) {
              return (
                "<tr><td>" + esc(d.symbol) + "</td><td>" + sideHtml(d.side) + "</td>" +
                "<td class=\"num\">" + fmtNum(d.quantity) + "</td><td>" + decisionBadge(d.decision) + "</td>" +
                "<td>" + esc(d.reason) + "</td><td class=\"mono\">" + fmtTime(d.timestamp) + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No decisions</div>') +
      "</div></div>";

    const orderTable =
      '<div class="card mb"><div class="card-title">Orders</div>' +
      (data.orders && data.orders.length
        ? '<div class="table-wrap"><table><thead><tr><th>Order ID</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Status</th></tr></thead><tbody>' +
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
          : '<div class="empty">No orders</div>') +
      "</div></div>";

    return (
      '<div class="card mb"><div class="kv" style="grid-template-columns:140px 1fr">' +
      "<dt>Strategy</dt><dd class=\"mono\">" + esc(data.strategy_id) + "</dd>" +
      "<dt>Status</dt><dd>" + badge(data.status, data.status === "RUNNING" ? "badge-green" : "badge-gray") + "</dd>" +
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
    const data = await api.get("/dashboard/risk");
    const m = data.metrics || {};
    const metric = function (label, value, cls) {
      return (
        '<div class="card metric-card"><span class="metric-label">' + esc(label) + "</span>" +
        '<span class="metric-value sm ' + (cls || "") + '">' + value + "</span></div>"
      );
    };
    return (
      '<div class="grid grid-4 mb">' +
      metric("Risk Decisions", fmtNum(m.decisions)) +
      metric("Approved", fmtNum(m.approved), "pos") +
      metric("Rejected", fmtNum(m.rejected), "neg") +
      metric("Risk Exposure", fmtMoney(m.exposure)) +
      metric("Daily Loss", fmtMoney(m.daily_loss)) +
      metric("Drawdown", fmtMoney(m.drawdown)) +
      metric("Position Limit", fmtNum(m.position_quantity) + " / " + fmtNum(m.position_limit), m.position_quantity >= m.position_limit ? "neg" : "") +
      metric("Order Limit", fmtNum(m.order_limit)) +
      "</div>" +
      '<div class="card"><div class="card-title">Risk Decision Pipeline</div>' +
      (data.decisions && data.decisions.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Time</th><th>Strategy</th><th>Symbol</th><th>Side</th><th>Quantity</th><th>Decision</th><th>Reason</th><th>Risk Rule</th>" +
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
                "<td>" + (d.decision === "APPROVED" ? "Risk Policy" : "Exposure / Quantity Limit") + "</td></tr>"
              );
            })
            .join("")
          : '<div class="empty">No risk decisions yet</div>') +
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
      '<div class="card"><div class="card-title">Orders (' + fmtNum(list.length) + ")</div>" +
      (list.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Order ID</th><th>Account</th><th>Broker</th><th>Symbol</th><th>Side</th><th>Quantity</th><th>Price</th><th>Status</th><th>Created</th>" +
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
          : '<div class="empty">No orders yet</div>') +
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
      '<div class="card mb"><div class="card-title">Order Trace</div><div class="flow">' +
      '<span class="flow-step ' + (data.signal ? "done" : "") + '">Signal</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (data.risk_decision ? (data.risk_decision.approved ? "done" : "active") : "") + '">Risk Decision</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (data.order ? "done" : "") + '">Order</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (data.execution ? "done" : "") + '">Execution</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (data.position ? "done" : "") + '">Position</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (data.ledger && data.ledger.length ? "done" : "") + '">Ledger</span>' +
      "</div></div>";

    const kv = function (title, obj) {
      const rows = Object.keys(obj)
        .map(function (k) {
          return "<dt>" + esc(k) + "</dt><dd>" + esc(obj[k]) + "</dd>";
        })
        .join("");
      return '<div class="card trace-card ' + title.toLowerCase().replace(/[^a-z]/g, "") + ' mb"><div class="trace-head">' + esc(title) + "</div><div class=\"kv\">" + rows + "</div></div>";
    };

    let blocks = "";
    if (data.signal) blocks += kv("Signal", {
      id: data.signal.signal_id,
      symbol: data.signal.symbol,
      side: data.signal.side,
      quantity: data.signal.quantity,
      price: data.signal.price,
      time: fmtTime(data.signal.timestamp),
    });
    if (data.risk_decision) blocks += kv("Risk Decision", {
      approved: data.risk_decision.approved ? "YES" : "NO",
      reason: data.risk_decision.reason || "—",
    });
    blocks += kv("Order", {
      id: o.order_id,
      strategy: o.strategy_id || "—",
      symbol: o.symbol,
      side: o.side,
      quantity: o.quantity,
      price: o.price,
      status: o.status,
      filled: o.filled_quantity || 0,
      avg_fill_price: o.average_fill_price || "—",
      created: fmtTime(o.created_at),
      updated: fmtTime(o.updated_at),
    });
    if (data.execution) blocks += kv("Execution", {
      quantity: data.execution.quantity,
      price: data.execution.price,
      time: fmtTime(data.execution.timestamp),
    });
    if (data.position) blocks += kv("Position", {
      symbol: data.position.symbol,
      quantity: data.position.quantity,
      avg_price: data.position.avg_price,
      unrealized_pnl: fmtMoney(data.position.unrealized_pnl),
    });
    if (data.ledger && data.ledger.length) {
      blocks += kv("Ledger Events", {
        count: data.ledger.length,
        events: data.ledger.map(function (e) { return e.event_type; }).join(", "),
      });
    }

    const cancelBtn = canCancel
      ? '<button class="btn btn-danger" id="btn-cancel-order" data-order="' + esc(o.order_id) + '">Cancel Order</button>'
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
      metric("Total Equity (USD)", fmtMoney(s.total_equity_usd), "pos") +
      metric("Total Cash (USD)", fmtMoney(s.total_cash_usd)) +
      metric("Gross Exposure (USD)", fmtMoney(s.gross_exposure_usd)) +
      metric("Net Exposure (USD)", fmtMoney(s.net_exposure_usd)) +
      metric("Daily P&L (USD)", fmtMoney(s.daily_pnl_usd), pnlClass(s.daily_pnl_usd)) +
      metric("Total P&L (USD)", fmtMoney(s.total_pnl_usd), pnlClass(s.total_pnl_usd)) +
      metric("Drawdown (USD)", fmtMoney(s.drawdown_usd)) +
      metric("Accounts", fmtNum((data.accounts || []).length)) +
      "</div>" +
      '<div class="grid grid-2 mb">' +
      '<div class="card"><div class="card-title">Market Exposure</div>' +
      donutChart(
        exposureEntries.map(function (e, i) {
          return { label: e.label, value: e.value, color: colorMap[i % colorMap.length] };
        }),
        {}
      ) + "</div>" +
      '<div class="card"><div class="card-title">Equity Curve</div>' +
      lineChart(hist.equity, { color: "#00e5a0", id: "pe" }) + "</div>" +
      "</div>" +
      '<div class="card"><div class="card-title">Global Positions (' + fmtNum((data.positions || []).length) + ")</div>" +
      (data.positions && data.positions.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Account</th><th>Market</th><th>Symbol</th><th>Side</th><th>Quantity</th><th>Avg Price</th><th>Last</th><th>Market Value</th><th>Unrealized P&amp;L</th><th>Exposure</th><th>Ccy</th>" +
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
          : '<div class="empty">No positions</div>') +
      "</div></div>"
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
      '<div class="card mb"><div class="card-title">Reconciliation Flow</div><div class="flow">' +
      '<span class="flow-step done">Detect</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step ' + (ok ? "done" : "active") + '">Classify</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step">Risk Decision</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step">Recovery</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step">Repair</span><span class="flow-arrow">→</span>' +
      '<span class="flow-step">Verify</span>' +
      "</div></div>";

    const statusCard =
      '<div class="card mb">' +
      '<div class="card-title">Reconciliation Status</div>' +
      (ok
        ? '<div style="display:flex;align-items:center;gap:14px">' +
          '<span style="font-size:34px">🟢</span>' +
          '<div><div style="font-size:18px;font-weight:700;color:var(--accent)">All States Consistent</div>' +
          '<div class="metric-sub">Position and Ledger are aligned.</div></div></div>'
        : '<div style="display:flex;align-items:center;gap:14px">' +
          '<span style="font-size:34px">⚠️</span>' +
          '<div><div style="font-size:18px;font-weight:700;color:var(--amber)">INCONSISTENCY</div>' +
          '<div class="metric-sub">' + esc(rec.detail || "") + "</div></div></div>") +
      "</div>";

    const compare =
      '<div class="grid grid-2 mb">' +
      '<div class="card metric-card"><span class="metric-label">Position (Internal)</span>' +
      '<span class="metric-value">' + fmtNum(rec.position) + "</span></div>" +
      '<div class="card metric-card"><span class="metric-label">Ledger (External)</span>' +
      '<span class="metric-value">' + fmtNum(rec.ledger) + "</span></div>" +
      "</div>";

    const accountRec =
      '<div class="card mb"><div class="card-title">Account Reconciliation (Adapter Layer)</div>' +
      (data.accounts && data.accounts.accounts && data.accounts.accounts.length
        ? '<div class="table-wrap"><table><thead><tr><th>Account</th><th>Market</th><th>Status</th>' +
          "<th>Equity (expected)</th><th>Equity (actual)</th><th>Differences</th></tr></thead><tbody>" +
          data.accounts.accounts
            .map(function (a) {
              return (
                "<tr>" +
                '<td class="mono">' + esc(a.account_id) + "</td>" +
                "<td>" + marketBadge(marketLabel(a.market)) + "</td>" +
                "<td>" + (a.status === "CONSISTENT" ? badge("CONSISTENT", "badge-green") : badge("INCONSISTENT", "badge-red")) + "</td>" +
                "<td class=\"num\">" + fmtNum(a.expected.equity) + "</td>" +
                "<td class=\"num\">" + fmtNum(a.actual.equity) + "</td>" +
                "<td>" + esc((a.differences || []).join(", ") || "none") + "</td></tr>"
              );
            })
            .join("")
        : '<div class="empty">No account state</div>') +
      "</div></div>";

    const details =
      '<div class="card mb"><div class="card-title">Details</div><div class="kv">' +
      "<dt>Status</dt><dd>" + (ok ? '<span class="badge badge-green"><span class="dot"></span>CONSISTENT</span>' : '<span class="badge badge-red"><span class="dot"></span>RECOVERY_REQUIRED</span>') + "</dd>" +
      "<dt>Detected At</dt><dd>" + fmtDateTime(rec.detected_at) + "</dd>" +
      "</div></div>";

    const ledger =
      '<div class="card"><div class="card-title">Ledger Events (recent)</div>' +
      (data.ledger_events && data.ledger_events.length
        ? '<div class="table-wrap"><table><thead><tr><th>Type</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Time</th></tr></thead><tbody>' +
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
          : '<div class="empty">No ledger events</div>') +
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
    return (
      '<div class="card mb"><div class="card-title">Broker Connections</div>' +
      '<div class="grid grid-4 mb">' +
      (data.health || []).map(function (h) {
        return (
          '<div class="card metric-card"><span class="metric-label">' + esc(h.broker_name) + "</span>" +
          '<span class="metric-value sm">' + healthBadge(h.status) + "</span>" +
          '<span class="metric-sub">' + esc(h.market) + " · " + fmtNum(h.latency_ms) + " ms</span></div>"
        );
      }).join("") +
      "</div></div>" +
      '<div class="card"><div class="card-title">Accounts (' + fmtNum(accounts.length) + ")</div>" +
      (accounts.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Account</th><th>Broker</th><th>Market</th><th>Status</th><th>Equity</th><th>Cash</th><th>Buying Power</th><th>Margin</th><th>Pos</th><th>Orders</th><th>Exec</th>" +
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
              "<td class=\"num\">" + fmtMoneyCur(a.buying_power, a.currency) + "</td>" +
              "<td class=\"num\">" + fmtMoneyCur(a.margin, a.currency) + "</td>" +
              "<td class=\"num\">" + fmtNum(a.positions) + "</td>" +
              "<td class=\"num\">" + fmtNum(a.orders) + "</td>" +
              "<td class=\"num\">" + fmtNum(a.executions) + "</td></tr>"
            );
          }).join("")
        : '<div class="empty">No accounts</div>') +
      "</div></div>"
    );
  }

  async function pageAccountDetail(accountId) {
    const data = await api.get("/dashboard/accounts/" + encodeURIComponent(accountId));
    if (!data.account_id) {
      return '<div class="card"><div class="card-title">Account</div><div class="empty">Account not found</div></div>';
    }
    const metric = function (label, value, cls) {
      return (
        '<div class="card metric-card"><span class="metric-label">' + esc(label) + "</span>" +
        '<span class="metric-value sm ' + (cls || "") + '">' + value + "</span></div>"
      );
    };
    const ccy = data.currency || "USD";
    const back = '<a class="btn btn-ghost mb" href="#/accounts">← All Accounts</a>';
    const head =
      '<div class="card mb"><div class="card-title">' + esc(data.name) +
      " · " + marketBadge(data.market_label) + " · " + connBadge(data.connection) + "</div>" +
      '<div class="kv"><dt>Account</dt><dd class="mono">' + esc(data.account_id) + "</dd>" +
      "<dt>Broker</dt><dd>" + esc(data.broker_name) + "</dd>" +
      "<dt>Status</dt><dd>" + badge(data.status, "badge-gray") + "</dd>" +
      "<dt>Capabilities</dt><dd>" + esc((data.capabilities || []).join(", ")) + "</dd></div></div>";
    const metrics =
      '<div class="grid grid-4 mb">' +
      metric("Equity", fmtMoneyCur(data.equity, ccy), "pos") +
      metric("Cash", fmtMoneyCur(data.cash, ccy)) +
      metric("Buying Power", fmtMoneyCur(data.buying_power, ccy)) +
      metric("Margin", fmtMoneyCur(data.margin, ccy)) +
      metric("Daily P&L", fmtMoneyCur(data.daily_pnl, ccy), pnlClass(data.daily_pnl)) +
      metric("Total P&L", fmtMoneyCur(data.total_pnl, ccy), pnlClass(data.total_pnl)) +
      metric("Exposure", fmtMoneyCur(data.exposure, ccy)) +
      metric("Drawdown", fmtMoneyCur(data.drawdown, ccy)) +
      "</div>";

    const positionsTable =
      '<div class="card mb"><div class="card-title">Positions (' + fmtNum((data.positions || []).length) + ")</div>" +
      (data.positions && data.positions.length
        ? '<div class="table-wrap"><table><thead><tr><th>Symbol</th><th>Side</th><th>Quantity</th><th>Avg Price</th><th>Last</th><th>Market Value</th><th>Unrealized P&amp;L</th><th>Margin</th></tr></thead><tbody>' +
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
        : '<div class="empty">No positions</div>') +
      "</div></div>";

    const ordersTable =
      '<div class="card mb"><div class="card-title">Orders (' + fmtNum((data.orders || []).length) + ")</div>" +
      (data.orders && data.orders.length
        ? '<div class="table-wrap"><table><thead><tr><th>Order ID</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Status</th><th>Time</th></tr></thead><tbody>' +
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
        : '<div class="empty">No orders</div>') +
      "</div></div>";

    const execTable =
      '<div class="card mb"><div class="card-title">Executions (' + fmtNum((data.executions || []).length) + ")</div>" +
      (data.executions && data.executions.length
        ? '<div class="table-wrap"><table><thead><tr><th>Execution ID</th><th>Order ID</th><th>Symbol</th><th>Side</th><th>Fill Qty</th><th>Fill Price</th><th>Slippage</th><th>Time</th></tr></thead><tbody>' +
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
        : '<div class="empty">No executions</div>') +
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
      '<div class="card"><div class="card-title">Executions (' + fmtNum(list.length) + ")</div>" +
      (list.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Execution ID</th><th>Order ID</th><th>Account</th><th>Market</th><th>Symbol</th><th>Side</th><th>Fill Qty</th><th>Fill Price</th><th>Slippage</th><th>Timestamp</th>" +
          "</tr></thead><tbody>" +
          list.map(function (e) {
            return (
              "<tr>" +
              "<td class=\"mono\">" + esc(String(e.execution_id).slice(0, 18)) + "</td>" +
              '<td class="mono">' + esc(String(e.order_id).slice(0, 14)) + "</td>" +
              '<td class="mono">' + esc(e.account_id || "paper") + "</td>" +
              "<td>" + (e.market ? marketBadge(marketLabel(e.market)) : badge("PAPER", "badge-gray")) + "</td>" +
              "<td>" + esc(e.symbol) + "</td>" +
              "<td>" + sideHtml(e.side) + "</td>" +
              "<td class=\"num\">" + fmtNum(e.fill_quantity) + "</td>" +
              "<td class=\"num\">" + fmtNum(e.fill_price) + "</td>" +
              "<td class=\"num\">" + fmtPct(e.slippage) + "</td>" +
              "<td class=\"mono\">" + fmtTime(e.timestamp) + "</td></tr>"
            );
          }).join("")
        : '<div class="empty">No executions yet</div>') +
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
      "api", "database", "event-bus", "strategy-runtime", "risk-engine",
      "order-engine", "execution-engine", "position-ledger", "reconciliation", "monitoring",
    ];
    const rows = order
      .map(function (name) {
        const s = services[name] || { status: "UNKNOWN", detail: "not registered" };
        return (
          '<div class="status-row">' +
          '<span class="svc-name">' + esc(name) + "</span>" +
          healthBadge(s.status) +
          '<span class="metric-sub">' + esc(s.detail) + "</span>" +
          "</div>"
        );
      })
      .join("");
    const d = data.dashboard || {};
    const hist = state.history;
    return (
      '<div class="card mb"><div class="card-title">Services</div>' + rows + "</div>" +
      '<div class="grid grid-2">' +
      '<div class="card"><div class="card-title">Application</div><div class="kv">' +
      "<dt>Version</dt><dd>" + esc(d.version || "—") + "</dd>" +
      "<dt>Environment</dt><dd>" + esc(d.environment || "—") + "</dd>" +
      "<dt>Pipeline</dt><dd>" + (d.attached ? '<span class="badge badge-green"><span class="dot"></span>ATTACHED</span>' : '<span class="badge badge-gray"><span class="dot"></span>IDLE</span>') + "</dd>" +
      "<dt>Attached At</dt><dd>" + fmtDateTime(d.attached_at) + "</dd>" +
      "</div></div>" +
      '<div class="card"><div class="card-title">Event Processing</div>' +
      lineChart(hist.pnl, { color: "#4da3ff", id: "sys" }) +
      '<div class="metric-sub mt">P&amp;L progression of the attached pipeline.</div></div>' +
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
      '<div class="card"><div class="card-title">Alerts (' + fmtNum(list.length) + ")</div>" +
      (list.length
        ? list
            .map(function (a) {
              return (
                '<div class="alert alert-' + String(a.level).toLowerCase() + '">' +
                '<span class="alert-level">' + esc(a.level) + "</span>" +
                "<span><b>" + esc(a.source) + "</b> · " + esc(a.message) + "</span>" +
                '<span class="metric-sub" style="margin-left:auto">' + fmtTime(a.timestamp) + "</span>" +
                "</div>"
              );
            })
            .join("")
          : '<div class="empty">No alerts — system is healthy.</div>') +
      "</div>"
    );
  }

  /* ==================================================================
   * Router
   * ================================================================== */

  const ROUTES = [
    { re: /^#\/overview$/, title: "Overview", render: pageOverview },
    { re: /^#\/strategies$/, title: "Strategy", render: pageStrategies },
    { re: /^#\/strategies\/(.+)$/, title: "Strategy Detail", render: function (m) { return pageStrategyDetail(decodeURIComponent(m[1])); } },
    { re: /^#\/risk$/, title: "Risk", render: pageRisk },
    { re: /^#\/orders$/, title: "Orders", render: pageOrders },
    { re: /^#\/orders\/(.+)$/, title: "Order Detail", render: function (m) { return pageOrderDetail(decodeURIComponent(m[1])); } },
    { re: /^#\/executions$/, title: "Executions", render: pageExecutions },
    { re: /^#\/portfolio$/, title: "Portfolio", render: pagePortfolio },
    { re: /^#\/accounts$/, title: "Accounts", render: pageAccounts },
    { re: /^#\/accounts\/(.+)$/, title: "Account Detail", render: function (m) { return pageAccountDetail(decodeURIComponent(m[1])); } },
    { re: /^#\/reconciliation$/, title: "Reconciliation", render: pageReconciliation },
    { re: /^#\/system$/, title: "System", render: pageSystem },
    { re: /^#\/alerts$/, title: "Alerts", render: pageAlerts },
  ];

  function showToast(msg, cls) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.className = "toast " + (cls || "");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function () {
      t.className = "toast hidden";
    }, 3500);
  }

  function setNavActive(hash) {
    document.querySelectorAll("#nav .nav-link").forEach(function (a) {
      a.classList.remove("active");
    });
    const map = {
      "#/overview": "overview",
      "#/strategies": "strategies",
      "#/risk": "risk",
      "#/orders": "orders",
      "#/executions": "executions",
      "#/portfolio": "portfolio",
      "#/accounts": "accounts",
      "#/reconciliation": "reconciliation",
      "#/system": "system",
      "#/alerts": "alerts",
    };
    let key = null;
    for (const prefix in map) {
      if (hash.indexOf(prefix) === 0) {
        key = map[prefix];
        break;
      }
    }
    if (key) {
      const el = document.querySelector('#nav .nav-link[data-nav="' + key + '"]');
      if (el) el.classList.add("active");
    }
  }

  async function render() {
    if (!api.isAuthenticated()) {
      document.getElementById("app-view").classList.add("hidden");
      document.getElementById("login-view").classList.remove("hidden");
      return;
    }
    document.getElementById("login-view").classList.add("hidden");
    document.getElementById("app-view").classList.remove("hidden");

    const hash = location.hash || "#/overview";
    const user = api.user;
    document.getElementById("user-badge").innerHTML =
      esc(user ? user.username : "") + " · <b>" + esc(user ? user.role : "") + "</b>";

    let route = ROUTES[0];
    for (let i = 0; i < ROUTES.length; i++) {
      if (ROUTES[i].re.test(hash)) { route = ROUTES[i]; break; }
    }
    document.getElementById("page-title").textContent = route.title;
    setNavActive(hash);

    const content = document.getElementById("page-content");
    content.innerHTML = '<div class="empty">Loading…</div>';
    try {
      const html = await route.render(hash.match(route.re));
      content.innerHTML = html;
      bindActions();
    } catch (err) {
      if (err && err.status === 401) {
        render();
        return;
      }
      content.innerHTML =
        '<div class="card"><div class="empty">Failed to load data.<br><span class="metric-sub">' +
        esc(err && err.message ? err.message : String(err)) +
        "</span></div></div>";
    }
    updateConnDot();
  }

  function bindActions() {
    document.querySelectorAll("[data-href]").forEach(function (el) {
      el.addEventListener("click", function () {
        location.hash = el.getAttribute("data-href");
      });
    });
    const startBtn = document.getElementById("btn-session-start");
    if (startBtn) {
      startBtn.addEventListener("click", async function () {
        try {
          await api.post("/dashboard/session/start");
          showToast("Paper session started", "ok");
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
          showToast("Paper session stopped", "ok");
          render();
        } catch (e) {
          showToast("Failed to stop session: " + (e.message || e), "error");
        }
      });
    }
    const cancelBtn = document.getElementById("btn-cancel-order");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", async function () {
        if (!confirm("Cancel this order?")) return;
        try {
          await api.post("/dashboard/orders/" + encodeURIComponent(cancelBtn.getAttribute("data-order")) + "/cancel");
          showToast("Order cancelled", "ok");
          render();
        } catch (e) {
          showToast("Failed to cancel: " + (e.message || e), "error");
        }
      });
    }
  }

  function updateConnDot() {
    const dot = document.getElementById("conn-dot");
    const text = document.getElementById("conn-text");
    if (api.isAuthenticated()) {
      dot.className = "conn-dot up";
      text.textContent = "API connected";
    } else {
      dot.className = "conn-dot down";
      text.textContent = "not connected";
    }
  }

  function setupLogin() {
    document.getElementById("login-form").addEventListener("submit", async function (ev) {
      ev.preventDefault();
      const btn = document.getElementById("login-btn");
      const errBox = document.getElementById("login-error");
      btn.disabled = true;
      btn.textContent = "Signing in…";
      errBox.classList.add("hidden");
      try {
        await api.login(
          document.getElementById("login-username").value,
          document.getElementById("login-password").value
        );
        location.hash = "#/overview";
        render();
      } catch (e) {
        errBox.textContent = e.message || "Login failed";
        errBox.classList.remove("hidden");
      } finally {
        btn.disabled = false;
        btn.textContent = "Sign In";
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
        render();
      }
    }, state.refreshMs);
  }

  window.addEventListener("hashchange", render);

  setupLogin();
  startAutoRefresh();
  if (!location.hash) location.hash = "#/overview";
  render();
})();
