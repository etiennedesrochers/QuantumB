/** Generator: workbook selection -> circuit preview -> POST /api/generate & full project management. */

import { api } from "../api.js";
import { dataTable } from "../components/table.js";
import { downloadBlob, el, fillSelect, num, withBusy } from "../dom.js";
import { toast } from "../components/toast.js";
import { cached } from "../state.js";

const TENSIONS = ["208", "480", "575"];

let circuits = [];
let currentProjectId = null;
let ioRequestToken = 0;

/** The API returns tensions as {label, value}; fall back to plain strings. */
function tensionOptions(tensions) {
  if (!tensions?.length) return TENSIONS;
  return tensions.map((t) => (typeof t === "object" ? [t.value, t.label] : t));
}

export async function mount(root) {
  circuits = [];
  currentProjectId = null;
  ioRequestToken = 0;
  root.replaceChildren(render(root));

  const manufacturer = root.querySelector("#manufacturer");
  const capacity = root.querySelector("#capacity");

  manufacturer.addEventListener("change", () => refreshCapacities(manufacturer, capacity));
  root.querySelector("#loadCircuits").addEventListener("click", (e) => loadCircuits(root, e.target));
  root.querySelector("#generateForm").addEventListener("submit", (e) => submit(root, e));
  root.querySelector("#controller").addEventListener("change", () => refreshIoPreview(root));
  root.querySelector("#machineType").addEventListener("change", () => refreshIoPreview(root));

  // Project action buttons
  root.querySelector("#btnNewProject").addEventListener("click", () => newProject(root));
  root.querySelector("#btnSaveProject").addEventListener("click", (e) => saveCurrentProject(root, e.target));
  root.querySelector("#btnOpenProjects").addEventListener("click", () => openProjectModal(root));
  root.querySelector("#btnExportProject").addEventListener("click", () => exportCurrentProject(root));

  try {
    const filters = await api.workbook.generatorFilters();
    fillSelect(manufacturer, filters.manufacturers || [], { placeholder: "Select manufacturer\u2026" });
    fillSelect(capacity, filters.capacities || [], { placeholder: "Select capacity\u2026" });
    fillSelect(root.querySelector("#tension"), tensionOptions(filters.tensions), {
      placeholder: "Select tension\u2026",
    });
  } catch (error) {
    toast.error(`Could not load workbook filters: ${error.message}`);
  }

  try {
    const controllers = await cached("controllers", api.controllers);
    fillSelect(
      root.querySelector("#controller"),
      controllers.map((c) => [c.name, `${c.name} \u2014 ${c.company} (${c.inputs} in / ${c.outputs} out)`]),
      { placeholder: controllers.length ? undefined : "No controller in the module library" }
    );
  } catch (error) {
    toast.error(`Could not load controllers: ${error.message}`);
  }

  try {
    const machineTypes = await cached("machineTypes", api.machineTypes);
    fillSelect(root.querySelector("#machineType"), machineTypes, {
      placeholder: "No ordering \u2014 raw template I/O",
      selected: machineTypes[0],
    });
  } catch (error) {
    toast.error(`Could not load machine types: ${error.message}`);
  }

  // Auto-load project if redirected from Projects page
  const pendingId = sessionStorage.getItem("load_project_id");
  if (pendingId) {
    sessionStorage.removeItem("load_project_id");
    try {
      const projData = await api.projects.get(pendingId);
      await applyLoadedProject(root, projData);
    } catch (err) {
      toast.error(`Failed to auto-load project: ${err.message}`);
    }
  }
}

function render(root) {
  return el("form", { id: "generateForm", class: "stack" }, [
    el("section", { class: "card stack" }, [
      el("div", { class: "row-between wrap" }, [
        el("div", { class: "row-between", style: "gap: 12px;" }, [
          el("h2", { text: "Project Settings", style: "margin: 0;" }),
          el("span", { id: "projectBadge", class: "chip chip-shared", text: "Active: Unsaved Project" }),
        ]),
        el("div", { class: "toolbar" }, [
          el("button", { id: "btnNewProject", type: "button", class: "btn btn-secondary btn-sm" }, ["➕ New Project"]),
          el("button", { id: "btnSaveProject", type: "button", class: "btn btn-primary btn-sm" }, ["💾 Save Project"]),
          el("button", { id: "btnOpenProjects", type: "button", class: "btn btn-secondary btn-sm" }, ["📁 Open / Manage"]),
          el("button", { id: "btnExportProject", type: "button", class: "btn btn-secondary btn-sm" }, ["📥 Export (.aepj)"]),
        ]),
      ]),
      el("div", { class: "grid grid-4" }, [
        field("Project name", el("input", { id: "projectName", type: "text", value: "XNNOV Circuit Selection" })),
        field("Project number", el("input", { id: "projectNumber", type: "text", value: "PRJ-001" })),
        field("Revision", el("input", { id: "revision", type: "text", value: "A" })),
        field("Drawn by", el("input", { id: "drawnBy", type: "text", value: "" })),
      ]),
    ]),

    el("section", { class: "card" }, [
      el("h2", { text: "Workbook selection" }),
      el("div", { class: "grid grid-4" }, [
        field("Manufacturer", el("select", { id: "manufacturer" })),
        field("Nominal capacity (tons)", el("select", { id: "capacity" })),
        field("Tension", el("select", { id: "tension" })),
        field("\u00a0", el("button", { id: "loadCircuits", type: "button", class: "btn btn-secondary" }, [
          "Load circuits",
        ])),
      ]),
    ]),

    el("div", { class: "split" }, [
      el("section", { class: "card" }, [
        el("h2", { text: "Circuits" }),
        el("div", { id: "circuitList" }, [
          el("p", { class: "muted", text: "Load circuits from the workbook to continue." }),
        ]),
      ]),

      el("section", { class: "card stack" }, [
        el("div", { class: "row-between wrap" }, [
          el("h2", { text: "I/O list" }),
          el("div", { class: "chips", id: "ioSummary" }),
        ]),
        el("div", { class: "grid grid-2" }, [
          field("Machine type", el("select", { id: "machineType" })),
          field("Controller", el("select", { id: "controller" })),
        ]),
        el("div", { id: "ioList", class: "table-scroll" }, [
          el("p", { class: "muted", text: "Load circuits to see the I/O they generate." }),
        ]),
      ]),
    ]),

    el("section", { class: "card row-between" }, [
      field("Output format", el("select", { id: "format" }, [
        el("option", { value: "both", selected: true }, ["DXF + DWG"]),
        el("option", { value: "dxf" }, ["DXF only"]),
        el("option", { value: "dwg" }, ["DWG only"]),
      ])),
      el("button", { id: "generateBtn", type: "submit", class: "btn btn-primary" }, ["Generate drawings"]),
    ]),
  ]);
}

function field(label, control) {
  return el("label", { class: "field" }, [el("span", { class: "field-label", text: label }), control]);
}

async function refreshCapacities(manufacturerEl, capacityEl) {
  try {
    const filters = await api.workbook.generatorFilters(manufacturerEl.value);
    fillSelect(capacityEl, filters.capacities || [], { placeholder: "Select capacity\u2026" });
  } catch (error) {
    toast.error(`Could not load capacities: ${error.message}`);
  }
}

async function loadCircuits(root, button) {
  const capacity = root.querySelector("#capacity").value;
  const manufacturer = root.querySelector("#manufacturer").value;
  const tension = root.querySelector("#tension").value;

  if (!capacity || !manufacturer || !tension) {
    toast.error("Select a manufacturer, nominal capacity and tension first.");
    return;
  }

  await withBusy(button, "Loading\u2026", async () => {
    try {
      const payload = await api.workbook.circuits(capacity, manufacturer, tension);
      circuits = payload.circuits || [];
      renderCircuits(root.querySelector("#circuitList"), tension);
      refreshIoPreview(root);
      toast.success(`Loaded ${circuits.length} circuit(s).`);
    } catch (error) {
      circuits = [];
      renderCircuits(root.querySelector("#circuitList"), tension);
      refreshIoPreview(root);
      toast.error(`Could not load circuits: ${error.message}`);
    }
  });
}

function renderCircuits(container, tension) {
  if (circuits.length === 0) {
    container.replaceChildren(el("p", { class: "muted", text: "No circuits found for this selection." }));
    return;
  }

  container.replaceChildren(
    ...circuits.map((circuit, index) =>
      el("article", { class: "circuit" }, [
        el("header", { class: "circuit-head" }, [
          el("span", { class: "badge", text: String(index + 1) }),
          el("strong", { text: circuit.name || `Circuit ${index + 1}` }),
          el("span", { class: "muted", text: circuit.description || "" }),
        ]),
        el("div", { class: "circuit-body" }, (circuit.compressors || []).map((comp) => compressorRow(comp, tension))),
      ])
    )
  );
}

function compressorRow(comp, tension) {
  const templates = comp.templates || [];
  return el("div", { class: "compressor-row" }, [
    el("div", {}, [
      el("div", { class: "strong", text: comp.skid_model_number || comp.description || comp.model_number || "" }),
      el("div", { class: "muted small", text: `Model (${tension}V): ${comp.model_number || "-"} \u00b7 Qty: ${comp.quantity || 1}` }),
    ]),
    el("div", { class: "chips" }, templates.length
      ? templates.map((t) => el("span", { class: `chip chip-${t.scope === "shared" ? "shared" : "unit"}` }, [
          `${t.name} \u00b7 ${t.scope === "shared" ? "shared" : "per unit"}`,
        ]))
      : [el("span", { class: "muted small", text: "No templates assigned" })]),
  ]);
}

/** Expand each compressor's library templates into per-circuit quantities. */
function buildPayload(root, compressorLibrary) {
  const selectionCircuits = circuits.map((circuit, index) => {
    const compressors = (circuit.compressors || []).map((comp) => {
      const match = findLibraryMatch(comp, compressorLibrary);
      const quantity = num(comp.quantity, 1) || 1;
      const source = comp.templates?.length ? comp.templates : match?.templates || [];

      return {
        model_number: comp.model_number || "",
        description: comp.description || comp.skid_model_number || comp.model_number || "",
        templates: source.map((t) => ({
          name: t.name,
          quantity: t.scope === "shared" ? 1 : quantity,
        })),
      };
    });

    return {
      name: circuit.name || `CU${String(index + 1).padStart(3, "0")}`,
      description: circuit.description || "",
      compressors,
    };
  });

  return {
    project_name: root.querySelector("#projectName").value || "XNNOV Circuit Selection",
    project_number: root.querySelector("#projectNumber").value || "",
    revision: root.querySelector("#revision").value || "A",
    drawn_by: root.querySelector("#drawnBy").value || "",
    voltage: root.querySelector("#tension").value || "",
    circuits: selectionCircuits,
  };
}

function findLibraryMatch(comp, library) {
  const model = String(comp.model_number || "").toLowerCase();
  const skid = String(comp.skid_model_number || "").toLowerCase();
  return library.find((item) => {
    const itemModel = String(item.model || "").toLowerCase();
    const itemName = String(item.name || "").toLowerCase();
    return (model && itemModel === model) || (skid && (itemName === skid || itemModel === skid));
  });
}

async function submit(root, event) {
  event.preventDefault();

  if (circuits.length === 0) {
    toast.error("Load circuits from the workbook before generating.");
    return;
  }

  const button = root.querySelector("#generateBtn");
  await withBusy(button, "Generating\u2026", async () => {
    try {
      const library = await cached("compressors", api.compressors.list);
      const payload = buildPayload(root, library);
      if (payload.circuits.every((c) => c.compressors.every((comp) => comp.templates.length === 0))) {
        toast.info("No templates are assigned to these compressors \u2014 the drawings will be empty.");
      }
      const blob = await api.generate(
        payload,
        root.querySelector("#format").value,
        root.querySelector("#controller").value,
        root.querySelector("#machineType").value
      );
      downloadBlob(blob, "generated_drawings.zip");
      toast.success("Drawings generated.");
    } catch (error) {
      toast.error(`Generation failed: ${error.message}`);
    }
  });
}

/** Ask the backend which I/O the current selection would produce. */
async function refreshIoPreview(root) {
  const list = root.querySelector("#ioList");
  const summary = root.querySelector("#ioSummary");
  const token = ++ioRequestToken;

  if (circuits.length === 0) {
    summary.replaceChildren();
    list.replaceChildren(el("p", { class: "muted", text: "Load circuits to see the I/O they generate." }));
    return;
  }

  summary.replaceChildren();
  list.replaceChildren(el("p", { class: "muted", text: "Computing I/O\u2026" }));

  try {
    const library = await cached("compressors", api.compressors.list);
    const preview = await api.ioPreview(
      buildPayload(root, library),
      root.querySelector("#controller").value,
      root.querySelector("#machineType").value
    );
    if (token !== ioRequestToken) return;
    renderIoPreview(summary, list, preview);
  } catch (error) {
    if (token !== ioRequestToken) return;
    summary.replaceChildren();
    list.replaceChildren(el("p", { class: "error-text", text: error.message }));
  }
}

/** Dummy circuits carry the same value in name and number; don't repeat it. */
function circuitLabel(row) {
  const name = row.circuit_name || "";
  const no = row.circuit_no || "";
  return !no || no === name ? name : `${name} (${no})`;
}

function renderIoPreview(summary, list, preview) {
  const { total, inputs, outputs, reserved, controller_pages: pages } = preview.summary;
  summary.replaceChildren(
    ...[
      el("span", { class: "chip", text: `${total} I/O` }),
      el("span", { class: "chip", text: `${inputs} in` }),
      el("span", { class: "chip", text: `${outputs} out` }),
      reserved ? el("span", { class: "chip", text: `${reserved} reserved` }) : null,
      el("span", { class: "chip chip-shared", text: `${pages} controller page(s)` }),
    ].filter(Boolean)
  );

  list.replaceChildren(
    dataTable({
      columns: [
        { label: "Address", key: "address" },
        { label: "No", key: "number" },
        { label: "Dir", key: "io_type" },
        { label: "Tag", key: "tag" },
        { label: "Description", key: "description" },
        { label: "Type", key: "io_type_name" },
        { label: "Circuit", render: circuitLabel },
        { label: "Template", key: "template_name" },
      ],
      rows: preview.items,
      empty: "These templates define no I/O.",
    })
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Project Management (Save, Open, New, Export, Import)
// ─────────────────────────────────────────────────────────────────────────────

function updateProjectBadge(root, projData = null) {
  const badge = root.querySelector("#projectBadge");
  if (!badge) return;

  if (projData || currentProjectId) {
    const name = projData?.name || root.querySelector("#projectName").value || currentProjectId;
    const num = projData?.settings?.project_number || root.querySelector("#projectNumber").value || "";
    badge.textContent = `Active: ${name}${num ? ` [${num}]` : ""}`;
    badge.className = "chip chip-shared";
  } else {
    badge.textContent = "Active: Unsaved Project";
    badge.className = "chip";
  }
}

function newProject(root) {
  currentProjectId = null;
  root.querySelector("#projectName").value = "XNNOV Circuit Selection";
  root.querySelector("#projectNumber").value = "PRJ-001";
  root.querySelector("#revision").value = "A";
  root.querySelector("#drawnBy").value = "";
  root.querySelector("#manufacturer").value = "";
  root.querySelector("#capacity").value = "";
  root.querySelector("#tension").value = "";
  circuits = [];
  renderCircuits(root.querySelector("#circuitList"), "");
  refreshIoPreview(root);
  updateProjectBadge(root, null);
  toast.info("Cleared current state for new project.");
}

async function saveCurrentProject(root, button) {
  const name = root.querySelector("#projectName").value || "XNNOV Circuit Selection";
  const projNum = root.querySelector("#projectNumber").value || "";
  const rev = root.querySelector("#revision").value || "A";
  const drawnBy = root.querySelector("#drawnBy").value || "";
  const mfr = root.querySelector("#manufacturer").value || "";
  const cap = root.querySelector("#capacity").value || "";
  const tension = root.querySelector("#tension").value || "";
  const format = root.querySelector("#format").value || "both";

  const payload = {
    name: name,
    settings: {
      project_name: name,
      project_number: projNum,
      revision: rev,
      drawn_by: drawnBy,
      manufacturer: mfr,
      capacity: cap,
      tension: tension,
      format: format,
    },
    circuits: circuits,
  };

  await withBusy(button, "Saving\u2026", async () => {
    try {
      let saved;
      if (currentProjectId) {
        saved = await api.projects.update(currentProjectId, payload);
      } else {
        saved = await api.projects.create(payload);
      }
      currentProjectId = saved.id;
      updateProjectBadge(root, saved);
      toast.success(`Project '${saved.name}' saved to managed projects.`);
    } catch (err) {
      toast.error(`Save failed: ${err.message}`);
    }
  });
}

async function applyLoadedProject(root, proj) {
  currentProjectId = proj.id || proj.filename?.replace(/\.[^/.]+$/, "") || null;
  const settings = proj.settings || {};

  const nameInput = root.querySelector("#projectName");
  const numberInput = root.querySelector("#projectNumber");
  const revInput = root.querySelector("#revision");
  const drawnInput = root.querySelector("#drawnBy");
  const formatInput = root.querySelector("#format");

  if (nameInput) nameInput.value = proj.name || settings.project_name || settings.title || "XNNOV Circuit Selection";
  if (numberInput) numberInput.value = settings.project_number || settings.project || "";
  if (revInput) revInput.value = settings.revision || "A";
  if (drawnInput) drawnInput.value = settings.drawn_by || "";
  if (formatInput) formatInput.value = settings.format || "both";

  const mfrSelect = root.querySelector("#manufacturer");
  const capSelect = root.querySelector("#capacity");
  const tenSelect = root.querySelector("#tension");

  if (settings.manufacturer && mfrSelect) {
    mfrSelect.value = settings.manufacturer;
    await refreshCapacities(mfrSelect, capSelect);
  }
  if (settings.capacity && capSelect) capSelect.value = settings.capacity;
  if (settings.tension && tenSelect) tenSelect.value = settings.tension;

  circuits = proj.circuits || [];

  renderCircuits(root.querySelector("#circuitList"), settings.tension || tenSelect?.value || "");
  refreshIoPreview(root);
  updateProjectBadge(root, proj);
  toast.success(`Opened project '${proj.name || proj.id}'.`);
}

async function openProjectModal(root) {
  const modalContent = el("div", { class: "modal modal-lg stack" }, [
    el("div", { class: "row-between" }, [
      el("h3", { class: "modal-title", text: "Managed Projects Library" }),
      el("button", {
        type: "button",
        class: "btn btn-secondary btn-sm",
        onClick: () => triggerProjectImport(root, backdrop),
      }, ["📤 Import .aepj File"]),
    ]),
    el("div", { id: "modalProjectsBody" }, [el("p", { class: "muted", text: "Loading saved projects\u2026" })]),
    el("div", { class: "modal-actions" }, [
      el("button", {
        type: "button",
        class: "btn btn-secondary",
        onClick: () => backdrop.remove(),
      }, ["Close"]),
    ]),
  ]);

  const backdrop = el("div", { class: "modal-backdrop" }, [modalContent]);
  document.body.append(backdrop);

  try {
    const list = await api.projects.list();
    const body = modalContent.querySelector("#modalProjectsBody");
    if (list.length === 0) {
      body.replaceChildren(el("p", { class: "muted", text: "No saved projects in the managed library yet." }));
      return;
    }

    const columns = [
      { label: "Name", render: (r) => el("span", { style: "font-weight: 600;", text: r.name }) },
      { label: "Project #", key: "project_number" },
      { label: "Rev", key: "revision" },
      { label: "Circuits", render: (r) => `${r.circuits_count || 0} circuit(s)` },
      { label: "Updated", render: (r) => (r.updated_at ? new Date(r.updated_at).toLocaleString() : "-") },
      {
        label: "Action",
        render: (r) =>
          el("div", { class: "toolbar" }, [
            el("button", {
              type: "button",
              class: "btn btn-primary btn-sm",
              onClick: async () => {
                try {
                  const full = await api.projects.get(r.id);
                  await applyLoadedProject(root, full);
                  backdrop.remove();
                } catch (err) {
                  toast.error(`Could not load project: ${err.message}`);
                }
              },
            }, ["📂 Open"]),
            el("button", {
              type: "button",
              class: "btn btn-danger btn-sm",
              onClick: async () => {
                if (!confirm(`Delete project '${r.name}'?`)) return;
                try {
                  await api.projects.remove(r.id);
                  toast.success("Project deleted.");
                  backdrop.remove();
                  openProjectModal(root);
                } catch (err) {
                  toast.error(`Delete failed: ${err.message}`);
                }
              },
            }, ["🗑️"]),
          ]),
      },
    ];

    body.replaceChildren(dataTable({ columns, rows: list }));
  } catch (err) {
    toast.error(`Failed to list projects: ${err.message}`);
  }
}

function triggerProjectImport(root, modalBackdrop = null) {
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
        if (modalBackdrop) modalBackdrop.remove();
        await applyLoadedProject(root, res);
      } catch (err) {
        toast.error(`Import failed: ${err.message}`);
      }
    },
  });

  document.body.append(fileInput);
  fileInput.click();
  fileInput.remove();
}

function exportCurrentProject(root) {
  if (currentProjectId) {
    const url = api.projects.exportUrl(currentProjectId);
    const link = el("a", { href: url, download: "" });
    document.body.append(link);
    link.click();
    link.remove();
    toast.success("Downloading project file.");
    return;
  }

  const name = root.querySelector("#projectName").value || "XNNOV_Circuit_Selection";
  const fullProject = {
    version: 1,
    name: name,
    updated_at: new Date().toISOString(),
    settings: {
      title: name,
      project_name: name,
      project_number: root.querySelector("#projectNumber").value || "",
      revision: root.querySelector("#revision").value || "A",
      drawn_by: root.querySelector("#drawnBy").value || "",
      manufacturer: root.querySelector("#manufacturer").value || "",
      capacity: root.querySelector("#capacity").value || "",
      tension: root.querySelector("#tension").value || "",
      format: root.querySelector("#format").value || "both",
    },
    circuits: circuits,
  };

  const blob = new Blob([JSON.stringify(fullProject, null, 2)], { type: "application/json" });
  downloadBlob(blob, `${name.replace(/[^\w-]/g, "_")}.aepj`);
  toast.success("Exported project file.");
}
