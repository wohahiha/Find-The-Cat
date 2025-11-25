// 挑战后台表单辅助脚本：
// - 业务意图：在后台编辑题目时，只有当计分模式选择“动态”时才需要展示衰减配置（衰减类型/因子/最低分）。
// - 实现方式：监听计分模式下拉框变化，动态切换相关表单行的显示/隐藏，减少出题人误填。
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
