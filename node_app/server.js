/**
 * QuantumB web front end: Express + EJS.
 *
 * Renders the page shells; all data comes from the FastAPI backend, which the
 * browser calls directly at API_BASE (so that origin must allow CORS).
 */

import path from "node:path";
import { fileURLToPath } from "node:url";

import express from "express";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.PORT || 3000);
const API_BASE = process.env.API_BASE || "http://127.0.0.1:8000";

const PAGES = [
  { route: "generator", title: "Generator", nav: "Generator" },
  { route: "projects", title: "Projects", nav: "Projects" },
  { route: "compressors", title: "Compressors", nav: "Compressors" },
  { route: "libraries", title: "Libraries", nav: "Libraries" },
];

const app = express();

app.set("view engine", "ejs");
app.set("views", path.join(__dirname, "views"));
app.use(express.static(path.join(__dirname, "public")));

app.locals.apiBase = API_BASE;
app.locals.pages = PAGES;

app.get("/", (_req, res) => res.redirect("/generator"));

for (const page of PAGES) {
  app.get(`/${page.route}`, (_req, res) => {
    res.render(`pages/${page.route}`, { active: page.route, title: page.title });
  });
}

app.use((_req, res) => {
  res.status(404).render("pages/not-found", { active: "", title: "Not found" });
});

app.listen(PORT, () => {
  console.log(`QuantumB web UI  http://127.0.0.1:${PORT}`);
  console.log(`Backend API      ${API_BASE}`);
});
