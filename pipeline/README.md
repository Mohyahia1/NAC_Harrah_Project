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
5. **No score is produced when less than 90 % of a box has elevation data**. The score is left empty with a note, never filled in.

`data_coverage` / `confidence` currently reflect the share of the box with elevation data. When ASTER `num` (pass count) files are added, confidence will switch to the pass-count rule in the main README.

## Scale note

Global Moon and Mars DEMs make this a **regional-scale** comparison (terrain over ~100 km). Sharper target crops (LOLA 20 m south pole, SLDEM2015 ~60 m, CTX DTMs) would allow site-scale comparison; add them in `config/sources.json` when available.
