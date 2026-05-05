from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.services.parser import parse_docx
from app.services.validator import validate_apa, validate_apa_docx_path
from app.services.fixer import fix_apa_format

router = APIRouter(prefix="/documents", tags=["documents"])

BASE_STORAGE_DIR = Path("storage")
UPLOADS_DIR = BASE_STORAGE_DIR / "uploads"
FIXED_DIR = BASE_STORAGE_DIR / "fixed"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
FIXED_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    template_id: str = Form(...)
):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")

    document_id = str(uuid4())
    input_path = UPLOADS_DIR / f"{document_id}.docx"

    with open(input_path, "wb") as f:
        f.write(await file.read())

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
    template_id: str = Form(...)
):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")

    document_id = str(uuid4())
    input_path = UPLOADS_DIR / f"{document_id}.docx"
    output_path = FIXED_DIR / f"{document_id}_fixed.docx"

    with open(input_path, "wb") as f:
        f.write(await file.read())

    fixed_counts = fix_apa_format(str(input_path), str(output_path))
    validation_after_fix = validate_apa_docx_path(str(output_path))

    return {
        "document_id": document_id,
        "filename": file.filename,
        "template": template_id,
        "fixed_file_path": str(output_path),
        "download_url": f"/documents/download/{document_id}",
        "fixed_counts": fixed_counts,
        "validation_after_fix": validation_after_fix,
    }


@router.get("/download/{document_id}")
async def download_fixed_document(document_id: str):
    output_path = FIXED_DIR / f"{document_id}_fixed.docx"

    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Fixed document not found.")

    return FileResponse(
        path=str(output_path),
        filename=output_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
