const form = document.querySelector("#trip-form");

if (form) {
  const estimates = JSON.parse(document.querySelector("#estimates").textContent);
  const woman = document.querySelector("#woman");
  const womenOnly = document.querySelector("#women-only");
  const jod = (fils) => `JOD ${(fils / 1000).toFixed(2)}`;

  function update() {
    const estimate = estimates[form.elements.stop.value];
    document.querySelector("#solo").textContent = jod(estimate.solo);
    document.querySelector("#shared").textContent = jod(estimate.shared);
    womenOnly.disabled = !woman.checked;
    if (!woman.checked) womenOnly.checked = false;
  }

  form.addEventListener("input", update);
  update();
}
