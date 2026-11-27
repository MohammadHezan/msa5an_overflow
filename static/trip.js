(() => {
  const form = document.getElementById("trip-form");
  if (!form) return;

  const estimatesNode = document.getElementById("estimates");
  const estimates = estimatesNode ? JSON.parse(estimatesNode.textContent) : {};
  const stopSelect = document.getElementById("trip-stop");
  const campusRadio = document.getElementById("ride-campus");
  const details = document.getElementById("campus-details");
  const note = document.getElementById("demo-note");
  const confirm = document.getElementById("confirm");
  const detailSubmit = document.getElementById("find-shared");
  const startWrap = document.getElementById("class-start-wrap");
  const endWrap = document.getElementById("class-end-wrap");
  const prefWomen = document.getElementById("pref-women");
  const prefMen = document.getElementById("pref-men");
  const slowNote = document.getElementById("slow-note");
  const friendsStart = document.getElementById("friends-start");
  const friendsJoin = document.getElementById("friends-join");
  const jod = (fils) => `JOD ${(Number(fils || 0) / 1000).toFixed(2)}`;
  const currentEstimate = () => estimates[stopSelect.value] || {};
  const chosen = () => form.querySelector('input[name="ride"]:checked');
  const updateNames = () => {
    const selected = chosen();
    if (!selected) return;
    const label = selected.closest(".ride").querySelector(".ride-name").childNodes[0].textContent.trim();
    confirm.textContent = selected.value === "campus" ? "Choose Yalla Ride" :
      selected.value === "comfort" ? "Confirm Comfort" : `Confirm ${label}`;
  };
  const previewFor = (estimate, direction) => {
    const previews = estimate.pickups || estimate.pickup_previews || estimate.pickup_preview || {};
    const preview = previews[direction] || (estimates.pickup_previews && estimates.pickup_previews[stopSelect.value] && estimates.pickup_previews[stopSelect.value][direction]) || {};
    if (typeof preview === "string") return preview;
    if (preview.street) {
      const walk = preview.walk_minutes ?? 1;
      return `Walk ${walk} min${preview.walk_meters ? ` · ${preview.walk_meters} m` : ""} to ${preview.street}`;
    }
    return direction === "to_campus" ? `Walk 1 min to ${stopSelect.value} street` : "Walk 1 min to Cedar Campus Gate street";
  };
  const enableDetails = (enabled) => {
    details.querySelectorAll("input, select").forEach((el) => { el.disabled = !enabled; });
    detailSubmit.disabled = !enabled;
  };
  const updateDetails = () => {
    const estimate = currentEstimate();
    const direction = form.elements.direction.value;
    const gender = form.elements.gender.value;
    const shared = estimate.shared ?? 0;
    const solo = estimate.solo ?? 0;
    const shareNode = document.getElementById("shared");
    const campusSolo = document.getElementById("campus-solo");
    shareNode.textContent = jod(shared);
    campusSolo.textContent = jod(solo);
    document.getElementById("detail-shared").textContent = jod(shared);
    document.getElementById("detail-solo").textContent = jod(solo);
    document.getElementById("campus-saving").textContent = `save ~${estimate.save_percent ?? (solo ? Math.round((solo - shared) / solo * 100) : 0)}%`;
    const starts = direction === "to_campus";
    startWrap.hidden = !starts;
    endWrap.hidden = starts;
    form.elements.class_end.disabled = !details.classList.contains("is-open") || starts;
    form.elements.class_start.disabled = !details.classList.contains("is-open") || !starts;
    form.elements.class_end.required = !starts;
    form.elements.class_start.required = starts;
    document.getElementById("pickup-preview").textContent = previewFor(estimate, direction);
    document.querySelector(".destination-box small").textContent = direction === "to_campus" ? "Starting neighborhood" : "Drop-off";
    const priceFields = {
      economy: estimate.solo,
      taxi: estimate.taxi ?? estimate.solo,
      comfort: estimate.comfort ?? (estimate.solo ? Math.round(estimate.solo * 1.3) : 0),
      box: estimate.box ?? estimate.solo,
    };
    Object.entries(priceFields).forEach(([key, price]) => {
      const node = form.querySelector(`[data-price="${key}"]`);
      if (node) node.textContent = jod(price);
    });
    prefWomen.disabled = gender !== "woman";
    prefMen.disabled = gender !== "man";
    if (form.elements.preference.value === "women" && gender !== "woman") form.elements.preference.value = "mixed";
    if (form.elements.preference.value === "men" && gender !== "man") form.elements.preference.value = "mixed";
    slowNote.hidden = form.elements.preference.value === "mixed";
    if (friendsStart) {
      const mode = form.elements.friends.value;
      friendsStart.hidden = mode !== "start";
      friendsJoin.hidden = mode !== "join";
      const code = form.elements.group_code;
      if (code) code.required = mode === "join" && !friendsJoin.hidden;
    }
  };
  const openDetails = () => {
    if (!campusRadio) return;
    campusRadio.checked = true;
    details.hidden = false;
    details.classList.add("is-open");
    document.querySelector(".ride-list").hidden = true;
    document.querySelector(".rides-note").hidden = true;
    document.querySelector(".destination-box").hidden = true;
    document.querySelector(".ride-sheet-head").hidden = true;
    document.querySelector(".rides-foot").hidden = true;
    enableDetails(true);
    updateDetails();
    document.getElementById("details-title").focus?.();
    document.getElementById("details-back").focus();
  };
  const closeDetails = () => {
    details.hidden = true;
    details.classList.remove("is-open");
    document.querySelector(".ride-list").hidden = false;
    document.querySelector(".rides-note").hidden = false;
    document.querySelector(".destination-box").hidden = false;
    document.querySelector(".ride-sheet-head").hidden = false;
    document.querySelector(".rides-foot").hidden = false;
    enableDetails(false);
    updateNames();
    confirm.focus();
  };

  // Keep all fields in the separate details sheet disabled until it is opened;
  // native required validation can therefore never intercept demo-only rows.
  enableDetails(false);
  updateNames();
  updateDetails();
  form.addEventListener("change", (event) => {
    if (event.target === stopSelect) updateDetails();
    if (event.target.name === "ride") updateNames();
    if (event.target.name === "direction" || event.target.name === "gender" || event.target.name === "preference" || event.target.name === "friends") updateDetails();
  });
  confirm.addEventListener("click", () => {
    note.textContent = "";
    const selection = chosen();
    if (!selection) return;
    if (selection.value === "campus") {
      openDetails();
      return;
    }
    note.textContent = `${selection.closest(".ride").querySelector(".ride-name").childNodes[0].textContent.trim()} is demo only. No ride was booked.`;
  });
  document.getElementById("details-back").addEventListener("click", closeDetails);

  const verificationPanel = document.getElementById("verification-form");
  const openVerification = document.getElementById("open-verification");
  if (openVerification && verificationPanel) {
    const showVerification = () => { verificationPanel.hidden = false; document.getElementById("verification-email").focus(); };
    openVerification.addEventListener("click", (event) => { event.stopPropagation(); showVerification(); });
    const campusRow = document.getElementById("campus-row");
    campusRow.addEventListener("click", (event) => {
      if (event.target.closest("button")) return;
      showVerification();
    });
    campusRow.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        showVerification();
      }
    });
    document.getElementById("verification-back").addEventListener("click", () => { verificationPanel.hidden = true; openVerification.focus(); });
    document.getElementById("verify-submit").addEventListener("click", async () => {
      const email = document.getElementById("verification-email");
      const message = document.getElementById("verification-message");
      if (!email.reportValidity()) return;
      const body = new FormData(verificationPanel);
      body.append("email", email.value);
      message.textContent = "";
      try {
        const response = await fetch("/demo/student-verification", { method: "POST", body, credentials: "include" });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "We couldn't verify that email.");
        window.location.assign("/?screen=book&ride=campus");
      } catch (error) {
        message.textContent = error.message || "Verification failed. Please try again.";
      }
    });
  }
  const profileControl = document.getElementById("profile-control");
  if (profileControl) profileControl.addEventListener("click", async (event) => {
    event.preventDefault();
    const body = new FormData();
    body.append("csrf", form.elements.csrf.value);
    body.append("email", "");
    body.append("action", "reset");
    try {
      await fetch("/demo/student-verification", { method: "POST", body, credentials: "include" });
    } finally {
      window.location.assign("/?screen=book");
    }
  });
  if (campusRadio && campusRadio.checked) updateNames();
})();
