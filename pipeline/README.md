# pipeline (back end)

Owner: Mohammed (lead and back end). AI-assisted code; every file carries a header saying so.

Steps: crop → resample to a common pixel size → slope / roughness (TRI) / relief → percentiles → similarity → mission scores → `docs/data/results.json`.

Inputs: `data/sites.csv`, `data/targets.csv`, `config/missions.json`, DEM crops in `data/processed/` (or full tiles in `data/raw/`).
Output schema (one record per site × target × mission):
`site_id, target_id, mission, match, similarity{slope,roughness,relief}, confidence, access_km, data_status`.

Code lands on branch `mohammed/lead-backend`.
