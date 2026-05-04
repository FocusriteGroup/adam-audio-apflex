import os
import shutil
import threading
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from kivy.clock import Clock

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Data")
ARCHIVE_DIR = os.path.join(DATA_DIR, "Archive")

DEBOUNCE_SECONDS = 0.5


class _JsonEventHandler(FileSystemEventHandler):
    """Handles file system events for JSON files in the data directory.

    Uses a debounce timer per file to avoid processing files that are
    still being written by the measurement program.
    """

    def __init__(self, on_file_ready):
        super().__init__()
        self._on_file_ready = on_file_ready
        self._pending = {}
        self._lock = threading.Lock()

    def _schedule(self, path):
        with self._lock:
            existing = self._pending.get(path)
            if existing:
                existing.cancel()
            timer = threading.Timer(DEBOUNCE_SECONDS, self._process, args=[path])
            self._pending[path] = timer
            timer.start()

    def _process(self, path):
        with self._lock:
            self._pending.pop(path, None)

        if not os.path.exists(path):
            return

        # Build a unique destination path to avoid archive collisions
        filename = os.path.basename(path)
        base, ext = os.path.splitext(filename)
        dest = os.path.join(ARCHIVE_DIR, filename)
        if os.path.exists(dest):
            dest = os.path.join(ARCHIVE_DIR, f"{base}_{int(time.time())}{ext}")

        shutil.move(path, dest)

        # Notify the Kivy main thread
        Clock.schedule_once(lambda dt: self._on_file_ready(dest))

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".json"):
            self._schedule(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".json"):
            self._schedule(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.endswith(".json"):
            self._schedule(event.dest_path)


class DataWatcher:
    """Watches the Data directory for new or modified JSON files.

    When a file is ready, it is moved to the Archive directory and
    on_file_ready(archive_path) is called on the Kivy main thread.
    """

    def __init__(self, on_file_ready):
        self._handler = _JsonEventHandler(on_file_ready)
        self._observer = Observer()
        self._observer.schedule(self._handler, DATA_DIR, recursive=False)

    def start(self):
        self._observer.start()
        # Process JSON files already present in Data/ at startup
        self._scan_existing()

    def stop(self):
        self._observer.stop()
        self._observer.join()

    def _scan_existing(self):
        """Process any JSON files already in the Data directory."""
        for fname in os.listdir(DATA_DIR):
            if fname.endswith(".json"):
                self._handler._schedule(os.path.join(DATA_DIR, fname))
