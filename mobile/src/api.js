import Constants from "expo-constants";
import { Platform } from "react-native";

/**
 * The Flask server runs on the same PC as the Expo dev server, so by default we reuse the
 * IP address the phone already uses to reach Expo (e.g. "192.168.1.5:8081" -> http://192.168.1.5:5000).
 */
export function defaultServerUrl() {
  const host = Constants.expoConfig?.hostUri?.split(":")[0];
  return host ? `http://${host}:5000` : "http://192.168.1.5:5000";
}

async function request(baseUrl, path, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(baseUrl + path, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });
  } catch {
    throw new Error(`Cannot reach the server at ${baseUrl}. Is Flask running and is the phone on the same Wi-Fi?`);
  } finally {
    clearTimeout(timer);
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `Server error (${res.status})`);
  return body;
}

export function createApi(baseUrl) {
  return {
    baseUrl,
    health: () => request(baseUrl, "/api/health", {}, 4000),
    history: (limit = 50) => request(baseUrl, `/api/history?limit=${limit}`),
    deletePrediction: (id) => request(baseUrl, `/api/predictions/${id}`, { method: "DELETE" }),
    /** image: base64 string, metadata: object, store: save in MongoDB or not (live frames). */
    predict: (image, metadata, store = true) =>
      request(baseUrl, "/api/predict", {
        method: "POST",
        body: JSON.stringify({
          image,
          metadata: {
            client: "mobile",
            platform: Platform.OS,
            osVersion: String(Platform.Version),
            device: Constants.deviceName ?? null,
            ...metadata,
          },
          store,
        }),
      }),
    imageUrl: (path) => baseUrl + path,
  };
}
