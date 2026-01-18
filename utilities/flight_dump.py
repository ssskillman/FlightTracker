# utilities/flight_dump.py
import json
import time
import threading
import queue
from pathlib import Path

class FlightDumper:
    """
    Non-blocking flight dump sink.
    - Main thread calls dumper.submit(payload) (never blocks; drops if queue is full)
    - Background thread writes JSON lines in batches
    """
    def __init__(self, out_path: str, flush_every: float = 5.0, max_queue: int = 50):
        self.out_path = Path(out_path)
        self.flush_every = float(flush_every)
        self.q = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

        self.out_path.parent.mkdir(parents=True, exist_ok=True)

    def start(self):
        if not self._t.is_alive():
            self._t.start()

    def stop(self, timeout: float = 2.0):
        self._stop.set()
        self._t.join(timeout=timeout)

    def submit(self, record: dict) -> bool:
        """
        Returns True if queued, False if dropped.
        """
        try:
            self.q.put_nowait(record)
            return True
        except queue.Full:
            return False

    def _run(self):
        buf = []
        last_flush = time.time()

        while not self._stop.is_set():
            # Wait a bit for work
            try:
                item = self.q.get(timeout=0.5)
                buf.append(item)
            except queue.Empty:
                pass

            now = time.time()
            if buf and (now - last_flush >= self.flush_every):
                self._flush(buf)
                buf.clear()
                last_flush = now

        # final flush
        if buf:
            self._flush(buf)

    def _flush(self, items):
        # Append JSONL
        with self.out_path.open("a", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, default=str))
                f.write("\n")
