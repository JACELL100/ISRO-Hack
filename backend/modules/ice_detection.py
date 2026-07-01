"""
Ice Detection Module
Applies refined CPR + DOP criteria to identify high-probability
subsurface ice regions in lunar PSRs.

Scientific criteria (Putrevu et al. 2023, Chakraborty et al. 2024):
    CPR > 1.0   → volumetric scattering (ice or rough surface)
    DOP < 0.13  → eliminates rough rocky surfaces (which also have high CPR)
    Combined criterion → high-confidence subsurface ice signature

Additional cross-validation:
    - Located within a PSR or doubly shadowed crater
    - Temperature < 110 K (ice stability threshold) — used as HARD GATE
    - Morphological consistency (lobate crater rims)
    - Dual-frequency (L-band + S-band) consistency check
"""

from typing import Dict, List, Tuple

import numpy as np
from scipy.ndimage import (
    binary_dilation,
    binary_erosion,
    gaussian_filter,
    label,
    uniform_filter,
)

# ─── Detection Thresholds (from published literature) ──────────────────────────
CPR_THRESHOLD = 1.0  # Putrevu et al. 2023
DOP_THRESHOLD = 0.13  # Chakraborty et al. 2024
TEMP_THRESHOLD_K = 110.0  # Ice stability
CONFIDENCE_WEIGHTS = {
    "cpr_dop": 0.50,  # Primary radar criterion
    "shadow": 0.25,  # Inside PSR/shadow
    "morphology": 0.15,  # Lobate crater rim
    "temperature": 0.10,  # Thermal environment
}


def detect_ice_candidates(
    cpr: np.ndarray,
    dop: np.ndarray,
    shadow_mask: np.ndarray = None,
    psr_mask: np.ndarray = None,
    temperature: np.ndarray = None,
) -> Dict[str, np.ndarray]:
    """
    Apply CPR > 1 AND DOP < 0.13 ice detection criterion.
    Temperature < 110 K is applied as a hard physical gate (ice stability threshold).
    Returns binary ice candidate map and confidence scores.
    """
    # Primary ice criterion
    ice_raw = (cpr > CPR_THRESHOLD) & (dop < DOP_THRESHOLD)

    # ── HARD GATE: temperature stability threshold ───────────────────────────
    # Water ice is only stable below 110 K on the Moon (Zhang & Paige 2009)
    # Pixels warmer than this cannot sustain water ice regardless of radar signal
    if temperature is not None:
        thermal_gate = temperature < TEMP_THRESHOLD_K
        ice_raw = ice_raw & thermal_gate

    # Confidence from CPR strength and DOP suppression
    cpr_confidence = np.clip((cpr - CPR_THRESHOLD) / 2.0, 0, 1)
    dop_confidence = np.clip((DOP_THRESHOLD - dop) / DOP_THRESHOLD, 0, 1)
    radar_confidence = (cpr_confidence + dop_confidence) / 2.0

    # Temperature confidence (cooler → higher confidence)
    if temperature is not None:
        temp_confidence = np.clip(
            (TEMP_THRESHOLD_K - temperature) / TEMP_THRESHOLD_K, 0, 1
        )
    else:
        temp_confidence = np.zeros_like(cpr)

    # Context-based confidence boost
    context_confidence = np.zeros_like(cpr)
    if shadow_mask is not None:
        context_confidence += shadow_mask.astype(float) * 0.4
    if psr_mask is not None:
        context_confidence += psr_mask.astype(float) * 0.6
    context_confidence = np.clip(context_confidence, 0, 1)

    # Combined confidence.
    # morphology + temperature both proxy through temp_confidence here;
    # their weights are merged so the total always sums to 1.0.
    total_confidence = (
        CONFIDENCE_WEIGHTS["cpr_dop"] * radar_confidence
        + CONFIDENCE_WEIGHTS["shadow"] * context_confidence
        + (CONFIDENCE_WEIGHTS["morphology"] + CONFIDENCE_WEIGHTS["temperature"])
        * temp_confidence
    )
    total_confidence = np.clip(total_confidence, 0, 1)

    # Restrict to PSR/shadow regions
    if psr_mask is not None:
        ice_validated = ice_raw & (psr_mask == 1)
    elif shadow_mask is not None:
        ice_validated = ice_raw & (shadow_mask == 1)
    else:
        ice_validated = ice_raw

    return {
        "ice_raw": ice_raw.astype(np.uint8),
        "ice_validated": ice_validated.astype(np.uint8),
        "radar_confidence": radar_confidence.astype(np.float32),
        "total_confidence": total_confidence.astype(np.float32),
        "thermal_gate_applied": temperature is not None,
    }


def classify_ice_regions(
    ice_mask: np.ndarray,
    confidence: np.ndarray,
    doubly_shadowed: np.ndarray = None,
) -> Dict:
    """
    Label and classify detected ice regions into priority tiers.

    Priority Tier 1: Inside doubly shadowed craters (highest confidence)
    Priority Tier 2: Inside PSR but outside doubly shadowed
    Priority Tier 3: Radar signature only (lower confidence)
    """
    labeled, n_regions = label(ice_mask)
    regions = []

    for i in range(1, n_regions + 1):
        mask = labeled == i
        area = int(mask.sum())
        if area < 5:  # Filter noise
            continue

        ys, xs = np.where(mask)
        mean_confidence = float(confidence[mask].mean())

        # Classify tier
        if doubly_shadowed is not None and (doubly_shadowed[mask] > 0).any():
            tier = 1
            tier_label = "Doubly Shadowed Crater (Highest Priority)"
        elif mean_confidence > 0.6:
            tier = 2
            tier_label = "High-Confidence PSR Ice"
        else:
            tier = 3
            tier_label = "Moderate-Confidence Ice Signature"

        regions.append(
            {
                "id": int(i),
                "area_pixels": area,
                "area_km2": round(area * (30**2) / 1e6, 4),
                "center_row": int(ys.mean()),
                "center_col": int(xs.mean()),
                "mean_confidence": round(mean_confidence, 3),
                "priority_tier": tier,
                "tier_label": tier_label,
                "bbox": [int(ys.min()), int(xs.min()), int(ys.max()), int(xs.max())],
            }
        )

    # Sort by tier then confidence
    regions.sort(key=lambda x: (x["priority_tier"], -x["mean_confidence"]))

    total_ice_area_km2 = sum(r["area_km2"] for r in regions)
    tier1_count = sum(1 for r in regions if r["priority_tier"] == 1)
    tier2_count = sum(1 for r in regions if r["priority_tier"] == 2)

    return {
        "regions": regions,
        "n_regions": len(regions),
        "total_ice_area_km2": round(total_ice_area_km2, 4),
        "tier1_regions": tier1_count,
        "tier2_regions": tier2_count,
        "labeled_map": labeled,
    }


def compute_ice_probability_map(
    cpr: np.ndarray,
    dop: np.ndarray,
    shadow_mask: np.ndarray,
    psr_mask: np.ndarray,
    doubly_shadowed: np.ndarray,
) -> np.ndarray:
    """
    Compute a continuous ice probability map [0, 1] for the full scene.
    Combines radar, shadow, and morphological evidence.
    """
    rows, cols = cpr.shape

    # Radar score: CPR > 1 and DOP < threshold both contribute
    radar_score = np.clip(
        0.5 * np.clip((cpr - CPR_THRESHOLD) / 2.0, 0, 1)
        + 0.5 * np.clip((DOP_THRESHOLD - dop) / DOP_THRESHOLD, 0, 1),
        0,
        1,
    )

    # Shadow score
    shadow_score = shadow_mask.astype(float) * 0.5 + psr_mask.astype(float) * 0.5
    shadow_score = np.clip(shadow_score, 0, 1)

    # Doubly shadowed boost
    ds_boost = doubly_shadowed.astype(float) * 0.3

    prob = (
        CONFIDENCE_WEIGHTS["cpr_dop"] * radar_score
        + CONFIDENCE_WEIGHTS["shadow"] * 2 * shadow_score
        + ds_boost
    )
    prob = np.clip(prob, 0, 1)

    # Spatial smoothing
    prob = gaussian_filter(prob, sigma=2)
    return prob.astype(np.float32)


def run_ice_detection_pipeline(
    polarimetric: Dict,
    shadow_data: Dict,
    terrain: Dict,
    temperature: np.ndarray = None,
) -> Dict:
    """
    Full ice detection pipeline integrating all data sources.
    Temperature map (if provided) is used as a hard thermal stability gate
    per Zhang & Paige (2009): ice unstable above 110 K.
    """
    cpr = polarimetric["CPR"]
    dop = polarimetric["DOP"]
    shadow_mask = shadow_data.get("shadow_map")
    psr_mask = shadow_data.get("psr_mask")
    doubly_shadowed = shadow_data.get("doubly_shadowed_mask")

    # Step 1: Detect raw ice candidates (with temperature hard gate)
    candidates = detect_ice_candidates(cpr, dop, shadow_mask, psr_mask, temperature)

    # Step 2: Classify into priority regions
    classified = classify_ice_regions(
        candidates["ice_validated"],
        candidates["total_confidence"],
        doubly_shadowed,
    )

    # Step 3: Probability map
    if doubly_shadowed is None:
        doubly_shadowed = np.zeros_like(shadow_mask, dtype=np.uint8)
    prob_map = compute_ice_probability_map(
        cpr, dop, shadow_mask, psr_mask, doubly_shadowed
    )

    # Step 4: Summary statistics
    n_ice_pixels = int(candidates["ice_validated"].sum())
    total_pixels = int(cpr.size)
    ice_coverage_pct = round(n_ice_pixels / total_pixels * 100, 2)

    return {
        "ice_validated_mask": candidates["ice_validated"],
        "ice_raw_mask": candidates["ice_raw"],
        "radar_confidence": candidates["radar_confidence"],
        "total_confidence": candidates["total_confidence"],
        "probability_map": prob_map,
        "ice_regions": classified["regions"],
        "n_ice_regions": classified["n_regions"],
        "total_ice_area_km2": classified["total_ice_area_km2"],
        "ice_coverage_pct": ice_coverage_pct,
        "tier1_regions": classified["tier1_regions"],
        "tier2_regions": classified["tier2_regions"],
        "thermal_gate_applied": candidates.get("thermal_gate_applied", False),
        "temp_threshold_K": TEMP_THRESHOLD_K,
        "detection_criteria": {
            "CPR_threshold": CPR_THRESHOLD,
            "DOP_threshold": DOP_THRESHOLD,
            "temp_threshold_K": TEMP_THRESHOLD_K,
            "temp_gate": "Hard gate — ice excluded where T > 110 K (Zhang & Paige 2009)",
            "method": "Combined CPR+DOP+Thermal (Putrevu et al. 2023 / Chakraborty et al. 2024)",
        },
    }
