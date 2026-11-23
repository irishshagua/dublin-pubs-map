import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import refresh_licences as refresh


class Sheet:
    rows = [
        ['Register @ 03 November 2026'] + [''] * 8,
        refresh.HEADERS,
        ['CITY1', refresh.DESCRIPTION, 'City Ltd', 'City Pub', '', 'Dame Street', '', '', 'DUBLIN CITY'],
        ['COUNTY1', refresh.DESCRIPTION, 'County Ltd', 'County Pub', '', 'Main Street', '', '', 'CO. DUBLIN'],
        ['OTHER1', refresh.DESCRIPTION, 'Other Ltd', 'Other Pub', '', 'Dublin Road', '', '', 'CO. CORK'],
    ]
    nrows = len(rows)

    def row_values(self, index):
        return self.rows[index]

    def cell_value(self, row, column):
        return self.rows[row][column]


class Workbook:
    nsheets = 1

    def sheet_by_index(self, index):
        return Sheet()


class RefreshTests(unittest.TestCase):
    def test_city_and_county_are_included(self):
        with patch.object(refresh.xlrd, 'open_workbook', return_value=Workbook()):
            date, records = refresh.load_workbook(b'workbook')
        self.assertEqual(date, '2026-11-03')
        self.assertEqual(set(records), {'CITY1', 'COUNTY1'})

    def test_name_only_match_is_probable_and_duplicate_is_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workbook = root / 'register.xls'
            workbook.write_bytes(b'workbook')
            visits = root / 'postgres-pubs-dump.txt'
            visits.write_text('53.3\t-6.3\tCity Pub\tOriginal review\n', encoding='utf-8')

            def run_refresh():
                with patch.object(refresh, 'ROOT', root), \
                     patch.object(refresh.xlrd, 'open_workbook', return_value=Workbook()), \
                     patch.object(sys, 'argv', ['refresh_licences.py', '--xls', str(workbook)]), \
                     contextlib.redirect_stdout(io.StringIO()):
                    refresh.main()
                data = json.loads((root / 'remaining-pubs.json').read_text(encoding='utf-8'))
                return next(pub for pub in data['pubs'] if pub['licence_ref'] == 'CITY1')['status']

            self.assertEqual(run_refresh(), 'probable')
            self.assertEqual(visits.read_text(encoding='utf-8'), '53.3\t-6.3\tCity Pub\tOriginal review\n')
            with visits.open('a', encoding='utf-8') as file:
                file.write('53.31\t-6.31\tCity Pub\tOther review\n')
            self.assertEqual(run_refresh(), 'review')

    def test_new_visit_reopens_manual_remaining_and_dismissal_is_specific(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workbook = root / 'register.xls'
            workbook.write_bytes(b'workbook')
            visits = root / 'postgres-pubs-dump.txt'
            visits.write_text('', encoding='utf-8')
            overrides = root / 'licence-overrides.json'
            decision = {'decision': 'remaining'}
            overrides.write_text(json.dumps({'CITY1': decision}), encoding='utf-8')

            def run_refresh():
                with patch.object(refresh, 'ROOT', root), \
                     patch.object(refresh.xlrd, 'open_workbook', return_value=Workbook()), \
                     patch.object(sys, 'argv', ['refresh_licences.py', '--xls', str(workbook)]), \
                     contextlib.redirect_stdout(io.StringIO()):
                    refresh.main()
                data = json.loads((root / 'remaining-pubs.json').read_text(encoding='utf-8'))
                return next(pub for pub in data['pubs'] if pub['licence_ref'] == 'CITY1')['status']

            self.assertEqual(run_refresh(), 'remaining')
            visits.write_text('53.3\t-6.3\tCity Pub\tVisited\n', encoding='utf-8')
            self.assertEqual(run_refresh(), 'review')
            decision['dismissed_visits'] = [{'name': 'City Pub', 'latitude': 53.3, 'longitude': -6.3}]
            overrides.write_text(json.dumps({'CITY1': decision}), encoding='utf-8')
            self.assertEqual(run_refresh(), 'remaining')
            with visits.open('a', encoding='utf-8') as file:
                file.write('53.31\t-6.31\tCity Pub\tAnother visit\n')
            self.assertEqual(run_refresh(), 'review')


if __name__ == '__main__':
    unittest.main()
