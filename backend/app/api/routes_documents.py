from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.apa.engine.analyzer import analyze_document_path
from app.apa.engine.fixer import fix_document_path
from app.core.config import DOCX_MEDIA_TYPE
from app.services.document_store import (
    load_fixed_document,
    save_fixed_document,
    temp_fixed_path,
    write_temp_upload,
)
from app.services.parser import parse_docx

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    template_id: str = Form(...),
):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")

    document_id = str(uuid4())
    content = await file.read()
    input_path = write_temp_upload(document_id, content)

    parsed = parse_docx(str(input_path))
    analysis = analyze_document_path(str(input_path), template_id=template_id)
    api_payload = analysis.to_api_dict()

    # Compatibility: previous clients expected docx_validation/parsed_validation.
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
    file: UploadFile = File(...),
    template_id: str = Form(...),
):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")

    document_id = str(uuid4())
    content = await file.read()
    input_path = write_temp_upload(document_id, content)
    output_path = temp_fixed_path(document_id)

    fix_result = fix_document_path(
        str(input_path),
        str(output_path),
        template_id=template_id,
    )
    persisted_path = save_fixed_document(document_id, output_path)

    analysis_after = analyze_document_path(str(output_path), template_id=template_id)
    api_after = analysis_after.to_api_dict()

    verification = fix_result.get("verification") or {}
    preservation = fix_result.get("preservation") or {}

    return {
        "document_id": document_id,
        "filename": file.filename,
        "template": template_id,
        "fixed_file_path": persisted_path,
        "download_url": f"/documents/download/{document_id}",
        "fixed_counts": fix_result["fixed_counts"],
        # Legacy-compatible shape retained.
        "validation_after_fix": {
            "summary": api_after["summary"],
            "issues": api_after["issues"],
            # Additive full schema (shared with Analyze).
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
async def download_fixed_document(document_id: str):
    content, filename = load_fixed_document(document_id)

    return Response(
        content=content,
        media_type=DOCX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
