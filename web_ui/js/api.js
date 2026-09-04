/** The only module that knows API URLs. Everything else calls these helpers. */

const BASE = "/api";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, { method = "GET", body, query } = {}) {
  const url = new URL(BASE + path, window.location.origin);
  for (const [key, value] of Object.entries(query || {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const response = await fetch(url, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) throw new ApiError(await errorMessage(response), response.status);
  if (response.status === 204) return null;

  const type = response.headers.get("content-type") || "";
  if (type.includes("application/zip")) return response.blob();
  return response.json();
}

async function errorMessage(response) {
  try {
    const payload = await response.json();
    if (typeof payload?.error === "string") return payload.error;
    if (Array.isArray(payload?.detail)) {
      return payload.detail.map((d) => `${(d.loc || []).join(".")}: ${d.msg}`).join("; ");
    }
    if (payload?.detail) return String(payload.detail);
  } catch {
    /* fall through to status text */
  }
  return `${response.status} ${response.statusText}`;
}

async function uploadFile(path, formData) {
  const url = new URL(BASE + path, window.location.origin);
  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) throw new ApiError(await errorMessage(response), response.status);
  return response.json();
}

export const api = {
  health: () => request("/health"),

  templates: () => request("/templates"),
  templatesByCategory: (cat) => request(`/templates/${cat}`),
  uploadTemplate: (cat, formData) => uploadFile(`/templates/${cat}/upload`, formData),
  deleteTemplate: (cat, name) =>
    request(`/templates/${cat}/${encodeURIComponent(name)}`, { method: "DELETE" }),
  renameTemplate: (cat, name, newName) =>
    request(`/templates/${cat}/${encodeURIComponent(name)}/rename`, {
      method: "POST",
      body: { new_name: newName },
    }),
  templateInfo: (cat, name) =>
    request(`/templates/${cat}/${encodeURIComponent(name)}/info`),
  saveTemplateInfo: (cat, name, data) =>
    request(`/templates/${cat}/${encodeURIComponent(name)}/info`, { method: "PUT", body: data }),
  templateIos: (cat, name) =>
    request(`/templates/${cat}/${encodeURIComponent(name)}/ios`),
  saveTemplateIos: (cat, name, ios) =>
    request(`/templates/${cat}/${encodeURIComponent(name)}/ios`, { method: "PUT", body: ios }),

  circuits: () => request("/circuits"),
  createCircuit: (data) => request("/circuits", { method: "POST", body: data }),
  updateCircuit: (name, data) =>
    request(`/circuits/${encodeURIComponent(name)}`, { method: "PUT", body: data }),
  deleteCircuit: (name) =>
    request(`/circuits/${encodeURIComponent(name)}`, { method: "DELETE" }),
  saveCircuits: (circuits) => request("/circuits", { method: "PUT", body: circuits }),

  modules: () => request("/modules"),
  saveModules: (data) => request("/modules", { method: "PUT", body: data }),
  controllers: () => request("/controllers"),
  machineTypes: () => request("/machine-types"),
  machineOrder: (machineType) =>
    request(`/machine-types/${encodeURIComponent(machineType)}/order`),
  moduleIoValues: () => request("/module-io-values"),
  saveModuleIoValues: (data) => request("/module-io-values", { method: "PUT", body: data }),
  ioTypes: () => request("/io-types"),
  saveIoTypes: (data) => request("/io-types", { method: "PUT", body: data }),
  ladderTypes: () => request("/ladder-types"),
  saveLadderTypes: (data) => request("/ladder-types", { method: "PUT", body: data }),
  rules: () => request("/rules"),
  saveRules: (data) => request("/rules", { method: "PUT", body: data }),
  valveTypes: () => request("/valve-types"),
  saveValveTypes: (data) => request("/valve-types", { method: "PUT", body: data }),
  valveIos: () => request("/valve-ios"),
  saveValveIos: (data) => request("/valve-ios", { method: "PUT", body: data }),
  appConfig: () => request("/app-config"),
  saveAppConfig: (data) => request("/app-config", { method: "PUT", body: data }),

  workbook: {
    generatorFilters: (manufacturer) =>
      request("/workbook/generator-filters", { query: { manufacturer } }),
    circuits: (capacity, manufacturer, tension) =>
      request("/workbook/circuits", { query: { capacity, manufacturer, tension } }),
    compressors: () => request("/workbook/compressors"),
  },

  compressors: {
    list: () => request("/compressors"),
    create: (data) => request("/compressors", { method: "POST", body: data }),
    update: (id, data) => request(`/compressors/${id}`, { method: "PUT", body: data }),
    remove: (id) => request(`/compressors/${id}`, { method: "DELETE" }),
    syncWorkbook: () => request("/compressors/sync-workbook", { method: "POST", body: {} }),
    importAll: (compressors, mode) =>
      request("/compressors/import", { method: "POST", body: { compressors, mode } }),
    exportUrl: () => `${BASE}/compressors/export`,
  },

  projects: {
    list: () => request("/projects"),
    get: (id) => request(`/projects/${encodeURIComponent(id)}`),
    create: (data) => request("/projects", { method: "POST", body: data }),
    update: (id, data) => request(`/projects/${encodeURIComponent(id)}`, { method: "PUT", body: data }),
    remove: (id) => request(`/projects/${encodeURIComponent(id)}`, { method: "DELETE" }),
    import: (formData) => uploadFile("/projects/import", formData),
    exportUrl: (id) => `${BASE}/projects/${encodeURIComponent(id)}/export`,
  },

  ioPreview: (payload, controller, machineType) =>
    request("/io-preview", {
      method: "POST",
      body: payload,
      query: { controller, machine_type: machineType },
    }),

  generate: (payload, format, controller, machineType) =>
    request("/generate", {
      method: "POST",
      body: payload,
      query: { format, controller, machine_type: machineType },
    }),
};

export { ApiError };
