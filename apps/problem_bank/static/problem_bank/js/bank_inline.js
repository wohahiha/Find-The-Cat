// 题库导入 inline 交互脚本：比赛->分类->题目级联选择
(function () {
    function initRows(scope) {
        // TabularInline 的容器 id 会根据 related_name/prefix 变化，这里直接扫描所有包含 contest 下拉框的行，避免依赖特定 id
        var root = scope || document;
        var selects = root.querySelectorAll
            ? root.querySelectorAll('select[data-field="contest"]')
            : [];
        selects.forEach(function (contestSelect) {
            initRowBySelect(contestSelect);
        });
    }

    function initRowBySelect(contestSelect) {
        if (!contestSelect || contestSelect.dataset.bound === '1') {
            return;
        }
        contestSelect.dataset.bound = '1';
        var row = closestRow(contestSelect);
        var categorySelect = row ? row.querySelector('select[data-field="contest_category"]') : null;
        var challengeSelect = row ? row.querySelector('select[data-field="contest_challenge"]') : null;
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
        // 初始加载时根据默认值尝试同步分类/题目
        updateCategoryOptions(contestSelect, categorySelect, challengeSelect, true);
    }

    function closestRow(element) {
        if (!element) return null;
        if (element.closest) {
            return element.closest('tr') || element.closest('.form-row') || element.closest('.inline-related');
        }
        var node = element;
        while (node && node !== document.body) {
            if (
                node.tagName === 'TR' ||
                (node.classList && (node.classList.contains('form-row') || node.classList.contains('inline-related')))
            ) {
                return node;
            }
            node = node.parentElement;
        }
        return null;
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
        if (window.fetch) {
            fetch(url, { credentials: 'same-origin' })
                .then(function (resp) {
                    if (!resp.ok) throw new Error('network');
                    return resp.json();
                })
                .then(onSuccess)
                .catch(function () {
                    onSuccess({ results: [] });
                });
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
                    onSuccess({ results: [] });
                }
            } else {
                onSuccess({ results: [] });
            }
        };
        xhr.send();
    }

    function updateCategoryOptions(contestSelect, categorySelect, challengeSelect, initialLoad) {
        if (!contestSelect || !categorySelect) {
            console.warn('题库导入: 缺少必要的 select 元素', { contestSelect: !!contestSelect, categorySelect: !!categorySelect });
            return;
        }
        var contestId = contestSelect.value;
        var categoryUrl = contestSelect.dataset.categoryUrl;

        if (!categoryUrl) {
            console.error('题库导入: 缺少 data-category-url 属性');
            return;
        }

        clearSelect(categorySelect, '请选择题目分类');
        if (!contestId) {
            updateChallengeOptions(contestSelect, categorySelect, challengeSelect, initialLoad);
            return;
        }

        var url = categoryUrl + '?contest_id=' + encodeURIComponent(contestId);
        console.log('题库导入: 正在加载题目分类', { contestId: contestId, url: url });

        fetchJSON(url, function (data) {
            var results = data.results || [];
            console.log('题库导入: 获得题目分类', { count: results.length, results: results });

            results.forEach(function (item) {
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
        initRows(document);

        // 监听 Django admin 的 formset:added 事件（添加新行时）
        document.body.addEventListener('formset:added', function (event) {
            initRows(event && event.target ? event.target : document);
        });

        // 额外兼容：点击“添加另一项”后延迟扫描整页，确保克隆后的模板绑定事件
        document.body.addEventListener('click', function (event) {
            var target = event.target;
            if (!target) {
                return;
            }
            var addRowLink = null;
            if (target.closest) {
                addRowLink = target.closest('.add-row a');
            } else {
                var node = target;
                while (node && node !== document.body) {
                    if (node.classList && node.classList.contains('add-row')) {
                        addRowLink = node.querySelector && node.querySelector('a');
                        break;
                    }
                    node = node.parentElement;
                }
            }
            if (addRowLink) {
                setTimeout(function () {
                    initRows(document);
                }, 100);
            }
        });
    });
})();
