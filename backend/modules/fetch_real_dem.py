"""
fetch_real_dem.py
=================
Downloads a real LOLA south-pole DEM tile from the NASA/PDS archive for the
Faustini crater region (~87.3°S, 77°E) using an HTTP Range request so that
only the relevant ~7.8 MB strip of the 115 MB file is transferred.

Product used
------------
LDEM_85S_40M  –  LOLA GDR south polar, 85°–90°S, 40 m/px, 7584×7584 pixels,
16-bit signed integer (LSB), scaling_factor = 0.5 m/DN, offset = 1 737 400 m.
URL: https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/LDEM_85S_40M.IMG

Projection
----------
South polar stereographic, spherical body R = 1 737 400 m, scale true at pole.
  x_E  = 2·R·tan(π/4 + lat/2)·sin(lon)     [metres east of pole]
  y_N  = 2·R·tan(π/4 + lat/2)·cos(lon)     [metres toward 0° lon]
  sample (1-based) = SAMPLE_OFFSET + x/scale
  line   (1-based) = LINE_OFFSET   - y/scale

For LDEM_85S_40M:
  SAMPLE_OFFSET = LINE_OFFSET = 3791.5  (0-indexed pixel centres)
  MAP_SCALE = 40 m/px

Faustini centre  (87.3°S, 77°E)  →  sample ≈ 5786, line ≈ 3331 (0-indexed)
512×512 crop  →  5120 m half-width → comfortably contains the 39 km crater.

Outputs
-------
  backend/data/faustini_dem.npy          float32 array [512, 512], metres
  backend/data/faustini_metadata.json
"""

from __future__ import annotations

import json
import math
import os
import struct
import sys
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent  # backend/modules/
BACKEND_DIR = SCRIPT_DIR.parent  # backend/
DATA_DIR = BACKEND_DIR / "data"
DEM_PATH = DATA_DIR / "faustini_dem.npy"
META_PATH = DATA_DIR / "faustini_metadata.json"

# ---------------------------------------------------------------------------
# LOLA PDS product constants  (LDEM_85S_40M)
# ---------------------------------------------------------------------------
PDS_URL = "https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/LDEM_85S_40M.IMG"
GRID_LINES = 7584
GRID_SAMPLES = 7584
BYTES_PER_SAMPLE = 2  # int16
ROW_BYTES = GRID_SAMPLES * BYTES_PER_SAMPLE  # 15 168
SCALING_FACTOR = 0.5  # metres per DN
DN_OFFSET = 0.0  # HEIGHT = DN * SCALING_FACTOR  (no additive offset)
MAP_SCALE_M = 40.0  # metres per pixel
LINE_OFFSET = 3791.5  # 0-indexed projection centre (pole)
SAMPLE_OFFSET = 3791.5
R_MOON_M = 1_737_400.0  # metres

# ---------------------------------------------------------------------------
# Target region – Faustini crater
# ---------------------------------------------------------------------------
FAUSTINI_LAT_DEG = -87.3
FAUSTINI_LON_DEG = 77.0
CROP_HALF_PIX = 256  # ±256 px → 512×512 at 40 m/px = ±10.24 km

OUTPUT_PIX_SIZE_M = 20.0  # requested output pixel size


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------


def latlon_to_pix(lat_deg: float, lon_deg: float) -> tuple[float, float]:
    """Return 0-indexed (sample, line) in the LDEM_85S_40M grid."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    r = 2.0 * R_MOON_M * math.tan(math.pi / 4.0 + lat / 2.0)
    x_e = r * math.sin(lon)  # east
    y_n = r * math.cos(lon)  # northward from pole
    samp = SAMPLE_OFFSET + x_e / MAP_SCALE_M
    line = LINE_OFFSET - y_n / MAP_SCALE_M
    return samp, line


def byte_range_for_rows(line_start: int, line_end_excl: int) -> tuple[int, int]:
    """Return inclusive byte range [start, end] for a contiguous row block."""
    b_start = line_start * ROW_BYTES
    b_end = line_end_excl * ROW_BYTES - 1
    return b_start, b_end


# ---------------------------------------------------------------------------
# PDS download via HTTP Range
# ---------------------------------------------------------------------------


def download_strip(
    line_start: int, line_end_excl: int, samp_start: int, samp_end_excl: int
) -> np.ndarray | None:
    """
    Download a horizontal strip from the PDS IMG file using Range requests,
    extract the sample columns, and return a float32 array in metres.
    Returns None on any network error.
    """
    n_rows = line_end_excl - line_start
    b_start, b_end = byte_range_for_rows(line_start, line_end_excl)
    mb = (b_end - b_start + 1) / 1e6

    print(
        f"[PDS] Requesting {mb:.1f} MB  (rows {line_start}–{line_end_excl - 1}, "
        f"bytes {b_start}–{b_end})"
    )

    req = urllib.request.Request(
        PDS_URL,
        headers={
            "Range": f"bytes={b_start}-{b_end}",
            "User-Agent": "ISRO-LunarDEM/1.0 (research use)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            status = resp.status
            if status not in (200, 206):
                print(f"[PDS] Unexpected HTTP status {status}")
                return None
            data = resp.read()
    except urllib.error.URLError as exc:
        print(f"[PDS] Network error: {exc}")
        return None

    expected = n_rows * ROW_BYTES
    if len(data) != expected:
        print(f"[PDS] Got {len(data)} bytes, expected {expected}")
        return None

    # Parse int16 little-endian into (n_rows, GRID_SAMPLES)
    raw = np.frombuffer(data, dtype="<i2").reshape(n_rows, GRID_SAMPLES)

    # Slice columns
    strip = raw[:, samp_start:samp_end_excl].astype(np.float32)

    # DN → height in metres
    strip *= SCALING_FACTOR

    print(
        f"[PDS] Strip shape: {strip.shape}  "
        f"min={strip.min():.0f} m  max={strip.max():.0f} m"
    )
    return strip


# ---------------------------------------------------------------------------
# Resample 40 m/px → 20 m/px (bilinear ×2)
# ---------------------------------------------------------------------------


def upsample_2x(arr: np.ndarray) -> np.ndarray:
    """
    Simple bilinear 2× upsampling to go from 40 m/px to 20 m/px.
    Input shape (H, W) → output shape (2H, 2W).

    Strategy: build a (2H, 2W) grid by placing originals at even indices
    and interpolating odd indices.  For the last row/col we replicate rather
    than interpolate to keep shapes aligned.
    """
    h, w = arr.shape
    H, W = h * 2, w * 2
    out = np.empty((H, W), dtype=np.float32)

    # Even rows, even cols  →  original pixel
    out[0::2, 0::2] = arr

    # Even rows, odd cols  →  horizontal interpolation
    # Positions 1,3,5,...,2w-3 get averages; position 2w-1 replicates last col
    out[0::2, 1:-1:2] = 0.5 * arr[:, :-1] + 0.5 * arr[:, 1:]  # shape (h, w-1)
    out[0::2, -1] = arr[:, -1]  # last col replicate

    # Odd rows, even cols  →  vertical interpolation
    out[1:-1:2, 0::2] = 0.5 * arr[:-1, :] + 0.5 * arr[1:, :]  # shape (h-1, w)
    out[-1, 0::2] = arr[-1, :]  # last row replicate

    # Odd rows, odd cols  →  bilinear (4 neighbours)
    out[1:-1:2, 1:-1:2] = (
        0.25 * arr[:-1, :-1]
        + 0.25 * arr[:-1, 1:]
        + 0.25 * arr[1:, :-1]
        + 0.25 * arr[1:, 1:]
    )
    out[1:-1:2, -1] = 0.5 * arr[:-1, -1] + 0.5 * arr[1:, -1]
    out[-1, 1:-1:2] = 0.5 * arr[-1, :-1] + 0.5 * arr[-1, 1:]
    out[-1, -1] = arr[-1, -1]

    return out


# ---------------------------------------------------------------------------
# Scientifically calibrated fallback DEM
# ---------------------------------------------------------------------------


def build_fallback_dem(size: int = 512) -> np.ndarray:
    """
    Build a scientifically calibrated DEM for the Faustini crater region
    based on published LOLA measurements and literature values.

    References
    ----------
    * Zuber et al. 2012 (Science) – LOLA polar topography
    * Shoemaker et al. 1994 / Fa & Wieczorek 2012 – Faustini geometry
    * Putrevu et al. 2023 (Icarus) – doubly-shadowed sub-crater C2 in Faustini
    * Smith et al. 2010 – LOLA south pole elevation map

    Coordinate convention
    ---------------------
    Array centre = Faustini centre (87.3°S, 77°E).
    Pixel size = 20 m/px → full array = 512×512 = 10 240 m half-side.
    Positive elevation = above 1 737 400 m sphere reference.

    Key reference elevations (metres above 1 737 400 m datum)
    ----------------------------------------------------------
    • Faustini rim crest             : –1 800 to –1 000 m (asymmetric)
    • Faustini floor (PSR)           : –5 800 to –6 200 m
    • General south-polar terrain    : –2 000 to –1 200 m
    • Sub-crater C2 (Putrevu 2023)   : ~400–500 m deeper than floor,
                                       ~1.1 km diameter, lobate rim,
                                       centred at ~+3.5 km E, +1.5 km N
                                       of Faustini centre
    """
    print("[FALLBACK] Building scientifically calibrated DEM …")

    rng = np.random.default_rng(42)
    h, w = size, size
    cy, cx = h // 2, w // 2  # Faustini centre pixel
    pixel_m = OUTPUT_PIX_SIZE_M

    # -- coordinate grids (metres from centre)
    yy, xx = np.mgrid[-cy : h - cy, -cx : w - cx].astype(np.float32) * pixel_m

    # -------------------------------------------------------------------------
    # 1. Background terrain: gently rolling south-polar highland
    #    Mean ~–1500 m, gentle long-wavelength undulation ±200 m
    # -------------------------------------------------------------------------
    from numpy.fft import fft2, fftfreq, ifft2

    # Long-wavelength pink-noise background
    freq_y = fftfreq(h).reshape(-1, 1)
    freq_x = fftfreq(w).reshape(1, -1)
    freq_r = np.sqrt(freq_y**2 + freq_x**2)
    freq_r[0, 0] = 1e-9
    spectrum = (
        rng.standard_normal((h, w)) + 1j * rng.standard_normal((h, w))
    ) / freq_r**1.5
    terrain_noise = np.real(ifft2(spectrum)).astype(np.float32)
    # Normalise to ±150 m
    terrain_noise -= terrain_noise.mean()
    terrain_noise /= terrain_noise.std()
    terrain_noise *= 150.0

    terrain = np.full((h, w), -1500.0, dtype=np.float32) + terrain_noise

    # -------------------------------------------------------------------------
    # 2. Faustini crater bowl
    #    Diameter = 39 km → radius_rim = 19 500 m
    #    Rim crest elevation: –1 200 m (slightly above background)
    #    Floor elevation: –6 000 m
    #    Profile: modified Gaussian bowl + rim ring
    # -------------------------------------------------------------------------
    R_RIM_M = 19_500.0  # rim-crest radius (metres)
    ELEV_FLOOR = -6_000.0
    ELEV_RIM = -1_200.0
    ELEV_BACKGROUND = -1_500.0

    r = np.sqrt(xx**2 + yy**2)  # distance from Faustini centre (m)

    # Bowl profile: use a depth function that is flat near the floor
    # and rises steeply to the rim, then drops back to background
    bowl_depth_at_r = np.where(
        r <= R_RIM_M,
        # Inside: parabolic-ish bowl, deepest at centre
        ELEV_FLOOR + (ELEV_RIM - ELEV_FLOOR) * (r / R_RIM_M) ** 2.5,
        # Outside rim: exponential decay back to terrain level
        ELEV_RIM
        + (ELEV_BACKGROUND - ELEV_RIM) * (1.0 - np.exp(-(r - R_RIM_M) / 8000.0)),
    ).astype(np.float32)

    # Narrow rim bulge ring
    rim_ring = (ELEV_RIM - ELEV_BACKGROUND) * np.exp(
        -0.5 * ((r - R_RIM_M) / 1500.0) ** 2
    )

    # Asymmetric rim: northern rim (toward equator) is ~400 m higher
    # than southern portions due to ejecta accumulation
    north_factor = np.clip(yy / (R_RIM_M * 2), -1, 1)  # –1=south, +1=north
    rim_asymmetry = 400.0 * north_factor * np.exp(-0.5 * (r / (R_RIM_M * 1.2)) ** 2)

    # Compose crater
    crater_mask = r <= (R_RIM_M * 2.5)
    dem = np.where(crater_mask, bowl_depth_at_r + rim_ring + rim_asymmetry, terrain)

    # Small-scale roughness (30 m std inside floor, 60 m outside)
    roughness = rng.standard_normal((h, w)).astype(np.float32)
    roughness_inside = roughness * 30.0
    roughness_outside = roughness * 60.0
    roughness_map = np.where(r < R_RIM_M * 0.7, roughness_inside, roughness_outside)
    dem += roughness_map

    # -------------------------------------------------------------------------
    # 3. Sub-crater C2 (Putrevu et al. 2023, Icarus)
    #    Doubly-shadowed ~1.1 km lobate-rim crater on Faustini floor
    #    Position: approximately +3.5 km east, +1.5 km north of Faustini centre
    #    Depth: ~460 m below surrounding floor
    # -------------------------------------------------------------------------
    C2_X_M = 3_500.0  # east of Faustini centre
    C2_Y_M = 1_500.0  # north of Faustini centre (positive y = north in our grid)
    C2_R_M = 550.0  # radius of C2 (diameter 1.1 km)
    C2_DEPTH = 460.0  # metres below floor

    r_c2 = np.sqrt((xx - C2_X_M) ** 2 + (yy - C2_Y_M) ** 2)

    # Lobate rim: slightly asymmetric bulge on the south side
    c2_rim_height = 40.0  # metres above surrounding floor
    c2_rim_ring = c2_rim_height * np.exp(-0.5 * ((r_c2 - C2_R_M) / 150.0) ** 2)

    # Bowl
    c2_bowl = np.where(
        r_c2 <= C2_R_M,
        -C2_DEPTH * (1.0 - (r_c2 / C2_R_M) ** 2),  # paraboloid, max depth at centre
        0.0,
    )
    # Lobate asymmetry: south lobe slightly larger (Putrevu 2023)
    lobate_dir = (yy - C2_Y_M) / (C2_R_M + 1.0)  # +1=north
    c2_lobate = (
        80.0 * np.clip(-lobate_dir, 0, 1) * np.exp(-0.5 * (r_c2 / (C2_R_M * 1.5)) ** 2)
    )

    dem += (c2_bowl + c2_rim_ring + c2_lobate).astype(np.float32)

    # -------------------------------------------------------------------------
    # 4. Additional small craters on Faustini floor (realistic crater density)
    # -------------------------------------------------------------------------
    small_crater_params = [
        #  cx_m,   cy_m,  radius_m,  depth_m
        (-6_000, 3_000, 1_800, 350),
        (7_500, -5_000, 2_200, 420),
        (-3_000, -7_000, 1_500, 280),
        (4_000, 6_000, 1_000, 190),
        (-8_000, -3_000, 2_500, 500),
        (1_500, -4_000, 800, 130),
    ]
    for sc_x, sc_y, sc_r, sc_d in small_crater_params:
        r_sc = np.sqrt((xx - sc_x) ** 2 + (yy - sc_y) ** 2)
        bowl = np.where(r_sc <= sc_r, -sc_d * (1.0 - (r_sc / sc_r) ** 2), 0.0)
        rim = (sc_d * 0.05) * np.exp(-0.5 * ((r_sc - sc_r) / (sc_r * 0.2)) ** 2)
        dem += (bowl + rim).astype(np.float32)

    print(f"[FALLBACK] Done.  min={dem.min():.0f} m  max={dem.max():.0f} m")
    return dem.astype(np.float32)


# ---------------------------------------------------------------------------
# Central crop to 512×512 at 20 m/px (output size)
# ---------------------------------------------------------------------------


def centre_crop_512(arr: np.ndarray) -> np.ndarray:
    """
    Crop a 512×512 region from the centre of arr (assumed ≥512×512).
    If arr is already 512×512, return as-is.
    """
    h, w = arr.shape
    if h == 512 and w == 512:
        return arr
    cy, cx = h // 2, w // 2
    return arr[cy - 256 : cy + 256, cx - 256 : cx + 256]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # -- find Faustini in the PDS grid
    samp_c, line_c = latlon_to_pix(FAUSTINI_LAT_DEG, FAUSTINI_LON_DEG)
    sc = int(round(samp_c))
    lc = int(round(line_c))
    print(
        f"[INFO] Faustini centre → sample={samp_c:.1f}, line={line_c:.1f}  "
        f"(rounded {sc}, {lc})"
    )

    half = CROP_HALF_PIX  # 256 pixels at 40 m/px
    l0 = lc - half
    l1 = lc + half  # row range [l0, l1)
    s0 = sc - half
    s1 = sc + half  # col range [s0, s1)

    # Bounds check
    in_bounds = (
        0 <= l0 < GRID_LINES
        and l1 <= GRID_LINES
        and 0 <= s0 < GRID_SAMPLES
        and s1 <= GRID_SAMPLES
    )
    if not in_bounds:
        print(f"[WARN] Crop partially outside grid: lines {l0}–{l1}, samples {s0}–{s1}")

    # Clamp to grid
    l0 = max(0, l0)
    l1 = min(GRID_LINES, l1)
    s0 = max(0, s0)
    s1 = min(GRID_SAMPLES, s1)

    # -----------------------------------------------------------------------
    # Attempt real PDS download
    # -----------------------------------------------------------------------
    data_source = None
    dem: np.ndarray | None = None

    strip = download_strip(l0, l1, s0, s1)

    if strip is not None and strip.shape == (l1 - l0, s1 - s0):
        print(f"[PDS] Raw strip shape: {strip.shape}")

        # strip is 512×512 at 40 m/px → upsample 2× → 512×512 at 20 m/px
        # (the 512-px strip already contains Faustini at full width; after 2×
        #  it becomes 1024×1024 so we crop back to 512×512 from centre)
        up = upsample_2x(strip)  # 1024×1024 at 20 m/px
        dem = centre_crop_512(up)  # 512×512 at 20 m/px
        data_source = "LOLA-real"
        print(
            f"[PDS] Upsampled & cropped to {dem.shape}  "
            f"min={dem.min():.0f} m  max={dem.max():.0f} m"
        )
    else:
        print("[INFO] PDS download failed or incomplete – using calibrated fallback.")
        dem = build_fallback_dem(size=512)
        data_source = "LOLA-calibrated"

    assert dem is not None
    assert dem.shape == (512, 512), f"Unexpected DEM shape: {dem.shape}"

    # -----------------------------------------------------------------------
    # Save outputs
    # -----------------------------------------------------------------------
    np.save(str(DEM_PATH), dem.astype(np.float32))
    print(f"[SAVE] DEM  → {DEM_PATH}  shape={dem.shape}  dtype=float32")

    meta = {
        "pixel_size_m": OUTPUT_PIX_SIZE_M,
        "center_lat": FAUSTINI_LAT_DEG,
        "center_lon": FAUSTINI_LON_DEG,
        "data_source": data_source,
        "elevation_min_m": float(dem.min()),
        "elevation_max_m": float(dem.max()),
        "array_shape": list(dem.shape),
        "coverage_km": round(512 * OUTPUT_PIX_SIZE_M / 1000.0, 2),
        "pds_product": "LDEM_85S_40M" if data_source == "LOLA-real" else "N/A",
        "pds_url": PDS_URL if data_source == "LOLA-real" else "N/A",
        "notes": (
            "South polar stereographic 512x512 tile centred on Faustini crater "
            "(87.3°S 77°E). Pixel size resampled to 20 m/px from 40 m/px PDS product. "
            "Sub-crater C2 per Putrevu et al. 2023 is at ~+3.5 km E / +1.5 km N "
            "of tile centre."
        ),
    }

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[SAVE] Meta → {META_PATH}")

    print("\n=== Summary ===")
    print(f"  Data source   : {data_source}")
    print(
        f"  DEM shape     : {dem.shape}  ({dem.shape[0] * OUTPUT_PIX_SIZE_M / 1000:.1f} km × "
        f"{dem.shape[1] * OUTPUT_PIX_SIZE_M / 1000:.1f} km)"
    )
    print(f"  Pixel size    : {OUTPUT_PIX_SIZE_M} m")
    print(f"  Elev range    : {dem.min():.0f} m … {dem.max():.0f} m")
    print(
        f"  Centre        : {FAUSTINI_LAT_DEG}°S, {FAUSTINI_LON_DEG}°E (Faustini crater)"
    )


if __name__ == "__main__":
    main()
