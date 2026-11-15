# Cave Finder – Methodology

NASA Space Apps Challenge 2026 · Team AOU_RUH (Alyahia Team)

This document describes how the terrain data for the Cave Finder project was collected, processed and ranked. Everything below is implemented in the notebook `Cave_finder_data_preparation.ipynb`.

## 1. Goal

Find terrain that is likely to host cave or lava-tube openings. The approach is built and checked on Earth (Saudi Arabia) and then applied with the same logic to the Moon and Mars.

## 2. Earth (Saudi Arabia)

### 2.1 Study sites

Nine sites: seven core sites and two additional sites.

| ID | Site | Category |
|----|------|----------|
| S01 | Umm Jirsan | Core |
| S02 | Harrat Khaybar | Core |
| S03 | Al Wahbah | Core |
| S04 | Harrat Rahat | Core |
| S05 | Harrat Uwayrid | Core |
| S06 | Wabar Craters | Core |
| S07 | Ghar Al Hibashi | Core |
| S08 | Harrat Lunayyir | Additional |
| S09 | Harrat Kishb | Additional |

The coordinates of the two additional sites come from the Smithsonian Global Volcanism Program entries for each volcanic field. Harrat Kishb (22.8°N, 41.38°E) was confirmed on the GVP page itself. For Harrat Lunayyir (25.17°N, 37.75°E) the coordinates were confirmed against COMET and a USGS volcano list.

Note that Al Wahbah is a feature inside the Harrat Kishb field, so S03 and S09 overlap spatially.

### 2.2 Elevation data

- Source: ASTER Global DEM v003 (`ASTGTMV003`), downloaded from NASA Earthdata with the `earthaccess` library.
- Each tile covers 1° × 1° and is named after its south-west corner (for example `N25E039`).
- Two layers per tile: `_dem` (elevation) and `_num` (the number of ASTER scenes behind each pixel, used as a data-quality indicator).
- The tile of every site is computed from its coordinates, so the nine sites need seven tiles:

| Tile | Sites |
|------|-------|
| N25E039 | Umm Jirsan, Harrat Khaybar |
| N22E041 | Al Wahbah, Harrat Kishb |
| N23E039 | Harrat Rahat |
| N27E037 | Harrat Uwayrid |
| N21E050 | Wabar Craters |
| N21E042 | Ghar Al Hibashi |
| N25E037 | Harrat Lunayyir |

### 2.3 Terrain features

1. Each DEM tile is reprojected from geographic coordinates to UTM at 30 m, so that distances are in metres.
2. **Slope** (degrees) is computed from the elevation gradient using the 30 m pixel size. An early version computed slope with degree-based spacing and returned values near 90° everywhere. That was corrected by working in UTM metres.
3. **Roughness** is computed as a local measure of elevation variability.
4. Per-tile statistics and the NUM quality statistics are merged into one table per tile.
5. For every study site, the same features are summarised in a window of about 1 km around the site. This separates sites that share a tile.

### 2.4 Pixel-level dataset and quality checks

- Pixels from all tiles are sampled on a regular grid into one dataset (elevation, slope, roughness, NUM, coordinates).
- Checks: missing values, duplicates, outliers and coordinate validity.
- A final cleaned dataset and a per-tile statistics table are saved.

## 3. Moon and Mars

### 3.1 Elevation data

| Body | Source | Resolution |
|------|--------|------------|
| Moon | LRO LOLA gridded elevation (`LDEM_16`) | 16 pixels per degree |
| Mars | MGS MOLA gridded elevation (`MEGT90N000EB`) | 16 pixels per degree |

Raw values are converted to metres using the scaling factors from each file's label. Missing values are checked, and the label metadata (map centre and projection offsets) is kept for coordinate conversion.

### 3.2 Features

- **Slope** is computed from the elevation gradient. The pixel size in metres is derived from the angular pixel size and the radius of the body, so slope is in degrees and comparable between the Moon and Mars.
- **Roughness** is computed as local elevation variability.
- Features are normalised so they can be combined into one score.

### 3.3 Cave candidate score

1. **Depression index:** elevation minus the smoothed local mean elevation. Caves and skylights show up as local depressions, so a stronger depression gives a higher score.
2. **Suitability score:** a weighted sum of the depression index (50%), low slope (25%) and low roughness (25%).
3. The highest-scoring pixels are kept as candidates and grouped with DBSCAN, so neighbouring pixels become one candidate site.
4. Pixel positions are converted to latitude and longitude using the label metadata, then longitudes are validated to the range −180° to 180°.
5. Candidates are ranked per body and compared in a final chart.

## 4. Output files

Output files are saved in Google Drive under `Cave_Finder/data/processed/`, with names that start with `Earth_` or `Moon_Mars_`. The last notebook cell creates `00_File_Guide.csv`, which lists every file with a short description.

## 5. Current status and limitations

- The Earth pipeline needs one full re-run after the fixes (slope, tile list, file names) so that all outputs reflect all seven tiles.
- The Moon and Mars candidate selection, clustering and ranking steps are written but have not been run yet.
- Slope and roughness for Earth, Moon and Mars come from different elevation products and resolutions (30 m for Earth; at 16 pixels per degree a pixel is roughly 1.9 km on the Moon and 3.7 km on Mars at the equator). Scores are therefore comparable within one body, not between bodies.
- Roughness is defined in two slightly different ways in the notebook (standard deviation in the tile table, range in the pixel dataset). One definition should be chosen before the data is used downstream.
- The highest-scoring pixels tend to be neighbours, so the number of distinct candidates after clustering can be small.
- No weather or surface-temperature data is included yet. For Mars, MRO Mars Climate Sounder data could provide surface temperature, but it was not integrated.

## 6. Data sources

- ASTER GDEM v003, NASA / METI, via NASA Earthdata.
- LRO LOLA lunar elevation model, NASA PDS.
- MGS MOLA Mars elevation model, NASA PDS.
- Smithsonian Institution Global Volcanism Program, volcano pages 231040 (Harrat Lunayyir) and 231071 (Harrat Kishb), for the additional site coordinates.
