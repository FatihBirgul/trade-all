"""Explicit domain upgrade into a NEW copy only. Source is always read-only."""
from contextlib import closing
from pathlib import Path
import argparse
import json
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.backup_v2 import copy_database
from market_ai.v2 import domain_journal as domain


def copy_upgrade(source, destination, *, clock=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    from market_ai.v2.paper_audit import audit_database
    report = audit_database(source)
    if report['status'] not in ('PASS','INCOMPLETE'):
        raise ValueError('Source accounting/integrity verification failed')
    # Existing target is rejected by copy_database before any cleanup ownership.
    copy_database(source, destination)
    try:
        with closing(sqlite3.connect(destination, isolation_level=None, factory=domain.Connection)) as c:
            c.execute('BEGIN IMMEDIATE')
            try:
                changed = domain.install(c, clock or (lambda:int(time.time()*1000)))
                domain.validate_chain(c)
                c.commit()
            except BaseException:
                c.rollback()
                raise
        return {'status':'upgraded_copy' if changed else 'already_enabled_copy', 'source_modified':False,
                'history_backfilled':False, 'schema_version':domain.VERSION, 'source_audit_status':report['status']}
    except BaseException:
        destination.unlink(missing_ok=True)  # Only this new exclusively created copy.
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path, help='Must not exist; source is never upgraded in place')
    args = parser.parse_args(argv)
    print(json.dumps(copy_upgrade(args.source, args.destination), sort_keys=True))


if __name__ == '__main__':main()
