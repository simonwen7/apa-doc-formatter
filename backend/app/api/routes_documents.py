from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

from app.api.auth_deps import AuthenticatedUser
from app.api.deps import require_authenticated_user
from app.apa.engine.analyzer import analyze_document_path
from app.apa.engine.fixer import fix_document_path
from app.core.config import DOCX_MEDIA_TYPE
from app.services.document_store import (
    load_fixed_document,
    save_fixed_document,
    temp_fixed_path,
    write_temp_upload,
)
from app.services.download_auth import (
    make_download_token,
    validate_document_id,
    validate_docx_upload,
    verify_download_token,
)
from app.services.parser import parse_docx
from app.services.vercel_oidc import extract_vercel_oidc_token

router = APIRouter(prefix="/documents", tags=["documents"])

_PRIVATE_DOWNLOAD_HEADERS = {
    "Cache-Control": "private, no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
}


@router.post("/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    template_id: str = Form(...),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    content = await file.read()
    validate_docx_upload(filename=file.filename, content=content)

    document_id = str(uuid4())
    input_path = write_temp_upload(document_id, content)

    try:
        parsed = parse_docx(str(input_path))
        analysis = analyze_document_path(str(input_path), template_id=template_id)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to read this .docx file. It may be corrupt or unsupported.",
        ) from None

    api_payload = analysis.to_api_dict()

    docx_validation = {
        "summary": {
            **api_payload["summary"],
            "role_counts": {},
            "table_count": parsed.get("table_count", 0),
        },
        "issues": api_payload["issues"],
    }

    return {
        "document_id": document_id,
        "filename": file.filename,
        "template": template_id,
        "template_id": template_id,
        "summary": api_payload["summary"],
        "issues": api_payload["issues"],
        "safe_auto_fix": api_payload["safe_auto_fix"],
        "author_action_required": api_payload["author_action_required"],
        "uncertain": api_payload["uncertain"],
        "unsupported": api_payload["unsupported"],
        "parsed_result": parsed,
        "parsed_validation": {
            "summary": api_payload["summary"],
            "issues": [],
        },
        "docx_validation": docx_validation,
    }


@router.post("/fix")
async def fix_document(
    request: Request,
    file: UploadFile = File(...),
    template_id: str = Form(...),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    content = await file.read()
    validate_docx_upload(filename=file.filename, content=content)

    document_id = str(uuid4())
    input_path = write_temp_upload(document_id, content)
    output_path = temp_fixed_path(current_user.user_id, document_id)

    try:
        fix_result = fix_document_path(
            str(input_path),
            str(output_path),
            template_id=template_id,
        )
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to format this .docx file. The original upload was not changed.",
        ) from None

    persisted_path = save_fixed_document(
        current_user.user_id,
        document_id,
        output_path,
        oidc_token=extract_vercel_oidc_token(request),
    )

    analysis_after = analyze_document_path(str(output_path), template_id=template_id)
    api_after = analysis_after.to_api_dict()

    verification = fix_result.get("verification") or {}
    preservation = fix_result.get("preservation") or {}
    download_token = make_download_token(
        user_id=current_user.user_id,
        document_id=document_id,
    )

    return {
        "document_id": document_id,
        "filename": file.filename,
        "template": template_id,
        # Logical storage key only — never expose host filesystem / Blob URLs.
        "fixed_file_path": persisted_path,
        "download_url": f"/documents/download/{document_id}?token={download_token}",
        "fixed_counts": fix_result["fixed_counts"],
        "validation_after_fix": {
            "summary": api_after["summary"],
            "issues": api_after["issues"],
            "safe_auto_fix": api_after["safe_auto_fix"],
            "author_action_required": api_after["author_action_required"],
            "uncertain": api_after["uncertain"],
            "unsupported": api_after["unsupported"],
            "template_id": api_after["template_id"],
        },
        "verification": {
            **verification,
            "text_integrity_ok": verification.get("text_integrity_ok", True),
            "document_preservation_ok": verification.get(
                "document_preservation_ok",
                preservation.get("document_preservation_ok", True),
            ),
            "safe_issues_before": verification.get("safe_issues_before"),
            "safe_issues_after": verification.get("safe_issues_after"),
            "author_action_issues": verification.get("author_action_issues"),
            "verified": verification.get("verified"),
        },
        "preservation": preservation,
        "safe_auto_fix_after": fix_result["safe_auto_fix_after"],
        "author_action_required": fix_result["author_action_required"],
        "engine": fix_result["engine"],
    }


@router.get("/download/{document_id}")
async def download_fixed_document(
    request: Request,
    document_id: str,
    token: str | None = Query(default=None),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    """
    Download requires:
    1) verified Supabase user (Bearer)
    2) owner-scoped storage lookup
    3) user-bound expiring HMAC token (defense in depth)
    """
    validate_document_id(document_id)
    verify_download_token(
        user_id=current_user.user_id,
        document_id=document_id,
        token=token,
    )
    content, filename = load_fixed_document(
        current_user.user_id,
        document_id,
        oidc_token=extract_vercel_oidc_token(request),
    )

    return Response(
        content=content,
        media_type=DOCX_MEDIA_TYPE,
        headers={
            **_PRIVATE_DOWNLOAD_HEADERS,
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
