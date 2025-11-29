// 题库导入 inline 交互脚本：比赛->分类->题目级联选择
(function () {
    function initRows() {
        document.querySelectorAll('.dynamic-bankchallenge_set').forEach(function (row) {
            initRow(row);
        });
    }

    function initRow(row) {
        if (!row) return;
        var contestSelect = row.querySelector('select[data-field="contest"]');
        if (!contestSelect || contestSelect.dataset.bound === '1') {
            return;
        }
        contestSelect.dataset.bound = '1';
        var categorySelect = row.querySelector('select[data-field="contest_category"]');
        var challengeSelect = row.querySelector('select[data-field="contest_challenge"]');
        if (categorySelect) {
            categorySelect.addEventListener('change', function () {
                updateChallengeOptions(contestSelect, categorySelect, challengeSelect, false);
            });
        }
        contestSelect.addEventListener('change', function () {
            clearSelect(categorySelect, '请选择题目分类');
            clearSelect(challengeSelect, '请选择具体题目');
            updateCategoryOptions(contestSelect, categorySelect, challengeSelect, false);
        });
        updateCategoryOptions(contestSelect, categorySelect, challengeSelect, true);
    }

    function clearSelect(select, placeholder) {
        if (!select) return;
        while (select.options.length) {
            select.remove(0);
        }
        var option = document.createElement('option');
        option.value = '';
        option.textContent = placeholder || '---------';
        select.appendChild(option);
        select.value = '';
    }

    function fetchJSON(url, onSuccess) {
        if (!url) {
            onSuccess({ results: [] });
            return;
        }
        fetch(url, { credentials: 'same-origin' })
            .then(function (resp) {
                if (!resp.ok) throw new Error('network');
                return resp.json();
            })
            .then(onSuccess)
            .catch(function () {
                onSuccess({ results: [] });
            });
    }

    function updateCategoryOptions(contestSelect, categorySelect, challengeSelect, initialLoad) {
        if (!contestSelect || !categorySelect) {
            return;
        }
        var contestId = contestSelect.value;
        var categoryUrl = contestSelect.dataset.categoryUrl;
        clearSelect(categorySelect, '请选择题目分类');
        if (!contestId) {
            updateChallengeOptions(contestSelect, categorySelect, challengeSelect, initialLoad);
            return;
        }
        var url = categoryUrl + '?contest_id=' + encodeURIComponent(contestId);
        fetchJSON(url, function (data) {
            (data.results || []).forEach(function (item) {
                var option = document.createElement('option');
                option.value = item.id;
                option.textContent = item.name;
                categorySelect.appendChild(option);
            });
            var initial = categorySelect.dataset.initial || '';
            if (initial && (initialLoad || !categorySelect.value)) {
                categorySelect.value = initial;
                categorySelect.dataset.initial = '';
            }
            updateChallengeOptions(contestSelect, categorySelect, challengeSelect, initialLoad);
        });
    }

    function updateChallengeOptions(contestSelect, categorySelect, challengeSelect, initialLoad) {
        if (!contestSelect || !challengeSelect) {
            return;
        }
        var contestId = contestSelect.value;
        clearSelect(challengeSelect, '请选择具体题目');
        if (!contestId) {
            return;
        }
        var challengeUrl = contestSelect.dataset.challengeUrl;
        var url = challengeUrl + '?contest_id=' + encodeURIComponent(contestId);
        if (categorySelect && categorySelect.value) {
            url += '&category_id=' + encodeURIComponent(categorySelect.value);
        }
        fetchJSON(url, function (data) {
            (data.results || []).forEach(function (item) {
                var option = document.createElement('option');
                option.value = item.id;
                option.textContent = item.title + ' (' + item.slug + ')';
                challengeSelect.appendChild(option);
            });
            var initial = challengeSelect.dataset.initial || '';
            if (initial && (initialLoad || !challengeSelect.value)) {
                challengeSelect.value = initial;
                challengeSelect.dataset.initial = '';
            }
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initRows();
        document.body.addEventListener('formset:added', function (event) {
            var row = event.target;
            if (row && row.classList && row.classList.contains('dynamic-bankchallenge_set')) {
                initRow(row);
            } else if (row && row.querySelector) {
                row.querySelectorAll('.dynamic-bankchallenge_set').forEach(initRow);
            }
        });
    });
})();
