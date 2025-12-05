(function () {
    function initRow(row) {
        if (!row || row.dataset.deleteBound === "1") {
            return;
        }
        var checkbox = row.querySelector('td.delete input[type="checkbox"]');
        if (!checkbox) {
            return;
        }
        row.dataset.deleteBound = "1";
        checkbox.style.display = "none";
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "inline-delete-toggle";
        row.querySelector("td.delete").appendChild(btn);

        function refresh() {
            if (checkbox.checked) {
                btn.textContent = "↺ 撤销";
                row.classList.add("marked-for-delete");
            } else {
                btn.textContent = "× 删除";
                row.classList.remove("marked-for-delete");
            }
        }

        btn.addEventListener("click", function (event) {
            event.preventDefault();
            checkbox.checked = !checkbox.checked;
            refresh();
        });

        refresh();
    }

    function bindAll() {
        document.querySelectorAll(".dynamic-bankcategory_set").forEach(initRow);
    }

    document.addEventListener("DOMContentLoaded", function () {
        bindAll();
        document.body.addEventListener("formset:added", function (event) {
            var newRow = event.target;
            if (!newRow) {
                return;
            }
            if (newRow.classList && newRow.classList.contains("dynamic-bankcategory_set")) {
                initRow(newRow);
            } else {
                newRow.querySelectorAll(".dynamic-bankcategory_set").forEach(initRow);
            }
        });
    });
})();
