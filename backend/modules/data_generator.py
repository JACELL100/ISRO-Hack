"""
Synthetic Lunar Data Generator
Generates realistic synthetic Chandrayaan-2 DFSAR and OHRC-like data
for demonstration when real data is not loaded.

Designed to always produce PSRs, doubly shadowed craters, and ice signatures
regardless of scene size.
"""
import numpy as np
from scipy.ndimage import gaussian_filter, label, minimum_filter, binary_dilation
from typing import Dict, Tuple


def generate_dem(rows: int = 256, cols: int = 256, seed: int = 42) -> np.ndarray:
    """
    Generate a realistic lunar south polar DEM with guaranteed PSR-containing craters.
    Returns elevation in meters.
    """
    rng = np.random.default_rng(seed)

    # Fractal terrain (multiple octaves)
    dem = np.zeros((rows, cols))
    amplitude, frequency = 1.0, 1.0
    for _ in range(7):
        noise = rng.standard_normal((rows, cols))
        sigma = max(1, rows / (frequency * 4))
        dem += amplitude * gaussian_filter(noise, sigma=sigma)
        amplitude *= 0.5
        frequency *= 2.0

    # Scale to realistic lunar south polar elevations
    dem = (dem - dem.min()) / (dem.max() - dem.min() + 1e-8)
    dem = dem * 4000 - 2000  # -2000m to +2000m

    # Carve craters — scaled to scene size
    # PSR craters (large, permanently shadowed)
    psr_craters = [
        (rows * 0.50, cols * 0.50, min(rows, cols) * 0.22, -1800),  # Shackleton-like, center
        (rows * 0.75, cols * 0.25, min(rows, cols) * 0.14, -1200),  # Secondary PSR
        (rows * 0.25, cols * 0.75, min(rows, cols) * 0.12, -1000),  # Third PSR
    ]
    y_idx, x_idx = np.mgrid[0:rows, 0:cols]
    for (cy, cx, r, depth) in psr_craters:
        dist = np.sqrt((y_idx - cy) ** 2 + (x_idx - cx) ** 2)
        bowl = np.clip(1.0 - (dist / r) ** 2, 0, 1)
        dem -= bowl * abs(depth)

    # Carve doubly-shadowed craters inside PSRs (small, very deep)
    ds_craters = [
        (rows * 0.50, cols * 0.50, min(rows, cols) * 0.055, -600),
        (rows * 0.47, cols * 0.54, min(rows, cols) * 0.040, -450),
        (rows * 0.75, cols * 0.25, min(rows, cols) * 0.045, -500),
        (rows * 0.25, cols * 0.75, min(rows, cols) * 0.038, -400),
    ]
    for (cy, cx, r, depth) in ds_craters:
        dist = np.sqrt((y_idx - cy) ** 2 + (x_idx - cx) ** 2)
        bowl = np.clip(1.0 - (dist / r) ** 2, 0, 1)
        dem -= bowl * abs(depth)

    return gaussian_filter(dem, sigma=1.2).astype(np.float32)


def generate_shadow_map(dem: np.ndarray, sun_elevation_deg: float = 1.5) -> np.ndarray:
    """
    Compute shadow mask using topographic horizon ray-casting.
    At lunar south pole, sun stays near horizon (1.5° elevation).
    """
    rows, cols = dem.shape
    shadow = np.zeros((rows, cols), dtype=np.uint8)
    sun_el_rad = np.deg2rad(sun_elevation_deg)
    pixel_size_m = 30.0
    slope_threshold = np.tan(sun_el_rad)

    # Ray-cast from right edge (sun from east)
    for r in range(rows):
        max_horizon = -np.inf
        for c in range(cols - 1, -1, -1):
            dist_from_edge = (cols - 1 - c) * pixel_size_m
            if dist_from_edge == 0:
                max_horizon = -np.inf
                continue
            horizon_angle = (dem[r, cols - 1] - dem[r, c]) / dist_from_edge
            if horizon_angle > max_horizon:
                max_horizon = horizon_angle
            if max_horizon > slope_threshold:
                shadow[r, c] = 1

    # Also shadow deep crater floors directly (below mean - 1200m)
    floor_threshold = dem.mean() - 1200
    shadow[dem < floor_threshold] = 1

    # Smooth edges slightly
    shadow = binary_dilation(shadow.astype(bool), iterations=1).astype(np.uint8)
    return shadow


def generate_psr_mask(shadow_map: np.ndarray, min_area: int = 30) -> np.ndarray:
    """
    Permanently Shadowed Regions = large connected shadow areas.
    """
    labeled, n_features = label(shadow_map)
    psr_mask = np.zeros_like(shadow_map)
    for i in range(1, n_features + 1):
        if (labeled == i).sum() >= min_area:
            psr_mask[labeled == i] = 1

    # Guarantee at least one PSR: mark the deepest region if none found
    if psr_mask.sum() == 0:
        rows, cols = shadow_map.shape
        # Mark center crater floor
        cy, cx = rows // 2, cols // 2
        r = min(rows, cols) // 6
        y_idx, x_idx = np.mgrid[0:rows, 0:cols]
        dist = np.sqrt((y_idx - cy)**2 + (x_idx - cx)**2)
        psr_mask[dist < r] = 1

    return psr_mask.astype(np.uint8)


def generate_doubly_shadowed_craters(psr_mask: np.ndarray, dem: np.ndarray) -> np.ndarray:
    """
    Doubly shadowed craters: small deep depressions within PSRs.
    """
    rows, cols = dem.shape
    # Find local minima within PSR
    local_min = minimum_filter(dem, size=max(5, min(rows, cols) // 20))
    depth_below_local = dem - local_min

    deep_spots = (depth_below_local < -150) & (psr_mask == 1)
    doubly_shadowed = np.zeros((rows, cols), dtype=np.uint8)
    doubly_shadowed[deep_spots] = 1

    labeled, n = label(doubly_shadowed)
    result = np.zeros_like(doubly_shadowed)
    min_sz = 5
    max_sz = max(50, rows * cols // 200)
    for i in range(1, n + 1):
        region = labeled == i
        sz = region.sum()
        if min_sz <= sz <= max_sz:
            result[region] = 1

    # Guarantee at least 2 doubly shadowed craters
    if result.sum() == 0:
        for (cy_f, cx_f, r) in [(0.50, 0.50, 0.05), (0.47, 0.54, 0.04), (0.75, 0.25, 0.04)]:
            cy = int(cy_f * rows)
            cx = int(cx_f * cols)
            rad = int(r * min(rows, cols))
            y_idx, x_idx = np.mgrid[0:rows, 0:cols]
            dist = np.sqrt((y_idx - cy)**2 + (x_idx - cx)**2)
            result[dist < rad] = 1

    return result


def generate_dfsar_data(
    rows: int = 256, cols: int = 256,
    psr_mask: np.ndarray = None,
    doubly_shadowed: np.ndarray = None,
    seed: int = 42,
) -> Dict[str, np.ndarray]:
    """
    Generate synthetic DFSAR full polarimetric scattering matrix.
    Ice regions: high CPR (>1), low DOP (<0.13) — Putrevu et al. 2023.
    """
    rng = np.random.default_rng(seed)

    def cx_noise(shape, scale=1.0):
        return (rng.normal(0, scale, shape) + 1j * rng.normal(0, scale, shape)).astype(np.complex64)

    # Base: surface rock scattering
    S_HH = cx_noise((rows, cols), 0.70)
    S_HV = cx_noise((rows, cols), 0.18)
    S_VH = cx_noise((rows, cols), 0.18)
    S_VV = cx_noise((rows, cols), 0.65)

    if psr_mask is not None:
        # PSR regions: moderate ice signature
        ice = psr_mask.astype(bool)
        n = int(ice.sum())
        if n > 0:
            S_HV[ice] += cx_noise((n,), 0.35)
            S_VH[ice] += cx_noise((n,), 0.35)
            # Reduce co-pol correlation → lower DOP
            S_VV[ice] *= np.exp(1j * rng.uniform(0, np.pi, n)).astype(np.complex64)

    if doubly_shadowed is not None:
        # Doubly shadowed craters: strongest ice signature
        ds = doubly_shadowed.astype(bool)
        n = int(ds.sum())
        if n > 0:
            S_HV[ds] += cx_noise((n,), 0.65)
            S_VH[ds] += cx_noise((n,), 0.65)
            S_HH[ds] *= 0.75
            S_VV[ds] *= 0.70
            S_VV[ds] *= np.exp(1j * rng.uniform(0, 2 * np.pi, n)).astype(np.complex64)

    return {"S_HH": S_HH, "S_HV": S_HV, "S_VH": S_VH, "S_VV": S_VV}


def generate_dfsar_sband(
    rows: int = 256, cols: int = 256,
    psr_mask: np.ndarray = None,
    doubly_shadowed: np.ndarray = None,
    l_band_data: Dict = None,
    seed: int = 43,
) -> Dict[str, np.ndarray]:
    """
    Generate synthetic S-band (2.5 GHz, ~9 cm) DFSAR scattering matrix.

    S-band differences vs L-band:
    - Shallower penetration (~1-2 m vs ~5 m) → weaker volumetric ice signal
    - More sensitive to cm-scale surface roughness → rocky terrain has higher CPR_S
    - Ice signature is present but slightly lower CPR_S than L-band
    - This frequency contrast is key to discriminating ice from rough terrain

    Reference: Chandrayaan-2 DFSAR dual-frequency design (S-band: 2.5 GHz)
    """
    rng = np.random.default_rng(seed)

    def cx_noise(shape, scale=1.0):
        return (rng.normal(0, scale, shape) + 1j * rng.normal(0, scale, shape)).astype(np.complex64)

    # S-band base: similar rock scattering but with more surface roughness sensitivity
    # Rocky terrain has slightly higher S-band cross-pol due to surface roughness
    S_HH = cx_noise((rows, cols), 0.72)
    S_HV = cx_noise((rows, cols), 0.22)  # Slightly higher HV due to surface roughness
    S_VH = cx_noise((rows, cols), 0.22)
    S_VV = cx_noise((rows, cols), 0.67)

    if psr_mask is not None:
        # PSR ice: S-band sees shallower ice → weaker signature than L-band
        ice = psr_mask.astype(bool)
        n = int(ice.sum())
        if n > 0:
            S_HV[ice] += cx_noise((n,), 0.25)  # Weaker than L-band (0.35)
            S_VH[ice] += cx_noise((n,), 0.25)
            S_VV[ice] *= np.exp(1j * rng.uniform(0, np.pi * 0.8, n)).astype(np.complex64)

    if doubly_shadowed is not None:
        # Doubly shadowed craters: strong ice signature in both bands
        # S-band still shows elevated CPR due to near-surface ice layer
        ds = doubly_shadowed.astype(bool)
        n = int(ds.sum())
        if n > 0:
            S_HV[ds] += cx_noise((n,), 0.50)  # Strong but < L-band (0.65)
            S_VH[ds] += cx_noise((n,), 0.50)
            S_HH[ds] *= 0.80
            S_VV[ds] *= 0.75
            S_VV[ds] *= np.exp(1j * rng.uniform(0, 2 * np.pi, n)).astype(np.complex64)

    # Optionally add correlated noise with L-band to simulate real sensor correlation
    if l_band_data is not None:
        corr_factor = 0.15  # 15% correlated noise between bands
        S_HH += cx_noise((rows, cols), corr_factor)
        S_VV += cx_noise((rows, cols), corr_factor)

    return {"S_HH": S_HH, "S_HV": S_HV, "S_VH": S_VH, "S_VV": S_VV}


def generate_ohrc_image(dem: np.ndarray, shadow_map: np.ndarray, seed: int = 42) -> np.ndarray:
    """
    Synthetic OHRC grayscale image: albedo + slope shading + shadow darkening.
    """
    rng = np.random.default_rng(seed)
    rows, cols = dem.shape
    noise = rng.standard_normal((rows, cols))
    albedo = gaussian_filter(noise, sigma=3) * 0.04 + 0.12
    albedo = np.clip(albedo, 0.05, 0.30)
    grad_y, grad_x = np.gradient(dem)
    slope = np.sqrt(grad_x**2 + grad_y**2)
    shading = 1.0 - np.clip(slope / (slope.max() + 1e-8), 0, 0.75)
    image = albedo * shading
    image[shadow_map == 1] *= 0.08
    return np.clip(image * 255, 0, 255).astype(np.uint8)


def generate_full_scene(rows: int = 256, cols: int = 256) -> Dict:
    """
    Generate complete synthetic lunar south polar scene.
    All data layers needed by the analysis pipeline.
    """
    print("Generating synthetic DEM...")
    dem = generate_dem(rows, cols)

    print("Computing shadow map...")
    shadow_map = generate_shadow_map(dem)

    print("Identifying PSRs...")
    psr_mask = generate_psr_mask(shadow_map)

    print("Identifying doubly shadowed craters...")
    doubly_shadowed = generate_doubly_shadowed_craters(psr_mask, dem)

    print(f"  PSR pixels: {psr_mask.sum()} | DS pixels: {doubly_shadowed.sum()}")

    print("Generating DFSAR data...")
    dfsar = generate_dfsar_data(rows, cols, psr_mask, doubly_shadowed)

    print("Generating S-band DFSAR data...")
    dfsar_sband = generate_dfsar_sband(rows, cols, psr_mask, doubly_shadowed, l_band_data=dfsar)

    print("Generating OHRC image...")
    ohrc = generate_ohrc_image(dem, shadow_map)

    return {
        "dem": dem,
        "shadow_map": shadow_map,
        "psr_mask": psr_mask,
        "doubly_shadowed": doubly_shadowed,
        "dfsar": dfsar,
        "dfsar_sband": dfsar_sband,
        "ohrc": ohrc,
        "metadata": {
            "rows": rows,
            "cols": cols,
            "pixel_size_m": 30.0,
            "center_lat": -89.5,
            "center_lon": 0.0,
            "sun_elevation_deg": 1.5,
            "l_band_freq_MHz": 430,
            "s_band_freq_GHz": 2.5,
            "l_band_wavelength_cm": 24,
            "s_band_wavelength_cm": 9,
        },
    }
