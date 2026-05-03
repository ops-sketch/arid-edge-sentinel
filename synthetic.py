"""
synthetic.py
------------
Plausible fallback ECOSTRESS / Landsat / GEDI / LST rasters.
Works for any global bbox -- generates latitudinally-aware
background fields plus a localized drought hotspot.

Each scene exposes seven 2-D fields:
  esi, ndmi, height, lst, risk, wildfire_risk, atmospheric_dryness
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from resilience_score import (
    calculate_resilience_risk,
    calculate_wildfire_risk,
    calculate_atmospheric_dryness,
)


@dataclass
class SyntheticScene:
    lons: np.ndarray
    lats: np.ndarray
    esi: np.ndarray
    ndmi: np.ndarray
    height: np.ndarray
    lst: np.ndarray
    risk: np.ndarray
    wildfire_risk: np.ndarray
    atmospheric_dryness: np.ndarray


def _make_grid(bbox, n=80):
    lon_min, lat_min, lon_max, lat_max = bbox
    lons = np.linspace(lon_min, lon_max, n)
    lats = np.linspace(lat_min, lat_max, n)
    return lons, lats


def _gaussian_blob(n, center=(0.65, 0.55), radius=0.35):
    xs = np.linspace(0, 1, n)
    ys = np.linspace(0, 1, n)
    X, Y = np.meshgrid(xs, ys)
    return np.exp(-(((X - center[0]) ** 2 + (Y - center[1]) ** 2) / (2 * radius ** 2)))


def _latitudinal_temperature(lats):
    """Crude global LST proxy in Kelvin: hot near equator, cool polewards."""
    abs_lat = np.abs(lats)
    return 315.0 - 0.5 * abs_lat - 0.005 * abs_lat ** 2


def _latitudinal_moisture(lats):
    """Moist near equator + temperate band, dry around 25 deg subtropics."""
    abs_lat = np.abs(lats)
    base = 0.55 + 0.25 * np.cos(np.deg2rad(lats))
    subtropical_well = 0.25 * np.exp(-((abs_lat - 25.0) ** 2) / (2 * 8.0 ** 2))
    return np.clip(base - subtropical_well, 0.05, 0.95)


def synthesize_scene(bbox=(-5.0, 12.0, 20.0, 18.0), n=96, seed=42, drought_intensity=0.55):
    rng = np.random.default_rng(seed)
    lons, lats = _make_grid(bbox, n=n)

    moisture_by_lat = _latitudinal_moisture(lats)
    lst_by_lat = _latitudinal_temperature(lats)
    moisture_field = np.tile(moisture_by_lat[:, None], (1, n))
    lst_field = np.tile(lst_by_lat[:, None], (1, n))
    ripple = 0.04 * np.sin(np.linspace(0, 4 * np.pi, n))[None, :]

    hotspot = _gaussian_blob(n, center=(0.65, 0.55), radius=0.35)
    cool_patch = _gaussian_blob(n, center=(0.25, 0.30), radius=0.20)

    esi = np.clip(
        moisture_field + ripple - drought_intensity * hotspot
        + 0.04 * rng.standard_normal((n, n)),
        0.0, 1.0,
    )
    ndmi = np.clip(
        (esi - 0.5) * 1.2 + 0.08 * rng.standard_normal((n, n)) - 0.4 * hotspot,
        -1.0, 1.0,
    )
    biomass_potential = np.clip(moisture_field * 25.0 - 5.0, 0.0, 25.0)
    savanna = _gaussian_blob(n, center=(0.30, 0.40), radius=0.25)
    height = np.clip(
        biomass_potential + 8.0 * savanna + 1.5 * rng.standard_normal((n, n)),
        0.0, 50.0,
    )
    lst = np.clip(
        lst_field + 8.0 * hotspot - 4.0 * cool_patch + 0.8 * rng.standard_normal((n, n)),
        270.0, 330.0,
    )

    risk = calculate_resilience_risk(ndmi=ndmi, esi=esi, gedi_height=height)
    wildfire_risk = calculate_wildfire_risk(ndmi=ndmi, gedi_height=height)
    adi = calculate_atmospheric_dryness(esi=esi, lst_kelvin=lst)

    return SyntheticScene(
        lons=lons, lats=lats,
        esi=esi, ndmi=ndmi, height=height, lst=lst,
        risk=risk, wildfire_risk=wildfire_risk, atmospheric_dryness=adi,
    )


if __name__ == "__main__":
    for label, bbox in [
        ("Sahel",      (-5.0, 12.0, 20.0, 18.0)),
        ("California", (-122.0, 35.0, -118.5, 39.5)),
        ("Amazon",     (-65.0, -12.0, -50.0, -3.0)),
    ]:
        s = synthesize_scene(bbox=bbox)
        print(f"{label:12s} ESI {s.esi.min():.2f}-{s.esi.max():.2f}  "
              f"BDI {s.wildfire_risk.min():.2f}-{s.wildfire_risk.max():.2f}  "
              f"ADI {s.atmospheric_dryness.min():.2f}-{s.atmospheric_dryness.max():.2f}  "
              f"LST {s.lst.min():.0f}-{s.lst.max():.0f}K")
