(function () {
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.getElementById('site-nav');
  if (!toggle || !nav) return;
  toggle.addEventListener('click', function () {
    var open = nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  nav.addEventListener('click', function (e) {
    if (e.target.tagName === 'A') {
      nav.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }
  });
})();

// Ask before risky admin actions (buttons with a data-confirm message).
document.addEventListener('click', function (e) {
  var el = e.target.closest('[data-confirm]');
  if (el && !window.confirm(el.getAttribute('data-confirm'))) e.preventDefault();
});

(function () {
  'use strict';
  document.documentElement.classList.add('js');

  /* ---------- Flash messages: dismiss button, success fades out ---------- */
  document.querySelectorAll('.flash').forEach(function (box) {
    var close = document.createElement('button');
    close.type = 'button'; close.className = 'flash-close'; close.setAttribute('aria-label', 'Dismiss message'); close.textContent = '\u00d7';
    close.addEventListener('click', function () { box.remove(); });
    box.appendChild(close);
    if (box.classList.contains('flash-success')) setTimeout(function () { box.classList.add('flash-out'); }, 7000);
  });

  /* ---------- Copy and share buttons ---------- */
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-copy]');
    if (btn) {
      var text = btn.getAttribute('data-copy'), original = btn.textContent;
      var done = function () { btn.textContent = 'Copied'; setTimeout(function () { btn.textContent = original; }, 1500); };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, function () { window.prompt('Copy this:', text); });
      else window.prompt('Copy this:', text);
      return;
    }
    var share = e.target.closest('[data-share]');
    if (share && navigator.share) navigator.share({ title: share.getAttribute('data-title'), url: share.getAttribute('data-url') }).catch(function () {});
  });
  document.querySelectorAll('[data-share]').forEach(function (b) { if (navigator.share) b.hidden = false; });

  /* ---------- Live search and filters for admin lists ---------- */
  document.querySelectorAll('form[data-live-filter]').forEach(function (form) {
    var target = document.querySelector(form.getAttribute('data-live-filter'));
    if (!target) return;
    var timer, controller;
    function run() {
      var url = new URL(form.getAttribute('action') || window.location.pathname, window.location.href);
      url.search = new URLSearchParams(new FormData(form)).toString();
      if (controller) controller.abort();
      controller = new AbortController();
      target.setAttribute('aria-busy', 'true');
      fetch(url.toString(), { credentials: 'same-origin', signal: controller.signal })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          var fresh = new DOMParser().parseFromString(html, 'text/html').querySelector(form.getAttribute('data-live-filter'));
          if (fresh) { target.innerHTML = fresh.innerHTML; history.replaceState(null, '', url.toString()); }
        })
        .catch(function (err) { if (err.name !== 'AbortError') form.submit(); })
        .then(function () { target.removeAttribute('aria-busy'); });
    }
    form.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 300); });
    form.addEventListener('submit', function (e) { e.preventDefault(); clearTimeout(timer); run(); });
  });

  /* ---------- Gentle reveal of sections on the home page ---------- */
  var reveals = document.querySelectorAll('.home .section, .home .cta');
  if ('IntersectionObserver' in window && reveals.length && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    var seen = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('is-visible'); seen.unobserve(en.target); } });
    }, { threshold: 0.12 });
    reveals.forEach(function (el) { el.classList.add('reveal'); seen.observe(el); });
    setTimeout(function () { reveals.forEach(function (el) { el.classList.add('is-visible'); }); }, 2500); // safety net
  }
})();
