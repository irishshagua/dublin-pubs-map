#!/usr/bin/env python3
"""Refresh the Dublin 7-day ordinary licence list and its review queue."""

import argparse
import csv
import difflib
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import unicodedata
from datetime import datetime
from urllib.request import Request, urlopen

import xlrd

ROOT = Path(__file__).resolve().parent
SOURCE_URL = "https://www.revenue.ie/en/corporate/documents/statistics/excise/liquor-licences.xls"
DESCRIPTION = "Publican's Licence (7-Day Ordinary)"
COUNTIES = ('CO. DUBLIN', 'DUBLIN CITY')
HEADERS = ["Licence Ref", "Description", "Licensee Name", "Trading Name", "Nominee Name", "Address 1", "Address 2", "Address 3", "County"]


def normalized(value):
    value = unicodedata.normalize("NFKD", value.casefold())
    value = ''.join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"['’]", '', value)
    value = re.sub(r'[^a-z0-9]+', ' ', value).strip()
    return re.sub(r'^the ', '', value)


def load_workbook(data):
    book = xlrd.open_workbook(file_contents=data)
    if book.nsheets != 1:
        raise ValueError('Expected one worksheet in the Revenue workbook')
    sheet = book.sheet_by_index(0)
    if [str(c).strip() for c in sheet.row_values(1)] != HEADERS:
        raise ValueError('Unexpected Revenue workbook columns')
    title = str(sheet.cell_value(0, 0))
    match = re.search(r'@\s*(\d{1,2}\s+\w+\s+\d{4})', title)
    if not match:
        raise ValueError('Could not find the register date in the workbook title')
    source_date = datetime.strptime(match.group(1), '%d %B %Y').date().isoformat()
    records = {}
    for row_no in range(2, sheet.nrows):
        row = [str(value).strip() for value in sheet.row_values(row_no)]
        if row[1] != DESCRIPTION or row[8] not in COUNTIES:
            continue
        ref = row[0]
        if not ref or ref in records:
            raise ValueError(f'Missing or duplicate licence reference on row {row_no + 1}: {ref!r}')
        trading = '' if row[3].upper() in ('', 'NA') else row[3]
        address = ', '.join(value for value in row[5:9] if value and value.upper() != 'NA')
        records[ref] = {'licence_ref': ref, 'name': trading or row[2], 'address': address,
                        'trading_name_present': bool(trading)}
    if not records:
        raise ValueError('No matching Dublin licences found; refusing to publish an empty list')
    return source_date, records


def point(lat, lon):
    if isinstance(lat, bool) or isinstance(lon, bool):
        raise ValueError('Coordinates must be numbers')
    lat, lon = float(lat), float(lon)
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f'Invalid coordinates: {lat}, {lon}')
    return lat, lon


def load_visits():
    with (ROOT / 'visits.json').open(encoding='utf-8') as file:
        visits = json.load(file)
    if not isinstance(visits, list):
        raise ValueError('Visits must be an array')
    result = []
    for row_no, visit in enumerate(visits, 1):
        if not isinstance(visit, dict) or not isinstance(visit.get('name'), str) or not visit['name'].strip():
            raise ValueError(f'Invalid visit {row_no}')
        lat, lon = point(visit.get('latitude'), visit.get('longitude'))
        result.append({'name': visit['name'], 'latitude': lat, 'longitude': lon})
    return result


def distance(a, b):
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    return 12742000 * math.asin(min(1, math.sqrt(h)))


def load_json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def fingerprints(record):
    return {'name': record['name'], 'address': record['address']}


def extract_osm(path, snapshot_date, records):
    try:
        import osmium
        from shapely.geometry import Polygon
    except ImportError as error:
        raise ValueError('Install osmium and shapely to use --osm-pbf') from error
    datetime.strptime(snapshot_date, '%Y-%m-%d')
    by_name = {}
    for ref, record in records.items():
        if record['trading_name_present']:
            by_name.setdefault(normalized(record['name']), []).append(ref)
    matches = {}

    class Handler(osmium.SimpleHandler):
        def record_location(self, tags, kind, object_id, latitude, longitude):
            street = normalized(tags.get('addr:street', ''))
            city = normalized(tags.get('addr:city', ''))
            number = normalized(tags.get('addr:housenumber', ''))
            for ref in by_name.get(normalized(tags['name']), []):
                record = records[ref]
                address = ' ' + normalized(record['address']) + ' '
                street_matches = street and f' {street} ' in address
                number_matches = number and f' {number} ' in address
                city_matches = city and city not in ('dublin', 'co dublin') and f' {city} ' in address
                generic_streets = {'main street', 'high street', 'church street', 'church road', 'station road', 'bridge street', 'new road'}
                distinctive_street = street_matches and len(street) >= 8 and street not in generic_streets
                # Conflicting street tags are not accepted as a locality-only match.
                address_matches = ((street_matches and (number_matches or city_matches or distinctive_street)) or
                                   (not street and city_matches))
                if not address_matches:
                    continue
                try:
                    lat, lon = point(latitude, longitude)
                except (ValueError, RuntimeError):
                    continue
                matches.setdefault(ref, []).append({'latitude': lat, 'longitude': lon,
                    'source': f'https://www.openstreetmap.org/{kind}/{object_id}',
                    'osm_name': tags['name'], 'osm_address': ', '.join(filter(None, [tags.get('addr:housenumber'), tags.get('addr:street'), tags.get('addr:city')])),
                    'snapshot_date': snapshot_date, **fingerprints(record)})

        def node(self, node):
            tags = dict(node.tags)
            if tags.get('amenity') not in ('pub', 'bar') or not tags.get('name') or not node.location.valid():
                return
            self.record_location(tags, 'node', node.id, node.location.lat, node.location.lon)

        def way(self, way):
            tags = dict(way.tags)
            if (tags.get('amenity') not in ('pub', 'bar') or not tags.get('name') or
                    normalized(tags['name']) not in by_name or not way.is_closed()):
                return
            if len(way.nodes) < 4 or any(not node.location.valid() for node in way.nodes):
                return
            polygon = Polygon([(node.location.lon, node.location.lat) for node in way.nodes])
            if polygon.is_empty or not polygon.is_valid or polygon.area == 0:
                return
            centroid = polygon.centroid
            location = centroid if polygon.covers(centroid) else polygon.representative_point()
            self.record_location(tags, 'way', way.id, location.y, location.x)
    handler = Handler()
    handler.apply_file(str(path), locations=True)
    # Multiple potential features must be resolved by a person, not arbitrarily selected.
    return {ref: candidates[0] for ref, candidates in matches.items() if len(candidates) == 1}


def check_location(location):
    if set(location) != {'latitude', 'longitude', 'source'} or not isinstance(location['source'], str) or not location['source'].strip():
        raise ValueError('A location override needs latitude, longitude and a nonempty source')
    return point(location['latitude'], location['longitude'])


def resolve_visit(selector, visits):
    if not isinstance(selector, dict) or set(selector) != {'name', 'latitude', 'longitude'}:
        raise ValueError('A visit selector needs name, latitude and longitude')
    lat, lon = point(selector['latitude'], selector['longitude'])
    found = [v for v in visits if v['name'] == selector['name'] and v['latitude'] == lat and v['longitude'] == lon]
    if len(found) != 1:
        raise ValueError(f'Visit selector must match exactly one visit: {selector!r}')
    return found[0]


def similar_name(name, other, score):
    if name and name == other:
        return True
    generic = {'bar', 'pub', 'inn', 'house', 'lounge', 'tavern', 'hotel', 'restaurant'}
    left = [word for word in name.split() if word not in generic]
    right = [word for word in other.split() if word not in generic]
    if any(len(a) >= 5 and a == b for a in left for b in right):
        return True
    if score < 0.72:
        return False
    return any(a == b or (len(a) >= 4 and len(b) >= 4 and
               difflib.SequenceMatcher(None, a, b).ratio() >= 0.8)
               for a in left for b in right)


def candidates(record, visits, location):
    result = []
    name = normalized(record['name']) if record['trading_name_present'] else ''
    for visit in visits:
        other = normalized(visit['name'])
        similarity = difflib.SequenceMatcher(None, name, other).ratio() if name and other else 0
        metres = distance(location, (visit['latitude'], visit['longitude'])) if location else None
        if similar_name(name, other, similarity) or (metres is not None and metres <= 250):
            result.append((visit, similarity, metres))
    return sorted(result, key=lambda item: (-item[1], item[2] if item[2] is not None else float('inf')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xls', type=Path, help='Use an already downloaded Revenue workbook instead of downloading it')
    parser.add_argument('--osm-pbf', type=Path, help='Rebuild the OSM coordinate cache from an offline Dublin PBF extract')
    parser.add_argument('--osm-date', help='Snapshot date of the OSM extract, YYYY-MM-DD (required with --osm-pbf)')
    args = parser.parse_args()
    if bool(args.osm_pbf) != bool(args.osm_date):
        parser.error('--osm-pbf and --osm-date must be supplied together')
    data = args.xls.read_bytes() if args.xls else urlopen(Request(SOURCE_URL, headers={'User-Agent': 'DublinPubsTracker/1.0'}), timeout=120).read()
    source_date, records = load_workbook(data)
    visits = load_visits()
    overrides = load_json(ROOT / 'licence-overrides.json', {})
    cache_path = ROOT / 'osm-locations.json'
    cache = extract_osm(args.osm_pbf, args.osm_date, records) if args.osm_pbf else load_json(cache_path, {})
    if not isinstance(overrides, dict) or not isinstance(cache, dict):
        raise ValueError('Overrides and OSM cache must be JSON objects')
    for ref, override in overrides.items():
        if not isinstance(override, dict) or set(override) - {'visit', 'decision', 'location', 'dismissed_visits'}:
            raise ValueError(f'{ref}: unexpected override fields')
        if override.get('decision') not in (None, 'remaining', 'review', 'excluded'):
            raise ValueError(f'{ref}: invalid decision')
        if 'visit' in override and override.get('decision') is not None:
            raise ValueError(f'{ref}: visit and decision are mutually exclusive')
        if 'visit' in override:
            resolve_visit(override['visit'], visits)
        if 'dismissed_visits' in override:
            if override.get('decision') != 'remaining' or not isinstance(override['dismissed_visits'], list):
                raise ValueError(f'{ref}: dismissed_visits requires a remaining decision and a list')
            for selector in override['dismissed_visits']:
                resolve_visit(selector, visits)
        if 'location' in override:
            check_location(override['location'])
    used_visits = {}
    for ref, override in overrides.items():
        if ref in records and 'visit' in override:
            visit = resolve_visit(override['visit'], visits)
            key = (visit['name'], visit['latitude'], visit['longitude'])
            if key in used_visits:
                raise ValueError(f'Visit linked to both {used_visits[key]} and {ref}')
            used_visits[key] = ref
    name_counts = {}
    for record in records.values():
        name = normalized(record['name'])
        name_counts[name] = name_counts.get(name, 0) + 1
    visit_name_counts = {}
    for visit in visits:
        name = normalized(visit['name'])
        visit_name_counts[name] = visit_name_counts.get(name, 0) + 1
    pubs, review_rows = [], []
    for ref, record in sorted(records.items(), key=lambda pair: (pair[1]['name'].casefold(), pair[0])):
        override = overrides.get(ref, {})
        cached = cache.get(ref)
        if cached and any(cached.get(key) != value for key, value in fingerprints(record).items()):
            cached = None
        location_source = ''
        location = None
        if 'location' in override:
            location = check_location(override['location'])
            location_source = override['location']['source']
        elif 'visit' in override:
            visit = resolve_visit(override['visit'], visits)
            location = (visit['latitude'], visit['longitude'])
            location_source = 'confirmed visit'
        elif cached:
            location = point(cached['latitude'], cached['longitude'])
            location_source = cached['source']
        possible = candidates(record, visits, location)
        dismissed = override.get('dismissed_visits', [])
        possible = [item for item in possible if not any(
            item[0]['name'] == selector['name'] and item[0]['latitude'] == selector['latitude'] and
            item[0]['longitude'] == selector['longitude'] for selector in dismissed)]
        reason = ''
        if 'visit' in override:
            status, reason = 'visited', 'manual visit link'
        elif override.get('decision') == 'remaining' and possible:
            status, reason = 'review', 'manual remaining decision conflicts with a possible visit'
        elif override.get('decision'):
            status, reason = override['decision'], 'manual decision'
        elif not record['trading_name_present']:
            status, reason = 'review', 'no trading name'
        elif 'hotel' in normalized(record['name']).split():
            status, reason = 'review', 'hotel: manual decision needed'
        elif possible:
            # Even exact names can refer to different pubs. Proximity supplies independent evidence.
            exact_near = [c for c in possible if normalized(record['name']) == normalized(c[0]['name']) and c[2] is not None and c[2] <= 100]
            similar_near = [c for c in possible if c[2] is not None and c[2] <= 100 and similar_name(normalized(record['name']), normalized(c[0]['name']), c[1])]
            if len(exact_near) == 1 and len(similar_near) == 1 and name_counts[normalized(record['name'])] == 1:
                visit = exact_near[0][0]
                key = (visit['name'], visit['latitude'], visit['longitude'])
                if key not in used_visits:
                    status, reason = 'visited', 'unique exact name and nearby verified location'
                    used_visits[key] = ref
                else:
                    status, reason = 'review', 'possible visit already linked to another licence'
            elif location is None and name_counts[normalized(record['name'])] == 1 and visit_name_counts.get(normalized(record['name'])) == 1 and any(
                    normalized(c[0]['name']) == normalized(record['name']) and
                    (c[0]['name'], c[0]['latitude'], c[0]['longitude']) not in used_visits for c in possible):
                status, reason = 'probable', 'unique exact name match without verified location'
            else:
                status, reason = 'review', 'possible visit: check name and location'
        elif location is None:
            status, reason = 'review', 'no independently verified location'
        else:
            status, reason = 'remaining', 'verified location, no nearby or similarly named visit'
        pubs.append({'licence_ref': ref, 'name': record['name'], 'address': record['address'], 'status': status,
                     'latitude': location[0] if location else None, 'longitude': location[1] if location else None})
        if status in ('review', 'probable'):
            formatted = '; '.join(f"{v['name']} ({v['latitude']}, {v['longitude']}; name {score:.2f}" + (f', {metres:.0f}m' if metres is not None else '') + ')' for v, score, metres in possible)
            review_rows.append({'licence_ref': ref, 'name': record['name'], 'address': record['address'],
                                'reason': reason, 'possible_visits': formatted, 'location_source': location_source})
    output = {'source_date': source_date, 'pubs': pubs}
    (ROOT / 'remaining-pubs.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (ROOT / 'licence-review.csv').open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['licence_ref', 'name', 'address', 'reason', 'possible_visits', 'location_source'])
        writer.writeheader()
        writer.writerows(review_rows)
    if args.osm_pbf:
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    provenance = {'source_url': SOURCE_URL, 'source_date': source_date,
                  'sha256': hashlib.sha256(data).hexdigest(),
                  'input': 'local workbook' if args.xls else 'download',
                  'description': DESCRIPTION, 'counties': list(COUNTIES)}
    (ROOT / 'licence-source.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
    print(f"Revenue register {source_date}; SHA-256 {provenance['sha256']}")
    print(', '.join(f"{status}: {sum(pub['status'] == status for pub in pubs)}" for status in ('visited', 'probable', 'remaining', 'review', 'excluded')))
    print(f"Located: {sum(pub['latitude'] is not None for pub in pubs)}/{len(pubs)}; "
          f"located remaining: {sum(pub['status'] == 'remaining' and pub['latitude'] is not None for pub in pubs)}")
    stale = sorted(set(overrides) - set(records))
    if stale:
        print('Overrides for licences absent from this register (retained): ' + ', '.join(stale), file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, xlrd.XLRDError) as error:
        print(f'Refresh failed: {error}', file=sys.stderr)
        sys.exit(1)
