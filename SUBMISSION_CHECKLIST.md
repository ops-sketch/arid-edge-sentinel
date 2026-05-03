# Submission Checklist — NASA Space to Soil Challenge 2026

**Deadline: 4 May 2026 (today is 2 May 2026 — 2 days remaining).**

This checklist walks through what to submit and where. **You do NOT
upload the folder itself anywhere.** You submit *links* via the
challenge portal.

---

## Step 1 — Push the repo to GitHub

The judges expect a public GitHub URL, not a zip.

```bash
cd C:\Users\jkell\OneDrive\Documents\Claude\Projects\S2S\arid-edge-sentinel

# One-time setup
git init
git add .
git commit -m "Initial submission — Arid-Edge Sentinel"

# Create a new public repo on GitHub (e.g. via web UI or `gh repo create`)
git remote add origin https://github.com/<your-username>/arid-edge-sentinel.git
git branch -M main
git push -u origin main
```

**Sanity check before pushing:** confirm `.env` is NOT in the staged
files. The `.gitignore` excludes it, but verify:
```bash
git status            # .env should NOT appear
git ls-files | findstr ".env"   # should print only .env.example
```

If `.env` ever leaks, rotate the Earthdata password immediately at
<https://urs.earthdata.nasa.gov>.

---

## Step 2 — Capture demo screenshots

Make a `docs/screenshots/` folder and drop in the key views the judges
should see at a glance:

- `01_global_view.png` — world choropleth with leaderboard
- `02_algorithm_spotlight.png` — Section 3.2 formula + decomposition
- `03_country_drill.png` — Portugal drill-in with raster overlay
- `04_threshold_mask.png` — same view with critical-pixel mask at 85%
- `05_timelapse.png` — same view at day 1 vs day 14

Use Windows + Shift + S to capture, save into the folder, commit, push.

These let judges grasp the product in 30 seconds without booting the app.

---

## Step 3 — Record the pitch video (3–5 min)

Suggested narration arc:

1. **Problem (30 s):** "Current land-resilience tools wait days for
   data and rely on a single sensor — they miss flash droughts that
   start in the atmosphere."
2. **Solution (60 s):** show the Algorithm spotlight, narrate the
   Section 3.2 formula. "We fuse ECOSTRESS, Landsat, and GEDI into one
   per-pixel Resilience Risk Score that weights biomass at stake."
3. **Demo (90 s):** Global view → click Portugal → critical-pixel mask
   to 85% → drag timelapse 1 → 14 → "8 consecutive CRITICAL days
   means immediate intervention."
4. **NASA alignment (30 s):** "Pre-visual detection from ECOSTRESS,
   carbon-asset prioritisation from GEDI, edge-ready in pure NumPy."
5. **Latency stat (15 s):** "Standard workflow: 2400 s. Arid-Edge: 12 s."
6. **Close (15 s):** GitHub URL + team contact.

Upload to YouTube (unlisted is fine) or Vimeo, copy the link.

---

## Step 4 — Polish the 5-page paper

Sections (per the challenge brief):

1. **Abstract** — one paragraph, the formula and what it does
2. **Problem statement** — flash droughts, single-sensor blindness
3. **Algorithm (Section 3.2)** — the R formula in LaTeX, with the
   ATBD-aligned reasoning bullets from the app's "Why this wins" expander
4. **System architecture** — the diagram + module table from the README
5. **Results** — leaderboard screenshot + Portugal drill-in screenshot;
   note the Mediterranean / Australia ranking and what it implies for
   wildfire planners
6. **NASA mission alignment** — the table from README §6
7. **Onboard efficiency** — the latency-comparison chart; argue the
   85% bandwidth reduction
8. **Future work** — wider country coverage, real-time HDF5 streaming
   in production, multi-day forecast
9. **References** — link the four ATBD PDFs

Export to PDF, name it `ArideEdge_Sentinel_Paper.pdf`, drop in
`paper/` folder, commit, push.

---

## Step 5 — Submit on the challenge portal

Go to the official Space to Soil submission page (in the challenge
brief or your team's email). You will be asked for:

- [ ] **Project name:** `Arid-Edge Sentinel — Multi-Modal Land Resilience`
- [ ] **GitHub repository URL** (public)
- [ ] **5-page paper PDF** (upload, or link to the file in your repo)
- [ ] **Pitch video URL** (YouTube / Vimeo)
- [ ] **Team / contact email:** `ops@launchdetect.com`

Hit submit. **Do this at least 4 hours before the deadline** — last
hour traffic crashes most submission portals.

---

## Step 6 — Post-submission

- Confirm the email receipt
- Pin the repo on your GitHub profile
- Save the submission confirmation as a PDF
- Tag the commit you submitted: `git tag -a submission-v1 -m "..." && git push --tags`

---

## Files in this folder (judge-facing)

| File | Purpose |
|---|---|
| `README.md` | Main entry point — what / why / how |
| `SUBMISSION_CHECKLIST.md` | This file |
| `LICENSE` | MIT |
| `app.py` | Streamlit Command Center |
| `nasa_fusion.py` | NASA Earthdata API engine |
| `resilience_score.py` | Algorithm (Section 3.2) implementation |
| `synthetic.py` | Fallback scene generator |
| `requirements.txt` | Minimal demo deps |
| `requirements-live.txt` | Optional live-API deps |
| `.env.example` | Earthdata credential template |
| `Launch Arid-Edge Sentinel.bat` | Windows one-click launcher |
| `Launch Arid-Edge Sentinel (silent).vbs` | No-terminal launcher |
