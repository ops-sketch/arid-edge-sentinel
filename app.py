"""
app.py -- Arid-Edge Sentinel: Multi-Modal Land Resilience COMMAND CENTER
========================================================================
Streamlit front-end for the NASA Space to Soil Challenge 2026.

Two view modes:

  1. GLOBAL VIEW  -- world choropleth colored by mean Resilience Risk per
                     country, with clickable leaderboard in the sidebar.
                     Click a country (or a leaderboard row) to drill in.

  2. COUNTRY DRILL-IN  -- satellite raster overlay of the chosen country,
                          14-day spatial-temporal R timeline, severity
                          breakdown, hotspot pins, actionable alert.

Algorithm (Section 3.2) is spotlit in both modes.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from nasa_fusion import (
    DEFAULT_SAHEL_BBOX,
    ADAPTIVE_ESI_THRESHOLD,
    authenticate,
    search_arid_edge,
    summarize_granules,
    run_adaptive_pipeline,
)
from synthetic import synthesize_scene
from resilience_score import alert_for_score, calculate_resilience_risk

load_dotenv(Path(__file__).parent / ".env", override=False)

st.set_page_config(
    page_title="Arid-Edge Sentinel -- Command Center",
    page_icon="SAT",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# CONSTANTS
# ============================================================================

ALERT_COLOR = {
    "NOMINAL":  "#1f9d55",
    "ADVISORY": "#7cb342",
    "WATCH":    "#f4b400",
    "WARNING":  "#fb8c00",
    "CRITICAL": "#d93025",
}

# (ISO-3, display name, bbox lon_min/lat_min/lon_max/lat_max)
COUNTRIES = {
    "USA": ("United States",        (-125.0,  24.0,  -66.0,  49.0)),
    "CAN": ("Canada",               (-141.0,  41.0,  -52.0,  70.0)),
    "MEX": ("Mexico",               (-118.0,  14.0,  -86.0,  33.0)),
    "BRA": ("Brazil",               ( -74.0, -34.0,  -34.0,   5.0)),
    "ARG": ("Argentina",            ( -74.0, -55.0,  -53.0, -22.0)),
    "CHL": ("Chile",                ( -76.0, -56.0,  -66.0, -17.0)),
    "PER": ("Peru",                 ( -82.0, -19.0,  -68.0,   0.0)),
    "COL": ("Colombia",             ( -79.0,  -5.0,  -67.0,  13.0)),
    "VEN": ("Venezuela",            ( -73.0,   0.5,  -59.0,  12.5)),
    "ESP": ("Spain",                (  -9.5,  36.0,    4.0,  44.0)),
    "FRA": ("France",               (  -5.0,  41.0,    9.0,  51.0)),
    "PRT": ("Portugal",             (  -9.5,  37.0,   -6.0,  42.0)),
    "ITA": ("Italy",                (   6.0,  36.0,   19.0,  47.0)),
    "GRC": ("Greece",               (  19.0,  34.0,   29.0,  42.0)),
    "TUR": ("Turkey",               (  26.0,  36.0,   45.0,  42.0)),
    "MAR": ("Morocco",              ( -13.0,  21.0,   -1.0,  36.0)),
    "DZA": ("Algeria",              (  -9.0,  19.0,   12.0,  37.0)),
    "EGY": ("Egypt",                (  24.0,  22.0,   36.0,  31.0)),
    "MLI": ("Mali",                 ( -12.0,  10.0,    4.0,  25.0)),
    "NER": ("Niger",                (   0.0,  12.0,   16.0,  23.0)),
    "NGA": ("Nigeria",              (   3.0,   4.0,   14.0,  14.0)),
    "TCD": ("Chad",                 (  14.0,   7.0,   24.0,  23.0)),
    "SDN": ("Sudan",                (  22.0,   9.0,   38.0,  22.0)),
    "ETH": ("Ethiopia",             (  33.0,   3.0,   48.0,  14.0)),
    "KEN": ("Kenya",                (  34.0,  -5.0,   41.0,   5.0)),
    "ZAF": ("South Africa",         (  16.0, -35.0,   33.0, -22.0)),
    "AUS": ("Australia",            ( 113.0, -39.0,  154.0, -10.0)),
    "IND": ("India",                (  68.0,   8.0,   97.0,  35.0)),
    "PAK": ("Pakistan",             (  61.0,  24.0,   77.0,  37.0)),
    "CHN": ("China",                (  74.0,  18.0,  135.0,  53.0)),
    "MNG": ("Mongolia",             (  88.0,  41.0,  120.0,  52.0)),
    "RUS": ("Russia",               (  20.0,  41.0,  180.0,  78.0)),
    "IDN": ("Indonesia",            (  95.0, -11.0,  141.0,   6.0)),
    "PHL": ("Philippines",          ( 117.0,   5.0,  127.0,  19.0)),
    "VNM": ("Vietnam",              ( 102.0,   8.0,  110.0,  23.0)),
}

# Per-country priors: (drought_factor 0..1, biomass_factor 0..1).
# Drives realistic country-by-country variation in synthesize_scene + R.
COUNTRY_PRIORS = {
    "USA": (0.50, 0.70), "CAN": (0.25, 0.85), "MEX": (0.60, 0.40),
    "BRA": (0.20, 0.95), "ARG": (0.40, 0.50), "CHL": (0.55, 0.40),
    "PER": (0.35, 0.65), "COL": (0.20, 0.85), "VEN": (0.30, 0.75),
    "ESP": (0.70, 0.55), "FRA": (0.45, 0.70), "PRT": (0.70, 0.60),
    "ITA": (0.60, 0.60), "GRC": (0.75, 0.50), "TUR": (0.65, 0.55),
    "MAR": (0.78, 0.30), "DZA": (0.85, 0.20), "EGY": (0.92, 0.08),
    "MLI": (0.85, 0.30), "NER": (0.85, 0.25), "NGA": (0.55, 0.70),
    "TCD": (0.85, 0.25), "SDN": (0.85, 0.25), "ETH": (0.55, 0.55),
    "KEN": (0.50, 0.60), "ZAF": (0.55, 0.50),
    "AUS": (0.82, 0.55), "IND": (0.55, 0.55), "PAK": (0.78, 0.30),
    "CHN": (0.45, 0.60), "MNG": (0.65, 0.30), "RUS": (0.30, 0.75),
    "IDN": (0.20, 0.95), "PHL": (0.30, 0.85), "VNM": (0.35, 0.85),
}

ESRI_WORLD_IMAGERY = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
ESRI_BOUNDARIES_PLACES = (
    "https://services.arcgisonline.com/arcgis/rest/services/Reference/"
    "World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
)

# ============================================================================
# HELPERS
# ============================================================================

def bbox_area_km2(bbox):
    lon_min, lat_min, lon_max, lat_max = bbox
    mean_lat = (lat_min + lat_max) / 2.0
    width_km = (lon_max - lon_min) * 111.32 * np.cos(np.deg2rad(mean_lat))
    height_km = (lat_max - lat_min) * 111.0
    return abs(width_km * height_km)


def severity_breakdown(z, layer_label):
    arr = np.asarray(z, dtype=float).ravel()
    if "0-1)" in layer_label or "Atm. Dryness" in layer_label:
        arr = arr * 10.0
    if "(-1 dry" in layer_label:
        arr = (1 - ((arr + 1) / 2)) * 10.0
    if "(m)" in layer_label:
        bins = [(0, 2, "<2 m"), (2, 5, "2-5 m"), (5, 10, "5-10 m"),
                (10, 20, "10-20 m"), (20, 60, ">20 m")]
        return ({lab: float(np.mean((arr >= lo) & (arr < hi))) * 100
                 for lo, hi, lab in bins}, "height")
    bands = [(0.0, 1.5, "NOMINAL"), (1.5, 3.5, "ADVISORY"),
             (3.5, 6.0, "WATCH"), (6.0, 8.0, "WARNING"), (8.0, 10.1, "CRITICAL")]
    return ({lab: float(np.mean((arr >= lo) & (arr < hi))) * 100
             for lo, hi, lab in bands}, "alert")


def hotspot_coords(z, lons, lats, k=3):
    flat = z.ravel()
    idx = np.argpartition(flat, -k)[-k:]
    idx = idx[np.argsort(flat[idx])[::-1]]
    LON, LAT = np.meshgrid(lons, lats)
    return [(float(LAT.ravel()[i]), float(LON.ravel()[i]), float(flat[i])) for i in idx]


# -------- Raster overlay helpers --------
_LUT_STOPS = {
    "Reds":   [(255,245,240),(252,187,161),(251,106, 74),(203, 24, 29),(103,  0, 13)],
    "OrRd":   [(255,247,236),(253,212,158),(253,141, 60),(215, 48, 31),(127,  0,  0)],
    "YlOrBr": [(255,255,229),(254,217,142),(254,153, 41),(217, 95, 14),(102, 37,  6)],
    "YlOrRd": [(255,255,178),(254,217,118),(253,141, 60),(240, 59, 32),(189,  0, 38)],
    "Blues":  [(247,251,255),(198,219,239),(107,174,214),( 33,113,181),(  8, 48,107)],
    "Greens": [(247,252,245),(199,233,192),(116,196,118),( 35,139, 69),(  0, 68, 27)],
}


def _colormap_lut(name, n=256):
    stops = _LUT_STOPS.get(name, _LUT_STOPS["Reds"])
    xs = np.linspace(0, 1, len(stops))
    ts = np.linspace(0, 1, n)
    rgb = np.zeros((n, 3), dtype=np.uint8)
    for i in range(3):
        ys = [s[i] for s in stops]
        rgb[:, i] = np.clip(np.interp(ts, xs, ys), 0, 255).astype(np.uint8)
    return rgb


def array_to_png_data_uri(z, cmap_name, alpha=0.75, threshold_pct=0):
    """Render array as PNG. threshold_pct (0-99): pixels below that
    percentile of finite values become fully transparent, so only the
    most-critical pixels remain visible against the satellite basemap."""
    from PIL import Image
    import io, base64
    arr = np.asarray(z, dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        vmin, vmax = 0.0, 1.0
    else:
        vmin, vmax = float(finite.min()), float(finite.max())
    norm = np.clip((arr - vmin) / max(vmax - vmin, 1e-9), 0, 1)
    idx = (norm * 255).astype(np.uint8)
    lut = _colormap_lut(cmap_name)
    rgb = lut[idx]
    # Per-pixel alpha (default uniform)
    a = np.full(rgb.shape[:-1], int(alpha * 255), dtype=np.uint8)
    if threshold_pct > 0 and finite.size > 0:
        cutoff = float(np.percentile(finite, threshold_pct))
        mask_below = arr < cutoff
        a[mask_below] = 0  # fully transparent below cutoff
    rgba = np.concatenate([rgb, a[..., None]], axis=-1)
    rgba = np.flipud(rgba)
    img = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ============================================================================
# CORE COMPUTATIONS (cached)
# ============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def compute_country_risk_grid(w1: float, w2: float) -> pd.DataFrame:
    """Mean R per country, driven by per-country drought + biomass priors
    so the leaderboard actually differentiates regions. Cached 1 h."""
    rows = []
    for iso, (name, bbox) in COUNTRIES.items():
        drought, biomass_factor = COUNTRY_PRIORS.get(iso, (0.55, 0.5))
        # Country-specific seed = stable hash, so each country looks unique
        seed = abs(hash(iso)) % 10000
        s = synthesize_scene(bbox=bbox, n=48, seed=seed, drought_intensity=drought)
        # Scale canopy by per-country biomass density
        height_scaled = np.clip(s.height * (0.4 + 1.4 * biomass_factor), 0.0, 60.0)
        R = calculate_resilience_risk(
            ndmi=s.ndmi, esi=s.esi, gedi_height=height_scaled, w1=w1, w2=w2
        )
        BDI = ((1 - ((s.ndmi + 1) / 2)) * np.log1p(height_scaled) * 2.5)
        rows.append({
            "iso": iso,
            "country": name,
            "mean_R": float(np.mean(R)),
            "peak_R": float(np.max(R)),
            "critical_pct": float(np.mean(R >= 3.0)) * 100,
            "warning_pct": float(np.mean(R >= 2.4)) * 100,
            "watch_pct":   float(np.mean((R >= 1.6) & (R < 2.4))) * 100,
            "peak_BDI":    float(np.max(BDI)),
            "drought_prior": drought,
            "biomass_prior": biomass_factor,
            "bbox": bbox,
        })
    return pd.DataFrame(rows).sort_values("peak_R", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=600, show_spinner=False)
def temporal_timeline(bbox_key: tuple, w1: float, w2: float, iso: str = "", days: int = 14) -> pd.DataFrame:
    """N-day R timeseries with per-country drought + biomass prior baked in."""
    bbox = tuple(bbox_key)
    base_drought, biomass_factor = COUNTRY_PRIORS.get(iso, (0.55, 0.5))
    seed_base = abs(hash(iso)) % 10000 if iso else 42
    rng = np.random.default_rng(seed_base)
    rows = []
    today = date.today()
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        # Drought drifts up over the window from baseline -> 1.4x baseline
        intensity = base_drought * (0.7 + 0.7 * (i / max(days - 1, 1))) + 0.03 * rng.standard_normal()
        intensity = float(np.clip(intensity, 0.05, 0.95))
        s = synthesize_scene(bbox=bbox, n=48, seed=seed_base + i, drought_intensity=intensity)
        height_scaled = np.clip(s.height * (0.4 + 1.4 * biomass_factor), 0.0, 60.0)
        R = calculate_resilience_risk(
            ndmi=s.ndmi, esi=s.esi, gedi_height=height_scaled, w1=w1, w2=w2
        )
        rows.append({
            "date": d.isoformat(),
            "mean_R": float(np.mean(R)),
            "peak_R": float(np.max(R)),
            "critical_pct": float(np.mean(R >= 3.0)) * 100,
            "warning_pct": float(np.mean(R >= 2.4)) * 100,
            "alert_level": alert_for_score(float(np.max(R)))["level"],
            "drought_intensity": intensity,
        })
    return pd.DataFrame(rows)


def consecutive_days_at_or_above(series: pd.Series, threshold: float) -> int:
    """How many consecutive trailing days the series has been >= threshold."""
    n = 0
    for v in reversed(series.tolist()):
        if v >= threshold:
            n += 1
        else:
            break
    return n


# ============================================================================
# SIDEBAR -- mission controls + leaderboard (always visible)
# ============================================================================

with st.sidebar:
    st.title("Arid-Edge Sentinel")
    st.caption("Command Center  -  NASA Space to Soil 2026")

    # Apply any pending view-mode change from a previous rerun BEFORE the
    # radio is instantiated. Streamlit forbids writing to a widget's own
    # session_state key after the widget exists, so we use this indirection.
    if "_pending_view_mode" in st.session_state:
        st.session_state["view_mode_key"] = st.session_state.pop("_pending_view_mode")

    view_mode = st.radio(
        "View mode",
        ["Global view", "Country drill-in"],
        key="view_mode_key",
        help="Global = world choropleth + leaderboard. Drill-in = pick a country and see the full R analysis.",
    )

    st.divider()
    st.subheader("Algorithm Weights")
    st.caption("R = (w1 * dryness + w2 * stress) * ln(1+H)")
    w1 = st.slider("w1 -- Hydraulic stress (NDMI)", 0.0, 1.0, 0.5, 0.05)
    w2 = st.slider("w2 -- Physiological stress (ESI)", 0.0, 1.0, 0.5, 0.05)
    if abs((w1 + w2) - 1.0) > 0.001:
        _wsum = max(w1 + w2, 1e-9)
        st.caption(f"Auto-normalized -> w1={w1/_wsum:.2f}, w2={w2/_wsum:.2f}")

    st.divider()
    st.subheader("NASA Earthdata")
    user = st.text_input("Username", value=os.getenv("EARTHDATA_USERNAME", ""))
    pwd = st.text_input("Password", value=os.getenv("EARTHDATA_PASSWORD", ""), type="password")
    if st.button("Connect", use_container_width=True):
        os.environ["EARTHDATA_USERNAME"] = user
        os.environ["EARTHDATA_PASSWORD"] = pwd
        with st.spinner("Authenticating..."):
            auth = authenticate("environment")
        st.session_state["auth_ok"] = auth is not None

# Compute country leaderboard once (cached)
with st.spinner("Scoring countries..."):
    leaderboard = compute_country_risk_grid(w1, w2)


# ============================================================================
# Algorithm Spotlight (always shown -- core of the submission)
# ============================================================================

def render_algorithm_spotlight(scene=None, label_for_R="across all listed countries"):
    """Render the Section 3.2 formula + a live decomposition."""
    st.subheader("Algorithm  -  Resilience Risk Score (Section 3.2)")

    # Full-width formula row (LaTeX needs the whole page so it doesn't overflow)
    st.latex(r"R \;=\; \Big( w_1 \cdot \big[1 - NDMI_{norm}\big] \;+\; w_2 \cdot \big[1 - ESI_{norm}\big] \Big) \;\times\; \ln\big(1 + H_{GEDI}\big)")
    st.caption(
        "Hydraulic stress (Landsat NDMI) + Physiological stress (ECOSTRESS ESI), "
        "scaled by biomass-at-stake (GEDI / ICESat-2 canopy height). Logarithmic "
        "height keeps tall timberlands and short regenerative crops both visible."
    )

    # Live decomposition below (full width too, so the metric cards are big)
    with st.container():
        if scene is None:
            # Use leaderboard aggregates
            mean_R = float(leaderboard["mean_R"].mean())
            peak_R = float(leaderboard["peak_R"].max())
            top = leaderboard.iloc[0]
            cols = st.columns(4)
            cols[0].metric("Mean R", f"{mean_R:.2f}", label_for_R)
            cols[1].metric("Peak R", f"{peak_R:.2f}", f"in {top['country']}")
            cols[2].metric("Top country", top["country"], f"R={top['peak_R']:.2f}")
            cols[3].metric("Countries scored", str(len(leaderboard)),
                           f"weights w1={w1:.2f}, w2={w2:.2f}")
        else:
            _dry = float(np.mean(1.0 - ((scene.ndmi + 1.0) / 2.0)))
            _str = float(np.mean(1.0 - scene.esi))
            _bio = float(np.mean(np.log1p(scene.height)))
            _wsum = max(w1 + w2, 1e-9)
            _w1n, _w2n = w1 / _wsum, w2 / _wsum
            _Rmean = (_w1n * _dry + _w2n * _str) * _bio
            cols = st.columns(4)
            cols[0].metric("1 - NDMI_norm",  f"{_dry:.2f}", "Hydraulic")
            cols[1].metric("1 - ESI_norm",   f"{_str:.2f}", "Physiological")
            cols[2].metric("ln(1 + H_GEDI)", f"{_bio:.2f}",
                           f"mean H = {float(np.mean(scene.height)):.1f} m")
            cols[3].metric("Mean R (AOI)",   f"{_Rmean:.2f}",
                           alert_for_score(_Rmean)["level"])

            _hyd = _w1n * _dry; _phy = _w2n * _str
            _tot = max(_hyd + _phy, 1e-9)
            _hp = _hyd / _tot * 100; _pp = _phy / _tot * 100
            sf = go.Figure()
            sf.add_trace(go.Bar(name=f"Hydraulic ({_hp:.0f}%)", y=["share"], x=[_hp],
                                orientation="h", marker=dict(color="#1f77b4"),
                                hovertemplate=f"Hydraulic: {_hp:.1f}%%<extra></extra>"))
            sf.add_trace(go.Bar(name=f"Physiological ({_pp:.0f}%)", y=["share"], x=[_pp],
                                orientation="h", marker=dict(color="#d62728"),
                                hovertemplate=f"Physiological: {_pp:.1f}%%<extra></extra>"))
            sf.update_layout(barmode="stack", height=85, showlegend=True,
                             legend=dict(orientation="h", y=-0.6, x=0),
                             margin=dict(l=10, r=10, t=10, b=5),
                             xaxis=dict(range=[0, 100], title="Stress contribution share"),
                             yaxis=dict(showticklabels=False))
            st.plotly_chart(sf, use_container_width=True)


# ============================================================================
# GLOBAL VIEW
# ============================================================================

def render_global_view():
    st.title("Global Resilience Risk  -  Command Center")
    st.markdown(
        "World view: each country is colored by **mean Resilience Risk** "
        "computed via the Section 3.2 formula. Click the leaderboard buttons "
        "(left sidebar) to drill into any country's full R analysis."
    )

    # Sidebar leaderboard
    with st.sidebar:
        st.divider()
        st.subheader("Risk Leaderboard")
        st.caption("Click any country to drill in.")
        for i, row in leaderboard.head(10).iterrows():
            level = alert_for_score(row["peak_R"])["level"]
            color = ALERT_COLOR.get(level, "#666")
            label = f"#{i+1}  {row['country']}  -  R {row['peak_R']:.2f}"
            if st.button(label, key=f"drill_{row['iso']}", use_container_width=True):
                st.session_state["drill_iso"] = row["iso"]
                st.session_state["_pending_view_mode"] = "Country drill-in"
                st.rerun()

    # KPI row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Countries scored",   str(len(leaderboard)))
    k2.metric("Highest peak R",     f"{leaderboard['peak_R'].max():.2f}",
              leaderboard.iloc[0]["country"])
    k3.metric("Highest mean R",     f"{leaderboard['mean_R'].max():.2f}",
              leaderboard.sort_values('mean_R', ascending=False).iloc[0]["country"])
    k4.metric("Most WARNING area",  f"{leaderboard['warning_pct'].max():.1f}%",
              leaderboard.sort_values('warning_pct', ascending=False).iloc[0]["country"])

    # Algorithm spotlight (uses leaderboard aggregates)
    render_algorithm_spotlight(scene=None)

    # World choropleth
    st.subheader("World Map  -  Mean Resilience Risk by Country")
    fig = px.choropleth(
        leaderboard,
        locations="iso",
        color="peak_R",
        hover_name="country",
        hover_data={"iso": False, "peak_R": ":.2f", "mean_R": ":.2f", "warning_pct": ":.1f"},
        color_continuous_scale="Reds",
        labels={"peak_R": "Peak R", "mean_R": "Mean R", "warning_pct": "% WARNING"},
        range_color=[float(leaderboard["peak_R"].min()),
                     float(leaderboard["peak_R"].max())],
    )
    fig.update_geos(
        showcountries=True, countrycolor="#888",
        showcoastlines=True, coastlinecolor="#aaa",
        showland=True, landcolor="#f4f4f4",
        showocean=True, oceancolor="#e6f0fa",
        projection_type="natural earth",
    )
    fig.update_layout(height=620, margin=dict(l=0, r=0, t=10, b=0),
                      coloraxis_colorbar=dict(title="Peak R"))

    selected = st.plotly_chart(fig, use_container_width=True,
                               key="globe", on_select="rerun")
    # Capture clicks on the choropleth
    if selected and selected.get("selection") and selected["selection"].get("points"):
        pts = selected["selection"]["points"]
        if pts:
            iso = pts[0].get("location") or pts[0].get("hovertext")
            if iso and iso in COUNTRIES:
                st.session_state["drill_iso"] = iso
                st.session_state["_pending_view_mode"] = "Country drill-in"
                st.rerun()

    # Full leaderboard table
    st.subheader("Full Country Leaderboard")
    show_df = leaderboard[["country", "peak_R", "mean_R", "critical_pct", "warning_pct", "watch_pct", "peak_BDI"]].copy()
    show_df.columns = ["Country", "Peak R", "Mean R", "% CRITICAL", "% WARNING", "% WATCH", "Peak BDI"]
    show_df.index = show_df.index + 1
    st.dataframe(show_df.style.format({
        "Peak R": "{:.2f}", "Mean R": "{:.2f}",
        "% CRITICAL": "{:.1f}", "% WARNING": "{:.1f}", "% WATCH": "{:.1f}", "Peak BDI": "{:.2f}",
    }), use_container_width=True)


# ============================================================================
# COUNTRY DRILL-IN VIEW
# ============================================================================

def render_country_drill():
    iso_default = st.session_state.get("drill_iso", "NER")
    if iso_default not in COUNTRIES:
        iso_default = "NER"

    iso = st.sidebar.selectbox(
        "Country",
        list(COUNTRIES.keys()),
        index=list(COUNTRIES.keys()).index(iso_default),
        format_func=lambda k: f"{k}  -  {COUNTRIES[k][0]}",
    )
    st.session_state["drill_iso"] = iso
    name, bbox = COUNTRIES[iso]
    drought_prior, biomass_prior = COUNTRY_PRIORS.get(iso, (0.55, 0.5))

    st.sidebar.divider()
    st.sidebar.subheader("Map controls")
    show_places = st.sidebar.toggle("Country / city labels", value=True)
    overlay_style = st.sidebar.radio(
        "Data overlay", ["Raster image", "Bubble grid"], index=0, horizontal=True,
    )
    overlay_alpha = st.sidebar.slider("Overlay opacity", 0.3, 1.0, 0.80, 0.05)
    threshold_pct = st.sidebar.slider(
        "Critical pixel threshold (%)", 0, 95, 70, 5,
        help="Hide all pixels below this percentile -- only the top (100-X)% remain visible. "
             "70 means only the worst 30% of pixels show; 90 means only the worst 10%.",
    )
    st.sidebar.toggle("Manual zoom override", value=False, key="use_manual_zoom")
    st.sidebar.slider("Map zoom", 1.0, 14.0, 5.0, 0.5,
                      key="manual_zoom_override",
                      disabled=not st.session_state.get("use_manual_zoom", False))
    use_synthetic = st.sidebar.toggle("Use synthetic scene", value=True)
    days_back = st.sidebar.slider("Timeline window (days)", 7, 30, 14)

    st.sidebar.divider()
    st.sidebar.subheader("Timelapse")
    timelapse_day = st.sidebar.slider(
        "Day in window (1 = oldest, N = today)", 1, days_back, days_back,
        help="Drag to scrub through the spatial-temporal evolution.",
    )
    threshold = st.sidebar.slider("ECOSTRESS ESI trigger", 0.10, 0.90,
                                   float(ADAPTIVE_ESI_THRESHOLD), 0.05)

    st.title(f"{name}  -  Country Drill-in")
    st.caption(f"ISO {iso}  -  bbox {bbox}  -  drought prior {drought_prior:.2f}  -  "
               f"biomass prior {biomass_prior:.2f}  -  weights w1={w1:.2f}, w2={w2:.2f}")

    # Per-country drought intensity for the chosen day in the timelapse
    rng_day = np.random.default_rng(abs(hash(iso)) % 10000 + timelapse_day)
    intensity_day = float(np.clip(
        drought_prior * (0.7 + 0.7 * ((timelapse_day - 1) / max(days_back - 1, 1)))
        + 0.03 * rng_day.standard_normal(),
        0.05, 0.95
    ))
    scene = synthesize_scene(
        bbox=bbox, n=96,
        seed=abs(hash(iso)) % 10000 + timelapse_day,
        drought_intensity=intensity_day,
    )
    scene.height = np.clip(scene.height * (0.4 + 1.4 * biomass_prior), 0.0, 60.0)
    scene.risk = calculate_resilience_risk(
        ndmi=scene.ndmi, esi=scene.esi, gedi_height=scene.height, w1=w1, w2=w2
    )
    scene.wildfire_risk = ((1 - ((scene.ndmi + 1) / 2)) * np.log1p(scene.height) * 2.5)
    area_km2 = bbox_area_km2(bbox)
    end_d = date.today()
    start_d = end_d - timedelta(days=days_back)
    temporal = (start_d.isoformat(), end_d.isoformat())

    # Run mission button
    if st.button("Run Mission (live API + adaptive fusion)", type="primary"):
        with st.spinner("Querying CMR + running adaptive fusion..."):
            mission = run_adaptive_pipeline(
                bbox=bbox, temporal=temporal, threshold=threshold,
                synthetic_esi=0.32 if use_synthetic else None,
                synthetic_ndmi=-0.22 if use_synthetic else None,
                synthetic_gedi_height=9.5 if use_synthetic else None,
            )
        st.session_state[f"mission_{iso}"] = mission
    mission = st.session_state.get(f"mission_{iso}")

    # KPIs
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("AOI area", f"{area_km2:,.0f} km^2")
    k2.metric("Mean R", f"{float(np.mean(scene.risk)):.2f}",
              alert_for_score(float(np.mean(scene.risk)))["level"])
    k3.metric("Peak R", f"{float(np.max(scene.risk)):.2f}",
              alert_for_score(float(np.max(scene.risk)))["level"])
    k4.metric("% CRITICAL", f"{float(np.mean(scene.risk >= 3.0)) * 100:.1f}%",
              f"~{area_km2 * float(np.mean(scene.risk >= 3.0)):,.0f} km^2 in CRITICAL")
    k5.metric("Mean LST", f"{float(np.mean(scene.lst) - 273.15):.1f} C")

    # Algorithm spotlight (per-country)
    render_algorithm_spotlight(scene=scene)

    # Layer selector + map
    st.subheader("Mission Map")
    LAYERS = {
        "Fused Risk":                  (scene.risk,                "Reds",   "Resilience Risk (0-10)"),
        "Wildfire Risk (BDI)":         (scene.wildfire_risk,       "OrRd",   "Biomass-to-Dryness (0-10)"),
        "Atmospheric Dryness (VPD)":   (scene.atmospheric_dryness, "YlOrBr", "Atm. Dryness (0-1)"),
        "Thermal Stress (ECOSTRESS)":  (1 - scene.esi,             "YlOrRd", "Stress (0-1, 1=high)"),
        "Moisture (Landsat)":          (scene.ndmi,                "Blues",  "NDMI (-1 dry, +1 wet)"),
        "Biomass (GEDI)":              (scene.height,              "Greens", "Canopy Height (m)"),
    }
    layer_name = st.radio("Active layer", list(LAYERS.keys()), horizontal=True)
    z, cmap, label = LAYERS[layer_name]

    LON, LAT = np.meshgrid(scene.lons, scene.lats)
    aoi_lon = [bbox[0], bbox[2], bbox[2], bbox[0], bbox[0]]
    aoi_lat = [bbox[1], bbox[1], bbox[3], bbox[3], bbox[1]]
    center_lon = (bbox[0] + bbox[2]) / 2
    center_lat = (bbox[1] + bbox[3]) / 2

    _span_lon = max(bbox[2] - bbox[0], 0.01)
    _span_lat = max(bbox[3] - bbox[1], 0.01)
    _z_lon = float(np.log2(360.0 * 1400.0 / (_span_lon * 256.0)))
    _z_lat = float(np.log2(180.0 *  620.0 / (_span_lat * 256.0)))
    auto_zoom = float(np.clip(min(_z_lon, _z_lat) - 0.3, 1.0, 14.0))
    zoom = (float(st.session_state.get("manual_zoom_override", auto_zoom))
            if st.session_state.get("use_manual_zoom") else auto_zoom)

    hots = hotspot_coords(z, scene.lons, scene.lats, k=3)
    basemap = go.Figure()

    if overlay_style == "Raster image":
        img_uri = array_to_png_data_uri(z, cmap, alpha=overlay_alpha, threshold_pct=threshold_pct)
        basemap.add_trace(go.Scattermapbox(
            lon=[center_lon], lat=[center_lat], mode="markers",
            marker=dict(size=0.1, color=[float(np.nanmin(z)), float(np.nanmax(z))],
                        colorscale=cmap, opacity=0.0,
                        showscale=True, cmin=float(np.nanmin(z)), cmax=float(np.nanmax(z)),
                        colorbar=dict(title=label, x=1.01, thickness=18)),
            hoverinfo="skip", showlegend=False, name=layer_name,
        ))
    else:
        step = max(1, scene.lons.shape[0] // 32)
        basemap.add_trace(go.Scattermapbox(
            lon=LON[::step, ::step].ravel(), lat=LAT[::step, ::step].ravel(), mode="markers",
            marker=dict(size=28, color=z[::step, ::step].ravel(), colorscale=cmap,
                        opacity=overlay_alpha, showscale=True,
                        colorbar=dict(title=label, x=1.01, thickness=18)),
            hovertemplate=("lat %{lat:.2f}, lon %{lon:.2f}<br>"
                           + layer_name + ": %{marker.color:.2f}<extra></extra>"),
            name=layer_name,
        ))

    # AOI shadow + magenta line
    basemap.add_trace(go.Scattermapbox(lon=aoi_lon, lat=aoi_lat, mode="lines",
        line=dict(width=10, color="#000000"), hoverinfo="skip", showlegend=False))
    basemap.add_trace(go.Scattermapbox(lon=aoi_lon, lat=aoi_lat, mode="lines",
        line=dict(width=5, color="#ff00ff"), name="Mission AOI", hoverinfo="skip"))
    # Hotspots
    basemap.add_trace(go.Scattermapbox(
        lon=[h[1] for h in hots], lat=[h[0] for h in hots],
        mode="markers", marker=dict(size=24, color="#000000"),
        hoverinfo="skip", showlegend=False))
    basemap.add_trace(go.Scattermapbox(
        lon=[h[1] for h in hots], lat=[h[0] for h in hots],
        mode="markers+text", marker=dict(size=18, color="#ffeb3b"),
        text=[f"  #{i+1} = {h[2]:.2f}" for i, h in enumerate(hots)],
        textposition="middle right",
        textfont=dict(color="#ffeb3b", size=14, family="Arial Black"),
        name="Top hotspots",
        hovertemplate=("Hotspot %{text}<br>lat %{lat:.3f}, lon %{lon:.3f}<extra></extra>"),
    ))

    map_layers = [dict(sourcetype="raster", source=[ESRI_WORLD_IMAGERY],
                       sourceattribution="(c) Esri World Imagery", below="traces")]
    if show_places:
        map_layers.append(dict(sourcetype="raster", source=[ESRI_BOUNDARIES_PLACES],
                               sourceattribution="(c) Esri Boundaries & Places", below="traces"))
    if overlay_style == "Raster image":
        map_layers.append(dict(
            sourcetype="image", source=img_uri,
            coordinates=[[bbox[0], bbox[3]], [bbox[2], bbox[3]],
                         [bbox[2], bbox[1]], [bbox[0], bbox[1]]],
            below="traces",
        ))

    basemap.update_layout(
        mapbox=dict(style="white-bg", layers=map_layers,
                    center=dict(lon=center_lon, lat=center_lat), zoom=zoom),
        height=620, margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", x=0.0, y=1.02, yanchor="bottom",
                    bgcolor="rgba(0,0,0,0.6)", font=dict(color="white", size=12)),
    )
    st.plotly_chart(basemap, use_container_width=True)

    # ---- Spatial-Temporal Timeline ----
    st.subheader("Spatial-Temporal Timeline  -  last "
                 + str(days_back) + " days")
    tl = temporal_timeline(tuple(bbox), w1, w2, iso=iso, days=days_back)
    days_critical = consecutive_days_at_or_above(tl["peak_R"], 3.0)
    days_warning  = consecutive_days_at_or_above(tl["peak_R"], 2.4)
    days_watch    = consecutive_days_at_or_above(tl["peak_R"], 1.6)

    # Colored bars by alert level + mean line
    color_by_level = [ALERT_COLOR.get(lvl, "#888") for lvl in tl["alert_level"]]
    tlfig = go.Figure()
    tlfig.add_trace(go.Bar(
        x=tl["date"], y=tl["peak_R"], marker=dict(color=color_by_level),
        name="Peak R per day",
        hovertemplate="%{x}<br>Peak R: %{y:.2f}<extra></extra>",
    ))
    tlfig.add_trace(go.Scatter(
        x=tl["date"], y=tl["mean_R"], mode="lines+markers",
        line=dict(color="#222", width=2), marker=dict(size=6),
        name="Mean R", hovertemplate="%{x}<br>Mean R: %{y:.2f}<extra></extra>",
    ))
    tlfig.update_layout(
        height=320, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Date", yaxis_title="R (0-10)",
        legend=dict(orientation="h", y=-0.3),
    )
    st.plotly_chart(tlfig, use_container_width=True)

    tcol1, tcol2, tcol3, tcol4 = st.columns(4)
    tcol1.metric("Consecutive CRITICAL days", str(days_critical),
                 "peak R >= 3.0")
    tcol2.metric("Consecutive WARNING days",  str(days_warning),
                 "peak R >= 2.4")
    tcol3.metric("Consecutive WATCH days",    str(days_watch),
                 "peak R >= 1.6")
    tcol4.metric("Worst day in window",
                 tl.loc[tl["peak_R"].idxmax(), "date"],
                 f"peak R {tl['peak_R'].max():.2f}")

    st.caption(
        "Each bar = the daily AOI peak R, colored by alert level. "
        "Black line = AOI mean R. The 'consecutive days' counters quantify "
        "how long the country has been in crisis -- the spatial-temporal "
        "duration NASA's mission planners need to prioritize intervention."
    )

    # ---- Hotspot table ----
    st.subheader("Top Hotspots inside " + name)
    hot_df = pd.DataFrame([
        {"#": i + 1, "Lat": f"{h[0]:.3f}", "Lon": f"{h[1]:.3f}",
         "R": f"{h[2]:.2f}",
         "Severity": alert_for_score(h[2])["level"]
                      if "0-10" in label else "-"}
        for i, h in enumerate(hots)
    ])
    st.dataframe(hot_df, use_container_width=True, hide_index=True)

    # ---- Mission timeline + Alert ----
    if mission:
        left, right = st.columns([2, 1])
        with left:
            st.subheader("Mission Timeline (adaptive fusion)")
            tl_df = pd.DataFrame([
                {"t (s)": round(e.t_offset_s, 3), "Sensor": e.sensor,
                 "Action": e.action, "Detail": e.detail}
                for e in mission.timeline
            ])
            st.dataframe(tl_df, use_container_width=True, hide_index=True)
        with right:
            st.subheader("Actionable Alert")
            color = ALERT_COLOR.get(mission.alert["level"], "#666")
            st.markdown(
                f"""<div style="border-left:6px solid {color}; padding:12px 16px;
                background:rgba(0,0,0,0.03); border-radius:6px;">
                <div style="font-size:12px; color:#555; letter-spacing:1px;">ALERT LEVEL</div>
                <div style="font-size:28px; font-weight:700; color:{color};">{mission.alert['level']}</div>
                <div style="margin-top:8px; font-size:14px;">{mission.alert['action']}</div>
                <div style="margin-top:12px; font-size:12px; color:#666;">
                  Resilience Risk Score: <b>{mission.risk_score:.2f}</b> / 10
                </div></div>""",
                unsafe_allow_html=True,
            )

    # Back to global
    st.divider()
    if st.button("Back to Global view"):
        st.session_state["_pending_view_mode"] = "Global view"
        st.rerun()


# ============================================================================
# ROUTING
# ============================================================================

# View mode is already resolved by the keyed radio at the top of the sidebar.
if view_mode == "Global view":
    render_global_view()
else:
    render_country_drill()

st.divider()
st.caption("Datasets: ECO_L4_ESI_PTJPL  -  HLSL30  -  GEDI02_A  -  ECOSTRESS L2 LSTE.  "
           "Tiles: Esri World Imagery + Esri Boundaries & Places.  "
           "Built for NASA Space to Soil Challenge 2026.")
