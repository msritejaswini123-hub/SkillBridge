/* ==========================================================================
   SkillBridge - script.js
   Small vanilla-JS helpers. The site works with JavaScript disabled; these
   only add convenience.
   ========================================================================== */
(function () {
  "use strict";

  /* ----------------------------------------------------------------------
     1. Register page: show only the fields that apply to the chosen role.
     ---------------------------------------------------------------------- */
  function syncRoleFields() {
    var chosen = document.querySelector('input[name="role"]:checked');
    if (!chosen) return;
    var role = chosen.value;
    document.querySelectorAll(".role-field").forEach(function (field) {
      var applies = field.getAttribute("data-for") === role;
      field.classList.toggle("hidden", !applies);
      field.querySelectorAll("input").forEach(function (input) {
        if (!applies) input.value = input.value; // keep the typed value, just hide it
      });
    });
  }
  document.querySelectorAll('input[name="role"]').forEach(function (radio) {
    radio.addEventListener("change", syncRoleFields);
  });
  syncRoleFields();

  /* ----------------------------------------------------------------------
     2. Resume upload: show the chosen file name and catch obvious mistakes
        before the request is even sent.
     ---------------------------------------------------------------------- */
  var fileInput = document.getElementById("resume");
  var fileHint = document.getElementById("file-hint");
  var MAX_BYTES = 5 * 1024 * 1024;

  if (fileInput && fileHint) {
    fileInput.addEventListener("change", function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file) {
        fileHint.textContent = "Nothing selected yet.";
        fileHint.style.color = "";
        return;
      }
      var sizeMB = (file.size / (1024 * 1024)).toFixed(2);
      var isPdf = /\.pdf$/i.test(file.name);

      if (!isPdf) {
        fileHint.textContent = "That is not a PDF. Please choose a .pdf file.";
        fileHint.style.color = "#97292a";
      } else if (file.size > MAX_BYTES) {
        fileHint.textContent = "That file is " + sizeMB + " MB - the limit is 5 MB.";
        fileHint.style.color = "#97292a";
      } else {
        fileHint.textContent = "Ready: " + file.name + " (" + sizeMB + " MB)";
        fileHint.style.color = "#006300";
      }
    });

    var resumeForm = document.getElementById("resume-form");
    if (resumeForm) {
      resumeForm.addEventListener("submit", function (event) {
        var file = fileInput.files && fileInput.files[0];
        if (!file) {
          event.preventDefault();
          fileHint.textContent = "Please choose a PDF file first.";
          fileHint.style.color = "#97292a";
          return;
        }
        if (!/\.pdf$/i.test(file.name) || file.size > MAX_BYTES) {
          event.preventDefault();
          return;
        }
        var button = resumeForm.querySelector('button[type="submit"]');
        if (button) {
          button.textContent = "Reading your resume ...";
          button.disabled = true;
        }
      });
    }
  }

  /* ----------------------------------------------------------------------
     3. Skill review: select all / clear all inside one list.
     ---------------------------------------------------------------------- */
  function setAll(selector, checked) {
    var list = document.querySelector(selector);
    if (!list) return;
    list.querySelectorAll('input[type="checkbox"]').forEach(function (box) {
      box.checked = checked;
    });
  }
  document.querySelectorAll("[data-check-all]").forEach(function (button) {
    button.addEventListener("click", function () {
      setAll(button.getAttribute("data-check-all"), true);
    });
  });
  document.querySelectorAll("[data-uncheck-all]").forEach(function (button) {
    button.addEventListener("click", function () {
      setAll(button.getAttribute("data-uncheck-all"), false);
    });
  });

  /* ----------------------------------------------------------------------
     4. Generic show/hide toggle (used for the extracted resume text).
     ---------------------------------------------------------------------- */
  document.querySelectorAll("[data-toggle]").forEach(function (button) {
    button.addEventListener("click", function () {
      var target = document.querySelector(button.getAttribute("data-toggle"));
      if (target) target.classList.toggle("hidden");
    });
  });

  /* ----------------------------------------------------------------------
     5. Candidates page: jumping to another posting without a Go button.
     ---------------------------------------------------------------------- */
  var postingSelect = document.getElementById("posting-select");
  if (postingSelect) {
    postingSelect.addEventListener("change", function () {
      var base = postingSelect.getAttribute("data-jump-base").replace(/\/$/, "");
      window.location.href = base + "/" + postingSelect.value;
    });
  }

  /* ----------------------------------------------------------------------
     6. Filter bar: re-submit as soon as a dropdown changes.
     ---------------------------------------------------------------------- */
  var filterForm = document.getElementById("filter-form");
  if (filterForm) {
    filterForm.querySelectorAll("select").forEach(function (select) {
      select.addEventListener("change", function () { filterForm.submit(); });
    });
  }

  /* ----------------------------------------------------------------------
     7. Comma-separated skill inputs: light normalisation on blur so the
        server receives a tidy list.
     ---------------------------------------------------------------------- */
  ["required_skills", "preferred_skills", "extra_skills"].forEach(function (id) {
    var input = document.getElementById(id);
    if (!input) return;
    input.addEventListener("blur", function () {
      var parts = input.value.split(",").map(function (part) {
        return part.trim();
      }).filter(function (part) { return part.length > 0; });
      input.value = parts.join(", ");
    });
  });

  /* ----------------------------------------------------------------------
     8. Auto-dismiss success/info flashes after a few seconds.
     ---------------------------------------------------------------------- */
  window.setTimeout(function () {
    document.querySelectorAll(".flash-success, .flash-info").forEach(function (flash) {
      flash.style.transition = "opacity .4s";
      flash.style.opacity = "0";
      window.setTimeout(function () { flash.remove(); }, 400);
    });
  }, 6000);
})();
