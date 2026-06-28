"""
Shadow Mapping & PSR (Permanently Shadowed Region) Detection
Models solar illumination on the lunar south polar terrain to identify
PSRs and doubly shadowed craters from DEM data.
"""
import numpy as np
from scipy.ndimage import label, binary_erosion, binary_dilation, gaussian_filter
from typing import Dict, List, Tuple


def compute_illumination(
    dem: np.ndarray,
    sun_azimuth_deg: float = 0.0,
    sun_elevation_deg: float = 1.5,
    pixel_size_m: float = 30.0,
) -> np.ndarray:
    """
    Ray-casting illumination model for low-angle solar illumination.
    Simulates solar geometry at lunar south pole.

    Args:
        dem: Digital elevation model (meters)
        sun_azimuth_deg: Solar azimuth (degrees, 0=north, 90=east)
        sun_elevation_deg: Solar elevation angle (very low at south pole, ~1-2°)
        pixel_size_m: Spatial resolution in meters per pixel

    Returns:
        illumination: Float array [0,1] where 0=fully shadowed, 1=illuminated
    """
    rows, cols = dem.shape
    sun_el_rad = np.deg2rad(sun_elevation_deg)
    sun_az_rad = np.deg2rad(sun_azimuth_deg)

    # Sun direction vector in grid coordinates
    dx = np.sin(sun_az_rad)
    dy = -np.cos(sun_az_rad)  # y increases downward in array

    illumination = np.ones((rows, cols), dtype=np.float32)

    # Determine ray direction
    step_x = dx / max(abs(dx), abs(dy)) if max(abs(dx), abs(dy)) > 0 else 0
    step_y = dy / max(abs(dx), abs(dy)) if max(abs(dx), abs(dy)) > 0 else 0

    # Cast rays for each pixel (simplified horizon scan)
    tan_el = np.tan(sun_el_rad)

    # Scan along sun direction
    n_steps = max(rows, cols)
    for step in range(1, n_steps):
        shift_x = int(round(step * step_x))
        shift_y = int(round(step * step_y))

        if abs(shift_x) >= cols and abs(shift_y) >= rows:
            break

        # Shifted DEM
        src_r_start = max(0, -shift_y)
        src_r_end = min(rows, rows - shift_y)
        src_c_start = max(0, -shift_x)
        src_c_end = min(cols, cols - shift_x)

        dst_r_start = src_r_start + shift_y
        dst_r_end = src_r_end + shift_y
        dst_c_start = src_c_start + shift_x
        dst_c_end = src_c_end + shift_x

        if src_r_end <= src_r_start or src_c_end <= src_c_start:
            continue

        horizontal_dist = step * np.sqrt(step_x**2 + step_y**2) * pixel_size_m
        if horizontal_dist == 0:
            continue

        # Minimum elevation along ray required to be illuminated
        required_elev = dem[src_r_start:src_r_end, src_c_start:src_c_end] + horizontal_dist * tan_el

        target_elev = dem[dst_r_start:dst_r_end, dst_c_start:dst_c_end]

        shadow_cond = target_elev < required_elev
        illumination[dst_r_start:dst_r_end, dst_c_start:dst_c_end] = np.where(
            shadow_cond,
            np.minimum(illumination[dst_r_start:dst_r_end, dst_c_start:dst_c_end], 0.0),
            illumination[dst_r_start:dst_r_end, dst_c_start:dst_c_end],
        )

    return illumination


def compute_multi_angle_illumination(
    dem: np.ndarray,
    n_azimuths: int = 8,
    sun_elevation_deg: float = 1.5,
    pixel_size_m: float = 30.0,
) -> Dict[str, np.ndarray]:
    """
    Compute illumination from multiple solar azimuths to identify PSRs.
    Pixels shadowed from ALL directions → Permanently Shadowed Region (PSR).
    """
    rows, cols = dem.shape
    total_illumination = np.zeros((rows, cols), dtype=np.float32)
    azimuths = np.linspace(0, 360, n_azimuths, endpoint=False)

    illumination_stack = []
    for az in azimuths:
        illum = compute_illumination(dem, az, sun_elevation_deg, pixel_size_m)
        illumination_stack.append(illum)
        total_illumination += illum

    # PSR: never illuminated from any direction
    mean_illumination = total_illumination / n_azimuths
    shadow_map = (mean_illumination < 0.1).astype(np.uint8)

    # Additional PSR identification from topography: very deep relative lows
    local_mean = gaussian_filter(dem, sigma=20)
    deep_floor = (dem < local_mean - 400).astype(np.uint8)
    shadow_map = np.clip(shadow_map + deep_floor, 0, 1).astype(np.uint8)

    return {
        "shadow_map": shadow_map,
        "mean_illumination": mean_illumination,
        "illumination_stack": np.array(illumination_stack),
    }


def identify_psr_regions(
    shadow_map: np.ndarray, min_area_pixels: int = 20, max_area_pixels: int = 100000
) -> Dict[str, np.ndarray]:
    """
    Label and characterize PSR regions from the shadow map.
    """
    labeled, n_regions = label(shadow_map)
    psr_mask = np.zeros_like(shadow_map, dtype=np.uint8)
    psr_info = []

    for i in range(1, n_regions + 1):
        region = labeled == i
        area = region.sum()
        if min_area_pixels <= area <= max_area_pixels:
            psr_mask[region] = 1
            ys, xs = np.where(region)
            psr_info.append({
                "id": int(i),
                "area_pixels": int(area),
                "center_row": int(ys.mean()),
                "center_col": int(xs.mean()),
                "bbox": [int(ys.min()), int(xs.min()), int(ys.max()), int(xs.max())],
            })

    # Fallback: if no PSRs found via shadow map, use topographic lows
    if not psr_info:
        # Shadow map itself is the best proxy for PSR when no large regions are found
        psr_mask = shadow_map.copy()
        labeled2, n2 = label(psr_mask)
        for i in range(1, n2 + 1):
            region = labeled2 == i
            area = region.sum()
            if area >= 5:
                ys, xs = np.where(region)
                psr_info.append({
                    "id": int(i),
                    "area_pixels": int(area),
                    "center_row": int(ys.mean()),
                    "center_col": int(xs.mean()),
                    "bbox": [int(ys.min()), int(xs.min()), int(ys.max()), int(xs.max())],
                })

    return {"psr_mask": psr_mask, "psr_regions": psr_info, "n_psrs": len(psr_info)}


def identify_doubly_shadowed_craters(
    psr_mask: np.ndarray,
    dem: np.ndarray,
    shadow_map: np.ndarray,
    min_depth_m: float = 80.0,
) -> Dict[str, np.ndarray]:
    """
    Identify doubly shadowed craters: small deep sub-craters WITHIN PSRs.
    Uses fine-scale local topography to find crater bowls.
    """
    from scipy.ndimage import minimum_filter, maximum_filter

    rows, cols = dem.shape

    # Fine-scale local depth: compare 5px neighborhood (finds crater bowl shape)
    # This finds pixels that are locally LOW (crater floors)
    sz_small = max(3, min(rows, cols) // 40)
    sz_large = max(7, min(rows, cols) // 20)
    local_min_small = minimum_filter(dem, size=sz_small)
    local_max_ring = maximum_filter(dem, size=sz_large)

    # A pixel is a crater floor if it's significantly below its wider neighborhood
    local_depth = local_max_ring - dem

    # Search within PSR if available, else shadow, else all
    search_mask = (
        psr_mask if psr_mask.sum() > 0
        else shadow_map if shadow_map.sum() > 0
        else np.ones_like(psr_mask)
    )

    # Also identify peaks (crater rims) to find transitions rim->floor
    local_mean = (local_max_ring + local_min_small) / 2
    crater_floor = (dem < local_mean - min_depth_m * 0.3) & (search_mask == 1)

    # Use distance from local minimum: pixels near local minima with steep surroundings
    # Primary: pixels with high local_depth within search mask
    candidate = (local_depth > min_depth_m) & crater_floor

    # If nothing found, relax threshold
    if candidate.sum() == 0:
        candidate = (local_depth > min_depth_m * 0.4) & (search_mask == 1)
    if candidate.sum() == 0:
        candidate = local_depth > min_depth_m * 0.3

    labeled, n = label(candidate)
    doubly_shadowed = np.zeros_like(shadow_map, dtype=np.uint8)
    crater_info = []
    min_sz = 4
    # Max size: no bigger than ~10% of scene (avoids entire PSR being one region)
    max_sz = max(100, rows * cols // 100)

    for i in range(1, n + 1):
        region = labeled == i
        area = region.sum()
        if min_sz <= area <= max_sz:
            doubly_shadowed[region] = 1
            ys, xs = np.where(region)
            center_r, center_c = int(ys.mean()), int(xs.mean())
            crater_depth = float(local_depth[region].max())
            crater_info.append({
                "id": int(i),
                "center_row": center_r,
                "center_col": center_c,
                "area_pixels": int(area),
                "max_depth_m": round(crater_depth, 1),
                "min_elevation_m": round(float(dem[region].min()), 1),
                "priority_score": round(crater_depth / 100.0 * np.sqrt(area), 2),
            })

    crater_info.sort(key=lambda x: x["priority_score"], reverse=True)

    return {
        "doubly_shadowed_mask": doubly_shadowed,
        "crater_list": crater_info,
        "n_craters": len(crater_info),
    }


def compute_thermal_environment(
    shadow_map: np.ndarray, illumination: np.ndarray
) -> np.ndarray:
    """
    Estimate surface temperature distribution.
    PSRs: ~25-40 K (ice preservation), illuminated: ~200-400 K
    """
    temp = np.zeros_like(illumination)
    # Illuminated regions: 200-400 K based on illumination intensity
    temp = illumination * 200 + 200
    # PSR regions: 25-40 K (below water ice stability threshold)
    temp[shadow_map == 1] = 25 + np.random.default_rng(0).uniform(
        0, 15, shadow_map.sum()
    )
    return np.clip(temp, 25, 400).astype(np.float32)
