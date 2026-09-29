"""Reference program: fetch and print one place's Waqt state over HTTP.

    python -m api_consumer.cli --base-url http://localhost:8000 --lat 21.4225 --lon 39.8262
"""

from __future__ import annotations

import argparse
import sys

from .waqt_api import WaqtApiClient, WaqtApiError, WaqtTransportError


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--instant", default=None, help="ISO 8601 (default: now)")
    ap.add_argument("--provider", default="arithmetic-tabular")
    return ap


def render(waqt: dict, version: dict | None) -> str:
    lines = []
    if waqt["status"] != "OK":
        lines.append(f"Waqt is undefined here/now: {waqt['undefined_reason']}")
    else:
        lines.append(f"Waqt clock : {waqt['waqt']['display']}  ({waqt['weekday']})")
        lines.append(f"Hijri      : {waqt['hijri']['display']}")
        lines.append(f"timezone   : {waqt['timezone']['name']}")
        ne = waqt["next_event"]
        if ne:
            lines.append(f"next event : {ne['name']} at {ne['instant']} (in {ne['countdown']['display']})")
    c = waqt["computation"]
    lines.append(f"computation: {c['engine']} r{c['revision']} (accuracy {c['accuracy_level']})")
    if version:
        lines.append(f"server     : waqt-core {version['waqt_core_version']}, API {version['api_version']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    client = WaqtApiClient(args.base_url)
    try:
        waqt = client.get_waqt(args.lat, args.lon, instant=args.instant, calendar_provider=args.provider)
        try:
            version = client.get_version()
        except (WaqtApiError, WaqtTransportError):
            version = None  # pre-1.4.0 server: fine, just no version block
        print(render(waqt, version))
        return 0
    except WaqtApiError as e:
        print(f"api-consumer: server rejected the request — {e}", file=sys.stderr)
        return 2
    except WaqtTransportError as e:
        print(f"api-consumer: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
