#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Build the read-only Mathlib workspace for the isolated worker's mathlib lane.
# Runs at IMAGE BUILD time (network allowed here, never inside the sandbox).
# The Mathlib rev is pinned to lutar-lean's lake-manifest.json so the lane checks
# lutar-lean benchmark statements against the same library they were written for.
# Needs roughly 6 GB and ~130k inodes.
set -euo pipefail
DEST="${1:?usage: setup_mathlib_workspace.sh <dest-dir>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
MATHLIB_REV="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["mathlib_rev"])' "$HERE/mathlib-pin.json")"
TOOLCHAIN="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["toolchain"])' "$HERE/mathlib-pin.json")"
mkdir -p "$DEST"
cd "$DEST"
printf '%s\n' "$TOOLCHAIN" > lean-toolchain
cat > lakefile.toml <<TOML
name = "szlMathlibReferee"
defaultTargets = []

[[require]]
name = "mathlib"
git = "https://github.com/leanprover-community/mathlib4"
rev = "$MATHLIB_REV"
TOML
lake update mathlib
lake exe cache get
test -f .lake/packages/mathlib/.lake/build/lib/lean/Mathlib.olean
echo "mathlib workspace ready at $DEST (rev $MATHLIB_REV)"
