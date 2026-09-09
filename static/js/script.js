/* ==========================================================================
   SkillBridge - script.js

   Progressive enhancement only. Every page works with JavaScript disabled:
   forms submit normally, filters have a Filter button, the candidate picker has
   a <noscript> Go button. Nothing here is required to use the site.
   ========================================================================== */
(function () {
  "use strict";

  var reduceMotion = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;

  /* ----------------------------------------------------------------------
     1. Register page: show only the fields that apply to the chosen role.
     ---------------------------------------------------------------------- */
  function syncRoleFields() {
    var chosen = document.querySelector('input[name="role"]:checked');
    if (!chosen) return;
    document.querySelectorAll(".role-field").forEach(function (field) {
      field.classList.toggle("hidden", field.getAttribute("data-for") !== chosen.value);
    });
  }
  document.querySelectorAll('input[name="role"]').forEach(function (radio) {
    radio.addEventListener("change", syncRoleFields);
  });
  syncRoleFields();

  /* ----------------------------------------------------------------------
     2. Resume upload: name the chosen file, catch obvious mistakes before the
        request, and show a spinner while the PDF is being parsed.
     ---------------------------------------------------------------------- */
  var fileInput = document.getElementById("resume");
  var fileHint = document.getElementById("file-hint");
  var MAX_BYTES = 5 * 1024 * 1024;

  function describeFile() {
    var file = fileInput.files && fileInput.files[0];
    if (!file) {
      fileHint.textContent = "PDF only, up to 5 MB.";
      fileHint.style.color = "";
      return true;
    }
    var sizeMB = (file.size / (1024 * 1024)).toFixed(2);
    if (!/\.pdf$/i.test(file.name)) {
      fileHint.textContent = "That is not a PDF. Please choose a .pdf file.";
      fileHint.style.color = "var(--bad)";
      return false;
    }
    if (file.size > MAX_BYTES) {
      fileHint.textContent = "That file is " + sizeMB + " MB — the limit is 5 MB.";
      fileHint.style.color = "var(--bad)";
      return false;
    }
    fileHint.textContent = "Ready: " + file.name + " (" + sizeMB + " MB)";
    fileHint.style.color = "var(--ok)";
    return true;
  }

  if (fileInput && fileHint) {
    fileInput.addEventListener("change", describeFile);

    var resumeForm = document.getElementById("resume-form");
    if (resumeForm) {
      resumeForm.addEventListener("submit", function (event) {
        if (!fileInput.files || !fileInput.files[0]) {
          event.preventDefault();
          fileHint.textContent = "Please choose a PDF file first.";
          fileHint.style.color = "var(--bad)";
          return;
        }
        if (!describeFile()) {
          event.preventDefault();
          return;
        }
        var button = resumeForm.querySelector('button[type="submit"]');
        if (button) {
          button.setAttribute("data-busy", "true");
          button.innerHTML = '<span class="spinner"></span> Reading your resume…';
        }
      });
    }
  }

  /* ----------------------------------------------------------------------
     3. Skill review: select all / clear all within one list.
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
     4. Show/hide toggle (the extracted resume text).
     ---------------------------------------------------------------------- */
  document.querySelectorAll("[data-toggle]").forEach(function (button) {
    button.addEventListener("click", function () {
      var target = document.querySelector(button.getAttribute("data-toggle"));
      if (!target) return;
      var nowHidden = target.classList.toggle("hidden");
      button.textContent = nowHidden ? "Show" : "Hide";
      button.setAttribute("aria-expanded", String(!nowHidden));
    });
  });

  /* ----------------------------------------------------------------------
     5. Candidates page: switch posting without a Go button.
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
     7. Tidy comma-separated skill inputs on blur.
     ---------------------------------------------------------------------- */
  ["required_skills", "preferred_skills", "extra_skills"].forEach(function (id) {
    var input = document.getElementById(id);
    if (!input) return;
    input.addEventListener("blur", function () {
      input.value = input.value
        .split(",")
        .map(function (part) { return part.trim(); })
        .filter(function (part) { return part.length > 0; })
        .join(", ");
    });
  });

  /* ----------------------------------------------------------------------
     8. Dismiss success/info flashes after a few seconds. Errors and warnings
        stay until the user navigates - those are worth reading.
     ---------------------------------------------------------------------- */
  var transient = document.querySelectorAll(".flash-success, .flash-info");
  if (transient.length) {
    window.setTimeout(function () {
      transient.forEach(function (flash) {
        if (reduceMotion) { flash.remove(); return; }
        flash.setAttribute("data-leaving", "true");   // CSS handles the fade
        window.setTimeout(function () { flash.remove(); }, 220);
      });
    }, 6000);
  }

  /* The scrollable-table edge shadow needs no JS: .scroll-x layers two
     surface-coloured gradients (background-attachment: local) over two shadow
     gradients (attachment: scroll), so the shadow is masked at whichever edge
     has nothing left to scroll to. See section 7 of style.css. */
})();
