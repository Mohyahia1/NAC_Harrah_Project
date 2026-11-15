# data/raw (not in git)

Large source files stay on the team's Google Drive. Put them here to run the pipeline locally:

```
data/raw/aster/   ASTER GDEM v3 elevation GeoTIFFs, one per 1x1 degree tile, name starting with the tile (e.g. N25E039_elevation.tif or ASTGTMV003_N25E039_dem.tif)
data/raw/moon/elevation.npy   raw LOLA elevation, metres (not normalized)
data/raw/mars/elevation.npy   raw MOLA elevation, metres (not normalized)
```

## ASTER tiles needed (100 km box around every site)

Already downloaded (7): N21E042, N21E050, N22E041, N23E039, N25E037, N25E039, N27E037

Still needed (17): N20E041, N20E042, N21E041, N21E049, N22E039, N22E040, N23E040, N23E041, N24E037, N24E038, N25E038, N25E040, N26E036, N26E037, N26E039, N26E040, N27E036

Source: NASA Earthdata Search, product "ASTER Global Digital Elevation Model V003" (ASTGTM v003). Only the `_dem.tif` file of each tile is needed; the `_num.tif` file is optional (used for confidence).
