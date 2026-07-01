# 🌙 ISRO Lunar Ice Explorer — BAH 2026 · Problem Statement 8

**Detection and Characterization of Subsurface Ice in Lunar South Polar Regions**
using Chandrayaan-2 DFSAR/OHRC data, with landing site selection and rover traverse planning.

---

## 🏗️ Architecture

```
Frontend (Next.js)   →   Backend (Python FastAPI)
  Vercel                   Render
  isro-app.vercel.app  →   isro-backend.onrender.com
```

---

## 🚀 Deployment

### Step 1 — Push to GitHub

```bash
# Make sure the LOLA DEM data files are tracked (run once)
git add backend/data/faustini_dem.npy
git add backend/data/faustini_metadata.json
git add .
git commit -m "Add deployment config and LOLA DEM data"
git push origin main
```

---

### Step 2 — Deploy Backend to Render

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repository
3. Render auto-detects `render.yaml` — click **Apply**
4. Service settings (if configuring manually):
   | Setting | Value |
   |---|---|
   | **Root Directory** | `backend` |
   | **Runtime** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1` |
5. Add environment variables in Render dashboard:
   | Variable | Value |
   |---|---|
   | `PYTHONUNBUFFERED` | `1` |
   | `PYTHONIOENCODING` | `utf-8` |
   | `ISRO_SCENE_SIZE` | `256` |
6. Click **Deploy** — wait for the build (~3-5 min)
7. Copy the service URL: `https://isro-lunar-ice-backend.onrender.com`

> **Note:** The free tier spins down after 15 min of inactivity. The first request
> after a cold start takes ~30-60 s while the analysis pipeline pre-warms. Subsequent
> requests are served from cache and are instant.

---

### Step 3 — Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project**
2. Import your GitHub repository
3. Set the **Root Directory** to `frontend`
4. Add the environment variable **before** clicking Deploy:
   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://isro-lunar-ice-backend.onrender.com` |
5. Click **Deploy** — build takes ~1 min
6. Your app is live at `https://your-project.vercel.app`

> **After deploying**, go back to Render and optionally lock down CORS:
> Add `CORS_ORIGINS = https://your-project.vercel.app` to the Render env vars.

---

### Step 4 — Optional: lock down CORS on Render

Once you have your Vercel URL, restrict the backend CORS to that domain only:

```
CORS_ORIGINS=https://isro-lunar-ice.vercel.app
```

Set this in Render Dashboard → Environment → Add Environment Variable, then **Manual Deploy** to restart.

---

## 💻 Local Development

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
uvicorn app:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
# Create .env.local with: NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Or use Docker Compose:
```bash
docker-compose up --build
```

App: http://localhost:3000 | API: http://localhost:8000

---

## 🔬 Scientific Modules

| Module | Method |
|---|---|
| `polarimetric.py` | Stokes parameters, CPR = P_SC/P_OC, DOP = √(S₁²+S₂²+S₃²)/S₀, m-δ decomposition |
| `shadow_mapping.py` | Ray-casting illumination model at 1.5° solar elevation |
| `ice_detection.py` | CPR > 1 AND DOP < 0.13 with thermal gate T < 110 K |
| `terrain_analysis.py` | Slope, TRI, boulder density from DEM/OHRC |
| `landing_site.py` | 5-criteria weighted scoring (safety, ice proximity, solar, scientific, trafficability) |
| `path_planning.py` | A* with terrain-aware cost function |
| `ice_volume.py` | CRIM dielectric mixing + Monte Carlo (n=2000) |
| `dfsar_processor.py` | PDS4 DFSAR reader + LOLA DEM loader (graceful fallback) |

---

## 📡 API Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Health check + endpoint list |
| `GET /api/overview` | Dashboard summary statistics |
| `GET /api/shadow-mapping` | PSR/illumination/temperature maps |
| `GET /api/polarimetric` | CPR, DOP, Stokes, m-δ decomposition |
| `GET /api/dual-frequency` | L-band vs S-band dual-frequency analysis |
| `GET /api/ice-detection` | Ice candidate maps + confidence scores |
| `GET /api/terrain` | Slope, roughness, crater + boulder maps |
| `GET /api/landing-site` | Ranked landing site candidates |
| `GET /api/path-planning` | A* rover traverse path + metrics |
| `GET /api/ice-volume` | CRIM-model ice volume estimates |
| `GET /api/faustini-inventory` | Published 9-crater inventory (Chakraborty 2026) |
| `GET /api/thermal-stability` | Diviner-based thermal stability zones |
| `POST /api/refresh` | Clear analysis cache and recompute |

---

## 🛰️ Data Sources

| Dataset | Source | Use |
|---|---|---|
| **LOLA South Pole DEM** | NASA PGDA · Barker et al. (2021) · [LDEM_85S_40M](https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/LDEM_85S_40M.IMG) | Real terrain for shadow/PSR/landing |
| **Chandrayaan-2 DFSAR** | ISRO PRADAN · [pradan.issdc.gov.in](https://pradan.issdc.gov.in/ch2/) | Calibrated synthetic model (real data plug-in ready) |
| **Diviner Thermal** | Paige et al. (2010) Science 330:479 | Temperature stability thresholds |
| **DFSAR Ice Criterion** | Putrevu et al. (2023) / Chakraborty et al. (2026) npj Space Exploration | CPR > 1, DOP < 0.13 |

---

## 📚 References

- Chakraborty et al. (2026). *Subsurface ice in doubly shadowed craters as revealed by Chandrayaan-2 DFSAR.* npj Space Exploration. DOI: 10.1038/s44453-026-00038-9
- Putrevu et al. (2023). *Full-polarimetric L-band DFSAR ice detection.* JGR Planets.
- Shroff et al. (2024). *Detection of Water Ice in Faustini Crater Floor Using DFSAR.* IGARSS 2024.
- Barker et al. (2021). *Improved LOLA Elevation Maps for South Pole Landing Sites.* Planet. Space Sci. 203, 105119.
- Paige et al. (2010). *Diviner Lunar Radiometer Observations of Cold Traps.* Science 330, 479–482.
- Zhang & Paige (2009). *Cold-trapped organic compounds at the poles of the Moon.* Geophys. Res. Lett.
