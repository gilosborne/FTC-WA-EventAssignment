#!/usr/bin/env bash
# Enable drive-time mode by setting up OSRM and building the drive matrix.
# This is optional - the sorter works in straight-line mode without it.
#
# Covers the states in sorter.toml. Requirements:
#   - Docker (on Linux/Codespaces) or Homebrew osrm-backend (on macOS)
#   - osmium-tool when sorter.toml lists more than one state (the devcontainer installs it)
#   - About 2 GB disk per state for map data and the routing graph
#   - RAM: the graph build peaked at 4.7 GB for Washington alone; more states need more
#
# Usage: bash tools/enable_drive_times.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Enabling Drive-Time Mode for $(python3 tools/region.py states) ==="
echo ""

# Check for teams/events files
if [ ! -f .data/teams.csv ] || [ ! -f .data/events.csv ]; then
    echo "Error: Missing .data/teams.csv or .data/events.csv" >&2
    echo "Place your team and event data in .data/ first." >&2
    exit 1
fi
if [ ! -f .data/zips.csv ]; then
    echo "Error: Missing .data/zips.csv. Run 'bash setup.sh' first." >&2
    exit 1
fi

# Check resources
CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "unknown")
if [ "$CORES" != "unknown" ] && [ "$CORES" -lt 4 ]; then
    echo "⚠️  Warning: Running on a ${CORES}-core machine"
    echo "The OSRM graph build may run out of memory on 8 GB, especially for more than one state."
    echo "A larger Codespace costs more; see CODESPACES.md before changing machine type."
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

# Run OSRM setup
echo "Step 1/2: Setting up OSRM routing engine..."
if ! bash tools/osrm_setup.sh; then
    echo "Error: OSRM setup failed" >&2
    exit 1
fi

echo ""
echo "Step 2/2: Building drive-time matrix..."
if ! python3 tools/build_drive_matrix.py --source osrm; then
    echo "Error: Drive matrix build failed" >&2
    exit 1
fi

echo ""
echo "✓ Drive-time mode enabled!"
echo ""
echo "The sorter will now use drive minutes instead of straight-line miles."
echo "Re-run your sorting command:"
echo "  python3 -m sorter.cli        (settings are in sorter.toml)"
