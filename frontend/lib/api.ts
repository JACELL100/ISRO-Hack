const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function fetchApi(endpoint: string) {
  const res = await fetch(`${API_URL}${endpoint}`, {
    next: { revalidate: 0 }, // Always fresh in development
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  overview: () => fetchApi('/api/overview'),
  shadowMapping: () => fetchApi('/api/shadow-mapping'),
  polarimetric: () => fetchApi('/api/polarimetric'),
  iceDetection: () => fetchApi('/api/ice-detection'),
  terrain: () => fetchApi('/api/terrain'),
  landingSite: () => fetchApi('/api/landing-site'),
  pathPlanning: () => fetchApi('/api/path-planning'),
  iceVolume: () => fetchApi('/api/ice-volume'),
  refresh: () => fetch(`${API_URL}/api/refresh`, { method: 'POST' }).then(r => r.json()),
};
