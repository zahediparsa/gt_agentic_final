"""Check exact name==version pins using https://docs.pypi.org/api/json/.

Usage: python check_requirements.py [requirements.txt]
All physical lines are counted; blank lines and comments need no API lookup.
Other requirement formats are reported to stderr as unsupported.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([^\s=<>!~*;,]+)")


def fetch_json(name, version=None):
    """Return PyPI metadata, or None only when the endpoint returns 404."""
    url = f"https://pypi.org/pypi/{quote(name, safe='')}/"
    if version is not None:
        url += f"{quote(version, safe='')}/"
    request = Request(url + "json", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", default="requirements.txt")
    args = parser.parse_args()
    try:
        with Path(args.file).open(encoding="utf-8-sig") as source:
            lines = source.readlines()
    except (OSError, UnicodeError) as error:
        print(f"Cannot read {args.file}: {error}", file=sys.stderr)
        return 1

    missing_packages = []
    missing_versions = []
    oldest = None
    had_errors = False

    for line_number, line in enumerate(lines, start=1):
        requirement = line.split("#", 1)[0].strip()
        if not requirement:
            continue
        match = PIN.fullmatch(requirement)
        if match is None:
            print(f"Line {line_number}: expected name==version: {requirement}",
                  file=sys.stderr)
            had_errors = True
            continue

        name, version = match.groups()
        pin = f"{name}=={version}"
        try:
            if fetch_json(name) is None:
                missing_packages.append(name)
                continue
            release = fetch_json(name, version)
            if release is None:
                missing_versions.append(pin)
                continue

            # Use exactly the first file, even if a later file is older.
            files = release["urls"]
            if not files:
                raise ValueError("release exists but urls contains no files")
            uploaded = datetime.fromisoformat(files[0]["upload_time"])
            if oldest is None or uploaded < oldest[0]:
                oldest = (uploaded, pin)
        except (URLError, OSError, ValueError, KeyError, TypeError) as error:
            print(f"Line {line_number}: cannot check {pin}: {error}", file=sys.stderr)
            had_errors = True

    print(f"dependencies checked: {len(lines)}")
    print(f"packages not in pypi: {', '.join(missing_packages) or 'none'}")
    print(f"versions not pypi: {', '.join(missing_versions) or 'none'}")
    print(f"oldest pinned release: {oldest[1] if oldest else 'none'}")
    return 1 if had_errors else 0


if __name__ == "__main__":
    sys.exit(main())
