/* views.js — render functions, one per screen + the bed drill-down.
   Written for local farmers first:
   - every number carries its meaning ("water in soil", "about 7 hours")
   - no jargon (no dBm, nodes, envelopes); "sensor box", "signal good"
   - statuses read as instructions, not codes
   - the water-tank gauge shows "how much water is left for the plants"
   Render functions only; no fetching, polling or bus logic. */
(function () {
  'use strict';
  var SF = window.SF = window.SF || {};
  var esc = SF.esc;

  /* ---------- inline icons: small hand-drawn-style SVG, never emoji ---------- */

  var ICONS = {
    water:   '<path d="M12 3.5c3.2 3.8 5.5 6.8 5.5 9.6a5.5 5.5 0 1 1-11 0c0-2.8 2.3-5.8 5.5-9.6z"/>',
    fix:     '<path d="M21 6.7a4.7 4.7 0 0 1-6.3 6.3l-7 7a2 2 0 0 1-2.8-2.8l7-7A4.7 4.7 0 0 1 18.2 4l-2.6 2.6 2.8 2.8L21 6.7z"/>',
    clock:   '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    sprout:  '<path d="M12 21v-7.5"/><path d="M12 13.5c0-4.2 3-7.2 8-7.2-.4 4.6-3.5 7.2-8 7.2z"/><path d="M12 13.5c-.3-3.2-2.6-5.4-6.5-5.4.3 3.6 2.7 5.4 6.5 5.4z"/>',
    battery: '<rect x="2.5" y="8" width="16" height="9" rx="2"/><path d="M21.5 11v3"/><path d="M6 11.5v3"/>',
    therm:   '<path d="M10 13.5a4 4 0 1 0 4 0V4.5a2 2 0 0 0-4 0v9z"/><path d="M12 8v5"/>',
    humid:   '<path d="M3 9c1.5-1.6 3-1.6 4.5 0s3 1.6 4.5 0 3-1.6 4.5 0 3 1.6 4.5 0"/><path d="M3 15c1.5-1.6 3-1.6 4.5 0s3 1.6 4.5 0 3-1.6 4.5 0 3 1.6 4.5 0"/>',
    signal:  '<path d="M4 10a12 12 0 0 1 16 0"/><path d="M7 13.4a7.4 7.4 0 0 1 10 0"/><circle cx="12" cy="17" r="1.2" fill="currentColor" stroke="none"/>'
  };

  function icon(name, size) {
    var s = size || 14;
    return '<svg class="ic" viewBox="0 0 24 24" width="' + s + '" height="' + s +
      '" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      ICONS[name] + '</svg>';
  }

  /* ---------- shared pieces ---------- */

  function chip(text, cls) {
    return '<span class="chip ' + (cls || '') + '">' + esc(text) + '</span>';
  }

  function statusOf(b) {
    if (b.no_data) return 'off';
    if (b.status === 'check_hardware') return 'warn';
    if (b.status === 'water_now') return 'critical';
    return 'ok';
  }

  /** The farmer-facing sentence for a bed's state. Same words on every surface. */
  function plain(b) {
    if (b.no_data) return 'Waiting for sensor node to report...';
    if (b.status === 'water_now') return 'Soil is dry. Give this bed water today.';
    if (b.status === 'check_hardware') return 'Hardware problem. Water by hand for now.';
    if (b.status === 'too_wet') return 'Soil is wet. No watering needed.';
    if (b.status === 'water_soon' && b.forecast_h !== null && b.forecast_h !== undefined) {
      return 'Soil is fine. Water again in about ' + Math.round(b.forecast_h) + ' hours.';
    }
    return 'Soil is fine.';
  }

  /** -85 dBm means nothing to a farmer; three plain words do. */
  function signalWord(rssi) {
    if (rssi === null || rssi === undefined) return 'unknown';
    if (rssi >= -70) return 'good';
    if (rssi >= -85) return 'ok';
    return 'weak';
  }

  function bar(b, mini) {
    var has = b.aw_pct !== null;
    var w = has ? Math.max(0, Math.min(100, b.aw_pct)) : 0;
    var low = has && b.aw_pct <= b.trigger_pct ? ' critical' : '';
    var out = '<div class="moist-bar' + (mini ? ' mini' : '') + '" role="img" aria-label="Water in soil ' +
      (has ? b.aw_pct + '%' : 'no reading') + '">' +
      '<div class="moist-band" style="left:' + b.trigger_pct + '%;width:' + Math.max(0, b.target_pct - b.trigger_pct) + '%"></div>' +
      '<div class="moist-fill' + low + '" style="width:' + w + '%"></div></div>';
    if (mini) return out;
    return out + '<p class="bar-note mono">' + (has ? '<b>' + b.aw_pct + '%</b> of the water plants can drink &middot; add water below ' + b.trigger_pct + '%' : '<b>No valid reading</b> &mdash; the sensor is not reporting') + '</p>';
  }

  function bedClass(b) {
    return 'bedcard st-' + (b.no_data ? 'off' : statusOf(b));
  }

  /** Little sensor-box line for the bottom of a card. */
  function bedMini(b) {
    return icon('battery', 12) + ' ' + b.batt_pct + '%' +
      ' &middot; ' + icon('signal', 12) + 'signal ' + signalWord(b.rssi) +
      ' &middot; heard ' + b.age_min + ' min ago';
  }

  /** The air conditions the sensor reports, in plain words; '' when none. */
  function airOf(b) {
    if (b.no_data || b.temp === null || b.temp === undefined) return '';
    var out = icon('therm', 12) + ' ' + Math.round(b.temp) + ' °C';
    if (b.hum !== null && b.hum !== undefined) {
      out += ' &middot; ' + icon('humid', 12) + ' air moisture ' + Math.round(b.hum) + '%';
    }
    return out;
  }

  /** Trend sparkline; hover tells what it is. */
  function spark(i, b, sparks) {
    var h = sparks && sparks[b.id];
    if (b.no_data) return '<div class="bt-spark"><p class="dim sub">no readings</p></div>';
    if (h) return '<div class="bt-spark" title="Water in the soil over the last 2 days. The line falling = soil drying out. The dot is right now.">' + SF.chart.spark(h, SF.chart.bedColor(i)) + '</div>';
    return '<div class="bt-spark bt-spark-wait"><p class="dim sub">&hellip;</p></div>';
  }

  /** Water-tank gauge wrapper (drawing lives in charts.js). */
  function tank(b, big) {
    return '<span class="bt-tank">' + SF.chart.tank(b, big) + '</span>';
  }

  /* ---------- Overview ---------- */

  /** What this page shows, once, in farmer words. */
  function legend() {
    return '<details class="howto" id="howto-overview">' +
      '<summary>What does this page show? &amp; the color key</summary>' +
      '<div class="howto-body">' +
      '<p><b>&ldquo;Water in soil&rdquo;</b> is the share of water plants can actually drink from this soil. ' +
      '<b>100%</b> means freshly watered, <b>0%</b> means the plant is suffering. Below the red dashed line, water the bed.</p>' +
      '<p>Colors: <span class="k-dot k-ok"></span> all good &nbsp; <span class="k-dot k-info"></span> water soon &nbsp;' +
      '<span class="k-dot k-warn"></span> fix something &nbsp; <span class="k-dot k-crit"></span> do it now.</p>' +
      '</div></details>';
  }

  function tiles(s) {
    var water = 0, crit = 0, nextH = null, i;
    for (i = 0; i < s.beds.length; i++) {
      var b = s.beds[i];
      if (b.status === 'water_now') water++;
      if (b.status === 'check_hardware') water++;
      if (b.forecast_h !== null && (nextH === null || b.forecast_h < nextH)) nextH = b.forecast_h;
    }
    for (i = 0; i < s.faults.length; i++) if (s.faults[i].severity === 'critical') crit++;
    return '<div class="tiles">' +
      tile(water, icon('water') + 'To water today', !water, !!water) +
      tile(crit, icon('fix') + 'To fix', !crit, !!crit) +
      tile(nextH === null ? '&mdash;' : Math.round(nextH) + ' h', icon('clock') + 'Next watering in', nextH === null, false) +
      tile(s.beds.length, icon('sprout') + 'Beds on the farm', false, false) +
      '</div>';
  }

  function tile(v, label, isQuiet, hot) {
    return '<div class="tile ' + (isQuiet ? 'tile-quiet' : '') + (hot ? ' hot' : '') + '">' +
      '<span class="tile-value num">' + v + '</span><span class="tile-label">' + label + '</span></div>';
  }

  /** The action sentence on a queue row. */
  function actionOf(a) {
    if (a.status === 'check_hardware') {
      return a.litres ? 'Water by hand: about ' + a.litres + ' L' : 'Check the pump and pipes';
    }
    if (a.status === 'water_now') return 'Give ' + a.minutes + ' min of water';
    if (a.status === 'water_soon') return 'water needed in about ' + Math.round(a.forecast_h || 12) + ' h';
    if (a.status === 'too_wet') return 'no watering needed';
    return 'all good';
  }

  function queueRow(a) {
    var dot = a.urgency === 'urgent' ? 'dot-critical' : a.urgency === 'today' ? 'dot-warn' :
      a.urgency === 'soon' ? 'dot-info' : 'dot-ok';
    var words = a.status === 'water_now' ? 'Do now' : a.status === 'check_hardware' ? 'Fix' :
      a.status === 'water_soon' ? 'Plan' : a.status === 'too_wet' ? 'Wet' : 'Ok';
    return '<div class="qrow" data-bed="' + esc(a.node) + '" role="button" tabindex="0" title="' +
      esc('Open ' + a.bed + ' for details') + '">' +
      '<span class="qdot ' + dot + '" aria-hidden="true"></span>' +
      '<span class="qtag mono ' + dot + '">' + words + '</span>' +
      '<span class="qname">' + esc(a.bed) + '<i class="dim">' + esc(a.crop) + '</i></span>' +
      '<span class="qact">' + actionOf(a) + '</span>' +
      '<span class="qchev" aria-hidden="true">&rsaquo;</span></div>';
  }

  function overview(s, sparks) {
    sparks = sparks || {};
    var out = legend() + tiles(s);

    var todo = [], i;
    for (i = 0; i < s.actions.length; i++) {
      if (s.actions[i].status !== 'ok') todo.push(s.actions[i]);
    }
    var pending = [];
    for (i = 0; i < (s.commands || []).length; i++) {
      if (s.commands[i].status === 'queued') pending.push(s.commands[i]);
    }
    if (pending.length) {
      out += '<div class="note note-info" role="status">' + pending.length +
        ' water' + (pending.length === 1 ? 'ing is' : 'ings are') +
        ' waiting to run &mdash; the pump starts when that bed&rsquo;s sensor box checks in (about every 15 minutes).</div>';
    }

    var allNoData = s.beds.length > 0 && s.beds.every(function (b) { return b.no_data; });
    if (allNoData) {
      out += '<div class="card pad" style="text-align:center; padding: 28px 16px;">' +
        '<h3 style="margin: 0 0 8px 0;">Waiting for Hardware Telemetry</h3>' +
        '<p class="sub" style="margin: 0;">No sensor packets have arrived yet. Start your ESP32 in Wokwi (or run the gateway bridge) to begin live monitoring.</p></div>';
    } else if (todo.length) {
      out += '<h2 class="sect">What to do first</h2><div class="queue">';
      for (i = 0; i < todo.length; i++) {
        if (todo[i].urgency === 'none' && todo.length > 3) continue;
        out += queueRow(todo[i]);
      }
      out += '</div>';
    } else {
      out += '<div class="card ok">Every bed has enough water. Nothing to do.</div>';
    }

    out += '<h2 class="sect">Water in the soil, last 2 days</h2><div class="card pad pulse-card">' +
      SF.chart.pulse(sparks, s.beds) +
      '<p class="sub pulse-cap">Each line is one bed. <b>The line falling = the soil is drying out.</b> ' +
      'A bed under the red dashed line needs water. The bed name is at the end of its own line.</p></div>';

    out += '<h2 class="sect">When to water next</h2><div class="card pad sched-card">' +
      SF.chart.schedule(s.beds) +
      '<p class="sub pulse-cap"><b>Short red bars = water today.</b> Long green bars can wait. ' +
      'Open a bed below to see its full history or to water it.</p></div>';

    out += '<p class="sub go-beds">Every bed in full detail, with its history and watering: <a href="#beds">open the Beds tab</a></p>';
    return out;
  }

  /* ---------- Beds ---------- */

  function bedCard(i, b, sparks, changed) {
    if (b.no_data) {
      return '<article class="' + bedClass(b) + '"><div class="card-accent" aria-hidden="true"></div>' +
        '<h3 class="card-title">' + esc(b.bed) + '</h3>' +
        '<p class="card-detail">Waiting for hardware. The sensor node has not reported yet &mdash; start the node in Wokwi to stream live telemetry.</p>' +
        '</article>';
    }
    var value = b.aw_pct === null ? '&mdash;' : b.aw_pct + '%';
    var stageIn = esc(b.stage);
    return '<article class="' + bedClass(b) + (changed ? ' just-changed' : '') +
      '" data-bed="' + esc(b.id) + '" tabindex="0" role="button" title="Open ' + esc(b.bed) + ' for details and watering">' +
      '<div class="card-accent" aria-hidden="true"></div>' +
      '<header class="bedcard-head"><div><h3 class="card-title">' + esc(b.bed) + '</h3>' +
      '<p class="sub">' + esc(b.crop) + ' &middot; day ' + b.day + ' (' + stageIn + ') &middot; ' + esc(b.soil) + '</p></div>' +
      chip(b.auto ? 'Waters itself' : 'You water it', b.auto ? 'chip-auto' : 'chip-manual') + '</header>' +
      '<div class="bedbig">' + tank(b, true) +
        '<span class="bb-right"><span class="pct num">' + value + '<i class="bt-cap">water in soil</i></span>' +
        '<span class="stat plain">' + (b.forecast_h === null || b.forecast_h === undefined ? 'Waiting for more readings&hellip;' :
          'Water needed in about <b>' + Math.round(b.forecast_h) + ' h</b>') + '</span></span></div>' +
      spark(i, b, sparks) +
      bar(b, true) +
      '<p class="bed-plain">' + plain(b) + '</p>' +
      (airOf(b) ? '<p class="bed-sub">' + airOf(b) + '</p>' : '') +
      '<p class="bed-sub">' + bedMini(b) +
      ' &middot; last watering: ' + (b.last_water ? esc(b.last_water) : 'none yet') + '</p>' +
      '</article>';
  }

  function beds(s, sparks, changed) {
    if (!s.beds.length) return '<div class="card empty">No beds configured yet.</div>';
    var out = '<div class="grid beds">';
    for (var i = 0; i < s.beds.length; i++) out += bedCard(i, s.beds[i], sparks, changed && changed[s.beds[i].id]);
    return out + '</div>';
  }

  /* ---------- Alerts ---------- */

  function alertCard(q) {
    var steps = '', i;
    for (i = 0; i < q.what_to_check.length; i++) steps += '<li>' + esc(q.what_to_check[i]) + '</li>';
    return '<article class="card fault severity-' + q.severity + '">' +
      '<div class="card-accent" aria-hidden="true"></div>' +
      '<div class="actclass"><div><h3 class="card-title">' + esc(q.bed) + ' &middot; ' + esc(q.title) + '</h3>' +
      '<p class="evidence"><b>Seen on the sensors:</b> ' + esc(q.evidence) + '</p></div>' +
      chip(q.severity, 'chip-' + q.severity) + '</div>' +
      '<details class="steps-fold" id="alert-fold-' + esc(q.node || q.bed) + '"><summary>How to fix it (' + q.what_to_check.length + ')</summary>' +
      '<ul class="steps">' + steps + '</ul></details></article>';
  }

  function alerts(s) {
    if (!s.faults.length) return '<div class="card ok">All equipment is healthy. Pump, pipes, battery and sensors are fine.</div>';
    var out = '', i;
    for (i = 0; i < s.faults.length; i++) out += alertCard(s.faults[i]);
    return out;
  }

  /* ---------- Activity ---------- */

  function activityRow(c) {
    var mins = Math.round(c.run_s / 60);
    var dot = c.source === 'farmer' ? 'dot-manual' : c.status === 'sent' ? 'dot-sent' : 'dot-queued';
    var who = c.source === 'farmer' ? 'you asked' : 'the system decided';
    var why = c.reason && c.reason !== 'manual' ? ' &mdash; ' + whyShort(c.reason) : '';
    var how = c.status === 'queued' ? '<i class="waits">starts at its next check-in</i>' : esc(c.time);
    return '<div class="act-row">' +
      '<span class="qdot ' + dot + '" aria-hidden="true"></span>' +
      '<div class="act-main"><b>' + esc(c.bed) + '</b> &middot; ' + mins + ' min of water' +
      ' &middot; <span class="dim">' + who + why + '</span></div>' +
      '<span class="act-time mono">' + how + '</span></div>';
  }

  function activity(s) {
    if (!s.commands || !s.commands.length) {
      return '<div class="card empty">Nothing has been watered yet. Every automatic watering, and every watering you ask for, will be listed here.</div>';
    }
    var out = '', i;
    for (i = 0; i < s.commands.length; i++) out += activityRow(s.commands[i]);
    return '<div class="feed">' + out + '</div>';
  }

  /* ---------- Bed drill-down ---------- */

  function whoWatered(c) {
    return c.source === 'farmer' ? 'you' : 'the system';
  }

  function wateringList(s, nid) {
    var rows = '', i, n = 0;
    var cmds = s.commands || [];
    for (i = 0; i < cmds.length && n < 8; i++) {
      if (cmds[i].node !== nid) continue;
      n++;
      rows += '<li><span class="mono"><b>' + Math.round(cmds[i].run_s / 60) + ' min</b></span> of water &middot; ' +
        (cmds[i].status === 'queued' ? '<i class="waits">starts at its next check-in</i>' : esc(cmds[i].time)) +
        ' &middot; ' + whoWatered(cmds[i]) +
        (cmds[i].reason && cmds[i].reason !== 'manual' ? ' &mdash; ' + whyShort(cmds[i].reason) : '') + '</li>';
    }
    return '<p class="list-label">Previous waterings</p><ul class="steps history-list">' +
      (rows || '<li class="dim">This bed has not been watered yet.</li>') + '</ul>';
  }

  function whyShort(t) {
    t = String(t);
    if (t.length > 72) t = t.slice(0, 69) + '&hellip;';
    return t;
  }

  /** Liter estimate for a manual 5-min watering, from the advice if it has one. */
  function litresOf(b, s) {
    var acts = s.actions || [];
    for (var i = 0; i < acts.length; i++) {
      if (acts[i].node === b.id && acts[i].litres) return acts[i].litres;
    }
    return 20;
  }

  /** Two-step watering: arm shows what will happen; confirm actually queues it. */
  function wateringPanel(b, s, armed) {
    var litre = litresOf(b, s);
    var fault = null, i;
    for (i = 0; i < (s.faults || []).length; i++) if (s.faults[i].node === b.id) fault = s.faults[i];
    var msg = '<p>Opens the pump on this bed for <b>5 minutes</b> (about ' + litre + ' L of water).</p>' +
      '<p class="sub">The command is sent to the sensor box now, and the pump starts at its next check-in &mdash; within about 15 minutes.</p>';
    if (fault) {
      msg += '<p class="bnote"><b>Note:</b> this bed has a hardware problem (' + esc(fault.title) +
        '). The pump may not run &mdash; if it does not, water by hand.</p>';
    }
    if (armed === b.id) {
      return '<div class="waterbox st-armed"><h3 class="card-title">Confirm the watering</h3>' + msg +
        '<div class="water-actions">' +
        '<button type="button" class="btn" data-water-confirm="' + esc(b.id) + '">Yes, water this bed now</button>' +
        '<button type="button" class="btn btn-ghost" data-water-cancel>Cancel</button></div></div>';
    }
    return '<div class="waterbox"><h3 class="card-title">Water this bed</h3>' +
      '<p>This sends a 5-minute watering (about ' + litre + ' L). Nothing starts yet &mdash; you confirm it in the next step.</p>' +
      '<button type="button" class="btn" data-water-arm="' + esc(b.id) + '">Water this bed&hellip;</button></div>';
  }

  function dialogBody(s, armed) {
    var b = null, i;
    for (i = 0; i < s.beds.length; i++) if (s.beds[i].id === s.selected) b = s.beds[i];
    if (!b) return '';
    var head = '<div class="dstat-row">' +
      dstat('Crop', esc(b.crop)) +
      dstat('Plant age', 'day ' + b.day + ' ' + esc(b.stage)) +
      dstat('Soil', esc(b.soil)) +
      dstat('Heard', b.age_min + ' min ago') +
      dstat('Battery', b.batt_pct + '%') +
      dstat('Signal', signalWord(b.rssi) + ' <i class="dim mono">(' + b.rssi + ' dBm)</i>') +
      (airOf(b) ? dstat('Air', airOf(b)) : '') +
      '</div>';
    var chartNote = '<p class="sub">The shaded band = where the soil should stay. ' +
      'Blue marks = waterings. Red dashed = add water when the soil line gets here. ' +
      'This chart counts <i>all</i> water in the soil; the big % on the card counts only what the roots can drink.</p>';
    var words = '<div class="card pad"><h3 class="card-title">Advice</h3><p class="card-detail">' +
      esc(b.headline) + '</p><p class="card-detail">' + esc(b.detail) + '</p></div>';
    var tanks = '<div class="chart-block">' + wateringPanel(b, s, armed) + '</div>';
    return '<div class="card pad">' + head + '</div>' + tanks +
      '<p class="list-label">Water in the soil now</p>' + bar(b, false) +
      words +
      wateringList(s, b.id) +
      '<div class="chart-block"><p class="list-label">History</p><div id="dialog-chart-note"></div>' + chartNote + '</div>';
  }

  function dstat(k, v) {
    return '<div class="dstat"><span class="dstat-k">' + k + '</span><span class="dstat-v">' + v + '</span></div>';
  }

  SF.views = {
    statusOf: statusOf,
    plain: plain,
    signalWord: signalWord,
    overview: overview,
    beds: beds,
    alerts: alerts,
    activity: activity,
    dialogBody: dialogBody
  };
})();
