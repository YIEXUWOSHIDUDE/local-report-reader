from __future__ import annotations

import shutil
import socket
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import bundled_resource_dir, get_settings
from .database import (
    get_comparison,
    get_report,
    init_db,
    insert_comparison,
    insert_report,
    list_reports,
    update_report_analysis,
)
from .services.analysis import AIAnalysisError, analyze_report, compare_reports
from .services.exporter import export_comparison_docx, export_report_docx
from .services.parser import parse_document


class CompareRequest(BaseModel):
    report_ids: list[int]


app = FastAPI(title="可研报告精读工具", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {"ok": True, "app": settings.app_name, "ai_configured": bool(settings.openai_api_key)}


@app.get("/api/access-info")
def access_info() -> dict[str, list[str]]:
    return {"local_ips": _local_ipv4_addresses()}


def _local_ipv4_addresses() -> list[str]:
    addresses: set[str] = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
            address = item[4][0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)


@app.post("/api/reports/upload")
async def upload_reports(files: Annotated[list[UploadFile], File(...)]) -> dict[str, list[dict]]:
    settings = get_settings()
    created: list[dict] = []
    for upload in files:
        safe_name = Path(upload.filename or "report").name
        stored_path = settings.uploads_dir / f"{uuid.uuid4().hex}-{safe_name}"
        with stored_path.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)

        parsed = parse_document(stored_path, safe_name)
        report_id = insert_report(
            {
                "filename": safe_name,
                "stored_path": str(stored_path),
                "mime_type": upload.content_type,
                "file_size": stored_path.stat().st_size,
                "status": "parsed" if parsed.text else "parse_failed",
                "language": parsed.language,
                "parser_notes": "；".join(parsed.notes),
                "extracted_text": parsed.text,
            }
        )
        report = get_report(report_id)
        if report:
            created.append(report)
    return {"reports": created}


@app.get("/api/reports")
def reports() -> dict[str, list[dict]]:
    return {"reports": list_reports()}


@app.get("/api/reports/{report_id}")
def report_detail(report_id: int) -> dict:
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.post("/api/reports/{report_id}/analyze")
async def analyze(report_id: int) -> dict:
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not report.get("extracted_text"):
        raise HTTPException(status_code=422, detail="No extracted text available")
    try:
        analysis = await analyze_report(report["filename"], report["extracted_text"], report.get("language", "unknown"))
    except AIAnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    update_report_analysis(report_id, analysis)
    updated = get_report(report_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Report not found")
    return updated


@app.post("/api/reports/compare")
async def compare(request: CompareRequest) -> dict:
    if len(request.report_ids) < 2:
        raise HTTPException(status_code=422, detail="At least two reports are required")
    selected = []
    for report_id in request.report_ids:
        report = get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
        selected.append(report)
    try:
        result = await compare_reports(selected)
    except AIAnalysisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    comparison_id = insert_comparison(request.report_ids, result)
    return {"id": comparison_id, "report_ids": request.report_ids, "result": result}


@app.get("/api/reports/{report_id}/export")
def export_report(report_id: int) -> FileResponse:
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    path = export_report_docx(report)
    return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.get("/api/comparisons/{comparison_id}/export")
def export_comparison(comparison_id: int) -> FileResponse:
    comparison = get_comparison(comparison_id)
    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")
    path = export_comparison_docx(comparison)
    return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


frontend_dist = bundled_resource_dir() / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
