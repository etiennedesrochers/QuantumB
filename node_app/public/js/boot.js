/** Mounts the page module named by the bootstrap script's data-page attribute. */

import { el } from "./dom.js";
import { toast } from "./components/toast.js";

const PAGES = {
  generator: () => import("./pages/generator.js"),
  projects: () => import("./pages/projects.js"),
  compressors: () => import("./pages/compressors.js"),
  libraries: () => import("./pages/libraries.js"),
};

function initTheme() {
  const button = document.getElementById("themeToggle");
  const apply = (dark) => {
    document.documentElement.classList.toggle("dark", dark);
    button.innerHTML = dark ? "&#9790;" : "&#9788;";
  };

  apply(localStorage.getItem("theme") === "dark");
  button.addEventListener("click", () => {
    const dark = !document.documentElement.classList.contains("dark");
    localStorage.setItem("theme", dark ? "dark" : "light");
    apply(dark);
  });
}

async function mountPage() {
  const name = document.querySelector("script[data-page]")?.dataset.page;
  const load = PAGES[name];
  const view = document.getElementById("view");
  if (!load) return;

  try {
    const page = await load();
    await page.mount(view);
  } catch (error) {
    view.replaceChildren(el("p", { class: "error-text", text: `Failed to load page: ${error.message}` }));
    toast.error(error.message);
  }
}

initTheme();
mountPage();
