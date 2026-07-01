"""
DFSAR / OHRC / DEM Real-Data I/O Module
=======================================
Loads real Chandrayaan-2 DFSAR (Dual Frequency SAR) and OHRC (Orbiter High
Resolution Camera) products and assembles a complete analysis "scene" that is
schema-compatible with `data_generator.generate_full_scene()`.

If real data is unavailable (or the required geospatial libraries are missing)
the module transparently falls back to the synthetic data generator so the
application always runs.

────────────────────────────────────────────────────────────────────────────
Data source: ISRO PRADAN portal  →  https://pradan.issdc.gov.in/ch2/
  • DFSAR : SARLTA*.tar archives — calibrated full-polarimetric SLC products.
            Bands HH, HV, VH, VV per frequency (L-band 430 MHz, S-band 2.5 GHz).
            Distributed as PDS4 (.img raw binary + .xml label) or GeoTIFF.
  • OHRC  : Calibrated/derived high-resolution imagery + DEM/Ortho (GeoTIFF).

Supported input formats
  1. GeoTIFF  (.tif/.tiff)            — preferred, read via rasterio or GDAL.
  2. PDS4     (.img + .xml label)     — raw binary, complex SLC.

Directory layout expected by `load_real_scene(data_dir)`
  data_dir/
    ├── dfsar_HH.(tif|img)   (+ .xml for PDS4)   L-band, required
    ├── dfsar_HV.(tif|img)                       L-band, required
    ├── dfsar_VH.(tif|img)                       L-band, required
    ├── dfsar_VV.(tif|img)                       L-band, required
    ├── dfsar_s_HH.(tif|img) ...                 S-band, optional
    ├── dem.(tif|img)                            DEM (metres), optional
    └── ohrc.(tif|img)                           OHRC grayscale, optional

Environment variable override
  ISRO_DATA_DIR  — absolute path to the product directory. When set and valid,
                   real data is used automatically by `app.get_scene()`.
"""

from __future__ import annotations

import glob
import os
from typing import Dict, List, Optional, Tuple

import numpy as np

# ── Optional geospatial backends (graceful degradation) ──────────────────────
try:
    import rasterio  # type: ignore

    _HAS_RASTERIO = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_RASTERIO = False

try:
    from osgeo import gdal  # type: ignore

    gdal.UseExceptions()
    _HAS_GDAL = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_GDAL = False


# Polarisation channels expected for a full-pol product
L_BAND_POLS = ["HH", "HV", "VH", "VV"]


# ─────────────────────────────────────────────────────────────────────────────
# Low-level raster readers
# ─────────────────────────────────────────────────────────────────────────────
def _read_geotiff(path: str) -> Tuple[np.ndarray, Optional[float]]:
    """
    Read a single-band raster (GeoTIFF or any GDAL/rasterio supported format).

    Returns (array, pixel_size_m). pixel_size_m is None when no geotransform
    is available. For complex SAR products the native complex dtype is kept.
    """
    if _HAS_RASTERIO:
        with rasterio.open(path) as ds:
            arr = ds.read(1)
            px = None
            try:
                # res returns (x_res, y_res) in CRS units (metres for polar stereo)
                px = float(abs(ds.res[0]))
            except Exception:
                px = None
            return arr, px

    if _HAS_GDAL:
        ds = gdal.Open(path)
        if ds is None:
            raise IOError(f"GDAL could not open: {path}")
        band = ds.GetRasterBand(1)
        arr = band.ReadAsArray()
        gt = ds.GetGeoTransform()
        px = float(abs(gt[1])) if gt else None
        return arr, px

    raise RuntimeError(
        "No geospatial backend available — install 'rasterio' or 'gdal' to read "
        "GeoTIFF products, or supply PDS4 .img/.xml instead."
    )


def _parse_pds4_dimensions(xml_path: str) -> Tuple[int, int]:
    """Parse (lines, samples) from a PDS4 XML label."""
    if not os.path.exists(xml_path):
        return 0, 0
    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # PDS4 namespace-agnostic search (labels vary across releases)
        def _find_int(tag: str) -> Optional[int]:
            for el in root.iter():
                if el.tag.split("}")[-1].lower() == tag:
                    try:
                        return int(float(el.text))
                    except (TypeError, ValueError):
                        continue
            return None

        lines = _find_int("lines")
        samples = _find_int("samples")
        if lines and samples:
            return lines, samples
    except Exception as exc:  # pragma: no cover
        print(f"  ⚠️  PDS4 label parse failed ({xml_path}): {exc}")
    return 0, 0


def _read_pds4_img(img_path: str, dtype: np.dtype = np.complex64) -> np.ndarray:
    """
    Read a PDS4 raw binary .img using its accompanying .xml label for shape.
    Falls back to inferring a square shape from file size when label is absent.
    """
    xml_path = os.path.splitext(img_path)[0] + ".xml"
    rows, cols = _parse_pds4_dimensions(xml_path)
    raw = np.fromfile(img_path, dtype=dtype)

    if rows and cols and rows * cols == raw.size:
        return raw.reshape(rows, cols)

    # Infer a square scene if the label is missing / mismatched
    side = int(np.sqrt(raw.size))
    if side * side == raw.size:
        print(
            f"  ℹ️  Inferred square shape {side}×{side} for {os.path.basename(img_path)}"
        )
        return raw.reshape(side, side)

    raise ValueError(
        f"Cannot determine raster shape for {img_path} "
        f"(size={raw.size}); provide a valid PDS4 .xml label."
    )


def _find_channel_file(data_dir: str, basename: str) -> Optional[str]:
    """
    Locate a channel file by stem, trying GeoTIFF first then PDS4 .img.
    e.g. basename='dfsar_HH' → dfsar_HH.tif / .tiff / .img (case-insensitive).
    """
    for ext in (".tif", ".tiff", ".TIF", ".TIFF", ".img", ".IMG"):
        cand = os.path.join(data_dir, basename + ext)
        if os.path.exists(cand):
            return cand
    # Glob fallback (handles product-id prefixed names containing the stem)
    matches = glob.glob(os.path.join(data_dir, f"*{basename}*"))
    matches = [m for m in matches if m.lower().endswith((".tif", ".tiff", ".img"))]
    return matches[0] if matches else None


def _read_channel(path: str) -> Tuple[np.ndarray, Optional[float]]:
    """Dispatch to the correct reader based on file extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".tif", ".tiff"):
        return _read_geotiff(path)
    if ext == ".img":
        return _read_pds4_img(path), None
    raise ValueError(f"Unsupported raster extension: {ext}")


# ─────────────────────────────────────────────────────────────────────────────
# Product loaders
# ─────────────────────────────────────────────────────────────────────────────
def _crop_to_common_shape(channels: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """Crop all channels to the smallest common (rows, cols)."""
    min_rows = min(a.shape[0] for a in channels.values())
    min_cols = min(a.shape[1] for a in channels.values())
    return {k: v[:min_rows, :min_cols] for k, v in channels.items()}


def load_dfsar_product(
    data_dir: str, prefix: str = "dfsar"
) -> Optional[Tuple[Dict[str, np.ndarray], Optional[float]]]:
    """
    Load a full-polarimetric DFSAR product (one frequency band).

    Args:
        data_dir: product directory
        prefix:   'dfsar' for L-band, 'dfsar_s' for S-band

    Returns:
        ({S_HH, S_HV, S_VH, S_VV}, pixel_size_m) or None if any channel missing.
    """
    channels: Dict[str, np.ndarray] = {}
    pixel_size: Optional[float] = None

    for pol in L_BAND_POLS:
        path = _find_channel_file(data_dir, f"{prefix}_{pol}")
        if path is None:
            return None  # incomplete product → caller decides fallback
        try:
            arr, px = _read_channel(path)
            # SAR scattering matrix must be complex
            if not np.iscomplexobj(arr):
                arr = arr.astype(np.complex64)
            channels[f"S_{pol}"] = arr.astype(np.complex64)
            if px and pixel_size is None:
                pixel_size = px
            print(f"  ✅ {prefix}_{pol}: {os.path.basename(path)} {arr.shape}")
        except Exception as exc:
            print(f"  ⚠️  Failed reading {path}: {exc}")
            return None

    channels = _crop_to_common_shape(channels)
    return channels, pixel_size


def load_raster_optional(
    data_dir: str, basename: str
) -> Optional[Tuple[np.ndarray, Optional[float]]]:
    """Load an optional single-band raster (DEM or OHRC). Returns None if absent."""
    path = _find_channel_file(data_dir, basename)
    if path is None:
        return None
    try:
        arr, px = _read_channel(path)
        if np.iscomplexobj(arr):
            arr = np.abs(arr)
        arr = np.asarray(arr, dtype=np.float32)
        # Replace nodata/NaN with local median-ish value
        if not np.all(np.isfinite(arr)):
            finite = arr[np.isfinite(arr)]
            fill = float(np.median(finite)) if finite.size else 0.0
            arr = np.where(np.isfinite(arr), arr, fill)
        print(f"  ✅ {basename}: {os.path.basename(path)} {arr.shape}")
        return arr, px
    except Exception as exc:
        print(f"  ⚠️  Failed reading optional raster {path}: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Scene assembly (real data → analysis-ready dict)
# ─────────────────────────────────────────────────────────────────────────────
def _resample_to(arr: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    """Nearest-neighbour resample a 2-D array to `shape` (no SciPy dependency)."""
    if arr.shape == shape:
        return arr
    r_idx = (np.linspace(0, arr.shape[0] - 1, shape[0])).round().astype(int)
    c_idx = (np.linspace(0, arr.shape[1] - 1, shape[1])).round().astype(int)
    return arr[np.ix_(r_idx, c_idx)]


def _synthesize_dem_from_dfsar(s0: np.ndarray) -> np.ndarray:
    """
    Fallback DEM when no real DEM is supplied: derive a smooth pseudo-relief
    from total backscatter power so downstream slope/shadow code still runs.
    NOTE: clearly a proxy — real DEM (LOLA/OHRC) should be supplied for rigor.
    """
    from modules.compat import gaussian_filter

    s0 = np.asarray(s0, dtype=np.float32)
    s0 = (s0 - s0.min()) / (s0.ptp() + 1e-8)
    # Low backscatter (radar-dark crater floors) → topographic lows
    pseudo = gaussian_filter(s0, sigma=4) * 2000.0 - 1000.0
    return pseudo.astype(np.float32)


def load_real_scene(
    data_dir: str,
    target_size: Optional[int] = 256,
) -> Optional[Dict]:
    """
    Assemble a complete analysis scene from real Chandrayaan-2 products.

    Returns a dict schema-compatible with `generate_full_scene()`:
        dem, shadow_map, psr_mask, doubly_shadowed, dfsar, dfsar_sband,
        ohrc, metadata
    or None if the mandatory L-band DFSAR product is unavailable.
    """
    if not data_dir or not os.path.isdir(data_dir):
        return None

    if not (_HAS_RASTERIO or _HAS_GDAL):
        # We can still read PDS4 .img directly without geospatial libs, so only
        # warn — don't abort.
        print("  ℹ️  rasterio/GDAL not found — only PDS4 .img inputs will be readable.")

    print(f"🔭 Loading REAL Chandrayaan-2 data from: {data_dir}")

    # 1) Mandatory L-band DFSAR
    l_result = load_dfsar_product(data_dir, prefix="dfsar")
    if l_result is None:
        print(
            "  ⚠️  Complete L-band DFSAR product not found — falling back to synthetic."
        )
        return None
    dfsar, px_l = l_result

    ref_shape = dfsar["S_HH"].shape

    # Optional downsampling for performance parity with the synthetic pipeline
    if target_size and max(ref_shape) > target_size:
        new_shape = (target_size, target_size)
        dfsar = {k: _resample_to(v, new_shape) for k, v in dfsar.items()}
        if px_l:
            px_l = px_l * (ref_shape[0] / target_size)
        ref_shape = new_shape
        print(f"  ↓ Resampled DFSAR to {new_shape} for analysis performance.")

    # 2) Optional S-band DFSAR (dual-frequency validation)
    s_result = load_dfsar_product(data_dir, prefix="dfsar_s")
    if s_result is not None:
        dfsar_sband, _ = s_result
        dfsar_sband = {k: _resample_to(v, ref_shape) for k, v in dfsar_sband.items()}
    else:
        print("  ℹ️  No S-band product — dual-frequency analysis will reuse L-band.")
        dfsar_sband = dfsar

    # 3) Optional DEM
    dem_result = load_raster_optional(data_dir, "dem")
    if dem_result is not None:
        dem, px_dem = dem_result
        dem = _resample_to(dem, ref_shape)
        if px_dem and not px_l:
            px_l = px_dem
    else:
        print(
            "  ℹ️  No DEM supplied — synthesizing pseudo-relief from DFSAR power (proxy)."
        )
        # total power S0 proxy
        s0 = (
            np.abs(dfsar["S_HH"]) ** 2
            + np.abs(dfsar["S_VV"]) ** 2
            + 2 * np.abs(dfsar["S_HV"]) ** 2
        ).astype(np.float32)
        dem = _synthesize_dem_from_dfsar(s0)

    # 4) Optional OHRC imagery
    ohrc_result = load_raster_optional(data_dir, "ohrc")
    if ohrc_result is not None:
        ohrc, _ = ohrc_result
        ohrc = _resample_to(ohrc, ref_shape)
        # Normalise to 0-255 uint8 for boulder detection
        omin, omax = float(np.nanmin(ohrc)), float(np.nanmax(ohrc))
        ohrc = ((ohrc - omin) / (omax - omin + 1e-8) * 255).astype(np.uint8)
    else:
        print("  ℹ️  No OHRC supplied — terrain boulder analysis will be skipped.")
        ohrc = None

    pixel_size_m = float(px_l) if px_l else 30.0

    # 5) Derive shadow / PSR / doubly-shadowed maps from the real DEM
    from modules.shadow_mapping import (
        compute_multi_angle_illumination,
        identify_doubly_shadowed_craters,
        identify_psr_regions,
    )

    print("  🌑 Computing illumination & PSRs from real DEM...")
    illum = compute_multi_angle_illumination(
        dem, n_azimuths=8, sun_elevation_deg=1.5, pixel_size_m=pixel_size_m
    )
    shadow_map = illum["shadow_map"]

    psr = identify_psr_regions(shadow_map)
    psr_mask = psr["psr_mask"]

    ds = identify_doubly_shadowed_craters(psr_mask, dem, shadow_map)
    doubly_shadowed = ds["doubly_shadowed_mask"]

    print(
        f"  📊 PSR pixels: {int(psr_mask.sum())} | "
        f"Doubly-shadowed pixels: {int(doubly_shadowed.sum())}"
    )

    metadata = {
        "rows": int(ref_shape[0]),
        "cols": int(ref_shape[1]),
        "pixel_size_m": pixel_size_m,
        "center_lat": -89.5,
        "center_lon": 0.0,
        "sun_elevation_deg": 1.5,
        "l_band_freq_MHz": 430,
        "s_band_freq_GHz": 2.5,
        "l_band_wavelength_cm": 24,
        "s_band_wavelength_cm": 9,
        "data_source": "Chandrayaan-2 DFSAR/OHRC (real)",
        "data_dir": data_dir,
        "has_real_dem": dem_result is not None,
        "has_real_ohrc": ohrc_result is not None,
        "has_real_sband": s_result is not None,
    }

    return {
        "dem": dem.astype(np.float32),
        "shadow_map": shadow_map.astype(np.uint8),
        "psr_mask": psr_mask.astype(np.uint8),
        "doubly_shadowed": doubly_shadowed.astype(np.uint8),
        "dfsar": dfsar,
        "dfsar_sband": dfsar_sband,
        "ohrc": ohrc if ohrc is not None else _blank_ohrc(ref_shape),
        "metadata": metadata,
    }


def _blank_ohrc(shape: Tuple[int, int]) -> np.ndarray:
    """Neutral mid-grey OHRC placeholder when no imagery is supplied."""
    return np.full(shape, 32, dtype=np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point used by app.py
# ─────────────────────────────────────────────────────────────────────────────
def load_or_generate(
    data_dir: Optional[str] = None,
    scene_size: int = 256,
) -> Dict:
    """
    Main entry point. Tries real data (from `data_dir` or the ISRO_DATA_DIR
    environment variable); transparently falls back to the synthetic generator.
    """
    data_dir = data_dir or os.environ.get("ISRO_DATA_DIR")

    if data_dir:
        try:
            scene = load_real_scene(data_dir, target_size=scene_size)
            if scene is not None:
                print(
                    f"[OK] Using REAL Chandrayaan-2 data ({scene['metadata']['rows']}x"
                    f"{scene['metadata']['cols']}, {scene['metadata']['pixel_size_m']} m/px)"
                )
                return scene
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[WARN] Real-data load failed ({exc}) -- using synthetic data.")

    print("[INFO] No real DFSAR data found. Using synthetic data generator.")
    from modules.data_generator import generate_full_scene

    scene = generate_full_scene(rows=scene_size, cols=scene_size)
    # Tag provenance so the API/overview can report the data source.
    scene.setdefault("metadata", {})
    scene["metadata"].setdefault("data_source", "Synthetic data generator")
    return scene


# ── Backwards-compatible helpers (kept for any external callers) ──────────────
def coregister_channels(
    S_HH: np.ndarray,
    S_HV: np.ndarray,
    S_VH: np.ndarray,
    S_VV: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Co-register all polarisation channels to a common grid (crop)."""
    return _crop_to_common_shape(
        {
            "S_HH": S_HH,
            "S_HV": S_HV,
            "S_VH": S_VH,
            "S_VV": S_VV,
        }
    )
