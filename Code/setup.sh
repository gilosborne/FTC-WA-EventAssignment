#!/usr/bin/env bash
# Basic setup: create .data/ and build the zip table for the states in sorter.toml.
# This runs automatically on fresh Codespaces (devcontainer postCreateCommand).
# For drive-time mode, run tools/enable_drive_times.sh after this.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "=== Setting up team sorter ==="

mkdir -p .data

if python3 tools/build_zip_table.py; then
    echo "✓ Zip table built for the states in sorter.toml"
elif [ -f reference/wa_zips.csv ]; then
    # Offline fallback: the committed table only covers Washington.
    cp reference/wa_zips.csv .data/zips.csv
    echo "⚠️  Could not build the zip table (no network?). Using reference/wa_zips.csv,"
    echo "   which covers Washington only. Teams in other states will be flagged."
    echo "   Rerun 'bash setup.sh' once you are online."
else
    echo "✗ Could not build the zip table and reference/wa_zips.csv is missing." >&2
    exit 1
fi

echo ""
echo "✓ Setup complete! The sorter is ready in straight-line mode."
echo ""
echo "Quick start:"
echo "  python3 -m sorter.cli        (settings are in sorter.toml)"
echo ""
echo "To enable drive-time mode (optional, requires OSRM):"
echo "  bash tools/enable_drive_times.sh"
