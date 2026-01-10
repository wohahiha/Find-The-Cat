(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var teamCheckbox = document.getElementById("id_is_team_based");
    var maxField = document.getElementById("id_max_team_members");
    if (!teamCheckbox || !maxField) {
      return;
    }

    var fieldRow =
      document.querySelector(".form-row.field-max_team_members") ||
      maxField.closest(".form-row") ||
      maxField.closest(".field-box");

    function toggleMaxField() {
      if (!fieldRow) {
        return;
      }
      if (teamCheckbox.checked) {
        fieldRow.style.display = "";
      } else {
        fieldRow.style.display = "none";
        maxField.value = "1";
      }
    }

    teamCheckbox.addEventListener("change", toggleMaxField);
    toggleMaxField();

    hideDisabledDateShortcuts();
  });

  function hideDisabledDateShortcuts() {
    var dateFields = document.querySelectorAll("input.vDateField, input.vTimeField");
    dateFields.forEach(function (input) {
      if (!input.disabled) {
        return;
      }
      var shortcuts = input.parentElement.querySelector(".datetimeshortcuts");
      if (shortcuts) {
        shortcuts.style.display = "none";
      }
      var buttons = input.parentElement.querySelectorAll("button");
      buttons.forEach(function (btn) {
        btn.style.display = "none";
      });
    });
  }

})();
