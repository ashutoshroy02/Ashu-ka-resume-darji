"""
main.py — FastAPI wrapper around tailor.py's resume-tailoring pipeline.

Reuses tailor.py's functions directly (fetch_jd, analyze_jd, get_rewrites,
apply_changes, compile_latex, TEMPLATE_MAP) rather than duplicating any
logic — this file only adds the HTTP layer + auth + the one-page retry
loop (same loop that lives in tailor.py's main(), lifted here so the API
path doesn't need the CLI's argparse/main()).

Endpoints:
  GET  /health           liveness check for Render
  POST /tailor            { "jd": "<url or plain text>", "company": "optional" }
                           → returns the compiled PDF as a binary download

Auth: every /tailor request must include header  X-API-Key: <TAILOR_API_KEY>
"""

import os
import re
import uuid
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import tailor  # your existing tailor.py, imported as a module

app = FastAPI(title="Resume Tailor API")

TAILOR_API_KEY = os.getenv("TAILOR_API_KEY")
if not TAILOR_API_KEY:
    raise RuntimeError("❌ TAILOR_API_KEY not set — required to protect this endpoint")

MAX_PAGE_ATTEMPTS = 4


class TailorRequest(BaseModel):
    jd: str                       # job posting URL, or raw JD text pasted in
    company: Optional[str] = None  # optional override; auto-detected from URL/filename otherwise


def _check_api_key(x_api_key: Optional[str]):
    if x_api_key != TAILOR_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tailor")
def tailor_resume(req: TailorRequest, x_api_key: Optional[str] = Header(default=None)):
    """
    Runs the same pipeline as tailor.py's main(): fetch JD -> analyze ->
    rewrite (with one-page retry loop) -> compile -> return PDF bytes.

    Defined as a plain `def` (not `async def`) so FastAPI runs it in its
    threadpool — necessary because tailor.py's Playwright fetch and the
    pdflatex/tectonic subprocess calls are both blocking, synchronous calls.
    """
    _check_api_key(x_api_key)

    if not req.jd.strip():
        raise HTTPException(status_code=400, detail="`jd` is empty")

    # ── 1. Fetch JD (URL -> scrape+extract, else treated as raw JD text) ──
    # tailor.py's helpers call sys.exit() on unrecoverable errors (e.g. a
    # JD_NOT_FOUND page). We catch SystemExit here and convert it into a
    # proper HTTP error instead of letting it kill the whole server process.
    try:
        jd_text, company_auto = tailor.fetch_jd(req.jd)
    except SystemExit as e:
        raise HTTPException(status_code=422, detail=str(e))

    company      = req.company or company_auto
    company_slug = re.sub(r"[^a-zA-Z0-9]+", "-", company).strip("-").lower() or "company"

    # ── 2. Analyze JD -> archetype + keywords ──
    try:
        analysis = tailor.analyze_jd(jd_text)
    except SystemExit as e:
        raise HTTPException(status_code=502, detail=f"JD analysis failed: {e}")

    archetype     = analysis["role_archetype"]
    template_name = tailor.TEMPLATE_MAP.get(archetype, tailor.TEMPLATE_MAP["ML_AI"])

    tpl_path = tailor.TEMPLATES / template_name
    if not tpl_path.exists():
        raise HTTPException(status_code=500, detail=f"Template not found on server: {template_name}")
    tex_content = tpl_path.read_text(encoding="utf-8")

    # ── 3. Rewrite + compile, with one-page retry loop ──
    # Unique per-request stem (uuid) so concurrent requests never collide
    # on the same .tex/.pdf filename on disk.
    request_id  = uuid.uuid4().hex[:8]
    output_stem = f"cv-{company_slug}-{request_id}"

    word_buffer = 3
    pdf_path    = None
    page_count  = None

    for attempt in range(1, MAX_PAGE_ATTEMPTS + 1):
        try:
            rewrites = tailor.get_rewrites(tex_content, jd_text, analysis, word_buffer=word_buffer)
        except SystemExit as e:
            raise HTTPException(status_code=502, detail=f"Rewrite generation failed: {e}")

        tex_tailored = tailor.apply_changes(tex_content, analysis, rewrites)

        try:
            pdf_path, page_count = tailor.compile_latex(tex_tailored, output_stem)
        except SystemExit as e:
            raise HTTPException(status_code=500, detail=f"PDF compilation failed: {e}")

        if page_count <= 1:
            break
        word_buffer -= 4  # tighten below original length on the next retry

    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(status_code=500, detail="PDF was not produced")

    # Handy metadata as response headers — useful for a Shortcuts/bot
    # frontend to show "Tailored for CONXAI · ML_AI · 1 page" without
    # having to parse the PDF.
    headers = {
        "X-Page-Count": str(page_count),
        "X-Archetype": archetype,
        "X-Company": company,
    }

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{output_stem}.pdf",
        headers=headers,
    )