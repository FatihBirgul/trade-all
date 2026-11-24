import argparse
import getpass
import json
import logging
import os
from pathlib import Path
import uvicorn
from .app import Settings, create_app
from .store import AuthStore
from .control import LocalControl


def main():
    parser = argparse.ArgumentParser(description="Trade AI private mobile gateway")
    parser.add_argument("--database", type=Path, default=Path("local_data/gateway.sqlite"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve")
    pair = sub.add_parser("pair")
    pair.add_argument("--account", action="append", choices=["AUTO", "MANUAL"])
    pair.add_argument("--discovery-write", action="store_true", help="Explicit dual-scanner configuration/tick grant; no financial or worker activation authority")
    pair.add_argument("--scanner-write", action="store_true", help="Explicit scanner administration grant; paper orders remain disabled")
    pair.add_argument("--notifications-write", action="store_true", help="Explicit owned notification preference grant; no sender or paper orders")
    pair.add_argument("--profiles-write", action="store_true", help="Explicit immutable strategy profile write grant; grants no paper orders")
    sub.add_parser("sessions")
    revoke = sub.add_parser("revoke")
    revoke.add_argument("session_id")
    args = parser.parse_args()
    if args.command == "serve":
        origin = os.environ.get("GATEWAY_PUBLIC_ORIGIN", "")
        token = os.environ.get("V2_API_TOKEN") or getpass.getpass("V2 private backend token (hidden; never paste into Android): ")
        settings = Settings(origin, token, args.database)
        # Drop HTTP client INFO logging, including when installed in an existing environment.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=8787, workers=1,
                    proxy_headers=False, access_log=False, log_level="warning", timeout_keep_alive=5))
        control = LocalControl(args.database.parent, lambda: setattr(server, "should_exit", True))
        try:
            control.start()
            server.run()
        finally:
            control.close()
    else:
        store = AuthStore(args.database)
        if args.command == "pair":
            print("One use / 120 seconds. Enter this only in your Android app:")
            print(store.pairing(accounts=args.account or ["AUTO", "MANUAL"], scanner_write=args.scanner_write, profiles_write=args.profiles_write, notifications_write=args.notifications_write, discovery_write=args.discovery_write))
        elif args.command == "sessions":
            print(json.dumps(store.sessions(), indent=2))
        else:
            store.revoke(args.session_id)
            print("Session revoked.")

if __name__ == "__main__":
    main()
