"""
Terrain Analysis Module
Computes slope, roughness, crater morphology, and boulder density
from DEM (LOLA/SLDEM) and OHRC imagery for landing site safety evaluation.
"""
import numpy as np
from scipy.ndimage import gaussian_filter, uniform_filter, label, maximum_filter, minimum_filter
from typing import Dict, Tuple


def compute_slope(dem: np.ndarray, pixel_size_m: float = 30.0) -> np.ndarray:
    """
    Compute terrain slope in degrees from DEM.
    Uses 2nd-order central difference (Horn's method for robustness).
    """
    grad_y, grad_x = np.gradient(dem, pixel_size_m)
    slope_rad = np.arctan(np.sqrt(grad_x**2 + grad_y**2))
    slope_deg = np.degrees(slope_rad)
    return slope_deg.astype(np.float32)


def compute_aspect(dem: np.ndarray, pixel_size_m: float = 30.0) -> np.ndarray:
    """
    Compute terrain aspect (compass direction of steepest descent).
    Returns degrees from north (0=N, 90=E, 180=S, 270=W).
    """
    grad_y, grad_x = np.gradient(dem, pixel_size_m)
    aspect = np.degrees(np.arctan2(-grad_x, grad_y))
    aspect = (aspect + 360) % 360
    return aspect.astype(np.float32)


def compute_roughness(dem: np.ndarray, window: int = 11) -> np.ndarray:
    """
    Compute terrain roughness as standard deviation of elevation in a local window.
    High roughness → hazardous surface (boulders, rough crater floor).

    Also computes the TRI (Terrain Ruggedness Index):
    TRI = mean absolute difference between center and 8 neighbors
    """
    rows, cols = dem.shape

    # Local standard deviation
    mean_sq = uniform_filter(dem**2, size=window)
    sq_mean = uniform_filter(dem, size=window) ** 2
    roughness = np.sqrt(np.maximum(mean_sq - sq_mean, 0))

    return roughness.astype(np.float32)


def compute_terrain_ruggedness_index(dem: np.ndarray) -> np.ndarray:
    """
    TRI: Root mean square difference between a cell and its neighbors.
    Riley et al. (1999)
    """
    rows, cols = dem.shape
    tri = np.zeros_like(dem)

    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            r_src = slice(max(0, dr), min(rows, rows + dr))
            c_src = slice(max(0, dc), min(cols, cols + dc))
            r_dst = slice(max(0, -dr), min(rows, rows - dr))
            c_dst = slice(max(0, -dc), min(cols, cols - dc))

            diff = dem[r_dst, c_dst] - dem[r_src, c_src]
            tri[r_dst, c_dst] += diff**2

    return np.sqrt(tri / 8).astype(np.float32)


def detect_craters(
    dem: np.ndarray, min_radius_pixels: int = 3, max_radius_pixels: int = 80
) -> Dict:
    """
    Simple crater detection using local topographic minima surrounded by rims.
    """
    # Craters are local minima with a surrounding rim
    local_min = minimum_filter(dem, size=min_radius_pixels * 2)
    local_max = maximum_filter(dem, size=max_radius_pixels * 2)

    depth = local_max - dem
    crater_floor = (depth > 50) & (dem == local_min)

    # Label detected craters
    labeled, n = label(crater_floor)
    craters = []
    for i in range(1, n + 1):
        region = labeled == i
        ys, xs = np.where(region)
        if len(ys) == 0:
            continue
        cy, cx = int(ys.mean()), int(xs.mean())
        craters.append({
            "center_row": cy,
            "center_col": cx,
            "estimated_radius_pixels": int(np.sqrt(region.sum() / np.pi)),
            "depth_m": float(depth[region].max()),
        })

    crater_mask = (labeled > 0).astype(np.uint8)
    return {"crater_mask": crater_mask, "craters": craters, "n_craters": len(craters)}


def detect_boulders(ohrc: np.ndarray, threshold_percentile: float = 92.0) -> np.ndarray:
    """
    Detect boulders from OHRC high-resolution image.
    Boulders appear as bright spots with sharp edges.
    """
    from scipy.ndimage import binary_dilation

    ohrc_float = ohrc.astype(np.float32)

    # Local contrast enhancement
    local_mean = gaussian_filter(ohrc_float, sigma=5)
    contrast = ohrc_float - local_mean

    # Threshold bright features
    thresh = np.percentile(contrast, threshold_percentile)
    boulder_mask = (contrast > thresh).astype(np.uint8)

    # Remove very small noise pixels
    labeled, n = label(boulder_mask)
    cleaned = np.zeros_like(boulder_mask)
    for i in range(1, n + 1):
        region = labeled == i
        if region.sum() >= 2:
            cleaned[region] = 1

    return cleaned


def compute_boulder_density(boulder_mask: np.ndarray, window: int = 50) -> np.ndarray:
    """
    Compute local boulder density as fraction of boulder pixels in a window.
    """
    density = uniform_filter(boulder_mask.astype(np.float32), size=window)
    return density


def analyze_crater_morphology(
    dem: np.ndarray, crater_list: list
) -> list:
    """
    Analyze crater morphology to detect lobate-rim signatures
    (indicative of subsurface ice excavation during impact).
    """
    rows, cols = dem.shape
    enhanced_craters = []

    for crater in crater_list:
        cy = crater["center_row"]
        cx = crater["center_col"]
        r = crater.get("estimated_radius_pixels", 10)

        # Extract rim region
        y_idx, x_idx = np.mgrid[
            max(0, cy - r * 2) : min(rows, cy + r * 2),
            max(0, cx - r * 2) : min(cols, cx + r * 2),
        ]
        dist = np.sqrt(
            (y_idx - cy) ** 2 + (x_idx - cx) ** 2
        )
        rim_mask = (dist > r * 0.8) & (dist < r * 1.4)

        if rim_mask.sum() < 10:
            enhanced_craters.append({**crater, "lobate_rim": False, "rim_asymmetry": 0.0})
            continue

        rim_dem = dem[
            max(0, cy - r * 2): min(rows, cy + r * 2),
            max(0, cx - r * 2): min(cols, cx + r * 2),
        ]

        # Rim asymmetry: high variance → lobate structure
        rim_elevations = rim_dem[rim_mask]
        rim_asymmetry = float(rim_elevations.std() / (rim_elevations.mean() + 1e-6))
        lobate_rim = rim_asymmetry > 0.15

        enhanced_craters.append({
            **crater,
            "lobate_rim": lobate_rim,
            "rim_asymmetry": rim_asymmetry,
            "ice_probability_morphology": min(1.0, rim_asymmetry * 3),
        })

    return enhanced_craters


def compute_full_terrain_analysis(
    dem: np.ndarray,
    ohrc: np.ndarray = None,
    pixel_size_m: float = 30.0,
) -> Dict:
    """
    Complete terrain analysis pipeline.
    """
    slope = compute_slope(dem, pixel_size_m)
    aspect = compute_aspect(dem, pixel_size_m)
    roughness = compute_roughness(dem)
    tri = compute_terrain_ruggedness_index(dem)
    crater_info = detect_craters(dem)

    result = {
        "slope": slope,
        "aspect": aspect,
        "roughness": roughness,
        "tri": tri,
        "craters": crater_info["craters"],
        "crater_mask": crater_info["crater_mask"],
        "n_craters": crater_info["n_craters"],
        "slope_stats": {
            "mean": float(slope.mean()),
            "max": float(slope.max()),
            "safe_fraction": float((slope < 15).mean()),  # <15° is typically safe
        },
    }

    if ohrc is not None:
        boulder_mask = detect_boulders(ohrc)
        boulder_density = compute_boulder_density(boulder_mask)
        result["boulder_mask"] = boulder_mask
        result["boulder_density"] = boulder_density
        result["boulder_coverage_pct"] = float(boulder_mask.mean() * 100)

    return result
