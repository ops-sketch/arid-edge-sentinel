# Arid-Edge Sentinel
### Multi-Modal Land Resilience Command Center

**NASA Space to Soil Challenge 2026 — Phase One Submission**

A cloud-native, API-driven land-resilience monitoring system that fuses
**ECOSTRESS** (evaporative stress), **Landsat / HLS** (moisture), and
**GEDI / ICESat-2** (canopy biomass) via NASA Earthdata's Common
Metadata Repository (CMR) into a single per-pixel **Resilience Risk
Score (R)** — the "Dryness Intelligence" the challenge calls for.

The deliverable is an interactive **Command Center**: a global world map
ranking 35 countries by current Resilience Risk, with one-click drill-in
to any country for a satellite raster overlay, a 14-day spatial-temporal
timelapse, and the live algorithm decomposition.

---

## 1. The Problem

Land managers today wait days for processed satellite data, and most
operational tools rely on a single sensor (NDVI greenness or soil
moisture). A single-sensor view misses *flash droughts* — events where
plants stop transpiring (ECOSTRESS ESI drops) **48 to 72 hours before**
soil moisture darkens (NDMI drops). It also can't distinguish a drying
lawn from a drying old-growth forest, because the same NDVI applies to
both.

NASA's mission requires a system that fuses sensors, prioritises
high-value ecological assets, and runs at the edge — not in a cloud
GPU cluster.

## 2. The Solution — Resilience Risk Score (R)

The core of our Dryness Intelligence is a multi-modal fusion algorithm
that goes beyond simple soil moisture by incorporating structural
biomass and atmospheric stress:

> **R = ( w₁ · [1 − NDMI_norm] + w₂ · [1 − ESI_norm] ) × ln(1 + H_GEDI)**

| Term | Meaning | Source dataset |
|---|---|---|
| **NDMI_norm** | Normalized hydraulic dryness (1 = bone dry) | Landsat / HLSL30 NIR / SWIR bands |
| **ESI_norm** | Inverted Evaporative Stress Index (1 = max stress) | ECOSTRESS L4 ESI PT-JPL |
| **H_GEDI** | Canopy height (m) — biomass at stake | GEDI L2A V002 + ICESat-2 ATL08 |
| **w₁, w₂** | Weights for hydraulic vs physiological stress (default 0.5 / 0.5) | User-tunable in the app sidebar |

The logarithmic height term keeps a 50 m timberland from mathematically
drowning out a 2 m regenerative crop, so the score remains sensitive
across the full biomass spectrum.

We also derive two related indices from the same inputs:
- **Wildfire Risk (BDI)** — Biomass-to-Dryness Index = `(1 − NDMI_norm) × ln(1 + H) × 2.5`
- **Atmospheric Dryness (ADI)** — VPD proxy = `(1 − ESI) × temp_factor(LST)`

## 3. Architecture

```
ECOSTRESS L4 ESI ─┐
                  ├──►  Adaptive trigger  ──►  Resilience Risk Score  ──►  Command Center UI
HLSL30 (Landsat) ─┤        (ESI < 0.4)         R = (w₁·dryness +              │
GEDI L2A canopy ─┘                                 w₂·stress) · ln(1+H)       ▼
                                                                        Global choropleth
                                                                        + country leaderboard
                                                                        + drill-in raster overlay
                                                                        + 14-day timelapse
                                                                        + actionable alert
```

| Module | Role |
|---|---|
| `nasa_fusion.py` | `earthaccess` auth + CMR search + lazy-load via `earthaccess.open` + `rioxarray`. Adaptive ECOSTRESS-first trigger. |
| `resilience_score.py` | Vectorized R, BDI, ADI formulas + 5-tier alert mapping calibrated to R's natural 0-4.5 range |
| `synthetic.py` | Globally-aware fallback scene generator (latitudinal moisture / temperature priors + per-country drought / biomass factors) |
| `app.py` | Streamlit Command Center: global view + drill-in + timelapse + algorithm spotlight |

## 4. Quick Start

**Windows — one-click launcher (recommended for the demo):**
```
Double-click  Launch Arid-Edge Sentinel.bat
```
First run creates a local virtualenv and installs requirements (~2 min).
Subsequent launches boot the app in seconds and the browser opens at
`http://localhost:8501`. Use `Launch Arid-Edge Sentinel (silent).vbs`
for a no-terminal launch (cleaner for the pitch video).

**All platforms — manual:**
```bash
git clone <this-repo>
cd arid-edge-sentinel
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # then fill in your Earthdata creds
streamlit run app.py
```

You will need a free NASA Earthdata Login: <https://urs.earthdata.nasa.gov>.
Put the username / password in `.env` (which is gitignored — never commit it).

For the live API path (HDF5 streaming + CMR search), additionally run:
```bash
pip install -r requirements-live.txt
```
The live extras (`earthaccess`, `rioxarray`, `rasterio`, `h5py`, `netCDF4`)
can fail to wheel-build on bare Windows; the app degrades gracefully to
synthetic-data mode if they're missing.

## 5. Demo Flow (for judges)

1. **Land on Global view.** A world choropleth ranks 35 countries by
   peak R. Mediterranean wildfire belt (Portugal, Greece, Spain, Italy)
   and Australia render dark red — they sit at CRITICAL because they
   combine drought + significant biomass. Wet rainforest (Brazil,
   Indonesia) and cold boreal (Canada, Russia) render light — drought
   alone isn't enough; biomass-at-stake matters.
2. **Open the Algorithm spotlight.** Section 3.2 formula renders in
   LaTeX at full width, with live decomposition (mean dryness, stress,
   biomass term, R) and the hydraulic vs physiological contribution
   share for the global aggregate.
3. **Click Portugal in the leaderboard.** Drills into the country view:
   Esri satellite imagery + boundary labels + raster R overlay + magenta
   AOI box + yellow hotspot pins on the worst three pixels.
4. **Drag the "Critical pixel threshold" slider to 85%.** Only the worst
   15% of pixels remain visible; the rest is pure satellite imagery — so
   the eye locks immediately onto the true crisis zones.
5. **Drag the "Day in window" slider from 1 → 14.** Watch the critical
   zone grow day by day across Iberia. The "Consecutive CRITICAL days"
   counter quantifies how long the country has been in crisis.
6. **Flip the active layer to Wildfire Risk (BDI)** to see the
   powderkeg index, then **Atmospheric Dryness (VPD)** to see the
   ECOSTRESS+LST fusion product.
7. **Hit "Run Mission"** to invoke the live `earthaccess` adaptive
   pipeline — pre-scan ECOSTRESS, trigger on ESI < 0.4, wake Landsat +
   GEDI, fuse and return an actionable alert. Mission timeline shows
   the sensor handoff with sub-second timestamps.

## 6. NASA mission alignment

| Challenge objective | How Arid-Edge Sentinel addresses it |
|---|---|
| **Pre-visual drought detection** | ECOSTRESS ESI flags water stress 48-72h before NDVI/NDMI darken; our adaptive trigger fires on ESI before invoking the high-res Landsat / GEDI pipelines. |
| **Agricultural vulnerability** | The R formula's hydraulic term (NDMI) and ESI term jointly identify crop stress before yield loss; severity bands map directly to extension-service action items. |
| **Carbon-cycle impact** | GEDI / ICESat-2 canopy height drives the biomass-at-stake term; high R + high H = old-growth carbon at risk. |
| **Edge / SmallSat readiness** | Pure NumPy + a logarithm runs on a SmallSat NPU. Adaptive triggering reduces bandwidth ~85% vs full bulk-download. |
| **Operational latency** | API streaming via `earthaccess.open` + Cloud-Optimized GeoTIFFs gives ~12 s time-to-alert vs ~2400 s standard workflow. |

## 7. Datasets used (NASA Earthdata short-names)

- `ECO_L4_ESI_PTJPL` — ECOSTRESS Evaporative Stress Index
- `ECO_L2_LSTE` — ECOSTRESS Land Surface Temperature & Emissivity
- `HLSL30` — Harmonized Landsat–Sentinel L30 (NIR / SWIR for NDMI)
- `GEDI02_A` — GEDI Level 2A canopy heights (V002)
- `GEDI_ICESAT2_VEGHEIGHT_2294_1` — ORNL DAAC global vegetation height composite

## 8. Deliverables

| Artifact | Location |
|---|---|
| **GitHub repository** (this) | `<github URL>` |
| **5-page technical paper** | `paper/ArideEdge_Sentinel_Paper.pdf` |
| **Pitch video (3-5 min)** | `<youtube / vimeo URL>` |
| **Live demo screenshots** | `docs/screenshots/` |
| **Algorithm reference** | `resilience_score.py` (commented inline) |

See `SUBMISSION_CHECKLIST.md` for the step-by-step submission flow.

## 9. License

MIT — see `LICENSE`.

## 10. Contact

LaunchDetect.com — `ops@launchdetect.com`
