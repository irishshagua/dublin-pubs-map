# Repository guidance

This project tracks pubs visited in Dublin and publishes a map. Most changes add or update pubs, but changes to the converter or website may also be needed.

## Data and GeoJSON (master)

- `postgres-pubs-dump.txt` is the source of truth. It is a headerless, tab-separated file with four fields: latitude, longitude, pub name and review.
- Preserve reviews as supplied, including subjective comments and profanity. Do not rewrite them unless asked.
- Before regenerating, run `python3 validate_pubs.py` from the repository root. Fix validation errors and review shared-coordinate warnings; shared coordinates are not necessarily mistakes.
- After changing the pub data, run `python3 convertToGeoJson.py` from the repository root and include the regenerated `dublin-pubs.geojson` in the change. The script uses only the Python standard library.
- The converter emits point coordinates in GeoJSON order (longitude, latitude), carries over names and reviews, and appends the feature from `dublinBoundary.geojson`.
- Keep the boundary unchanged unless the task requires changing it.

## Licence data (master)

- See README for the Revenue XLS refresh and manual review process. `remaining-pubs.json` is generated; make decisions in `licence-overrides.json`, keyed by licence reference, then rerun `refresh_licences.py`.
- Keep ambiguous matches as `review`, and decide hotel exclusions manually. Do not infer coordinates or publish a home address. Preserve the per-location OSM source and snapshot when refreshing the cache.
- After adding a visit, run the licence refresh too and inspect `licence-review.csv` for the corresponding licence. Keep the visit list and its reviews intact.

## Website (gh-pages)

- The static website source is on the separate `gh-pages` branch, not in the `master` working tree. Inspect that branch before planning website changes.
- The Leaflet map reads `postgres-pubs-dump.txt` and `remaining-pubs.json` from the default branch. The generated GeoJSON is a separate visualisation.
- Consider both branches when changing the data format or website integration; retain compatibility across them.

## Verification

- There is no test suite on `master`. For data changes, run the converter and check that the generated features reflect the edited rows. For website changes, verify the affected page and map in a browser when possible.
