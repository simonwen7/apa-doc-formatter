# Forma APA — environment & deployment (Phase 3D)

Follow this document for local development, Vercel Preview, and Vercel Production.
Never put backend secrets in `VITE_` variables. Never commit `.env` files.

Accurate retention wording (matches implementation):

> Formatted documents are kept temporarily for download and become eligible for
> automatic deletion after the retention period (default 24 hours). On the Hobby
> deployment, deletion runs once daily, so removal happens on the next daily
> cleanup run and is not guaranteed exactly at 24 hours.

---

## A. Local development

### Frontend (`frontend/.env.local`) — browser-visible

| Variable | Required | Secret? | Notes |
|----------|----------|---------|-------|
| `VITE_SUPABASE_URL` | Yes | No | Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Yes | No | Publishable/anon key |
| `VITE_API_BASE_URL` | Recommended | No | `http://127.0.0.1:8000` when API is separate |

### Backend (`backend/.env` — not committed)

| Variable | Required | Secret? | Notes |
|----------|----------|---------|-------|
| `SUPABASE_URL` | Yes for real auth | No | Same project as frontend |
| `SUPABASE_ANON_KEY` **or** `SUPABASE_PUBLISHABLE_KEY` | Yes for real auth | No* | Publishable/anon key for `get_claims` (*treat as sensitive in shared logs) |
| `DOCUMENT_DOWNLOAD_SECRET` | Optional locally | Yes | If unset, local-only fallback secret is used |
| `DOCUMENT_DOWNLOAD_TOKEN_TTL_SECONDS` | Optional | No | Default `3600` |
| `DOCUMENT_RETENTION_HOURS` | Optional | No | Default `24` |
| `CRON_SECRET` / `CLEANUP_JOB_SECRET` | Optional locally | Yes | Needed only to exercise cleanup endpoint |
| `CORS_ALLOWED_ORIGINS` | Optional | No | Defaults include `http://localhost:5173` and `http://127.0.0.1:5173` |

Blob variables are not required locally (`USE_BLOB_STORAGE` is false unless `VERCEL=1`).

### Local verification

1. Start backend: `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
2. Start frontend: `npm run dev`
3. Sign in → Analyze → Fix → Download
4. Confirm requests include `Authorization: Bearer …` (do not copy the token)

---

## B. Vercel Preview

### Frontend

| Variable | Preview | Secret? |
|----------|---------|---------|
| `VITE_SUPABASE_URL` | Yes | No |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Yes | No |
| `VITE_API_BASE_URL` | Usually empty (same-origin rewrites) | No |

### Backend

| Variable | Preview | Secret? | Format / shape |
|----------|---------|---------|----------------|
| `SUPABASE_URL` | Yes | No | `https://<project>.supabase.co` |
| `SUPABASE_ANON_KEY` or `SUPABASE_PUBLISHABLE_KEY` | Yes | No* | JWT-like publishable key |
| `DOCUMENT_DOWNLOAD_SECRET` | Recommended | Yes | ≥32 random chars |
| `CRON_SECRET` | Yes if cron enabled | Yes | ≥16 random chars (official Vercel Cron auth) |
| `CLEANUP_JOB_SECRET` | Optional | Yes | Manual cleanup header; may equal `CRON_SECRET` |
| `CORS_ALLOWED_ORIGINS` | Yes | No | Comma-separated absolute origins including Preview URL(s) |
| `BLOB_STORE_ID` or `VERCEL_BLOB_STORE_ID` | Yes | No | Private Blob store id |
| `BLOB_READ_WRITE_TOKEN` | Optional | Yes | Prefer OIDC on Vercel |
| `DOCUMENT_DOWNLOAD_TOKEN_TTL_SECONDS` | Optional | No | Default 3600 |
| `DOCUMENT_RETENTION_HOURS` | Optional | No | Default 24 |
| `VERCEL` | Injected | — | Platform sets `1` |
| `VERCEL_OIDC_TOKEN` | Injected when OIDC enabled | — | Short-lived |

`vercel.json` declares a once-daily cron (Hobby-compatible): `0 5 * * *` (05:00 UTC)
→ `GET /internal/cleanup-fixed-documents`.

---

## C. Vercel Production

Same as Preview, with:

- Production frontend origin in `CORS_ALLOWED_ORIGINS` (never `*`)
- `DOCUMENT_DOWNLOAD_SECRET` **required** (≥32)
- `CRON_SECRET` **required** for scheduled cleanup
- Private Blob store connected; OIDC preferred
- Confirm rewrite `/internal/(.*)` → backend (already in `vercel.json`)

### Cleanup architecture

1. Vercel Cron hits `GET /internal/cleanup-fixed-documents` once daily at 05:00 UTC (`0 5 * * *`), which is within Hobby plan limits (at most once per day).
2. Vercel sends `Authorization: Bearer <CRON_SECRET>` automatically when `CRON_SECRET` is set.
3. Endpoint deletes only `fixed/{user_id}/{document_id}.docx` (+ meta) older than `DOCUMENT_RETENTION_HOURS`.
4. Manual ops: `POST` same path with `X-Cleanup-Secret: <CLEANUP_JOB_SECRET|CRON_SECRET>`.

### Retention semantics

`DOCUMENT_RETENTION_HOURS` defaults to **24**. A document becomes **eligible** for deletion after that period, but on the Hobby deployment it is deleted only on the **next daily cleanup run**. Deletion is therefore not guaranteed exactly at 24 hours and may occur later depending on when the next scheduled cron executes.

---

## Secret generation (run locally; do not paste into chat)

```bash
openssl rand -hex 32   # DOCUMENT_DOWNLOAD_SECRET
openssl rand -hex 32   # CRON_SECRET (and optional CLEANUP_JOB_SECRET)
```

---

## Pre-deploy checklist

See Phase 3D report / `PRE-DEPLOY CHECKLIST` section.
