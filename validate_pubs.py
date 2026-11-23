#!/usr/bin/env python3
"""Validate the tab-separated pub list before regenerating GeoJSON."""

import argparse
import csv
import math
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", default="postgres-pubs-dump.txt")
    args = parser.parse_args()
    errors = 0
    count = 0
    coordinates = {}

    try:
        with open(args.file, encoding="utf-8", newline="") as source:
            for line in source:
                count += 1
                row = line.rstrip("\r\n").split("\t")
                parsed = next(csv.reader([line], delimiter="\t", strict=True))
                if row != parsed or len(row) != 4 or any(not field.strip() for field in row):
                    print(f"Line {count}: expected four non-empty tab-separated fields", file=sys.stderr)
                    errors += 1
                    continue
                try:
                    latitude, longitude = float(row[0]), float(row[1])
                    if not (math.isfinite(latitude) and -90 <= latitude <= 90 and
                            math.isfinite(longitude) and -180 <= longitude <= 180):
                        raise ValueError
                except ValueError:
                    print(f"Line {count}: invalid latitude or longitude", file=sys.stderr)
                    errors += 1
                    continue
                point = (latitude, longitude)
                if point in coordinates:
                    previous_line, previous_name = coordinates[point]
                    print(f"Warning: line {count} ({row[2]}) shares coordinates with "
                          f"line {previous_line} ({previous_name})", file=sys.stderr)
                else:
                    coordinates[point] = (count, row[2])
    except (OSError, UnicodeError, csv.Error) as error:
        print(f"Could not read {args.file}: {error}", file=sys.stderr)
        return 1

    if not count:
        print("The pub list is empty", file=sys.stderr)
        return 1
    if errors:
        print(f"Validation failed: {errors} invalid row(s)", file=sys.stderr)
        return 1
    print(f"Validated {count} pub rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
