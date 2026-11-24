"""Cooperative cancellation between bounded research operations; no partial result publication."""
from threading import Event


class ResearchCancelled(ValueError):
    pass


class CancellationToken:
    def __init__(self):self.event=Event()
    def cancel(self):self.event.set()
    def check(self):
        if self.event.is_set():raise ResearchCancelled('research cancelled; partial results discarded')
