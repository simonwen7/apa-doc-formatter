from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_documents import router as documents_router
from app.api.routes_internal import router as internal_router
from app.core.config import CORS_ALLOWED_ORIGINS

app = FastAPI(
    title="DOC Formatter API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    # Authorization must be explicitly allowed for authenticated SPA calls.
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Cleanup-Secret"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def register_vercel_request_headers(request: Request, call_next):
    """
    Expose incoming Vercel request headers (including x-vercel-oidc-token)
    to vercel.oidc helpers for on-platform Blob authentication.
    """
    try:
        from vercel.headers import set_headers

        set_headers({key.lower(): value for key, value in request.headers.items()})
    except Exception:
        # Local / non-Vercel environments may not have the helper wired; ignore.
        pass

    return await call_next(request)


app.include_router(documents_router)
app.include_router(internal_router)
