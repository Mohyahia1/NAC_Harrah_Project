# pipeline (back end)

Owner: Mohammed (lead and back end). AI-assisted code; every file carries a header saying so.

```bash
pip install -r pipeline/requirements.txt
python pipeline/run.py            # real scores if the DEMs below are present, otherwise SAMPLE values
python pipeline/run.py --sample   # force sample values (for front-end work)
```

Output: `docs/data/results.json`. `meta.status` is `sample`, `preliminary` or `final`; the web tool must show a visible label when it is not `final`.

## Inputs

| What | Where | In git? |
|---|---|---|
| Sites (11 rows: 7 core, 2 additional, 2 cave-test points) | `data/sites.csv` | yes |
| Moon / Mars targets | `data/targets.csv` | yes |
| Mission weights | `config/missions.json` | yes |
| DEM locations, box size, settings | `config/sources.json` | yes |
| Climate (NASA POWER) | `data/climate_nasa_power.csv` | yes |
| ASTER GDEM v3 elevation tiles (GeoTIFF, any CRS) | `data/raw/aster/` | no (Drive) |
| Moon elevation, LOLA 16 ppd, metres (`.npy`, 2880 × 5760) | `data/raw/moon/elevation.npy` | no (Drive) |
| Mars elevation, MOLA MEGDR 16 ppd, metres (`.npy`, 2880 × 5760) | `data/raw/mars/elevation.npy` | no (Drive) |

## Method

The same code runs on all three worlds:
1. A 100 km × 100 km local grid in metres around each site and target (azimuthal equidistant projection, so the lunar south pole is handled correctly).
2. Raw elevation is sampled onto that grid at the planet's pixel size: about 1.9 km for Moon comparisons and 3.7 km for Mars. Saudi terrain is resampled to the same size, so both sides are measured at one scale.
3. Traits: slope (degrees), roughness (Terrain Ruggedness Index, Riley et al. 1999, metres) and relief (max − min in a 5 × 5 pixel window, metres).
4. Percentiles p10 / p50 / p90 → distance normalised by the target's IQR → similarity `exp(−d)` → `Match = 100 × Σ weight × similarity`.
5. **No score is produced when less than 35 % of a box has elevation data** (`min_coverage` in `config/sources.json`). The score is left empty with a note, never filled in. Between 35 % and 90 % the score is shown with a lower confidence label; it improves automatically as the missing neighbouring ASTER tiles are added.

`data_coverage` / `confidence` currently reflect the share of the box with elevation data (High ≥ 90 %, Medium 70–90 %, Low < 70 %). When ASTER `num` (pass count) files are added, confidence will switch to the pass-count rule in the main README.

## Scale

Each target is compared at the sharpest resolution we have for it, inside a 20 km box (`local_box_km`). The Saudi side is resampled to exactly the same pixel size and box.

| Target | Dataset | Pixel |
|---|---|---|
| Shackleton (lunar south pole) | LRO LOLA polar DEM | 120 m |
| Marius Hills pit, Mare Tranquillitatis pit | SLDEM2015 (LOLA + SELENE TC), every 3rd pixel | ~178 m |
| Jezero, Gale, Arsia Mons pit | MGS MOLA MEGDR 128 ppd | ~463 m |

The crops (`data/processed/target_crops.json`, ~230 KB) were cut from the NASA PDS Geosciences Node files with HTTP range requests, so only the area around each target was downloaded; source URLs are inside the file. A target without a crop falls back to the global 16 ppd DEM at regional scale (100 km box).

Current limits:
- A 20 km box describes the terrain around a site. Features much smaller than the box, such as the 2 km Al Wahbah crater or the ~116 m Wabar craters, contribute but do not dominate the score.
- No Saudi site resembles the steep interior of Shackleton crater (median slope ~29°); the best partial match is Harrat Rahat.
- Slope, roughness and relief move together, so the ranking for a target changes little between missions; the mission weights mostly change the score level.

## Relief images (Compare terrain)

For every target and every site × target pair, the pipeline saves a shaded-relief PNG in `docs/data/relief/` (`t_<target>.png`, `<site>__<target>.png`), rendered from the **same elevation grids used for scoring**: same 20 km box, same pixel size, vertical exaggeration ×2 and north-west light on both sides. Paths are in `results.json` (`targets[].relief`, `sites[].relief[target]`). The web tool's **Compare terrain** panel shows each pair side by side with the trait ranges (p10–p90, median) and per-trait similarity.
