# ISRO Lunar Ice Explorer — Walkthrough

## ✅ Build Complete

The full-stack ISRO BAH 2026 Problem Statement 8 solution has been built and verified.

---

## 🌐 Frontend — Live at http://localhost:3000

All 8 pages are running with zero errors:

![Dashboard Home](file:///C:/Users/hp/.gemini/antigravity-ide/brain/338d925e-ec80-4674-81f0-17436843b2b9/dashboard_home_1782656719632.png)

---

## 📸 Page Screenshots

````carousel
![Dashboard](file:///C:/Users/hp/.gemini/antigravity-ide/brain/338d925e-ec80-4674-81f0-17436843b2b9/dashboard_home_1782656719632.png)
<!-- slide -->
![Shadow Mapping](file:///C:/Users/hp/.gemini/antigravity-ide/brain/338d925e-ec80-4674-81f0-17436843b2b9/shadow_mapping_page_1782656738656.png)
<!-- slide -->
![Polarimetric](file:///C:/Users/hp/.gemini/antigravity-ide/brain/338d925e-ec80-4674-81f0-17436843b2b9/polarimetric_page_1782656768716.png)
<!-- slide -->
![Ice Detection](file:///C:/Users/hp/.gemini/antigravity-ide/brain/338d925e-ec80-4674-81f0-17436843b2b9/ice_detection_page_1782656777125.png)
<!-- slide -->
![Terrain](file:///C:/Users/hp/.gemini/antigravity-ide/brain/338d925e-ec80-4674-81f0-17436843b2b9/terrain_page_1782656821496.png)
<!-- slide -->
![Landing Site](file:///C:/Users/hp/.gemini/antigravity-ide/brain/338d925e-ec80-4674-81f0-17436843b2b9/landing_site_page_1782656842307.png)
<!-- slide -->
![Path Planning](file:///C:/Users/hp/.gemini/antigravity-ide/brain/338d925e-ec80-4674-81f0-17436843b2b9/path_planning_page_1782656866522.png)
<!-- slide -->
![Ice Volume](file:///C:/Users/hp/.gemini/antigravity-ide/brain/338d925e-ec80-4674-81f0-17436843b2b9/ice_volume_page_1782656895270.png)
````

---

## 🚀 To Start the Full Application

**Step 1** — Start backend (once pip install finishes):
```powershell
cd c:\Users\hp\Desktop\ISRO\backend
venv\Scripts\python -m uvicorn app:app --reload --port 8000
```

**Step 2** — Frontend is already running. Or restart with:
```powershell
cd c:\Users\hp\Desktop\ISRO\frontend
npm run dev
```

**Or use the convenience script:**
```powershell
cd c:\Users\hp\Desktop\ISRO
.\start.ps1
```

---

## 📁 Project Structure

| Location | Contents |
|---|---|
| [backend/app.py](file:///c:/Users/hp/Desktop/ISRO/backend/app.py) | FastAPI app — 8 API endpoints |
| [backend/modules/](file:///c:/Users/hp/Desktop/ISRO/backend/modules) | 8 scientific processing modules |
| [frontend/app/](file:///c:/Users/hp/Desktop/ISRO/frontend/app) | 8 Next.js pages |
| [frontend/components/Heatmap.tsx](file:///c:/Users/hp/Desktop/ISRO/frontend/components/Heatmap.tsx) | Canvas heatmap renderer (8 colormaps) |
| [README.md](file:///c:/Users/hp/Desktop/ISRO/README.md) | Full documentation |
| [docker-compose.yml](file:///c:/Users/hp/Desktop/ISRO/docker-compose.yml) | Docker deployment |

---

## 🔬 Scientific Modules Built

| Module | Scientific Method |
|---|---|
| `polarimetric.py` | Stokes parameters, CPR = P_SC/P_OC, DOP = √(S₁²+S₂²+S₃²)/S₀ |
| `shadow_mapping.py` | Ray-casting illumination at 1.5° solar elevation |
| `ice_detection.py` | CPR > 1 AND DOP < 0.13 (Putrevu et al. 2023) |
| `terrain_analysis.py` | Slope, TRI, boulder density from DEM/OHRC |
| `landing_site.py` | 5-criteria weighted scoring |
| `path_planning.py` | A* with terrain-aware cost function |
| `ice_volume.py` | CRIM dielectric mixing + Monte Carlo (n=2000) |
| `dfsar_processor.py` | PDS4 DFSAR reader with synthetic fallback |
