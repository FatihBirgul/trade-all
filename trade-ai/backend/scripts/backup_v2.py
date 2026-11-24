"""Read-only V2 SQLite backup or restore into a NEW file; never overwrites data."""
from contextlib import closing
from pathlib import Path
import argparse
import sqlite3
import sys
from hashlib import sha256
import json

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from market_ai.v2.product_db import ProductDatabase


def validate(connection):
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("SQLite integrity check failed")
    rows=connection.execute("SELECT version,mode FROM product_meta").fetchall()
    if len(rows)!=1 or rows[0][0]!=1 or rows[0][1] not in ("live","fixture"):
        raise ValueError("Not a supported V2 product database")
    tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in ("accounts","analyses","orders","positions","transactions","events","commands","scanner_state","watchlist","scanner_jobs","notifications","analysis_tracking","analysis_tracking_state","strategy_profiles","equity_snapshots","notification_delivery_state","notification_delivery_attempts","notification_controls"):
        if table not in tables:
            if table in ("scanner_state","watchlist","scanner_jobs","notifications","analysis_tracking","analysis_tracking_state","strategy_profiles","equity_snapshots","notification_delivery_state","notification_delivery_attempts","notification_controls"):continue
            raise ValueError("Missing V2 table: "+table)
        for row in connection.execute(f"SELECT body,body_hash FROM {table}"):
            ProductDatabase.decode(row)
    for record_id, body in connection.execute("SELECT record_id,body_json FROM decision_records"):
        if sha256(body.encode()).hexdigest()!=record_id:
            raise ValueError("Decision record hash mismatch")
    from market_ai.v2 import domain_journal
    if domain_journal.marker(connection):
        domain_journal.validate_chain(connection)
    return rows[0][1]


def copy_database(source, destination):
    source, destination=Path(source).resolve(),Path(destination).resolve()
    if source==destination or not source.is_file():
        raise ValueError("An existing source and a different new destination are required")
    destination.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation prevents accidental overwrites, including a racing job.
    with destination.open("xb"):
        pass
    try:
        with closing(sqlite3.connect(source.as_uri()+"?mode=ro",uri=True)) as src:
            with closing(sqlite3.connect(destination)) as dst:
                src.backup(dst,pages=256)
                mode=validate(dst)
        return {"status":"verified","mode":mode,"destination":str(destination),"overwritten":False}
    except BaseException:
        destination.unlink(missing_ok=True)  # Only the new file reserved above.
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("destination",type=Path,help="Must not exist; restore uses the same verified-copy operation")
    args=parser.parse_args()
    print(json.dumps(copy_database(args.source,args.destination)))


if __name__=="__main__":main()

