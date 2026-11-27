const form = document.querySelector("#trip-form");

if (form) {
  const estimates = JSON.parse(document.querySelector("#estimates").textContent);
  const woman = document.querySelector("#woman");
  const womenOnly = document.querySelector("#women-only");
  const confirm = document.querySelector("#confirm");
  const note = document.querySelector("#demo-note");
  const jod = (fils) => `JOD ${(fils / 1000).toFixed(2)}`;
  // Other Jeeny services are shown for comparison only, priced from the solo fare to this drop-off.
  const factors = { economy: 1, taxi: 1, comfort: 1.1, box: 0.88 };

  function selected() {
    return form.querySelector('input[name="ride"]:checked');
  }

  function update() {
    const estimate = estimates[form.elements.stop.value];
    document.querySelector("#shared").textContent = jod(estimate.shared);
    for (const el of form.querySelectorAll("[data-price]")) {
      el.textContent = jod(Math.round((estimate.solo * factors[el.dataset.price]) / 10) * 10);
    }
    womenOnly.disabled = !woman.checked;
    if (!woman.checked) womenOnly.checked = false;
    const ride = selected();
    confirm.textContent = `Confirm ${ride.closest(".ride").querySelector(".ride-name").firstChild.textContent.trim()}`;
    note.textContent = "";
  }

  form.addEventListener("input", update);
  form.addEventListener("submit", (event) => {
    if (selected().value !== "campus") {
      event.preventDefault();
      note.textContent = "This demo books Campus Connect only. Pick it above to continue.";
    }
  });
  update();
}
