"""
DFSAR Data I/O Module
Handles reading of Chandrayaan-2 DFSAR data in PDS4 format.
When real data is unavailable, falls back to the synthetic data generator.

DFSAR Data Source: ISRO PRADAN portal (https://pradan.issdc.gov.in)
Data format: PDS4 SLC (Single Look Complex) — binary .img files with XML labels
"""
import numpy as np
import os
from typing import Dict, Optional, Tuple


def read_dfsar_slc(
    img_path: str,
    rows: int,
    cols: int,
    dtype: np.dtype = np.complex64,
) -> np.ndarray:
    """
    Read a DFSAR Single Look Complex (SLC) binary image.
    PDS4 format: raw binary, row-major order.

    Args:
        img_path: Path to .img file
        rows: Number of range lines
        cols: Number of azimuth samples
        dtype: Data type (complex64 for SLC)

    Returns:
        Complex numpy array of shape (rows, cols)
    """
    if not os.path.exists(img_path):
        raise FileNotFoundError(f"DFSAR file not found: {img_path}")
    data = np.fromfile(img_path, dtype=dtype)
    data = data.reshape(rows, cols)
    return data


def load_dfsar_product(
    product_dir: str,
    polarizations: list = ['HH', 'HV', 'VH', 'VV'],
) -> Optional[Dict[str, np.ndarray]]:
    """
    Load a complete DFSAR polarimetric product from a directory.
    Expects files named: dfsar_HH.img, dfsar_HV.img, etc.

    Returns None if files are not found (triggers synthetic data fallback).
    """
    result = {}
    for pol in polarizations:
        fpath = os.path.join(product_dir, f'dfsar_{pol}.img')
        if not os.path.exists(fpath):
            return None  # Trigger fallback
        try:
            # Read XML label to get dimensions
            xml_path = fpath.replace('.img', '.xml')
            rows, cols = _parse_pds4_dimensions(xml_path)
            result[f'S_{pol}'] = read_dfsar_slc(fpath, rows, cols)
        except Exception as e:
            print(f"Warning: Could not read {fpath}: {e}")
            return None
    return result


def _parse_pds4_dimensions(xml_path: str) -> Tuple[int, int]:
    """Parse rows/cols from PDS4 XML label."""
    if not os.path.exists(xml_path):
        return 512, 512  # Default fallback
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {'pds': 'http://pds.nasa.gov/pds4/pds/v1'}
        lines = int(root.find('.//pds:lines', ns).text)
        samples = int(root.find('.//pds:samples', ns).text)
        return lines, samples
    except Exception:
        return 512, 512


def load_or_generate(
    data_dir: Optional[str] = None,
    scene_size: int = 256,
) -> Dict:
    """
    Try to load real DFSAR data; fall back to synthetic generator if unavailable.
    This is the main entry point used by the API.
    """
    if data_dir and os.path.isdir(data_dir):
        result = load_dfsar_product(data_dir)
        if result is not None:
            print(f"✅ Loaded real DFSAR data from: {data_dir}")
            return result

    print("ℹ️  No real DFSAR data found. Using synthetic data generator.")
    from modules.data_generator import generate_full_scene
    return generate_full_scene(rows=scene_size, cols=scene_size)


def apply_range_doppler(slc: np.ndarray) -> np.ndarray:
    """
    Apply Range-Doppler focusing if data is raw (unfocused).
    For SLC products from PRADAN, data is already focused.
    This is a placeholder for raw data processing.
    """
    # PRADAN distributes focused SLC products
    # Raw data processing would require: range compression → azimuth compression
    return slc


def coregister_channels(
    S_HH: np.ndarray, S_HV: np.ndarray,
    S_VH: np.ndarray, S_VV: np.ndarray,
) -> Dict[str, np.ndarray]:
    """
    Co-register all polarization channels to a common grid.
    For DFSAR, HH/HV and VH/VV are acquired simultaneously,
    so co-registration is minimal.
    """
    # Simple crop to common shape
    min_rows = min(d.shape[0] for d in [S_HH, S_HV, S_VH, S_VV])
    min_cols = min(d.shape[1] for d in [S_HH, S_HV, S_VH, S_VV])
    return {
        'S_HH': S_HH[:min_rows, :min_cols],
        'S_HV': S_HV[:min_rows, :min_cols],
        'S_VH': S_VH[:min_rows, :min_cols],
        'S_VV': S_VV[:min_rows, :min_cols],
    }
