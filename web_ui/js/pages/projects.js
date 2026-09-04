/** Projects Page: Manage saved project files (.aepj). */

import { api } from "../api.js";
import { downloadBlob, el, withBusy } from "../dom.js";
import { dataTable } from "../components/table.js";
import { toast } from "../components/toast.js";

export async function mount(root) {
  root.replaceChildren(
    el("section", { class: "card stack" }, [
      el("div", { class: "row-between wrap" }, [
        el("div", {}, [
          el("h2", { text: "Saved Projects" }),
          el("p", { class: "muted", text: "Manage and open saved AutoCAD Electrical Project files (.aepj)." }),
        ]),
        el("div", { class: "toolbar" }, [
          el("button", {
            type: "button",
            class: "btn btn-secondary",
            onClick: () => triggerImport(root),
          }, ["📤 Import .aepj Project"]),
          el("a", {
            href: "#/generator",
            class: "btn btn-primary",
          }, ["➕ Create New Project"]),
        ]),
      ]),
      el("div", { id: "projectsBody" }),
    ])
  );

  await loadProjects(root);
}

async function loadProjects(root) {
  const body = root.querySelector("#projectsBody");
  if (!body) return;

  body.replaceChildren(el("p", { class: "muted", text: "Loading projects\u2026" }));

  try {
    const projects = await api.projects.list();
    renderProjectsTable(root, projects);
  } catch (err) {
    body.replaceChildren(el("p", { class: "error-text", text: `Could not load projects: ${err.message}` }));
    toast.error(`Error loading projects: ${err.message}`);
  }
}

function renderProjectsTable(root, projects) {
  const body = root.querySelector("#projectsBody");
  if (!body) return;

  if (projects.length === 0) {
    body.replaceChildren(
      el("div", { class: "card stack", style: "text-align: center; padding: 40px;" }, [
        el("p", { class: "muted", text: "No saved projects found in the application library." }),
        el("div", { class: "toolbar", style: "justify-content: center;" }, [
          el("a", { href: "#/generator", class: "btn btn-primary" }, ["Start Generator"]),
        ]),
      ])
    );
    return;
  }

  const columns = [
    {
      label: "Project Name",
      key: "name",
      render: (r) => el("span", { style: "font-weight: 600;", text: r.name || r.id }),
    },
    { label: "Project #", key: "project_number", render: (r) => r.project_number || "-" },
    { label: "Revision", key: "revision", render: (r) => r.revision || "A" },
    { label: "Drawn By", key: "drawn_by", render: (r) => r.drawn_by || "-" },
    {
      label: "Workbook Selection",
      render: (r) => {
        const parts = [r.manufacturer, r.capacity ? `${r.capacity}T` : null, r.tension ? `${r.tension}V` : null].filter(Boolean);
        return parts.length ? parts.join(" · ") : "-";
      },
    },
    { label: "Circuits", render: (r) => el("span", { class: "chip", text: `${r.circuits_count || 0} circuit(s)` }) },
    {
      label: "Last Modified",
      render: (r) => (r.updated_at ? new Date(r.updated_at).toLocaleString() : "-"),
    },
    {
      label: "Actions",
      render: (r) =>
        el("div", { class: "toolbar" }, [
          el("button", {
            type: "button",
            class: "btn btn-primary btn-sm",
            onClick: () => openProjectInGenerator(r.id),
          }, ["📂 Open"]),
          el("a", {
            href: api.projects.exportUrl(r.id),
            download: `${r.filename || r.id + ".aepj"}`,
            class: "btn btn-secondary btn-sm",
          }, ["📥 Download"]),
          el("button", {
            type: "button",
            class: "btn btn-danger btn-sm",
            onClick: () => handleDeleteProject(root, r.id, r.name),
          }, ["🗑️"]),
        ]),
    },
  ];

  body.replaceChildren(dataTable({ columns, rows: projects }));
}

function openProjectInGenerator(projectId) {
  sessionStorage.setItem("load_project_id", projectId);
  window.location.hash = "#/generator";
}

async function handleDeleteProject(root, id, name) {
  if (!confirm(`Delete project '${name || id}'?`)) return;
  try {
    await api.projects.remove(id);
    toast.success(`Project '${name || id}' deleted.`);
    await loadProjects(root);
  } catch (err) {
    toast.error(`Delete failed: ${err.message}`);
  }
}

function triggerImport(root) {
  const fileInput = el("input", {
    type: "file",
    accept: ".aepj,.json",
    style: "display: none;",
    onChange: async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const formData = new FormData();
      formData.append("file", file);
      try {
        const res = await api.projects.import(formData);
        toast.success(`Imported project '${res.name || res.id}'.`);
        openProjectInGenerator(res.id);
      } catch (err) {
        toast.error(`Import failed: ${err.message}`);
      }
    },
  });

  document.body.append(fileInput);
  fileInput.click();
  fileInput.remove();
}
