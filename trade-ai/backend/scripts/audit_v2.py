"""Audit an explicitly selected existing V2 database; no repair or default path."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from market_ai.v2.paper_audit import audit_database


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path, help='Existing SQLite file, opened read-only')
    parser.add_argument('--max-records', type=int, default=1_000_000)
    parser.add_argument('--max-body-bytes', type=int, default=2_097_152)
    parser.add_argument('--max-findings', type=int, default=200)
    parser.add_argument('--max-total-body-bytes', type=int, default=134_217_728)
    parser.add_argument('--require-domain', action='store_true', help='Legacy missing domain history must be INCOMPLETE')
    args = parser.parse_args(argv)
    if min(args.max_records, args.max_body_bytes, args.max_findings, args.max_total_body_bytes) < 1:
        parser.error('limits must be positive')
    report = audit_database(args.database, max_records=args.max_records,
                            max_body_bytes=args.max_body_bytes, max_findings=args.max_findings,
                            max_total_body_bytes=args.max_total_body_bytes, require_domain=args.require_domain)
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return {'PASS': 0, 'MISMATCH': 1, 'INCOMPLETE': 2, 'CORRUPT': 3, 'ERROR': 4}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
