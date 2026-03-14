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

# WSLg prevents xvfb-run from being truly headless — it intercepts X11/Wayland
# and renders real windows. Unsetting these variables forces Godot to use only
# the virtual display created by xvfb-run.
unset WAYLAND_DISPLAY 2>/dev/null || true
unset XDG_RUNTIME_DIR 2>/dev/null || true

xvfb-run --auto-servernum \
  "$GODOT_BIN" --display-driver x11 --rendering-driver opengl3 --audio-driver Dummy \
  --path "$PROJECT_DIR" \
  -s addons/gdUnit4/bin/GdUnitCmdTool.gd \
  --continue "$@"
