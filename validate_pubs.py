#!/usr/bin/env python3
"""Validate the canonical visit list before regenerating GeoJSON."""

import argparse
import json
import math
import re
import sys

import osm_pubs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', nargs='?', default='visits.json')
    parser.add_argument('--osm-pubs', default='osm-pubs.json', help='OSM snapshot used to validate links')
    args = parser.parse_args()
    try:
        with open(args.file, encoding='utf-8') as source:
            visits = json.load(source)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f'Could not read {args.file}: {error}', file=sys.stderr)
        return 1

    if not isinstance(visits, list) or not visits:
        print('The pub list must be a non-empty array', file=sys.stderr)
        return 1

    errors = 0
    ids = set()
    osm_ids = {}
    coordinates = {}
    for index, visit in enumerate(visits, 1):
        if not isinstance(visit, dict):
            print(f'Visit {index}: expected an object', file=sys.stderr)
            errors += 1
            continue
        visit_id = visit.get('id')
        name, review = visit.get('name'), visit.get('review')
        osm_id = visit.get('osm_id')
        latitude, longitude = visit.get('latitude'), visit.get('longitude')
        valid_coordinates = all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and -limit <= value <= limit
            for value, limit in ((latitude, 90), (longitude, 180))
        )
        if (not isinstance(visit_id, str) or not re.fullmatch(r'visit-[0-9]+', visit_id) or visit_id in ids
                or not isinstance(name, str) or not name.strip()
                or not isinstance(review, str) or not review.strip()
                or 'osm_id' not in visit
                or (osm_id is not None and (not isinstance(osm_id, str)
                    or not re.fullmatch(r'(node|way|relation)/[1-9][0-9]*', osm_id)))
                or not valid_coordinates):
            print(f'Visit {index}: invalid fields or duplicate ID', file=sys.stderr)
            errors += 1
            continue
        ids.add(visit_id)

        if osm_id is not None:
            if osm_id in osm_ids:
                print(f'Visit {index}: OSM ID {osm_id} already claimed by visit {osm_ids[osm_id]}',
                      file=sys.stderr)
                errors += 1
            else:
                osm_ids[osm_id] = index
        point = (latitude, longitude)
        if point in coordinates:
            previous_index, previous_name = coordinates[point]
            print(f'Warning: visit {index} ({name}) shares coordinates with '
                  f'visit {previous_index} ({previous_name})', file=sys.stderr)
        else:
            coordinates[point] = (index, name)
    if not errors and osm_ids:
        try:
            with open(args.osm_pubs, encoding='utf-8') as source:
                aliases = osm_pubs.validate_pubs(json.load(source))
            osm_pubs.validate_visits(visits, aliases)
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
            print(f'Invalid OSM links: {error}', file=sys.stderr)
            errors += 1


    if errors:
        print(f'Validation failed: {errors} invalid visit(s)', file=sys.stderr)
        return 1
    print(f'Validated {len(visits)} visits')
    return 0


if __name__ == "__main__":
    sys.exit(main())
