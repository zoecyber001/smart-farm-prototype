/* Offline service worker for the farm dashboard. ES5, no build step.
   What it caches, and why:

   - App shell (html/css/js/icons/manifest): network-first so the farmer always
     gets the newest dashboard when the server is reachable; on failure the last
     cached copy answers, so the page still opens with no connectivity.
   - /api/state and /api/history/<bed>: network-first, and every good response
     is stored as it comes in. When the network is down, the last state the
     server ever returned is served, so the dashboard keeps showing the farm
     (the existing "connection lost" banner still tells you it is stale).
   - POST /api/manual (watering): never cached. If offline it fails and the app
     shows "the request did not reach the server" rather than pretending water
     was sent.

   To ship an update to the shell, bump the version below; the old cache is
   deleted on activate.
*/
'use strict';

var CACHE = 'farm-shell-v2';   // v2: clears any shell cached before the chart-caption overlap fix

var SHELL = [
  '/',
  '/service-worker.js',
  '/static/style.css',
  '/static/js/api.js',
  '/static/js/state.js',
  '/static/js/charts.js',
  '/static/js/views.js',
  '/static/js/main.js',
  '/static/manifest.webmanifest',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon-192-maskable.png',
  '/static/icons/icon-512-maskable.png'
];

function stash(req, resp) {
  if (resp && resp.ok) {
    var copy = resp.clone();
    caches.open(CACHE).then(function (c) { c.put(req, copy); });
  }
  return resp;
}

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) { return c.addAll(SHELL); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        return k === CACHE ? null : caches.delete(k);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;                 // watering commands always go over the wire
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  /* network-first, cache as the safety net; one rule for the shell and the data */
  e.respondWith(
    fetch(req).then(function (r) { return stash(req, r); }).catch(function () {
      return caches.match(req, { ignoreSearch: true }).then(function (hit) {
        if (hit) return hit;
        return caches.match('/').then(function (home) { return home || Response.error(); });
      });
    })
  );
});
