/* api.js — only file that knows about HTTP. ES5 on purpose: works on old phones
   and lab PCs over the LAN, no internet needed. */
(function () {
  'use strict';
  var SF = window.SF = window.SF || {};

  function request(method, url, body, cb) {
    var x = new XMLHttpRequest();
    x.open(method, url, true);
    if (body) x.setRequestHeader('Content-Type', 'application/json');
    x.onreadystatechange = function () {
      if (x.readyState !== 4) return;
      var data = null;
      var err = null;
      if (x.status >= 200 && x.status < 300) {
        try { data = JSON.parse(x.responseText); } catch (e) { err = e; }
      } else {
        err = new Error('HTTP ' + x.status);
      }
      if (cb) cb(err, data, x.status);
    };
    x.onerror = function () { if (cb) cb(new Error('network'), null, 0); };
    x.send(body ? JSON.stringify(body) : null);
  }

  SF.esc = function (s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  };

  SF.api = {
    state: function (cb) { request('GET', '/api/state', null, cb); },
    history: function (id, hours, cb) { request('GET', '/api/history/' + encodeURIComponent(id) + '?hours=' + hours, null, cb); },
    water: function (id, runS, cb) { request('POST', '/api/manual', { node: id, run_s: runS }, cb); }
  };
})();
