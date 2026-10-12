#!/bin/sh
set -eu

base_url="${1:-http://localhost:8080}"
repo_dir="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

curl -fsS "$base_url/health" | grep -q '"status":"ok"'
curl -fsS -X POST -F "file=@$repo_dir/examples/leads.csv;type=text/csv" "$base_url/api/imports" | grep -q '"total_rows":30'
curl -fsS "$base_url/api/leads?page=1&page_size=1" | grep -q '"total":30'
curl -fsS "$base_url/api/rankings?target=replied" | grep -q '"suggested_score"'

echo "Smoke test passed: health, import, persistence query, and rankings"
