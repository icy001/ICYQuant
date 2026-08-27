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
    { re: /^#\/factor$/, title: "Factor / 因子纸面交易", render: pageFactor },
    { re: /^#\/backtest$/, title: "Backtest / 回测", render: pageBacktest },
    { re: /^#\/settings$/, title: "Settings / 设置", render: pageSettings },
    { re: /^#\/risk$/, title: "Risk / 风控", render: pageRisk },
    { re: /^#\/reconciliation$/, title: "Reconciliation / 对账", render: pageReconciliation },
    { re: /^#\/system$/, title: "System / 系统", render: pageSystem },
    { re: /^#\/alerts$/, title: "Alerts / 告警", render: pageAlerts },
    { re: /^#\/audit$/, title: "Audit / 审计日志", render: pageAuditLog },
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
      "#/factor": "factor",
      "#/backtest": "backtest",
      "#/settings": "settings",
      "#/risk": "risk",
      "#/reconciliation": "reconciliation",
      "#/system": "system",
      "#/alerts": "alerts",
      "#/audit": "audit",
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
  startAutoRefresh();
  if (!location.hash) location.hash = "#/overview";
  render();
})();
