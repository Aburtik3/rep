from __future__ import annotations

import argparse

from domain_hunter.backend.services import recheck
from domain_hunter.collector.collector import collect_domains
from domain_hunter.export.exporter import export_domains


def main() -> None:
    parser = argparse.ArgumentParser(prog="domain-hunter", description="DOMAIN HUNTER PRO manual commands")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("topic")
    collect.add_argument("count", type=int)
    check = sub.add_parser("check")
    check.add_argument("group")
    export = sub.add_parser("export")
    export.add_argument("format", choices=["csv", "xlsx", "txt"])
    args = parser.parse_args()
    if args.command == "collect":
        result = collect_domains(args.topic, args.count)
        print(f"saved={result.saved} raw={result.collected_raw} requested={result.requested}")
    elif args.command == "check":
        filters = {} if args.group == "all" else {"category": args.group}
        print(recheck(filters))
    elif args.command == "export":
        print(export_domains(args.format))


if __name__ == "__main__":
    main()
