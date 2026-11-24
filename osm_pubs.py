#!/usr/bin/env python3
"""Extract an OSM pub snapshot and review possible links to recorded visits."""

import argparse
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import unicodedata
from datetime import date

ROOT = Path(__file__).resolve().parent
VISITS = ROOT / 'visits.json'
PUBS = ROOT / 'osm-pubs.json'
BOUNDARY = ROOT / 'dublinBoundary.geojson'
OSM_ID = re.compile(r'(node|way|relation)/[1-9][0-9]*\Z')
VISIT_ID = re.compile(r'visit-[0-9]+\Z')
HEADER = re.compile(r'<!-- osm-review-v3 visits=([0-9a-f]{64}) pubs=([0-9a-f]{64}) -->\Z')
ROW = re.compile(r'- \[([ xX])\] (.*) <!-- osm-match visit=(visit-[0-9]+) osm=((?:node|way|relation)/[1-9][0-9]*) -->\Z')
CONFIRMED = re.compile(r'<!-- osm-confirmed visit=(visit-[0-9]+) osm=((?:node|way|relation)/[1-9][0-9]*) -->\Z')


def read_json(path):
    with path.open(encoding='utf-8') as file:
        return json.load(file)


def encode_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def atomic_write(path, text, *, replace):
    path = Path(path)
    if not replace:
        # Exclusive creation is essential: a checklist can contain unprocessed edits.
        with path.open('x', encoding='utf-8', newline='\n') as file:
            file.write(text)
        return
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        if path.exists():
            os.fchmod(fd, path.stat().st_mode & 0o777)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as file:
            file.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def normalize(name):
    value = unicodedata.normalize('NFKD', name.casefold())
    value = ''.join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"['’]", '', value)
    return ' '.join(re.findall(r'[^\W_]+', value, flags=re.UNICODE))


def match_name(name):
    words = normalize(name).split()
    if len(words) > 1 and words[0] == 'the':
        words = words[1:]
    if len(words) > 1 and words[-1] in ('pub', 'bar', 'lounge'):
        words = words[:-1]
    return ' '.join(words)


def distance(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a['latitude'], a['longitude'], b['latitude'], b['longitude']))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 12742000 * math.asin(min(1, math.sqrt(h)))


def id_key(osm_id):
    kind, number = osm_id.split('/')
    return ({'node': 0, 'way': 1, 'relation': 2}[kind], int(number))


def deduplicate(features):
    # Exact normalized names and a 12 m radius are required. A group may contain
    # at most one object of each OSM type; ambiguous possible pairings are left
    # separate instead of guessing which nearby venues are the same.
    by_name = {}
    for feature in features:
        by_name.setdefault(normalize(feature['name']), []).append(feature)
    groups = []
    for name in sorted(by_name):
        records = sorted(by_name[name], key=lambda item: id_key(item['id']))
        neighbours = {item['id']: [] for item in records}
        for index, a in enumerate(records):
            for b in records[index + 1:]:
                if a['id'].split('/')[0] != b['id'].split('/')[0] and distance(a, b) <= 12:
                    neighbours[a['id']].append(b['id'])
                    neighbours[b['id']].append(a['id'])
        by_id = {item['id']: item for item in records}
        used = set()
        for a in records:
            if a['id'] in used:
                continue
            partners = neighbours[a['id']]
            # Only mutually unique pairs are unambiguously the same venue.
            if len(partners) == 1 and len(neighbours[partners[0]]) == 1:
                b = by_id[partners[0]]
                used.add(b['id'])
                ids = sorted((a['id'], b['id']), key=id_key)
            else:
                ids = [a['id']]
            used.add(a['id'])
            groups.append({'id': a['id'], 'name': a['name'], 'latitude': a['latitude'],
                           'longitude': a['longitude'], 'osm_ids': ids})
    return sorted(groups, key=lambda item: id_key(item['id']))


def extract(args):
    try:
        import osmium
        from shapely import wkb
        from shapely.geometry import LineString, Point, Polygon, shape
    except ImportError as error:
        raise ValueError('OSM extraction requires the Python packages osmium and shapely') from error
    if args.output.resolve() in {args.pbf.resolve(), args.boundary.resolve(), args.visits.resolve()}:
        raise ValueError('The OSM snapshot output must not overwrite an input file')
    date.fromisoformat(args.source_date)
    boundary_data = read_json(args.boundary)
    boundary = shape(boundary_data['geometry'] if boundary_data['type'] == 'Feature' else boundary_data)
    if boundary.is_empty or not boundary.is_valid:
        raise ValueError('The boundary geometry is empty or invalid')
    features = []
    relation_ids = set()
    emitted_relations = set()
    invalid = []
    factory = osmium.geom.WKBFactory()

    class Handler(osmium.SimpleHandler):
        def add(self, kind, osm_id, tags, point):
            if tags.get('amenity') not in ('pub', 'bar') or not tags.get('name', '').strip():
                return
            if point is None or point.is_empty or not math.isfinite(point.x) or not math.isfinite(point.y):
                invalid.append(f'{kind}/{osm_id}')
                return
            if boundary.covers(point):
                features.append({'id': f'{kind}/{osm_id}', 'name': tags['name'].strip(),
                                 'latitude': point.y, 'longitude': point.x, 'amenity': tags['amenity']})

        def node(self, node):
            if node.tags.get('amenity') not in ('pub', 'bar') or not node.tags.get('name', '').strip():
                return
            self.add('node', node.id, node.tags, Point(node.location.lon, node.location.lat) if node.location.valid() else None)

        def way(self, way):
            if way.tags.get('amenity') not in ('pub', 'bar') or not way.tags.get('name', '').strip():
                return
            try:
                coords = [(node.location.lon, node.location.lat) for node in way.nodes]
                if not coords:
                    point = None
                elif len(coords) >= 4 and coords[0] == coords[-1]:
                    polygon = Polygon(coords)
                    point = polygon.representative_point() if polygon.is_valid and not polygon.is_empty else None
                elif len(coords) >= 2:
                    point = LineString(coords).interpolate(0.5, normalized=True)
                else:
                    point = Point(coords[0])
                self.add('way', way.id, way.tags, point)
            except (RuntimeError, ValueError):
                invalid.append(f'way/{way.id}')

        def relation(self, relation):
            if relation.tags.get('amenity') in ('pub', 'bar') and relation.tags.get('name', '').strip():
                relation_ids.add(relation.id)

        def area(self, area):
            if area.from_way() or area.tags.get('amenity') not in ('pub', 'bar') or not area.tags.get('name', '').strip():
                return
            relation_id = area.orig_id()
            emitted_relations.add(relation_id)
            try:
                geometry = wkb.loads(factory.create_multipolygon(area), hex=True)
                self.add('relation', relation_id, area.tags,
                         geometry.representative_point() if geometry.is_valid and not geometry.is_empty else None)
            except (RuntimeError, ValueError):
                invalid.append(f'relation/{relation_id}')

    Handler().apply_file(str(args.pbf), locations=True)
    missing_relations = sorted(relation_ids - emitted_relations)
    if invalid:
        print('Warning: invalid or missing OSM geometry: ' + ', '.join(invalid), file=sys.stderr)
    if missing_relations:
        print('Warning: named pub relations without assembled area geometry: ' +
              ', '.join('relation/' + str(value) for value in missing_relations), file=sys.stderr)
    categories = {feature['id']: feature['amenity'] for feature in features}
    groups = deduplicate(features)
    pubs, bars = [], []
    for group in groups:
        group['amenity'] = 'pub' if any(categories[osm_id] == 'pub' for osm_id in group['osm_ids']) else 'bar'
        (pubs if group['amenity'] == 'pub' else bars).append(group)
    if not pubs:
        raise ValueError('No named pub features within the boundary; refusing an empty snapshot')
    snapshot = {'source_date': args.source_date, 'pubs': pubs, 'bars': bars}
    aliases = validate_pubs(snapshot)
    if args.visits.exists():
        validate_visits(read_json(args.visits), aliases)
    atomic_write(args.output, encode_json(snapshot), replace=args.replace)
    print(f'Extracted {len(features)} named features into {len(pubs)} pub candidates and {len(bars)} bars for matching ({len(missing_relations)} relations without areas)')


def validate_point(item, label):
    lat, lon = item.get('latitude'), item.get('longitude')
    if (isinstance(lat, bool) or isinstance(lon, bool) or not isinstance(lat, (int, float)) or
        not isinstance(lon, (int, float)) or not math.isfinite(lat) or not math.isfinite(lon) or
        not -90 <= lat <= 90 or not -180 <= lon <= 180):
        raise ValueError(f'Invalid coordinates for {label}')


def validate_pubs(snapshot):
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get('pubs'), list):
        raise ValueError('OSM snapshot must contain a pubs array')
    date.fromisoformat(snapshot['source_date'])
    aliases = {}
    bars = snapshot.get('bars', [])
    if not isinstance(bars, list):
        raise ValueError('OSM bars must be an array')
    for pub in snapshot['pubs'] + bars:
        if not isinstance(pub, dict) or not isinstance(pub.get('name'), str) or not pub['name'].strip():
            raise ValueError('OSM pub must have a name')
        validate_point(pub, pub['name'])
        ids = pub.get('osm_ids')
        if not isinstance(ids, list) or not ids or pub.get('id') not in ids:
            raise ValueError('Each OSM pub must include its canonical ID in osm_ids')
        for osm_id in ids:
            if not isinstance(osm_id, str) or not OSM_ID.fullmatch(osm_id) or osm_id in aliases:
                raise ValueError(f'Invalid or duplicate OSM ID: {osm_id!r}')
            aliases[osm_id] = pub
    return aliases


def validate_visits(visits, aliases):
    if not isinstance(visits, list):
        raise ValueError('Visits must be a JSON array')
    by_id, assigned = {}, {}
    for visit in visits:
        if not isinstance(visit, dict):
            raise ValueError('Each visit must be an object')
        visit_id = visit.get('id')
        if not isinstance(visit_id, str) or not VISIT_ID.fullmatch(visit_id) or visit_id in by_id:
            raise ValueError(f'Invalid or duplicate visit ID: {visit_id!r}')
        if not isinstance(visit.get('name'), str) or not visit['name'].strip() or not isinstance(visit.get('review'), str):
            raise ValueError(f'Invalid name or review for {visit_id}')
        validate_point(visit, visit_id)
        if 'osm_id' not in visit:
            raise ValueError(f'Missing osm_id for {visit_id}')
        osm_id = visit.get('osm_id')
        if osm_id is not None:
            if not isinstance(osm_id, str) or osm_id not in aliases:
                raise ValueError(f'Visit {visit_id} has obsolete or unknown OSM ID {osm_id!r}')
            canonical = aliases[osm_id]['id']
            if canonical in assigned:
                raise ValueError(f'OSM pub {canonical} linked to both {assigned[canonical]} and {visit_id}')
            assigned[canonical] = visit_id
        by_id[visit_id] = visit
    return by_id, assigned


def load_inputs(args):
    visits = read_json(args.visits)
    snapshot = read_json(args.pubs)
    aliases = validate_pubs(snapshot)
    by_id, assigned = validate_visits(visits, aliases)
    return visits, snapshot, aliases, by_id, assigned


def digest(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def fingerprints(visits, snapshot):
    # Linking is the only field intentionally excluded, so applying a checklist
    # does not itself invalidate it. All other source edits require a new review.
    return digest([{k: v for k, v in visit.items() if k != 'osm_id'} for visit in visits]), digest(snapshot)


def md(text):
    return re.sub(r'([\\`*_\[\]<>])', r'\\\1', text.replace('\n', ' ').replace('\r', ' '))


def confidence(visit, pub):
    metres = distance(visit, pub)
    if metres > 120:
        return None
    a, b = normalize(visit['name']), normalize(pub['name'])
    if not a or not b:
        return None
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    left, right = match_name(visit['name']), match_name(pub['name'])
    if len(left) >= 4 and left == right:
        ratio = 1.0
    if a == b and metres <= 50 or ratio >= 0.9 and metres <= 25:
        return 'High', metres, ratio
    if a == b or ratio >= 0.7 and metres <= 80:
        return 'Medium', metres, ratio
    if metres <= 20:
        return 'Nearby', metres, ratio
    return None


def row_text(visit, pub):
    result = confidence(visit, pub)
    if result is None:
        raise ValueError(f"{visit['id']} and {pub['id']} are no longer suggested")
    level, metres, _ = result
    alias_text = ', '.join(f'[{osm_id}](https://www.openstreetmap.org/{osm_id})' for osm_id in pub['osm_ids'])
    category = ' (OSM bar; matching only)' if pub.get('amenity') == 'bar' else ''
    if level == 'Nearby':
        level = 'Nearby only — may be a different pub; check history'
    return (f"**{md(pub['name'])}**{category} — {level}, {metres:.0f} m — {alias_text} "
            f"(`{visit['id']}` → `{pub['id']}`)")


def suggestions(visit, pubs):
    candidates, nearby = [], []
    for pub in pubs:
        result = confidence(visit, pub)
        if result:
            level, metres, ratio = result
            if level == 'Nearby':
                nearby.append((metres, -ratio, id_key(pub['id']), pub))
            else:
                candidates.append((0 if level == 'High' else 1, -ratio, metres, id_key(pub['id']), pub))
    if candidates:
        candidates.sort(key=lambda item: item[:4])
        return [item[4] for item in candidates[:3]]
    nearby.sort(key=lambda item: item[:3])
    return [item[3] for item in nearby[:3]]


def review(args):
    visits, snapshot, aliases, _, assigned = load_inputs(args)
    visits_hash, pubs_hash = fingerprints(visits, snapshot)
    lines = [f'<!-- osm-review-v3 visits={visits_hash} pubs={pubs_hash} -->',
             '# Unmatched visits', '',
             f"Snapshot: {snapshot['source_date']}. Suggestions are not confirmations.",
             'Check a maximum of one candidate per visit only after verifying the actual venue.',
             'Leave uncertain choices unchecked; an unchecked item is not a rejection.',
             'Nearby-only suggestions may be different pubs or renamed venues; proximity alone is not a match.',
             'Do not remove or alter candidate rows; you may add notes outside checklist rows.',
             f'Apply the checks with `python3 osm_pubs.py apply {shlex.quote(str(args.output))}`.',
             'To confirm a pub not listed here, find its exact ID in osm-pubs.json and run',
             '`python3 osm_pubs.py link <visit-id> <osm-id>` after independently verifying the venue.',
             'This file is never overwritten by the review or apply commands.', '']
    for visit in visits:
        if visit.get('osm_id') is not None:
            continue
        lines.extend([f"## {md(visit['name'])} (`{visit['id']}`) — unlinked",
                      f"Visit location: {visit['latitude']}, {visit['longitude']}", ''])
        candidates = suggestions(visit, snapshot['pubs'] + snapshot.get('bars', []))
        for pub in candidates:
            if pub['id'] in assigned:
                lines.append(f"- {row_text(visit, pub)} — already linked to `{assigned[pub['id']]}`; not selectable.")
            else:
                lines.append(f"- [ ] {row_text(visit, pub)} <!-- osm-match visit={visit['id']} osm={pub['id']} -->")
        if not candidates:
            lines.append('No matching or nearby suggestions; use the manual link command if appropriate.')
        lines.append('')
    lines.extend(f"<!-- osm-confirmed visit={visit['id']} osm={visit['osm_id']} -->"
                 for visit in visits if visit.get('osm_id') is not None)
    atomic_write(args.output, '\n'.join(lines), replace=False)
    print(f"Created {args.output} for {sum(visit.get('osm_id') is None for visit in visits)} unmatched visits; no links were changed")


def apply_review(args):
    visits, snapshot, aliases, by_id, assigned = load_inputs(args)
    expected = fingerprints(visits, snapshot)
    lines = args.review.read_text(encoding='utf-8').splitlines()
    if not lines or not (header := HEADER.fullmatch(lines[0])) or header.groups() != expected:
        raise ValueError('Review snapshot is missing or stale; preserve it and create a new review file')
    checked = {}
    seen = set()
    confirmed_at_generation = set()
    for number, line in enumerate(lines[1:], 2):
        if '<!-- osm-confirmed' in line:
            marker = line.partition('<!-- osm-confirmed')[2]
            match = CONFIRMED.fullmatch('<!-- osm-confirmed' + marker)
            if not match:
                raise ValueError(f'Invalid confirmed marker on line {number}')
            visit_id, osm_id = match.groups()
            if visit_id in confirmed_at_generation or visit_id not in by_id or by_id[visit_id].get('osm_id') != osm_id:
                raise ValueError(f'Changed confirmed link on line {number}; create a new checklist')
            confirmed_at_generation.add(visit_id)
            continue
        if not re.match(r'^\s*[-*+]\s+\[[^]]*\]', line):
            continue
        match = ROW.fullmatch(line)
        if not match:
            raise ValueError(f'Invalid checklist row on line {number}; no changes were written')
        tick, description, visit_id, osm_id = match.groups()
        if visit_id not in by_id or osm_id not in aliases or aliases[osm_id]['id'] != osm_id:
            raise ValueError(f'Unknown or obsolete IDs on line {number}')
        visit, pub = by_id[visit_id], aliases[osm_id]
        if description != row_text(visit, pub):
            raise ValueError(f'Changed checklist row on line {number}; restore the original row before applying')
        pair = (visit_id, osm_id)
        if pair in seen:
            raise ValueError(f'Duplicate checklist row on line {number}')
        seen.add(pair)
        if tick.lower() == 'x':
            if visit_id in checked:
                raise ValueError(f'Multiple checked choices for {visit_id}')
            checked[visit_id] = osm_id
    reserved = {aliases[by_id[visit_id]['osm_id']]['id'] for visit_id in confirmed_at_generation}
    expected_rows = {(visit['id'], pub['id']) for visit in visits
                     if visit['id'] not in confirmed_at_generation
                     for pub in suggestions(visit, snapshot['pubs'] + snapshot.get('bars', []))
                     if pub['id'] not in reserved}
    if seen != expected_rows:
        raise ValueError('Checklist rows are missing or unexpected; restore them before applying')
    for visit_id, osm_id in checked.items():
        current = by_id[visit_id].get('osm_id')
        if current is not None and aliases[current]['id'] != osm_id:
            raise ValueError(f'{visit_id} is already linked to {current}; refusing to overwrite')
        if osm_id in assigned and assigned[osm_id] != visit_id:
            raise ValueError(f'{osm_id} is already linked to {assigned[osm_id]}')
        assigned[osm_id] = visit_id
    changes = 0
    for visit_id, osm_id in checked.items():
        if by_id[visit_id].get('osm_id') is None:
            by_id[visit_id]['osm_id'] = osm_id
            changes += 1
    if changes:
        atomic_write(args.visits, encode_json(visits), replace=True)
    print(f'Applied {changes} confirmed links; checklist left unchanged')


def link(args):
    visits, _, aliases, by_id, assigned = load_inputs(args)
    if args.visit_id not in by_id:
        raise ValueError(f'Unknown visit ID: {args.visit_id}')
    if args.osm_id not in aliases:
        raise ValueError(f'Unknown or obsolete OSM ID: {args.osm_id}')
    visit, pub = by_id[args.visit_id], aliases[args.osm_id]
    current = visit.get('osm_id')
    if current is not None and aliases[current]['id'] != pub['id']:
        raise ValueError(f'{args.visit_id} is already linked to {current}; refusing to overwrite')
    if pub['id'] in assigned and assigned[pub['id']] != args.visit_id:
        raise ValueError(f"{pub['id']} is already linked to {assigned[pub['id']]}")
    if current is None:
        visit['osm_id'] = args.osm_id
        atomic_write(args.visits, encode_json(visits), replace=True)
        print(f"Confirmed {args.visit_id} ({visit['name']}) → {args.osm_id} ({pub['name']})")
    else:
        print(f'{args.visit_id} is already linked to the same OSM pub; no change')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    extraction = commands.add_parser('extract', help='Extract named pub nodes, ways and relation areas from an offline PBF')
    extraction.add_argument('pbf', type=Path)
    extraction.add_argument('--source-date', required=True, help='PBF snapshot date, YYYY-MM-DD')
    extraction.add_argument('--boundary', type=Path, default=BOUNDARY)
    extraction.add_argument('--visits', type=Path, default=VISITS,
                            help='Validate existing confirmed links against the new snapshot, if the file exists')
    extraction.add_argument('--output', type=Path, default=PUBS)
    extraction.add_argument('--replace', action='store_true', help='Explicitly replace the output snapshot')
    extraction.set_defaults(run=extract)
    for command in ('review', 'apply', 'link'):
        sub = commands.add_parser(command, help={'review': 'Create a new Markdown checklist without overwriting an existing file',
                                                'apply': 'Apply checked choices after validating the whole checklist',
                                                'link': 'Manually confirm a specific visit and OSM ID'}[command])
        sub.add_argument('--visits', type=Path, default=VISITS)
        sub.add_argument('--pubs', type=Path, default=PUBS)
        if command == 'review':
            sub.add_argument('output', type=Path)
            sub.set_defaults(run=review)
        elif command == 'apply':
            sub.add_argument('review', type=Path)
            sub.set_defaults(run=apply_review)
        else:
            sub.add_argument('visit_id')
            sub.add_argument('osm_id')
            sub.set_defaults(run=link)
    args = parser.parse_args()
    try:
        args.run(args)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(1, f'Error: {error}\n')


if __name__ == '__main__':
    main()
