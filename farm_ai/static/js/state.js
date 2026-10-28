/* state.js — one store, one bus. Views render FROM the store; interactions write
   TO the store and emit. Keeps render functions dumb and the data flow one-way. */
(function () {
  'use strict';
  var SF = window.SF = window.SF || {};

  var bus = {
    subs: {},
    on: function (ev, fn) { (this.subs[ev] = this.subs[ev] || []).push(fn); },
    emit: function (ev) {
      var l = this.subs[ev] || [], i;
      for (i = 0; i < l.length; i++) l[i](SF.store.get());
    }
  };
  SF.bus = bus;

  var store = {
    view: 'overview',        // overview | beds | alerts | activity (hash-routed)
    selected: null,          // bed id open in the drill-down dialog
    hours: 72,               // chart window
    data: null,              // last good /api/state payload
    status: 'loading',       // loading | online | offline
    updated: 0               // ms timestamp of the last good fetch
  };
  var writes = {};           // keeps polling from stomping on pending details between ticks

  SF.store = {
    get: function () { return store; },
    /** Seed state from location.hash if no writes are pending. */
    route: function () {
      var h = (location.hash || '').replace(/^#/, '');
      if (!h || h.indexOf('/') === -1) {
        store.selected = null;
        if (h) store.view = h in { overview: 1, beds: 1, alerts: 1, activity: 1 } ? h : store.view;
      } else {
        var parts = h.split('/');
        if (parts[0] === 'bed' && parts[1]) { store.selected = parts[1]; store.view = 'beds'; }
      }
    },
    set: function (key, value) { store[key] = value; },
    /** Track when the user changed something mid-tick so the next poll merge can detect staleness. */
    touch: function (key) { writes[key] = true; },
    touched: function (key) { return !!writes[key]; }, // (kept simple: views re-render on every tick)
    swap: function (patch) {
      for (var k in patch) if (Object.prototype.hasOwnProperty.call(patch, k)) store[k] = patch[k];
      bus.emit('change');
    }
  };
})();
