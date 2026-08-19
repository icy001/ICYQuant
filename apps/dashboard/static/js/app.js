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
    if (!list.length) {
      return '<div class="card"><div class="empty">No strategies running / 暂无运行中策略.<br><br><span class="metric-sub">Start a paper session or run a Golden Scenario to see live strategy activity. / 启动模拟会话或运行 Golden Scenario 即可看到实时策略活动。</span></div></div>';
    }
    return (
      '<div class="card"><div class="card-title">Running Strategies / 运行中策略</div>' +
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
    );
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
      metric("Risk Decisions / 风控决策", fmtNum(m.decisions)) +
      metric("Approved / 通过", fmtNum(m.approved), "pos") +
      metric("Rejected / 拒绝", fmtNum(m.rejected), "neg") +
      metric("Exposure / 风险敞口", fmtMoney(m.exposure)) +
      metric("Daily Loss / 当日亏损", fmtMoney(m.daily_loss)) +
      metric("Drawdown / 回撤", fmtMoney(m.drawdown)) +
      metric("Position Limit / 持仓限制", fmtNum(m.position_quantity) + " / " + fmtNum(m.position_limit), m.position_quantity >= m.position_limit ? "neg" : "") +
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
    return (
      '<div class="card mb"><div class="card-title">Broker Connections / 券商连接</div>' +
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
      '<div class="card"><div class="card-title">Accounts / 账户 (' + fmtNum(accounts.length) + ")</div>" +
      (accounts.length
        ? '<div class="table-wrap"><table><thead><tr>' +
          "<th>Account / 账户</th><th>Broker / 券商</th><th>Market / 市场</th><th>Status / 状态</th><th>Equity / 总权益</th><th>Cash / 现金</th><th>Buying Power / 可用资金</th><th>Margin / 保证金</th><th>Pos / 持仓</th><th>Orders / 订单</th><th>Exec / 成交</th>" +
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
   * Router
   * ================================================================== */

  const ROUTES = [
    { re: /^#\/overview$/, title: "Dashboard / 仪表盘", render: pageOverview },
    { re: /^#\/accounts$/, title: "Accounts / 账户", render: pageAccounts },
    { re: /^#\/portfolio$/, title: "Portfolio / 组合", render: pagePortfolio },
    { re: /^#\/positions$/, title: "Positions / 持仓", render: pagePositions },
    { re: /^#\/orders$/, title: "Orders / 订单", render: pageOrders },
    { re: /^#\/executions$/, title: "Executions / 成交", render: pageExecutions },
    { re: /^#\/strategies$/, title: "Strategies / 策略", render: pageStrategies },
    { re: /^#\/risk$/, title: "Risk / 风控", render: pageRisk },
    { re: /^#\/reconciliation$/, title: "Reconciliation / 对账", render: pageReconciliation },
    { re: /^#\/system$/, title: "System / 系统", render: pageSystem },
    { re: /^#\/alerts$/, title: "Alerts / 告警", render: pageAlerts },
    { re: /^#\/strategies\/(.+)$/, title: "Strategy Detail / 策略详情", render: function (m) { return pageStrategyDetail(decodeURIComponent(m[1])); } },
    { re: /^#\/orders\/(.+)$/, title: "Order Detail / 订单详情", render: function (m) { return pageOrderDetail(decodeURIComponent(m[1])); } },
    { re: /^#\/accounts\/(.+)$/, title: "Account Detail / 账户详情", render: function (m) { return pageAccountDetail(decodeURIComponent(m[1])); } },
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
      "#/accounts": "accounts",
      "#/portfolio": "portfolio",
      "#/positions": "positions",
      "#/orders": "orders",
      "#/executions": "executions",
      "#/strategies": "strategies",
      "#/risk": "risk",
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
    content.innerHTML = '<div class="empty">Loading… / 加载中…</div>';
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
        '<div class="card"><div class="empty">Failed to load data / 数据加载失败.<br><span class="metric-sub">' +
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
  }

  function updateConnDot() {
    const dot = document.getElementById("conn-dot");
    const text = document.getElementById("conn-text");
    if (api.isAuthenticated()) {
      dot.className = "conn-dot up";
      text.textContent = "API connected / 已连接";
    } else {
      dot.className = "conn-dot down";
      text.textContent = "not connected / 未连接";
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
