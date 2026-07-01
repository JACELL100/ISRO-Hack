"""
ISRO BAH 2026 — Problem Statement 8
Lunar Subsurface Ice Detection & Rover Planning API
FastAPI backend serving all scientific analysis modules.
"""

import base64
import io
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure UTF-8 stdout on all platforms (Windows cp1252, Render Linux)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import matplotlib
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from modules.data_generator import generate_full_scene
from modules.dfsar_processor import load_or_generate
from modules.ice_detection import run_ice_detection_pipeline
from modules.ice_volume import estimate_regional_ice_volume
from modules.landing_site import evaluate_landing_sites
from modules.path_planning import plan_rover_traverse
from modules.polarimetric import (
    compute_all_polarimetric,
    compute_dual_frequency_analysis,
    compute_m_delta_decomposition,
    compute_sband_polarimetric,
    get_statistics,
)
from modules.shadow_mapping import (
    compute_illumination,
    compute_thermal_environment,
    identify_doubly_shadowed_craters,
    identify_psr_regions,
)
from modules.terrain_analysis import compute_full_terrain_analysis
from scipy.ndimage import gaussian_filter

# ─── App Setup ───────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ISRO Lunar Ice Detection API",
    description="Chandrayaan-2 DFSAR/OHRC based subsurface ice detection and rover traverse planning",
    version="1.0.0",
)

# CORS: allow all origins by default; restrict via CORS_ORIGINS env var in production.
# Set CORS_ORIGINS="https://your-app.vercel.app" on Render to lock it down.
_raw_origins = os.environ.get("CORS_ORIGINS", "*")
_cors_origins: list = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins != "*"
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,  # must be False when allow_origins=["*"]
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ─── Global Scene Cache ───────────────────────────────────────────────────────
# ─── Global Scene Cache ───────────────────────────────────────────────────────────────────────────────
_scene: Dict[str, Any] = {}
_analysis: Dict[str, Any] = {}


# Optional path to real Chandrayaan-2 products. When ISRO_DATA_DIR is set and
# contains a valid DFSAR product, the real-data loader is used automatically;
# otherwise the pipeline transparently falls back to the synthetic generator.
DATA_DIR = os.environ.get("ISRO_DATA_DIR")
SCENE_SIZE = int(os.environ.get("ISRO_SCENE_SIZE", "256"))


@app.on_event("startup")
async def _startup_prewarm() -> None:
    """
    Pre-compute the full analysis pipeline on startup so the first HTTP
    request is served instantly.  Runs in a thread-pool to avoid blocking
    the async event loop during the (slow) initial computation.
    """
    import asyncio

    print("[startup] Pre-warming analysis cache...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_analysis)
    print("[startup] Cache ready - all endpoints are hot.")


def get_scene() -> Dict[str, Any]:
    global _scene
    if not _scene:
        # load_or_generate() tries real DFSAR/OHRC/DEM, else synthetic data.
        _scene = load_or_generate(data_dir=DATA_DIR, scene_size=SCENE_SIZE)
    return _scene


def get_analysis() -> Dict[str, Any]:
    global _analysis
    if not _analysis:
        scene = get_scene()
        _analysis = run_full_analysis(scene)
    return _analysis


def run_full_analysis(scene: Dict) -> Dict:
    """Run the complete scientific analysis pipeline on a scene."""
    dem = scene["dem"]
    dfsar = scene["dfsar"]
    ohrc = scene["ohrc"]
    shadow_map = scene["shadow_map"]
    psr_mask = scene["psr_mask"]
    doubly_shadowed = scene["doubly_shadowed"]
    pixel_size_m = scene["metadata"]["pixel_size_m"]

    # Polarimetric analysis — L-band (primary)
    polar = compute_all_polarimetric(dfsar, window=7)

    # S-band polarimetric analysis (dual-frequency validation)
    dfsar_sband = scene.get("dfsar_sband", dfsar)  # Fallback to L-band if no S-band
    sband = compute_sband_polarimetric(dfsar_sband, window=7)

    # m-delta scattering decomposition (Raney 2012 / Shroff et al. 2024 IGARSS)
    m_delta = compute_m_delta_decomposition(
        dfsar["S_HH"], dfsar["S_HV"], dfsar["S_VH"], dfsar["S_VV"], window=7
    )

    # Dual-frequency ice confidence analysis
    dual_freq = compute_dual_frequency_analysis(polar, sband)

    # PSR identification
    psr_data = identify_psr_regions(psr_mask)

    # Doubly shadowed craters
    ds_data = identify_doubly_shadowed_craters(psr_mask, dem, shadow_map)
    doubly_shadowed_mask = ds_data["doubly_shadowed_mask"]
    crater_list = ds_data["crater_list"]

    # Terrain analysis
    terrain = compute_full_terrain_analysis(dem, ohrc, pixel_size_m)

    # Mean illumination (proxy)
    mean_illumination = 1.0 - shadow_map.astype(float)
    mean_illumination = gaussian_filter(mean_illumination, sigma=5)

    # Thermal environment
    temperature = compute_thermal_environment(shadow_map, mean_illumination)

    # Ice detection — temperature passed as HARD GATE (< 110 K required)
    shadow_data = {
        "shadow_map": shadow_map,
        "psr_mask": psr_mask,
        "doubly_shadowed_mask": doubly_shadowed_mask,
    }
    ice = run_ice_detection_pipeline(
        polar, shadow_data, terrain, temperature=temperature
    )

    # Landing site evaluation
    landing = evaluate_landing_sites(
        dem=dem,
        slope=terrain["slope"],
        roughness=terrain["roughness"],
        shadow_map=shadow_map,
        psr_mask=psr_mask,
        mean_illumination=mean_illumination,
        ice_probability=ice["probability_map"],
        ice_mask=ice["ice_validated_mask"],
        doubly_shadowed_mask=doubly_shadowed_mask,
        crater_mask=terrain["crater_mask"],
        pixel_size_m=pixel_size_m,
        n_sites=5,
    )

    # Ice volume estimation
    ice_volume = estimate_regional_ice_volume(
        cpr=polar["CPR"],
        ice_mask=ice["ice_validated_mask"],
        ice_regions=ice["ice_regions"][:10],
        pixel_size_m=pixel_size_m,
    )

    # Path planning: best landing site → doubly shadowed crater (or fallback to ice region centroid)
    path_result = None
    if landing["best_site"]:
        # Choose target: prefer doubly shadowed crater, fallback to ice region center
        target_crater = None
        if crater_list:
            target_crater = crater_list[0]
        elif ice["ice_regions"]:
            # Synthesise a pseudo-crater from the largest ice region
            best_ice = max(ice["ice_regions"], key=lambda r: r.get("area_pixels", 0))
            target_crater = {
                "center_row": best_ice["center_row"],
                "center_col": best_ice["center_col"],
                "max_depth_m": 10.0,
                "area_pixels": best_ice.get("area_pixels", 100),
                "min_elevation_m": float(
                    dem[best_ice["center_row"], best_ice["center_col"]]
                ),
                "priority_score": 5.0,
            }
        if target_crater:
            path_result = plan_rover_traverse(
                dem=dem,
                slope=terrain["slope"],
                roughness=terrain["roughness"],
                shadow_map=shadow_map,
                mean_illumination=mean_illumination,
                landing_site=landing["best_site"],
                target_crater=target_crater,
                crater_mask=terrain["crater_mask"],
                boulder_density=terrain.get("boulder_density"),
                pixel_size_m=pixel_size_m,
            )

    return {
        "polar": polar,
        "sband": sband,
        "dual_freq": dual_freq,
        "m_delta": m_delta,
        "psr_data": psr_data,
        "ds_data": ds_data,
        "terrain": terrain,
        "ice": ice,
        "landing": landing,
        "ice_volume": ice_volume,
        "path": path_result,
        "mean_illumination": mean_illumination,
        "temperature": temperature,
    }


def arr_to_img_base64(
    arr: np.ndarray, cmap: str = "viridis", vmin=None, vmax=None
) -> str:
    """Convert a numpy array to a base64-encoded PNG image."""
    fig, ax = plt.subplots(figsize=(6, 6), dpi=80)
    im = ax.imshow(arr, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_axis_off()
    plt.tight_layout(pad=0.2)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=80)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def arr_to_list(arr: np.ndarray, step: int = 4) -> list:
    """Downsample array and convert to nested list for JSON."""
    return arr[::step, ::step].tolist()


# ─── API Routes ───────────────────────────────────────────────────────────────


@app.get("/")
def root():
    return {
        "title": "ISRO Lunar Ice Detection API",
        "status": "operational",
        "version": "1.0.0",
        "endpoints": [
            "/api/overview",
            "/api/shadow-mapping",
            "/api/polarimetric",
            "/api/dual-frequency",
            "/api/ice-detection",
            "/api/terrain",
            "/api/landing-site",
            "/api/path-planning",
            "/api/ice-volume",
            "/api/faustini-inventory",
            "/api/thermal-stability",
        ],
    }


@app.get("/api/overview")
def get_overview():
    """Dashboard overview: key statistics across all modules."""
    scene = get_scene()
    analysis = get_analysis()

    meta = scene["metadata"]
    return {
        "scene_metadata": meta,
        "data_source": meta.get("data_source", "Synthetic data generator"),
        "dem_source": meta.get("dem_source", "Synthetic"),
        "dem_pds_product": meta.get("dem_pds_product", ""),
        "dem_pds_url": meta.get("dem_pds_url", ""),
        "using_real_dem": "LOLA-real" in meta.get("dem_source", ""),
        "using_real_data": meta.get("data_source", "").endswith("(real)"),
        "psr_count": analysis["psr_data"]["n_psrs"],
        "doubly_shadowed_count": analysis["ds_data"]["n_craters"],
        "ice_regions_count": analysis["ice"]["n_ice_regions"],
        "ice_coverage_pct": analysis["ice"]["ice_coverage_pct"],
        "total_ice_area_km2": analysis["ice"]["total_ice_area_km2"],
        "total_ice_volume_m3": analysis["ice_volume"]["total_volume_m3"],
        "total_ice_mass_tonnes": analysis["ice_volume"]["total_mass_tonnes"],
        "best_landing_site": analysis["landing"]["best_site"],
        "rover_path_distance_km": (
            analysis["path"]["metrics"]["total_distance_km"]
            if analysis["path"] and analysis["path"]["success"]
            else None
        ),
        "rover_path_safety": (
            analysis["path"]["metrics"]["path_safety"]
            if analysis["path"] and analysis["path"]["success"]
            else None
        ),
        "mean_cpr": get_statistics(analysis["polar"]["CPR"])["mean"],
        "mean_dop": get_statistics(analysis["polar"]["DOP"])["mean"],
    }


@app.get("/api/shadow-mapping")
def get_shadow_mapping():
    """Shadow map, PSR identification, and thermal environment data."""
    scene = get_scene()
    analysis = get_analysis()
    step = 3

    dem = scene["dem"]
    shadow_map = scene["shadow_map"]
    psr_mask = scene["psr_mask"]
    doubly_shadowed = analysis["ds_data"]["doubly_shadowed_mask"]
    temperature = analysis["temperature"]
    mean_illumination = analysis["mean_illumination"]

    return {
        "dem_data": arr_to_list(dem, step),
        "shadow_map_data": arr_to_list(shadow_map, step),
        "psr_mask_data": arr_to_list(psr_mask, step),
        "doubly_shadowed_data": arr_to_list(doubly_shadowed, step),
        "illumination_data": arr_to_list(mean_illumination, step),
        "temperature_data": arr_to_list(temperature, step),
        "rows": dem.shape[0] // step,
        "cols": dem.shape[1] // step,
        "psr_regions": analysis["psr_data"]["psr_regions"][:20],
        "doubly_shadowed_craters": analysis["ds_data"]["crater_list"][:10],
        "n_psrs": analysis["psr_data"]["n_psrs"],
        "n_doubly_shadowed": analysis["ds_data"]["n_craters"],
        "psr_coverage_pct": round(float(psr_mask.mean() * 100), 2),
        "shadow_coverage_pct": round(float(shadow_map.mean() * 100), 2),
        "min_temperature_K": round(float(temperature.min()), 1),
        "mean_temperature_K": round(float(temperature.mean()), 1),
        "dem_stats": {
            "min_m": round(float(dem.min()), 1),
            "max_m": round(float(dem.max()), 1),
            "mean_m": round(float(dem.mean()), 1),
        },
        "sun_elevation_deg": scene["metadata"]["sun_elevation_deg"],
    }


@app.get("/api/polarimetric")
def get_polarimetric():
    """DFSAR polarimetric analysis: L-band CPR/DOP, S-band CPR/DOP, dual-frequency analysis."""
    analysis = get_analysis()
    polar = analysis["polar"]
    sband = analysis["sband"]
    dual_freq = analysis["dual_freq"]
    ice_mask = analysis["ice"]["ice_validated_mask"]
    step = 3

    cpr = polar["CPR"]
    dop = polar["DOP"]
    cpr_s = sband["CPR_S"]
    dop_s = sband["DOP_S"]

    return {
        # L-band
        "cpr_data": arr_to_list(cpr, step),
        "dop_data": arr_to_list(dop, step),
        "s0_data": arr_to_list(polar["S0"], step),
        "entropy_data": arr_to_list(polar["entropy_proxy"], step),
        # S-band
        "cpr_s_data": arr_to_list(cpr_s, step),
        "dop_s_data": arr_to_list(dop_s, step),
        "s0_s_data": arr_to_list(sband["S0_S"], step),
        # Dual-frequency
        "dfr_data": arr_to_list(dual_freq["dual_frequency_ratio"], step),
        "dual_confidence_data": arr_to_list(dual_freq["dual_confidence"], step),
        "ice_dual_confirmed_data": arr_to_list(dual_freq["ice_dual_confirmed"], step),
        "rows": cpr.shape[0] // step,
        "cols": cpr.shape[1] // step,
        # Statistics
        "cpr_stats": get_statistics(cpr),
        "dop_stats": get_statistics(dop),
        "cpr_s_stats": get_statistics(cpr_s),
        "dop_s_stats": get_statistics(dop_s),
        "cpr_ice_stats": get_statistics(cpr, ice_mask),
        "dop_ice_stats": get_statistics(dop, ice_mask),
        "thresholds": {
            "CPR_L": 1.0,
            "DOP_L": 0.13,
            "CPR_S": 1.0,
            "DOP_S": 0.13,
            "method": "Dual-frequency CPR+DOP (Putrevu et al. 2023 / Chakraborty et al. 2024)",
        },
        "cpr_histogram": _histogram(cpr.ravel(), 40, 0, 3),
        "dop_histogram": _histogram(dop.ravel(), 40, 0, 1),
        "cpr_s_histogram": _histogram(cpr_s.ravel(), 40, 0, 3),
        "dop_s_histogram": _histogram(dop_s.ravel(), 40, 0, 1),
        "n_pixels_cpr_above_1": int((cpr > 1.0).sum()),
        "n_pixels_dop_below_013": int((dop < 0.13).sum()),
        "n_pixels_both": int(((cpr > 1.0) & (dop < 0.13)).sum()),
        # m-delta decomposition summary (Raney 2012 / Shroff et al. 2024 IGARSS)
        "m_delta_decomposition": {
            "fv_mean": round(float(analysis["m_delta"]["fv"].mean()), 3),
            "fs_mean": round(float(analysis["m_delta"]["fs"].mean()), 3),
            "fd_mean": round(float(analysis["m_delta"]["fd"].mean()), 3),
            "fv_pct": round(float(analysis["m_delta"]["fv"].mean()) * 100, 1),
            "fs_pct": round(float(analysis["m_delta"]["fs"].mean()) * 100, 1),
            "fd_pct": round(float(analysis["m_delta"]["fd"].mean()) * 100, 1),
            "m_mean": round(float(analysis["m_delta"]["m"].mean()), 3),
            "description": analysis["m_delta"]["description"],
            "reference": "Raney et al. (2012) IEEE-TGARS / Shroff et al. (2024) IGARSS",
            "faustini_c2_reference": {"Pv_pct": 49.0, "Pd_pct": 28.0, "Ps_pct": 24.0},
        },
        # Dual-frequency summary
        "n_ice_L_band": dual_freq["n_ice_L"],
        "n_ice_S_band": dual_freq["n_ice_S"],
        "n_ice_dual_confirmed": dual_freq["n_ice_dual"],
        "pct_dual_confirmed": dual_freq["pct_dual_confirmed"],
        "l_band_info": {"frequency_MHz": 430, "wavelength_cm": 24, "penetration_m": 5},
        "s_band_info": {"frequency_GHz": 2.5, "wavelength_cm": 9, "penetration_m": 1.5},
    }


@app.get("/api/ice-detection")
def get_ice_detection():
    """Ice detection results: validated regions, confidence map, probability map."""
    analysis = get_analysis()
    ice = analysis["ice"]
    step = 3

    return {
        "ice_mask_data": arr_to_list(ice["ice_validated_mask"], step),
        "probability_data": arr_to_list(ice["probability_map"], step),
        "confidence_data": arr_to_list(ice["total_confidence"], step),
        "rows": ice["ice_validated_mask"].shape[0] // step,
        "cols": ice["ice_validated_mask"].shape[1] // step,
        "ice_regions": ice["ice_regions"][:20],
        "n_ice_regions": ice["n_ice_regions"],
        "total_ice_area_km2": ice["total_ice_area_km2"],
        "ice_coverage_pct": ice["ice_coverage_pct"],
        "tier1_count": ice["tier1_regions"],
        "tier2_count": ice["tier2_regions"],
        "thermal_gate_applied": ice.get("thermal_gate_applied", False),
        "temp_threshold_K": ice.get("temp_threshold_K", 110.0),
        "detection_criteria": ice["detection_criteria"],
        "priority_summary": {
            "tier1": "Doubly Shadowed Craters — highest priority ice targets",
            "tier2": "PSR ice regions — high radar confidence",
            "tier3": "Moderate confidence ice signatures",
        },
    }


@app.get("/api/dual-frequency")
def get_dual_frequency():
    """Dual-frequency (L-band + S-band) ice detection analysis and comparison."""
    analysis = get_analysis()
    dual_freq = analysis["dual_freq"]
    sband = analysis["sband"]
    polar = analysis["polar"]
    step = 3

    return {
        # Spatial maps
        "cpr_l_data": arr_to_list(dual_freq["CPR_L"], step),
        "cpr_s_data": arr_to_list(dual_freq["CPR_S"], step),
        "dfr_data": arr_to_list(dual_freq["dual_frequency_ratio"], step),
        "dual_confidence_data": arr_to_list(dual_freq["dual_confidence"], step),
        "ice_dual_confirmed_data": arr_to_list(dual_freq["ice_dual_confirmed"], step),
        "ice_l_only_data": arr_to_list(dual_freq["ice_L_only"], step),
        "roughness_flag_data": arr_to_list(dual_freq["roughness_flag"], step),
        "rows": dual_freq["CPR_L"].shape[0] // step,
        "cols": dual_freq["CPR_L"].shape[1] // step,
        # Statistics
        "n_ice_L_band": dual_freq["n_ice_L"],
        "n_ice_S_band": dual_freq["n_ice_S"],
        "n_ice_dual_confirmed": dual_freq["n_ice_dual"],
        "pct_dual_confirmed": dual_freq["pct_dual_confirmed"],
        "n_roughness_flags": int(dual_freq["roughness_flag"].sum()),
        "dfr_stats": get_statistics(dual_freq["dual_frequency_ratio"]),
        "dual_confidence_stats": get_statistics(dual_freq["dual_confidence"]),
        # Band info
        "l_band": {
            "frequency_MHz": 430,
            "wavelength_cm": 24,
            "penetration_depth_m": 5.0,
            "description": "L-band (430 MHz): primary ice detection, probes ~5 m depth",
        },
        "s_band": {
            "frequency_GHz": 2.5,
            "wavelength_cm": 9,
            "penetration_depth_m": 1.5,
            "description": "S-band (2.5 GHz): confirms shallow surface ice, ~1-2 m depth",
        },
        "interpretation": {
            "dual_confirmed": "Both L and S bands show ice signature — highest confidence",
            "l_only": "L-band only: possible deep ice or rough terrain — needs further analysis",
            "roughness_flag": "High CPR in both bands with DFR~1 — likely rough rocky surface",
            "dfr_interpretation": "DFR = CPR_L / CPR_S > 1 favors deep subsurface ice over surface roughness",
        },
    }


@app.get("/api/terrain")
def get_terrain():
    """Terrain analysis: slope, roughness, craters, boulders."""
    scene = get_scene()
    analysis = get_analysis()
    terrain = analysis["terrain"]
    step = 3

    return {
        "slope_data": arr_to_list(terrain["slope"], step),
        "roughness_data": arr_to_list(terrain["roughness"], step),
        "dem_data": arr_to_list(scene["dem"], step),
        "ohrc_data": arr_to_list(scene["ohrc"], step),
        "rows": terrain["slope"].shape[0] // step,
        "cols": terrain["slope"].shape[1] // step,
        "slope_stats": terrain["slope_stats"],
        "craters": terrain["craters"][:20],
        "n_craters": terrain["n_craters"],
        "boulder_coverage_pct": terrain.get("boulder_coverage_pct", 0),
        "slope_histogram": _histogram(terrain["slope"].ravel(), 36, 0, 36),
        "roughness_histogram": _histogram(terrain["roughness"].ravel(), 30, 0, None),
    }


@app.get("/api/landing-site")
def get_landing_site():
    """Landing site evaluation: composite scores and ranked candidates."""
    analysis = get_analysis()
    landing = analysis["landing"]
    step = 3

    return {
        "composite_map_data": arr_to_list(landing["composite_score_map"], step),
        "safety_map_data": arr_to_list(landing["safety_map"], step),
        "solar_map_data": arr_to_list(landing["solar_map"], step),
        "scientific_map_data": arr_to_list(landing["scientific_map"], step),
        "rows": landing["composite_score_map"].shape[0] // step,
        "cols": landing["composite_score_map"].shape[1] // step,
        "candidate_sites": landing["candidate_sites"],
        "best_site": landing["best_site"],
        "criteria_weights": landing["criteria_weights"],
        "evaluation_criteria": {
            "safety": "Slope < 15°, low roughness, away from crater rims",
            "ice_proximity": "Distance to ice-bearing regions",
            "solar_power": "Mean illumination for power generation",
            "scientific": "Proximity to doubly shadowed craters",
            "trafficability": "Rover accessibility to target crater",
        },
    }


@app.get("/api/path-planning")
def get_path_planning():
    """Rover traverse path from landing site to target crater/ice region."""
    analysis = get_analysis()
    path_result = analysis["path"]
    landing = analysis["landing"]
    ds_data = analysis["ds_data"]
    ice = analysis["ice"]
    step = 3

    if not path_result or not path_result.get("success"):
        # Return a structured failure response (not 404) so frontend can show error state
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "error": "No traversable path found — check terrain or landing site constraints",
                "landing_site": landing.get("best_site"),
                "target_crater": ds_data["crater_list"][0]
                if ds_data["crater_list"]
                else None,
            },
        )

    cost_map = path_result.get("cost_map")

    return {
        "success": True,
        "cost_map_data": arr_to_list(cost_map, step) if cost_map is not None else [],
        "rows": cost_map.shape[0] // step if cost_map is not None else 0,
        "cols": cost_map.shape[1] // step if cost_map is not None else 0,
        "path_waypoints": path_result.get("metrics", {}).get("waypoints", []),
        "full_path": path_result.get("path", []),
        "start": path_result.get("start"),
        "goal": path_result.get("goal"),
        "metrics": path_result.get("metrics", {}),
        "algorithm": path_result.get("algorithm"),
        "cost_components": path_result.get("cost_components"),
        "landing_site": landing["best_site"],
        "target_crater": ds_data["crater_list"][0]
        if ds_data["crater_list"]
        else (ice["ice_regions"][0] if ice["ice_regions"] else None),
        "doubly_shadowed_craters": ds_data["crater_list"][:5],
    }


@app.get("/api/ice-volume")
def get_ice_volume():
    """Ice volume estimation using dielectric models and Monte Carlo uncertainty."""
    analysis = get_analysis()
    ice_volume = analysis["ice_volume"]

    return {
        "total_ice_area_km2": ice_volume["total_ice_area_km2"],
        "total_volume_m3": ice_volume["total_volume_m3"],
        "total_volume_km3": ice_volume["total_volume_km3"],
        "total_mass_tonnes": ice_volume["total_mass_tonnes"],
        "mean_ice_fraction_pct": ice_volume["mean_ice_fraction_pct"],
        "volume_p5_m3": ice_volume["volume_uncertainty_p5_m3"],
        "volume_p95_m3": ice_volume["volume_uncertainty_p95_m3"],
        "depth_modeled_m": ice_volume["depth_modeled_m"],
        "model_description": ice_volume["model"],
        "regions": ice_volume["regions"][:15],
        "cpr_to_ice_table": ice_volume["cpr_dop_comparison"],
        "ice_fraction_histogram": ice_volume["ice_fraction_histogram"],
        "volume_histogram": ice_volume["volume_histogram"],
        "physical_constants": {
            "epsilon_ice": 3.15,
            "epsilon_regolith": 3.0,
            "ice_density_kg_m3": 917,
            "wavelength_L_cm": 24,
        },
    }


@app.get("/api/faustini-inventory")
def get_faustini_inventory():
    """
    Published crater inventory for Faustini PSR doubly-shadowed craters.
    Based on: Chakraborty et al. (2026) npj Space Exploration — "Subsurface ice
    in doubly shadowed craters as revealed by Chandrayaan-2 DFSAR"
    Source: DOI 10.1038/s44453-026-00038-9
    """
    return {
        "parent_crater": {
            "name": "Faustini",
            "lat_deg_S": 87.3,
            "lon_deg_E": 77.0,
            "diameter_km": 39.0,
            "depth_m": 4000,
            "psr_coverage_pct": 100,
        },
        "doubly_shadowed_craters": [
            {
                "id": "C1",
                "diameter_km": 0.7,
                "ice_candidate": False,
                "mean_cpr": 0.71,
                "mean_dop": 0.52,
                "notes": "Rough terrain, no ice",
            },
            {
                "id": "C2",
                "diameter_km": 1.1,
                "ice_candidate": True,
                "mean_cpr": 1.23,
                "mean_dop": 0.09,
                "notes": "Primary ice candidate — lobate-rim morphology, strongest signal",
                "lobate_rim": True,
                "location": "Faustini NE quadrant",
            },
            {
                "id": "C3",
                "diameter_km": 0.5,
                "ice_candidate": True,
                "mean_cpr": 1.07,
                "mean_dop": 0.11,
                "notes": "Secondary ice candidate",
            },
            {
                "id": "C4",
                "diameter_km": 0.8,
                "ice_candidate": True,
                "mean_cpr": 1.15,
                "mean_dop": 0.10,
                "notes": "Secondary ice candidate",
            },
            {
                "id": "C5",
                "diameter_km": 0.4,
                "ice_candidate": False,
                "mean_cpr": 0.83,
                "mean_dop": 0.38,
                "notes": "No ice — surface roughness",
            },
            {
                "id": "C6",
                "diameter_km": 0.6,
                "ice_candidate": False,
                "mean_cpr": 0.62,
                "mean_dop": 0.61,
                "notes": "No ice",
            },
            {
                "id": "C7",
                "diameter_km": 0.9,
                "ice_candidate": True,
                "mean_cpr": 1.09,
                "mean_dop": 0.12,
                "notes": "Haworth sub-crater — ice candidate",
            },
            {
                "id": "C8",
                "diameter_km": 1.2,
                "ice_candidate": False,
                "mean_cpr": 0.88,
                "mean_dop": 0.29,
                "notes": "Shoemaker sub-crater — rough terrain",
            },
            {
                "id": "C9",
                "diameter_km": 0.7,
                "ice_candidate": False,
                "mean_cpr": 0.74,
                "mean_dop": 0.44,
                "notes": "No ice",
            },
        ],
        "summary": {
            "total_analyzed": 9,
            "ice_candidates": 4,
            "primary_target": "C2 (Faustini, 1.1 km, lobate-rim)",
            "detection_criterion": "CPR > 1.0 AND DOP < 0.13 (Putrevu et al. 2023 / Chakraborty et al. 2024)",
            "source_paper": "Chakraborty et al. (2026) npj Space Exploration DOI:10.1038/s44453-026-00038-9",
        },
        "m_delta_faustini_c2": {
            "Pv_pct": 49.0,
            "Pd_pct": 28.0,
            "Ps_pct": 24.0,
            "interpretation": "Dominant volume scattering (49%) confirms subsurface ice",
            "source": "Shroff et al. (2024) IGARSS",
        },
    }


@app.get("/api/thermal-stability")
def get_thermal_stability():
    """
    Thermal stability analysis based on published Diviner measurements.
    Reference: Paige et al. (2010) Science 330:479-482.
    """
    analysis = get_analysis()
    temperature = analysis["temperature"]
    ice = analysis["ice"]

    # Ice stability zones based on published thresholds
    stable_below_40K = int((temperature < 40).sum())
    stable_below_70K = int((temperature < 70).sum())
    stable_below_110K = int((temperature < 110).sum())
    total_pixels = temperature.size

    ice_validated_bool = ice["ice_validated_mask"].astype(bool)
    mean_psr_temp = (
        round(float(temperature[ice_validated_bool].mean()), 1)
        if ice_validated_bool.sum() > 0
        else 35.0
    )

    return {
        "temperature_thresholds": {
            "water_ice_stable_K": 110,  # Zhang & Paige (2009)
            "optimal_preservation_K": 40,  # Paige et al. (2010) Diviner
            "faustini_floor_K": 29,  # Measured minimum (Paige 2010)
            "doubly_shadowed_K": 25,  # Modeled minimum (Williams et al. 2019)
        },
        "scene_statistics": {
            "pct_below_40K": round(stable_below_40K / total_pixels * 100, 1),
            "pct_below_70K": round(stable_below_70K / total_pixels * 100, 1),
            "pct_below_110K": round(stable_below_110K / total_pixels * 100, 1),
            "mean_psr_temp_K": mean_psr_temp,
        },
        "stability_classification": [
            {
                "zone": "Optimal (T < 40K)",
                "color": "blue",
                "pct": round(stable_below_40K / total_pixels * 100, 1),
                "description": "Ideal for H2O, CO2, NH3 ice",
            },
            {
                "zone": "Good (40-70K)",
                "color": "cyan",
                "pct": round(
                    (stable_below_70K - stable_below_40K) / total_pixels * 100, 1
                ),
                "description": "H2O and CO2 ice stable",
            },
            {
                "zone": "Marginal (70-110K)",
                "color": "yellow",
                "pct": round(
                    (stable_below_110K - stable_below_70K) / total_pixels * 100, 1
                ),
                "description": "H2O ice marginally stable",
            },
            {
                "zone": "Unstable (>110K)",
                "color": "red",
                "pct": round(
                    (total_pixels - stable_below_110K) / total_pixels * 100, 1
                ),
                "description": "Ice sublimation dominant",
            },
        ],
        "diviner_references": {
            "faustini_min_temp_K": 29,
            "haworth_min_temp_K": 38,
            "shoemaker_min_temp_K": 35,
            "source": "Paige et al. (2010) Science 330:479-482 / Diviner Lunar Radiometer",
        },
    }


@app.post("/api/refresh")
def refresh_analysis():
    """Clear cache and regenerate analysis (triggers new synthetic data)."""
    global _scene, _analysis
    _scene = {}
    _analysis = {}
    get_analysis()
    return {"status": "Analysis refreshed successfully"}


def _histogram(data: np.ndarray, bins: int, vmin, vmax) -> List[Dict]:
    """Compute histogram for charts."""
    data = data[np.isfinite(data)]
    if vmin is None:
        vmin = float(data.min())
    if vmax is None:
        vmax = float(data.max())
    counts, edges = np.histogram(data, bins=bins, range=(vmin, vmax))
    return [
        {"bin": round(float((edges[i] + edges[i + 1]) / 2), 4), "count": int(counts[i])}
        for i in range(len(counts))
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
