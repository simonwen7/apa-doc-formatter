#!/usr/bin/env bash
# Forma APA release readiness check (Phase 3B).
# Verifies readiness only — does NOT deploy or push.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo "== Forma APA release check =="
echo "Root: $ROOT"

echo
echo "-- Backend: import app --"
cd "$BACKEND"
# Prefer project venv when present.
if [[ -f "$BACKEND/venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$BACKEND/venv/bin/activate"
fi
python -c "from app.main import app; print('app_ok', app.title if hasattr(app, 'title') else True)"

echo
echo "-- Backend: APA + release safety tests --"
python -m pytest tests/apa -q

echo
echo "-- Frontend: unit tests --"
cd "$FRONTEND"
npm test

echo
echo "-- Frontend: lint --"
npm run lint

echo
echo "-- Frontend: production build --"
npm run build

echo
echo "== Release check PASSED =="
echo "Manual remaining gates: real browser auth/upload flows, production secrets review."
