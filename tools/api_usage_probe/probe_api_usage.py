#!/usr/bin/env python3
"""
Attach to a Chrome-DevTools-Protocol target (real Chrome OR content_shell,
both speak the same protocol), inject instrument.js before any page script
runs, drive it to a URL, and dump a log of which fingerprinting-relevant
Web APIs got touched -- plus the exact headers of the "sensor" request
(default: anything matching microsummary/recaptcha/akam/).

Usage:
    pip install requests websocket-client
    python3 probe_api_usage.py --port 9223 --url "https://www.royalmail.com/track-your-item#/tracking-results/JV768816105GB" \
        --out real_chrome_hits.json --timeout 25

Launch the browser first with --remote-debugging-port=9223 (see README notes
printed at the bottom of this file's --help).
"""
import argparse
import json
import os
import sys
import time

import requests
import websocket  # pip install websocket-client


def get_ws_url(port, start_url):
    # Create a fresh, blank tab so our instrumentation script is guaranteed to
    # be registered before the real navigation happens.
    r = requests.put(f"http://127.0.0.1:{port}/json/new?about:blank", timeout=5)
    r.raise_for_status()
    return r.json()["webSocketDebuggerUrl"]


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=30)
        self._id = 0

    def send(self, method, params=None):
        self._id += 1
        msg_id = self._id
        self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        return msg_id

    def recv_until(self, want_id=None, matcher=None, overall_timeout=30):
        """Read messages until one matches `want_id` (a command response) or
        `matcher(msg)` returns True (an event). Returns that message. Also
        yields other messages to caller via return value list if needed."""
        deadline = time.time() + overall_timeout
        self.ws.settimeout(1.0)
        while time.time() < deadline:
            try:
                raw = self.ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            if not raw:
                continue
            msg = json.loads(raw)
            if want_id is not None and msg.get("id") == want_id:
                return msg
            if matcher is not None and matcher(msg):
                return msg
        return None

    def call(self, method, params=None, timeout=30):
        msg_id = self.send(method, params)
        resp = self.recv_until(want_id=msg_id, overall_timeout=timeout)
        if resp is None:
            raise TimeoutError(f"no response for {method}")
        if "error" in resp:
            raise RuntimeError(f"{method} failed: {resp['error']}")
        return resp.get("result", {})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, required=True, help="--remote-debugging-port used to launch the browser")
    ap.add_argument("--url", required=True, help="page URL to navigate to")
    ap.add_argument("--out", required=True, help="output JSON path for the captured API-hit log")
    ap.add_argument("--timeout", type=int, default=25, help="seconds to wait for the sensor request before dumping")
    ap.add_argument("--script", default=os.path.join(os.path.dirname(__file__), "instrument.js"))
    args = ap.parse_args()

    with open(args.script) as f:
        instrument_source = f.read()

    ws_url = get_ws_url(args.port, args.url)
    cdp = CDP(ws_url)

    cdp.call("Page.enable")
    cdp.call("Network.enable")
    cdp.call("Runtime.enable")
    # Registers the script to run on every new document in this target,
    # BEFORE any other page script -- this is what makes the instrumentation
    # observe the sensor's real behavior instead of racing it.
    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": instrument_source})

    print(f"[+] navigating to {args.url}")
    cdp.send("Page.navigate", {"url": args.url})

    sensor_seen = {"hit": False}

    def is_sensor_event(msg):
        if msg.get("method") != "Network.requestWillBeSent":
            return False
        url = msg.get("params", {}).get("request", {}).get("url", "")
        import re
        if re.search(r"microsummary|recaptcha|akam/", url, re.I):
            sensor_seen["hit"] = True
            sensor_seen["url"] = url
            sensor_seen["headers"] = msg["params"]["request"].get("headers", {})
            return True
        return False

    print(f"[+] waiting up to {args.timeout}s for a sensor-tagged request (microsummary/recaptcha/akam/)...")
    cdp.recv_until(matcher=is_sensor_event, overall_timeout=args.timeout)

    if sensor_seen["hit"]:
        print(f"[+] sensor request seen: {sensor_seen['url']}")
        for k, v in sensor_seen["headers"].items():
            shown = v if len(v) < 80 else v[:77] + "..."
            print(f"      {k}: {shown}")
    else:
        print("[!] no sensor-tagged request observed within timeout -- dumping whatever was collected anyway")

    result = cdp.call("Runtime.evaluate", {
        "expression": "JSON.stringify({full: window.__apiHits||[], atSensorRequest: window.__apiHitsAtSensorRequest||null, sensorUrl: window.__sensorRequestUrl||null})",
        "returnByValue": True,
    })
    payload = json.loads(result["result"]["value"])
    payload["sensorRequestHeaders"] = sensor_seen.get("headers")
    payload["sensorRequestUrlFromNetwork"] = sensor_seen.get("url")

    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)

    counts = {}
    for hit in payload["full"]:
        counts[hit["name"]] = counts.get(hit["name"], 0) + 1
    print(f"[+] wrote {args.out} -- {len(payload['full'])} total API hits, {len(counts)} distinct APIs")
    for name, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"      {c:4d}  {name}")


if __name__ == "__main__":
    main()
