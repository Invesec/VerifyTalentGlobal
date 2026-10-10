(function () {
  'use strict';

  /* ---------- Password: show/hide, strength, match ---------- */
  document.querySelectorAll('input[type=password]').forEach(function (input) {
    var wrap = document.createElement('div');
    wrap.className = 'pw-wrap';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    var toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'pw-toggle';
    toggle.textContent = 'Show';
    toggle.setAttribute('aria-pressed', 'false');
    toggle.setAttribute('aria-label', 'Show password');
    toggle.addEventListener('click', function () {
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      toggle.textContent = show ? 'Hide' : 'Show';
      toggle.setAttribute('aria-pressed', show ? 'true' : 'false');
      toggle.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    });
    wrap.appendChild(toggle);

    if (input.getAttribute('autocomplete') === 'new-password' && input.id === 'password') {
      var meter = document.createElement('p');
      meter.className = 'strength';
      meter.setAttribute('aria-live', 'polite');
      wrap.parentNode.insertBefore(meter, wrap.nextSibling);
      input.addEventListener('input', function () {
        var v = input.value, score = 0;
        if (v.length >= 10) score++;
        if (v.length >= 14) score++;
        if (/[a-z]/.test(v) && /[A-Z]/.test(v)) score++;
        if (/\d/.test(v)) score++;
        if (/[^A-Za-z0-9]/.test(v)) score++;
        var label = !v ? '' : v.length < 10 ? 'Too short: use at least 10 characters' : score <= 2 ? 'Okay' : score <= 3 ? 'Good' : 'Strong';
        meter.textContent = label;
        meter.setAttribute('data-level', !v ? '' : v.length < 10 ? 'weak' : score <= 2 ? 'ok' : 'strong');
      });
    }
  });

  var pw = document.getElementById('password'), confirm = document.getElementById('confirm_password');
  if (pw && confirm) {
    var note = document.createElement('p');
    note.className = 'strength';
    note.setAttribute('aria-live', 'polite');
    confirm.closest('.field').appendChild(note);
    var check = function () {
      if (!confirm.value) { note.textContent = ''; confirm.setCustomValidity(''); return; }
      var same = pw.value === confirm.value;
      note.textContent = same ? 'Passwords match' : 'Passwords do not match yet';
      note.setAttribute('data-level', same ? 'strong' : 'weak');
      confirm.setCustomValidity(same ? '' : 'Passwords do not match');
    };
    pw.addEventListener('input', check);
    confirm.addEventListener('input', check);
  }

  /* ---------- Character counters ---------- */
  document.querySelectorAll('textarea[maxlength]').forEach(function (area) {
    var counter = document.createElement('p');
    counter.className = 'counter';
    area.parentNode.insertBefore(counter, area.nextSibling);
    var update = function () { counter.textContent = area.value.length + ' / ' + area.getAttribute('maxlength'); };
    area.addEventListener('input', update);
    update();
  });

  /* ---------- Step-by-step forms ---------- */
  document.querySelectorAll('form[data-wizard]').forEach(function (form) {
    var submit = form.querySelector('button[type=submit]');
    if (!submit) return;
    form.classList.add('wizard-on');

    var progress = document.createElement('div');
    progress.className = 'wiz-progress';
    progress.innerHTML = '<p class="wiz-text" aria-live="polite"></p><div class="wiz-track"><div class="wiz-fill"></div></div>';
    form.insertBefore(progress, form.firstChild.nextSibling);

    var nav = document.createElement('div');
    nav.className = 'wiz-nav';
    var back = document.createElement('button');
    back.type = 'button'; back.className = 'btn btn-navy'; back.textContent = 'Back';
    var next = document.createElement('button');
    next.type = 'button'; next.className = 'btn btn-gold'; next.textContent = 'Next';
    nav.appendChild(back); nav.appendChild(next);
    submit.parentNode.insertBefore(nav, submit);

    function steps() {
      return Array.prototype.filter.call(form.querySelectorAll('fieldset'), function (f) { return !f.hasAttribute('hidden'); });
    }
    var current = 0;
    function show(index) {
      var list = steps();
      current = Math.max(0, Math.min(index, list.length - 1));
      form.querySelectorAll('fieldset').forEach(function (f) { f.classList.add('wiz-off'); });
      list[current].classList.remove('wiz-off');
      var legend = list[current].querySelector('legend');
      progress.querySelector('.wiz-text').textContent = 'Step ' + (current + 1) + ' of ' + list.length + (legend ? ': ' + legend.textContent : '');
      progress.querySelector('.wiz-fill').style.width = ((current + 1) / list.length * 100) + '%';
      var last = current === list.length - 1;
      submit.hidden = !last;
      next.hidden = last;
      back.hidden = current === 0;
      list[current].scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    function valid() {
      var fields = steps()[current].querySelectorAll('input, select, textarea');
      for (var i = 0; i < fields.length; i++) {
        if (!fields[i].disabled && !fields[i].checkValidity()) { fields[i].reportValidity(); return false; }
      }
      return true;
    }
    next.addEventListener('click', function () { if (valid()) show(current + 1); });
    back.addEventListener('click', function () { show(current - 1); });
    form.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA' && current < steps().length - 1) {
        e.preventDefault();
        next.click();
      }
    });
    form.addEventListener('submit', function (e) {
      if (current < steps().length - 1) { e.preventDefault(); next.click(); }
    });
    // Choosing a profession adds or removes a step, so refresh the counter.
    var profession = document.getElementById('profession');
    if (profession) profession.addEventListener('change', function () { setTimeout(function () { show(current); }, 0); });

    // After a server error, jump to the first step that has one.
    var firstError = form.querySelector('.has-error');
    var start = 0;
    if (firstError) {
      var holder = firstError.closest('fieldset');
      var idx = steps().indexOf(holder);
      if (idx >= 0) start = idx;
    }
    show(start);
    window.scrollTo(0, 0);
  });

  /* ---------- Resend-code countdown ---------- */
  var resend = document.getElementById('resend');
  if (resend) {
    var left = parseInt(resend.getAttribute('data-cooldown'), 10) || 0;
    var label = resend.textContent;
    if (left > 0) {
      resend.disabled = true;
      var timer = setInterval(function () {
        left -= 1;
        if (left <= 0) { clearInterval(timer); resend.disabled = false; resend.textContent = label; }
        else resend.textContent = 'Send a new code in ' + left + 's';
      }, 1000);
      resend.textContent = 'Send a new code in ' + left + 's';
    }
  }
  var code = document.getElementById('code');
  if (code) code.addEventListener('input', function () { code.value = code.value.replace(/\D/g, '').slice(0, 6); });
})();
