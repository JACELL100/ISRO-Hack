const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://backend-isrohack.onrender.com";

async function fetchApi(endpoint: string) {
  // 60-second timeout — Render free tier can take ~30s to wake from sleep
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60_000);
  try {
    const res = await fetch(`${API_URL}${endpoint}`, {
      next: { revalidate: 0 },
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
    return res.json();
  } catch (err: any) {
    if (err.name === "AbortError") {
      throw new Error("Request timed out — backend may be waking up (Render free tier). Please wait 30s and refresh.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  overview: () => fetchApi("/api/overview"),
  shadowMapping: () => fetchApi("/api/shadow-mapping"),
  polarimetric: () => fetchApi("/api/polarimetric"),
  dualFrequency: () => fetchApi("/api/dual-frequency"),
  iceDetection: () => fetchApi("/api/ice-detection"),
  terrain: () => fetchApi("/api/terrain"),
  landingSite: () => fetchApi("/api/landing-site"),
  pathPlanning: () => fetchApi("/api/path-planning"),
  iceVolume: () => fetchApi("/api/ice-volume"),
  faustiniInventory: () => fetchApi("/api/faustini-inventory"),
  thermalStability: () => fetchApi("/api/thermal-stability"),
  refresh: () =>
    fetch(`${API_URL}/api/refresh`, { method: "POST" }).then((r) => r.json()),
};
