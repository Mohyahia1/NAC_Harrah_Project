"""
Harrah scoring pipeline: ranks Saudi sites as terrain analogs for Moon and Mars targets.

AI-assisted code: written with the help of an AI coding assistant and reviewed by the team.
See README section "Use of AI".

Usage
-----
    python pipeline/run.py            # real run if DEMs are present, otherwise a SAMPLE file
    python pipeline/run.py --sample   # force a sample file (format only, not real scores)

Output: docs/data/results.json (read by the web tool).

Method (same code for Earth, Moon and Mars)
------------------------------------------
1. For every site and target, build a local square grid in metres (azimuthal equidistant
   projection centred on the point), BOX_KM wide, at a common pixel size for that world pair.
2. Sample raw elevation (metres) onto that grid by bilinear interpolation.
3. Traits per pixel:
     slope      degrees, from central differences
     roughness  Terrain Ruggedness Index (Riley et al. 1999): sqrt(sum of squared
                differences to the 8 neighbours), metres
     relief     max - min elevation in a RELIEF_WIN x RELIEF_WIN pixel window, metres
4. For each trait keep the 10th, 50th and 90th percentiles of the box.
5. distance  d = mean(|site_p - target_p|) / IQR_target   (IQR = p75 - p25 of the target)
   similarity s = exp(-d)
6. Match = 100 * sum(weight_mission[trait] * s[trait])   weights from config/missions.json
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import zlib
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "docs" / "data" / "results.json"
SOURCES = json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))

BOX_KM = SOURCES["box_km"]
RELIEF_WIN = SOURCES["relief_window_px"]
MIN_COVERAGE = SOURCES.get("min_coverage", 0.9)
LOCAL_BOX_KM = SOURCES.get("local_box_km", 20)  # box for targets that have a sharper crop  # share of the box that must have elevation data
TRAITS = ("slope", "roughness", "relief")
RADIUS_M = {"Moon": 1_737_400.0, "Mars": 3_396_190.0}

# Nearest-city points for straight-line access distance (approximate town centres).
CITIES = {
    "Khaybar": (25.70, 39.29), "Al Muwayh": (22.43, 41.76), "Madinah": (24.47, 39.61),
    "Haradh": (24.15, 49.07), "AlUla": (26.61, 37.92), "Turabah": (21.21, 41.63),
    "Umluj": (25.02, 37.27),
}


# ----------------------------------------------------------------------------- inputs
def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


# ----------------------------------------------------------------------------- grids
def local_grid(pixel_m: float, box_km: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    """x, y offsets in metres of an n x n grid centred on (0, 0)."""
    n = int(round((box_km or BOX_KM) * 1000 / pixel_m)) + 1
    half = (n - 1) / 2 * pixel_m
    ax = np.linspace(-half, half, n)
    x, y = np.meshgrid(ax, -ax)  # row 0 = north
    return x, y


def aeqd_inverse_sphere(x, y, lat0, lon0, radius):
    """Azimuthal equidistant inverse on a sphere: metres -> lat/lon degrees."""
    phi0, lam0 = math.radians(lat0), math.radians(lon0)
    rho = np.hypot(x, y)
    c = rho / radius
    with np.errstate(invalid="ignore", divide="ignore"):
        lat = np.arcsin(np.cos(c) * math.sin(phi0) + np.where(rho > 0, y * np.sin(c) * math.cos(phi0) / rho, 0))
        lon = lam0 + np.arctan2(x * np.sin(c), rho * math.cos(phi0) * np.cos(c) - y * math.sin(phi0) * np.sin(c))
    lat = np.where(rho > 0, lat, phi0)
    return np.degrees(lat), (np.degrees(lon) + 360) % 360


def sample_global_grid(dem: np.ndarray, ppd: float, lat, lon) -> np.ndarray:
    """Bilinear sample of a global equirectangular grid (row 0 at 90N, col 0 at 0E, cell centres)."""
    rows = (90.0 - lat) * ppd - 0.5
    cols = lon * ppd - 0.5
    # pad one column on each side so longitude wraps cleanly
    padded = np.concatenate([dem[:, -1:], dem, dem[:, :1]], axis=1)
    return ndimage.map_coordinates(padded, [rows, cols + 1], order=1, mode="nearest")


def load_target_crops() -> dict:
    """Sharper elevation crops around targets (data/processed/target_crops.json), if present."""
    path = ROOT / SOURCES.get("target_crops", "data/processed/target_crops.json")
    if not path.exists():
        return {}
    import base64
    crops = json.loads(path.read_text(encoding="utf-8"))["crops"]
    for c in crops.values():
        c["z"] = np.frombuffer(base64.b64decode(c.pop("int16_b64")), dtype="<i2").reshape(c["nr"], c["nc"]).astype("float64")
        if c["grid"] == "latlon":
            c["pixel_m"] = math.radians(c["step_deg"]) * RADIUS_M[c["world"]]
        else:
            c["pixel_m"] = float(c["scale_m"])
    return crops


def sample_crop(c: dict, lat, lon) -> np.ndarray:
    """Bilinear sample of a target crop at lat/lon (degrees). NaN outside the crop."""
    if c["grid"] == "latlon":
        rows = (c["lat_first"] - lat) / c["step_deg"]
        cols = ((lon - c["lon_first"] + 180) % 360 - 180) / c["step_deg"]
    else:  # south polar stereographic (LOLA polar products)
        rho = 2 * RADIUS_M["Moon"] * np.tan(np.pi / 4 + np.radians(lat) / 2)
        x, y = rho * np.sin(np.radians(lon)), rho * np.cos(np.radians(lon))
        rows = c["projection_offset"] - y / c["scale_m"] - c["line_first"]
        cols = c["projection_offset"] + x / c["scale_m"] - c["sample_first"]
    return ndimage.map_coordinates(c["z"], [rows, cols], order=1, mode="constant", cval=np.nan)


def sample_earth(tiles: list[Path], lat0, lon0, x, y) -> np.ndarray:
    """Sample GeoTIFF tile(s) of any CRS onto the local grid. NaN where no tile covers."""
    import rasterio
    from pyproj import Transformer

    out = np.full(x.shape, np.nan)
    local = f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +datum=WGS84 +units=m"
    for tile in tiles:
        with rasterio.open(tile) as src:
            tr = Transformer.from_crs(local, src.crs, always_xy=True)
            X, Y = tr.transform(x, y)
            inv = ~src.transform
            cols, rows = inv * (X, Y)
            band = src.read(1, masked=True).astype("float64").filled(np.nan)
            band[band == 0] = np.nan  # ASTER GDEM v3 sets sea to 0 m: water is not terrain
            vals = ndimage.map_coordinates(band, [rows - 0.5, cols - 0.5], order=1, mode="constant", cval=np.nan)
            inside = (rows >= 0) & (rows < src.height) & (cols >= 0) & (cols < src.width)
            fill = inside & np.isnan(out)
            out[fill] = vals[fill]
    return out


def tiles_for(tile_dir: Path, lat: float, lon: float, box_km: float | None = None) -> list[Path]:
    """ASTER 1x1 degree tiles (named like N25E039...) that overlap the box around a point."""
    half = (box_km or BOX_KM) / 2
    dla, dlo = half / 111.0, half / (111.0 * math.cos(math.radians(lat)))
    names = {f"N{a:02d}E{b:03d}" for a in range(math.floor(lat - dla), math.floor(lat + dla) + 1)
             for b in range(math.floor(lon - dlo), math.floor(lon + dlo) + 1)}
    found = []
    for n in sorted(names):
        hits = sorted(tile_dir.glob(f"{n}*elev*.tif")) or sorted(tile_dir.glob(f"*{n}*dem*.tif")) \
            or sorted(tile_dir.glob(f"{n}*.tif"))
        found += hits[:1]
    return found


# ----------------------------------------------------------------------------- relief images
RELIEF_DIR = ROOT / "docs" / "data" / "relief"
RELIEF_EXAG = 2.0           # same vertical exaggeration on both sides of every comparison
RELIEF_SUN = (315.0, 45.0)  # azimuth, altitude in degrees (standard north-west light)


def save_relief(z: np.ndarray, pixel_m: float, path: Path, size: int = 320) -> None:
    """Shaded relief of the exact grid that was scored, rendered in the harrah palette."""
    from PIL import Image
    valid = np.isfinite(z)
    zz = np.where(valid, z, np.nanmean(z) if valid.any() else 0.0) * RELIEF_EXAG
    gy, gx = np.gradient(zz, pixel_m)          # row 0 is north
    dzdx, dzdy = gx, -gy                       # east, north
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = np.arctan2(dzdy, -dzdx)
    az = math.radians((360.0 - RELIEF_SUN[0] + 90.0) % 360.0)
    zen = math.radians(90.0 - RELIEF_SUN[1])
    hs = np.cos(zen) * np.cos(slope) + np.sin(zen) * np.sin(slope) * np.cos(az - aspect)
    hs = np.clip(hs, 0, 1)
    dark, light = np.array([46, 41, 36]), np.array([246, 238, 224])   # basalt -> sand
    rgb = (dark + hs[..., None] * (light - dark)).astype(np.uint8)
    alpha = (valid * 255).astype(np.uint8)
    img = Image.fromarray(np.dstack([rgb, alpha]), "RGBA").resize((size, size), Image.BICUBIC)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)


# ----------------------------------------------------------------------------- traits
def traits(z: np.ndarray, pixel_m: float) -> dict:
    """Percentiles of slope, roughness and relief inside the box, plus valid-pixel share."""
    gy, gx = np.gradient(z, pixel_m)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    sq = np.zeros_like(z)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                sq += (np.roll(np.roll(z, dy, 0), dx, 1) - z) ** 2
    rough = np.sqrt(sq)

    # NaN-aware window: missing pixels never count as high or low ground
    zmax = ndimage.maximum_filter(np.where(np.isnan(z), -np.inf, z), RELIEF_WIN)
    zmin = ndimage.minimum_filter(np.where(np.isnan(z), np.inf, z), RELIEF_WIN)
    relief = zmax - zmin
    relief[np.isnan(z) | ~np.isfinite(relief)] = np.nan

    edge = max(1, RELIEF_WIN // 2)
    inner = (slice(edge, -edge), slice(edge, -edge))
    res = {"valid_share": float(np.isfinite(z[inner]).mean())}
    for name, arr in (("slope", slope), ("roughness", rough), ("relief", relief)):
        v = arr[inner][np.isfinite(arr[inner])]
        p = np.percentile(v, [10, 25, 50, 75, 90]) if v.size else [np.nan] * 5
        res[name] = {k: round(float(val), 3) for k, val in zip(("p10", "p25", "p50", "p75", "p90"), p)}
    return res


def similarity(site_t: dict, target_t: dict) -> dict:
    out = {}
    for t in TRAITS:
        s, g = site_t[t], target_t[t]
        iqr = max(g["p75"] - g["p25"], 1e-6, 0.05 * abs(g["p50"]))
        d = np.mean([abs(s[p] - g[p]) for p in ("p10", "p50", "p90")]) / iqr
        out[t] = round(float(math.exp(-d)), 4)
    return out


# ----------------------------------------------------------------------------- main
def load_inputs():
    sites = [s for s in read_csv(DATA / "sites.csv") if s["category"] in ("core", "additional")]
    targets = [t for t in read_csv(DATA / "targets.csv") if t["lat"] and t["lon_east"]]
    missions = {k: v for k, v in json.loads((ROOT / "config" / "missions.json").read_text(encoding="utf-8")).items()
                if not k.startswith("_")}
    climate = {}
    cpath = DATA / "climate_nasa_power.csv"
    if cpath.exists():
        alias = {"harrat_khaybar": "khaybar_field", "harrat_uwayrid": "uwayrid", "ghar_al_hibashi": "hibashi"}
        for r in read_csv(cpath):
            climate[alias.get(r["site_id"], r["site_id"])] = r
    images = {}
    ipath = DATA / "target_images.csv"
    if ipath.exists():
        images = {r["target_id"]: {k: r[k] for k in ("image_title", "image_id", "page_url", "credit")} for r in read_csv(ipath)}
    for t in targets:
        t["_image"] = images.get(t["target_id"])
    return sites, targets, missions, climate


def site_record(s: dict, climate: dict) -> dict:
    lat, lon = float(s["lat"]), float(s["lon"])
    city = s.get("nearest_city", "")
    c = climate.get(s["id"], {})

    def num(key, nd=1):
        try:
            return round(float(c[key]), nd)
        except (KeyError, ValueError):
            return None

    return {
        "id": s["id"], "code": s["site_code"], "name": s["name"], "name_ar": s["name_ar"],
        "lat": lat, "lon": lon, "coord_quality": s["coord_quality"], "category": s["category"],
        "type": s["site_type"], "analog_for": s["analog_for"], "facts": s["key_facts"],
        "access_note": s["access_note"], "source": s["source"], "region": s["region"],
        "nearest_city": city,
        "access_km": round(haversine_km((lat, lon), CITIES[city]), 0) if city in CITIES else None,
        "climate": {
            "hottest_month_max_c": num("hottest_month_avg_daily_max_C"),
            "coldest_month_min_c": num("coldest_month_avg_daily_min_C"),
            "rain_mm_day": num("rain_mm_per_day_avg", 2),
            "sunlight_kwh_m2_day": num("sunlight_kWh_m2_day_avg"),
        },
    }


def confidence_label(share: float | None) -> str:
    if share is None:
        return "Unknown"
    return "High" if share >= 0.9 else "Medium" if share >= 0.7 else "Low"


def run(force_sample: bool) -> dict:
    sites, targets, missions, climate = load_inputs()
    moon_path, mars_path = ROOT / SOURCES["moon_dem"], ROOT / SOURCES["mars_dem"]
    tile_dir = ROOT / SOURCES["earth_tiles_dir"]
    have_planets = moon_path.exists() and mars_path.exists()
    have_earth = any(tile_dir.glob("*.tif"))
    real = have_planets and have_earth and not force_sample

    site_traits: dict[str, dict] = {}   # key: site_id|target_id
    target_traits: dict[str, dict] = {}
    target_scale: dict[str, dict] = {}
    if real:
        planet = {"Moon": (np.load(moon_path, mmap_mode="r"), SOURCES["moon_ppd"]),
                  "Mars": (np.load(mars_path, mmap_mode="r"), SOURCES["mars_ppd"])}
        crops = load_target_crops()
        for t in targets:
            world, tid = t["world"], t["target_id"]
            tlat, tlon = float(t["lat"]), float(t["lon_east"])
            if tid in crops:  # site scale: sharper crop around the target
                c = crops[tid]
                pixel_m, box_km = c["pixel_m"], LOCAL_BOX_KM
                x, y = local_grid(pixel_m, box_km)
                lat, lon = aeqd_inverse_sphere(x, y, tlat, tlon, RADIUS_M[world])
                zt = sample_crop(c, lat, lon)
                target_scale[tid] = {"scale": "site", "pixel_m": round(pixel_m), "box_km": box_km,
                                     "dataset": c["dataset"], "url": c["url"]}
            else:  # regional scale: global DEM
                dem, ppd = planet[world]
                pixel_m, box_km = 2 * math.pi * RADIUS_M[world] / (360 * ppd), BOX_KM
                x, y = local_grid(pixel_m, box_km)
                lat, lon = aeqd_inverse_sphere(x, y, tlat, tlon, RADIUS_M[world])
                zt = sample_global_grid(np.asarray(dem), ppd, lat, lon)
                target_scale[tid] = {"scale": "regional", "pixel_m": round(pixel_m), "box_km": box_km,
                                     "dataset": f"{'LRO LOLA' if world == 'Moon' else 'MGS MOLA'} global DEM, {ppd} ppd"}
            target_traits[tid] = traits(zt, pixel_m)
            save_relief(zt, pixel_m, RELIEF_DIR / f"t_{tid}.png")
            for s in sites:  # Saudi terrain measured at exactly the same pixel size and box
                slat, slon = float(s["lat"]), float(s["lon"])
                z = sample_earth(tiles_for(tile_dir, slat, slon, box_km), slat, slon, x, y)
                site_traits[f"{s['id']}|{tid}"] = traits(z, pixel_m)
                save_relief(z, pixel_m, RELIEF_DIR / f"{s['id']}__{tid}.png")

    scores = []
    for t in targets:
        for s in sites:
            st = site_traits.get(f"{s['id']}|{t['target_id']}")
            tt = target_traits.get(t["target_id"])
            if real:
                ok = bool(st and tt and st["valid_share"] >= MIN_COVERAGE and tt["valid_share"] >= MIN_COVERAGE)
                sim = similarity(st, tt) if ok else None  # never invent a score for thin data
            else:  # SAMPLE: deterministic placeholder values so the front end can be built
                rng = np.random.default_rng(zlib.crc32(f"{s['id']}|{t['target_id']}".encode()))
                sim = {k: round(float(rng.uniform(0.2, 0.95)), 4) for k in TRAITS}
            for m_id, w in missions.items():
                match = round(100 * sum(w[k] * sim[k] for k in TRAITS), 1) if sim else None
                cov = st["valid_share"] if (real and st) else None
                scores.append({"site_id": s["id"], "target_id": t["target_id"], "mission": m_id,
                               "match": match, "similarity": sim,
                               "coverage": round(cov, 3) if cov is not None else None,
                               "confidence": confidence_label(cov) if real else "Sample",
                               "note": None if sim else "insufficient elevation coverage around this site"})

    # rank within each target x mission
    from itertools import groupby
    key = lambda r: (r["target_id"], r["mission"])
    for r in scores:
        r.setdefault("rank", None)
    for _, grp in groupby(sorted(scores, key=key), key=key):
        ranked = sorted((r for r in grp if r["match"] is not None), key=lambda r: -r["match"])
        for i, r in enumerate(ranked, 1):
            r["rank"] = i

    site_out = []
    for s in sites:
        rec = site_record(s, climate)
        shares = [v["valid_share"] for k, v in site_traits.items() if k.startswith(s["id"] + "|")]
        rec["data_coverage"] = round(min(shares), 3) if shares else None
        rec["confidence"] = confidence_label(rec["data_coverage"]) if real else "Sample"
        rec["traits"] = {t["target_id"]: site_traits.get(f"{s['id']}|{t['target_id']}") for t in targets} if real else None
        rec["relief"] = {t["target_id"]: f"data/relief/{s['id']}__{t['target_id']}.png" for t in targets} if real else None
        site_out.append(rec)

    return {
        "meta": {
            "project": "Harrah",
            "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "preliminary" if real else "sample",
            "status_note": ("Real scores from NASA elevation data. Each target is compared at its own scale "
                            "(see targets[].scale); Saudi terrain is resampled to the same pixel size and box."
                            if real else "SAMPLE values for building the interface. Not real scores."),
            "relief_window_px": RELIEF_WIN,
            "min_coverage": MIN_COVERAGE,
            "relief": {"vertical_exaggeration": RELIEF_EXAG, "sun_azimuth_deg": RELIEF_SUN[0],
                       "sun_altitude_deg": RELIEF_SUN[1],
                       "note": "Rendered from the same elevation grids used for scoring, identical settings on both sides."},
            "missions": missions,
            "traits": {"slope": "degrees", "roughness": "TRI (Riley), metres", "relief": "max-min in window, metres"},
            "datasets": SOURCES["datasets"],
        },
        "sites": site_out,
        "targets": [{"id": t["target_id"], "world": t["world"], "name": t["name"], "lat": float(t["lat"]),
                     "lon_east": float(t["lon_east"]), "missions": t["missions"].split(";"),
                     "dataset": t["dem_dataset"], "status": t["status"],
                     "scale": target_scale.get(t["target_id"]),
                     "image": t.get("_image"),
                     "relief": f"data/relief/t_{t['target_id']}.png" if real else None,
                     "traits": target_traits.get(t["target_id"])} for t in targets],
        "scores": scores,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="write sample values (format only)")
    result = run(ap.parse_args().sample)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  status={result['meta']['status']}  "
          f"sites={len(result['sites'])}  targets={len(result['targets'])}  scores={len(result['scores'])}")
