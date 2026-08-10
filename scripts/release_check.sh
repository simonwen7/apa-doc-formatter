#!/usr/bin/env bash
# Forma APA release readiness check (Phase 3D).
# Verifies readiness only — does NOT deploy or push.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo "== Forma APA release check =="
echo "Root: $ROOT"

echo
echo "-- Git secret hygiene (tracked env files) --"
cd "$ROOT"
if git ls-files | grep -E '(^|/)\.env($|\.)' >/dev/null; then
  echo "BLOCKER: env files appear tracked by git"
  git ls-files | grep -E '(^|/)\.env($|\.)' || true
  exit 1
fi
echo "no_tracked_env_files_ok"

echo
echo "-- Backend: import app --"
cd "$BACKEND"
if [[ -f "$BACKEND/venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$BACKEND/venv/bin/activate"
fi
python -c "from app.main import app; print('app_ok', app.title if hasattr(app, 'title') else True)"

echo
echo "-- Backend: production secret + CORS policy (unit) --"
python - <<'PY'
from app.core import config as c
prev_prod = c.IS_PRODUCTION
prev_secret = c.DOCUMENT_DOWNLOAD_SECRET
try:
    c.IS_PRODUCTION = False
    c.DOCUMENT_DOWNLOAD_SECRET = None
    assert c.resolve_download_secret()
    c.IS_PRODUCTION = True
    c.DOCUMENT_DOWNLOAD_SECRET = None
    try:
        c.resolve_download_secret()
        raise SystemExit('expected production secret failure')
    except RuntimeError:
        pass
    try:
        c.parse_cors_origins('*')
        raise SystemExit('expected cors wildcard failure')
    except ValueError:
        print('production_secret_and_cors_policy_ok')
finally:
    c.IS_PRODUCTION = prev_prod
    c.DOCUMENT_DOWNLOAD_SECRET = prev_secret
PY

echo
echo "-- Backend: APA + auth/ownership/retention/ops tests --"
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
echo "Manual remaining gates: configure Vercel env + CRON_SECRET; logged-in E2E with backend Supabase vars."
