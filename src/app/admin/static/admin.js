(function () {
  "use strict";

  function fmtTime(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    return d.toLocaleTimeString();
  }

  function renderStatus(el, s) {
    var running = s.running;
    el.dataset.running = running ? "true" : "false";
    var parts = [];
    if (running) {
      parts.push('<span class="badge running">Scan in progress…</span>');
      if (s.started_at) parts.push(' started at ' + fmtTime(s.started_at));
    } else if (s.finished_at) {
      var okClass = s.last_scan_ok === false ? '' : 'ok';
      var label = s.last_scan_ok === false ? 'Scan failed' : 'Scan completed';
      parts.push('<span class="badge ' + okClass + '">' + label + '</span>');
      parts.push(' at ' + fmtTime(s.finished_at));
      parts.push(' (' + s.total_tracks + ' indexed, ' + s.error_count + ' errors)');
    } else {
      parts.push('<span class="badge muted">Not yet scanned</span>');
    }
    el.innerHTML = parts.join('');

    var btn = document.querySelector('[data-scan-button]');
    if (btn) btn.disabled = running;
  }

  function poll() {
    fetch('/admin/scan/status', { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s) return;
        var el = document.getElementById('scan-status');
        if (!el) return;
        renderStatus(el, s);
        if (s.running) {
          setTimeout(poll, 2000);
        }
      })
      .catch(function () {
        setTimeout(poll, 5000);
      });
  }

  function initToasts() {
    var toasts = document.querySelectorAll('.toast');
    toasts.forEach(function (t) {
      setTimeout(function () {
        t.classList.add('toast-hide');
        setTimeout(function () { t.remove(); }, 400);
      }, 4000);
    });
  }

  function initScanStatus() {
    var el = document.getElementById('scan-status');
    if (!el) return;
    if (el.dataset.running === 'true') {
      poll();
    } else {
      // Fetch once anyway to reflect fresh state if user just navigated in.
      fetch('/admin/scan/status', { credentials: 'same-origin' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (s) {
          if (!s) return;
          renderStatus(el, s);
          if (s.running) setTimeout(poll, 2000);
        })
        .catch(function () {});
    }
  }

  function initScanForm() {
    var form = document.querySelector('form[data-scan-form]');
    if (!form) return;
    form.addEventListener('submit', function () {
      var el = document.getElementById('scan-status');
      if (el) {
        el.dataset.running = 'true';
        el.innerHTML = '<span class="badge running">Scan starting…</span>';
      }
      setTimeout(poll, 1000);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initToasts();
    initScanStatus();
    initScanForm();
  });
})();
