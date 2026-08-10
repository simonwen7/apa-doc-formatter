# Forma APA — production / preview environment (Phase 3C)

This document lists backend and frontend variables required for a controlled beta.
Do **not** put backend secrets in `VITE_` variables.

## Frontend (Vercel / `.env.local`)

| Variable | Required | Notes |
|----------|----------|-------|
| `VITE_SUPABASE_URL` | Yes | Supabase project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Yes | Publishable/anon key for browser client |
| `VITE_API_BASE_URL` | Preview/local | Empty in same-origin production; `http://127.0.0.1:8000` locally |

## Backend (Vercel Function env)

| Variable | Required | Notes |
|----------|----------|-------|
| `SUPABASE_URL` | Yes | Same project URL as frontend (no `VITE_` prefix) |
| `SUPABASE_ANON_KEY` or `SUPABASE_PUBLISHABLE_KEY` | Yes | Publishable/anon key for `auth.get_claims` verification |
| `DOCUMENT_DOWNLOAD_SECRET` | Yes (prod/preview) | ≥32 chars. Generate: `openssl rand -hex 32`. **No insecure fallback in production.** |
| `DOCUMENT_DOWNLOAD_TOKEN_TTL_SECONDS` | Optional | Default `3600` (1 hour) |
| `DOCUMENT_RETENTION_HOURS` | Optional | Default `24` |
| `CLEANUP_JOB_SECRET` | Yes for cleanup cron | Shared secret for `POST /internal/cleanup-fixed-documents` via `X-Cleanup-Secret` |
| `CORS_ALLOWED_ORIGINS` | Recommended | Comma-separated SPA origins (include production domain + localhost for preview as needed) |
| `BLOB_STORE_ID` / `VERCEL_BLOB_STORE_ID` | Yes on Vercel | Private Blob store |
| `BLOB_READ_WRITE_TOKEN` | Optional | Prefer OIDC on Vercel; RW token fallback if needed |
| `VERCEL` | Platform | Set automatically on Vercel |

## Cleanup cron (manual configuration — not auto-deployed)

1. Set `CLEANUP_JOB_SECRET` in Vercel.
2. Add a Vercel Cron (or external scheduler) that `POST`s:

   `https://<your-api>/internal/cleanup-fixed-documents`

   with header: `X-Cleanup-Secret: <CLEANUP_JOB_SECRET>`

3. Suggested cadence: hourly or daily.
4. Cleanup only deletes `fixed/{user_id}/{document_id}.docx` (+ meta) older than `DOCUMENT_RETENTION_HOURS`.

## Auth model summary

- Frontend sends `Authorization: Bearer <Supabase access_token>`.
- Backend verifies with official `supabase.auth.get_claims(jwt=...)`.
- Fixed files stored at `fixed/{user_id}/{document_id}.docx`.
- Download requires Bearer ownership **and** short-lived user-bound HMAC token.
