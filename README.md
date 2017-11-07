# Dublin Pubs
The source of truth for a project to try and drink in all the registered pubs in Dublin.

# Website
There is a website available [here](https://irishshagua.github.io/dublin-pubs-map) which is built as a GitHub Page. This uses the GitHub API to read current list of pubs from ![a resource stored in this repo](postgres-pubs-dump.txt). So it should always be up to date

# Visualisation
A GeoJson file is also located ![here](dublin-pubs.geojson). When viewing on Github this should be rendered by a GeoJson viewer.

# Updates
When adding or updating pubs, they should be edited ![here](postgres-pubs-dump.txt) and then ![this](convertToGeoJson.py) should be run to rebuild the geo json file so that the visualisations (as mentioned above) are up to date on Github. This is not a requirement for the GitHub Page mentioned further above, as this is rendered in OpenStreet Maps with detail from the ![master](postgres-pubs-dump.txt) data file.
