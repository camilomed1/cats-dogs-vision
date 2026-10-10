// Thin wrapper around the Flask API. In dev, Vite proxies /api to http://localhost:5000.
const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("Cannot reach the server. Is the Flask backend running?");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `Server error (${res.status})`);
  return body;
}

export const api = {
  health: () => request("/api/health"),
  history: (limit = 50, client = "") =>
    request(`/api/history?limit=${limit}${client ? `&client=${client}` : ""}`),
  deletePrediction: (id) => request(`/api/predictions/${id}`, { method: "DELETE" }),
  /** image: base64 string, metadata: object, store: save in MongoDB or not (live frames). */
  predict: (image, metadata, store = true) =>
    request("/api/predict", {
      method: "POST",
      body: JSON.stringify({ image, metadata: { client: "web", ...metadata }, store }),
    }),
  imageUrl: (path) => BASE + path,
};
