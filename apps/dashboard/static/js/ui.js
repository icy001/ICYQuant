/* ==========================================================================
 * ICYQuant Design System — UI Component Builders
 * Vanilla JS functions that return HTML strings.
 * Mount to DOM, then call UI.mount* for interactive components.
 *
 * Usage:
 *   content.innerHTML = UI.metricCard("Equity", "$1,087,000", "+7.32%", "pos");
 *   UI.openModal({ title: "Add Account", body: formHTML });
 * ========================================================================== */
(function (global) {
  "use strict";

  var UI = {};

  // ── Helpers ──────────────────────────────────────────────────────
  function esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmtNum(n, opts) {
    opts = opts || {};
    var decimals = opts.decimals != null ? opts.decimals : 2;
    var prefix = opts.prefix || "";
    var suffix = opts.suffix || "";
    var sign = opts.signed ? (n >= 0 ? "+" : "") : "";
    var abs = Math.abs(n);
    var formatted = abs.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
    return sign + prefix + formatted + suffix;
  }

  function pct(n, decimals) {
    if (decimals == null) decimals = 2;
    var sign = n >= 0 ? "+" : "";
    return sign + (n * 100).toFixed(decimals) + "%";
  }

  function money(n, decimals) {
    if (decimals == null) decimals = 2;
    var sign = n >= 0 ? "" : "-";
    return sign + "$" + Math.abs(n).toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  function signedMoney(n) {
    var sign = n >= 0 ? "+" : "-";
    return sign + "$" + Math.abs(n).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  // ── Page Header ──────────────────────────────────────────────────
  UI.pageHeader = function (title, desc, actions) {
    return (
      '<div class="page-header">' +
      '<div class="page-header-text">' +
      '<h2 class="page-header-title">' + esc(title) + "</h2>" +
      (desc ? '<p class="page-header-desc">' + esc(desc) + "</p>" : "") +
      "</div>" +
      (actions ? '<div class="page-header-actions">' + actions + "</div>" : "") +
      "</div>"
    );
  };

  // ── KPI Grid ─────────────────────────────────────────────────────
  UI.kpiGrid = function (cardsHtml, columns) {
    var cols = columns || 4;
    return (
      '<div style="display:grid;grid-template-columns:repeat(' + cols +
      ",1fr);gap:var(--ds-space-4);margin-bottom:var(--ds-space-6);\">" +
      cardsHtml + "</div>"
    );
  };

  // ── Section Heading ───────────────────────────────────────────────
  UI.sectionHeading = function (title, actions) {
    return (
      '<div class="section-heading">' +
      '<h3>' + esc(title) + "</h3>" +
      (actions ? '<div class="section-heading-actions">' + actions + "</div>" : "") +
      "</div>"
    );
  };

  // ── Metric Card ───────────────────────────────────────────────────
  UI.metricCard = function (label, value, sub, subType) {
    var subClass = subType || (sub && sub.charAt(0) === "-" ? "neg" : "pos");
    var subHtml = sub
      ? '<span class="ds-metric-sub ' + subClass + '">' + esc(sub) + "</span>"
      : "";
    return (
      '<div class="ds-metric-card">' +
      '<div class="ds-metric-label">' + esc(label) + "</div>" +
      '<div class="ds-metric-value">' + esc(value) + "</div>" +
      subHtml +
      "</div>"
    );
  };

  // ── Panel ─────────────────────────────────────────────────────────
  UI.panel = function (title, bodyHtml, opts) {
    opts = opts || {};
    var actions = opts.actions
      ? '<div class="ds-panel-actions">' + opts.actions + "</div>"
      : "";
    return (
      '<div class="ds-panel">' +
      '<div class="ds-panel-header">' +
      '<span class="ds-panel-title">' + esc(title) + "</span>" +
      actions +
      "</div>" +
      '<div class="ds-panel-body">' + bodyHtml + "</div>" +
      "</div>"
    );
  };

  // ── Table ─────────────────────────────────────────────────────────
  UI.table = function (opts) {
    var cols = opts.columns || [];
    var rows = opts.rows || [];
    var sortable = opts.sortable !== false;

    var headerHtml = cols
      .map(function (c) {
        var cls = c.numeric ? "num" : "";
        if (sortable && c.sortable !== false) {
          cls += " sortable";
        }
        return (
          '<th class="' + cls + '">' + esc(c.label) +
          (c.numeric ? ' <span class="sort-indicator">↕</span>' : "") +
          "</th>"
        );
      })
      .join("");

    var bodyHtml;
    if (rows.length === 0) {
      bodyHtml =
        '<tr><td colspan="' + cols.length + '">' +
        UI.empty("No data", opts.emptyDesc || "No rows to display.") +
        "</td></tr>";
    } else {
      bodyHtml = rows
        .map(function (row) {
          var cells = cols
            .map(function (c) {
              var val = row[c.key];
              var formatted = c.format ? c.format(val, row) : esc(val);
              var cls = "num";
              if (c.numeric) cls += " num";
              if (c.color) {
                var col = typeof c.color === "function" ? c.color(val, row) : c.color;
                if (col) cls += " " + col;
              }
              return '<td class="' + cls + '">' + formatted + "</td>";
            })
            .join("");
          return "<tr>" + cells + "</tr>";
        })
        .join("");
    }

    return (
      '<table class="ds-table">' +
      "<thead><tr>" + headerHtml + "</tr></thead>" +
      "<tbody>" + bodyHtml + "</tbody>" +
      "</table>"
    );
  };

  // ── Button ────────────────────────────────────────────────────────
  UI.button = function (text, variant, opts) {
    opts = opts || {};
    var cls = "ds-btn ds-btn-" + (variant || "secondary");
    if (opts.sm) cls += " ds-btn-sm";
    if (opts.block) cls += " ds-btn-block";
    if (opts.disabled) cls += " disabled";
    var id = opts.id ? ' id="' + esc(opts.id) + '"' : "";
    var action = opts.action ? ' data-action="' + esc(opts.action) + '"' : "";
    var onclick = opts.onclick
      ? ' onclick="' + esc(opts.onclick) + '"'
      : "";
    return (
      "<button" + id + ' class="' + cls + '"' + action + onclick +
      (opts.disabled ? " disabled" : "") + ">" +
      esc(text) + "</button>"
    );
  };

  // ── Input ─────────────────────────────────────────────────────────
  UI.input = function (opts) {
    opts = opts || {};
    var id = opts.id ? ' id="' + esc(opts.id) + '"' : "";
    var type = ' type="' + (opts.type || "text") + '"';
    var ph = opts.placeholder ? ' placeholder="' + esc(opts.placeholder) + '"' : "";
    var val = opts.value ? ' value="' + esc(opts.value) + '"' : "";
    var step = opts.step ? ' step="' + esc(opts.step) + '"' : "";
    var action = opts.action ? ' data-action="' + esc(opts.action) + '"' : "";
    var dis = opts.disabled ? " disabled" : "";
    var cls = ' class="ds-input"';
    return "<input" + id + type + ph + val + step + action + dis + cls + ">";
  };

  UI.field = function (label, inputHtml) {
    return (
      '<div class="ds-field">' +
      '<label class="ds-field-label">' + esc(label) + "</label>" +
      inputHtml +
      "</div>"
    );
  };

  UI.select = function (opts) {
    opts = opts || {};
    var id = opts.id ? ' id="' + esc(opts.id) + '"' : "";
    var options = (opts.options || [])
      .map(function (o) {
        var val = typeof o === "object" ? o.value : o;
        var txt = typeof o === "object" ? o.label : o;
        var sel = opts.value === val ? " selected" : "";
        return "<option" + sel + ' value="' + esc(val) + '">' + esc(txt) + "</option>";
      })
      .join("");
    return "<select" + id + ' class="ds-select">' + options + "</select>";
  };

  UI.search = function (placeholder, id) {
    return (
      '<div class="ds-search">' +
      '<input type="text" class="ds-input"' +
      (id ? ' id="' + esc(id) + '"' : "") +
      ' placeholder="' + esc(placeholder || "Search…") + '">' +
      "</div>"
    );
  };

  // ── Badge ────────────────────────────────────────────────────────
  UI.badge = function (text, variant) {
    return (
      '<span class="ds-badge ds-badge-' + (variant || "neutral") + '">' +
      '<span class="ds-badge-dot"></span>' +
      esc(text) +
      "</span>"
    );
  };

  UI.envBadge = function (env) {
    var e = (env || "paper").toLowerCase();
    return '<span class="ds-env-badge ds-env-' + e + '">' + esc(e.toUpperCase()) + "</span>";
  };

  // ── Tabs ─────────────────────────────────────────────────────────
  UI.tabs = function (tabs) {
    var html = '<div class="ds-tabs">';
    tabs.forEach(function (t, i) {
      html +=
        '<button class="ds-tab' + (i === 0 ? " active" : "") + '"' +
        ' data-tab="' + esc(t.id) + '">' +
        esc(t.label) +
        "</button>";
    });
    html += "</div>";
    tabs.forEach(function (t, i) {
      html +=
        '<div class="ds-tab-panel' + (i === 0 ? "" : " hidden") + '"' +
        ' data-panel="' + esc(t.id) + '">' +
        (t.content || "") +
        "</div>";
    });
    return html;
  };

  // ── Modal ────────────────────────────────────────────────────────
  UI.openModal = function (opts) {
    UI.closeModal();
    var backdrop = document.createElement("div");
    backdrop.className = "ds-modal-backdrop";
    backdrop.innerHTML =
      '<div class="ds-modal">' +
      '<div class="ds-modal-header">' +
      '<span class="ds-modal-title">' + esc(opts.title || "") + "</span>" +
      '<button class="ds-modal-close" data-action="close-modal">✕</button>' +
      "</div>" +
      '<div class="ds-modal-body">' + (opts.body || "") + "</div>" +
      (opts.footer ? '<div class="ds-modal-footer">' + opts.footer + "</div>" : "") +
      "</div>";
    document.body.appendChild(backdrop);
    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop || e.target.hasAttribute("data-action")) {
        if (e.target.getAttribute("data-action") === "close-modal" || e.target === backdrop) {
          UI.closeModal();
        }
      }
    });
    if (opts.onMount) opts.onMount(backdrop);
    return backdrop;
  };

  UI.closeModal = function () {
    var existing = document.querySelector(".ds-modal-backdrop");
    if (existing) existing.remove();
  };

  // ── Drawer ───────────────────────────────────────────────────────
  UI.openDrawer = function (opts) {
    UI.closeDrawer();
    var backdrop = document.createElement("div");
    backdrop.className = "ds-drawer-backdrop";
    var drawer = document.createElement("div");
    drawer.className = "ds-drawer";
    drawer.innerHTML =
      '<div class="ds-drawer-header">' +
      '<span class="ds-drawer-title">' + esc(opts.title || "") + "</span>" +
      '<button class="ds-drawer-close" data-action="close-drawer">✕</button>' +
      "</div>" +
      '<div class="ds-drawer-body">' + (opts.body || "") + "</div>" +
      (opts.footer ? '<div class="ds-drawer-footer">' + opts.footer + "</div>" : "");
    backdrop.appendChild(drawer);
    document.body.appendChild(backdrop);
    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop || (e.target.getAttribute && e.target.getAttribute("data-action") === "close-drawer")) {
        UI.closeDrawer();
      }
    });
    if (opts.onMount) opts.onMount(drawer);
    return drawer;
  };

  UI.closeDrawer = function () {
    var existing = document.querySelector(".ds-drawer-backdrop");
    if (existing) existing.remove();
  };

  // ── Loading ──────────────────────────────────────────────────────
  UI.loading = function (text) {
    return (
      '<div class="ds-loading">' +
      '<div class="ds-loading-spinner"></div>' +
      '<div class="ds-loading-text">' + esc(text || "Loading…") + "</div>" +
      "</div>"
    );
  };

  // ── Empty ────────────────────────────────────────────────────────
  UI.empty = function (title, desc, icon) {
    return (
      '<div class="ds-empty">' +
      '<div class="ds-empty-icon">' + (icon || "◯") + "</div>" +
      '<div class="ds-empty-title">' + esc(title || "No data") + "</div>" +
      '<div class="ds-empty-desc">' + esc(desc || "") + "</div>" +
      "</div>"
    );
  };

  // ── Error ────────────────────────────────────────────────────────
  UI.error = function (title, desc, retryAction) {
    var retry = retryAction
      ? '<button class="ds-btn ds-btn-secondary ds-btn-sm" data-action="' +
        esc(retryAction) + '">Retry</button>'
      : "";
    return (
      '<div class="ds-error">' +
      '<div class="ds-error-icon">✕</div>' +
      '<div class="ds-error-title">' + esc(title || "Error") + "</div>" +
      '<div class="ds-error-desc">' + esc(desc || "") + "</div>" +
      retry +
      "</div>"
    );
  };

  // ── Grid helper ──────────────────────────────────────────────────
  UI.grid = function (html, columns) {
    return (
      '<div style="display:grid;grid-template-columns:repeat(' +
      (columns || 4) +
      ",1fr);gap:var(--ds-space-4);\">" +
      html +
      "</div>"
    );
  };

  // ── Equity Curve (SVG line chart) ────────────────────────────────
  // data: [{ value: Number, label: String }]  (labels optional, used for x-axis)
  // opts: { height, yTicks: [Number], yFormat: fn, xLabels: [String], color }
  UI.equityCurve = function (data, opts) {
    opts = opts || {};
    if (!data || data.length === 0) return UI.empty("No data", "Equity curve unavailable.");
    var W = 880, H = opts.height || 240;
    var pad = { top: 16, right: 16, bottom: 28, left: 64 };
    var w = W - pad.left - pad.right;
    var h = H - pad.top - pad.bottom;

    var vals = data.map(function (d) { return d.value; });
    var min = opts.yMin != null ? opts.yMin : Math.min.apply(null, vals);
    var max = opts.yMax != null ? opts.yMax : Math.max.apply(null, vals);
    var range = max - min || 1;
    // pad range a little so the line doesn't touch edges
    var padR = range * 0.08;
    var yMin = min - padR;
    var yMax = max + padR;
    var yRange = yMax - yMin || 1;

    var xStep = data.length > 1 ? w / (data.length - 1) : 0;
    var pts = data.map(function (d, i) {
      var x = pad.left + i * xStep;
      var y = pad.top + h - ((d.value - yMin) / yRange) * h;
      return { x: x, y: y, value: d.value, label: d.label };
    });

    var color = opts.color || "var(--ds-profit)";
    var lineD = "M " + pts.map(function (p) { return p.x.toFixed(1) + " " + p.y.toFixed(1); }).join(" L ");
    var areaD = lineD + " L " + pts[pts.length - 1].x.toFixed(1) + " " + (pad.top + h) +
      " L " + pts[0].x.toFixed(1) + " " + (pad.top + h) + " Z";

    // Y axis ticks
    var yTicks = opts.yTicks || [yMin, (yMin + yMax) / 2, yMax];
    var yTickHtml = yTicks.map(function (t) {
      var y = pad.top + h - ((t - yMin) / yRange) * h;
      var lbl = opts.yFormat ? opts.yFormat(t) : UI.money(t, 0);
      return (
        '<line x1="' + pad.left + '" y1="' + y.toFixed(1) + '" x2="' + (pad.left + w) + '" y2="' + y.toFixed(1) + '" stroke="var(--ds-border-soft)" stroke-width="1" stroke-dasharray="2 4" />' +
        '<text x="' + (pad.left - 8) + '" y="' + (y + 3).toFixed(1) + '" text-anchor="end" class="eqc-axis-label">' + esc(lbl) + '</text>'
      );
    }).join("");

    // X axis labels
    var xLabels = opts.xLabels || data.map(function (d) { return d.label; });
    var xTickHtml = (xLabels || []).map(function (lbl, i) {
      if (!lbl) return "";
      var x = pad.left + (xLabels.length > 1 ? (i * w / (xLabels.length - 1)) : 0);
      return '<text x="' + x.toFixed(1) + '" y="' + (pad.top + h + 18) + '" text-anchor="middle" class="eqc-axis-label">' + esc(lbl) + '</text>';
    }).join("");

    // Last point marker
    var last = pts[pts.length - 1];
    var markerHtml =
      '<circle cx="' + last.x.toFixed(1) + '" cy="' + last.y.toFixed(1) + '" r="4" fill="' + color + '" />' +
      '<circle cx="' + last.x.toFixed(1) + '" cy="' + last.y.toFixed(1) + '" r="8" fill="' + color + '" opacity="0.2" />';

    return (
      '<div class="eqc-wrap">' +
      '<svg class="eqc-svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Equity curve">' +
      '<defs><linearGradient id="eqc-grad" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="' + color + '" stop-opacity="0.28" />' +
      '<stop offset="100%" stop-color="' + color + '" stop-opacity="0" />' +
      '</linearGradient></defs>' +
      '<path d="' + areaD + '" fill="url(#eqc-grad)" />' +
      '<path d="' + lineD + '" fill="none" stroke="' + color + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />' +
      yTickHtml + xTickHtml + markerHtml +
      '</svg>' +
      '</div>'
    );
  };

  // ── Sparkline (small inline SVG) ─────────────────────────────────
  // data: [Number, ...]; opts: { color, width, height, fill }
  UI.sparkline = function (data, opts) {
    opts = opts || {};
    if (!data || data.length === 0) return "";
    var W = opts.width || 120, H = opts.height || 36;
    var pad = 3;
    var w = W - pad * 2, h = H - pad * 2;
    var min = Math.min.apply(null, data);
    var max = Math.max.apply(null, data);
    var range = max - min || 1;
    var xStep = data.length > 1 ? w / (data.length - 1) : 0;
    var color = opts.color || "var(--ds-profit)";
    var pts = data.map(function (v, i) {
      var x = pad + i * xStep;
      var y = pad + h - ((v - min) / range) * h;
      return x.toFixed(1) + " " + y.toFixed(1);
    });
    var lineD = "M " + pts.join(" L ");
    var fillD = opts.fill === false ? "" : lineD + " L " + (pad + (data.length - 1) * xStep) + " " + (pad + h) + " L " + pad + " " + (pad + h) + " Z";
    var fillPath = fillD ? '<path d="' + fillD + '" fill="' + color + '" fill-opacity="0.14" />' : "";
    return (
      '<svg class="ds-spark" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" aria-hidden="true">' +
      fillPath +
      '<path d="' + lineD + '" fill="none" stroke="' + color + '" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" />' +
      '</svg>'
    );
  };

  // ── Timeline (activity feed) ────────────────────────────────────
  // items: [{ time, type, title, desc?, variant? }]
  // variant: "profit" | "loss" | "warning" | "info" | "neutral" | "purple"
  UI.timeline = function (items) {
    if (!items || items.length === 0) return UI.empty("No activity", "Recent events will appear here.");
    var html = '<div class="ds-timeline">';
    items.forEach(function (it) {
      var v = it.variant || "neutral";
      html +=
        '<div class="ds-timeline-item">' +
        '<div class="ds-timeline-dot ds-timeline-dot-' + v + '"></div>' +
        '<div class="ds-timeline-content">' +
        '<div class="ds-timeline-row">' +
        '<span class="ds-timeline-time">' + esc(it.time || "") + '</span>' +
        '<span class="ds-timeline-type">' + esc(it.type || "") + '</span>' +
        '</div>' +
        '<div class="ds-timeline-title">' + esc(it.title || "") + '</div>' +
        (it.desc ? '<div class="ds-timeline-desc">' + esc(it.desc) + '</div>' : '') +
        '</div>' +
        '</div>';
    });
    html += '</div>';
    return html;
  };

  // ── Stat Row (label / value pairs for strategy cards) ────────────
  // rows: [{ label, value, variant?, mono? }]
  UI.statRows = function (rows) {
    return rows.map(function (r) {
      var v = r.variant || "default";
      var cls = "ds-stat-value ds-stat-" + v;
      if (r.mono !== false) cls += " ds-text-mono";
      return (
        '<div class="ds-stat-row">' +
        '<span class="ds-stat-label">' + esc(r.label || "") + '</span>' +
        '<span class="' + cls + '">' + esc(r.value == null ? "" : r.value) + '</span>' +
        '</div>'
      );
    }).join("");
  };

  // ── Period Tabs (1D/1W/1M/...) ───────────────────────────────────
  // periods: ["1D","1W","1M","3M","YTD","ALL"]; activeIdx: default selected
  UI.periodTabs = function (periods, activeIdx, id) {
    var aIdx = activeIdx == null ? 0 : activeIdx;
    var html = '<div class="ds-period-tabs"' + (id ? ' id="' + esc(id) + '"' : '') + '>';
    periods.forEach(function (p, i) {
      html += '<button class="ds-period-tab' + (i === aIdx ? " active" : "") + '" data-period="' + esc(p) + '">' + esc(p) + '</button>';
    });
    html += '</div>';
    return html;
  };

  // ── Status Pill (● label) ────────────────────────────────────────
  UI.statusPill = function (label, variant) {
    var v = variant || "profit";
    return '<span class="ds-status-pill ds-status-' + v + '"><span class="ds-status-dot"></span>' + esc(label) + '</span>';
  };

  // ── Segmented Toggle (BUY/SELL, Market/Limit) ───────────────────
  // options: [{ value, label, variant? }]; activeIdx: default; id?: for binding
  UI.segToggle = function (options, activeIdx, id) {
    var aIdx = activeIdx == null ? 0 : activeIdx;
    var html = '<div class="ds-seg-toggle"' + (id ? ' id="' + esc(id) + '"' : '') + '>';
    options.forEach(function (o, i) {
      var v = o.variant || "";
      html += '<button class="ds-seg' + (i === aIdx ? " active" : "") +
        (v ? " ds-seg-" + v : "") +
        '" data-value="' + esc(o.value) + '">' + esc(o.label) + '</button>';
    });
    html += '</div>';
    return html;
  };

  // ── Instrument Header (symbol, price, change, bid/ask) ─────────
  // opts: { symbol, name, price, change, changePct, bid, ask, spread, status, time }
  UI.instrumentHeader = function (opts) {
    var up = opts.change >= 0;
    var arrow = up ? "▲" : "▼";
    var cls = up ? "pos" : "neg";
    return (
      '<div class="tr-inst">' +
      '<div class="tr-inst-left">' +
      '<div class="tr-inst-symbol">' + esc(opts.symbol) + '</div>' +
      '<div class="tr-inst-name">' + esc(opts.name || "") + '</div>' +
      '</div>' +
      '<div class="tr-inst-price-block">' +
      '<span class="tr-inst-price ds-text-mono">' + money(opts.price) + '</span>' +
      '<span class="tr-inst-change ds-text-mono tr-' + cls + '">' + arrow + ' ' + Math.abs(opts.change).toFixed(2) + ' (' + pct(opts.changePct, 2) + ')</span>' +
      '</div>' +
      '<div class="tr-inst-quote">' +
      '<div class="tr-inst-quote-row"><span class="tr-inst-quote-label">Bid</span><span class="ds-text-mono">' + money(opts.bid) + '</span></div>' +
      '<div class="tr-inst-quote-row"><span class="tr-inst-quote-label">Ask</span><span class="ds-text-mono">' + money(opts.ask) + '</span></div>' +
      '<div class="tr-inst-quote-row"><span class="tr-inst-quote-label">Spread</span><span class="ds-text-mono">' + opts.spread + '</span></div>' +
      '</div>' +
      '<div class="tr-inst-meta">' +
      '<div class="tr-inst-quote-row"><span class="tr-inst-quote-label">Status</span>' + UI.statusPill(opts.status || "Open", "profit") + '</div>' +
      '<div class="tr-inst-quote-row"><span class="tr-inst-quote-label">Time</span><span class="ds-text-mono">' + esc(opts.time || "") + '</span></div>' +
      '</div>' +
      '<div class="tr-inst-search">' + UI.search("Search symbol", "tr-symbol-search") + '</div>' +
      '</div>'
    );
  };

  // ── Watchlist ──────────────────────────────────────────────────
  // items: [{ symbol, price, changePct }]; activeSymbol: highlighted item
  UI.watchlist = function (items, activeSymbol) {
    var rows = items.map(function (it) {
      var up = it.changePct >= 0;
      var cls = up ? "pos" : "neg";
      var active = it.symbol === activeSymbol ? " active" : "";
      return (
        '<div class="tr-wl-item' + active + '" data-symbol="' + esc(it.symbol) + '">' +
        '<span class="tr-wl-symbol">' + esc(it.symbol) + '</span>' +
        '<span class="tr-wl-price ds-text-mono">' + money(it.price) + '</span>' +
        '<span class="tr-wl-change ds-text-mono tr-' + cls + '">' + (up ? "+" : "") + (it.changePct * 100).toFixed(2) + '%</span>' +
        '</div>'
      );
    }).join("");
    return '<div class="tr-watchlist">' + rows + '</div>';
  };

  // ── Candlestick Chart (SVG mock) ───────────────────────────────
  // candles: [{ o, h, l, c }]  (open/high/low/close)
  // opts: { height, width }
  UI.candleChart = function (candles, opts) {
    opts = opts || {};
    if (!candles || candles.length === 0) return UI.empty("No data", "Chart unavailable.");
    var W = opts.width || 840, H = opts.height || 320;
    var pad = { top: 10, right: 50, bottom: 24, left: 10 };
    var w = W - pad.left - pad.right;
    var h = H - pad.top - pad.bottom;

    var allVals = [];
    candles.forEach(function (c) { allVals.push(c.h, c.l); });
    var min = Math.min.apply(null, allVals);
    var max = Math.max.apply(null, allVals);
    var range = max - min || 1;
    var padR = range * 0.05;
    var yMin = min - padR;
    var yMax = max + padR;
    var yRange = yMax - yMin || 1;

    var n = candles.length;
    var cw = w / n; // candle slot width
    var bodyW = Math.max(2, cw * 0.6);

    function y(val) { return pad.top + h - ((val - yMin) / yRange) * h; }

    var candleHtml = "";
    candles.forEach(function (c, i) {
      var cx = pad.left + i * cw + cw / 2;
      var up = c.c >= c.o;
      var color = up ? "var(--ds-profit)" : "var(--ds-loss)";
      var yHigh = y(c.h);
      var yLow = y(c.l);
      var yOpen = y(c.o);
      var yClose = y(c.c);
      var bodyTop = Math.min(yOpen, yClose);
      var bodyH = Math.max(1, Math.abs(yClose - yOpen));
      // Wick
      candleHtml += '<line x1="' + cx.toFixed(1) + '" y1="' + yHigh.toFixed(1) + '" x2="' + cx.toFixed(1) + '" y2="' + yLow.toFixed(1) + '" stroke="' + color + '" stroke-width="1" />';
      // Body
      candleHtml += '<rect x="' + (cx - bodyW / 2).toFixed(1) + '" y="' + bodyTop.toFixed(1) + '" width="' + bodyW.toFixed(1) + '" height="' + bodyH.toFixed(1) + '" fill="' + color + '" rx="0.5" />';
    });

    // Price axis labels (right side)
    var priceLabels = "";
    var ticks = [yMin, yMin + (yMax - yMin) / 2, yMax];
    ticks.forEach(function (t) {
      var yp = y(t);
      priceLabels += '<line x1="' + pad.left + '" y1="' + yp.toFixed(1) + '" x2="' + (pad.left + w) + '" y2="' + yp.toFixed(1) + '" stroke="var(--ds-border-soft)" stroke-width="1" stroke-dasharray="2 4" />' +
        '<text x="' + (pad.left + w + 6) + '" y="' + (yp + 3).toFixed(1) + '" class="eqc-axis-label">' + money(t) + '</text>';
    });

    return (
      '<div class="tr-chart-wrap">' +
      '<svg class="tr-chart-svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Price chart">' +
      priceLabels + candleHtml +
      '</svg>' +
      '</div>'
    );
  };

  // ── Chart Shell (timeframe tabs + chart + volume/indicators) ────
  UI.chartShell = function (opts) {
    opts = opts || {};
    var tfs = opts.timeframes || ["1m", "5m", "15m", "1H", "4H", "1D"];
    var tfHtml = tfs.map(function (tf, i) {
      return '<button class="tr-tf' + (i === (opts.activeTf || 0) ? " active" : "") + '" data-tf="' + esc(tf) + '">' + esc(tf) + '</button>';
    }).join("");
    var chartHtml = opts.chartHtml || '<div class="chart-placeholder">Chart area</div>';
    var volHtml = opts.showVolume !== false
      ? '<div class="tr-volume-bar">' +
        Array.from({ length: 40 }, function (_, i) {
          var hh = 20 + Math.abs(Math.sin(i * 0.5)) * 60 + (i % 5) * 8;
          return '<div class="tr-vol-col" style="height:' + hh.toFixed(0) + 'px"></div>';
        }).join("") +
        '</div>'
      : "";
    return (
      '<div class="tr-chart-shell">' +
      '<div class="tr-chart-toolbar">' +
      '<div class="tr-tf-group">' + tfHtml + '</div>' +
      '<div class="tr-chart-tools">' +
      '<button class="tr-tool active" data-tool="candles">Candles</button>' +
      '<button class="tr-tool" data-tool="volume">Volume</button>' +
      '<button class="tr-tool" data-tool="indicators">Indicators</button>' +
      '</div>' +
      '</div>' +
      chartHtml +
      volHtml +
      '</div>'
    );
  };

  // ── Order Ticket ────────────────────────────────────────────────
  // opts: { symbol, price, side, orderType, qty, limitPrice, stopLoss, takeProfit }
  UI.orderTicket = function (opts) {
    opts = opts || {};
    return (
      '<div class="tr-order-ticket" id="tr-order-ticket">' +
      '<div class="tr-ot-head">' +
      '<span class="tr-ot-title">Order Ticket</span>' +
      '<span class="tr-ot-symbol">' + esc(opts.symbol || "NVDA") + '</span>' +
      '</div>' +
      UI.segToggle([
        { value: "BUY", label: "BUY", variant: "profit" },
        { value: "SELL", label: "SELL", variant: "loss" },
      ], 0, "tr-ot-side") +
      '<div class="tr-ot-field">' +
      '<label class="tr-ot-label">Order Type</label>' +
      UI.select({
        id: "tr-ot-type",
        options: [
          { value: "market", label: "Market" },
          { value: "limit", label: "Limit" },
          { value: "stop", label: "Stop" },
          { value: "stop_limit", label: "Stop-Limit" },
        ],
      }) +
      '</div>' +
      '<div class="tr-ot-row">' +
      '<div class="tr-ot-field">' +
      '<label class="tr-ot-label">Quantity</label>' +
      UI.input({ id: "tr-ot-qty", type: "number", value: opts.qty || "100", placeholder: "0" }) +
      '</div>' +
      '<div class="tr-ot-field">' +
      '<label class="tr-ot-label">Limit Price</label>' +
      UI.input({ id: "tr-ot-limit", type: "number", value: opts.limitPrice || opts.price || "", step: "0.01", placeholder: "0.00" }) +
      '</div>' +
      '</div>' +
      '<div class="tr-ot-row">' +
      '<div class="tr-ot-field">' +
      '<label class="tr-ot-label">Stop Loss</label>' +
      UI.input({ id: "tr-ot-sl", type: "number", step: "0.01", placeholder: "0.00" }) +
      '</div>' +
      '<div class="tr-ot-field">' +
      '<label class="tr-ot-label">Take Profit</label>' +
      UI.input({ id: "tr-ot-tp", type: "number", step: "0.01", placeholder: "0.00" }) +
      '</div>' +
      '</div>' +
      '<div class="tr-ot-notional">' +
      '<span class="tr-ot-label">Estimated Notional</span>' +
      '<span class="tr-ot-notional-val ds-text-mono" id="tr-ot-notional">$' + ((opts.qty || 100) * (opts.price || 178.42)).toLocaleString("en-US", { maximumFractionDigits: 0 }) + '</span>' +
      '</div>' +
      '<button class="ds-btn ds-btn-primary tr-ot-submit" id="tr-ot-review" data-side="BUY">REVIEW ORDER</button>' +
      '<div class="tr-ot-disclaimer">Paper trading only · No real execution</div>' +
      '</div>'
    );
  };

  // ── Donut Chart (allocation pie) ──────────────────────────────
  // segments: [{ label, value, color }]  (color = CSS var or hex)
  // opts: { size, thickness, centerLabel, centerValue }
  UI.donutChart = function (segments, opts) {
    opts = opts || {};
    if (!segments || segments.length === 0) return UI.empty("No data", "Allocation unavailable.");
    var size = opts.size || 180;
    var r = size / 2;
    var thickness = opts.thickness || 22;
    var cx = r, cy = r;
    var radius = r - thickness / 2 - 2;
    var total = segments.reduce(function (s, seg) { return s + (seg.value || 0); }, 0) || 1;

    // SVG arc path generator
    function polar(cx, cy, r, angle) {
      var rad = (angle - 90) * Math.PI / 180;
      return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
    }
    function arcPath(cx, cy, r, startAngle, endAngle) {
      var s = polar(cx, cy, r, endAngle);
      var e = polar(cx, cy, r, startAngle);
      var large = endAngle - startAngle <= 180 ? 0 : 1;
      return "M " + s.x.toFixed(2) + " " + s.y.toFixed(2) +
        " A " + r + " " + r + " 0 " + large + " 0 " + e.x.toFixed(2) + " " + e.y.toFixed(2);
    }

    var angle = 0;
    var paths = "";
    var legendItems = "";
    segments.forEach(function (seg) {
      var pctVal = (seg.value / total) * 100;
      var sweep = (seg.value / total) * 360;
      if (sweep >= 360) {
        // Full circle — draw as circle
        paths += '<circle cx="' + cx + '" cy="' + cy + '" r="' + radius + '" fill="none" stroke="' + (seg.color || "var(--ds-info)") + '" stroke-width="' + thickness + '" />';
      } else {
        var path = arcPath(cx, cy, radius, angle, angle + sweep);
        paths += '<path d="' + path + '" fill="none" stroke="' + (seg.color || "var(--ds-info)") + '" stroke-width="' + thickness + '" stroke-linecap="butt" />';
      }
      angle += sweep;
      legendItems +=
        '<div class="pf-alloc-leg-item">' +
        '<span class="pf-alloc-leg-dot" style="background:' + (seg.color || "var(--ds-info)") + '"></span>' +
        '<span class="pf-alloc-leg-label">' + esc(seg.label) + '</span>' +
        '<span class="pf-alloc-leg-val ds-text-mono">' + pctVal.toFixed(1) + '%</span>' +
        '</div>';
    });

    var centerHtml = "";
    if (opts.centerLabel || opts.centerValue) {
      centerHtml =
        '<text x="' + cx + '" y="' + (cy - 4) + '" text-anchor="middle" class="pf-donut-center-val">' + esc(opts.centerValue || "") + '</text>' +
        '<text x="' + cx + '" y="' + (cy + 16) + '" text-anchor="middle" class="pf-donut-center-label">' + esc(opts.centerLabel || "") + '</text>';
    }

    return (
      '<div class="pf-alloc">' +
      '<div class="pf-alloc-chart">' +
      '<svg class="pf-donut" viewBox="0 0 ' + size + ' ' + size + '" role="img" aria-label="Allocation chart">' +
      paths + centerHtml +
      '</svg>' +
      '</div>' +
      '<div class="pf-alloc-legend">' + legendItems + '</div>' +
      '</div>'
    );
  };

  // ── Formatting utilities (exposed for page code) ──────────────────
  UI.fmtNum = fmtNum;
  UI.pct = pct;
  UI.money = money;
  UI.signedMoney = signedMoney;
  UI.esc = esc;

  // ==================================================================
  // Commit 020 — Final Polish: Terminal helpers (state, toast, confirm)
  // ==================================================================

  // ── Breadcrumb — ICYQuant / GROUP / Page ─────────────────────────
  UI.breadcrumb = function (parts) {
    parts = parts || [];
    return (
      '<div class="breadcrumb">' +
      parts.map(function (p) { return "<span>" + esc(p) + "</span>"; }).join("") +
      "</div>"
    );
  };

  // ── Page chrome: breadcrumb + pageHeader ────────────────────────
  //   parts[]: breadcrumb; title/desc/actions: pageHeader args
  UI.pageChrome = function (opts) {
    return (
      UI.breadcrumb(opts.crumb || ["ICYQuant"]) +
      UI.pageHeader(opts.title, opts.desc, opts.actions)
    );
  };

  // ── Keyboard Hint Line: shows kbd chips in a toolbar ────────────
  UI.kbdBar = function (hints) {
    return (
      '<div style="display:flex;gap:var(--ds-space-2);flex-wrap:wrap;color:var(--ds-text-muted);font-size:var(--ds-text-xs);">' +
      hints.map(function (h) {
        return '<span><span class="kbd">' + esc(h.key) + "</span> " + esc(h.label) + "</span>";
      }).join("") +
      "</div>"
    );
  };

  // ── Final polish state blocks (empty / loading / error) ─────────
  UI.stateEmpty = function (title, desc, btn) {
    return (
      '<div class="state-empty">' +
      '<div class="state-icon">◯</div>' +
      '<div class="state-title">' + esc(title || "No data") + "</div>" +
      '<div class="state-sub">' + esc(desc || "") + "</div>" +
      (btn ? '<div class="state-actions">' + btn + "</div>" : "") +
      "</div>"
    );
  };
  UI.stateLoading = function (title, desc) {
    return (
      '<div class="state-loading">' +
      '<div class="state-icon" aria-label="Loading"></div>' +
      '<div class="state-title">' + esc(title || "Loading") + "</div>" +
      '<div class="state-sub">' + esc(desc || "Fetching latest data…") + "</div>" +
      "</div>"
    );
  };
  UI.stateError = function (title, desc, retryLabel, retryAction) {
    return (
      '<div class="state-error">' +
      '<div class="state-icon" aria-hidden="true">⚠</div>' +
      '<div class="state-title">' + esc(title || "Error") + "</div>" +
      '<div class="state-sub">' + esc(desc || "") + "</div>" +
      (retryLabel
        ? '<div class="state-actions"><button class="ds-btn primary" data-action="' + esc(retryAction || "retry") + '">' + esc(retryLabel) + "</button></div>"
        : "") +
      "</div>"
    );
  };

  // ── Toast Center — host mounted once at first toast. ────────────
  function toastHost() {
    var h = document.getElementById("ds-toast-host");
    if (h) return h;
    h = document.createElement("div");
    h.id = "ds-toast-host";
    document.body.appendChild(h);
    return h;
  }
  /**
   * UI.toast({ kind: info|success|warning|error, title, sub, ttl })
   *   kind defaults: error => 6s, warning 5s, else 3.5s
   */
  UI.toast = function (opts) {
    opts = opts || {};
    var kind = opts.kind || "info";
    var ttl = opts.ttl != null
      ? opts.ttl
      : (kind === "error" ? 6000 : kind === "warning" ? 5000 : 3500);
    var host = toastHost();
    var t = document.createElement("div");
    t.className = "ds-toast " + kind;
    t.innerHTML =
      (opts.title ? '<div class="ds-toast-title">' + esc(opts.title) + "</div>" : "") +
      (opts.sub   ? '<div class="ds-toast-sub">'   + esc(opts.sub)   + "</div>" : "");
    host.appendChild(t);
    if (ttl > 0) {
      setTimeout(function () {
        t.style.transition = "opacity 200ms ease, transform 200ms ease";
        t.style.opacity = "0";
        t.style.transform = "translateY(-6px)";
        setTimeout(function () { t.remove(); }, 220);
      }, ttl);
    }
    return t;
  };

  // ── Confirm Dialog — promise-style, with Cancel / Primary ───────
  UI.confirm = function (opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      var backdrop = document.createElement("div");
      backdrop.className = "ds-modal-backdrop";
      backdrop.innerHTML =
        '<div class="ds-modal" role="dialog" aria-modal="true">' +
        '<div class="ds-modal-title">' + esc(opts.title || "Confirm") + "</div>" +
        '<div class="ds-modal-message">' + esc(opts.message || "") + "</div>" +
        '<div class="ds-modal-actions">' +
        '<button class="ds-btn ghost" data-role="cancel">' + esc(opts.cancelLabel || "Cancel") + "</button>" +
        '<button class="ds-btn ' + (opts.okVariant || "danger") + '" data-role="ok">' + esc(opts.okLabel || "Confirm") + "</button>" +
        "</div>" +
        "</div>";
      function finish(result) {
        backdrop.remove();
        document.removeEventListener("keydown", onKey, true);
        resolve(result);
      }
      function onKey(e) {
        if (e.key === "Escape") { e.preventDefault(); finish(false); }
        if (e.key === "Enter")  { e.preventDefault(); finish(true);  }
      }
      backdrop.addEventListener("click", function (e) {
        var role = e.target.getAttribute && e.target.getAttribute("data-role");
        if (role === "cancel" || e.target === backdrop) finish(false);
        if (role === "ok") finish(true);
      });
      document.addEventListener("keydown", onKey, true);
      document.body.appendChild(backdrop);
      // Focus primary
      var ok = backdrop.querySelector('[data-role="ok"]');
      if (ok) ok.focus({ preventScroll: true });
    });
  };

  // ── Tick Flash helper — apply flash-up/dn/info on an element ────
  UI.flashCell = function (el, direction) {
    if (!el) return;
    var cls = direction > 0 ? "flash-profit"
      : direction < 0 ? "flash-loss"
      :                 "flash-info";
    el.classList.remove("flash-profit", "flash-loss", "flash-info");
    // Restart animation
    void el.offsetWidth;
    el.classList.add(cls);
  };

  // ── Active row helpers (for keyboard navigation) ───────────────
  UI.setActiveRow = function (tbody, idx) {
    var rows = tbody.querySelectorAll("tr");
    rows.forEach(function (r, i) {
      if (i === idx) r.setAttribute("data-active-row", "1");
      else           r.removeAttribute("data-active-row");
    });
  };

  // ── Tab interaction (call after inserting tabs HTML) ────────────
  UI.bindTabs = function (container) {
    var tabs = container.querySelectorAll(".ds-tab");
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var tabId = tab.getAttribute("data-tab");
        container.querySelectorAll(".ds-tab").forEach(function (t) {
          t.classList.remove("active");
        });
        tab.classList.add("active");
        container.querySelectorAll(".ds-tab-panel").forEach(function (p) {
          if (p.getAttribute("data-panel") === tabId) {
            p.classList.remove("hidden");
          } else {
            p.classList.add("hidden");
          }
        });
      });
    });
  };

  // ── Global dismiss handlers ──────────────────────────────────────
  document.addEventListener("click", function (e) {
    var action = e.target.getAttribute && e.target.getAttribute("data-action");
    if (action === "close-modal") UI.closeModal();
    if (action === "close-drawer") UI.closeDrawer();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      UI.closeModal();
      UI.closeDrawer();
    }
  });

  global.UI = UI;
})(window);
