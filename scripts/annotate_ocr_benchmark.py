#!/usr/bin/env python3

"""
Local manual-annotation tool for the final 50-image OCR benchmark.

Purpose:
    Fill in "manual_transcription" in
    data/benchmark/final_benchmark_metadata.csv by hand, one image
    at a time, without retyping ingredient lists from scratch and
    without ever auto-copying Open Food Facts reference text into
    the ground-truth field.

This is a standalone local tool. It:
- Reads/writes ONLY data/benchmark/final_benchmark_metadata.csv
- Reads images ONLY from data/benchmark/final_images/ (read-only)
- Does not import or modify the matcher, OCR pipeline, backend,
  frontend, or the 300-product held-out evaluation in any way.

Usage:
    ./venv/bin/python scripts/annotate_ocr_benchmark.py
    ./venv/bin/python scripts/annotate_ocr_benchmark.py --port 8765

Then open http://127.0.0.1:8765 in a browser.

Every Save writes the full CSV back to disk immediately (atomic
write via a temp file + rename), so progress survives closing the
browser tab, killing the server, or the machine sleeping.
"""

from __future__ import annotations

import argparse
import atexit
import csv
import json
import mimetypes
import signal
import sys
import threading
import webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = BASE_DIR / "data" / "benchmark"
METADATA_PATH = BENCHMARK_DIR / "final_benchmark_metadata.csv"
IMAGES_DIR = BENCHMARK_DIR / "final_images"
LOCK_PATH = BENCHMARK_DIR / ".annotate_lock"

DEFAULT_PORT = 8765


class AlreadyRunningError(Exception):
    pass


def acquire_lock(lock_path: Path) -> None:
    """
    Refuse to start a second instance against the same metadata file.

    Two instances writing the same CSV is exactly what caused real
    data loss during development of this tool (a forgotten process
    silently overwrote a live annotation session). This makes that
    mistake impossible instead of just fixed-after-the-fact.
    """
    import os

    if lock_path.exists():
        try:
            existing_pid = int(lock_path.read_text().strip())
        except (ValueError, OSError):
            existing_pid = None

        if existing_pid is not None:
            try:
                os.kill(existing_pid, 0)
                alive = True
            except ProcessLookupError:
                alive = False
            except PermissionError:
                alive = True  # exists, owned by someone else

            if alive:
                raise AlreadyRunningError(
                    "Another annotation-tool instance appears to be "
                    f"running already (pid {existing_pid}). Stop it "
                    "before starting a new one - running two at once "
                    "against the same CSV can silently overwrite "
                    "each other's saves.\n"
                    f"If that process is actually gone, delete "
                    f"{lock_path} and try again."
                )

        # Stale lock file from a process that no longer exists.
        lock_path.unlink()

    lock_path.write_text(str(os.getpid()))


def release_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass

# Columns this tool is allowed to write. Everything else in the
# CSV (code, image_path, reference_ingredients, ...) is treated as
# read-only context and is never modified by this tool.
EDITABLE_COLUMNS = [
    "manual_transcription",
    "manual_transcription_notes",
    "annotation_status",
]

STATUS_INCOMPLETE = "incomplete"
STATUS_COMPLETE = "complete"


# ============================================================
# DATA LAYER
# ============================================================

class AnnotationStore:
    """
    Disk-is-source-of-truth wrapper around the metadata CSV.

    Deliberately does NOT cache rows in memory between requests.
    Every read and every write re-reads the CSV from disk first.
    This file is tiny (50 rows), so the cost of that is negligible,
    and it is the only way to make concurrent access safe: a long-
    lived in-memory cache that gets rewritten wholesale on save is
    exactly what caused real data loss in practice, when a second,
    forgotten server process (with its own stale cache) wrote the
    whole file from an old snapshot and clobbered rows a live
    session had already filled in. Every write here starts from
    whatever is on disk *right now*, not from a snapshot taken at
    process startup.

    This still assumes a single writer process at a time (see the
    PID lock in main()) - it removes the staleness bug, not the
    theoretical two-writers-in-the-same-instant race, which a local
    single-user annotation tool does not need to solve.
    """

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

        if not self.path.exists():
            raise FileNotFoundError(
                f"Missing {self.path}. Run "
                "scripts/download_ocr_benchmark_final.py first."
            )

        # Fail fast at startup if the file is unreadable or malformed,
        # even though every request re-reads it independently.
        self._read_from_disk()

    def _read_from_disk(self):
        df = pd.read_csv(self.path, dtype=str, keep_default_na=False)

        if "code" not in df.columns:
            raise ValueError(
                f"{self.path} has no 'code' column - unexpected schema."
            )

        # Migrate: add annotation_status if this CSV predates it.
        # Never infer "complete" from existing text - status only
        # ever becomes "complete" through an explicit save from the
        # UI, so a pre-existing non-empty manual_transcription still
        # starts as "incomplete" until a human confirms it.
        if "annotation_status" not in df.columns:
            df["annotation_status"] = STATUS_INCOMPLETE

        df["annotation_status"] = df["annotation_status"].replace(
            "", STATUS_INCOMPLETE
        )

        for column in EDITABLE_COLUMNS:
            if column not in df.columns:
                df[column] = ""

        columns = list(df.columns)
        rows = df.to_dict(orient="records")
        return columns, rows

    def list_rows(self):
        with self._lock:
            _columns, rows = self._read_from_disk()
            return rows

    def get_row(self, code: str):
        with self._lock:
            _columns, rows = self._read_from_disk()
            for row in rows:
                if row["code"] == code:
                    return row
            return None

    def save_row(
        self,
        code: str,
        manual_transcription: str,
        manual_transcription_notes: str,
        annotation_status: str,
    ):
        if annotation_status not in (STATUS_INCOMPLETE, STATUS_COMPLETE):
            raise ValueError(
                f"Invalid annotation_status: {annotation_status!r}"
            )

        # Authoritative check: a row can only be "complete" when the
        # transcription actually contains non-whitespace text. This
        # is enforced here (not just in the browser) so it can't be
        # bypassed by a client bug, a stale page, or a direct API
        # call - which is exactly how 47 empty rows previously ended
        # up marked complete.
        if (
            annotation_status == STATUS_COMPLETE
            and not manual_transcription.strip()
        ):
            raise ValueError(
                "Cannot mark complete: manual_transcription is empty."
            )

        with self._lock:
            columns, rows = self._read_from_disk()

            idx = None
            for i, row in enumerate(rows):
                if row["code"] == code:
                    idx = i
                    break

            if idx is None:
                raise KeyError(f"Unknown product code: {code}")

            rows[idx]["manual_transcription"] = manual_transcription
            rows[idx]["manual_transcription_notes"] = (
                manual_transcription_notes
            )
            rows[idx]["annotation_status"] = annotation_status

            self._write_to_disk(columns, rows)

            return dict(rows[idx])

    def _write_to_disk(self, columns, rows):
        """Assumes caller already holds self._lock."""

        tmp_path = self.path.with_suffix(".csv.tmp")

        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        tmp_path.replace(self.path)


# ============================================================
# HTML / JS FRONTEND (single page, no build step, no framework)
# ============================================================

PAGE_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>OCR Benchmark Annotation</title>
<style>
  :root {
    color-scheme: light;
    --bg: #f6f5f2;
    --panel: #ffffff;
    --border: #ddd6cb;
    --text: #2b2621;
    --muted: #7a7268;
    --accent: #b5522a;
    --complete: #3f7d4f;
    --incomplete: #b08a3e;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
  }
  #layout { display: flex; height: 100vh; }
  #sidebar {
    width: 220px;
    flex-shrink: 0;
    overflow-y: auto;
    background: var(--panel);
    border-right: 1px solid var(--border);
    padding: 12px 0;
  }
  #sidebar h2 {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
    padding: 0 14px 8px;
    margin: 0;
  }
  .item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    cursor: pointer;
    font-size: 13px;
  }
  .item:hover { background: #f1ede6; }
  .item.active { background: #ece2d6; font-weight: 600; }
  .dot {
    width: 9px; height: 9px; border-radius: 50%;
    flex-shrink: 0;
    background: var(--incomplete);
  }
  .dot.complete { background: var(--complete); }
  #main {
    flex: 1;
    overflow-y: auto;
    padding: 20px 28px 60px;
  }
  #progress {
    font-size: 14px;
    color: var(--muted);
    margin-bottom: 14px;
  }
  #topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 16px;
  }
  .nav-buttons button {
    margin-left: 6px;
  }
  button {
    font: inherit;
    padding: 7px 14px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--panel);
    cursor: pointer;
  }
  button.primary {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
  }
  button:disabled { opacity: 0.5; cursor: default; }
  #content { display: flex; gap: 24px; align-items: flex-start; }
  #image-pane {
    flex: 1.1;
    min-width: 0;
  }
  #image-pane img {
    max-width: 100%;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: white;
    display: block;
  }
  #form-pane {
    flex: 1;
    min-width: 0;
  }
  .meta {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 14px;
    font-size: 13px;
    line-height: 1.5;
  }
  .meta b { color: var(--text); }
  .meta .row { margin-bottom: 2px; }
  #reference-box {
    background: #fbf3e7;
    border: 1px solid #e3cfa4;
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 14px;
    font-size: 13px;
  }
  #reference-box .label {
    font-weight: 600;
    color: #8a6a2c;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.03em;
    margin-bottom: 6px;
  }
  #reference-box .warning {
    color: #8a6a2c;
    font-size: 12px;
    margin-top: 8px;
  }
  #reference-text {
    white-space: pre-wrap;
    font-family: ui-monospace, monospace;
    font-size: 12.5px;
  }
  label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 4px;
  }
  textarea, input[type=text] {
    width: 100%;
    font: inherit;
    font-family: ui-monospace, monospace;
    font-size: 13px;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 8px;
    resize: vertical;
  }
  #transcription {
    min-height: 220px;
    margin-bottom: 14px;
  }
  #notes { min-height: 50px; margin-bottom: 14px; }
  .status-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
  }
  #save-state {
    font-size: 12px;
    color: var(--muted);
    margin-left: 10px;
  }
  #copy-ref {
    font-size: 12px;
    padding: 4px 10px;
  }
  #validation-error {
    color: #a3312a;
    font-size: 12.5px;
    margin-top: 8px;
  }
</style>
</head>
<body>

<div id="layout">
  <div id="sidebar">
    <h2>50 images</h2>
    <div id="item-list"></div>
  </div>

  <div id="main">
    <div id="topbar">
      <div id="progress"></div>
      <div class="nav-buttons">
        <button id="btn-prev">&larr; Prev</button>
        <button id="btn-next-incomplete">Next incomplete</button>
        <button id="btn-next">Next &rarr;</button>
      </div>
    </div>

    <div id="content">
      <div id="image-pane">
        <img id="image" src="" alt="benchmark image">
      </div>

      <div id="form-pane">
        <div class="meta">
          <div class="row"><b>Code:</b> <span id="m-code"></span></div>
          <div class="row"><b>Product name:</b> <span id="m-name"></span></div>
          <div class="row"><b>Target language:</b> <span id="m-lang"></span></div>
          <div class="row"><b>Declared allergens (OFF):</b> <span id="m-declared"></span></div>
          <div class="row"><b>Trace allergens (OFF):</b> <span id="m-trace"></span></div>
        </div>

        <div id="reference-box">
          <div class="label">Open Food Facts reference ingredients (context only)</div>
          <div id="reference-text"></div>
          <button id="copy-ref">Copy into draft below</button>
          <div class="warning">
            This is NOT ground truth. It is never copied automatically -
            use it only as a hint, then correct it against what is
            actually visible in the image.
          </div>
        </div>

        <label for="transcription">Manual transcription (exactly as visible in the image)</label>
        <textarea id="transcription" placeholder="Type or paste-and-correct the visible ingredient section here..."></textarea>

        <label for="notes">Notes (optional - e.g. blurry, cropped, illegible portion)</label>
        <textarea id="notes"></textarea>

        <div class="status-row">
          <input type="checkbox" id="mark-complete">
          <label for="mark-complete" style="margin:0;">Mark this row complete</label>
        </div>

        <button class="primary" id="btn-save">Save</button>
        <span id="save-state"></span>
        <div id="validation-error"></div>
      </div>
    </div>
  </div>
</div>

<script>
let rows = [];
let currentIndex = 0;
let dirty = false;

async function loadRows() {
  const res = await fetch('/api/rows');
  rows = await res.json();
  renderSidebar();
  goTo(0);
}

function renderSidebar() {
  const list = document.getElementById('item-list');
  list.innerHTML = '';
  rows.forEach((row, i) => {
    const el = document.createElement('div');
    el.className = 'item' + (i === currentIndex ? ' active' : '');
    el.innerHTML =
      '<span class="dot' +
      (row.annotation_status === 'complete' ? ' complete' : '') +
      '"></span><span>' + row.code + '</span>';
    el.onclick = () => { saveCurrent(() => goTo(i)); };
    list.appendChild(el);
  });
}

function updateProgress() {
  const done = rows.filter(r => r.annotation_status === 'complete').length;
  document.getElementById('progress').textContent =
    done + ' / ' + rows.length + ' complete';
}

function goTo(i) {
  if (i < 0 || i >= rows.length) return;
  currentIndex = i;
  const row = rows[i];

  document.getElementById('image').src = '/image/' + encodeURIComponent(row.image_path.split('/').pop());
  document.getElementById('m-code').textContent = row.code;
  document.getElementById('m-name').textContent = row.product_name || '(no name in dataset)';
  document.getElementById('m-lang').textContent = row.target_language;
  document.getElementById('m-declared').textContent = row.declared_allergens || 'none';
  document.getElementById('m-trace').textContent = row.trace_allergens || 'none';
  document.getElementById('reference-text').textContent = row.reference_ingredients || '(no reference text available)';

  document.getElementById('transcription').value = row.manual_transcription || '';
  document.getElementById('notes').value = row.manual_transcription_notes || '';
  document.getElementById('mark-complete').checked = row.annotation_status === 'complete';

  document.getElementById('save-state').textContent = '';
  document.getElementById('validation-error').textContent = '';
  dirty = false;

  document.getElementById('btn-prev').disabled = (i === 0);
  document.getElementById('btn-next').disabled = (i === rows.length - 1);

  renderSidebar();
  updateProgress();
}

function currentDraft() {
  return {
    code: rows[currentIndex].code,
    manual_transcription: document.getElementById('transcription').value,
    manual_transcription_notes: document.getElementById('notes').value,
    annotation_status: document.getElementById('mark-complete').checked ? 'complete' : 'incomplete',
  };
}

async function saveCurrent(onDone) {
  const draft = currentDraft();
  const errorEl = document.getElementById('validation-error');
  errorEl.textContent = '';

  // Client-side check first, so the user gets an instant message
  // without a round trip. The server enforces the same rule
  // independently (see AnnotationStore.save_row) - that is the
  // authoritative check; this is just a fast-path UX nicety.
  if (
    draft.annotation_status === 'complete' &&
    draft.manual_transcription.trim() === ''
  ) {
    errorEl.textContent =
      'Cannot mark complete: the transcription field is empty. ' +
      'Enter the visible ingredient text, or uncheck "Mark this row complete".';
    document.getElementById('save-state').textContent = '';
    // Do not navigate away and do not save - this prevents an
    // empty row from ever being persisted as "complete", including
    // via Prev/Next/sidebar clicks.
    return;
  }

  document.getElementById('save-state').textContent = 'Saving...';

  const res = await fetch('/api/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(draft),
  });

  if (!res.ok) {
    let message = 'Save failed.';
    try {
      const body = await res.json();
      if (body && body.error) message = body.error;
    } catch (e) {}
    errorEl.textContent = message;
    document.getElementById('save-state').textContent = '';
    return;
  }

  const saved = await res.json();
  rows[currentIndex] = saved;
  dirty = false;
  document.getElementById('save-state').textContent = 'Saved.';
  updateProgress();
  renderSidebar();
  if (onDone) onDone();
}

document.getElementById('transcription').addEventListener('input', () => { dirty = true; });
document.getElementById('notes').addEventListener('input', () => { dirty = true; });
document.getElementById('mark-complete').addEventListener('change', () => { dirty = true; });

document.getElementById('copy-ref').addEventListener('click', () => {
  const ref = rows[currentIndex].reference_ingredients || '';
  const field = document.getElementById('transcription');
  field.value = ref;
  dirty = true;
  field.focus();
});

document.getElementById('btn-save').addEventListener('click', () => saveCurrent());

document.getElementById('btn-prev').addEventListener('click', () => {
  saveCurrent(() => goTo(currentIndex - 1));
});

document.getElementById('btn-next').addEventListener('click', () => {
  saveCurrent(() => goTo(currentIndex + 1));
});

document.getElementById('btn-next-incomplete').addEventListener('click', () => {
  saveCurrent(() => {
    let i = rows.findIndex((r, idx) => idx > currentIndex && r.annotation_status !== 'complete');
    if (i === -1) {
      i = rows.findIndex(r => r.annotation_status !== 'complete');
    }
    if (i !== -1) goTo(i);
  });
});

window.addEventListener('beforeunload', (e) => {
  if (dirty) {
    e.preventDefault();
    e.returnValue = '';
  }
});

loadRows();
</script>
</body>
</html>
"""


# ============================================================
# HTTP SERVER
# ============================================================

class Handler(BaseHTTPRequestHandler):

    store: AnnotationStore = None  # set in main()

    def log_message(self, format, *args):
        pass  # keep console quiet

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            body = PAGE_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/rows":
            self._send_json(self.store.list_rows())
            return

        if path.startswith("/image/"):
            filename = unquote(path[len("/image/"):])
            # Prevent path traversal - only serve exact filenames
            # from IMAGES_DIR, never a nested/relative path.
            if "/" in filename or ".." in filename:
                self.send_error(400, "Invalid image filename")
                return

            image_path = IMAGES_DIR / filename
            if not image_path.is_file():
                self.send_error(404, "Image not found")
                return

            content_type = (
                mimetypes.guess_type(str(image_path))[0]
                or "application/octet-stream"
            )
            data = image_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path != "/api/save":
            self.send_error(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except ValueError:
            self._send_json({"error": "invalid JSON"}, status=400)
            return

        try:
            saved = self.store.save_row(
                code=str(payload["code"]),
                manual_transcription=str(
                    payload.get("manual_transcription", "")
                ),
                manual_transcription_notes=str(
                    payload.get("manual_transcription_notes", "")
                ),
                annotation_status=str(
                    payload.get("annotation_status", STATUS_INCOMPLETE)
                ),
            )
        except (KeyError, ValueError) as exc:
            self._send_json({"error": str(exc)}, status=400)
            return

        self._send_json(saved)


def main():
    parser = argparse.ArgumentParser(
        description="Local annotation tool for the OCR benchmark."
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"Port to serve on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't automatically open a browser tab.",
    )
    args = parser.parse_args()

    try:
        acquire_lock(LOCK_PATH)
    except AlreadyRunningError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)

    # Release the lock on every normal exit path, INCLUDING a plain
    # `kill <pid>` (SIGTERM), not just Ctrl+C. Python's default
    # SIGTERM handling skips `finally` blocks entirely, which is
    # exactly the gap that left a stale lock file after `kill` in
    # testing - atexit alone does not fire for SIGTERM either unless
    # the signal is first turned into a normal Python exception.
    atexit.register(release_lock, LOCK_PATH)

    def _handle_termination(signum, frame):
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_termination)
    signal.signal(signal.SIGINT, _handle_termination)

    try:
        Handler.store = AnnotationStore(METADATA_PATH)

        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
        url = f"http://127.0.0.1:{args.port}"

        print(f"Annotation tool running at {url}")
        print(f"Editing: {METADATA_PATH}")
        print(f"Images from: {IMAGES_DIR}")
        print(
            "Every row is read from and written straight to disk - "
            "there is no in-memory cache to go stale."
        )
        print("Press Ctrl+C to stop.")

        if not args.no_browser:
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    finally:
        release_lock(LOCK_PATH)


if __name__ == "__main__":
    main()
