"""
resilience_score.py
-------------------
Resilience indices for the NASA Space to Soil Challenge.

  1. Resilience Risk Score (R)    - "ecological collapse risk"
  2. Biomass-to-Dryness Index (BDI) - "wildfire powderkeg risk"
  3. Atmospheric Dryness Index (ADI) - "VPD-style atmospheric demand"

Formula (Section 3.2):
    R = ( w1*(1 - NDMI_norm) + w2*(1 - ESI_norm) ) * ln(1 + H_GEDI)

Natural range of R: 0 to ~4.5 (when fully stressed over a 50 m canopy).
Alert bands below are calibrated to that natural range so categorical
levels span the realistic distribution rather than a hypothetical 0-10.
"""

from __future__ import annotations

import numpy as np


def normalize_ndmi(ndmi):
    ndmi = np.asarray(ndmi, dtype=float)
    return np.clip(1.0 - ((ndmi + 1.0) / 2.0), 0.0, 1.0)


def normalize_esi(esi):
    esi = np.asarray(esi, dtype=float)
    return np.clip(1.0 - esi, 0.0, 1.0)


def calculate_resilience_risk(ndmi, esi, gedi_height, w1=0.5, w2=0.5, *, clip=(0.0, 5.0)):
    if not np.isclose(w1 + w2, 1.0, atol=1e-3):
        total = w1 + w2
        if total > 0:
            w1, w2 = w1 / total, w2 / total
    dryness = normalize_ndmi(ndmi)
    stress = normalize_esi(esi)
    h = np.asarray(gedi_height, dtype=float)
    h = np.where(h < 0, 0.0, h)
    biomass = np.log1p(h)
    risk = (w1 * dryness + w2 * stress) * biomass
    risk = np.clip(risk, clip[0], clip[1])
    if risk.ndim == 0:
        return float(risk)
    return risk


def calculate_wildfire_risk(ndmi, gedi_height, *, clip=(0.0, 10.0)):
    """Biomass-to-Dryness Index (BDI) -- wildfire powderkeg risk."""
    dryness = normalize_ndmi(ndmi)
    h = np.asarray(gedi_height, dtype=float)
    h = np.where(h < 0, 0.0, h)
    biomass = np.log1p(h)
    bdi = dryness * biomass * 2.5
    bdi = np.clip(bdi, clip[0], clip[1])
    if bdi.ndim == 0:
        return float(bdi)
    return bdi


_LST_MIN_K = 285.0
_LST_MAX_K = 320.0


def calculate_atmospheric_dryness(esi, lst_kelvin=None, *, clip=(0.0, 1.0)):
    """Atmospheric Dryness Index (ADI) -- VPD-style atmospheric demand proxy."""
    stress = normalize_esi(esi)
    if lst_kelvin is None:
        adi = stress
    else:
        lst = np.asarray(lst_kelvin, dtype=float)
        temp_factor = np.clip((lst - _LST_MIN_K) / (_LST_MAX_K - _LST_MIN_K), 0.0, 1.0)
        adi = stress * (0.4 + 0.6 * temp_factor)
    adi = np.clip(adi, clip[0], clip[1])
    if adi.ndim == 0:
        return float(adi)
    return adi


# Calibrated to R's natural 0-4.5 range (formula caps near ln(51) = 3.93)
ALERT_LEVELS = [
    (0.0, 0.8,  "NOMINAL",  "Continue passive monitoring"),
    (0.8, 1.6,  "ADVISORY", "Schedule next high-res pass"),
    (1.6, 2.4,  "WATCH",    "Targeted irrigation review recommended"),
    (2.4, 3.0,  "WARNING",  "Targeted thinning / emergency irrigation"),
    (3.0, 5.1,  "CRITICAL", "Immediate intervention -- wildfire / crop-loss imminent"),
]


def alert_for_score(score):
    s = float(score)
    for lo, hi, level, action in ALERT_LEVELS:
        if lo <= s < hi:
            return {"score": round(s, 2), "level": level, "action": action}
    return {"score": round(s, 2), "level": "UNKNOWN", "action": "Investigate"}


if __name__ == "__main__":
    healthy = calculate_resilience_risk(ndmi=0.6,  esi=0.9, gedi_height=30.0)
    crisis  = calculate_resilience_risk(ndmi=-0.4, esi=0.1, gedi_height=30.0)
    bare    = calculate_resilience_risk(ndmi=-0.4, esi=0.1, gedi_height=0.5)
    print(f"Healthy: {healthy:.2f} {alert_for_score(healthy)['level']}")
    print(f"Crisis:  {crisis:.2f} {alert_for_score(crisis)['level']}")
    print(f"Bare:    {bare:.2f} {alert_for_score(bare)['level']}")
    assert healthy < crisis and bare < crisis

    powderkeg  = calculate_wildfire_risk(ndmi=-0.4, gedi_height=30.0)
    wet_forest = calculate_wildfire_risk(ndmi=0.5,  gedi_height=30.0)
    dry_grass  = calculate_wildfire_risk(ndmi=-0.4, gedi_height=0.5)
    print(f"BDI powderkeg: {powderkeg:.2f}  wet-forest: {wet_forest:.2f}  dry-grass: {dry_grass:.2f}")
    assert powderkeg > wet_forest and powderkeg > dry_grass

    print("All assertions passed.")
