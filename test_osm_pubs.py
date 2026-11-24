import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

import osm_pubs
import validate_pubs


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.visits_path = self.root / 'visits.json'
        self.pubs_path = self.root / 'osm-pubs.json'
        self.review_path = self.root / 'review.md'
        self.visits = [
            {'id': 'visit-0001', 'latitude': 53.1, 'longitude': -6.2,
             'name': 'Alpha Pub', 'review': 'First review', 'osm_id': None},
            {'id': 'visit-0002', 'latitude': 53.1001, 'longitude': -6.2,
             'name': 'Alpha Pub', 'review': 'Second review', 'osm_id': None},
            {'id': 'visit-0003', 'latitude': 53.2, 'longitude': -6.2,
             'name': 'No suggestion', 'review': 'Unmatched', 'osm_id': None},
        ]
        self.snapshot = {'source_date': '2026-11-21', 'pubs': [
            {'id': 'node/1', 'name': 'Alpha Pub', 'latitude': 53.1, 'longitude': -6.2,
             'osm_ids': ['node/1', 'way/1']},
            {'id': 'node/2', 'name': 'Alpha Pubs', 'latitude': 53.1001, 'longitude': -6.2,
             'osm_ids': ['node/2']},
        ]}
        self.write_json(self.visits_path, self.visits)
        self.write_json(self.pubs_path, self.snapshot)
        self.args = argparse.Namespace(visits=self.visits_path, pubs=self.pubs_path,
                                       output=self.review_path, review=self.review_path)

    def tearDown(self):
        self.directory.cleanup()

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def tick(self, visit_id, osm_id):
        lines = self.review_path.read_text(encoding='utf-8').splitlines()
        marker = f'<!-- osm-match visit={visit_id} osm={osm_id} -->'
        lines = [line.replace('- [ ] ', '- [x] ', 1) if marker in line else line for line in lines]
        self.review_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def test_visit_validator_rejects_unknown_and_duplicate_alias_links(self):
        def validate():
            with patch.object(sys, 'argv', ['validate_pubs.py', str(self.visits_path), '--osm-pubs', str(self.pubs_path)]), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return validate_pubs.main()

        self.visits[0]['osm_id'] = 'node/999'
        self.write_json(self.visits_path, self.visits)
        self.assertEqual(validate(), 1)
        self.visits[0]['osm_id'] = 'node/1'
        self.visits[1]['osm_id'] = 'way/1'
        self.write_json(self.visits_path, self.visits)
        self.assertEqual(validate(), 1)
        self.visits[1]['osm_id'] = None
        self.write_json(self.visits_path, self.visits)
        self.assertEqual(validate(), 0)

    def test_common_name_variants_require_close_location_for_high_confidence(self):
        visit = {'name': 'Crowes Pub', 'latitude': 53.32905, 'longitude': -6.23048}
        nearby = {'name': 'Crowe’s', 'latitude': 53.32912, 'longitude': -6.23048}
        far = {'name': 'Crowe’s', 'latitude': 53.32935, 'longitude': -6.23048}
        self.assertEqual(osm_pubs.confidence(visit, nearby)[0], 'High')
        self.assertEqual(osm_pubs.confidence(visit, far)[0], 'Medium')
        self.assertNotEqual(osm_pubs.match_name('Crowes Pub'), osm_pubs.match_name('Crowley Pub'))

    def test_nearby_only_suggestion_is_not_a_high_confidence_match(self):
        visit = {'id': 'visit-0042', 'name': 'The Wellington', 'latitude': 53.3, 'longitude': -6.2}
        pub = {'id': 'node/44', 'name': 'Bar Eile', 'latitude': 53.30002,
               'longitude': -6.2, 'osm_ids': ['node/44']}
        self.assertEqual(osm_pubs.confidence(visit, pub)[0], 'Nearby')
        self.assertIn('may be a different pub', osm_pubs.row_text(visit, pub))
        far = dict(pub, latitude=53.301)
        self.assertIsNone(osm_pubs.confidence(visit, far))

    def test_matching_only_bar_can_be_confirmed(self):
        self.snapshot['bars'] = [
            {'id': 'way/9', 'name': 'No suggestion', 'latitude': 53.2, 'longitude': -6.2,
             'osm_ids': ['way/9'], 'amenity': 'bar'}
        ]
        self.write_json(self.pubs_path, self.snapshot)
        osm_pubs.review(self.args)
        text = self.review_path.read_text(encoding='utf-8')
        self.assertIn('OSM bar; matching only', text)
        self.tick('visit-0003', 'way/9')
        osm_pubs.apply_review(self.args)
        actual = json.loads(self.visits_path.read_text(encoding='utf-8'))
        self.assertEqual(actual[2]['osm_id'], 'way/9')
        self.assertEqual(len(self.snapshot['pubs']), 2)

    def test_checklist_is_exclusive_and_retains_unmatched_visits(self):
        osm_pubs.review(self.args)
        before = self.review_path.read_text(encoding='utf-8')
        self.assertIn('No suggestion (`visit-0003`)', before)
        self.assertIn('No matching or nearby suggestions', before)
        self.assertIn('https://www.openstreetmap.org/way/1', before)
        self.tick('visit-0001', 'node/1')
        edited = self.review_path.read_bytes()
        with self.assertRaises(FileExistsError):
            osm_pubs.review(self.args)
        self.assertEqual(edited, self.review_path.read_bytes())

    def test_apply_is_atomic_and_keeps_checklist(self):
        osm_pubs.review(self.args)
        self.tick('visit-0001', 'node/1')
        before = self.review_path.read_bytes()
        osm_pubs.apply_review(self.args)
        actual = json.loads(self.visits_path.read_text(encoding='utf-8'))
        self.assertEqual('node/1', actual[0]['osm_id'])
        self.assertIsNone(actual[1]['osm_id'])
        self.assertEqual('First review', actual[0]['review'])
        self.assertEqual(before, self.review_path.read_bytes())
        osm_pubs.apply_review(self.args)
        self.assertEqual(before, self.review_path.read_bytes())

    def test_regenerated_checklist_skips_already_confirmed_visits(self):
        osm_pubs.review(self.args)
        self.tick('visit-0001', 'node/1')
        osm_pubs.apply_review(self.args)
        osm_pubs.apply_review(self.args)  # The original checklist remains reusable.

        self.review_path = self.root / 'next-review.md'
        self.args.output = self.review_path
        self.args.review = self.review_path
        osm_pubs.review(self.args)
        text = self.review_path.read_text(encoding='utf-8')
        self.assertIn('<!-- osm-confirmed visit=visit-0001 osm=node/1 -->', text)
        self.assertNotIn('## Alpha Pub (`visit-0001`)', text)
        self.assertNotIn('<!-- osm-match visit=visit-0001 ', text)
        self.assertNotIn('<!-- osm-match visit=visit-0002 osm=node/1 -->', text)
        self.assertIn('already linked to `visit-0001`; not selectable', text)
        self.assertIn('<!-- osm-match visit=visit-0002 osm=node/2 -->', text)
        self.tick('visit-0002', 'node/2')
        osm_pubs.apply_review(self.args)
        actual = json.loads(self.visits_path.read_text(encoding='utf-8'))
        self.assertEqual([visit['osm_id'] for visit in actual[:2]], ['node/1', 'node/2'])

    def test_conflicting_ticks_do_not_write_any_visit(self):
        osm_pubs.review(self.args)
        self.tick('visit-0001', 'node/1')
        self.tick('visit-0001', 'node/2')
        before = self.visits_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Multiple checked choices'):
            osm_pubs.apply_review(self.args)
        self.assertEqual(before, self.visits_path.read_bytes())

    def test_same_pub_cannot_be_confirmed_for_two_visits(self):
        osm_pubs.review(self.args)
        self.tick('visit-0001', 'node/1')
        self.tick('visit-0002', 'node/1')
        before = self.visits_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already linked'):
            osm_pubs.apply_review(self.args)
        self.assertEqual(before, self.visits_path.read_bytes())

    def test_missing_rows_and_stale_snapshots_are_rejected(self):
        osm_pubs.review(self.args)
        original = self.review_path.read_text(encoding='utf-8')
        filtered = [line for line in original.splitlines() if 'osm-match visit=visit-0001 osm=node/1' not in line]
        self.review_path.write_text('\n'.join(filtered) + '\n', encoding='utf-8')
        before = self.visits_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'rows are missing'):
            osm_pubs.apply_review(self.args)
        self.assertEqual(before, self.visits_path.read_bytes())
        self.review_path.write_text(original, encoding='utf-8')
        self.snapshot['pubs'][0]['name'] = 'New name'
        self.write_json(self.pubs_path, self.snapshot)
        with self.assertRaisesRegex(ValueError, 'stale'):
            osm_pubs.apply_review(self.args)
        self.assertEqual(before, self.visits_path.read_bytes())

    def test_manual_link_accepts_alias_and_rejects_collisions(self):
        self.args.visit_id = 'visit-0001'
        self.args.osm_id = 'way/1'
        osm_pubs.link(self.args)
        before = self.visits_path.read_bytes()
        self.assertEqual('way/1', json.loads(before)[0]['osm_id'])
        self.args.visit_id = 'visit-0002'
        self.args.osm_id = 'node/1'
        with self.assertRaisesRegex(ValueError, 'already linked'):
            osm_pubs.link(self.args)
        self.assertEqual(before, self.visits_path.read_bytes())
        self.args.osm_id = 'node/999'
        with self.assertRaisesRegex(ValueError, 'unknown|obsolete'):
            osm_pubs.link(self.args)
        self.assertEqual(before, self.visits_path.read_bytes())

    def test_ambiguous_duplicate_representations_are_not_combined(self):
        records = [
            {'id': 'node/1', 'name': 'The Pub', 'latitude': 53.1, 'longitude': -6.2},
            {'id': 'way/1', 'name': 'The Pub', 'latitude': 53.10001, 'longitude': -6.2},
            {'id': 'node/2', 'name': 'The Pub', 'latitude': 53.2, 'longitude': -6.2},
            {'id': 'node/3', 'name': 'Another Pub', 'latitude': 53.1, 'longitude': -6.2},
        ]
        groups = osm_pubs.deduplicate(records)
        self.assertEqual(['node/1', 'way/1'], groups[0]['osm_ids'])
        self.assertEqual(3, len(groups))
        records.append({'id': 'node/4', 'name': 'The Pub', 'latitude': 53.10002, 'longitude': -6.2})
        groups = osm_pubs.deduplicate(records)
        self.assertTrue(all(len(group['osm_ids']) == 1 for group in groups))


if __name__ == '__main__':
    unittest.main()
