/** Compressor library: CRUD, template assignment, workbook sync, import/export. */

import { api } from "../api.js";
import { el, fillSelect, num, withBusy } from "../dom.js";
import { dataTable } from "../components/table.js";
import { confirmAction, confirmDialog, toast } from "../components/toast.js";
import { cached, invalidate, set } from "../state.js";

let compressors = [];
let templatesByCategory = {};
let selectedId = null;
let rootEl = null;

export async function mount(root) {
  selectedId = null;
  rootEl = root;
  root.replaceChildren(render());
  bindToolbar(root);

  try {
    [compressors, templatesByCategory] = await Promise.all([
      api.compressors.list(),
      cached("templates", api.templates),
    ]);
    set("compressors", compressors);
    renderList(root);
    renderDetail(root);
  } catch (error) {
    toast.error(`Could not load compressors: ${error.message}`);
  }
}

function render() {
  return el("div", { class: "stack" }, [
    el("section", { class: "card row-between wrap" }, [
      el("h2", { text: "Compressor library" }),
      el("div", { class: "toolbar" }, [
        el("button", { id: "newBtn", type: "button", class: "btn btn-primary" }, ["New compressor"]),
        el("button", { id: "syncBtn", type: "button", class: "btn btn-secondary" }, ["Sync from workbook"]),
        el("a", { id: "exportBtn", class: "btn btn-secondary", href: api.compressors.exportUrl() }, ["Export"]),
        el("label", { class: "btn btn-secondary" }, [
          "Import",
          el("input", { id: "importInput", type: "file", accept: "application/json", hidden: true }),
        ]),
      ]),
    ]),
    el("div", { class: "split" }, [
      el("section", { class: "card", id: "listCard" }),
      el("section", { class: "card", id: "detailCard" }),
    ]),
  ]);
}

function bindToolbar(root) {
  root.querySelector("#newBtn").addEventListener("click", () => createCompressor(root));
  root.querySelector("#syncBtn").addEventListener("click", (e) => syncWorkbook(root, e.target));
  root.querySelector("#importInput").addEventListener("change", (e) => importFile(root, e.target));
}

function renderList(root) {
  const sorted = [...compressors].sort(
    (a, b) =>
      String(a.manufacturer || "").localeCompare(String(b.manufacturer || "")) ||
      num(a.capacity) - num(b.capacity) ||
      String(a.name || "").localeCompare(String(b.name || ""))
  );

  root.querySelector("#listCard").replaceChildren(
    el("h3", { text: `Compressors (${compressors.length})` }),
    dataTable({
      columns: [
        { label: "Name", key: "name" },
        { label: "Model", key: "model" },
        { label: "Manufacturer", key: "manufacturer" },
        { label: "Tons", render: (row) => String(row.capacity ?? "") },
        { label: "Templates", render: (row) => String((row.templates || []).length) },
      ],
      rows: sorted,
      onRowClick: (row) => {
        selectedId = row.id;
        renderList(root);
        renderDetail(root);
      },
      isActive: (row) => row.id === selectedId,
      empty: "No compressors yet \u2014 create one or sync from the workbook.",
    })
  );
}

function selected() {
  return compressors.find((c) => c.id === selectedId) || null;
}

function renderDetail(root) {
  const card = root.querySelector("#detailCard");
  const compressor = selected();

  if (!compressor) {
    card.replaceChildren(el("p", { class: "muted", text: "Select a compressor to edit it." }));
    return;
  }

  card.replaceChildren(
    el("div", { class: "row-between" }, [
      el("h3", { text: compressor.name || "(unnamed)" }),
      el("button", { id: "deleteBtn", type: "button", class: "btn btn-danger" }, ["Delete"]),
    ]),
    el("div", { class: "grid grid-2" }, [
      textField("Name", "fName", compressor.name),
      textField("Model", "fModel", compressor.model),
      textField("Manufacturer", "fManufacturer", compressor.manufacturer),
      textField("Capacity (tons)", "fCapacity", compressor.capacity, "number"),
    ]),
    el("div", { class: "row-end" }, [
      el("button", { id: "saveBtn", type: "button", class: "btn btn-primary" }, ["Save details"]),
    ]),
    el("hr"),
    el("h3", { text: "Templates" }),
    templatePicker(),
    templateList(compressor),
  );

  card.querySelector("#saveBtn").addEventListener("click", (e) => saveDetails(root, e.target));
  card.querySelector("#deleteBtn").addEventListener("click", () => removeCompressor(root));
  card.querySelector("#addTemplateBtn").addEventListener("click", () => addTemplate(root));

  const category = card.querySelector("#templateCategory");
  category.addEventListener("change", () => fillTemplateNames(card));
  fillSelect(category, Object.keys(templatesByCategory));
  fillTemplateNames(card);
}

function textField(label, id, value, type = "text") {
  return el("label", { class: "field" }, [
    el("span", { class: "field-label", text: label }),
    el("input", { id, type, value: value ?? "" }),
  ]);
}

function templatePicker() {
  return el("div", { class: "grid grid-4 align-end" }, [
    el("label", { class: "field" }, [
      el("span", { class: "field-label", text: "Category" }),
      el("select", { id: "templateCategory" }),
    ]),
    el("label", { class: "field" }, [
      el("span", { class: "field-label", text: "Template" }),
      el("select", { id: "templateName" }),
    ]),
    el("label", { class: "field" }, [
      el("span", { class: "field-label", text: "Scope" }),
      el("select", { id: "templateScope" }, [
        el("option", { value: "per_unit", selected: true }, ["Per unit"]),
        el("option", { value: "shared" }, ["Shared"]),
      ]),
    ]),
    el("button", { id: "addTemplateBtn", type: "button", class: "btn btn-secondary" }, ["Add template"]),
  ]);
}

function fillTemplateNames(card) {
  const category = card.querySelector("#templateCategory").value;
  const names = templatesByCategory[category] || [];
  fillSelect(card.querySelector("#templateName"), names, {
    placeholder: names.length ? undefined : "No templates in this category",
  });
}

function templateList(compressor) {
  const templates = compressor.templates || [];
  if (templates.length === 0) return el("p", { class: "muted", text: "No templates assigned." });

  return el("ul", { class: "template-list" }, templates.map((template, index) =>
    el("li", { class: "template-item" }, [
      el("span", { class: "strong", text: template.name }),
      el("span", { class: "chip", text: template.type || "regular" }),
      el("select", {
        class: "scope-select",
        dataset: { index: String(index) },
        onChange: (event) => changeScope(index, event.target.value),
      }, [
        el("option", { value: "per_unit", selected: template.scope !== "shared" }, ["Per unit"]),
        el("option", { value: "shared", selected: template.scope === "shared" }, ["Shared"]),
      ]),
      el("button", {
        type: "button",
        class: "btn btn-ghost btn-sm",
        onClick: () => removeTemplate(index),
      }, ["Remove"]),
    ])
  ));
}

async function persistTemplates(templates) {
  const compressor = selected();
  try {
    const updated = await api.compressors.update(compressor.id, { templates });
    Object.assign(compressor, updated);
    invalidate("compressors");
    renderList(rootEl);
    renderDetail(rootEl);
  } catch (error) {
    toast.error(`Could not save templates: ${error.message}`);
  }
}

function changeScope(index, scope) {
  const templates = [...(selected().templates || [])];
  templates[index] = { ...templates[index], scope };
  persistTemplates(templates);
}

function removeTemplate(index) {
  persistTemplates((selected().templates || []).filter((_, i) => i !== index));
}

function addTemplate(root) {
  const card = root.querySelector("#detailCard");
  const name = card.querySelector("#templateName").value;
  if (!name) {
    toast.error("Pick a template first.");
    return;
  }
  persistTemplates([...(selected().templates || []), {
    name,
    type: card.querySelector("#templateCategory").value,
    scope: card.querySelector("#templateScope").value,
  }]);
}

async function saveDetails(root, button) {
  const card = root.querySelector("#detailCard");
  const compressor = selected();
  const payload = {
    name: card.querySelector("#fName").value.trim(),
    model: card.querySelector("#fModel").value.trim(),
    manufacturer: card.querySelector("#fManufacturer").value.trim(),
    capacity: num(card.querySelector("#fCapacity").value),
  };
  if (!payload.name) {
    toast.error("Name is required.");
    return;
  }

  await withBusy(button, "Saving\u2026", async () => {
    try {
      const updated = await api.compressors.update(compressor.id, payload);
      Object.assign(compressor, updated);
      invalidate("compressors");
      renderList(root);
      renderDetail(root);
      toast.success("Compressor saved.");
    } catch (error) {
      toast.error(`Could not save: ${error.message}`);
    }
  });
}

async function createCompressor(root) {
  try {
    const created = await api.compressors.create({ name: "New compressor" });
    compressors.push(created);
    selectedId = created.id;
    invalidate("compressors");
    renderList(root);
    renderDetail(root);
    toast.success("Compressor created \u2014 edit its details below.");
  } catch (error) {
    toast.error(`Could not create compressor: ${error.message}`);
  }
}

async function removeCompressor(root) {
  const compressor = selected();
  const ok = await confirmAction(`Delete "${compressor.name}"? This cannot be undone.`, {
    confirmLabel: "Delete",
  });
  if (!ok) return;

  try {
    await api.compressors.remove(compressor.id);
    compressors = compressors.filter((c) => c.id !== compressor.id);
    selectedId = null;
    invalidate("compressors");
    renderList(root);
    renderDetail(root);
    toast.success("Compressor deleted.");
  } catch (error) {
    toast.error(`Could not delete: ${error.message}`);
  }
}

async function syncWorkbook(root, button) {
  await withBusy(button, "Syncing\u2026", async () => {
    try {
      const result = await api.compressors.syncWorkbook();
      compressors = result.compressors;
      invalidate("compressors");
      renderList(root);
      renderDetail(root);
      toast.success(`Imported ${result.imported}, updated ${result.updated}, skipped ${result.skipped}.`);
    } catch (error) {
      toast.error(`Workbook sync failed: ${error.message}`);
    }
  });
}

async function importFile(root, input) {
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;

  let payload;
  try {
    payload = JSON.parse(await file.text());
  } catch {
    toast.error("That file is not valid JSON.");
    return;
  }

  const list = Array.isArray(payload) ? payload : payload.compressors;
  if (!Array.isArray(list)) {
    toast.error("Expected a compressors array in the file.");
    return;
  }

  const mode = await confirmDialog({
    title: "Import compressors",
    message: `${list.length} compressor(s) found. Merge them with the current library, or replace it?`,
    choices: [
      { label: "Cancel", value: null },
      { label: "Replace all", value: "replace", variant: "btn-danger" },
      { label: "Merge", value: "merge", variant: "btn-primary" },
    ],
  });
  if (!mode) return;

  try {
    const result = await api.compressors.importAll(list, mode);
    compressors = result.compressors;
    selectedId = null;
    invalidate("compressors");
    renderList(root);
    renderDetail(root);
    toast.success(`Imported ${result.imported} compressor(s).`);
  } catch (error) {
    toast.error(`Import failed: ${error.message}`);
  }
}
