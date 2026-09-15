/* ==================================================================
 * ICYQuant Dashboard — Broker Account / Position Sync client (Commit 015)
 *
 * §16 / §17 — the front end talks to ICYQuant's own API only:
 *
 *     Dashboard → /api/accounts/* → AccountService → Snapshot
 *
 * It never reaches a broker.  That is why this file has no vendor
 * vocabulary in it: it knows the §12 status vocabulary, the §10
 * reconciliation verdicts and the response shapes, and nothing else.
 *
 * Two rules are encoded here rather than in each panel:
 *
 *   * **A verdict is not a colour.**  STATUS / HEALTH / RECONCILIATION
 *     tone mapping lives in one place, so a MISMATCH can never be painted
 *     green by a component that forgot the mapping.
 *   * **An absent number stays absent.**  `null` renders as "—", never as
 *     0, so an unvalued position (§18) is visibly unvalued instead of
 *     looking like a zero-value holding.
 */
(function () {
  "use strict";

  var API = window.ICY_API;

  /* ── §12 account status vocabulary ─────────────────────────────── */

  var STATUS_META = {
    CONNECTED: { tone: "info", label: "CONNECTED", zh: "已连接" },
    SYNCING: { tone: "warning", label: "SYNCING", zh: "同步中" },
    SYNCED: { tone: "profit", label: "SYNCED", zh: "已同步" },
    STALE: { tone: "warning", label: "STALE", zh: "数据过期" },
    MISMATCH: { tone: "danger", label: "MISMATCH", zh: "持仓不符" },
    ERROR: { tone: "danger", label: "ERROR", zh: "错误" },
    OFFLINE: { tone: "neutral", label: "OFFLINE", zh: "离线" },
  };

  /* §14 roll-up health (Monitor vocabulary, Commit 013). */
  var HEALTH_META = {
    HEALTHY: { tone: "profit", label: "HEALTHY", zh: "正常" },
    DEGRADED: { tone: "warning", label: "DEGRADED", zh: "降级" },
    BLOCKED: { tone: "danger", label: "BLOCKED", zh: "已阻断" },
    OFFLINE: { tone: "neutral", label: "OFFLINE", zh: "离线" },
  };

  /* §10 reconciliation verdicts. */
  var RECON_META = {
    RECONCILED: { tone: "profit", label: "PASS", zh: "一致" },
    MISMATCH: { tone: "danger", label: "MISMATCH", zh: "不一致" },
    MISSING_BROKER: { tone: "danger", label: "MISSING @BROKER", zh: "券商缺失" },
    MISSING_LEDGER: { tone: "danger", label: "MISSING @LEDGER", zh: "账本缺失" },
    INVALID: { tone: "danger", label: "INVALID", zh: "无效" },
  };

  var CHECK_LABELS = {
    ACCOUNT_BALANCE: "账户资金",
    POSITION_QUANTITY: "持仓数量",
    AVAILABLE_QUANTITY: "可用数量",
    AVERAGE_COST: "持仓成本",
    MARKET_VALUE: "持仓市值",
  };

  function _upper(v) {
    return String(v == null ? "" : v).toUpperCase();
  }

  function meta(table, key, fallbackTone) {
    var m = table[_upper(key)];
    return m || { tone: fallbackTone || "neutral", label: _upper(key) || "UNKNOWN", zh: "" };
  }

  function statusMeta(status) { return meta(STATUS_META, status); }
  function healthMeta(health) { return meta(HEALTH_META, health); }
  function reconMeta(status) { return meta(RECON_META, status, "warning"); }
  function checkLabel(check) { return CHECK_LABELS[_upper(check)] || _upper(check); }

  /* §11 — blocking is a consequence of the verdict, derived here once. */
  function isBlocked(syncStatus) {
    if (!syncStatus) return false;
    if (syncStatus.new_orders_blocked === true) return true;
    return _upper(syncStatus.status) === "MISMATCH";
  }

  /* ── number / time formatting ──────────────────────────────────── */

  var DASH = "—";

  function _num(v) {
    if (v === null || v === undefined || v === "") return null;
    var n = Number(v);
    return isFinite(n) ? n : null;
  }

  function fmtMoney(v, decimals) {
    var n = _num(v);
    if (n === null) return DASH;
    return "¥" + n.toLocaleString("zh-CN", {
      minimumFractionDigits: decimals == null ? 2 : decimals,
      maximumFractionDigits: decimals == null ? 2 : decimals,
    });
  }

  function fmtSignedMoney(v) {
    var n = _num(v);
    if (n === null) return DASH;
    return (n >= 0 ? "+¥" : "-¥") + Math.abs(n).toLocaleString("zh-CN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function fmtPrice(v, decimals) {
    var n = _num(v);
    if (n === null) return DASH;
    return n.toFixed(decimals == null ? 3 : decimals);
  }

  function fmtQty(v) {
    var n = _num(v);
    if (n === null) return DASH;
    return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
  }

  function fmtPct(v) {
    var n = _num(v);
    if (n === null) return DASH;
    // The API sends a ratio (0.0234 → "+2.34%").
    var scaled = Math.abs(n) <= 1.5 ? n * 100 : n;
    return (scaled >= 0 ? "+" : "") + scaled.toFixed(2) + "%";
  }

  function fmtLatency(ms) {
    var n = _num(ms);
    if (n === null) return DASH;
    return n >= 1000 ? (n / 1000).toFixed(2) + "s" : Math.round(n) + "ms";
  }

  function fmtAge(seconds) {
    var n = _num(seconds);
    if (n === null) return DASH;
    if (n < 60) return Math.round(n) + "s";
    if (n < 3600) return Math.floor(n / 60) + "m " + Math.round(n % 60) + "s";
    return Math.floor(n / 3600) + "h " + Math.floor((n % 3600) / 60) + "m";
  }

  /* §13 — always show the broker's clock and ours, never just ours. */
  function fmtTime(iso) {
    if (!iso) return DASH;
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    return d.toLocaleTimeString("zh-CN", { hour12: false }) +
      "." + String(d.getMilliseconds()).padStart(3, "0");
  }

  function fmtDateTime(iso) {
    if (!iso) return DASH;
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    return d.toLocaleString("zh-CN", { hour12: false });
  }

  /* ── §15 API client ────────────────────────────────────────────── */

  var accountsApi = {
    base: "/accounts",

    list: function () {
      return API.get("/accounts");
    },

    detail: function (accountId) {
      return API.get("/accounts/" + encodeURIComponent(accountId));
    },

    getBalance: function (accountId) {
      return API.get("/accounts/" + encodeURIComponent(accountId) + "/balance");
    },

    getPositions: function (accountId) {
      return API.get("/accounts/" + encodeURIComponent(accountId) + "/positions");
    },

    getSyncStatus: function (accountId) {
      return API.get("/accounts/" + encodeURIComponent(accountId) + "/sync-status");
    },

    getSnapshots: function (accountId, limit) {
      return API.get("/accounts/" + encodeURIComponent(accountId) + "/snapshots", {
        limit: limit || 20,
      });
    },

    health: function () {
      return API.get("/accounts/health");
    },

    connect: function () {
      return API.post("/accounts/connect");
    },

    disconnect: function () {
      return API.post("/accounts/disconnect");
    },

    /* Operator action (§6) — the Dashboard never triggers this on a poll. */
    sync: function (accountId, connect) {
      return API.post(
        "/accounts/" + encodeURIComponent(accountId) + "/sync" +
          (connect === false ? "?connect=false" : "")
      );
    },
  };

  /* ── §16 table schemas ─────────────────────────────────────────── */

  var POSITION_COLUMNS = [
    { key: "symbol", label: "Symbol", sortable: true },
    { key: "name", label: "Name / 名称" },
    { key: "quantity", label: "Qty / 数量", numeric: true, format: fmtQty },
    { key: "available_quantity", label: "Available / 可用", numeric: true, format: fmtQty },
    { key: "frozen_quantity", label: "Frozen / 冻结", numeric: true, format: fmtQty },
    { key: "average_cost", label: "Cost / 成本", numeric: true, format: fmtPrice },
    { key: "market_price", label: "Price / 现价", numeric: true, format: fmtPrice },
    { key: "market_value", label: "Market Value / 市值", numeric: true, format: fmtMoney },
    {
      key: "unrealized_pnl",
      label: "P&L / 盈亏",
      numeric: true,
      format: fmtSignedMoney,
      color: function (v) { var n = _num(v); return n == null ? "" : (n >= 0 ? "pos" : "neg"); },
    },
    {
      key: "unrealized_pnl_pct",
      label: "P&L % / 收益率",
      numeric: true,
      format: fmtPct,
      color: function (v) { var n = _num(v); return n == null ? "" : (n >= 0 ? "pos" : "neg"); },
    },
    {
      key: "status",
      label: "Status",
      format: function (v) {
        // §3 / §21 — an INVALID position must be visible, not silently listed.
        var m = _upper(v) === "INVALID"
          ? { tone: "danger", label: "INVALID" }
          : { tone: "profit", label: "VALID" };
        return UI.statusPill(m.label, m.tone);
      },
    },
  ];

  var SNAPSHOT_COLUMNS = [
    { key: "sequence", label: "#", numeric: true, format: function (v) { return v == null ? DASH : "#" + v; } },
    { key: "snapshot_id", label: "Snapshot ID" },
    { key: "timestamp", label: "Broker Time / 券商时间", format: fmtTime },
    { key: "received_timestamp", label: "Received / 接收时间", format: fmtTime },
    { key: "sync_latency_ms", label: "Latency", numeric: true, format: fmtLatency },
    { key: "position_count", label: "Positions", numeric: true, format: fmtQty },
    { key: "source", label: "Source" },
    {
      key: "reconciliation_status",
      label: "Reconciliation",
      format: function (v) {
        if (!v) return DASH;
        var m = reconMeta(v);
        return UI.statusPill(m.label, m.tone);
      },
    },
  ];

  var RECON_ITEM_COLUMNS = [
    { key: "symbol", label: "Symbol" },
    { key: "check", label: "Check / 检查项", format: checkLabel },
    { key: "broker_value", label: "Broker / 券商", numeric: true, format: function (v, row) { return _fmtByCheck(row.check, v); } },
    { key: "ledger_value", label: "Ledger / 账本", numeric: true, format: function (v, row) { return _fmtByCheck(row.check, v); } },
    { key: "difference", label: "Diff / 差异", numeric: true, format: function (v, row) { return _fmtByCheck(row.check, v); },
      color: function (v) { var n = _num(v); return n == null || n === 0 ? "" : "neg"; } },
    {
      key: "status",
      label: "Status",
      format: function (v) {
        var m = reconMeta(v);
        return UI.statusPill(m.label, m.tone);
      },
    },
  ];

  function _fmtByCheck(check, value) {
    if (_upper(check) === "AVERAGE_COST") return fmtPrice(value);
    if (_upper(check) === "POSITION_QUANTITY" || _upper(check) === "AVAILABLE_QUANTITY") {
      return fmtQty(value);
    }
    return fmtMoney(value);
  }

  window.ICY_ACCOUNTS = {
    api: accountsApi,
    STATUS: STATUS_META,
    HEALTH: HEALTH_META,
    RECONCILIATION: RECON_META,
    statusMeta: statusMeta,
    healthMeta: healthMeta,
    reconMeta: reconMeta,
    checkLabel: checkLabel,
    isBlocked: isBlocked,
    POSITION_COLUMNS: POSITION_COLUMNS,
    SNAPSHOT_COLUMNS: SNAPSHOT_COLUMNS,
    RECON_ITEM_COLUMNS: RECON_ITEM_COLUMNS,
    fmtMoney: fmtMoney,
    fmtSignedMoney: fmtSignedMoney,
    fmtPrice: fmtPrice,
    fmtQty: fmtQty,
    fmtPct: fmtPct,
    fmtLatency: fmtLatency,
    fmtAge: fmtAge,
    fmtTime: fmtTime,
    fmtDateTime: fmtDateTime,
    DASH: DASH,
  };

  /* Alias used by the spec's components. */
  window.accountsApi = accountsApi;
})();
