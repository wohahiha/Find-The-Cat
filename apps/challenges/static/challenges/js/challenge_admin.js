// 挑战后台表单辅助脚本：
// - 业务意图：
//   1) 仅在计分模式为“动态”时展示衰减配置
//   2) n 血奖励：根据选择展示数量/加分输入，不衰减仅在动态模式下可选
(function () {
    function getRow(id) {
        const el = document.querySelector('#id_' + id);
        return el ? (el.closest('.form-row') || el.parentElement) : null;
    }

    function toggleDecayFields() {
        const select = document.querySelector('#id_scoring_mode');
        const show = select && select.value === 'dynamic';
        ['decay_type', 'decay_factor', 'min_score'].forEach(function (field) {
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
            .map(function (v) {
                return v.trim();
            })
            .filter(function (v) {
                return v.length > 0;
            });
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

    document.addEventListener('DOMContentLoaded', function () {
        const scoringSelect = document.querySelector('#id_scoring_mode');
        const rewardSelect = document.querySelector('#id_blood_reward_type');
        const rewardCount = document.querySelector('#id_blood_reward_count');
        toggleDecayFields();
        syncBloodRewardFields();
        if (scoringSelect) {
            scoringSelect.addEventListener('change', function () {
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
        initContestCategoryOptions();

        // 隐藏靶机配置 inline 的 "靶机配置: #1" 标题
        hideMachineConfigInlineTitle();
    });

    function hideMachineConfigInlineTitle() {
        // 查找靶机配置的 inline group
        const machineGroup = document.querySelector('#challengemachineconfig_set-group');
        if (machineGroup) {
            // 查找并隐藏所有 h3 标签（"靶机配置: #1"）
            const h3Elements = machineGroup.querySelectorAll('h3');
            h3Elements.forEach(function(h3) {
                h3.style.display = 'none';
            });
        }

        // 备用方案：通过 class 查找
        const inlineRelated = document.querySelectorAll('.inline-group .inline-related h3');
        inlineRelated.forEach(function(h3) {
            if (h3.textContent && h3.textContent.indexOf('靶机配置') !== -1) {
                h3.style.display = 'none';
            }
        });
    }

    function initContestCategoryOptions() {
        const contestSelect = document.querySelector('#id_contest');
        const categorySelect = document.querySelector('#id_category');
        if (!contestSelect || !categorySelect) return;
        const endpoint = contestSelect.dataset.categoryUrl;
        if (!endpoint) return;

        const initialContest = contestSelect.value;
        const initialCategory = categorySelect.dataset.initial || categorySelect.value;
        updateCategoryOptions(endpoint, contestSelect, categorySelect, initialContest, initialCategory);

        contestSelect.addEventListener('change', function () {
            updateCategoryOptions(endpoint, contestSelect, categorySelect, contestSelect.value, null);
        });
    }

    function requestCategoryOptions(url, onSuccess, onError) {
        onSuccess = typeof onSuccess === 'function' ? onSuccess : function () {};
        onError = typeof onError === 'function' ? onError : function () {};
        if (window.fetch && window.Promise) {
            window.fetch(url, { credentials: 'same-origin' })
                .then(function (resp) { return resp.json(); })
                .then(onSuccess)
                .catch(onError);
            return;
        }
        var xhr = new XMLHttpRequest();
        xhr.open('GET', url, true);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    var data = JSON.parse(xhr.responseText);
                    onSuccess(data);
                } catch (err) {
                    onError(err);
                }
            } else {
                onError(new Error('Request failed'));
            }
        };
        xhr.send();
    }

    function updateCategoryOptions(endpoint, contestSelect, categorySelect, contestId, selectedId) {
        if (!categorySelect) return;
        resetCategorySelect(categorySelect);
        if (!contestId) {
            categorySelect.disabled = true;
            return;
        }
        categorySelect.disabled = true;
        requestCategoryOptions(
            endpoint + '?contest_id=' + encodeURIComponent(contestId),
            function (data) {
                const results = data && data.results ? data.results : [];
                populateCategoryOptions(categorySelect, results, selectedId);
                categorySelect.disabled = false;
            },
            function () {
                categorySelect.disabled = false;
            }
        );
    }

    function resetCategorySelect(select) {
        while (select.options.length > 0) {
            select.remove(0);
        }
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = '请先选择比赛';
        select.appendChild(placeholder);
        select.value = '';
    }

    function populateCategoryOptions(select, items, selectedId) {
        resetCategorySelect(select);
        const placeholder = select.options[0];
        if (!items.length) {
            placeholder.textContent = '当前比赛暂无分类，请到“题目分类”中新增';
            select.value = '';
            return;
        }
        placeholder.textContent = '---------';
        items.forEach(function (item) {
            const option = document.createElement('option');
            option.value = String(item.id);
            option.textContent = item.name;
            select.appendChild(option);
        });
        if (selectedId) {
            select.value = String(selectedId);
        } else {
            select.value = '';
        }
    }
})();
