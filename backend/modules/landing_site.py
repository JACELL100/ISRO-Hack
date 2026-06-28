"""
Landing Site Selection Module
Multi-criteria evaluation to propose scientifically viable and safe
landing sites near doubly shadowed craters with subsurface ice.

Evaluation Criteria:
1. Terrain Safety: slope < 15°, roughness below threshold
2. Proximity to Ice: near high-probability ice regions
3. Solar Power: partial illumination for power generation
4. Scientific Value: proximity to doubly shadowed craters
5. Trafficability: accessible from landing site to target crater
"""
import numpy as np
from scipy.ndimage import gaussian_filter, label, distance_transform_edt
from typing import Dict, List, Tuple


# Weights for multi-criteria evaluation
CRITERIA_WEIGHTS = {
    "safety": 0.30,          # Landing safety (slope, roughness)
    "ice_proximity": 0.25,   # Distance to ice regions
    "solar_power": 0.20,     # Illumination availability
    "scientific": 0.15,      # Near doubly shadowed craters
    "trafficability": 0.10,  # Terrain accessibility for rover
}

# Safety thresholds
MAX_SLOPE_DEG = 15.0
MAX_ROUGHNESS_M = 0.5
MIN_ILLUMINATION = 0.1      # At least 10% average illumination for power
EXCLUSION_BUFFER_PIX = 5    # Stay away from crater rims (reduced for small scenes)


def compute_safety_score(
    slope: np.ndarray,
    roughness: np.ndarray,
    crater_mask: np.ndarray = None,
) -> np.ndarray:
    """
    Compute landing safety score [0, 1].
    0 = unsafe, 1 = perfectly safe.
    """
    rows, cols = slope.shape

    # Slope score: 1.0 at 0°, 0.0 at ≥15°
    slope_score = np.clip(1.0 - slope / MAX_SLOPE_DEG, 0, 1)

    # Roughness score
    max_rough = roughness.max() if roughness.max() > 0 else 1.0
    roughness_score = np.clip(1.0 - roughness / (max_rough * 0.5), 0, 1)

    # Combined safety
    safety = 0.6 * slope_score + 0.4 * roughness_score

    # Exclude crater interiors (danger zones)
    if crater_mask is not None:
        from scipy.ndimage import distance_transform_edt, binary_dilation
        danger_zone = binary_dilation(crater_mask.astype(bool), iterations=EXCLUSION_BUFFER_PIX)
        safety[danger_zone] = 0.0

    return safety.astype(np.float32)


def compute_ice_proximity_score(
    ice_probability: np.ndarray,
    ice_mask: np.ndarray,
    max_distance_pixels: float = 200.0,
) -> np.ndarray:
    """
    Score based on proximity to ice-bearing regions.
    Closer to ice = higher score.
    """
    if ice_mask.sum() == 0:
        # Fallback: use probability map
        return gaussian_filter(ice_probability, sigma=20)

    # Distance transform from ice regions
    dist_to_ice = distance_transform_edt(1 - ice_mask.astype(bool))
    proximity_score = np.clip(1.0 - dist_to_ice / max_distance_pixels, 0, 1)

    # Weight by ice probability at those regions
    proximity_score *= (0.5 + 0.5 * gaussian_filter(ice_probability, sigma=5))
    return proximity_score.astype(np.float32)


def compute_solar_power_score(
    mean_illumination: np.ndarray,
    shadow_mask: np.ndarray,
) -> np.ndarray:
    """
    Score based on solar illumination availability for power generation.
    Landing sites need at least partial illumination outside PSR.
    """
    # Penalize fully shadowed regions (no solar power)
    illum_score = np.clip(mean_illumination * 2, 0, 1)
    illum_score[shadow_mask == 1] *= 0.1  # Heavy penalty inside PSR
    return illum_score.astype(np.float32)


def compute_scientific_score(
    doubly_shadowed_mask: np.ndarray,
    ice_probability: np.ndarray,
    max_distance_pixels: float = 150.0,
) -> np.ndarray:
    """
    Score based on scientific value: proximity to doubly shadowed craters.
    """
    if doubly_shadowed_mask.sum() == 0:
        return gaussian_filter(ice_probability, sigma=10)

    dist_to_ds = distance_transform_edt(1 - doubly_shadowed_mask.astype(bool))
    sci_score = np.clip(1.0 - dist_to_ds / max_distance_pixels, 0, 1)
    return sci_score.astype(np.float32)


def compute_trafficability_score(
    slope: np.ndarray,
    roughness: np.ndarray,
    doubly_shadowed_mask: np.ndarray,
) -> np.ndarray:
    """
    Score based on rover accessibility: is there a traversable path
    between the candidate landing site and target crater?
    Uses inverse of terrain difficulty as proxy.
    """
    # Terrain difficulty (high slope + roughness = difficult)
    difficulty = 0.6 * np.clip(slope / 25.0, 0, 1) + 0.4 * np.clip(
        roughness / roughness.max(), 0, 1
    )
    trafficability = 1.0 - difficulty
    return gaussian_filter(trafficability, sigma=5).astype(np.float32)


def evaluate_landing_sites(
    dem: np.ndarray,
    slope: np.ndarray,
    roughness: np.ndarray,
    shadow_map: np.ndarray,
    psr_mask: np.ndarray,
    mean_illumination: np.ndarray,
    ice_probability: np.ndarray,
    ice_mask: np.ndarray,
    doubly_shadowed_mask: np.ndarray,
    crater_mask: np.ndarray = None,
    pixel_size_m: float = 30.0,
    n_sites: int = 5,
) -> Dict:
    """
    Full multi-criteria landing site evaluation.
    Returns ranked candidate landing sites with scores.
    """
    # Compute individual criterion scores
    safety = compute_safety_score(slope, roughness, crater_mask)
    ice_proximity = compute_ice_proximity_score(ice_probability, ice_mask)
    solar = compute_solar_power_score(mean_illumination, shadow_map)
    scientific = compute_scientific_score(doubly_shadowed_mask, ice_probability)
    trafficability = compute_trafficability_score(slope, roughness, doubly_shadowed_mask)

    # Weighted combination
    composite = (
        CRITERIA_WEIGHTS["safety"] * safety
        + CRITERIA_WEIGHTS["ice_proximity"] * ice_proximity
        + CRITERIA_WEIGHTS["solar_power"] * solar
        + CRITERIA_WEIGHTS["scientific"] * scientific
        + CRITERIA_WEIGHTS["trafficability"] * trafficability
    )

    # Must be outside PSR (can't land in permanent shadow)
    composite[psr_mask == 1] *= 0.05
    # Must meet minimum safety threshold
    composite[safety < 0.15] = 0.0

    # Gaussian smooth to avoid single-pixel peaks
    composite = gaussian_filter(composite, sigma=3)

    # Find top candidate sites (local maxima, well-separated)
    candidates = _find_top_sites(
        composite, safety, solar, ice_proximity, scientific,
        trafficability, dem, n_sites, min_separation_pix=30
    )

    return {
        "composite_score_map": composite.astype(np.float32),
        "safety_map": safety,
        "ice_proximity_map": ice_proximity,
        "solar_map": solar,
        "scientific_map": scientific,
        "trafficability_map": trafficability,
        "candidate_sites": candidates,
        "best_site": candidates[0] if candidates else None,
        "criteria_weights": CRITERIA_WEIGHTS,
    }


def _find_top_sites(
    composite: np.ndarray,
    safety: np.ndarray,
    solar: np.ndarray,
    ice_proximity: np.ndarray,
    scientific: np.ndarray,
    trafficability: np.ndarray,
    dem: np.ndarray,
    n_sites: int,
    min_separation_pix: int = 30,
) -> List[Dict]:
    """
    Find top-N landing sites from composite score map with spatial separation.
    """
    rows, cols = composite.shape
    remaining = composite.copy()
    sites = []

    for rank in range(n_sites):
        idx = np.unravel_index(remaining.argmax(), remaining.shape)
        r, c = int(idx[0]), int(idx[1])
        score = float(composite[r, c])

        if score < 0.01:
            break

        sites.append({
            "rank": rank + 1,
            "row": r,
            "col": c,
            "composite_score": round(score, 3),
            "safety_score": round(float(safety[r, c]), 3),
            "solar_score": round(float(solar[r, c]), 3),
            "ice_proximity_score": round(float(ice_proximity[r, c]), 3),
            "scientific_score": round(float(scientific[r, c]), 3),
            "trafficability_score": round(float(trafficability[r, c]), 3),
            "elevation_m": round(float(dem[r, c]), 1),
            "description": _describe_site(rank, score, safety[r, c], ice_proximity[r, c]),
        })

        # Zero out neighborhood to enforce separation
        r_lo = max(0, r - min_separation_pix)
        r_hi = min(rows, r + min_separation_pix)
        c_lo = max(0, c - min_separation_pix)
        c_hi = min(cols, c + min_separation_pix)
        remaining[r_lo:r_hi, c_lo:c_hi] = 0.0

    return sites


def _describe_site(rank: int, score: float, safety: float, ice_prox: float) -> str:
    if rank == 0:
        return "Primary recommended landing site — optimal balance of safety and scientific access"
    elif safety > 0.8 and ice_prox > 0.6:
        return "Safe flat terrain with excellent proximity to ice-bearing crater"
    elif safety > 0.8:
        return "High-safety backup site with good slope characteristics"
    else:
        return f"Alternative site (rank {rank + 1}) — scientifically relevant, moderate terrain"
