/** Hash router + theme toggle. */

import { el } from "./dom.js";
import { toast } from "./components/toast.js";

const ROUTES = {
  generator: () => import("./pages/generator.js"),
  projects: () => import("./pages/projects.js"),
  compressors: () => import("./pages/compressors.js"),
  libraries: () => import("./pages/libraries.js"),
};

const DEFAULT_ROUTE = "generator";

async function renderRoute() {
  const name = (window.location.hash.replace(/^#\/?/, "") || DEFAULT_ROUTE).split("/")[0];
  const load = ROUTES[name] || ROUTES[DEFAULT_ROUTE];
  const view = document.getElementById("view");

  for (const link of document.querySelectorAll("#nav a")) {
    link.classList.toggle("is-active", link.dataset.route === name);
  }

  view.replaceChildren(el("p", { class: "muted", text: "Loading\u2026" }));
  try {
    const page = await load();
    await page.mount(view);
  } catch (error) {
    view.replaceChildren(el("p", { class: "error-text", text: `Failed to load page: ${error.message}` }));
    toast.error(error.message);
  }
}

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

window.addEventListener("hashchange", renderRoute);
initTheme();
renderRoute();
