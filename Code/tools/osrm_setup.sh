#!/usr/bin/env bash
# Build and start a self-hosted OSRM server for the states in sorter.toml, the
# drive-time source for tools/build_drive_matrix.py. Works on macOS (Homebrew) and
# on Linux / GitHub Codespaces (Docker, using the official ghcr.io/project-osrm/osrm-backend
# image). Nothing leaves the machine except the public map downloads from Geofabrik.
#
# Each state's Geofabrik extract is downloaded, and more than one state is merged with
# osmium into a single routing graph, so cross-border trips (Vancouver to Portland) exist.
#
# Memory: osrm-extract peaked at 4.7 GB on Washington alone. More states need more.
# In Codespaces, a 2-core (8 GB) machine is borderline even for one state; see
# CODESPACES.md before choosing a larger machine, which costs more.
#
# Usage: tools/osrm_setup.sh            build if needed, then serve on 127.0.0.1:5055
#        OSRM_DIR=/some/path tools/osrm_setup.sh
# Stop the server: kill "$(cat "$OSRM_DIR/routed.pid")" (macOS) or docker stop osrm-<tag> (Linux),
# where <tag> is printed by: python3 tools/region.py tag
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAG="$(python3 "$REPO_ROOT/tools/region.py" tag)"
STATES="$(python3 "$REPO_ROOT/tools/region.py" states)"
URLS=()
while IFS= read -r url; do URLS+=("$url"); done < <(python3 "$REPO_ROOT/tools/region.py" urls)

OSRM_DIR="${OSRM_DIR:-$HOME/.cache/osrm-$TAG}"   # not /tmp: macOS can clear /tmp on reboot
PORT="${OSRM_PORT:-5055}"
IMAGE="ghcr.io/project-osrm/osrm-backend"
CONTAINER="osrm-$TAG"
mkdir -p "$OSRM_DIR"
cd "$OSRM_DIR"
echo "Region: $STATES (build directory $OSRM_DIR)"

if [[ "$(uname)" == "Darwin" ]]; then
  command -v osrm-routed >/dev/null || brew install osrm-backend
  PROFILE="$(brew --prefix osrm-backend)/share/osrm/profiles/car.lua"
  run() { "$@"; }
  DATA="."
else
  command -v docker >/dev/null || { echo "Docker is required on Linux. In Codespaces, add the docker-in-docker feature (see .devcontainer/devcontainer.json)."; exit 1; }
  PROFILE="/opt/car.lua"
  run() { docker run --rm -t -v "$OSRM_DIR:/data" "$IMAGE" "$@"; }
  DATA="/data"
fi

PARTS=()
for url in "${URLS[@]}"; do
  part="$(basename "$url")"
  if [[ ! -f "$part" ]]; then
    echo "Downloading $part ..."
    curl -fL -o "$part.download" "$url"
    mv "$part.download" "$part"
  fi
  PARTS+=("$part")
done

if [[ ! -f region.osm.pbf ]]; then
  if [[ ${#PARTS[@]} -eq 1 ]]; then
    cp "${PARTS[0]}" region.osm.pbf
  else
    if ! command -v osmium >/dev/null; then
      echo "Installing osmium-tool to merge the state extracts..."
      if [[ "$(uname)" == "Darwin" ]]; then brew install osmium-tool
      else sudo apt-get update -qq && sudo apt-get install -y -qq osmium-tool; fi
    fi
    echo "Merging ${#PARTS[@]} state extracts..."
    osmium merge "${PARTS[@]}" -o region.osm.pbf
  fi
fi

if [[ ! -f region.osrm.mldgr ]]; then
  echo "Building the routing graph (several minutes per state)..."
  run osrm-extract -p "$PROFILE" "$DATA/region.osm.pbf" > extract.log 2>&1
  run osrm-partition "$DATA/region.osrm" > mld.log 2>&1
  run osrm-customize "$DATA/region.osrm" >> mld.log 2>&1
fi

echo "Starting OSRM on 127.0.0.1:$PORT ..."
if [[ "$(uname)" == "Darwin" ]]; then
  if [[ -f routed.pid ]] && kill -0 "$(cat routed.pid)" 2>/dev/null; then kill "$(cat routed.pid)"; fi
  nohup osrm-routed --algorithm mld -i 127.0.0.1 -p "$PORT" --max-table-size 2000 region.osrm > routed.log 2>&1 &
  echo $! > routed.pid
else
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  docker run -d --name "$CONTAINER" -p "127.0.0.1:$PORT:5000" -v "$OSRM_DIR:/data" "$IMAGE" \
    osrm-routed --algorithm mld --max-table-size 2000 /data/region.osrm > /dev/null
fi

for _ in $(seq 1 60); do
  if curl -fs "http://127.0.0.1:$PORT/nearest/v1/driving/-122.33,47.6" > /dev/null; then
    echo "OSRM is up for $STATES. Next: python3 tools/build_drive_matrix.py --source osrm"
    exit 0
  fi
  sleep 2
done
echo "OSRM did not answer within 2 minutes. Check $OSRM_DIR/routed.log or: docker logs $CONTAINER"
exit 1
