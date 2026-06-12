#!/usr/bin/env bash
# Vendors the generated brand visuals into frontend/public/visuals/.
# Run once from repo root before building: bash scripts/fetch_visuals.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)/frontend/public/visuals"
mkdir -p "$DIR"
BASE="https://d8j0ntlcm91z4.cloudfront.net/user_3Ezu3FyVZgfmIrgb7Sj43rMkwMy"

fetch() { echo "→ $1"; curl -fsSL -o "$DIR/$1" "$BASE/$2"; }

# Template-styled visual set (light, teal, white-card medical UI style)
fetch "dashboard.png"           "hf_20260612_065229_684b377a-99c5-45a2-af53-672ed338f8c0.png"
fetch "feature-bayesian.png"    "hf_20260612_065302_ed5cc9ee-36c3-4eb4-8f7d-0ed56f629b5f.png"
fetch "feature-safety-gate.png" "hf_20260612_065332_dded8244-2673-4b72-a709-1abcb8fbeeee.png"
fetch "empty-state.png"         "hf_20260612_065422_6e64035b-186f-42c1-ae36-7badb858dc21.png"
# Dark hero (landing/marketing use)
fetch "hero-dark.png"           "hf_20260611_164030_5f7d0546-c01c-4369-8f3c-cbc0e321df45.png"

echo "Done. Visuals in $DIR"
