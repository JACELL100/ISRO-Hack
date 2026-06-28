"""
DFSAR Polarimetric Analysis Engine
Computes Stokes parameters, Circular Polarization Ratio (CPR),
and Degree of Polarization (DOP) from Chandrayaan-2 DFSAR data.

Scientific basis:
- Stokes parameters characterize the polarization state of radar echoes
- CPR > 1 indicates volumetric scattering (ice signature)
- DOP < 0.13 eliminates rough rocky surfaces (which also have high CPR)
- Combined CPR > 1 AND DOP < 0.13 is the ice detection criterion
  (Putrevu et al. 2023, Chakraborty et al. 2024)

Dual-Frequency Analysis (L-band + S-band):
- L-band (24 cm): penetrates ~5 m into icy regolith; probes deep ice layers
- S-band (9 cm): penetrates ~1-2 m; confirms shallow near-surface ice
- Consistency between L-band and S-band ice signatures greatly reduces
  false positives from rough terrain (Nozette et al. 1996 analog)
"""
import numpy as np
from scipy.ndimage import uniform_filter
from typing import Dict, Tuple


def multilook(data: np.ndarray, window: int = 5) -> np.ndarray:
    """
    Apply multi-looking (spatial averaging) to reduce speckle noise.
    Equivalent to incoherent averaging over a sliding window.
    """
    if np.iscomplexobj(data):
        # Average magnitude squared (intensity), not complex values
        power = np.abs(data) ** 2
        return uniform_filter(power, size=window)
    return uniform_filter(data, size=window)


def compute_stokes_parameters(
    S_HH: np.ndarray,
    S_HV: np.ndarray,
    S_VH: np.ndarray,
    S_VV: np.ndarray,
    window: int = 5,
) -> Dict[str, np.ndarray]:
    """
    Compute Stokes parameters from the full polarimetric scattering matrix.

    For a monostatic fully polarimetric SAR (assuming S_HV = S_VH):
        S0 = <|S_HH|^2 + |S_VV|^2 + 2|S_HV|^2>   (total power)
        S1 = <|S_HH|^2 - |S_VV|^2>
        S2 = <2·Re(S_HH · S_VV*)>
        S3 = <2·Im(S_HH · S_VV*)>

    Angle brackets denote ensemble averaging (multi-look window).
    """
    HH = S_HH.astype(complex)
    HV = S_HV.astype(complex)
    VH = S_VH.astype(complex)
    VV = S_VV.astype(complex)

    HH_pow = uniform_filter(np.abs(HH) ** 2, size=window)
    HV_pow = uniform_filter(np.abs(HV) ** 2, size=window)
    VH_pow = uniform_filter(np.abs(VH) ** 2, size=window)
    VV_pow = uniform_filter(np.abs(VV) ** 2, size=window)
    HHVV_real = uniform_filter(np.real(HH * np.conj(VV)), size=window)
    HHVV_imag = uniform_filter(np.imag(HH * np.conj(VV)), size=window)

    S0 = HH_pow + VV_pow + 2 * HV_pow
    S1 = HH_pow - VV_pow
    S2 = 2 * HHVV_real
    S3 = 2 * HHVV_imag

    return {"S0": S0, "S1": S1, "S2": S2, "S3": S3}


def compute_cpr(
    S_HH: np.ndarray,
    S_HV: np.ndarray,
    S_VH: np.ndarray,
    S_VV: np.ndarray,
    window: int = 5,
) -> np.ndarray:
    """
    Compute Circular Polarization Ratio (CPR = P_SC / P_OC).

    Derived from Stokes parameters (circular basis transformation):
        P_RC (right circular) = (S0 - S3) / 2
        P_LC (left circular)  = (S0 + S3) / 2

    For a right-circular transmitted wave:
        P_OC = (S0 + S3) / 2  (opposite-sense = LC)
        P_SC = (S0 - S3) / 2  (same-sense = RC)

    CPR = P_SC / P_OC = (S0 - S3) / (S0 + S3)

    CPR > 1 → strong same-sense return → volumetric scattering → ice candidate
    """
    stokes = compute_stokes_parameters(S_HH, S_HV, S_VH, S_VV, window)
    S0, S3 = stokes["S0"], stokes["S3"]

    P_SC = (S0 - S3) / 2.0
    P_OC = (S0 + S3) / 2.0

    # Avoid division by zero
    eps = 1e-10
    cpr = P_SC / (P_OC + eps)
    cpr = np.clip(cpr, 0, 5.0)  # Physical range
    return cpr


def compute_dop(stokes: Dict[str, np.ndarray]) -> np.ndarray:
    """
    Compute Degree of Polarization (DOP).

    DOP = sqrt(S1^2 + S2^2 + S3^2) / S0

    Range [0, 1]:
    - DOP → 1: fully polarized (specular/surface scattering, rock)
    - DOP → 0: fully depolarized (volumetric scattering, ice)

    Ice criterion: DOP < 0.13
    """
    S0 = stokes["S0"]
    S1 = stokes["S1"]
    S2 = stokes["S2"]
    S3 = stokes["S3"]

    eps = 1e-10
    dop = np.sqrt(S1**2 + S2**2 + S3**2) / (S0 + eps)
    dop = np.clip(dop, 0, 1.0)
    return dop


def compute_all_polarimetric(
    dfsar: Dict[str, np.ndarray], window: int = 7
) -> Dict[str, np.ndarray]:
    """
    Compute all polarimetric parameters from DFSAR scattering matrix.
    Returns CPR, DOP, Stokes parameters, and additional indices.
    This processes the L-band data (primary ice detection channel).
    """
    S_HH = dfsar["S_HH"]
    S_HV = dfsar["S_HV"]
    S_VH = dfsar["S_VH"]
    S_VV = dfsar["S_VV"]

    stokes = compute_stokes_parameters(S_HH, S_HV, S_VH, S_VV, window)
    cpr = compute_cpr(S_HH, S_HV, S_VH, S_VV, window)
    dop = compute_dop(stokes)

    # Backscatter coefficients (sigma_0) in linear scale
    sigma_HH = stokes["S0"] * 0.5  # Approximate
    sigma_HV = uniform_filter(np.abs(S_HV) ** 2, size=window)

    # Entropy-like measure from DOP (1 - DOP → entropy proxy)
    entropy_proxy = 1.0 - dop

    return {
        "CPR": cpr,
        "DOP": dop,
        "S0": stokes["S0"],
        "S1": stokes["S1"],
        "S2": stokes["S2"],
        "S3": stokes["S3"],
        "sigma_HH": sigma_HH,
        "sigma_HV": sigma_HV,
        "entropy_proxy": entropy_proxy,
    }


def compute_sband_polarimetric(
    dfsar_sband: Dict[str, np.ndarray], window: int = 7
) -> Dict[str, np.ndarray]:
    """
    Compute S-band (9 cm wavelength) polarimetric parameters.
    Chandrayaan-2 DFSAR is dual-frequency: L-band (430 MHz) + S-band (2.5 GHz).

    S-band properties:
    - Wavelength: ~9 cm (vs 24 cm for L-band)
    - Penetration depth: ~1-2 m in icy regolith (vs ~5 m for L-band)
    - Higher sensitivity to surface roughness
    - S-band CPR > 1 + L-band CPR > 1 = strong dual-frequency ice confirmation

    Ice detection: S-band ice signature (CPR_S > 1 AND DOP_S < 0.13) combined
    with L-band ice signature provides high-confidence dual-frequency validation.
    """
    S_HH = dfsar_sband["S_HH"]
    S_HV = dfsar_sband["S_HV"]
    S_VH = dfsar_sband["S_VH"]
    S_VV = dfsar_sband["S_VV"]

    stokes = compute_stokes_parameters(S_HH, S_HV, S_VH, S_VV, window)
    cpr_s = compute_cpr(S_HH, S_HV, S_VH, S_VV, window)
    dop_s = compute_dop(stokes)

    # S-band specific: surface roughness contribution is stronger
    # Fresnel zone is smaller → more sensitive to cm-scale roughness
    sigma_HH_s = stokes["S0"] * 0.5
    entropy_proxy_s = 1.0 - dop_s

    return {
        "CPR_S": cpr_s,
        "DOP_S": dop_s,
        "S0_S": stokes["S0"],
        "entropy_proxy_S": entropy_proxy_s,
        "sigma_HH_S": sigma_HH_s,
        "frequency": "S-band (2.5 GHz, ~9 cm)",
        "penetration_depth_m": 1.5,  # Approximate for icy regolith
    }


def compute_dual_frequency_analysis(
    l_band: Dict[str, np.ndarray],
    s_band: Dict[str, np.ndarray],
) -> Dict[str, np.ndarray]:
    """
    Dual-frequency ice confidence analysis combining L-band and S-band.

    The key insight:
    - Rough rocky terrain produces high CPR in BOTH bands
    - Ice produces high CPR in L-band (deep penetration) but the S-band
      response is more nuanced due to shallower penetration
    - Frequency-ratio analysis can discriminate ice from rough terrain

    Dual-Frequency Ratio (DFR) = CPR_L / CPR_S:
    - DFR >> 1: L-band scatters more strongly → deep subsurface ice
    - DFR ~ 1: Both bands scatter equally → surface roughness (false positive)
    - Combined ice criterion: CPR_L > 1 AND DOP_L < 0.13 AND DFR > 0.8

    Returns:
        Dictionary with dual-frequency ice confidence map and component arrays.
    """
    CPR_L = l_band["CPR"]
    DOP_L = l_band["DOP"]
    CPR_S = s_band["CPR_S"]
    DOP_S = s_band["DOP_S"]

    eps = 1e-6

    # Dual-Frequency Ratio
    dfr = CPR_L / (CPR_S + eps)
    dfr = np.clip(dfr, 0, 5.0)

    # Ice candidate in each band
    ice_L = (CPR_L > 1.0) & (DOP_L < 0.13)  # L-band ice criterion
    ice_S = (CPR_S > 1.0) & (DOP_S < 0.13)  # S-band ice criterion

    # Dual-frequency confirmed ice: both bands agree
    ice_dual_confirmed = ice_L & ice_S  # Highest confidence
    ice_L_only = ice_L & ~ice_S          # L-band only: may be deep ice or roughness

    # Dual-frequency ice confidence score [0, 1]
    # L-band contribution (primary, deeper penetration)
    conf_L = np.clip(0.5 * (CPR_L - 1.0) / 2.0 + 0.5 * (0.13 - DOP_L) / 0.13, 0, 1)
    # S-band contribution (secondary, shallower)
    conf_S = np.clip(0.5 * (CPR_S - 1.0) / 2.0 + 0.5 * (0.13 - DOP_S) / 0.13, 0, 1)

    # Combined: dual-frequency agreement boosts confidence
    dual_confidence = 0.6 * conf_L + 0.4 * conf_S
    dual_confidence[ice_dual_confirmed] *= 1.3  # 30% boost for dual confirmation
    dual_confidence = np.clip(dual_confidence, 0, 1)

    # Roughness discriminator: if DFR ~ 1 and both CPRs are high → rough terrain
    roughness_flag = (dfr > 0.7) & (dfr < 1.3) & (CPR_L > 1.0) & (CPR_S > 1.0)
    # Actual ice has DFR > 1 (L-band penetrates deeper, sees more ice volume)
    ice_dfr_consistent = ice_L & (dfr > 0.8)

    return {
        "CPR_L": CPR_L,
        "DOP_L": DOP_L,
        "CPR_S": CPR_S,
        "DOP_S": DOP_S,
        "dual_frequency_ratio": dfr,
        "ice_L_band": ice_L.astype(np.uint8),
        "ice_S_band": ice_S.astype(np.uint8),
        "ice_dual_confirmed": ice_dual_confirmed.astype(np.uint8),
        "ice_L_only": ice_L_only.astype(np.uint8),
        "ice_dfr_consistent": ice_dfr_consistent.astype(np.uint8),
        "dual_confidence": dual_confidence.astype(np.float32),
        "roughness_flag": roughness_flag.astype(np.uint8),
        "n_ice_L": int(ice_L.sum()),
        "n_ice_S": int(ice_S.sum()),
        "n_ice_dual": int(ice_dual_confirmed.sum()),
        "pct_dual_confirmed": round(float(ice_dual_confirmed.sum()) / max(ice_L.sum(), 1) * 100, 1),
    }


def get_statistics(data: np.ndarray, mask: np.ndarray = None) -> Dict:
    """
    Compute descriptive statistics of a polarimetric parameter.
    Optionally restricted to a masked region.
    """
    if mask is not None:
        values = data[mask.astype(bool)]
    else:
        values = data.ravel()

    if len(values) == 0:
        return {"mean": 0, "std": 0, "min": 0, "max": 0, "median": 0, "p25": 0, "p75": 0}

    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "median": float(np.median(values)),
        "p25": float(np.percentile(values, 25)),
        "p75": float(np.percentile(values, 75)),
    }
