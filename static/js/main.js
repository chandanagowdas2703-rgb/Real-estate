// Small bits of JavaScript for HomeFinder.

// 1) Ask for confirmation before submitting any form that has data-confirm="..."
document.querySelectorAll("form[data-confirm]").forEach(function (form) {
  form.addEventListener("submit", function (e) {
    if (!confirm(form.dataset.confirm)) e.preventDefault();
  });
});

// 2) Show thumbnails of the images chosen in the add/edit listing form.
var input = document.getElementById("imageInput");
var preview = document.getElementById("preview");
if (input && preview) {
  input.addEventListener("change", function () {
    preview.innerHTML = "";
    Array.from(input.files).forEach(function (file) {
      if (!file.type.startsWith("image/")) return;
      var img = document.createElement("img");
      img.className = "preview-img";
      img.src = URL.createObjectURL(file);
      preview.appendChild(img);
    });
  });
}
