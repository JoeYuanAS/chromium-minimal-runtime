#!/usr/bin/env python3
import argparse
import datetime as dt
import http.server
import json
import os
import pathlib
import subprocess
import sys
import urllib.parse


ROOT = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]


class DiagnosticHandler(http.server.SimpleHTTPRequestHandler):
    server_version = "FingerprintDiagnostic/1.0"

    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/__health":
            self._send_json({"ok": True})
            return
        if parsed.path == "/__request_headers":
            self._send_json({
                "method": self.command,
                "path": self.path,
                "client": self.client_address[0],
                "headers": {key: value for key, value in self.headers.items()},
            })
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/__report":
            self._send_json({"ok": False, "error": "not found"}, status=404)
            return

        length = int(self.headers.get("content-length", "0"))
        if length <= 0 or length > 10 * 1024 * 1024:
            self._send_json({"ok": False, "error": "invalid body size"}, status=400)
            return

        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)
            return

        report_dir = pathlib.Path(self.server.report_dir).resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = "fingerprint-report-%s.json" % stamp
        path = report_dir / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._send_json({"ok": True, "path": str(path), "bytes": path.stat().st_size})


def open_content_shell(app, url, app_args):
    if sys.platform != "darwin":
        print("Auto-open is only implemented for macOS. URL: %s" % url)
        return
    command = ["open", "-n", app, "--args"] + app_args + [url]
    subprocess.Popen(command)


def main():
    parser = argparse.ArgumentParser(description="Serve the local fingerprint diagnostic page.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--report-dir", default=str(PROJECT_ROOT / "output" / "fingerprint-reports"))
    parser.add_argument("--open-app", action="store_true")
    parser.add_argument("--app", default=str(PROJECT_ROOT / "output" / "content-shell-minimal" / "Content Shell.app"))
    parser.add_argument("--app-arg", action="append", default=[])
    args = parser.parse_args()

    server = http.server.ThreadingHTTPServer((args.host, args.port), DiagnosticHandler)
    server.report_dir = args.report_dir
    url = "http://%s:%d/" % (args.host, args.port)

    print("Fingerprint diagnostic server: %s" % url)
    print("Report directory: %s" % pathlib.Path(args.report_dir).resolve())
    if args.open_app:
        if not os.path.isdir(args.app):
            print("Content Shell app not found: %s" % args.app, file=sys.stderr)
            server.server_close()
            return 1
        open_content_shell(args.app, url, args.app_arg)
        print("Opened app: %s" % args.app)
    print("Press Ctrl-C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
