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

- See README for the annual Revenue XLS refresh. The site displays the count of licence rows in `remaining-pubs.json`, not the experimental match statuses.
- The remaining-pub matching and route-planner work is paused; its data and investigation are retained for future work. Do not present uncertain matches as verified visits or require a licence refresh when adding a visit.

## Website (gh-pages)

- The static website source is on the separate `gh-pages` branch, not in the `master` working tree. Inspect that branch before planning website changes.
- The Leaflet map reads `postgres-pubs-dump.txt` and `remaining-pubs.json` from the default branch. The generated GeoJSON is a separate visualisation.
- Consider both branches when changing the data format or website integration; retain compatibility across them.

## Verification

- For data changes, run the converter and check that generated features reflect edited rows. Licence refresh regression tests are in `test_refresh_licences.py`. For website changes, verify the affected page and map in a browser when possible.
