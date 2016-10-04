#!/usr/bin/python
# -*- coding: utf-8 -*-

import csv
import json

with open("postgres-pubs-dump.txt") as file: 
    reader = csv.reader(file, delimiter='\t')

    data = {}
    data['type'] = 'FeatureCollection'
    features = []
    for row in reader:
    	feature = {}
    	feature['type'] = 'Feature'
    	
    	geometry = {}
    	geometry['type'] = 'Point'
    	geometry['coordinates'] = [row[0], row[1]]
    	feature['geometry'] = geometry
    	
    	properties = {}
        properties['marker-symbol'] = 'bar'
    	properties['name'] = row[2]
        properties['review'] = row[3]
    	feature['properties'] = properties

    	features.append(feature)

    data['features'] = features

    with open('dublin-pubs.geojson', 'w') as outfile:
	    json.dump(data, outfile)
