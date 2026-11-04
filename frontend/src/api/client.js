import axios from "axios";

const http = axios.create({ baseURL: "/api/v1", timeout: 120000 });
const TOKEN_KEY = "traffic_ai_token", USER_KEY = "traffic_ai_user";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const getUsername = () => localStorage.getItem(USER_KEY);
export function saveSession(token, username) { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(USER_KEY, username); }
export function clearSession() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }
/** Tell the app to show the login page (token expired or rejected). */
export function forceLogout() { clearSession(); window.dispatchEvent(new Event("auth:logout")); }

http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
http.interceptors.response.use((r) => r, (error) => {
  if (error.response?.status === 401 && getToken()) forceLogout();  // a wrong password at login has no token, so it is not affected
  return Promise.reject(error);
});

/** Turn an Axios error into a message a person can act on. */
export function errorMessage(error) {
  if (error.response) {
    const detail = error.response.data?.detail;
    if (Array.isArray(detail)) return detail.map((d) => `${d.loc?.slice(-1)}: ${d.msg}`).join("; ");
    return typeof detail === "string" ? detail : `Request failed (${error.response.status})`;
  }
  return "Cannot reach the API. Is the FastAPI server running on port 8000?";
}

const get = (url, params) => http.get(url, { params }).then((r) => r.data);
const post = (url, body) => http.post(url, body ?? {}).then((r) => r.data);

export const api = {
  login: (b) => post("/auth/login", b), register: (b) => post("/auth/register", b), health: () => get("/health"),
  dataset: () => get("/dataset"), peak: () => get("/peak-analysis"), dashboardSim: () => get("/dashboard/simulated"),
  predict: (params) => get("/predict", params), modelComparison: (horizon) => get("/model-comparison", { horizon }),
  optimize: (b) => post("/optimize", b), experiment: (b) => post("/experiments", b),
  history: () => get("/history"), historyItem: (id) => get(`/history/${id}`), clearHistory: () => http.delete("/history").then((r) => r.data),
  simStart: (b) => post("/simulation/start", b), simPause: () => post("/simulation/pause"),
  simResume: () => post("/simulation/resume"), simReset: () => post("/simulation/reset"),
};
