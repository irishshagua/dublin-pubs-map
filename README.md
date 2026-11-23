# Dublin Pubs

Two brothers on a mission to visit the pubs of Dublin.

- [Explore the map](https://irishshagua.github.io/dublin-pubs-map)
- [View the pub list](postgres-pubs-dump.txt)
- [View the GeoJSON map](dublin-pubs.geojson)

## Adding or updating pubs

Edit `postgres-pubs-dump.txt`. Each line contains latitude, longitude, name and review, separated by tabs. Then run from the repository root:

```sh
python3 validate_pubs.py
python3 convertToGeoJson.py
```

Review any shared-coordinate warnings and commit both the pub list and regenerated GeoJSON. Python 3 is the only requirement.

The website reads the pub list through the GitHub API; its source is on the `gh-pages` branch. The GeoJSON is a separate visualisation and includes the Dublin boundary.
