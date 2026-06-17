#!/usr/bin/env bash
set -e

OUT_DIR=${1:-out/CollectorRelease}

gn gen "$OUT_DIR"
autoninja -C "$OUT_DIR" content_shell
