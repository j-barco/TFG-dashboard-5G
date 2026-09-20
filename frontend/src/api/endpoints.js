import api from "./client";

export const auth = {
  status: () => api.get("/auth/status"),
  login: (username, password) => {
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);
    return api.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
  },
};

export const monitoring = {
  coreStatus: () => api.get("/status/core"),
  gnbStatus: () => api.get("/status/gnb"),
  ueStatus: () => api.get("/status/ues"),
  throughputHistory: () => api.get("/status/throughput"),
};

export const gnb = {
  getConfig: () => api.get("/gnb/config"),
  getHardware: () => api.get("/gnb/hardware"),
  getPresets: () => api.get("/gnb/presets"),
  getLogs: (tail = 100, mode = "tail") => api.get("/gnb/logs", { params: { tail, mode } }),
  searchLogs: (search) => api.get("/gnb/logs", { params: { search } }),
  downloadLogs: () => api.get("/gnb/logs/download", { responseType: "blob" }),
  getCustomPresets: () => api.get("/gnb/custom-presets"),
  saveCustomPreset: (name, config) => api.post("/gnb/custom-presets", { name, config }),
  deleteCustomPreset: (name) => api.delete(`/gnb/custom-presets/${encodeURIComponent(name)}`),
  setCustomPresetsPath: (path) => api.put("/gnb/custom-presets/path", { path }),
  updateConfig: (config) => api.put("/gnb/config", config),
  start: () => api.post("/gnb/start"),
  stop: () => api.post("/gnb/stop"),
};

export const coreLifecycle = {
  up: () => api.post("/core/up"),
  down: () => api.post("/core/down"),
};

export const coreServices = {
  start: (nf) => api.post(`/core/services/${nf}/start`),
  stop: (nf) => api.post(`/core/services/${nf}/stop`),
  restart: (nf) => api.post(`/core/services/${nf}/restart`),
  logs: (nf, tail = 100) => api.get(`/core/services/${nf}/logs`, { params: { tail } }),
  searchLogs: (nf, q) => api.get(`/core/services/${nf}/logs/search`, { params: { q } }),
  downloadLogs: (nf) =>
    api.get(`/core/services/${nf}/logs/download`, { responseType: "blob" }),
};

export const subscribers = {
  list: () => api.get("/subscribers"),
  create: (data) => api.post("/subscribers", data),
  remove: (imsi) => api.delete(`/subscribers/${imsi}`),
};
