// 切换计分模式时动态显示/隐藏衰减相关字段
(function() {
  function toggleDecayFields() {
    const select = document.querySelector('#id_scoring_mode');
    const show = select && select.value === 'dynamic';
    ['decay_type', 'decay_factor', 'min_score'].forEach(function(field) {
      const el = document.querySelector('#id_' + field);
      if (!el) return;
      const row = el.closest('.form-row') || el.parentElement;
      if (row) {
        row.style.display = show ? '' : 'none';
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function() {
    const select = document.querySelector('#id_scoring_mode');
    if (!select) return;
    toggleDecayFields();
    select.addEventListener('change', toggleDecayFields);
  });
})();
