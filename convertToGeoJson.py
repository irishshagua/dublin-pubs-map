#!/usr/bin/env python3

import json

with open('dublinBoundary.geojson', encoding='utf-8') as source:
    boundary = json.load(source)
with open('visits.json', encoding='utf-8') as source:
    visits = json.load(source)

features = [
    {
        'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [visit['longitude'], visit['latitude']]},
        'properties': {'marker-symbol': 'beer', 'name': visit['name'], 'review': visit['review']},
    }
    for visit in visits
]
features.append(boundary)
with open('dublin-pubs.geojson', 'w', encoding='utf-8') as outfile:
    json.dump({'type': 'FeatureCollection', 'features': features}, outfile, indent=2)
