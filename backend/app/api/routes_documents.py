from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.core.config import DOCX_MEDIA_TYPE
from app.services.document_store import (
    load_fixed_document,
    save_fixed_document,
    temp_fixed_path,
    write_temp_upload,
)
from app.services.fixer import fix_apa_format
from app.services.parser import parse_docx
from app.services.validator import validate_apa, validate_apa_docx_path

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
    parsed_validation = validate_apa(parsed, template_id)
    docx_validation = validate_apa_docx_path(str(input_path))

    return {
        "document_id": document_id,
        "filename": file.filename,
        "template": template_id,
        "summary": docx_validation["summary"],
        "issues": docx_validation["issues"],
        "parsed_result": parsed,
        "parsed_validation": parsed_validation,
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

    fixed_counts = fix_apa_format(str(input_path), str(output_path))
    persisted_path = save_fixed_document(document_id, output_path)
    validation_after_fix = validate_apa_docx_path(str(output_path))

    return {
        "document_id": document_id,
        "filename": file.filename,
        "template": template_id,
        "fixed_file_path": persisted_path,
        "download_url": f"/documents/download/{document_id}",
        "fixed_counts": fixed_counts,
        "validation_after_fix": validation_after_fix,
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
