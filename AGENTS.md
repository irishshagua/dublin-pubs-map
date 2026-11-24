# Repository guidance

This project tracks pubs visited in Dublin and publishes a map. Most changes add or update pubs, but changes to the converter or website may also be needed.

## Data and GeoJSON (master)

- `visits.json` is the source of truth: each entry has a stable ID, latitude, longitude, name, review and optional `osm_id` link.
- Preserve names and reviews exactly as supplied, including subjective comments and profanity. Do not rewrite them unless asked.
- Validate the visit data and regenerate `dublin-pubs.geojson` after changes; include both source and generated files.
- The converter emits point coordinates in GeoJSON order (longitude, latitude), carries over names and reviews, and appends the feature from `dublinBoundary.geojson`.
- Keep the boundary unchanged unless the task requires changing it.
- OSM candidate extraction uses `dublin-county-boundary.geojson` (the OSM County Dublin relation), not the older visualisation outline. Use a full-region source: the BBBike Dublin extract cuts off northern County Dublin.

## Licence data (master)

- See README for the Revenue XLS refresh. The site displays its licence count separately from OSM pubs and visit counts.
- OSM links belong to visits. High-confidence links approved for automatic matching are estimates recorded in the audit files; keep other suggestions unlinked and preserve OSM attribution. Use pub and bar features for matching, but only pub-tagged venues for Undone.

## Website (gh-pages)

- The static website source is on the separate `gh-pages` branch, not in the `master` working tree. Inspect that branch before planning website changes.
- The website reads `visits.json`, `osm-pubs.json` and the Revenue licence snapshot from the default branch. The generated GeoJSON is a separate visualisation.
- Coordinate branch changes when changing the data format; the website must distinguish recorded visits from estimated OSM links and unlinked candidates.

## Verification

- For data changes, run the converter and check that generated features reflect edited rows. Licence refresh regression tests are in `test_refresh_licences.py`. For website changes, verify the affected page and map in a browser when possible.
