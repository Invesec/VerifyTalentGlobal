(function () {
  var select = document.getElementById('profession');
  if (!select) return;
  var map = JSON.parse(select.getAttribute('data-groups') || '{}');
  var groups = document.querySelectorAll('fieldset.group');

  function update() {
    var active = map[select.value];
    groups.forEach(function (g) {
      var show = g.getAttribute('data-group') === active;
      g.hidden = !show;
      g.querySelectorAll('textarea, input').forEach(function (el) { el.disabled = !show; });
    });
  }
  select.addEventListener('change', update);
  update();
})();
