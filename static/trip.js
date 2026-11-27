const form = document.querySelector("#trip-form");

if (form) {
  const minutes = JSON.parse(form.dataset.minutes);
  const fares = JSON.parse(document.querySelector("#fares").textContent);
  const area = form.elements.area;
  const arrival = form.elements.arrival;
  const leaveBy = document.querySelector("#leave-by");
  const fare = document.querySelector("#fare");

  function updateEstimate() {
    const [hour, minute] = arrival.value.split(":").map(Number);
    const departure = hour * 60 + minute - minutes[area.value] - Number(form.dataset.buffer);
    const timePart = (value) => String(value).padStart(2, "0");
    leaveBy.textContent = arrival.validity.valid && arrival.value
      ? `${timePart(Math.floor(departure / 60))}:${timePart(departure % 60)}`
      : "—";
    fare.textContent = `JOD ${(fares[area.value] / 1000).toFixed(2)}`;
  }

  form.addEventListener("input", updateEstimate);
  updateEstimate();
}

const menu = document.querySelector("#menu-btn");
if (menu) {
  const setOpen = (open) => {
    document.body.classList.toggle("drawer-open", open);
    menu.setAttribute("aria-expanded", String(open));
  };
  menu.addEventListener("click", () => setOpen(!document.body.classList.contains("drawer-open")));
  document.querySelector("[data-close-drawer]").addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setOpen(false); });
}
