"""
ISRO BAH 2026 — Problem Statement 8
Lunar Subsurface Ice Detection & Rover Planning API
FastAPI backend serving all scientific analysis modules.
"""
import io
import base64
import json
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from scipy.ndimage import gaussian_filter

from modules.data_generator import generate_full_scene
from modules.polarimetric import (
    compute_all_polarimetric,
    compute_sband_polarimetric,
    compute_dual_frequency_analysis,
    get_statistics,
)
from modules.shadow_mapping import (
    identify_psr_regions,
    identify_doubly_shadowed_craters,
    compute_thermal_environment,
    compute_illumination,
)
from modules.terrain_analysis import compute_full_terrain_analysis
from modules.ice_detection import run_ice_detection_pipeline
from modules.landing_site import evaluate_landing_sites
from modules.path_planning import plan_rover_traverse
from modules.ice_volume import estimate_regional_ice_volume

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ISRO Lunar Ice Detection API",
    description="Chandrayaan-2 DFSAR/OHRC based subsurface ice detection and rover traverse planning",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Global Scene Cache ───────────────────────────────────────────────────────
_scene: Dict[str, Any] = {}
_analysis: Dict[str, Any] = {}


def get_scene() -> Dict[str, Any]:
    global _scene
    if not _scene:
        _scene = generate_full_scene(rows=256, cols=256)
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
    ice = run_ice_detection_pipeline(polar, shadow_data, terrain, temperature=temperature)

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
                "min_elevation_m": float(dem[best_ice["center_row"], best_ice["center_col"]]),
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


def arr_to_img_base64(arr: np.ndarray, cmap: str = "viridis", vmin=None, vmax=None) -> str:
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
        ],
    }


@app.get("/api/overview")
def get_overview():
    """Dashboard overview: key statistics across all modules."""
    scene = get_scene()
    analysis = get_analysis()

    return {
        "scene_metadata": scene["metadata"],
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
        return JSONResponse(status_code=200, content={
            "success": False,
            "error": "No traversable path found — check terrain or landing site constraints",
            "landing_site": landing.get("best_site"),
            "target_crater": ds_data["crater_list"][0] if ds_data["crater_list"] else None,
        })

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
        "target_crater": ds_data["crater_list"][0] if ds_data["crater_list"] else (
            ice["ice_regions"][0] if ice["ice_regions"] else None
        ),
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
        {"bin": round(float((edges[i] + edges[i+1]) / 2), 4), "count": int(counts[i])}
        for i in range(len(counts))
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
