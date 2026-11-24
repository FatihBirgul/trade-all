"""Local-only V2 launcher; never binds public interfaces or starts V1 services."""
import logging
from logging.handlers import RotatingFileHandler
import argparse
import os
from pathlib import Path
import uvicorn
from market_ai.v2.api import create_app
from market_ai.v2.scanner import ScannerWorker
from market_ai.v2.tracking import TrackingWorker


def main():
    parser = argparse.ArgumentParser(description="Trade AI V2 local paper-only backend")
    parser.add_argument("--database", type=Path, required=True, help="New, separate V2 SQLite file")
    parser.add_argument("--mode", choices=("live", "fixture"), default="live")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--scanner", action="store_true", help="Opt-in bounded 60-second worker; persisted pause defaults on")
    parser.add_argument("--tracking", action="store_true", help="Opt-in paper-free analysis follow worker, at most 2 analyses per minute")
    parser.add_argument("--domain-journal", action="store_true", help="Require domain extension; new DB only or explicitly migrated copy")
    parser.add_argument("--discovery",action="store_true",help="Explicit paper-free dual-scanner worker; account config defaults disabled")
    args = parser.parse_args()
    token = os.environ.get("V2_API_TOKEN", "")
    if len(token) < 24:
        parser.error("Set V2_API_TOKEN to a private random value of at least 24 characters")
    log_path = args.database.resolve().parent / "v2-runtime.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger("market_ai.v2").addHandler(handler)
    logging.getLogger("market_ai.v2").setLevel(logging.INFO)
    worker=None
    tracking_worker=None
    discovery_worker=None
    try:
        app = create_app(args.database, mode=args.mode, token=token, domain_journal=args.domain_journal)
        if args.scanner:
            worker=ScannerWorker(app.state.v2.scanner)
            worker.start()
        if args.tracking:
            tracking_worker=TrackingWorker(app.state.tracking)
            tracking_worker.start()
        if args.discovery:
            discovery_worker=app.state.v2.discovery
            discovery_worker.start()
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)
    finally:
        # Pause guard prevents in-flight analyses from placing new candidates.
        if discovery_worker is not None:
            discovery_worker.stop()
        if tracking_worker is not None:
            tracking_worker.stop()
        if worker is not None:
            worker.stop()
        logging.getLogger("market_ai.v2").removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    main()

