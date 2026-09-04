/** Full interactive browser & manager for Templates, Circuit, and Config libraries. */

import { api } from "../api.js";
import { el, withBusy } from "../dom.js";
import { dataTable } from "../components/table.js";
import { confirmAction, toast } from "../components/toast.js";

const CATEGORIES = [
  {
    key: "templates",
    label: "Templates",
    icon: "📁",
    description: "Drawing template files, ladder types, and valve type mappings.",
    sources: [
      { key: "templates", label: "Drawing Templates", load: api.templates },
      { key: "ladder-types", label: "Ladder Types", load: api.ladderTypes, save: api.saveLadderTypes },
      { key: "valve-types", label: "Valve Types", load: api.valveTypes, save: api.saveValveTypes },
      { key: "valve-ios", label: "Valve I/O", load: api.valveIos, save: api.saveValveIos },
    ],
  },
  {
    key: "io-types",
    label: "I/O Types",
    icon: "🔌",
    description: "Named I/O types: the controller-page and ladder-page templates each signal maps to.",
    sources: [
      { key: "io-types", label: "I/O Types", load: api.ioTypes, save: api.saveIoTypes },
    ],
  },
  {
    key: "circuit",
    label: "Circuit",
    icon: "⚡",
    description: "Circuit specifications, module definitions, I/O values, and compressor circuit mappings.",
    sources: [
      { key: "circuits", label: "Circuits", load: api.circuits, isCircuits: true },
      { key: "modules", label: "Modules", load: api.modules, save: api.saveModules },
      { key: "module-io-values", label: "Module I/O Values", load: api.moduleIoValues, save: api.saveModuleIoValues },
      { key: "workbook", label: "Workbook Compressors", load: api.workbook.compressors },
    ],
  },
  {
    key: "config",
    label: "Config",
    icon: "⚙️",
    description: "Application configuration, generation rules, and system settings.",
    sources: [
      { key: "app-config", label: "App Config", load: api.appConfig, save: api.saveAppConfig },
      { key: "rules", label: "Rules", load: api.rules, save: api.saveRules },
    ],
  },
];

let activeCategory = CATEGORIES[0];
let activeSource = activeCategory.sources[0];
let cachedTemplates = null;
let cachedValveTypes = null;
let cachedIoTypes = null;

export function sortIoItems(ios) {
  if (!Array.isArray(ios)) return [];
  return ios.sort((a, b) => {
    const dirA = String(a.direction || "").trim().toLowerCase();
    const dirB = String(b.direction || "").trim().toLowerCase();
    const dirOrderA = dirA === "input" ? 1 : dirA === "output" ? 2 : 3;
    const dirOrderB = dirB === "input" ? 1 : dirB === "output" ? 2 : 3;
    if (dirOrderA !== dirOrderB) return dirOrderA - dirOrderB;

    const sigA = String(a.signal_type || a.signal_category || "").trim().toLowerCase();
    const sigB = String(b.signal_type || b.signal_category || "").trim().toLowerCase();
    const sigOrderA = sigA === "digital" ? 1 : sigA === "analog" ? 2 : 3;
    const sigOrderB = sigB === "digital" ? 1 : sigB === "analog" ? 2 : 3;
    if (sigOrderA !== sigOrderB) return sigOrderA - sigOrderB;

    const nameA = String(a.name || "").toLowerCase();
    const nameB = String(b.name || "").toLowerCase();
    return nameA.localeCompare(nameB);
  });
}

export async function mount(root) {
  root.replaceChildren(
    el("section", { class: "card stack" }, [
      el("div", { class: "row-between wrap" }, [
        el("div", {}, [
          el("h2", { text: "Libraries" }),
          el("p", { class: "muted", id: "categoryDescription", text: activeCategory.description }),
        ]),
      ]),
      el("div", { class: "category-tabs", id: "categoryTabs" }, CATEGORIES.map((cat) =>
        el("button", {
          type: "button",
          class: `category-tab ${cat.key === activeCategory.key ? "is-active" : ""}`,
          dataset: { key: cat.key },
          onClick: () => switchCategory(root, cat),
        }, [
          el("span", { text: cat.icon }),
          el("span", { text: cat.label }),
        ])
      )),
      el("div", { class: "sub-tabs", id: "subTabs" }),
      el("div", { id: "libraryBody" }),
    ])
  );

  renderSubTabs(root);
  await loadSource(root, activeSource);
}

function switchCategory(root, category) {
  activeCategory = category;
  activeSource = category.sources[0];

  const categoryTabs = root.querySelectorAll(".category-tab");
  for (const tab of categoryTabs) {
    tab.classList.toggle("is-active", tab.dataset.key === category.key);
  }

  const desc = root.querySelector("#categoryDescription");
  if (desc) desc.textContent = category.description;

  renderSubTabs(root);
  loadSource(root, activeSource);
}

function renderSubTabs(root) {
  const container = root.querySelector("#subTabs");
  if (!container) return;

  // A single-source category needs no sub-tab bar.
  if (activeCategory.sources.length < 2) {
    container.replaceChildren();
    container.hidden = true;
    return;
  }
  container.hidden = false;

  container.replaceChildren(
    ...activeCategory.sources.map((source) =>
      el("button", {
        type: "button",
        class: `tab ${source.key === activeSource.key ? "is-active" : ""}`,
        dataset: { key: source.key },
        onClick: () => switchSource(root, source),
      }, [source.label])
    )
  );
}

function switchSource(root, source) {
  activeSource = source;

  const tabs = root.querySelectorAll("#subTabs .tab");
  for (const tab of tabs) {
    tab.classList.toggle("is-active", tab.dataset.key === source.key);
  }

  loadSource(root, source);
}

async function loadSource(root, source) {
  const body = root.querySelector("#libraryBody");
  if (!body) return;

  body.replaceChildren(el("p", { class: "muted", text: "Loading\u2026" }));

  try {
    const data = await source.load();
    body.replaceChildren(renderData(root, data, source));
  } catch (error) {
    body.replaceChildren(el("p", { class: "error-text", text: error.message }));
    toast.error(`Could not load ${source.label}: ${error.message}`);
  }
}

function renderData(root, data, source) {
  const sourceKey = source.key;
  if (data === null || data === undefined) {
    return el("p", { class: "muted", text: "No data available." });
  }

  // ── Drawing Templates View ───────────────────────────────────────────────
  if (sourceKey === "templates" && typeof data === "object" && !Array.isArray(data)) {
    cachedTemplates = data;
    return renderTemplatesView(root, data);
  }

  // ── Circuits Management View ──────────────────────────────────────────────
  if (source.isCircuits && Array.isArray(data)) {
    return renderCircuitsView(root, data);
  }

  // ── I/O Types Configuration View ──────────────────────────────────────────
  if (sourceKey === "io-types" && Array.isArray(data)) {
    cachedIoTypes = data;
    return renderIoTypesView(root, data, source);
  }

  // ── Array of primitive strings (e.g. module-io-values, valve-types) ─────
  if (Array.isArray(data) && (data.length === 0 || typeof data[0] === "string")) {
    return renderStringListView(root, data, source);
  }

  // ── Array of objects (e.g. modules, rules, ladder-types, io-types) ────────
  if (Array.isArray(data) && data.length > 0 && typeof data[0] === "object") {
    return renderObjectListView(root, data, source);
  }

  // ── Generic key-value object (e.g. appConfig, valveIos) ───────────────────
  if (typeof data === "object") {
    return renderDictView(root, data, source);
  }

  return el("pre", { class: "code", text: JSON.stringify(data, null, 2) });
}

// ─────────────────────────────────────────────────────────────────────────────
// Drawing Templates Configuration (Single Table, Sorting, Details & I/O Editor)
// ─────────────────────────────────────────────────────────────────────────────

let selectedTemplateItem = null;
let currentTemplateCategoryFilter = "all";
let templateSearchQuery = "";
let templateSortKey = "category"; // "category" or "name"
let templateSortAsc = true;

function renderTemplatesView(root, templatesDict) {
  // Build flat array of templates
  const allTemplates = [];
  for (const [category, files] of Object.entries(templatesDict)) {
    if (Array.isArray(files)) {
      for (const file of files) {
        allTemplates.push({ name: file, category });
      }
    }
  }

  if (allTemplates.length === 0) {
    return el("p", { class: "muted", text: "No templates found on disk." });
  }

  // Ensure initial selection
  if (!selectedTemplateItem || !allTemplates.some(t => t.name === selectedTemplateItem.name && t.category === selectedTemplateItem.category)) {
    selectedTemplateItem = allTemplates[0];
  }

  const categoriesList = ["all", ...Object.keys(templatesDict)];

  const searchInput = el("input", {
    type: "search",
    placeholder: "Search template name or category…",
    value: templateSearchQuery,
    style: "max-width: 280px;",
    onInput: (e) => {
      templateSearchQuery = e.target.value.toLowerCase().trim();
      updateTableAndDetails();
    },
  });

  const uploadInput = el("input", {
    type: "file",
    accept: ".dxf,.dwg",
    style: "display: none;",
    onChange: async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const cat = currentTemplateCategoryFilter === "all" ? "regular" : currentTemplateCategoryFilter;
      const formData = new FormData();
      formData.append("file", file);
      try {
        const res = await api.uploadTemplate(cat, formData);
        toast.success(res.message || `Uploaded ${res.name}`);
        selectedTemplateItem = { name: res.name, category: cat };
        await loadSource(root, activeSource);
      } catch (err) {
        toast.error(`Upload failed: ${err.message}`);
      }
    },
  });

  const tableContainer = el("div", { id: "templatesTableContainer" });
  const detailContainer = el("div", { id: "templateDetailContainer", class: "stack" });

  function filterAndSortTemplates() {
    return allTemplates
      .filter((t) => {
        const matchesCategory = currentTemplateCategoryFilter === "all" || t.category === currentTemplateCategoryFilter;
        const matchesSearch = !templateSearchQuery ||
          t.name.toLowerCase().includes(templateSearchQuery) ||
          t.category.toLowerCase().includes(templateSearchQuery);
        return matchesCategory && matchesSearch;
      })
      .sort((a, b) => {
        let valA = a[templateSortKey].toLowerCase();
        let valB = b[templateSortKey].toLowerCase();
        if (valA < valB) return templateSortAsc ? -1 : 1;
        if (valA > valB) return templateSortAsc ? 1 : -1;
        return 0;
      });
  }

  function updateTableAndDetails() {
    const filtered = filterAndSortTemplates();

    if (filtered.length > 0 && (!selectedTemplateItem || !filtered.some(t => t.name === selectedTemplateItem.name && t.category === selectedTemplateItem.category))) {
      selectedTemplateItem = filtered[0];
    }

    const columns = [
      {
        label: "Template Name",
        key: "name",
        render: (row) => el("span", { style: "font-weight: 600;", text: row.name }),
      },
      {
        label: "Category / Type",
        key: "category",
        render: (row) => el("span", { class: "chip", text: row.category }),
      },
      {
        label: "Actions",
        render: (row) =>
          el("div", { class: "toolbar" }, [
            el("button", {
              type: "button",
              class: "btn btn-secondary btn-sm",
              title: "Rename Template",
              onClick: (e) => {
                e.stopPropagation();
                handleRenameTemplate(root, row.category, row.name);
              },
            }, ["✏️ Rename"]),
            el("button", {
              type: "button",
              class: "btn btn-danger btn-sm",
              title: "Delete Template",
              onClick: (e) => {
                e.stopPropagation();
                handleDeleteTemplate(root, row.category, row.name);
              },
            }, ["🗑️"]),
          ]),
      },
    ];

    tableContainer.replaceChildren(
      dataTable({
        columns,
        rows: filtered,
        onRowClick: (row) => {
          selectedTemplateItem = row;
          updateTableAndDetails();
        },
        isActive: (row) =>
          selectedTemplateItem &&
          row.name === selectedTemplateItem.name &&
          row.category === selectedTemplateItem.category,
        empty: "No templates match filter criteria.",
      })
    );

    if (selectedTemplateItem) {
      loadTemplateDetails(detailContainer, selectedTemplateItem, root);
    } else {
      detailContainer.replaceChildren(el("p", { class: "muted", text: "Select a template row above to view and configure details & I/O." }));
    }
  }

  const container = el("div", { class: "stack" }, [
    uploadInput,
    el("div", { class: "row-between wrap" }, [
      el("div", { class: "sub-tabs" }, categoriesList.map((cat) =>
        el("button", {
          type: "button",
          class: `tab ${currentTemplateCategoryFilter === cat ? "is-active" : ""}`,
          onClick: () => {
            currentTemplateCategoryFilter = cat;
            const categoryTabs = container.querySelectorAll(".sub-tabs .tab");
            for (const t of categoryTabs) {
              t.classList.toggle("is-active", t.textContent.toLowerCase() === cat);
            }
            updateTableAndDetails();
          },
        }, [cat === "all" ? "All Types" : cat])
      )),
      el("div", { class: "toolbar", style: "align-items: center;" }, [
        searchInput,
        el("button", {
          type: "button",
          class: "btn btn-secondary btn-sm",
          onClick: () => {
            if (templateSortKey === "category") {
              templateSortAsc = !templateSortAsc;
            } else {
              templateSortKey = "category";
              templateSortAsc = true;
            }
            updateTableAndDetails();
          },
        }, [`Sort by Category ${templateSortKey === "category" ? (templateSortAsc ? "▲" : "▼") : ""}`]),
        el("button", {
          type: "button",
          class: "btn btn-secondary btn-sm",
          onClick: () => {
            if (templateSortKey === "name") {
              templateSortAsc = !templateSortAsc;
            } else {
              templateSortKey = "name";
              templateSortAsc = true;
            }
            updateTableAndDetails();
          },
        }, [`Sort by Name ${templateSortKey === "name" ? (templateSortAsc ? "▲" : "▼") : ""}`]),
        el("button", {
          type: "button",
          class: "btn btn-primary btn-sm",
          onClick: () => uploadInput.click(),
        }, ["📤 Upload Template"]),
      ]),
    ]),
    tableContainer,
    el("hr"),
    detailContainer,
  ]);

  updateTableAndDetails();
  return container;
}

async function loadTemplateDetails(container, templateItem, root) {
  container.replaceChildren(el("p", { class: "muted", text: "Loading template details & I/O configuration\u2026" }));

  try {
    if (!cachedIoTypes) {
      try { cachedIoTypes = await api.ioTypes(); } catch { cachedIoTypes = []; }
    }
    const info = await api.templateInfo(templateItem.category, templateItem.name);
    renderTemplateDetailCard(container, info, templateItem, root);
  } catch (err) {
    container.replaceChildren(
      el("div", { class: "card error-text" }, [`Failed to load template info: ${err.message}`])
    );
  }
}

const IO_CATEGORY_FILTERS = [
  { key: "all", label: "All I/Os" },
  { key: "input_digital", label: "Input Digital (DI)", direction: "Input", signal_type: "Digital" },
  { key: "input_analog", label: "Input Analog (AI)", direction: "Input", signal_type: "Analog" },
  { key: "output_digital", label: "Output Digital (DO)", direction: "Output", signal_type: "Digital" },
  { key: "output_analog", label: "Output Analog (AO)", direction: "Output", signal_type: "Analog" },
];

function renderTemplateDetailCard(container, info, templateItem, root) {
  const currentIos = sortIoItems(JSON.parse(JSON.stringify(info.ios || [])));
  let currentIoCategoryFilter = "all";

  let insX = (info.insertion_point?.[0] ?? 0).toString();
  let insY = (info.insertion_point?.[1] ?? 0).toString();
  let offX = (info.offset?.[0] ?? 0).toString();
  let offY = (info.offset?.[1] ?? 0).toString();

  const insXInput = el("input", { type: "number", step: "any", value: insX, onChange: (e) => (insX = e.target.value) });
  const insYInput = el("input", { type: "number", step: "any", value: insY, onChange: (e) => (insY = e.target.value) });
  const offXInput = el("input", { type: "number", step: "any", value: offX, onChange: (e) => (offX = e.target.value) });
  const offYInput = el("input", { type: "number", step: "any", value: offY, onChange: (e) => (offY = e.target.value) });

  const iosTableContainer = el("div", { class: "stack" });

  function renderIosTable() {
    const activeFilterObj = IO_CATEGORY_FILTERS.find((f) => f.key === currentIoCategoryFilter);
    const filteredIos = currentIos.filter((io) => {
      if (currentIoCategoryFilter === "all" || !activeFilterObj) return true;
      return io.direction === activeFilterObj.direction && io.signal_type === activeFilterObj.signal_type;
    });

    const filterTabsHeader = el(
      "div",
      { class: "sub-tabs", style: "margin-bottom: 12px;" },
      IO_CATEGORY_FILTERS.map((f) => {
        const count =
          f.key === "all"
            ? currentIos.length
            : currentIos.filter((io) => io.direction === f.direction && io.signal_type === f.signal_type).length;
        return el(
          "button",
          {
            type: "button",
            class: `tab ${currentIoCategoryFilter === f.key ? "is-active" : ""}`,
            onClick: () => {
              currentIoCategoryFilter = f.key;
              renderIosTable();
            },
          },
          [`${f.label} (${count})`]
        );
      })
    );

    if (filteredIos.length === 0) {
      iosTableContainer.replaceChildren(
        filterTabsHeader,
        el("p", { class: "muted", text: "No I/O signals match the selected filter." })
      );
      return;
    }

    const rows = filteredIos.map((io) => {
      const idx = currentIos.indexOf(io);
      const nameIn = el("input", { class: "table-input", value: io.name || "", onChange: (e) => (io.name = e.target.value) });
      const descIn = el("input", { class: "table-input", value: io.description || "", onChange: (e) => (io.description = e.target.value) });
      const dirIn = el("select", {
        class: "table-input",
        onChange: (e) => {
          io.direction = e.target.value;
          sortIoItems(currentIos);
          renderIosTable();
        },
      }, [
        el("option", { value: "Input", selected: io.direction === "Input" }, ["Input"]),
        el("option", { value: "Output", selected: io.direction === "Output" }, ["Output"]),
      ]);
      const sigIn = el("select", {
        class: "table-input",
        onChange: (e) => {
          io.signal_type = e.target.value;
          sortIoItems(currentIos);
          renderIosTable();
        },
      }, [
        el("option", { value: "Digital", selected: io.signal_type === "Digital" }, ["Digital"]),
        el("option", { value: "Analog", selected: io.signal_type === "Analog" }, ["Analog"]),
      ]);

      // Filter I/O Types library dropdown options by matching direction & signal_type
      const matchingIoTypeDefs = (Array.isArray(cachedIoTypes) ? cachedIoTypes : []).filter((item) => {
        if (typeof item !== "object") return true;
        const matchDir = !io.direction || !item.direction || item.direction === io.direction;
        const matchSig = !io.signal_type || !item.signal_category || item.signal_category === io.signal_type;
        return matchDir && matchSig;
      });
      const matchingTypeNames = matchingIoTypeDefs
        .map((item) => (typeof item === "object" ? item.name : item))
        .filter(Boolean);

      const currentIoType = io.io_type || "";
      const ioTypeOptions = [
        el("option", { value: "", selected: !currentIoType }, ["-- Select I/O Type --"]),
        ...matchingTypeNames.map((tName) =>
          el("option", { value: tName, selected: String(tName) === String(currentIoType) }, [tName])
        ),
      ];
      // Preserve custom io_type if not in predefined list
      if (currentIoType && !matchingTypeNames.includes(currentIoType)) {
        ioTypeOptions.push(el("option", { value: currentIoType, selected: true }, [currentIoType]));
      }

      const ioTypeSelect = el(
        "select",
        {
          class: "table-input",
          onChange: (e) => {
            io.io_type = e.target.value;
            // Auto-populate signal_type and direction from selected I/O type metadata
            const foundDef = cachedIoTypes?.find(
              (item) => typeof item === "object" && item.name === e.target.value
            );
            if (foundDef) {
              if (foundDef.direction) io.direction = foundDef.direction;
              if (foundDef.signal_category) io.signal_type = foundDef.signal_category;
              if (foundDef.ladder_type && !io.ladder_type) io.ladder_type = foundDef.ladder_type;
            }
            sortIoItems(currentIos);
            renderIosTable();
          },
        },
        ioTypeOptions
      );

      const ladderTypeIn = el("input", { class: "table-input", value: io.ladder_type || "", onChange: (e) => (io.ladder_type = e.target.value) });

      return el("tr", {}, [
        el("td", {}, [nameIn]),
        el("td", {}, [descIn]),
        el("td", {}, [dirIn]),
        el("td", {}, [sigIn]),
        el("td", {}, [ioTypeSelect]),
        el("td", {}, [ladderTypeIn]),
        el("td", {}, [
          el("button", {
            type: "button",
            class: "btn btn-danger btn-sm",
            onClick: () => {
              if (idx !== -1) currentIos.splice(idx, 1);
              renderIosTable();
            },
          }, ["🗑️"]),
        ]),
      ]);
    });

    iosTableContainer.replaceChildren(
      filterTabsHeader,
      el("table", { class: "table" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: "Signal Name" }),
            el("th", { text: "Description" }),
            el("th", { text: "Direction" }),
            el("th", { text: "Signal Type" }),
            el("th", { text: "I/O Type" }),
            el("th", { text: "Action" }),
          ]),
        ]),
        el("tbody", {}, rows),
      ])
    );
  }

  renderIosTable();

  // Blocks & attributes summary
  const blocksCount = info.blocks ? info.blocks.length : 0;

  container.replaceChildren(
    el("div", { class: "card stack" }, [
      el("div", { class: "row-between wrap" }, [
        el("div", { class: "row-between", style: "gap: 10px;" }, [
          el("h3", { text: `Selected Template: ${info.name}`, style: "margin: 0;" }),
          el("span", { class: "chip", text: info.category }),
        ]),
        el("div", { class: "toolbar" }, [
          el("button", {
            type: "button",
            class: "btn btn-secondary btn-sm",
            onClick: () => handleRenameTemplate(root, info.category, info.name),
          }, ["✏️ Rename"]),
          el("button", {
            type: "button",
            class: "btn btn-danger btn-sm",
            onClick: () => handleDeleteTemplate(root, info.category, info.name),
          }, ["🗑️ Delete"]),
        ]),
      ]),
      el("hr"),
      el("div", { class: "grid grid-2" }, [
        el("div", { class: "card stack" }, [
          el("h3", { text: "Template Geometry & Placement" }),
          el("div", { class: "grid grid-2" }, [
            el("div", { class: "field" }, [
              el("label", { class: "field-label", text: "Insertion X" }),
              insXInput,
            ]),
            el("div", { class: "field" }, [
              el("label", { class: "field-label", text: "Insertion Y" }),
              insYInput,
            ]),
            el("div", { class: "field" }, [
              el("label", { class: "field-label", text: "Offset X" }),
              offXInput,
            ]),
            el("div", { class: "field" }, [
              el("label", { class: "field-label", text: "Offset Y" }),
              offYInput,
            ]),
          ]),
          el("div", { class: "row-end" }, [
            el("button", {
              type: "button",
              class: "btn btn-primary btn-sm",
              onClick: async (e) => {
                await withBusy(e.target, "Saving\u2026", async () => {
                  try {
                    await api.saveTemplateInfo(info.category, info.name, {
                      insertion_point: [parseFloat(insX) || 0, parseFloat(insY) || 0],
                      offset: [parseFloat(offX) || 0, parseFloat(offY) || 0],
                    });
                    toast.success("Geometry settings saved.");
                  } catch (err) {
                    toast.error(`Save failed: ${err.message}`);
                  }
                });
              },
            }, ["💾 Save Geometry Settings"]),
          ]),
        ]),
        el("div", { class: "card stack" }, [
          el("h3", { text: "Drawing Block Inspection" }),
          el("p", { class: "muted", text: `${blocksCount} embedded block INSERT instances found in drawing.` }),
          blocksCount > 0
            ? el("div", { style: "max-height: 180px; overflow-y: auto;" }, [
                el("table", { class: "table" }, [
                  el("thead", {}, [
                    el("tr", {}, [
                      el("th", { text: "Block Name" }),
                      el("th", { text: "Insert Point" }),
                      el("th", { text: "Attributes" }),
                    ]),
                  ]),
                  el("tbody", {}, info.blocks.map((blk) =>
                    el("tr", {}, [
                      el("td", { text: blk.name }),
                      el("td", { text: blk.insert_pt ? `${blk.insert_pt[0]}, ${blk.insert_pt[1]}` : "0, 0" }),
                      el("td", { text: blk.attributes ? blk.attributes.map((a) => a.tag).join(", ") : "-" }),
                    ])
                  )),
                ]),
              ])
            : null,
        ]),
      ]),
      el("hr"),
      el("div", { class: "stack" }, [
        el("div", { class: "row-between" }, [
          el("div", {}, [
            el("h3", { text: "Template I/O Signals Configuration", style: "margin: 0;" }),
            el("p", { class: "muted", text: "Configure hardware I/O signals linked directly to this drawing template (automatically sorted by Direction & Signal Type)." }),
          ]),
          el("div", { class: "toolbar" }, [
            el("button", {
              type: "button",
              class: "btn btn-secondary btn-sm",
              onClick: () => {
                sortIoItems(currentIos);
                renderIosTable();
                toast.success("Sorted I/O signals by Direction & Signal Type.");
              },
            }, ["⚡ Auto Sort"]),
            el("button", {
              type: "button",
              class: "btn btn-secondary btn-sm",
              onClick: () => {
                const activeF = IO_CATEGORY_FILTERS.find((f) => f.key === currentIoCategoryFilter);
                const defaultDir = activeF?.direction || "Input";
                const defaultSig = activeF?.signal_type || "Digital";

                currentIos.push({
                  name: `signal_${currentIos.length + 1}`,
                  description: "",
                  direction: defaultDir,
                  signal_type: defaultSig,
                  io_type: "",
                  ladder_type: "",
                  ladder_template: "",
                });
                sortIoItems(currentIos);
                renderIosTable();
              },
            }, ["➕ Add I/O Row"]),
            el("button", {
              type: "button",
              class: "btn btn-primary btn-sm",
              onClick: async (e) => {
                await withBusy(e.target, "Saving\u2026", async () => {
                  try {
                    sortIoItems(currentIos);
                    await api.saveTemplateIos(info.category, info.name, currentIos);
                    toast.success("Template I/O signals saved successfully.");
                  } catch (err) {
                    toast.error(`Save failed: ${err.message}`);
                  }
                });
              },
            }, ["💾 Save Template I/Os"]),
          ]),
        ]),
        iosTableContainer,
      ]),
    ])
  );
}

async function handleRenameTemplate(root, category, oldName) {
  const newName = prompt(`Enter new template name for '${oldName}':`, oldName);
  if (!newName || newName === oldName) return;
  try {
    const res = await api.renameTemplate(category, oldName, newName.trim());
    toast.success(res.message || "Template renamed.");
    await loadSource(root, activeSource);
  } catch (err) {
    toast.error(`Rename failed: ${err.message}`);
  }
}

async function handleDeleteTemplate(root, category, name) {
  if (!confirm(`Are you sure you want to delete template '${name}' from ${category}?`)) return;
  try {
    const res = await api.deleteTemplate(category, name);
    toast.success(res.message || "Template deleted.");
    await loadSource(root, activeSource);
  } catch (err) {
    toast.error(`Delete failed: ${err.message}`);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Circuits Configuration (Add, Edit, Delete)
// ─────────────────────────────────────────────────────────────────────────────

function renderCircuitsView(root, circuits) {
  const columns = [
    { label: "Name", key: "name" },
    { label: "Circuit #", key: "circuit_number" },
    { label: "Description", key: "description" },
    { label: "Templates", render: (r) => formatCell(r.templates) },
    { label: "Valves", render: (r) => formatCell(r.valves) },
    { label: "I/Os Count", render: (r) => (Array.isArray(r.circuit_ios) ? String(r.circuit_ios.length) : "0") },
    {
      label: "Actions",
      render: (circuit) =>
        el("div", { class: "toolbar" }, [
          el("button", {
            type: "button",
            class: "btn btn-secondary btn-sm",
            onClick: (e) => {
              e.stopPropagation();
              openCircuitModal(root, circuit);
            },
          }, ["✏️ Edit"]),
          el("button", {
            type: "button",
            class: "btn btn-danger btn-sm",
            onClick: (e) => {
              e.stopPropagation();
              handleDeleteCircuit(root, circuit.name);
            },
          }, ["🗑️"]),
        ]),
    },
  ];

  return el("div", { class: "stack" }, [
    el("div", { class: "row-between" }, [
      el("p", { class: "muted", text: `${circuits.length} circuit definitions in library.` }),
      el("button", {
        type: "button",
        class: "btn btn-primary",
        onClick: () => openCircuitModal(root),
      }, ["➕ Add Circuit"]),
    ]),
    dataTable({ columns, rows: circuits, empty: "No circuits defined." }),
  ]);
}

async function handleDeleteCircuit(root, name) {
  if (!confirm(`Delete circuit '${name}'?`)) return;
  try {
    await api.deleteCircuit(name);
    toast.success(`Circuit '${name}' deleted.`);
    await loadSource(root, activeSource);
  } catch (err) {
    toast.error(`Delete failed: ${err.message}`);
  }
}

async function openCircuitModal(root, existingCircuit = null) {
  const isEdit = Boolean(existingCircuit);
  let circuitData = existingCircuit
    ? JSON.parse(JSON.stringify(existingCircuit))
    : {
        name: "",
        circuit_number: "",
        description: "",
        templates: [],
        valves: [],
        circuit_ios: [],
      };

  circuitData.circuit_ios = sortIoItems(circuitData.circuit_ios || []);

  // Ensure drawing templates, valve types, and I/O types are available for pickers
  if (!cachedTemplates) {
    try { cachedTemplates = await api.templates(); } catch { cachedTemplates = {}; }
  }
  if (!cachedValveTypes) {
    try { cachedValveTypes = await api.valveTypes(); } catch { cachedValveTypes = []; }
  }
  if (!cachedIoTypes) {
    try { cachedIoTypes = await api.ioTypes(); } catch { cachedIoTypes = []; }
  }

  const allAvailableTemplates = Object.values(cachedTemplates || {}).flat();

  const nameInput = el("input", { value: circuitData.name || "", required: true, disabled: isEdit });
  const numberInput = el("input", { value: circuitData.circuit_number || "" });
  const descInput = el("input", { value: circuitData.description || "" });

  const templatesContainer = el("div", { class: "chips" });
  const valvesContainer = el("div", { class: "chips" });
  const iosContainer = el("div", { class: "stack" });

  function renderTemplatesList() {
    templatesContainer.replaceChildren(
      ...circuitData.templates.map((tmpl, idx) =>
        el("span", { class: "chip-editable" }, [
          el("span", { text: typeof tmpl === "object" ? tmpl.name : tmpl }),
          el("button", {
            type: "button",
            class: "chip-btn",
            onClick: () => {
              circuitData.templates.splice(idx, 1);
              renderTemplatesList();
            },
          }, ["❌"]),
        ])
      )
    );
  }

  function renderValvesList() {
    valvesContainer.replaceChildren(
      ...circuitData.valves.map((v, idx) =>
        el("span", { class: "chip-editable" }, [
          el("span", { text: typeof v === "object" ? v.name : v }),
          el("button", {
            type: "button",
            class: "chip-btn",
            onClick: () => {
              circuitData.valves.splice(idx, 1);
              renderValvesList();
            },
          }, ["❌"]),
        ])
      )
    );
  }

  function renderIosTable() {
    if (!circuitData.circuit_ios || circuitData.circuit_ios.length === 0) {
      iosContainer.replaceChildren(el("p", { class: "muted", text: "No I/O signals defined for this circuit." }));
      return;
    }

    const rows = circuitData.circuit_ios.map((io, idx) => {
      const nameIn = el("input", { class: "table-input", value: io.name || "", onChange: (e) => (io.name = e.target.value) });
      const descIn = el("input", { class: "table-input", value: io.description || "", onChange: (e) => (io.description = e.target.value) });
      const dirIn = el("select", {
        class: "table-input",
        onChange: (e) => {
          io.direction = e.target.value;
          sortIoItems(circuitData.circuit_ios);
          renderIosTable();
        },
      }, [
        el("option", { value: "Input", selected: io.direction === "Input" }, ["Input"]),
        el("option", { value: "Output", selected: io.direction === "Output" }, ["Output"]),
      ]);
      const sigIn = el("select", {
        class: "table-input",
        onChange: (e) => {
          io.signal_type = e.target.value;
          sortIoItems(circuitData.circuit_ios);
          renderIosTable();
        },
      }, [
        el("option", { value: "Digital", selected: io.signal_type === "Digital" }, ["Digital"]),
        el("option", { value: "Analog", selected: io.signal_type === "Analog" }, ["Analog"]),
      ]);

      // Filter I/O Types library dropdown options by matching direction & signal_type
      const matchingIoTypeDefs = (Array.isArray(cachedIoTypes) ? cachedIoTypes : []).filter((item) => {
        if (typeof item !== "object") return true;
        const matchDir = !io.direction || !item.direction || item.direction === io.direction;
        const matchSig = !io.signal_type || !item.signal_category || item.signal_category === io.signal_type;
        return matchDir && matchSig;
      });
      const matchingTypeNames = matchingIoTypeDefs
        .map((item) => (typeof item === "object" ? item.name : item))
        .filter(Boolean);

      const currentIoType = io.io_type || "";
      const ioTypeOptions = [
        el("option", { value: "", selected: !currentIoType }, ["-- Select I/O Type --"]),
        ...matchingTypeNames.map((tName) =>
          el("option", { value: tName, selected: String(tName) === String(currentIoType) }, [tName])
        ),
      ];
      if (currentIoType && !matchingTypeNames.includes(currentIoType)) {
        ioTypeOptions.push(el("option", { value: currentIoType, selected: true }, [currentIoType]));
      }

      const ioTypeSelect = el(
        "select",
        {
          class: "table-input",
          onChange: (e) => {
            io.io_type = e.target.value;
            const foundDef = cachedIoTypes?.find(
              (item) => typeof item === "object" && item.name === e.target.value
            );
            if (foundDef) {
              if (foundDef.direction) io.direction = foundDef.direction;
              if (foundDef.signal_category) io.signal_type = foundDef.signal_category;
            }
            sortIoItems(circuitData.circuit_ios);
            renderIosTable();
          },
        },
        ioTypeOptions
      );

      return el("tr", {}, [
        el("td", {}, [nameIn]),
        el("td", {}, [descIn]),
        el("td", {}, [dirIn]),
        el("td", {}, [sigIn]),
        el("td", {}, [ioTypeSelect]),
        el("td", {}, [
          el("button", {
            type: "button",
            class: "btn btn-danger btn-sm",
            onClick: () => {
              circuitData.circuit_ios.splice(idx, 1);
              renderIosTable();
            },
          }, ["🗑️"]),
        ]),
      ]);
    });

    iosContainer.replaceChildren(
      el("table", { class: "table" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: "Name" }),
            el("th", { text: "Description" }),
            el("th", { text: "Direction" }),
            el("th", { text: "Signal" }),
            el("th", { text: "IO Type" }),
            el("th", { text: "Action" }),
          ]),
        ]),
        el("tbody", {}, rows),
      ])
    );
  }

  renderTemplatesList();
  renderValvesList();
  renderIosTable();

  // Template select dropdown
  const tmplSelect = el("select", {}, [
    el("option", { value: "" }, ["-- Pick a template --"]),
    ...allAvailableTemplates.map((t) => el("option", { value: t }, [t])),
  ]);
  const addTmplBtn = el("button", {
    type: "button",
    class: "btn btn-secondary btn-sm",
    onClick: () => {
      const val = tmplSelect.value;
      if (val && !circuitData.templates.includes(val)) {
        circuitData.templates.push(val);
        renderTemplatesList();
        tmplSelect.value = "";
      }
    },
  }, ["+ Add Template"]);

  // Valve type select dropdown
  const valveSelect = el("select", {}, [
    el("option", { value: "" }, ["-- Pick a valve type --"]),
    ...(cachedValveTypes || []).map((v) => el("option", { value: v }, [v])),
  ]);
  const addValveBtn = el("button", {
    type: "button",
    class: "btn btn-secondary btn-sm",
    onClick: () => {
      const val = valveSelect.value;
      if (val && !circuitData.valves.includes(val)) {
        circuitData.valves.push(val);
        renderValvesList();
        valveSelect.value = "";
      }
    },
  }, ["+ Add Valve"]);

  // Modal structure
  const modalContent = el("div", { class: "modal modal-lg stack" }, [
    el("h3", { class: "modal-title", text: isEdit ? `Edit Circuit: ${circuitData.name}` : "Create New Circuit" }),
    el("div", { class: "grid grid-2" }, [
      el("div", { class: "field" }, [
        el("label", { class: "field-label", text: "Circuit Name" }),
        nameInput,
      ]),
      el("div", { class: "field" }, [
        el("label", { class: "field-label", text: "Circuit Number" }),
        numberInput,
      ]),
    ]),
    el("div", { class: "field" }, [
      el("label", { class: "field-label", text: "Description" }),
      descInput,
    ]),
    el("hr"),
    el("div", { class: "field" }, [
      el("label", { class: "field-label", text: "Assigned Templates" }),
      el("div", { class: "toolbar" }, [tmplSelect, addTmplBtn]),
      templatesContainer,
    ]),
    el("div", { class: "field" }, [
      el("label", { class: "field-label", text: "Assigned Valves" }),
      el("div", { class: "toolbar" }, [valveSelect, addValveBtn]),
      valvesContainer,
    ]),
    el("hr"),
    el("div", { class: "field" }, [
      el("div", { class: "row-between" }, [
        el("label", { class: "field-label", text: "Circuit I/O Signals" }),
        el("button", {
          type: "button",
          class: "btn btn-secondary btn-sm",
          onClick: () => {
            if (!circuitData.circuit_ios) circuitData.circuit_ios = [];
            circuitData.circuit_ios.push({
              name: `signal_${circuitData.circuit_ios.length + 1}`,
              description: "",
              direction: "Input",
              signal_type: "Digital",
              io_type: "",
              ladder_type: "",
              ladder_template: "",
            });
            renderIosTable();
          },
        }, ["➕ Add I/O Row"]),
      ]),
      iosContainer,
    ]),
    el("div", { class: "modal-actions" }, [
      el("button", {
        type: "button",
        class: "btn btn-secondary",
        onClick: () => backdrop.remove(),
      }, ["Cancel"]),
      el("button", {
        type: "button",
        class: "btn btn-primary",
        onClick: async (e) => {
          const btn = e.target;
          circuitData.name = nameInput.value.trim();
          circuitData.circuit_number = numberInput.value.trim();
          circuitData.description = descInput.value.trim();

          if (!circuitData.name) {
            toast.error("Circuit name is required.");
            return;
          }

          await withBusy(btn, "Saving\u2026", async () => {
            try {
              if (isEdit) {
                await api.updateCircuit(existingCircuit.name, circuitData);
                toast.success(`Circuit '${circuitData.name}' updated.`);
              } else {
                await api.createCircuit(circuitData);
                toast.success(`Circuit '${circuitData.name}' created.`);
              }
              backdrop.remove();
              await loadSource(root, activeSource);
            } catch (err) {
              toast.error(`Save failed: ${err.message}`);
            }
          });
        },
      }, [isEdit ? "Save Changes" : "Create Circuit"]),
    ]),
  ]);

  const backdrop = el("div", { class: "modal-backdrop" }, [modalContent]);
  document.body.append(backdrop);
}

// ─────────────────────────────────────────────────────────────────────────────
// Other Configuration Editors (List of primitive strings, List of objects, Dict)
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// I/O Types Configuration (master list + per-type config panel)
// ─────────────────────────────────────────────────────────────────────────────

let selectedIoTypeName = null;
let ioTypeSearchQuery = "";
let ioTypeDirectionFilter = "all";

const IO_TYPE_DIRECTION_FILTERS = [
  { key: "all", label: "All" },
  { key: "Input", label: "Inputs" },
  { key: "Output", label: "Outputs" },
];

/** Templates are only needed by this view, so fetch them on demand. */
async function ensureTemplates() {
  if (!cachedTemplates) {
    try {
      cachedTemplates = await api.templates();
    } catch {
      cachedTemplates = {};
    }
  }
  return cachedTemplates;
}

function templateSelect(category, value, onChange, placeholder = "-- none --") {
  const names = (cachedTemplates && cachedTemplates[category]) || [];
  const options = [
    el("option", { value: "", selected: !value }, [placeholder]),
    ...names.map((name) =>
      el("option", { value: name, selected: name === value }, [name])
    ),
  ];
  // Keep a value that points at a file that is no longer on disk visible.
  if (value && !names.includes(value)) {
    options.push(el("option", { value, selected: true }, [`${value} (missing)`]));
  }
  return el("select", { class: "table-input", onChange: (e) => onChange(e.target.value) }, options);
}

function renderIoTypesView(root, ioTypes, source) {
  const working = JSON.parse(JSON.stringify(ioTypes));

  const tableContainer = el("div", { id: "ioTypesTableContainer" });
  const detailContainer = el("div", { class: "stack" });

  const searchInput = el("input", {
    type: "search",
    placeholder: "Search name, description or template\u2026",
    value: ioTypeSearchQuery,
    style: "max-width: 280px;",
    onInput: (e) => {
      ioTypeSearchQuery = e.target.value.toLowerCase().trim();
      update();
    },
  });

  function filtered() {
    return working.filter((item) => {
      const matchesDir =
        ioTypeDirectionFilter === "all" || item.direction === ioTypeDirectionFilter;
      const haystack = [item.name, item.description, item.io_template, item.ladder_type]
        .join(" ")
        .toLowerCase();
      return matchesDir && (!ioTypeSearchQuery || haystack.includes(ioTypeSearchQuery));
    });
  }

  async function persist(button, message) {
    await withBusy(button, "Saving\u2026", async () => {
      try {
        await source.save(working);
        cachedIoTypes = JSON.parse(JSON.stringify(working));
        toast.success(message);
      } catch (err) {
        toast.error(`Save failed: ${err.message}`);
      }
    });
  }

  function selected() {
    return working.find((item) => item.name === selectedIoTypeName) || null;
  }

  function update() {
    const rows = filtered();
    if (rows.length && !rows.some((item) => item.name === selectedIoTypeName)) {
      selectedIoTypeName = rows[0].name;
    }

    tableContainer.replaceChildren(
      dataTable({
        columns: [
          {
            label: "Name",
            render: (row) => el("span", { style: "font-weight: 600;", text: row.name || "" }),
          },
          { label: "Direction", render: (row) => el("span", { class: "chip", text: row.direction || "-" }) },
          { label: "Signal", render: (row) => row.signal_category || "-" },
          { label: "I/O Template", render: (row) => row.io_template || "-" },
          { label: "Shared", render: (row) => (row.shared ? row.shared_template || "yes" : "-") },
          { label: "Ladder", render: (row) => row.ladder_type || "-" },
          { label: "Ladder Component", render: (row) => row.ladder_component_template || "-" },
        ],
        rows,
        onRowClick: (row) => {
          selectedIoTypeName = row.name;
          update();
        },
        isActive: (row) => row.name === selectedIoTypeName,
        empty: "No I/O types match the filter.",
      })
    );

    const current = selected();
    if (current) renderIoTypeDetail(detailContainer, current, working, update, persist);
    else detailContainer.replaceChildren(el("p", { class: "muted", text: "Select an I/O type to configure it." }));
  }

  const container = el("div", { class: "stack" }, [
    el("div", { class: "row-between wrap" }, [
      el("div", { class: "sub-tabs" }, IO_TYPE_DIRECTION_FILTERS.map((f) =>
        el("button", {
          type: "button",
          class: `tab ${ioTypeDirectionFilter === f.key ? "is-active" : ""}`,
          dataset: { key: f.key },
          onClick: (e) => {
            ioTypeDirectionFilter = f.key;
            for (const tab of container.querySelectorAll(".sub-tabs .tab")) {
              tab.classList.toggle("is-active", tab.dataset.key === f.key);
            }
            update();
          },
        }, [f.label])
      )),
      el("div", { class: "toolbar", style: "align-items: center;" }, [
        searchInput,
        el("button", {
          type: "button",
          class: "btn btn-primary btn-sm",
          onClick: () => {
            let name = "new_io_type";
            let suffix = 1;
            while (working.some((item) => item.name === name)) name = `new_io_type_${++suffix}`;
            working.push({
              name,
              description: "",
              signal_category: "Digital",
              direction: ioTypeDirectionFilter === "Output" ? "Output" : "Input",
              io_template: "",
              shared: false,
              shared_template: "",
              ladder_type: "",
              ladder_component_template: "",
            });
            selectedIoTypeName = name;
            update();
          },
        }, ["\u2795 Add I/O Type"]),
        el("button", {
          type: "button",
          class: "btn btn-primary btn-sm",
          onClick: (e) => persist(e.target, "I/O types library saved."),
        }, ["\uD83D\uDCBE Save Library"]),
      ]),
    ]),
    tableContainer,
    el("hr"),
    detailContainer,
  ]);

  ensureTemplates().then(update);
  update();
  return container;
}

function renderIoTypeDetail(container, item, working, update, persist) {
  const field = (label, control, hint) =>
    el("div", { class: "field" }, [
      el("label", { class: "field-label", text: label }),
      control,
      hint ? el("p", { class: "muted", text: hint }) : null,
    ]);

  const nameInput = el("input", {
    class: "table-input",
    value: item.name || "",
    onChange: (e) => {
      const next = e.target.value.trim();
      if (!next) {
        toast.error("Name is required.");
        e.target.value = item.name;
        return;
      }
      if (working.some((other) => other !== item && other.name === next)) {
        toast.error(`An I/O type named '${next}' already exists.`);
        e.target.value = item.name;
        return;
      }
      item.name = next;
      selectedIoTypeName = next;
      update();
    },
  });

  const sharedToggle = el("input", {
    type: "checkbox",
    checked: !!item.shared,
    onChange: (e) => {
      item.shared = e.target.checked;
      if (!item.shared) item.shared_template = "";
      update();
    },
  });

  container.replaceChildren(
    el("div", { class: "card stack" }, [
      el("div", { class: "row-between wrap" }, [
        el("h3", { text: `I/O Type: ${item.name}`, style: "margin: 0;" }),
        el("div", { class: "toolbar" }, [
          el("button", {
            type: "button",
            class: "btn btn-danger btn-sm",
            onClick: async (e) => {
              const removed = item.name;
              const ok = await confirmAction(`Delete I/O type '${removed}'?`, {
                confirmLabel: "Delete",
              });
              if (!ok) return;
              working.splice(working.indexOf(item), 1);
              await persist(e.target, `I/O type '${removed}' deleted.`);
              selectedIoTypeName = null;
              update();
            },
          }, ["\uD83D\uDDD1\uFE0F Delete"]),
        ]),
      ]),
      el("hr"),
      el("div", { class: "grid grid-2" }, [
        el("div", { class: "card stack" }, [
          el("h3", { text: "Identity" }),
          field("Name", nameInput),
          field(
            "Description",
            el("input", {
              class: "table-input",
              value: item.description || "",
              onChange: (e) => (item.description = e.target.value),
            })
          ),
          field(
            "Direction",
            el("select", {
              class: "table-input",
              onChange: (e) => {
                item.direction = e.target.value;
                update();
              },
            }, ["Input", "Output"].map((value) =>
              el("option", { value, selected: item.direction === value }, [value])
            ))
          ),
          field(
            "Signal Category",
            el("select", {
              class: "table-input",
              onChange: (e) => {
                item.signal_category = e.target.value;
                update();
              },
            }, ["Digital", "Analog"].map((value) =>
              el("option", { value, selected: item.signal_category === value }, [value])
            ))
          ),
        ]),
        el("div", { class: "card stack" }, [
          el("h3", { text: "Controller Page" }),
          field(
            "I/O Template",
            templateSelect("io", item.io_template || "", (value) => {
              item.io_template = value;
              update();
            }),
            "Drawn at the module slot on the controller (C) page."
          ),
          el("div", { class: "field" }, [
            el("label", { class: "field-label" }, [
              sharedToggle,
              el("span", { text: " Shares a common terminal" }),
            ]),
          ]),
          field(
            "Shared Template",
            templateSelect("io", item.shared_template || "", (value) => {
              item.shared_template = value;
              update();
            }),
            item.shared
              ? "Used for every slot after the first shared input."
              : "Only applies when 'shares a common terminal' is on."
          ),
        ]),
        el("div", { class: "card stack" }, [
          el("h3", { text: "Ladder Page" }),
          field(
            "Ladder Type",
            templateSelect("ladder", item.ladder_type || "", (value) => {
              item.ladder_type = value;
              update();
            }, "-- no ladder page --"),
            "The ladder (L) page this type's components are drawn on. Leave empty to exclude it from ladder generation."
          ),
          field(
            "Ladder Component Template",
            templateSelect("ladder_component", item.ladder_component_template || "", (value) => {
              item.ladder_component_template = value;
              update();
            }),
            "The rung artwork placed on that ladder page."
          ),
        ]),
      ]),
      el("div", { class: "row-end" }, [
        el("button", {
          type: "button",
          class: "btn btn-primary btn-sm",
          onClick: (e) => persist(e.target, `I/O type '${item.name}' saved.`),
        }, ["\uD83D\uDCBE Save Library"]),
      ]),
    ])
  );
}

function renderStringListView(root, list, source) {
  return el("div", { class: "stack" }, [
    el("div", { class: "row-between" }, [
      el("p", { class: "muted", text: `${list.length} items` }),
      source.save
        ? el("button", {
            type: "button",
            class: "btn btn-primary btn-sm",
            onClick: () => openStringListModal(root, list, source),
          }, ["✏️ Edit List"])
        : null,
    ]),
    el("div", { class: "chips" }, list.map((item) =>
      el("span", { class: "chip", text: item })
    )),
  ]);
}

function openStringListModal(root, list, source) {
  const textarea = el("textarea", {
    rows: 10,
    style: "width: 100%; font-family: monospace;",
    text: list.join("\n"),
  });

  const backdrop = el("div", { class: "modal-backdrop" }, [
    el("div", { class: "modal stack" }, [
      el("h3", { class: "modal-title", text: `Edit ${source.label}` }),
      el("p", { class: "muted", text: "Enter one item per line." }),
      textarea,
      el("div", { class: "modal-actions" }, [
        el("button", {
          type: "button",
          class: "btn btn-secondary",
          onClick: () => backdrop.remove(),
        }, ["Cancel"]),
        el("button", {
          type: "button",
          class: "btn btn-primary",
          onClick: async (e) => {
            const lines = textarea.value.split("\n").map((l) => l.trim()).filter(Boolean);
            await withBusy(e.target, "Saving\u2026", async () => {
              try {
                await source.save(lines);
                toast.success(`${source.label} updated.`);
                backdrop.remove();
                await loadSource(root, activeSource);
              } catch (err) {
                toast.error(`Save failed: ${err.message}`);
              }
            });
          },
        }, ["Save"]),
      ]),
    ]),
  ]);

  document.body.append(backdrop);
}

function renderObjectListView(root, rows, source) {
  const columns = [...new Set(rows.flatMap((r) => Object.keys(r)))].map((key) => ({
    label: key,
    render: (r) => formatCell(r[key]),
  }));

  return el("div", { class: "stack" }, [
    el("div", { class: "row-between" }, [
      el("p", { class: "muted", text: `${rows.length} entries` }),
      source.save
        ? el("button", {
            type: "button",
            class: "btn btn-primary btn-sm",
            onClick: () => openJsonEditorModal(root, rows, source),
          }, ["✏️ Edit Configuration"])
        : null,
    ]),
    dataTable({ columns, rows }),
  ]);
}

function renderDictView(root, dict, source) {
  const entries = Object.entries(dict);
  return el("div", { class: "stack" }, [
    el("div", { class: "row-between" }, [
      el("p", { class: "muted", text: `${entries.length} keys` }),
      source.save
        ? el("button", {
            type: "button",
            class: "btn btn-primary btn-sm",
            onClick: () => openJsonEditorModal(root, dict, source),
          }, ["✏️ Edit Configuration"])
        : null,
    ]),
    dataTable({
      columns: [
        { label: "Key", render: (r) => r[0] },
        { label: "Value", render: (r) => formatCell(r[1]) },
      ],
      rows: entries,
    }),
  ]);
}

function openJsonEditorModal(root, data, source) {
  const textarea = el("textarea", {
    rows: 15,
    style: "width: 100%; font-family: monospace; font-size: 13px;",
    text: JSON.stringify(data, null, 2),
  });

  const backdrop = el("div", { class: "modal-backdrop" }, [
    el("div", { class: "modal modal-lg stack" }, [
      el("h3", { class: "modal-title", text: `Edit ${source.label}` }),
      el("p", { class: "muted", text: "Edit configuration JSON directly." }),
      textarea,
      el("div", { class: "modal-actions" }, [
        el("button", {
          type: "button",
          class: "btn btn-secondary",
          onClick: () => backdrop.remove(),
        }, ["Cancel"]),
        el("button", {
          type: "button",
          class: "btn btn-primary",
          onClick: async (e) => {
            let parsed;
            try {
              parsed = JSON.parse(textarea.value);
            } catch (err) {
              toast.error(`Invalid JSON: ${err.message}`);
              return;
            }
            await withBusy(e.target, "Saving\u2026", async () => {
              try {
                await source.save(parsed);
                toast.success(`${source.label} saved.`);
                backdrop.remove();
                await loadSource(root, activeSource);
              } catch (err) {
                toast.error(`Save failed: ${err.message}`);
              }
            });
          },
        }, ["Save Changes"]),
      ]),
    ]),
  ]);

  document.body.append(backdrop);
}

function formatCell(value) {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.length ? `[${value.length}] ${JSON.stringify(value)}` : "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
