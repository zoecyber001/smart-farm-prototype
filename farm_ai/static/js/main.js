/* main.js — the conductor. Polls /api/state, routes hash -> view, wires one click
   delegation for every interaction, renders through views.js. Only SF is global. */
(function () {
  'use strict';
  var SF = window.SF;
  var VIEWS = { overview: 1, beds: 1, alerts: 1, activity: 1 };
  var state = SF.store.get();
  var healthy = false;
  var apiBusy = false;           // guard so a double-tap cannot queue two waterings
  var dialogWasOpen = null;      // bed id shown last tick, to redraw only on change
  var waterArmed = null;         // bed id whose "confirm watering" step is showing
  var lastBedVals = null;        // water reading + status per bed last tick, for change highlighting

  /* sparkline / pulse data: one history fetch per bed, backgrounded and staggered
     so it never delays the state poll or the drill-down chart */
  var SPARK_HOURS = 48;
  var sparks = {};
  var sparkFetching = false, sparkTimer = null;

  function fetchSparks() {
    if (sparkFetching || !state.data) return;
    var beds = state.data.beds || [], i = 0;
    sparkFetching = true;
    (function next() {
      if (!sparkFetching || i >= beds.length) { sparkFetching = false; return; }
      var b = beds[i++];
      if (!b || b.no_data) return setTimeout(next, 30);
      SF.api.history(b.id, SPARK_HOURS, function (err, h) {
        if (!err && h && h.t && h.t.length > 1) sparks[b.id] = h;
        clearTimeout(sparkTimer);
        sparkTimer = setTimeout(next, 150);   // keep some space between requests
      });
    })();
  }

  function $(id) { return document.getElementById(id); }

  /* innerHTML replacement that remembers which <details> the user has open,
     so the 3-second refresh does not slam their drop-downs shut */
  /* which beds' water reading (or status) is different from the previous tick.
     aw_pct is a rounded whole percent, so a change is occasional and worth a
     one-shot highlight - not a value that jitters every 3 seconds. */
  function bedChanges(s) {
    var out = {}, i;
    if (lastBedVals) {
      for (i = 0; i < s.beds.length; i++) {
        var b = s.beds[i], o = lastBedVals[b.id];
        if (o && (b.aw_pct !== o.aw || b.status !== o.status)) out[b.id] = true;
      }
    }
    lastBedVals = {};
    for (i = 0; i < s.beds.length; i++) {
      lastBedVals[s.beds[i].id] = { aw: s.beds[i].aw_pct, status: s.beds[i].status };
    }
    return out;
  }

  function setHTML(id, html) {
    var root = $(id), open = {}, keep, i;
    keep = root.querySelectorAll('details[open]');
    for (i = 0; i < keep.length; i++) if (keep[i].id) open[keep[i].id] = true;
    root.innerHTML = html;
    var now = root.querySelectorAll('details');
    for (i = 0; i < now.length; i++) if (now[i].id && open[now[i].id]) now[i].open = true;
  }

  /* ---------- routing ---------- */

  function applyHash() {
    var h = (location.hash || '').replace(/^#/, '');
    if (h.indexOf('bed/') === 0) {
      state.selected = h.slice(4);
      state.view = 'beds';
    } else if (VIEWS[h]) {
      state.selected = null;
      state.view = h;
    }
  }

  /* ---------- rendering ---------- */

  function render() {
    var s = state.data;
    if (!s) return;

    $('loading').hidden = true;
    $('farm-name').textContent = s.farm;
    $('clock').textContent = 'Updated ' + s.now;
    $('sim-tag').hidden = !s.sim;

    var tabs = document.querySelectorAll('.tab');
    for (var i = 0; i < tabs.length; i++) {
      var on = tabs[i].getAttribute('data-view') === state.view;
      tabs[i].classList.toggle('is-active', on);
      tabs[i].setAttribute('aria-selected', on ? 'true' : 'false');
    }

    var crit = 0;
    for (i = 0; i < s.faults.length; i++) if (s.faults[i].severity === 'critical') crit++;
    var badge = $('count-alerts');
    badge.hidden = crit === 0;
    badge.textContent = crit;

    setHTML('view-overview', SF.views.overview(s, sparks));
    setHTML('view-beds', SF.views.beds(s, sparks, bedChanges(s)));
    setHTML('view-alerts', SF.views.alerts(s));
    setHTML('view-activity', SF.views.activity(s));
    $('view-overview').hidden = state.view !== 'overview';
    $('view-beds').hidden = state.view !== 'beds';
    $('view-alerts').hidden = state.view !== 'alerts';
    $('view-activity').hidden = state.view !== 'activity';

    var m = s.model || {};
    $('foot').textContent = (m.mae_pts_per_h !== undefined)
      ? 'Forecast accuracy: the model\u2019s water need predictions miss by ' + m.mae_pts_per_h +
        '% of water on average, vs ' + m.baseline_mae_pts_per_h + '% for a simple average ' +
        '(' + m.improvement_pct + '% better, measured on beds it never saw in training).'
      : '';

    // drill-down dialog
    if (state.selected && state.data) {
      if (dialogWasOpen !== state.selected) {
        dialogWasOpen = state.selected;
        waterArmed = null;           // a different bed opened: start at the safe step
        openDialog(s);
      } else {
        updateDialog(s);             // keep live values fresh while open
      }
    } else if (dialogWasOpen !== null) {
      dialogWasOpen = null;
      waterArmed = null;
      closeDialog();
    }
  }

  function renderChart(h) {
    var box = $('chartbox');
    if (box) {
      box.innerHTML = '<svg viewBox="0 0 760 240" width="100%" role="img" aria-label="Soil moisture history">' +
        SF.chart.soil(h) + '</svg>';
    }
  }

  function openDialog(s) {
    var b = bedOf(s);
    if (!b) { state.selected = null; return; }
    $('dialog-title').textContent = b.bed + ' \u2014 ' + b.crop;
    $('dialog-sub').textContent = 'Tap 24 h / 3 days / 7 days to change the chart. Watering is at the bottom.';
    $('dialog-body').innerHTML = dialogFrame(s);
    var panel = $('bed-dialog');
    panel.hidden = false;
    document.body.classList.add('locked');
    // next frame: fade/slide the panel in (CSS .dialog-panel starts transparent)
    window.requestAnimationFrame(function () { panel.querySelector('.dialog-panel').classList.add('dialog-in'); });
    drawChart();
    $('dialog-close').focus();
  }

  function updateDialog(s) {
    if ($('bed-dialog').hidden) return;
    $('dialog-body').innerHTML = dialogFrame(s);
    drawChart();
  }

  function dialogFrame(s) {
    var b = bedOf(s);
    var hours = state.hours;
    var wl = '', opts = [24, 72, 168], i;
    var names = ['24 h', '3 days', '7 days'];
    for (i = 0; i < opts.length; i++) {
      wl += '<button type="button" class="range' + (hours === opts[i] ? ' is-picked' : '') +
        '" data-hours="' + opts[i] + '">' + names[i] + '</button>';
    }
    return '<div class="rangebar" role="group" aria-label="History window">' + wl + '</div>' +
      '<div id="chartbox" class="chartbox"><p class="sub">Loading history&hellip;</p></div>' +
      SF.views.dialogBody(s, waterArmed);
  }

  function bedOf(s) {
    if (!s) return null;
    for (var i = 0; i < s.beds.length; i++) if (s.beds[i].id === state.selected) return s.beds[i];
    return null;
  }

  function drawChart() {
    SF.api.history(state.selected, state.hours, function (err, h) {
      if (err || !h || !h.t || !h.t.length) {
        var box = $('chartbox');
        if (box) box.innerHTML = '<p class="sub">Not enough history for a chart yet. Keep the sensor running; a chart appears within a few hours.</p>';
        return;
      }
      renderChart(h);
    });
  }

  function closeDialog() {
    var panel = $('bed-dialog');
    panel.querySelector('.dialog-panel').classList.remove('dialog-in');
    panel.hidden = true;
    document.body.classList.remove('locked');
    waterArmed = null;
    if (location.hash.indexOf('#bed/') === 0) {
      history.pushState(null, '', '#beds');
    }
  }

  /* ---------- interactions ---------- */

  function toast(msg) {
    var t = $('toast');
    t.innerHTML = msg;
    t.hidden = false;
    // force reflow so the opacity transition applies
    void t.offsetWidth;
    t.classList.add('toast-in');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(function () {
      t.classList.remove('toast-in');
      toast.timer = setTimeout(function () { t.hidden = true; }, 200);
    }, 4000);
  }

  function water(id) {
    if (apiBusy) return;
    apiBusy = true;
    SF.api.water(id, 300, function (err) {
      apiBusy = false;
      if (err) {
        toast('<b>The request did not reach the server.</b> Check the connection and try again.');
        return;
      }
      toast('Watering queued for 5 minutes (&asymp;20 L). The pump starts when that bed\u2019s sensor box checks in.');
      refresh();
    });
  }

  document.addEventListener('click', function (ev) {
    var t = ev.target;

    if (t.closest('[data-close]')) { closeDialog(); return; }

    var tab = t.closest('.tab');
    if (tab) {
      var v = tab.getAttribute('data-view');
      if (state.selected) { state.selected = null; dialogWasOpen = null; closeDialog(); }
      state.view = v;
      history.pushState(null, '', '#' + v);
      render();
      return;
    }

    var hoursBtn = t.closest('.range');
    if (hoursBtn) {
      var hours = parseInt(hoursBtn.getAttribute('data-hours'), 10);
      if (state.hours !== hours) { state.hours = hours; drawChart(); }
      var pills = document.querySelectorAll('.range');
      for (var i = 0; i < pills.length; i++) {
        pills[i].classList.toggle('is-picked', parseInt(pills[i].getAttribute('data-hours'), 10) === state.hours);
      }
      return;
    }

    // watering is two deliberate steps, only from inside the bed dialog:
    //   arm (explain what happens) -> confirm (queue the command)
    var confirmBtn = t.closest('[data-water-confirm]');
    if (confirmBtn) {
      var id = confirmBtn.getAttribute('data-water-confirm');
      waterArmed = null;
      updateDialog(state.data);
      water(id);
      return;
    }

    var armBtn = t.closest('[data-water-arm]');
    if (armBtn) {
      waterArmed = armBtn.getAttribute('data-water-arm');
      $('dialog-body').innerHTML = dialogFrame(state.data);
      return;
    }

    if (t.closest('[data-water-cancel]')) {
      waterArmed = null;
      $('dialog-body').innerHTML = dialogFrame(state.data);
      return;
    }

    var card = t.closest('[data-bed]');
    if (card) {
      state.selected = card.getAttribute('data-bed');
      history.pushState(null, '', '#bed/' + state.selected);
      state.view = 'beds';
      render();
      return;
    }
  });

  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && !$('bed-dialog').hidden) { closeDialog(); return; }
    if (ev.key !== 'Enter' && ev.key !== ' ') return;
    var btn = ev.target.closest ? ev.target.closest('[data-water-arm], [data-water-confirm], [data-water-cancel]') : null;
    if (btn) { ev.preventDefault(); btn.click(); return; }
    var row = ev.target.closest ? ev.target.closest('.qrow, [data-bed]') : null;
    if (row) { ev.preventDefault(); row.click(); }
  });

  window.addEventListener('hashchange', function () {
    applyHash();
    render();
  });

  /* ---------- polling ---------- */

  function refresh() {
    SF.api.state(function (err, s) {
      if (err) {
        healthy = false;
        $('banner-offline').hidden = false;
        return;                          // keep last data on screen while offline
      }
      if (!healthy) { healthy = true; $('banner-offline').hidden = true; }
      state.data = s;
      state.updated = Date.now();
      render();
      fetchSparks();
    });
  }

  /* offline: a service worker caches the app shell and the last server state,
     so this URL still opens and reads when the network is down. If registration
     fails (old browser, plain http on some devices), the app runs as before. */
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/service-worker.js').catch(function () { /* offline UI still works without it */ });
  }

  applyHash();
  refresh();
  setInterval(refresh, 3000);
})();
