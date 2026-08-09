from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_documents import router as documents_router

app = FastAPI(
    title="DOC Formatter API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
