"""Bounded, process-local vectors; callers still supply authorized documents each time."""
from collections import OrderedDict
from threading import Lock
from time import monotonic

import numpy as np


class EmbeddingCache:
    def __init__(self, max_entries=512, ttl_seconds=900, clock=monotonic):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self.entries = OrderedDict()
        self.lock = Lock()

    def get(self, key):
        with self.lock:
            entry = self.entries.get(key)
            if entry is None:
                return None
            expires, vector = entry
            if expires <= self.clock():
                del self.entries[key]
                return None
            self.entries.move_to_end(key)
            return vector

    def put(self, key, vector):
        frozen = np.array(vector, dtype=np.float64, copy=True)
        frozen.setflags(write=False)
        with self.lock:
            self.entries[key] = (self.clock() + self.ttl_seconds, frozen)
            self.entries.move_to_end(key)
            while len(self.entries) > self.max_entries:
                self.entries.popitem(last=False)

    def clear(self):
        with self.lock:
            self.entries.clear()


document_embeddings = EmbeddingCache()
