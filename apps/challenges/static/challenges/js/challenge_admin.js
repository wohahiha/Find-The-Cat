// 挑战后台表单辅助脚本：
// - 业务意图：
//   1) 仅在计分模式为“动态”时展示衰减配置。
//   2) n 血奖励：根据选择展示数量/加分输入，不衰减仅在动态模式下可选。
(function() {
  function getRow(id) {
    const el = document.querySelector('#id_' + id);
    return el ? (el.closest('.form-row') || el.parentElement) : null;
  }

  function toggleDecayFields() {
    const select = document.querySelector('#id_scoring_mode');
    const show = select && select.value === 'dynamic';
    ['decay_type', 'decay_factor', 'min_score'].forEach(function(field) {
      const row = getRow(field);
      if (row) {
        row.style.display = show ? '' : 'none';
      }
    });
  }

  function parseBonusTextarea() {
    const textarea = document.querySelector('#id_blood_bonus_points');
    if (!textarea) return [];
    return (textarea.value || '')
      .replace(/,/g, '\n')
      .split(/\n+/)
      .map(function (v) { return v.trim(); })
      .filter(function (v) { return v.length > 0; });
  }

  function renderBonusInputs() {
    const container = document.querySelector('#blood_bonus_points_list');
    const textarea = document.querySelector('#id_blood_bonus_points');
    const countEl = document.querySelector('#id_blood_reward_count');
    if (!container || !textarea || !countEl) return;
    const count = parseInt(countEl.value || '0', 10);
    const bonuses = parseBonusTextarea();
    container.innerHTML = '';
    for (let i = 0; i < count; i++) {
      const wrapper = document.createElement('div');
      wrapper.style.marginBottom = '6px';
      const label = document.createElement('label');
      label.textContent = '第 ' + (i + 1) + ' 血加分';
      label.style.display = 'inline-block';
      label.style.width = '110px';
      const input = document.createElement('input');
      input.type = 'number';
      input.min = '0';
      input.style.width = '120px';
      input.value = bonuses[i] !== undefined ? bonuses[i] : '';
      input.addEventListener('input', syncTextarea);
      wrapper.appendChild(label);
      wrapper.appendChild(input);
      container.appendChild(wrapper);
    }
    syncTextarea();
  }

  function syncTextarea() {
    const container = document.querySelector('#blood_bonus_points_list');
    const textarea = document.querySelector('#id_blood_bonus_points');
    if (!container || !textarea) return;
    const values = [];
    container.querySelectorAll('input').forEach(function (input) {
      const v = (input.value || '').trim();
      if (v.length) {
        values.push(v);
      }
    });
    textarea.value = values.join('\n');
  }

  function syncBloodRewardFields() {
    const rewardSelect = document.querySelector('#id_blood_reward_type');
    const rewardRow = getRow('blood_reward_count');
    const hiddenBonusRow = getRow('blood_bonus_points');
    const modeSelect = document.querySelector('#id_scoring_mode');
    if (!rewardSelect) return;
    const dynamicMode = modeSelect && modeSelect.value === 'dynamic';
    // 不衰减仅在动态模式可选
    const noDecayOption = rewardSelect.querySelector('option[value="no_decay"]');
    if (noDecayOption) {
      noDecayOption.disabled = !dynamicMode;
      if (!dynamicMode && rewardSelect.value === 'no_decay') {
        rewardSelect.value = 'none';
      }
    }
    const rewardType = rewardSelect.value;
    if (rewardRow) {
      rewardRow.style.display = rewardType === 'none' ? 'none' : '';
    }
    if (hiddenBonusRow) {
      hiddenBonusRow.style.display = 'none';
    }
    // bonus 行生成
    if (rewardType === 'bonus') {
      if (!document.querySelector('#blood_bonus_points_list')) {
        const container = document.createElement('div');
        container.id = 'blood_bonus_points_list';
        const targetRow = rewardRow || hiddenBonusRow || document.body;
        targetRow.appendChild(container);
      }
      renderBonusInputs();
    }
  }

  document.addEventListener('DOMContentLoaded', function() {
    const scoringSelect = document.querySelector('#id_scoring_mode');
    const rewardSelect = document.querySelector('#id_blood_reward_type');
    const rewardCount = document.querySelector('#id_blood_reward_count');
    toggleDecayFields();
    syncBloodRewardFields();
    if (scoringSelect) {
      scoringSelect.addEventListener('change', function() {
        toggleDecayFields();
        syncBloodRewardFields();
      });
    }
    if (rewardSelect) {
      rewardSelect.addEventListener('change', syncBloodRewardFields);
    }
    if (rewardCount) {
      rewardCount.addEventListener('input', syncBloodRewardFields);
    }
  });
})();
