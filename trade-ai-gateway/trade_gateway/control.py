"""Local file-based graceful shutdown; no remotely accessible admin endpoint."""
import json
import os
import secrets
import threading
from pathlib import Path


class LocalControl:
    def __init__(self, directory: Path, shutdown):
        self.directory = Path(directory)
        self.shutdown = shutdown
        self.pidfile = self.directory / 'gateway.pid.json'
        self.stopfile = self.directory / 'gateway.stop.json'
        self.run_id = secrets.token_hex(16)
        self.done = threading.Event()
        self.thread = None

    def start(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        # Do not overwrite a running gateway's control record.
        with self.pidfile.open('x', encoding='utf-8') as f:
            json.dump({'pid': os.getpid(), 'run_id': self.run_id}, f)
        self.pidfile.chmod(0o600)
        def watch():
            while not self.done.wait(.5):
                if self.check_stop():
                    return
        self.thread = threading.Thread(target=watch, daemon=True)
        self.thread.start()

    def check_stop(self):
        try:
            body = json.loads(self.stopfile.read_text(encoding='utf-8-sig'))
            if body.get('pid') == os.getpid() and body.get('run_id') == self.run_id:
                self.shutdown()
                return True
        except (OSError, ValueError, AttributeError):
            pass
        return False

    def close(self):
        self.done.set()
        if self.thread:
            self.thread.join(timeout=1)
        for path in (self.pidfile, self.stopfile):
            try:
                if json.loads(path.read_text(encoding='utf-8-sig')).get('run_id') == self.run_id:
                    path.unlink()
            except (OSError, ValueError, AttributeError):
                pass
