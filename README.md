# Dublin Pubs

Two brothers on a mission to visit the pubs of Dublin.

- [Explore the map](https://irishshagua.github.io/dublin-pubs-map)
- [View recorded visits](visits.json)
- [View the GeoJSON map](dublin-pubs.geojson)

## Plan a route

On the map, choose **Done**, **Undone candidates** or **Both**. Green markers are recorded visits; orange markers are OSM pub candidates. Unlinked candidates may already have been visited, and some OSM links are automatic estimates.

Select up to nine orange markers on desktop, or three on a mobile browser, using their **Add to route** buttons or the list below the map. Enter your home address, then open **walking directions in Google Maps**. Stops are used in the order selected; the route starts and ends at home. The address is stored in your browser, not in the repository, and is sent to Google only when you open directions. Use **Clear home** to remove it.

## Add a visited pub

1. Find the pub on the Undone map or in the candidate list. Its popup and list row show an OSM ID such as `node/122079566`; follow the link and check that it is the right venue. Coordinates are also in [osm-pubs.json](osm-pubs.json). If it isn't in the snapshot, leave the OSM ID unknown for now.
2. Append an object to the JSON array in [visits.json](visits.json). Pick an unused `visit-` ID followed by digits, and enter the actual coordinates, name and review. Start with `"osm_id": null`. Preserve existing IDs, names and reviews. For reference, this is the existing Dawson Lounge entry; do not reuse its ID:

   ```json
   {
     "id": "visit-0001",
     "latitude": 53.33972,
     "longitude": -6.25886,
     "name": "Dawson Lounge",
     "review": "Smallest Pub In Ireland",
     "osm_id": "way/268843105"
   }
   ```

3. If the pub has a matching OSM ID, link the new visit. For example, substitute your new visit ID and the pub's actual OSM ID in `python3 osm_pubs.py link visit-0451 node/122079566`. This checks the ID and prevents assigning one venue to two visits. If you don't know the ID, keep `null`; the visit appears in Done but its potential OSM candidate may remain in Undone.
4. From the repository root, run `python3 validate_pubs.py` and `python3 convertToGeoJson.py`. Review shared-coordinate warnings. The website computes Undone from the links when it loads; no separate candidate file regeneration is needed.
5. Check in `visits.json` and `dublin-pubs.geojson` on `master` and push them. For example, after reviewing `git status`, run:

   ```sh
   git add visits.json dublin-pubs.geojson
   git commit --only -m "Add pub visit" -- visits.json dublin-pubs.geojson
   git push origin master
   ```

## Fix a Done/Undone overlap

Find the recorded visit in [visits.json](visits.json) by name and coordinates, and click the orange candidate for its OSM ID. Check they really are the same venue: nearby pubs, duplicate OSM objects, old names and moves can be misleading. For an unlinked visit, use `python3 osm_pubs.py link <visit-id> <osm-id>`, then validate and push `visits.json` as above. If a link is wrong or already belongs to another visit, record the old ID, set the incorrect visit's `osm_id` to `null` in `visits.json`, and then link the correct visit. The validator rejects duplicate or unknown OSM IDs; do not change historical names or reviews. A pub that moved can legitimately have two historical visits: don't link its old location to the new location just because the name matches.

The first-pass notes and remaining suggestions are preserved in [osm-unmatched-next.md](osm-unmatched-next.md). Unmatched historical visits remain visible in Done, including closed pubs; unlinked OSM candidates remain visible in Undone.

## Match visits to OpenStreetMap pubs

Open [osm-unmatched-next.md](osm-unmatched-next.md) for the current unlinked visits. Suggestions show a candidate name, distance and OpenStreetMap link; bar-tagged suggestions are labelled. Change `[ ]` to `[x]` only for the same place, at most one per visit. Nearby-only suggestions may be different pubs or renamed venues: proximity alone is not proof. Leave uncertainty unchecked. Previously linked high-confidence estimates are listed in [the original matches](osm-high-confidence-links.md), [fuzzy-name matches](osm-fuzzy-confidence-links.md) and [bar matches](osm-bar-confidence-links.md); they have not been independently verified.

```sh
python3 osm_pubs.py apply osm-unmatched-next.md
python3 validate_pubs.py
```

This updates `visits.json` without changing the checklist. Include both files in your change. If the correct pub is not suggested, find its ID in [osm-pubs.json](osm-pubs.json) and run `python3 osm_pubs.py link <visit-id> <osm-id>`; this requires a matching ID from the snapshot. An OSM pub cannot be linked to two visits.

The checklist is tied to the matcher version, OSM snapshot and visit details other than links. When those change, preserve the old checklist and create a fresh one with `python3 osm_pubs.py review new-review.md`; the command never overwrites an existing file or carries forward notes automatically. Earlier checklists remain as records. Previously linked visits are omitted; an already-linked candidate is shown without a checkbox. Do not alter or delete suggestion rows or confirmed markers: the apply command validates the whole file before writing.

## Refresh OpenStreetMap pubs

The snapshot contains named `amenity=pub` and `amenity=bar` features inside `dublinBoundary.geojson`. Both are used to match existing visits, but only pub-tagged venues are shown as Undone candidates. Same-name duplicate representations can be grouped while preserving their source IDs. Some venues may be missing, closed, duplicated or incorrectly tagged. Undone candidates can already be visited until their links are recorded.

Download the Dublin PBF from [BBBike](https://download.bbbike.org/osm/bbbike/Dublin/) and record its snapshot date. Install `osmium` and `shapely`, then run:

```sh
python3 -m pip install osmium shapely
python3 osm_pubs.py extract /path/to/Dublin.osm.pbf --source-date YYYY-MM-DD --replace
python3 osm_pubs.py review new-review.md
```

The extractor refuses to replace the snapshot if a confirmed OSM ID is missing or would conflict; resolve the changed feature before refreshing. The generated data is derived from [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) and available under the ODbL.

## Refreshing the licence list

The published `remaining-pubs.json` comes from Revenue's [register of renewed liquor licences](https://www.revenue.ie/en/corporate/information-about-revenue/statistics/excise/licences/liquor-licences.aspx). It includes **only** rows whose description is exactly `Publican's Licence (7-Day Ordinary)` and whose county field is exactly either `CO. DUBLIN` or `DUBLIN CITY`. Both are needed for Dublin city and county. It is a licence register, not a complete directory of open pubs: premises with another county label, new or unrenewed licences, closures, and licence changes may be absent. The date is Revenue's register date, not the download date. A premises may have renewed after that date.

To refresh the displayed licence total, install Python 3 and the workbook reader, then run:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 refresh_licences.py
```

The script downloads the current [Revenue XLS](https://www.revenue.ie/en/corporate/documents/statistics/excise/liquor-licences.xls), validates its headers and date, and writes `remaining-pubs.json`, `licence-review.csv` and `licence-source.json` with the source URL, register date and workbook SHA-256. The initial published data uses Revenue's 2026-11-03 register (2026/2027), downloaded 2026-11-23, SHA-256 `b37f55aa1d6457d373daade85c861196d1fb0a83948e7abc0ee9d401a7c6563b`. To reproduce an older refresh, retain the original workbook and pass `--xls /path/to/liquor-licences.xls`; local input must be verified against Revenue separately. Include the output files and any changed overrides or location cache together in the repository. No reviews are changed by this process.

## Previous Revenue matching investigation

Revenue matching results in the generated licence files are experimental and are not the source of the OSM map. The Revenue count is independent of historical visits and counts licences, not necessarily distinct pubs.

The November 2026 snapshot contained 639 licences, 450 historical visits and 503 licences without verified coordinates. A rough offline OpenStreetMap address experiment identified 85 unlocated entries with a potentially matching street and house number near a visit; these were not verified matches. Nearby or shared addresses can refer to different pubs, and Revenue trading names may differ from visit names. Address-to-location matching and stronger name/location evidence may improve coverage; keep uncertain matches separate from verified visits.

The earlier Revenue prototype is available in the `gh-pages` commit `c6a0586`. The retained `refresh_licences.py`, `osm-locations.json`, `licence-review.csv` and overrides document that matching attempt.

### Experimental matching details

Inspect `licence-review.csv`, Revenue's address, and the existing visit before deciding. The candidate list is a hint, not a match. Edit `licence-overrides.json`, keyed by Revenue licence reference. To link a visit, copy its **exact** name and coordinates from `visits.json`. For example, replace `<licence reference>` with the correct reference after verifying the premises:

```json
{
  "<licence reference>": {
    "visit": {"name": "Dawson Lounge", "latitude": 53.33972, "longitude": -6.25886}
  }
}
```

A visit selector must identify exactly one row and cannot be linked to two current licences. The visit's coordinates are used unless a location override is supplied. To decide a record is not visited, needs further review, or should be excluded (for example, a hotel), use `"decision": "remaining"`, `"review"`, or `"excluded"` instead of `visit`. Hotels are **not** automatically excluded. Hotel-named records default to review; manually inspect other records as needed. Decisions survive refreshes by licence reference; references missing from a later workbook are reported and retained for inspection. A changed or removed visit must have its override updated.

If a remaining decision conflicts with a visit that you have checked is a different pub, add `"dismissed_visits"` to that override as a list of visit selectors using the same name/latitude/longitude format above. Only those specific visits are dismissed; new possible matches still return the licence to review.

To add a verified location, add `"location": {"latitude": 53.33972, "longitude": -6.25886, "source": "<link or description of evidence>"}` to the appropriate override after checking that it is the actual premises. It can accompany either a visit or a decision. Do not estimate or guess coordinates. Run the refresh again and review the changed CSV and JSON. Do not add a home address to these files.

### OpenStreetMap locations

The checked-in `osm-locations.json` caches locations derived from [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, via the [BBBike Dublin extract](https://download.bbbike.org/osm/bbbike/Dublin/), initially dated 2026-11-21. Each entry links to its OSM node or closed way and records the extract date and Revenue name and address; a changed name or address invalidates the match. Only unique pub/bar features with an exact normalized trading name and corroborating address are accepted: a distinctive matching street, a matching street and house number or locality, or a matching non-generic locality when OSM has no street. For valid closed ways the point is the polygon centroid, or an interior point if the centroid falls outside. Multiple matching OSM features remain unresolved. No bulk geocoder is used; unmapped and uncertain entries have null coordinates. OSM data is available under the [ODbL](https://opendatacommons.org/licenses/odbl/).

To rebuild the cache, download `Dublin.osm.pbf` from BBBike, note its snapshot date, install the optional `osmium` and `shapely` Python packages, and run:

```sh
pip install osmium shapely
python3 refresh_licences.py --osm-pbf /path/to/Dublin.osm.pbf --osm-date YYYY-MM-DD
```

This replaces the cache; manual overrides are retained. Regular refreshes reuse the checked-in cache and need only `xlrd`.
