(() => {
  // 03: six code boxes behave like one field (typing moves on, backspace moves back, paste fills all).
  const otp = document.querySelector("[data-otp]");
  if (otp) {
    const boxes = [...otp.querySelectorAll('input[name="digit"]')];
    boxes[0].focus();
    boxes.forEach((box, i) => {
      box.addEventListener("input", () => {
        box.value = box.value.replace(/\D/g, "").slice(-1);
        if (box.value && boxes[i + 1]) boxes[i + 1].focus();
      });
      box.addEventListener("keydown", (event) => {
        if (event.key === "Backspace" && !box.value && boxes[i - 1]) boxes[i - 1].focus();
      });
      box.addEventListener("paste", (event) => {
        const digits = (event.clipboardData.getData("text") || "").replace(/\D/g, "").slice(0, 6);
        if (!digits) return;
        event.preventDefault();
        digits.split("").forEach((d, j) => { if (boxes[j]) boxes[j].value = d; });
        boxes[Math.min(digits.length, 5)].focus();
      });
    });
  }

  // 04: filter universities by name or city.
  document.querySelectorAll("[data-filter]").forEach((input) => {
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      document.querySelectorAll(input.dataset.filter).forEach((el) => { el.hidden = q && !el.textContent.toLowerCase().includes(q); });
    });
  });

  // 05: switching direction redraws the screen with the matching rows.
  document.querySelectorAll("[data-autosubmit]").forEach((input) => {
    input.addEventListener("change", () => {
      const form = input.form;
      form.querySelector('input[name="go"]').value = "";
      form.submit();
    });
  });

  // 06: "I can reach the street by" follows the class end time.
  const end = document.querySelector("[data-ready]");
  const out = document.querySelector("[data-ready-out]");
  if (end && out) end.addEventListener("input", () => {
    const [h, m] = end.value.split(":").map(Number);
    if (Number.isNaN(h)) return;
    const total = h * 60 + m + Number(end.dataset.ready);
    const hh = Math.floor(total / 60) % 24, mm = total % 60;
    out.textContent = `${(hh + 11) % 12 + 1}:${String(mm).padStart(2, "0")} ${hh < 12 ? "AM" : "PM"}`;
  });

  // 07: women only / men only follow "I am"; friends options show their field.
  const prefs = document.querySelector("[data-prefs]");
  if (prefs) {
    const sync = () => {
      const gender = prefs.elements.gender.value;
      prefs.querySelectorAll("[data-gender]").forEach((radio) => {
        radio.disabled = radio.dataset.gender !== gender;
        if (radio.disabled && radio.checked) prefs.querySelector('input[name="preference"][value="mixed"]').checked = true;
      });
      prefs.querySelector("[data-slow]").hidden = prefs.elements.preference.value === "mixed";
      const friends = prefs.elements.friends ? prefs.elements.friends.value : "";
      prefs.querySelectorAll("[data-friends]").forEach((el) => { el.hidden = el.dataset.friends !== friends; });
      if (prefs.elements.group_code) prefs.elements.group_code.required = friends === "join";
    };
    prefs.addEventListener("change", sync);
    sync();
  }
})();

// 15: "Share trip" copies the trip link (no message is sent from the demo).
document.querySelectorAll("[data-share]").forEach((button) => {
  button.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(button.dataset.share); } catch (error) { /* clipboard blocked: still show the link */ }
    const toast = document.createElement("p");
    toast.className = "yr-toast"; toast.setAttribute("role", "status");
    toast.textContent = "Trip link copied";
    document.querySelector(".screen.yr").appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
  });
});

// 35: when the phone loses its connection, cover the screen with "Your request is safe" until it is back.
(() => {
  const panel = document.querySelector("[data-offline]");
  const head = document.querySelector(".yr-head");
  if (!panel) return;
  if (head) panel.style.top = `${head.offsetTop + head.offsetHeight}px`;
  const show = () => { panel.hidden = navigator.onLine; };
  window.addEventListener("offline", show);
  window.addEventListener("online", show);
  panel.querySelector("[data-retry]").addEventListener("click", (event) => {
    if (!navigator.onLine) event.preventDefault();  // Still offline: stay here instead of showing a browser error
  });
  document.addEventListener("submit", (event) => {
    if (!navigator.onLine) { event.preventDefault(); panel.hidden = false; }  // No duplicate submits while offline
  });
})();

// Brief 05 lobby: "Copy code" copies the friends group code.
document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(button.dataset.copy); } catch (error) { /* clipboard blocked */ }
    const toast = document.createElement("p");
    toast.className = "yr-toast"; toast.setAttribute("role", "status");
    toast.textContent = "Group code copied";
    document.querySelector(".screen.yr").appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  });
});
