from __future__ import annotations
import logging
import threading
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
from backend.config import NOTES_DIR, SUPPORTED_EXTS
from backend.ingest import ingest_file

logger = logging.getLogger(__name__)

_DEBOUNCE_SECONDS = 0.75
_pending: dict[Path, threading.Timer] = {}
_pending_lock = threading.Lock()
_processing_lock = threading.Lock()


def _wait_for_stable(path: Path) -> bool:
    prev_size = -1
    for _ in range(20):
        time.sleep(0.1)
        try:
            curr_size = path.stat().st_size
        except FileNotFoundError:
            return False
        if curr_size == prev_size and curr_size > 0:
            return True
        prev_size = curr_size
    return path.exists() and path.stat().st_size > 0


def _process_file(path: Path) -> None:
    if not _processing_lock.acquire(blocking=False):
        logger.debug("Ingestion already running; skipping %s", path.name)
        return
    try:
        if path.suffix.lower() not in SUPPORTED_EXTS:
            logger.debug("Skipping unsupported file: %s", path.name)
            return

        logger.info("Auto-ingesting note: %s", path.name)
        try:
            result = ingest_file(path, replace=True)
            if result.chunks > 0:
                logger.info(
                    "Ingested %d chunks from %s in %.2fs",
                    result.chunks, path.name, result.latency,
                )
            else:
                logger.warning("No chunks from %s: %s", path.name, result.detail or result.status)
        except Exception as e:
            logger.error("Ingestion failed for %s: %s", path.name, e)
    finally:
        _processing_lock.release()


def _schedule(path: Path) -> None:
    with _pending_lock:
        timer = _pending.pop(path, None)
        if timer:
            timer.cancel()
        new_timer = threading.Timer(_DEBOUNCE_SECONDS, _process_file, args=(path,))
        new_timer.daemon = True
        _pending[path] = new_timer
        new_timer.start()


class _NotesHandler(FileSystemEventHandler):
    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not _wait_for_stable(path):
            return
        _schedule(path)

    def on_modified(self, event: FileModifiedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not _wait_for_stable(path):
            return
        _schedule(path)


_observer: Observer | None = None


def _scan_existing() -> None:
    files = sorted(
        p for p in NOTES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )
    if not files:
        logger.info("No existing files in %s", NOTES_DIR)
        return

    logger.info("Scanning %d existing file(s) in %s …", len(files), NOTES_DIR)
    for path in files:
        _process_file(path)


def start_watcher() -> None:
    global _observer
    _scan_existing()
    handler = _NotesHandler()
    _observer = Observer()
    _observer.schedule(handler, str(NOTES_DIR), recursive=False)
    _observer.start()
    logger.info("File watcher started on %s", NOTES_DIR)


def stop_watcher() -> None:
    global _observer
    with _pending_lock:
        for timer in _pending.values():
            timer.cancel()
        _pending.clear()
    if _observer:
        _observer.stop()
        _observer.join()
        _observer = None
