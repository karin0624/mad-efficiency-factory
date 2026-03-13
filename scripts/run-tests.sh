#!/usr/bin/env bash
set -euo pipefail

# GdUnit4 test runner — xvfb-run + X11 virtual display
# Usage: ./scripts/run-tests.sh [extra GdUnit4 args...]

if ! command -v xvfb-run &>/dev/null; then
  echo "ERROR: xvfb-run not found. Install it with:"
  echo "  sudo apt-get install -y xvfb"
  exit 1
fi

GODOT_BIN="${GODOT_BIN:-godot}"
PROJECT_DIR="$(cd "$(dirname "$0")/../godot" && pwd)"

xvfb-run --auto-servernum \
  "$GODOT_BIN" --display-driver x11 --rendering-driver opengl3 --audio-driver Dummy \
  --path "$PROJECT_DIR" \
  -s addons/gdUnit4/bin/GdUnitCmdTool.gd \
  --continue "$@"
