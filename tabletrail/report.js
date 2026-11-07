"use strict";
document.querySelectorAll("[data-filter]").forEach(input => {
  input.addEventListener("input", () => {
    const query = input.value.toLocaleLowerCase().trim();
    const table = document.querySelector(`[data-searchable="${input.dataset.filter}"]`);
    if (!table) return;
    table.querySelectorAll("tbody tr").forEach(row => {
      row.hidden = !row.textContent.toLocaleLowerCase().includes(query);
    });
  });
});
document.querySelectorAll("nav a").forEach(link => {
  link.addEventListener("click", () => {
    document.querySelectorAll("nav a").forEach(a => a.classList.remove("active"));
    link.classList.add("active");
  });
});
