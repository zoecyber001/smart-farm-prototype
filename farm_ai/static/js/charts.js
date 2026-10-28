/* charts.js — dependency-free SVG charts. Flat fills + hairlines only; no library, no CDN.
   Research-backed rules applied here:
   - Sparklines: "everything removed except the data line" (Tufte) — no axes, no labels,
     one small end-point dot so the eye lands on "now".
   - One farm-wide overview chart (the pulse), not one chart per screen mixed with prose.
   - Direct line-end labels instead of a legend box (Few) — the name sits at its own line.
   - The drill-down keeps a full-featured single-series chart with band + trigger + event marks.
   - Cap of overlaid series at 5 (this farm's bed count).
*/
(function () {
  'use strict';
  var SF = window.SF = window.SF || {};

  /* drill-down chart geometry */
  var W = 760, H = 240, L = 44, R = 12, T = 14, B = 28;
  var INK = '#2f5e49', BAND = '#e3efe2', TRIGGER = '#b23a2f', WATER = '#3d6b9e', GRID = '#e4e0d3', LABEL = '#7a8377';

  /* pulse chart geometry */
  var PW = 760, PH = 210, PL = 38, PR = 52, PT = 8, PB = 24;   // PR leaves room for line-end labels
  var PGRID = '#e4e0d3', PLABEL = '#7a8377';
  var PALETTE = ['#2c5e45', '#9a6310', '#33608e', '#7a3a52', '#5a6d3c'];

  /** % plant-available water 0..100 for a reading against its bed's soil constants. */
  function avail(v, wp, fc) {
    if (fc <= wp) return 0;
    return Math.max(0, Math.min(100, (v - wp) / (fc - wp) * 100));
  }

  function pathOf(pts) {
    var p = 'M' + pts[0][0].toFixed(1) + ' ' + pts[0][1].toFixed(1);
    for (var i = 1; i < pts.length; i++) p += ' L' + pts[i][0].toFixed(1) + ' ' + pts[i][1].toFixed(1);
    return p;
  }

  /** Unique UTC-day tick positions within [t0..t1], mapped by scale(). */
  function dayTicks(t0, t1) {
    var seen = {}, out = [];
    for (var t = t0; t <= t1; t += 86400) {
      var d = new Date(t * 1000);
      var key = d.getUTCFullYear() + '-' + d.getUTCMonth() + '-' + d.getUTCDate();
      if (seen[key]) continue;
      seen[key] = 1;
      out.push({ t: t, label: d.getUTCDate() + '/' + (d.getUTCMonth() + 1) });
    }
    return out;
  }

  SF.chart = {
    bedColor: function (i) { return PALETTE[i % PALETTE.length]; },

    /** history: {t[], vwc[], irr[], trigger, target, wp, fc} -> <g> for viewBox 0 0 W H. */
    soil: function (h) {
      if (!h || !h.t || h.t.length < 2) {
        return '<text x="14" y="40" font-size="12" fill="' + LABEL + '">Not enough data yet for a chart.</text>';
      }
      var t0 = h.t[0], t1 = h.t[h.t.length - 1], i;
      var maxV = Math.max.apply(null, h.vwc.concat([h.target + 2, h.fc]));
      var minV = Math.min.apply(null, h.vwc.concat([h.trigger - 2, h.wp]));
      var span = Math.max(1, maxV - minV);

      function X(t) { return L + (t - t0) / Math.max(1, t1 - t0) * (W - L - R); }
      function Y(v) { return T + (maxV - v) / span * (H - T - B); }

      var s = '';
      var gLo = Math.ceil(minV), gHi = Math.floor(maxV);
      var step = span > 20 ? 10 : span > 8 ? 5 : 2;
      for (var g = gLo; g <= gHi; g += step) {
        s += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(g).toFixed(1) + '" y2="' + Y(g).toFixed(1) + '" stroke="' + GRID + '" stroke-width="1"/>';
        s += '<text x="' + (L - 6) + '" y="' + (Y(g) + 3.5).toFixed(1) + '" font-size="10" fill="' + LABEL + '" text-anchor="end">' + g + '</text>';
      }
      s += '<rect x="' + L + '" y="' + Y(h.target).toFixed(1) + '" width="' + (W - L - R) + '" height="' + Math.max(0, Y(h.trigger) - Y(h.target)).toFixed(1) + '" fill="' + BAND + '"/>';
      s += '<line x1="' + L + '" x2="' + (W - R) + '" y1="' + Y(h.trigger).toFixed(1) + '" y2="' + Y(h.trigger).toFixed(1) + '" stroke="' + TRIGGER + '" stroke-width="1.5" stroke-dasharray="5 4"/>';
      s += '<text x="' + (W - R - 4) + '" y="' + (Y(h.trigger) - 5).toFixed(1) + '" font-size="10" fill="' + TRIGGER + '" text-anchor="end">water below this</text>';
      for (i = 0; i < (h.irr || []).length; i++) {
        s += '<line x1="' + X(h.irr[i]).toFixed(1) + '" y1="' + (T + 2) + '" x2="' + X(h.irr[i]).toFixed(1) + '" y2="' + (H - B) + '" stroke="' + WATER + '" stroke-width="2" opacity=".55"/>';
      }
      var pts = [];
      for (i = 0; i < h.t.length; i++) pts.push([X(h.t[i]), Y(h.vwc[i])]);
      var line = pathOf(pts);
      var area = line + ' L' + pts[pts.length - 1][0].toFixed(1) + ' ' + (H - B) + ' L' + pts[0][0].toFixed(1) + ' ' + (H - B) + ' Z';
      s += '<path d="' + area + '" fill="' + INK + '" opacity="0.07"/>';
      s += '<path d="' + line + '" fill="none" stroke="' + INK + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>';
      var ticks = dayTicks(t0, t1);
      for (i = 0; i < ticks.length; i++) {
        s += '<text x="' + X(ticks[i].t).toFixed(1) + '" y="' + (H - 8) + '" font-size="10" fill="' + LABEL + '" text-anchor="middle">' + ticks[i].label + '</text>';
      }
      s += '<text x="10" y="' + ((T + H - B) / 2).toFixed(1) + '" transform="rotate(-90 10 ' + ((T + H - B) / 2).toFixed(1) + ')" font-size="10" fill="' + LABEL + '" text-anchor="middle">soil water %</text>';
      return '<g>' + s + '</g>';
    },

    /** Tiny trend, everything removed except the line + end dot. h: {t[], vwc[], wp, fc}. */
    spark: function (h, color) {
      if (!h || !h.t || h.t.length < 2) return '';
      var SW = 160, SH = 40, PT2 = 4, PB2 = 3;
      var x0 = h.t[0], x1 = h.t[h.t.length - 1];
      function X(t) { return (t - x0) / Math.max(1, x1 - x0) * SW; }
      function Y(v) { return PT2 + (100 - v) / 100 * (SH - PT2 - PB2); }
      var pts = [];
      for (var i = 0; i < h.t.length; i++) pts.push([X(h.t[i]), Y(avail(h.vwc[i], h.wp, h.fc))]);
      var line = pathOf(pts);
      var area = line + ' L' + pts[pts.length - 1][0].toFixed(1) + ' ' + (SH - PB2) + ' L' + pts[0][0].toFixed(1) + ' ' + (SH - PB2) + ' Z';
      var end = pts[pts.length - 1];
      return '<svg class="spark" viewBox="0 0 ' + SW + ' ' + SH + '" width="100%" height="' + SH + '" preserveAspectRatio="none" aria-hidden="true">' +
        '<path d="' + area + '" fill="' + color + '" opacity=".10"/>' +
        '<path d="' + line + '" fill="none" stroke="' + color + '" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>' +
        '<circle cx="' + end[0].toFixed(1) + '" cy="' + end[1].toFixed(1) + '" r="2.6" fill="' + color + '"/></svg>';
    },

    /** Farm pulse: every bed on one % usable water axis, names labelled at line ends. */
    pulse: function (hists, beds) {
      var usable = [], i;
      for (i = 0; i < beds.length; i++) {
        var h = hists[beds[i].id];
        if (h && h.t && h.t.length > 1) usable.push(i);
      }
      if (!usable.length) return '<p class="sub">Trends appear here within a few readings.</p>';
      var tMin = Infinity, tMax = -Infinity;
      for (i = 0; i < usable.length; i++) {
        h = hists[beds[usable[i]].id];
        tMin = Math.min(tMin, h.t[0]);
        tMax = Math.max(tMax, h.t[h.t.length - 1]);
      }
      function X(t) { return PL + (t - tMin) / Math.max(1, tMax - tMin) * (PW - PL - PR); }
      function Y(v) { return PT + (100 - v) / 100 * (PH - PT - PB); }

      var s = '';
      [0, 25, 50, 75, 100].forEach(function (lvl) {
        s += '<line x1="' + PL + '" x2="' + (PW - PR) + '" y1="' + Y(lvl).toFixed(1) + '" y2="' + Y(lvl).toFixed(1) + '" stroke="' + PGRID + '" stroke-width="1"/>';
        s += '<text x="' + (PL - 5) + '" y="' + (Y(lvl) + 3).toFixed(1) + '" font-size="9" fill="' + PLABEL + '" text-anchor="end">' + lvl + '</text>';
      });
      // axis caption lives in the left margin (rotated), so it can never share
      // a row with the tick numbers the way "soil water %" and "100" did
      s += '<text x="10" y="' + ((PT + PH - PB) / 2).toFixed(1) + '" transform="rotate(-90 10 ' + ((PT + PH - PB) / 2).toFixed(1) + ')" font-size="9" fill="' + PLABEL + '" text-anchor="middle">soil water %</text>';

      // red "water needed" line at the beds' average trigger, so "too dry" is
      // visible without reading any number
      var trigSum = 0, trigN = 0;
      for (i = 0; i < beds.length; i++) {
        if (beds[i].aw_pct !== null && beds[i].trigger_pct !== null && beds[i].trigger_pct !== undefined) {
          trigSum += beds[i].trigger_pct; trigN++;
        }
      }
      if (trigN) {
        var trig = Math.round(trigSum / trigN);
        s += '<line x1="' + PL + '" x2="' + (PW - PR) + '" y1="' + Y(trig).toFixed(1) + '" y2="' + Y(trig).toFixed(1) + '" stroke="#b23a2f" stroke-width="1.4" stroke-dasharray="5 4"/>';
        s += '<text x="' + (PL + 6) + '" y="' + (Y(trig) + 11).toFixed(1) + '" font-size="9" fill="#b23a2f" font-weight="700">water needed below this</text>';
      }

      var labels = [], j;
      for (i = 0; i < beds.length; i++) {
        h = hists[beds[i].id];
        if (!h || !h.t || h.t.length < 2) {
          labels.push({ y: null, name: beds[i].bed, color: '#b9b3a2', off: true });
          continue;
        }
        var color = SF.chart.bedColor(i);
        var pts = [];
        for (j = 0; j < h.t.length; j++) pts.push([X(h.t[j]), Y(avail(h.vwc[j], h.wp, h.fc))]);
        s += '<path d="' + pathOf(pts) + '" fill="none" stroke="' + color + '" stroke-width="1.8" stroke-linejoin="round" opacity=".92"/>';
        labels.push({ y: pts[pts.length - 1][1], x: pts[pts.length - 1][0], name: beds[i].bed, color: color });
      }
      // push apart colliding end-labels (sorted by y, 12px min gap)
      var placed = labels.filter(function (l) { return l.y !== null; }).sort(function (a, b) { return a.y - b.y; });
      for (i = 1; i < placed.length; i++) {
        if (placed[i].y - placed[i - 1].y < 12) placed[i].y = placed[i - 1].y + 12;
      }
      // push-down alone can run a tight cluster of labels off the bottom of
      // the chart onto the day-tick row (PH - 6), e.g. several beds dry at
      // once. Sweep bottom-up to pull the stack back inside the plot while
      // keeping the same 12px gaps.
      for (i = placed.length - 1; i >= 0; i--) {
        if (placed[i].y > PH - 24) placed[i].y = PH - 24;
        if (i + 1 < placed.length && placed[i].y > placed[i + 1].y - 12) placed[i].y = placed[i + 1].y - 12;
      }
      for (i = 0; i < placed.length; i++) {
        s += '<circle cx="' + placed[i].x.toFixed(1) + '" cy="' + placed[i].y.toFixed(1) + '" r="3" fill="' + placed[i].color + '"/>';
        s += '<text x="' + (PW - PR + 6).toFixed(1) + '" y="' + (placed[i].y + 3).toFixed(1) + '" font-size="10" fill="' + placed[i].color + '">' +
          placed[i].name.replace('Bed ', '') + '</text>';
      }
      var ticks = dayTicks(tMin, tMax);
      var maxTicks = Math.max(1, Math.floor((PW - PL - PR) / 60));
      if (ticks.length > maxTicks) ticks = ticks.slice(-2);
      for (i = 0; i < ticks.length; i++) {
        s += '<text x="' + X(ticks[i].t).toFixed(1) + '" y="' + (PH - 6) + '" font-size="9" fill="' + PLABEL + '" text-anchor="middle">' + ticks[i].label + '</text>';
      }
      return '<svg viewBox="0 0 ' + PW + ' ' + PH + '" width="100%" role="img" aria-label="Farm pulse: usable water per bed over the last two days">' +
        '<g>' + s + '</g></svg>';
    },

    /**
     * Water-tank gauge: a farmer reads "how full is the water tank" at a glance.
     * Blue fill = water plants can drink; red dashed line = add water once it
     * drops below here. b: bed, big: bigger card variant.
     */
    tank: function (b, big) {
      var TRIG = b.trigger_pct === undefined || b.trigger_pct === null ? 25 : b.trigger_pct;
      var has = b.aw_pct !== null && b.aw_pct !== undefined && !b.no_data;
      var p = has ? Math.max(0, Math.min(100, b.aw_pct)) : 0;
      var low = has && b.aw_pct <= TRIG;
      var TX = 8, TW = 30, TY = 4, TH = 62, BOT = TY + TH;
      var depth = TH * p / 100;
      var wTop = BOT - depth;
      var trigY = BOT - TH * TRIG / 100;
      var col = has ? (low ? '#a83226' : '#2f6f9e') : '#d8d3c4';
      var s = '<rect x="' + TX + '" y="' + TY + '" width="' + TW + '" height="' + TH + '" rx="7" fill="#f5f3ec" stroke="#c9c3b1" stroke-width="1.5"/>';
      if (has && depth > 0.5) {
        s += '<rect x="' + (TX + 2) + '" y="' + wTop.toFixed(1) + '" width="' + (TW - 4) + '" height="' + depth.toFixed(1) + '" fill="' + col + '" opacity=".85"/>';
      }
      if (has) {
        s += '<line x1="' + (TX + 2) + '" x2="' + (TX + TW - 2) + '" y1="' + trigY.toFixed(1) + '" y2="' + trigY.toFixed(1) + '" stroke="#b23a2f" stroke-width="1.4" stroke-dasharray="4 3"/>';
      }
      var cls = 'tank' + (big ? ' tank-big' : '');
      var msg = has ? ('Water left in this soil: ' + p + '%. Red dashed line: add water below this.') : 'Not reporting right now.';
      return '<svg class="' + cls + '" viewBox="0 0 46 70" width="' + (big ? 52 : 40) + '" height="' + (big ? 78 : 62) + '" role="img" aria-label="' + msg + '"><title>' + msg + '</title>' + s + '</svg>';
    },

    /**
     * "When to water": one horizontal bar per bed = hours until that bed needs
     * water (capped at 3 days). Short red bars act first. null forecast = grey.
     */
    schedule: function (beds) {
      var rows = [], i;
      for (i = 0; i < beds.length; i++) {
        var b = beds[i];
        var f = (b.no_data || b.forecast_h === null || b.forecast_h === undefined || b.aw_pct === null) ? null : Math.max(0, b.forecast_h);
        rows.push({ name: b.bed, f: f });
      }
      rows.sort(function (a, c) {
        var fa = a.f === null ? Infinity : a.f, fc = c.f === null ? Infinity : c.f;
        return fa - fc;
      });
      var LH = 58, RHT = 96, ROW = 30, SW = 760;
      var plotW = SW - LH - RHT;
      function X(f) { return LH + Math.max(0, Math.min(1, f / 72)) * plotW; }
      var SH = rows.length * ROW + 30;
      var s = '';
      var ticks = [[0, 'now'], [24, '1 day'], [48, '2 days'], [72, '3 days']];
      for (i = 0; i < ticks.length; i++) {
        s += '<line x1="' + X(ticks[i][0]).toFixed(1) + '" x2="' + X(ticks[i][0]).toFixed(1) + '" y1="4" y2="' + (SH - 24) + '" stroke="#e4e0d3" stroke-width="1"/>';
        s += '<text x="' + X(ticks[i][0]).toFixed(1) + '" y="' + (SH - 8) + '" font-size="10" fill="#7a8377" text-anchor="middle">' + ticks[i][1] + '</text>';
      }
      for (i = 0; i < rows.length; i++) {
        var r = rows[i], y = i * ROW + 10;
        s += '<text x="' + (LH - 8) + '" y="' + (y + 10) + '" font-size="11" fill="#455244" text-anchor="end" font-weight="600">' + r.name + '</text>';
        if (r.f === null) {
          s += '<text x="' + (LH + 6) + '" y="' + (y + 10) + '" font-size="10" fill="#8b8877">not reporting</text>';
          continue;
        }
        var col = r.f <= 6 ? '#a83226' : r.f <= 36 ? '#9a6310' : '#2c5e45';
        var bw = Math.max(6, X(r.f) - LH);
        var label = r.f <= 1 ? 'water now' : 'about ' + Math.round(r.f) + ' h';
        s += '<rect x="' + LH + '" y="' + y + '" width="' + bw.toFixed(1) + '" height="14" rx="7" fill="' + col + '" opacity=".88">' +
          '<title>' + r.name + ': water is needed in about ' + Math.round(r.f) + ' hours</title></rect>';
        s += '<text x="' + (X(r.f) + 8).toFixed(1) + '" y="' + (y + 11) + '" font-size="11" fill="' + col + '" font-weight="700">' + label + '</text>';
      }
      return '<svg viewBox="0 0 ' + SW + ' ' + SH + '" width="100%" role="img" aria-label="How long until each bed needs watering"><g>' + s + '</g></svg>';
    }
  };
})();
