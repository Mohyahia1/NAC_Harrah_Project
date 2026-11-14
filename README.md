# Harrah (حرَّة)

**Ranking Saudi Arabian terrain as Earth analogs for Moon and Mars missions, using NASA elevation data.**

NASA Space Apps Challenge 2026 · Riyadh local event · Team **AOU_RUH – Alyahia Team**
Challenge: *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*

> Status: in active development during the hackathon (14–15 Nov 2026). Scores in the tool are labelled **sample** or **preliminary** until the final pipeline run.

---

## 1. What we are building

Before a rover, a lander or an astronaut suit goes to the Moon or Mars, it is tested on Earth in places that look and behave like the target. NASA's own challenge text says these analog sites are not fully characterised. Saudi Arabia has large basalt lava fields, lava tubes, a volcanic crater and real impact craters, but no tool ranks them against specific Moon and Mars targets.

**Harrah is a public, map-first web tool.** The user:

1. picks a **mission**: rover driving, crater operations, landing and base, or lava-tube shelter;
2. picks a **target** on the Moon or Mars (for example the Marius Hills pit or Jezero crater);
3. sees the **Saudi sites ranked by terrain match (0–100)** on a satellite map;
4. opens a **site card**: score per trait, data confidence, what is confirmed from orbit, what still needs a field check, access, and climate.

**What the tool does not claim:** it does not find caves, confirm geology or approve a site for testing. It ranks terrain similarity from NASA elevation data and shows what must still be checked on the ground.

## 2. How it works: data to screen

```
 NASA data                Pipeline (Python)                      Web tool (GitHub Pages)
 ─────────                ─────────────────                      ───────────────────────
 ASTER GDEM v3 (Earth) ─┐  1. crop a 10 km box per site/target
 LOLA / SLDEM (Moon)   ─┼─ 2. resample both sides to one pixel size ─┐
 MOLA (Mars)           ─┘  3. traits: slope, roughness, relief       │
 ASTER num files ───────── 4. confidence (satellite pass count)      ├─► docs/data/results.json ─► map, ranked list,
 NASA POWER ────────────── 5. climate per site                       │                              site card
 data/sites.csv, targets ─ 6. score = Σ weight × similarity  ────────┘
```

### The scoring model

For every site, target and mission:

1. **Traits** (measured inside the box, on the same pixel size for both worlds):
   - **Slope** in degrees
   - **Roughness**: Terrain Ruggedness Index (TRI) in metres
   - **Relief**: elevation range (max − min) within a 1 km window, in metres
2. **Distributions, not single numbers:** for each trait we take the 10th, 50th and 90th percentiles.
3. **Distance per trait:** `d = mean(|site_p − target_p|) / IQR_target` over the three percentiles.
4. **Similarity per trait:** `s = exp(−d)`, between 0 and 1.
5. **Match score:** `Match = 100 × Σ wᵢ · sᵢ`, with mission weights from [`config/missions.json`](config/missions.json):

   | Mission | Slope | Roughness | Relief |
   |---|---|---|---|
   | Rover driving | 0.4 | 0.4 | 0.2 |
   | Crater operations | 0.3 | 0.2 | 0.5 |
   | Landing and base | 0.5 | 0.3 | 0.2 |
   | Lava-tube shelter | 0.2 | 0.3 | 0.5 |

6. **Confidence** (separate from the score): share of site pixels with 3 or more ASTER passes. High ≥ 90%, Medium 70–90%, Low < 70%.
7. **Access:** straight-line distance to the nearest city.
8. **Checks:** Wabar and Al Wahbah should rank high for crater operations, Khaybar for rover driving; a ±0.1 change in any weight should not reorder the top sites.

Elevation itself is **not** a trait: absolute height on Earth, the Moon and Mars is measured against different reference surfaces and says nothing about how the ground behaves.

## 3. Repository layout

| Path | What it holds | Owner |
|---|---|---|
| `data/sites.csv` | The Saudi sites: names (EN/AR), coordinates, facts, sources | Rayan / Mohammed |
| `data/sites_map.csv` | Short version for mapping | – |
| `data/targets.csv` | Moon and Mars targets with coordinates and dataset | Rayan, Ryouf |
| `data/climate_nasa_power.csv` | NASA POWER climate per site | – |
| `data/processed/` | Small crops only (GeoTIFF, a few MB each) | Ryouf |
| `data/raw/` | **Not in git.** Large files stay on Google Drive; see `data/raw/README.md` | Ryouf |
| `config/missions.json` | Mission weights (team decision) | Team |
| `pipeline/` | Python scoring pipeline | Mohammed (back end) |
| `docs/` | The web tool, published by GitHub Pages | Asma |
| `docs/data/results.json` | Pipeline output that the tool reads. **Generated; do not edit by hand.** | Pipeline |
| `design/` | Screens, flows, components, mobile layouts | Jamal |
| `research/` | Target choices, site facts, references, NASA analog precedents | Rayan |
| `demo/` | 7-slide English demo (or 30-second video link) | Rayan |

## 4. Team and branches

Everyone works on **their own branch** and opens a **pull request into `main`**. Mohammed reviews and merges. GitHub Pages publishes `main`, so only merged work goes live.

| Member | Role | Branch | Works in |
|---|---|---|---|
| Mohammed Majdi Mohammed | Lead and back end: scope, scoring pipeline, README, project page, submission | `mohammed/lead-backend` | `pipeline/`, `docs/data/`, `README.md`, root files |
| Ryouf Alhuwaidi | Data: ASTER processing, Moon/Mars crops, method notes | `ryouf/data` | `data/` |
| Rayan Ayash Hmoud | Research and demo: targets, site facts, references, slides | `rayan/research-demo` | `research/`, `demo/`, `data/targets.csv` |
| Jamal Ahmed Jamous | UI/UX: layout, flows, site card, mobile | `jamal/ux-design` | `design/` |
| Asma | Front end: builds the web tool | `asma/frontend` | `docs/` (except `docs/data/`) |

### How to work (first time)

```bash
git clone https://github.com/Mohyahia1/NAC_Harrah_Project.git
cd NAC_Harrah_Project
git checkout <your-branch>        # e.g. git checkout asma/frontend
# ...work...
git add <files>
git commit -m "Short description of what you did"
git push
```

Then on GitHub: **Pull requests → New pull request → base: `main`, compare: your branch → Create**.

Rules:
- Stay inside your folders (table above) so merges don't collide.
- Pull `main` into your branch before opening a PR: `git pull origin main`.
- No files over 50 MB. No raw rasters, `.npy` or `.zip` in git.
- Everything in **English**: code, comments, UI text, slides.

## 5. Running the pipeline

```bash
pip install -r pipeline/requirements.txt
python pipeline/run.py            # writes docs/data/results.json
```

Details and inputs: [`pipeline/README.md`](pipeline/README.md).

## 6. Running the web tool locally

```bash
cd docs
python -m http.server 8000        # open http://localhost:8000
```

Public link (after GitHub Pages is enabled): `https://mohyahia1.github.io/NAC_Harrah_Project/`

## 7. Timeline

| When (Riyadh time) | Milestone |
|---|---|
| Sat 14 Nov, 22:00 | First working version merged and submitted |
| Sun 15 Nov, 15:00 | Sharper Moon/Mars crops in; scores re-run |
| Sun 15 Nov, 21:00 | Final merge, all links tested in a private window, resubmit |
| Sun 15 Nov, 23:59 | Hard deadline |

## 8. NASA data used

| Dataset | Producer | Used for |
|---|---|---|
| ASTER Global DEM v3 (30 m) | NASA / METI (Japan) | Saudi terrain; pass counts for confidence |
| LRO LOLA DEMs (global 16 ppd; south pole 20 m) | NASA | Moon terrain |
| SLDEM2015 (LOLA + Kaguya TC, ~60 m) | NASA GSFC / JAXA | Moon targets outside the poles |
| MGS MOLA MEGDR (16 and 128 ppd) | NASA | Mars terrain |
| NASA POWER climatology | NASA LaRC | Site climate |

## 9. References

Full list with links: [`research/references.md`](research/references.md). Key sources include:
- Stewart et al. (2024), *PLOS One*: Umm Jirsan lava tube survey and collapse coordinates.
- USGS: geologic map of northern Harrat Rahat.
- Smithsonian Global Volcanism Program: Harrat Khaybar, Harrat Rahat, Harrat Uwayrid.
- Grottocenter: Ghar Al Hibashi.

## 10. Use of AI

We used AI tools during this project and acknowledge it here, as the Space Apps rules require:
- An AI coding assistant helped draft this README, write the scoring pipeline code in `pipeline/` (AI-assisted files carry a header comment saying so), and build parts of the web tool.
- The team chose the challenge, the Saudi sites, the Moon and Mars targets, the traits and the mission weights, and reviewed the results.
- No AI-generated images are used without a visible watermark. No NASA logos or branding are used.

## License

Code: MIT. Data belongs to its original producers; see the credits in section 8 and `research/references.md`.
