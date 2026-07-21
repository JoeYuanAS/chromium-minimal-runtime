#!/usr/bin/env python3
"""
Diff two API-hit logs produced by probe_api_usage.py (e.g. one from real
Chrome, one from content_shell) and report which fingerprinting-relevant
APIs were touched differently before the sensor-tagged request fired.

Usage:
    python3 diff_api_hits.py real_chrome_hits.json content_shell_hits.json
"""
import argparse
import json


def counts(payload, key):
    hits = payload.get(key) or []
    c = {}
    for h in hits:
        c[h["name"]] = c.get(h["name"], 0) + 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a", help="baseline (e.g. real Chrome) hits json")
    ap.add_argument("b", help="candidate (e.g. content_shell) hits json")
    ap.add_argument("--key", default="atSensorRequest",
                    help="'atSensorRequest' (hits before the sensor request fired, default) or 'full' (whole page lifetime)")
    args = ap.parse_args()

    with open(args.a) as f:
        pa = json.load(f)
    with open(args.b) as f:
        pb = json.load(f)

    key = args.key
    if not pa.get(key):
        print(f"[!] {args.a} has no '{key}' data (sensor request maybe not observed) -- falling back to 'full'")
        key = "full"
    if not pb.get(key):
        print(f"[!] {args.b} has no '{key}' data (sensor request maybe not observed) -- falling back to 'full'")
        key = "full"

    ca, cb = counts(pa, key), counts(pb, key)
    all_names = sorted(set(ca) | set(cb))

    print(f"comparing '{key}' -- A={args.a}  B={args.b}\n")
    print(f"{'API':45s} {'A count':>8s} {'B count':>8s}  diff")
    only_a, only_b, diff_count = [], [], []
    for name in all_names:
        na, nb = ca.get(name, 0), cb.get(name, 0)
        marker = ""
        if na and not nb:
            only_a.append(name)
            marker = "  <-- A only (B never touched this)"
        elif nb and not na:
            only_b.append(name)
            marker = "  <-- B only"
        elif na != nb:
            diff_count.append(name)
            marker = "  <-- count differs"
        print(f"{name:45s} {na:8d} {nb:8d}{marker}")

    print("\n=== summary ===")
    print(f"APIs only touched in A ({args.a}): {only_a or '(none)'}")
    print(f"APIs only touched in B ({args.b}): {only_b or '(none)'}")
    print(f"APIs touched in both but different call counts: {diff_count or '(none)'}")

    if pa.get("sensorRequestHeaders") and pb.get("sensorRequestHeaders"):
        ha, hb = pa["sensorRequestHeaders"], pb["sensorRequestHeaders"]
        print("\n=== sensor request header presence diff ===")
        keys = sorted(set(ha) | set(hb))
        for k in keys:
            va, vb = ha.get(k), hb.get(k)
            if (va is None) != (vb is None):
                print(f"  {k}: A={'present' if va else 'MISSING'}  B={'present' if vb else 'MISSING'}")
            elif va != vb and k.lower() in ("x-rmg-recaptcha",):
                print(f"  {k}: lengths differ  A={len(va)}  B={len(vb)}")


if __name__ == "__main__":
    main()
