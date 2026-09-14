/* ICYQuant Dashboard — A-share Market Data module.
 *
 * Two responsibilities, and only two:
 *
 *   1. §18 — the single place that knows the ``/api/market-data/*``
 *      paths.  Components call ``marketDataApi.*``; they never build a
 *      URL and never touch ``fetch`` themselves.
 *   2. §12 — the single place that knows what a market-data status
 *      *means*, so the FRESH/WARNING/STALE/INVALID/QUARANTINED palette
 *      is not re-derived in every panel.
 *
 * It is also the owner of the §6 REST polling loop: the interval is
 * configuration (meta tag or ``window.MARKET_DATA_POLL_INTERVAL_MS``),
 * never a literal inside a component.
 */
(function () {
  "use strict";

  var API = window.ICY_API;

  var DEFAULT_POLL_MS = 1000;
  var MIN_POLL_MS = 250;

  function _upper(value) {
    return String(value == null ? "" : value).toUpperCase();
  }

  function _num(value) {
    var n = Number(value);
    return isFinite(n) ? n : null;
  }

  /* ── §22 provenance / dev mode ─────────────────────────────────── */

  /*: Provenance (adapter + poll cadence + request URLs) is useful when
   *  building the pipeline and noise in production, so it is gated. */
  function devMode() {
    if (window.ICY_DEV === true) return true;
    try {
      if (window.localStorage && localStorage.getItem("icy_dev") === "1") {
        return true;
      }
    } catch (e) {
      /* storage disabled — treat as off */
    }
    return /(^|[?&#])dev(=1)?($|&)/.test(String(location.hash || "") + String(location.search || ""));
  }

  /* ── §6 polling interval ───────────────────────────────────────── */

  function pollIntervalMs() {
    var raw = window.MARKET_DATA_POLL_INTERVAL_MS;
    if (raw == null) {
      var meta = document.querySelector(
        'meta[name="market-data-poll-interval-ms"]'
      );
      raw = meta ? meta.getAttribute("content") : null;
    }
    var ms = Number(raw);
    if (!isFinite(ms) || ms < MIN_POLL_MS) return DEFAULT_POLL_MS;
    return Math.round(ms);
  }

  function setPollIntervalMs(ms) {
    var n = Number(ms);
    if (isFinite(n) && n >= MIN_POLL_MS) {
      window.MARKET_DATA_POLL_INTERVAL_MS = Math.round(n);
    }
    return pollIntervalMs();
  }

  /* ── §18 the market-data API client ────────────────────────────── */

  var marketDataApi = {
    /*: Path prefix, kept here so a future move is a one-line change. */
    base: "/market-data",

    /* ① Universe — the Dashboard's only source of instruments. */
    getInstruments: function (filters) {
      return API.get("/market-data/instruments", filters || undefined);
    },

    /* ② one symbol */
    getQuote: function (symbol) {
      return API.get("/market-data/quotes/" + encodeURIComponent(symbol));
    },

    /* ③ many symbols — one request, never N (§14 of the UI spec). */
    getQuotes: function (symbols) {
      var params = null;
      if (symbols && symbols.length) params = { symbols: symbols.join(",") };
      return API.get("/market-data/quotes", params);
    },

    /* ④ 1m bars — historical + realtime already merged server-side. */
    getBars: function (symbol, timeframe, limit, range) {
      var params = {
        symbol: symbol,
        timeframe: timeframe || "1m",
        limit: limit || 200,
      };
      if (range && range.start) params.start = range.start;
      if (range && range.end) params.end = range.end;
      return API.get("/market-data/bars", params);
    },

    /* ⑤ trading session — never re-derive this from a wall clock. */
    getSession: function () {
      return API.get("/market-data/session");
    },

    /* ⑥ quality verdict for one symbol */
    getQuality: function (symbol) {
      return API.get("/market-data/quality/" + encodeURIComponent(symbol));
    },

    /* ⑥' quality roll-up for the universe */
    getQualityOverview: function (limit) {
      return API.get(
        "/market-data/quality",
        limit ? { limit: limit } : undefined
      );
    },

    /* ⑦ system health */
    getHealth: function () {
      return API.get("/market-data/health");
    },
  };

  /* ── §12 one status vocabulary ─────────────────────────────────── */

  var STATUS_META = {
    LIVE: { label: "LIVE", tone: "ok" },
    FRESH: { label: "FRESH", tone: "ok" },
    WARNING: { label: "WARNING", tone: "warn" },
    STALE: { label: "STALE", tone: "warn" },
    INVALID: { label: "INVALID", tone: "bad" },
    QUARANTINED: { label: "QUARANTINED", tone: "bad" },
    OFFLINE: { label: "OFFLINE", tone: "neutral" },
  };

  function _statusMeta(status) {
    return STATUS_META[_upper(status)] || null;
  }

  function getMarketDataStatusLabel(status) {
    var meta = _statusMeta(status);
    return meta ? meta.label : "UNKNOWN";
  }

  function getMarketDataStatusTone(status) {
    var meta = _statusMeta(status);
    return meta ? meta.tone : "neutral";
  }

  function getMarketDataStatusClass(status) {
    return "md-qs md-qs-" + getMarketDataStatusTone(status);
  }

  function getMarketDataStatusHint(status) {
    switch (_upper(status)) {
      case "LIVE":
      case "FRESH":
        return "数据新鲜";
      case "WARNING":
        return "需要关注";
      case "STALE":
        return "数据过期";
      case "INVALID":
        return "数据异常";
      case "QUARANTINED":
        return "已隔离";
      default:
        return "暂无行情";
    }
  }

  /*: A status that must not be dressed up as "live". */
  function isMarketDataDegraded(status) {
    var tone = getMarketDataStatusTone(status);
    return tone === "warn" || tone === "bad";
  }

  function showsLiveBadge(status) {
    var tone = getMarketDataStatusTone(status);
    return tone === "ok" && _upper(status) !== "UNKNOWN";
  }

  /* ── §10 session phases are named, not computed ────────────────── */

  var PHASE_DISPLAY = {
    PRE_OPEN: "PRE-OPEN",
    AUCTION: "OPENING AUCTION",
    CONTINUOUS_AM: "MARKET OPEN",
    CONTINUOUS_PM: "MARKET OPEN",
    LUNCH_BREAK: "LUNCH BREAK",
    CLOSE: "MARKET CLOSED",
    POST_CLOSE: "MARKET CLOSED",
  };

  function sessionPhaseLabel(phase) {
    return PHASE_DISPLAY[_upper(phase)] || "MARKET CLOSED";
  }

  function sessionPhaseTone(phase) {
    switch (_upper(phase)) {
      case "CONTINUOUS_AM":
      case "CONTINUOUS_PM":
        return "ok";
      case "PRE_OPEN":
      case "AUCTION":
      case "LUNCH_BREAK":
        return "warn";
      default:
        return "neutral";
    }
  }

  /* ── §13 health vocabulary ─────────────────────────────────────── */

  var HEALTH_TONE = {
    HEALTHY: "ok",
    DEGRADED: "warn",
    BLOCKED: "bad",
    OFFLINE: "neutral",
  };

  var COMPONENT_LABEL = {
    UP: "UP",
    DEGRADED: "DEGRADED",
    DOWN: "DOWN",
    DISABLED: "DISABLED",
    UNKNOWN: "UNKNOWN",
  };

  function healthStatusLabel(status) {
    var key = _upper(status);
    return HEALTH_TONE[key] ? key : "OFFLINE";
  }

  function getHealthStatusClass(status) {
    return "md-hs md-hs-" + (HEALTH_TONE[healthStatusLabel(status)] || "neutral");
  }

  function componentStatusLabel(status) {
    return COMPONENT_LABEL[_upper(status)] || "UNKNOWN";
  }

  /* ── §6 polling loop with a real lifecycle ─────────────────────── */

  var _timers = {};

  function startPoll(key, fn, ms) {
    stopPoll(key);
    if (typeof fn !== "function") return null;
    _timers[key] = window.setInterval(function () {
      // A background tab must not keep hammering the API.
      if (
        typeof document !== "undefined" &&
        document.visibilityState &&
        document.visibilityState !== "visible"
      ) {
        return;
      }
      try {
        fn();
      } catch (err) {
        /* one failed tick must never kill the loop */
      }
    }, ms || pollIntervalMs());
    return _timers[key];
  }

  function stopPoll(key) {
    if (_timers[key]) {
      window.clearInterval(_timers[key]);
      delete _timers[key];
    }
  }

  function stopAllPolls() {
    Object.keys(_timers).forEach(function (key) {
      stopPoll(key);
    });
  }

  function hasPoll(key) {
    return !!_timers[key];
  }

  /* ── §8/§9 bar series keyed by timestamp, not by index ─────────── */

  function createBarStore() {
    var byTs = {};
    var order = [];

    function keyOf(bar) {
      if (!bar || bar.timestamp == null) return null;
      return String(bar.timestamp);
    }

    function changed(a, b) {
      return (
        a.close !== b.close ||
        a.high !== b.high ||
        a.low !== b.low ||
        a.open !== b.open ||
        a.volume !== b.volume ||
        a.is_closed !== b.is_closed
      );
    }

    /*: Idempotent merge — re-fetching an unchanged bar is not an update. */
    function merge(bars) {
      var touched = 0;
      (bars || []).forEach(function (bar) {
        var key = keyOf(bar);
        if (!key) return;
        if (!Object.prototype.hasOwnProperty.call(byTs, key)) {
          byTs[key] = bar;
          order.push(key);
          touched += 1;
        } else if (changed(byTs[key], bar)) {
          byTs[key] = bar;
          touched += 1;
        }
      });
      // ISO-8601 strings from one exchange share an offset, so a plain
      // lexical sort is a chronological sort — ascending by construction.
      order.sort();
      return touched;
    }

    function bars() {
      return order.map(function (key) {
        return byTs[key];
      });
    }

    function last() {
      return order.length ? byTs[order[order.length - 1]] : null;
    }

    function reset() {
      byTs = {};
      order = [];
    }

    /*: Drop the oldest keys so a long session cannot grow without
     *  bound.  The chart shows the newest ``limit`` bars, so trimming
     *  is display-neutral. */
    function trim(limit) {
      var n = Number(limit);
      if (!isFinite(n) || n <= 0 || order.length <= n) return 0;
      var drop = order.splice(0, order.length - n);
      drop.forEach(function (key) {
        delete byTs[key];
      });
      return drop.length;
    }

    return {
      merge: merge,
      bars: bars,
      last: last,
      reset: reset,
      trim: trim,
      size: function () {
        return order.length;
      },
    };
  }

  /* ── formatting shared by the market-data panels ───────────────── */

  function formatAge(ms) {
    var n = _num(ms);
    if (n == null) return "—";
    if (n < 1000) return Math.round(n) + " ms";
    if (n < 60000) return (n / 1000).toFixed(1) + "s";
    return Math.round(n / 60000) + "m";
  }

  function formatCount(value) {
    var n = _num(value);
    if (n == null) return "—";
    return n.toLocaleString("en-US");
  }

  function formatTurnover(value) {
    var n = _num(value);
    if (n == null) return "—";
    var abs = Math.abs(n);
    if (abs >= 1e8) return (n / 1e8).toFixed(2) + " 亿";
    if (abs >= 1e4) return (n / 1e4).toFixed(2) + " 万";
    return n.toFixed(2);
  }

  /*: A-share ETF/LOF tick is 0.001, so three decimals is the natural
   *  price precision.  A missing price renders as an em dash — never 0. */
  function formatPrice(value, tickSize) {
    var n = _num(value);
    if (n == null) return "—";
    var decimals = 3;
    var tick = _num(tickSize);
    if (tick != null && tick > 0) {
      var s = String(tick);
      var dot = s.indexOf(".");
      decimals = dot >= 0 ? s.length - dot - 1 : 0;
      if (decimals > 6) decimals = 6;
    }
    return n.toFixed(decimals);
  }

  /*: Signed percentage with a fixed 2 decimals — the §5 display form. */
  function formatPct(value) {
    var n = _num(value);
    if (n == null) return "—";
    return (n > 0 ? "+" : "") + n.toFixed(2) + "%";
  }

  /*: Direction class used by the quote / watch cells (§14 palette). */
  function directionOf(value) {
    var n = _num(value);
    if (n == null || n === 0) return "neutral";
    return n > 0 ? "pos" : "neg";
  }

  /*: §5 — prefer the API's own change; compute only as a fallback. */
  function quoteChange(quote) {
    if (!quote) return { change: null, pct: null, prev: null };
    var last = _num(quote.last);
    var prev = _num(quote.pre_close);
    var change = _num(quote.change);
    var pct = _num(quote.change_pct);
    if (change == null && last != null && prev != null) change = last - prev;
    if (pct == null && change != null && prev) pct = (change / prev) * 100;
    return { change: change, pct: pct, prev: prev };
  }

  window.ICY_MD = {
    api: marketDataApi,
    devMode: devMode,
    pollIntervalMs: pollIntervalMs,
    setPollIntervalMs: setPollIntervalMs,
    startPoll: startPoll,
    stopPoll: stopPoll,
    stopAllPolls: stopAllPolls,
    hasPoll: hasPoll,
    createBarStore: createBarStore,
    formatAge: formatAge,
    formatCount: formatCount,
    formatTurnover: formatTurnover,
    formatPrice: formatPrice,
    formatPct: formatPct,
    directionOf: directionOf,
    quoteChange: quoteChange,
    getMarketDataStatusLabel: getMarketDataStatusLabel,
    getMarketDataStatusClass: getMarketDataStatusClass,
    getMarketDataStatusTone: getMarketDataStatusTone,
    getMarketDataStatusHint: getMarketDataStatusHint,
    isMarketDataDegraded: isMarketDataDegraded,
    showsLiveBadge: showsLiveBadge,
    sessionPhaseLabel: sessionPhaseLabel,
    sessionPhaseTone: sessionPhaseTone,
    healthStatusLabel: healthStatusLabel,
    getHealthStatusClass: getHealthStatusClass,
    componentStatusLabel: componentStatusLabel,
    STATUS: STATUS_META,
    DEFAULT_POLL_MS: DEFAULT_POLL_MS,
  };

  /* §18 alias — the name the spec uses in components. */
  window.marketDataApi = marketDataApi;
})();
