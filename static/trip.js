const form = document.querySelector("#trip-form");

if (form) {
  const estimates = JSON.parse(document.querySelector("#estimates").textContent);
  const prefWomen = document.querySelector("#pref-women");
  const prefMen = document.querySelector("#pref-men");
  const slowNote = document.querySelector("#slow-note");
  const friendsStart = document.querySelector("#friends-start");
  const friendsJoin = document.querySelector("#friends-join");
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
    // Women-only is for women students, men-only for men students
    const gender = form.elements.gender.value;
    prefWomen.disabled = gender !== "woman";
    prefMen.disabled = gender !== "man";
    if (form.elements.preference.value === "women" && gender !== "woman") form.elements.preference.value = "mixed";
    if (form.elements.preference.value === "men" && gender !== "man") form.elements.preference.value = "mixed";
    slowNote.hidden = form.elements.preference.value === "mixed";
    if (friendsStart) {
      friendsStart.hidden = form.elements.friends.value !== "start";
      friendsJoin.hidden = form.elements.friends.value !== "join";
      form.elements.group_code.required = form.elements.friends.value === "join";
    }
    const ride = selected();
    confirm.textContent = `Confirm ${ride.closest(".ride").querySelector(".ride-name").firstChild.textContent.trim()}`;
    note.textContent = "";
  }

  form.addEventListener("input", update);
  // Click runs before the browser's required-field check, which would block on the hidden Campus fields.
  confirm.addEventListener("click", (event) => {
    if (selected().value !== "campus") {
      event.preventDefault();
      note.textContent = "This demo books Campus Connect only. Pick it above to continue.";
    }
  });
  update();
}
