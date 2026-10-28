/* Plain ES5 on purpose: works on old phones and lab PCs. Polls the local server; no internet needed. */
var selected = null;
function $(id) { return document.getElementById(id); }
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
function get(url, cb) { var x = new XMLHttpRequest(); x.open('GET', url, true);
  x.onreadystatechange = function () { if (x.readyState === 4 && x.status === 200) cb(JSON.parse(x.responseText)); }; x.send(); }
function post(url, data, cb) { var x = new XMLHttpRequest(); x.open('POST', url, true); x.setRequestHeader('Content-Type', 'application/json');
  x.onreadystatechange = function () { if (x.readyState === 4) cb && cb(); }; x.send(JSON.stringify(data)); }

function render(s) {
  $('farm').textContent = s.farm; $('clock').textContent = 'Updated ' + s.now + (s.sim ? ' (simulated clock)' : '');
  $('mode').innerHTML = s.sim ? '<span class="tag t-sim">SIMULATION</span>' : '';
  var a = '', i;
  for (i = 0; i < s.actions.length; i++) { var x = s.actions[i];
    if (x.status === 'ok' && s.actions.length > 3 && x.urgency === 'none') continue;
    a += '<div class="card act ' + x.urgency + '"><div class="h">' + esc(x.headline) + '</div><div class="d">' + esc(x.detail) + '</div></div>'; }
  var quiet = 0; for (i = 0; i < s.actions.length; i++) if (s.actions[i].urgency === 'none') quiet++;
  if (quiet && s.actions.length > 3) a += '<div class="sub">' + quiet + ' bed(s) need no action right now.</div>';
  $('actions').innerHTML = a || '<div class="card ok">Nothing to do right now.</div>';

  var f = '';
  for (i = 0; i < s.faults.length; i++) { var q = s.faults[i], steps = '', j;
    for (j = 0; j < q.what_to_check.length; j++) steps += '<li>' + esc(q.what_to_check[j]) + '</li>';
    f += '<div class="card fault ' + q.severity + '"><div class="h"><span class="tag t-' + q.severity + '">' + q.severity.toUpperCase() + '</span>' +
         esc(q.bed) + ': ' + esc(q.title) + '</div><ul>' + steps + '</ul><div class="ev">Evidence: ' + esc(q.evidence) + '</div></div>'; }
  $('faults').innerHTML = f || '<div class="card ok">All sensors, pumps and radio links look healthy.</div>';

  var b = '';
  for (i = 0; i < s.beds.length; i++) { var d = s.beds[i];
    if (d.no_data) { b += '<div class="card bed"><b>' + esc(d.bed) + '</b><div class="mini">No data yet</div></div>'; continue; }
    var has = d.aw_pct !== null, w = has ? Math.max(0, Math.min(100, d.aw_pct)) : 0;
    b += '<div class="card bed" onclick="pick(\'' + d.id + '\')"><div class="row"><b>' + esc(d.bed) + ' &middot; ' + esc(d.crop) + '</b>' +
      '<span><span class="tag ' + (d.auto ? 't-auto">AUTO' : 't-adv">ADVICE ONLY') + '</span></span></div>' +
      '<div class="mini">' + esc(d.stage) + ', day ' + d.day + ' &middot; ' + esc(d.soil) + ' soil</div>' +
      '<div class="bar"><div class="band" style="left:' + d.trigger_pct + '%;width:' + Math.max(0, d.target_pct - d.trigger_pct) + '%"></div>' +
      '<div class="fill ' + (has && d.aw_pct <= d.trigger_pct ? 'low' : '') + '" style="width:' + w + '%"></div></div>' +
      '<div class="mini"><b>' + (has ? d.aw_pct + '%' : 'no valid reading') + '</b> of usable water (keep above ' + d.trigger_pct + '%)</div>' +
      '<div class="mini">Battery <b>' + d.batt_pct + '%</b> (' + d.batt_v.toFixed(2) + ' V) &middot; signal ' + d.rssi + ' dBm &middot; seen ' + d.age_min + ' min ago</div>' +
      '<div class="mini">' + (d.forecast_h !== null && d.status !== 'check_hardware' ? 'Forecast: needs water in about ' + Math.round(d.forecast_h) + ' h &middot; ' : '') +
      'Last watering: ' + (d.last_water ? esc(d.last_water) : 'none') + '</div>' +
      '<div style="margin-top:8px"><button onclick="event.stopPropagation();water(\'' + d.id + '\')">Water 5 min</button></div></div>'; }
  $('beds').innerHTML = b;
  var m = s.model || {};
  $('foot').textContent = m.mae_pts_per_h !== undefined ? 'Drying-rate model: average error ' + m.mae_pts_per_h + ' points/h vs ' + m.baseline_mae_pts_per_h + ' for a simple average (' + m.improvement_pct + '% better, tested on beds it never saw, simulated data).' : '';
}
function water(id) { if (confirm('Queue a 5 minute watering for ' + id + '? It runs at the next radio check-in (within about 15 minutes).')) post('/api/manual', { node: id, run_s: 300 }); }
function pick(id) { selected = id; loadChart(); }

function loadChart() {
  if (!selected) return;
  get('/api/history/' + selected + '?hours=72', function (h) {
    if (!h.t || !h.t.length) return;
    $('chartcard').style.display = 'block'; $('charttitle').textContent = 'Soil moisture, ' + selected;
    var W = 760, H = 210, L = 38, R = 10, T = 10, B = 24, t0 = h.t[0], t1 = h.t[h.t.length - 1], i;
    var ymax = Math.max.apply(null, h.vwc.concat([h.fc + 4])), ymin = Math.min.apply(null, h.vwc.concat([h.wp - 2]));
    function X(t) { return L + (t - t0) / Math.max(1, t1 - t0) * (W - L - R); }
    function Y(v) { return T + (ymax - v) / (ymax - ymin) * (H - T - B); }
    var svg = '<rect x="' + L + '" y="' + Y(h.target) + '" width="' + (W - L - R) + '" height="' + (Y(h.trigger) - Y(h.target)) + '" fill="#cfe9d4"/>';
    for (i = 0; i < h.irr.length; i++) svg += '<line x1="' + X(h.irr[i]) + '" y1="' + T + '" x2="' + X(h.irr[i]) + '" y2="' + (H - B) + '" stroke="#4a90d9" stroke-width="2" opacity=".6"/>';
    var pts = ''; for (i = 0; i < h.t.length; i++) pts += X(h.t[i]).toFixed(1) + ',' + Y(h.vwc[i]).toFixed(1) + ' ';
    svg += '<polyline points="' + pts + '" fill="none" stroke="#22292d" stroke-width="2"/>';
    svg += '<line x1="' + L + '" y1="' + Y(h.trigger) + '" x2="' + (W - R) + '" y2="' + Y(h.trigger) + '" stroke="#d9534f" stroke-dasharray="5 4"/>';
    svg += '<text x="' + (L + 4) + '" y="' + (Y(h.trigger) - 4) + '" font-size="11" fill="#d9534f">water below this</text>';
    svg += '<text x="4" y="' + (T + 10) + '" font-size="11" fill="#5b6b6a">% soil water</text>';
    var d0 = new Date(t0 * 1000), d1 = new Date(t1 * 1000);
    svg += '<text x="' + L + '" y="' + (H - 6) + '" font-size="11" fill="#5b6b6a">' + d0.getUTCDate() + '/' + (d0.getUTCMonth() + 1) + '</text>';
    svg += '<text x="' + (W - R - 30) + '" y="' + (H - 6) + '" font-size="11" fill="#5b6b6a">' + d1.getUTCDate() + '/' + (d1.getUTCMonth() + 1) + '</text>';
    $('chart').innerHTML = svg;
  });
}

function tick() { get('/api/state', function (s) { render(s); if (!selected && s.beds.length) { selected = s.beds[0].id; } loadChart(); }); }
tick(); setInterval(tick, 3000);
