#!/usr/bin/env python3
"""
tailor.py — Resume tailoring via keyword injection into existing .tex templates.
"""

import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
import io

# Rewrap stdout/stderr as UTF-8 with line-buffering so emoji/unicode print()
# calls show up immediately in a normal console. Guarded because under
# pythonw.exe (no console window — used for silent/background runs)
# sys.stdout is None, and a launcher script may have already redirected
# stdout to a plain file (no .buffer attribute) before importing this module.
if sys.stdout is not None and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True, write_through=True)
if sys.stderr is not None and hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True, write_through=True)

# ─── Paths ─────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent
USER_DATA  = ROOT / "user_data"
TEMPLATES  = ROOT / "templates" / "roles"
OUTPUT_DIR = USER_DATA / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── Load env ──────────────────────────────────────────────────────────
load_dotenv(ROOT / ".env")
# LLM provider: OpenRouter by default. Any OpenAI-compatible API works through the
# LLM_* settings in .env (e.g. Groq: LLM_BASE_URL=https://api.groq.com/openai/v1).
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or "https://openrouter.ai/api/v1"
LLM_API_KEY  = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")
if not LLM_API_KEY:
    sys.exit("❌  No LLM key: set LLM_API_KEY (or OPENROUTER_API_KEY) in .env")

client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    max_retries=5,   # free tiers rate-limit often; the SDK waits and retries
)
MODEL = os.getenv("LLM_MODEL") or os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")
# Extra provider-specific request fields as JSON, e.g. {"reasoning_effort": "none"}
# turns off Qwen's thinking on Groq.
LLM_EXTRA_BODY = json.loads(os.getenv("LLM_EXTRA_BODY") or "{}")

# ─── Template map ──────────────────────────────────────────────────────
# Older bases (01 ML_AI, 02 Data_Scientist, 03 Python_Dev, 05 AI_Agent) are
# in templates/roles/archive/; AI_ML_Engineer plus the project picker covers them.
TEMPLATE_MAP = {
    "AI_ML_Engineer": "07_AI_ML_Engineer_Ashutosh.tex",
    "AI_Builder":     "06_AI_Builder_Ashutosh.tex",
    "CV_Researcher":  "04_CV_Researcher_Ashutosh.tex",
}
DEFAULT_BASE = "AI_ML_Engineer"   # used when the JD analysis returns an unknown archetype

# Page target per base (default 1). The research CV is 2 pages by design.
PAGE_LIMIT = {"CV_Researcher": 2}

# Bases whose project picks are fixed by the owner: always pre-select the base's own
# Projects section (AI/ML Engineer also serves SDE/backend roles). No ranking LLM call.
FIXED_PICK_BASES = {"AI_ML_Engineer"}

# Human-readable names for the base templates (Telegram buttons, logs).
BASE_LABELS = {
    "AI_ML_Engineer": "AI/ML Engineer",
    "AI_Builder":     "AI-First Builder (Full-Stack)",
    "CV_Researcher":  "Research CV (2 pages)",
}

PROJECTS_FILE = ROOT / "templates" / "projects.yml"
MIN_PROJECTS  = 2   # one-page fitting never drops below this many projects


# ══════════════════════════════════════════════════════════════════════
# STEP 0 — Render JD page (JS-aware, falls back to plain requests)
# ══════════════════════════════════════════════════════════════════════
def _fetch_rendered_html(url: str) -> str:
    """
    Fetch a URL's fully JS-rendered HTML using a headless browser.
    Many career sites (Eightfold, Workday, Greenhouse, Lever, etc.) are SPAs
    that fetch job content via an API call *after* page load — plain
    requests.get() only ever sees the pre-hydration shell/fallback state.

    Falls back to a plain `requests` GET if Playwright / its browser
    binaries aren't installed, so this doesn't hard-crash on machines
    without it set up yet.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return _fetch_html_requests(url)

    print("  🧭 Rendering page with your installed Chrome (Playwright)...")
    try:
        with sync_playwright() as p:
            try:
                # Use the system-installed Chrome — no separate download needed.
                browser = p.chromium.launch(headless=True, channel="chrome")
            except Exception:
                browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"
            )
            page.goto(url, wait_until="networkidle", timeout=20000)
            # give SPA hydration/XHR-driven content a little extra buffer
            page.wait_for_timeout(1500)
            html = page.content()
            browser.close()
        return html
    except Exception:
        return _fetch_html_requests(url)


def _fetch_html_requests(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        sys.exit(f"  ❌ Failed to fetch URL: {e}")
    return resp.text


# ══════════════════════════════════════════════════════════════════════
# STEP 0b — Get RAW text (tags stripped only — no boilerplate guessing,
#           no truncation). Let the LLM figure out what's actually the JD.
# ══════════════════════════════════════════════════════════════════════
def _raw_text_dump(html: str) -> str:
    """
    Strip only non-content tags (script/style/svg/noscript) and return
    EVERYTHING else as plain text — nav, footer, cookie banner, the whole
    page. No boilerplate pattern guessing, no length cap. We deliberately
    give the LLM more than it needs and let it pick the JD out, since
    heuristic nav/footer detection is fragile across different ATS
    platforms (Workday, Eightfold, Greenhouse, Lever, iCIMS...).
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def extract_jd_from_raw_text(raw_text: str) -> str:
    """
    Send the FULL raw page text to the LLM and have it pull out just the
    actual job description (title, responsibilities, qualifications),
    dropping nav/footer/cookie-banner/unrelated-links noise. Returns
    plain text, verbatim JD wording (no summarizing/rewriting).
    """
    print("  🤖 Extracting structured JD from raw page text...")

    prompt = f"""Below is the FULL raw text scraped from a job listing webpage.
It includes navigation menus, footers, cookie notices, and other site
chrome mixed in with the actual job description. Some content may be
duplicated across sections of the page.

Your task: extract ONLY the actual job description content —
job title, location, responsibilities/roles, requirements/qualifications,
and any "about the role" / "about the team" sections.

Rules:
- Copy the JD content VERBATIM — do not summarize, paraphrase, or shorten it.
- Do NOT include navigation links, footer addresses, "browse jobs",
  "talent community", cookie notices, or other site-chrome text.
- Do NOT include any of your own commentary.
- If the page indicates the listing is expired/removed/no longer available
  and there is no real JD content present, respond with exactly:
  JD_NOT_FOUND: <one sentence reason>
- Preserve section structure (headers like "Responsibilities", "Qualifications")
  as plain text lines, not markdown.

Raw page text:
---
{raw_text}
---

Return ONLY the extracted job description text (or the JD_NOT_FOUND line)."""

    raw = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}], extra_body=LLM_EXTRA_BODY,
        temperature=0.0,
    ).choices[0].message.content.strip()

    if raw.startswith("JD_NOT_FOUND"):
        print(f"  ⚠️  WARNING: {raw}")

    return raw


# ══════════════════════════════════════════════════════════════════════
# STEP 1 — Fetch JD
# ══════════════════════════════════════════════════════════════════════
def fetch_jd(jd_input: str) -> tuple[str, str]:
    p = Path(jd_input)
    if p.exists() and p.is_file():
        print(f"  📄 Reading JD from file: {p}")
        text = p.read_text(encoding="utf-8")
        company = p.stem.replace("-", " ").replace("_", " ").title()
        return text, company

    if re.match(r"^https?://", jd_input):
        print(f"  🌐 Fetching JD from URL: {jd_input}")
        domain  = re.sub(r"https?://(www\.)?", "", jd_input).split("/")[0]
        company = domain.split(".")[0].title()

        html     = _fetch_rendered_html(jd_input)
        raw_text = _raw_text_dump(html)
        text     = extract_jd_from_raw_text(raw_text)

        if text.startswith("JD_NOT_FOUND"):
            sys.exit(f"  ❌ Could not find a real JD on this page: {text}\n"
                      f"      Re-check the URL, or paste the JD as plain text/file instead.")

        return text, company

    print("  📝 Using JD as plain text")
    return jd_input, "Company"


# ══════════════════════════════════════════════════════════════════════
# STEP 2 — Analyze JD → archetype + keywords
# ══════════════════════════════════════════════════════════════════════
def analyze_jd(jd_text: str) -> dict:
    print("  🤖 Analyzing JD — choosing template & extracting keywords...")

    # Static instructions/schema come FIRST and variable JD text LAST so the
    # stable prefix stays byte-identical across calls — this is what makes
    # Gemini's implicit prompt caching (via OpenRouter) eligible to hit.
    prompt = f"""Analyze this job description and return JSON.

Return ONLY this JSON (no markdown, no explanation):
{{
  "role_archetype": "one of: AI_ML_Engineer | AI_Builder | CV_Researcher",
  "keywords": ["15-20 exact keyword phrases from the JD"],
  "headline": "tailored job title line, max 8 words",
  "archetype_reason": "1 sentence why"
}}

Archetype guide:
- AI_ML_Engineer: the default. AI / ML / LLM / GenAI / AI agent / AI backend engineer roles, and data or backend roles: LLMs, RAG, fine-tuning, agents (LangGraph, MCP, tool calling), evaluation, MLOps, model serving, APIs.
- AI_Builder: full-stack / product engineer, shipping web/mobile/desktop apps, TypeScript, LLM APIs in products, AI-assisted development (Claude Code), founding/startup engineer
- CV_Researcher: research roles: research engineer / scientist / assistant / intern, PhD or lab positions, publications focus, computer vision or multimodal research

Job Description:
{jd_text}"""

    raw = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}], extra_body=LLM_EXTRA_BODY,
        temperature=0.2,
    ).choices[0].message.content.strip()

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"  ❌ Could not parse analysis JSON: {e}\nRaw:\n{raw}")

    return result


# ══════════════════════════════════════════════════════════════════════
# STEP 3 — Extract plain text from bullets/summary (strip LaTeX)
# ══════════════════════════════════════════════════════════════════════
def extract_braced(text: str, start_idx: int) -> tuple[str, int]:
    """Given index of '{', return (content, index_after_closing_brace)."""
    assert text[start_idx] == "{"
    depth = 0
    for i in range(start_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start_idx + 1 : i], i + 1
    raise ValueError(f"Unbalanced braces starting at index {start_idx}")


def find_all_command_args(tex: str, command: str) -> list[tuple[int, int, str]]:
    r"""Find every \command{...} using balanced-brace extraction."""
    results = []
    search_from = 0
    pattern = re.compile(re.escape(command) + r"\s*\{")
    while True:
        m = pattern.search(tex, search_from)
        if not m:
            break
        open_idx = m.end() - 1
        content, close_idx = extract_braced(tex, open_idx)
        results.append((open_idx, close_idx, content))
        search_from = close_idx
    return results


def _strip_latex(text: str) -> str:
    """Remove LaTeX commands, keep inner text and plain content."""
    text = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\(?:textbf|textit|emph|small|large|Large|textasciitilde|textasciicircum|textbackslash)\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _word_count(text: str) -> int:
    return len(_strip_latex(text).split())


# ══════════════════════════════════════════════════════════════════════
# STEP 4 — Gemini: get plain-text rewrites (word-count bounded)
# ══════════════════════════════════════════════════════════════════════
def get_rewrites(tex_content: str, jd_text: str, analysis: dict, word_buffer: int = 3) -> dict:
    """
    word_buffer controls how many words each rewrite is allowed to grow by
    relative to the original (can go negative to force shrinkage below the
    original length). Since the source templates are hand-tuned to exactly
    one page, growth of even a few words per bullet can push the PDF onto a
    second page — this is tightened on retry by the caller if that happens.
    """
    print(f"  🤖 Getting keyword-injected rewrites (word buffer {word_buffer:+d})...")

    keywords_str = "\n".join(f"- {kw}" for kw in analysis["keywords"])

    # Extract summary
    existing_summary_latex = ""
    sec_match = re.search(r"\\section\{Summary\}", tex_content)
    if sec_match:
        small_pat = re.compile(r"\\small\s*\{")
        sm = small_pat.search(tex_content, sec_match.end())
        if sm:
            open_idx = sm.end() - 1
            content, _ = extract_braced(tex_content, open_idx)
            existing_summary_latex = content.strip()
    existing_summary_plain = _strip_latex(existing_summary_latex)
    summary_wc = len(existing_summary_plain.split())

    # Extract bullets as plain text with original index
    item_occurrences = find_all_command_args(tex_content, r"\resumeItem")
    bullets_latex = [content for _, _, content in item_occurrences]
    bullets_plain = [_strip_latex(b) for b in bullets_latex]
    bullet_wcs    = [len(b.split()) for b in bullets_plain]

    print(f"      🔍 Extracted {len(bullets_latex)} bullets total")

    bullets_str = "\n".join(
        f"[{i}] (limit {max(1, wc + word_buffer)} words) {b}"
        for i, (b, wc) in enumerate(zip(bullets_plain, bullet_wcs))
    )

    # Ordering here is deliberate for cache-friendliness: rules/schema (fully
    # static) lead, then the resume template content (summary/bullets — only
    # changes when you edit the .tex template, so it's stable across many
    # tailor.py runs), and the JD/keywords (unique every single run) come
    # last. This maximizes the shared prefix across repeated runs against
    # the same template, which is what implicit prompt caching keys off.
    if word_buffer < 0:
        # Retry after a 2-page compile: every item has to get shorter, and
        # it must still read as a complete sentence (never cut mid-phrase).
        shrink_rule = ("5. SHRINK MODE — the resume is over one page. Rewrite EVERY bullet (no nulls) as a "
                       "complete, shorter sentence within its limit: drop filler words, keep the core "
                       "achievement and its metric. Never end a bullet mid-phrase.")
    else:
        shrink_rule = "5. Return null for bullets that don't need changes"

    prompt = f"""You are a resume expert. Inject JD keywords into resume text.

CRITICAL RULES:
1. Output PLAIN TEXT ONLY — absolutely no LaTeX, no backslashes, no \\textbf, no \\href
2. Each item MUST stay within its word limit — this is a 1-page resume, overflow = broken
3. Only swap existing words for JD vocabulary — never invent new experience
4. Keep all numbers/metrics exactly as-is (35%, 40%, 10,000+)
{shrink_rule}

Return ONLY this JSON structure (no markdown):
{{
  "new_summary": "plain text summary within word limit",
  "bullets": {{
    "0": "plain text rewrite or null",
    "1": "plain text rewrite or null"
  }}
}}

Current Summary (plain text, {summary_wc} words, limit {max(1, summary_wc + word_buffer)} words):
{existing_summary_plain}

Current Bullets (plain text):
{bullets_str}

JD Keywords to use:
{keywords_str}

Job Description:
{jd_text}"""

    raw = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}], extra_body=LLM_EXTRA_BODY,
        temperature=0.2,
    ).choices[0].message.content.strip()

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        raw2 = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
        try:
            result = json.loads(raw2)
        except json.JSONDecodeError as e:
            sys.exit(f"  ❌ Could not parse rewrite JSON: {e}\nRaw:\n{raw}")

    new_summary     = result.get("new_summary", "")
    changed_bullets = result.get("bullets", {})

    def _is_effectively_null(v) -> bool:
        """
        The model is supposed to return JSON null for 'no change needed',
        but small/fast models sometimes return the literal STRING "null"
        (or "none", or an empty string) instead. `v is None` only catches
        real JSON null — a string slips through and gets inserted as if it
        were real text (e.g. "- null query resolution time by 40%..."). 
        Catch that here so it's treated the same as no-change.
        """
        return v is None or (isinstance(v, str) and v.strip().lower() in ("null", "none", ""))

    if _is_effectively_null(new_summary):
        new_summary = ""

    for k in list(changed_bullets.keys()):
        if _is_effectively_null(changed_bullets[k]):
            changed_bullets[k] = None

    def trim(text: str, limit: int) -> str | None:
        """
        Fit text to `limit` words without ending mid-phrase: cut at the last
        clause boundary (", " / "; ") inside the limit and end with a period.
        A plain word cut produced broken bullets like "...reducing response
        time by". Returns None (= keep the original wording) if there is no
        clean cut point.
        """
        words = text.split()
        if len(words) <= limit:
            return text
        cut = " ".join(words[:limit])
        pos = max(cut.rfind(", "), cut.rfind("; "))
        if pos == -1 or len(cut[:pos].split()) < max(4, limit // 2):
            return None
        return cut[:pos].rstrip(" ,;") + "."

    if new_summary:
        new_summary = trim(new_summary, max(1, summary_wc + word_buffer)) or ""

    for k, v in changed_bullets.items():
        if v is None:
            continue
        try:
            idx = int(k)
            if idx < len(bullet_wcs):
                changed_bullets[k] = trim(v, max(1, bullet_wcs[idx] + word_buffer))
        except (ValueError, IndexError):
            pass

    changed_cnt = sum(1 for v in changed_bullets.values() if v is not None)
    print(f"      Summary rewritten : {'yes' if new_summary else 'no'}")
    print(f"      Bullets changed   : {changed_cnt} / {len(bullets_latex)}")

    return {
        "new_summary":        new_summary,
        "summary_plain":      existing_summary_plain,
        "bullets":            changed_bullets,
        "bullets_latex":      bullets_latex,
        "bullets_plain":      bullets_plain,
    }


# ══════════════════════════════════════════════════════════════════════
# STEP 5 — Apply plain-text rewrites back into LaTeX
# ══════════════════════════════════════════════════════════════════════
def _esc(text: str) -> str:
    """Escape special LaTeX chars in plain text."""
    for ch, repl in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                     ("#", r"\#"), ("_", r"\_")]:
        text = text.replace(ch, repl)
    return text


def apply_changes(tex_content: str, analysis: dict, rewrites: dict) -> str:
    print("  ✏️  Applying changes to template...")

    # 1. Headline
    headline = analysis.get("headline", "")
    if headline:
        tex_content, n = re.subn(
            r"(\\Large \\textbf\{)[^}]+(})",
            lambda m: m.group(1) + _esc(headline) + m.group(2),
            tex_content, count=1
        )

    # 2. Summary
    new_summary = rewrites.get("new_summary", "")
    if new_summary:
        tex_content, n = re.subn(
            r"(\\section\{Summary\}.*?\\small\{)(.*?)(\}\s*\\vspace)",
            lambda m: m.group(1) + "\n" + _esc(new_summary) + "\n" + m.group(3),
            tex_content, count=1, flags=re.DOTALL
        )

    # 3. Bullets
    bullets_latex = rewrites.get("bullets_latex", [])
    bullets_plain = rewrites.get("bullets_plain", [])
    changed       = rewrites.get("bullets", {})

    applied, skipped_same, skipped_nomatch = [], [], []

    for idx_str, new_plain in changed.items():
        if new_plain is None:
            continue
        try:
            idx = int(idx_str)
        except ValueError:
            continue
        if idx >= len(bullets_latex):
            continue

        orig_latex_exact = bullets_latex[idx]        # unstripped — must match tex_content exactly
        orig_plain       = bullets_plain[idx].strip()
        new_plain        = new_plain.strip()

        if not orig_plain or orig_plain == new_plain:
            skipped_same.append(idx)
            continue

        # Replace the ENTIRE original bullet content wholesale, rather than
        # pattern-matching a prefix of it. The previous approach matched
        # only the first 40 chars of the original plain text and replaced
        # just that fragment with the full new sentence — leaving
        # everything after char 40 of the *original* bullet still present,
        # glued onto the end of the new one (the duplicated/overlapping
        # text bug). Since bullets_latex[idx] already IS the exact original
        # content, there's nothing to pattern-match — just swap it whole.
        # Uses the UNSTRIPPED original so it matches tex_content byte-for-
        # byte, including any incidental leading/trailing whitespace inside
        # the \resumeItem{...} block.
        old_item = f"\\resumeItem{{{orig_latex_exact}}}"
        new_item = f"\\resumeItem{{{_esc(new_plain)}}}"
        if old_item in tex_content:
            tex_content = tex_content.replace(old_item, new_item, 1)
            applied.append(idx)
        else:
            skipped_nomatch.append(idx)

    return tex_content


def _count_pdf_pages(pdf_path: Path) -> int:
    """Cheap page count via raw /Type /Page object scan — no extra deps."""
    pdf_data = pdf_path.read_bytes().decode("latin-1", errors="replace")
    return len(re.findall(r"/Type\s*/Page[^s]", pdf_data))


# ══════════════════════════════════════════════════════════════════════
# STEP 6 — Compile
# ══════════════════════════════════════════════════════════════════════
_LATEX_ENGINE = None  # detected on the first compile, then reused


def compile_latex(tex_content: str, output_stem: str, passes: int = 2) -> tuple[Path, int]:
    tex_path = OUTPUT_DIR / f"{output_stem}.tex"
    pdf_path = OUTPUT_DIR / f"{output_stem}.pdf"

    tex_path.write_text(tex_content, encoding="utf-8")
    print(f"  📝 LaTeX saved: {tex_path.name}")

    # On Windows, subprocess.run() spawns a visible console window for the
    # child process by default even when the parent (e.g. pythonw.exe) has
    # none — with the compile retry loop calling this up to 4x per request,
    # that shows up as windows rapidly flashing open/closed. Suppress it.
    _subprocess_kwargs = {}
    if sys.platform == "win32":
        _subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    global _LATEX_ENGINE
    engine = _LATEX_ENGINE
    for candidate in [] if engine else ["tectonic", "pdflatex"]:
        try:
            subprocess.run([candidate, "--version"], capture_output=True, check=True, **_subprocess_kwargs)
            engine = candidate
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    if not engine:
        sys.exit("  ❌ No LaTeX engine found. Install pdflatex (MiKTeX) or tectonic.")
    _LATEX_ENGINE = engine

    print(f"  ⚙️  Compiling with {engine}...")
    try:
        if engine == "pdflatex":
            args = ["pdflatex", "-interaction=nonstopmode",
                    f"-output-directory={OUTPUT_DIR}", str(tex_path)]
            for _ in range(passes):  # 1 pass is enough when only the page count matters
                subprocess.run(args, capture_output=True, timeout=120, **_subprocess_kwargs)
        else:
            r = subprocess.run(["tectonic", "--outdir", str(OUTPUT_DIR), str(tex_path)],
                           capture_output=True, timeout=120, check=True, **_subprocess_kwargs)
    except subprocess.TimeoutExpired:
        sys.exit("  ❌ Compilation timed out")

    if pdf_path.exists():
        kb = pdf_path.stat().st_size / 1024
        page_count = _count_pdf_pages(pdf_path)
        status     = "✅" if page_count == 1 else "⚠️ "
        print(f"  {status} PDF: {pdf_path}  ({kb:.1f} KB, {page_count} page{'s' if page_count != 1 else ''})")
        return pdf_path, page_count
    else:
        sys.exit(f"  ❌ PDF not produced. Check: {OUTPUT_DIR / output_stem}.log")


# ══════════════════════════════════════════════════════════════════════
# STEP 7 — Project library: choose and swap the Projects section
# ══════════════════════════════════════════════════════════════════════
_BS = "\\"


def load_projects() -> list[dict]:
    """All projects from templates/projects.yml (see that file's header)."""
    data = yaml.safe_load(PROJECTS_FILE.read_text(encoding="utf-8")) or {}
    return data.get("projects", [])


def _project_blocks(chunk: str) -> list[str]:
    r"""Split LaTeX into its \resumeProjectHeading ... \resumeItemListEnd blocks."""
    head, end = _BS + "resumeProjectHeading", _BS + "resumeItemListEnd"
    blocks = []
    for part in chunk.split(head)[1:]:
        cut = part.find(end)
        blocks.append((head + (part[: cut + len(end)] if cut != -1 else part)).strip())
    return blocks


def _block_heading(block: str) -> str:
    return block.split(_BS + "resumeItemListStart")[0]


def _block_title(block: str) -> str:
    m = re.search(r"\\textbf\{([^}]*)\}", _block_heading(block))
    return _strip_latex(m.group(1)) if m else "Project"


def _match_project(block: str, library: list[dict]) -> str | None:
    heading = _block_heading(block)
    for p in library:
        if any(s in heading for s in p.get("match", [])):
            return p["id"]
    return None


def _projects_span(tex: str) -> tuple[int, int]:
    r"""(start, end) of the item list inside the first \section{...Projects...}."""
    sec = re.search(r"\\section\{[^}]*Projects[^}]*\}", tex)
    if not sec:
        raise ValueError("Template has no Projects section")
    start_tok, end_tok = _BS + "resumeSubHeadingListStart", _BS + "resumeSubHeadingListEnd"
    s = tex.index(start_tok, sec.end()) + len(start_tok)
    e = tex.index(end_tok, s)
    return s, e


def base_project_info(tex: str, library: list[dict]) -> dict:
    """
    What a base template offers:
      defaults : ids of the projects the template ships with, in its order
      options  : ids the user can choose from (whole library + template-only
                 projects), minus projects already shown in another section of
                 the base (e.g. Publications / Open Source) so nothing repeats
      blocks   : id -> LaTeX block to use (the template's own wording wins)
      names    : id -> short label for buttons
    """
    s, e = _projects_span(tex)
    outside = tex[:s] + tex[e:]
    hidden = {pid for b in _project_blocks(outside) if (pid := _match_project(b, library))}
    own = {pid for b in _project_blocks(tex[s:e]) if (pid := _match_project(b, library))}
    hidden |= {p["id"] for p in library                  # same work already shown elsewhere,
               if p["id"] not in own                      # unless the base lists it itself
               and any(x in outside for x in p.get("hide_if", []))}

    blocks = {p["id"]: p["latex"].strip() for p in library}
    names  = {p["id"]: p.get("name", p["id"]) for p in library}
    defaults, extra = [], []
    for i, b in enumerate(_project_blocks(tex[s:e])):
        pid = _match_project(b, library)
        if pid is None:                        # a project only this template has
            pid = f"base-{i}"
            names[pid] = _block_title(b)
            extra.append(pid)
        blocks[pid] = b
        if pid not in hidden and pid not in defaults:
            defaults.append(pid)

    options = [p["id"] for p in library if p["id"] not in hidden] + extra
    return {"defaults": defaults, "options": options, "blocks": blocks, "names": names}


def build_projects_tex(tex: str, ids: list[str], blocks: dict) -> str:
    """Replace the base template's Projects list with `ids`, in that order."""
    s, e = _projects_span(tex)
    sep = "\n\n\\vspace{4pt}\n\n" if "\\vspace{4" in tex[s:e] else "\n\n"
    return tex[:s] + "\n\n" + sep.join(blocks[i] for i in ids) + "\n\n" + tex[e:]


def rank_projects(jd_text: str, analysis: dict, base_key: str, info: dict, library: list[dict]) -> dict:
    """
    AI ranks every available project for this JD and base. Returns
      {"ranking": [all option ids, best first], "picks": [ids to pre-select], "reason": str}
    The number of picks = how many projects the base normally shows (min MIN_PROJECTS).
    If the model's answer is unusable, falls back to the base's own projects.
    Bases in FIXED_PICK_BASES skip the model and always pick their own projects.
    """
    if base_key in FIXED_PICK_BASES:
        picks = list(info["defaults"])
        print(f"  📌 Fixed projects for {BASE_LABELS.get(base_key, base_key)}: {', '.join(picks)}")
        return {"ranking": picks + [i for i in info["options"] if i not in picks],
                "picks": picks, "reason": "Your fixed projects for AI/ML and SDE roles."}
    print("  🤖 Ranking projects for this JD...")
    options = info["options"]
    tags_by_id = {p["id"]: ", ".join(p.get("tags", [])) for p in library}
    n_picks = max(MIN_PROJECTS, len(info["defaults"]))
    project_lines = "\n".join(
        f"- {pid}: {info['names'][pid]} [tags: {tags_by_id.get(pid, '')}] "
        f"{_strip_latex(info['blocks'][pid])[:300]}"
        for pid in options
    )

    prompt = f"""You choose which projects go on a one-page resume for a specific job.

Return ONLY this JSON (no markdown):
{{
  "ranking": ["every project id from the list, most relevant to the job first"],
  "reason": "1 short sentence on why the top {n_picks} fit this job"
}}

Rules:
- Use only ids from the list, each exactly once.
- Rank by how strongly each project proves skills the job asks for.
- Resume base: "{BASE_LABELS.get(base_key, base_key)}". When two projects are about equally relevant, prefer the one that fits this base.
- This base normally shows: {", ".join(info["defaults"]) or "none"}.

Projects:
{project_lines}

JD keywords: {", ".join(analysis.get("keywords", []))}

Job Description:
{jd_text}"""

    ranking, reason = [], ""
    try:
        raw = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}], extra_body=LLM_EXTRA_BODY,
            temperature=0.1,
        ).choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()
        data = json.loads(raw)
        ranking = [i for i in data.get("ranking", []) if i in options]
        reason = str(data.get("reason", "") or "")
    except Exception as e:  # bad JSON / API error -> template defaults
        print(f"  ⚠️  Project ranking failed ({e}); using the base's own projects.")

    ordered = []
    for i in ranking + info["defaults"] + options:
        if i not in ordered:
            ordered.append(i)
    return {"ranking": ordered, "picks": ordered[:n_picks], "reason": reason}


def fit_projects(tex_base: str, ids: list[str], blocks: dict, output_stem: str,
                 max_pages: int = 1) -> tuple[list[str], list[str], int]:
    """
    Page rule, step 1: compile the untailored resume and drop the
    lowest-ranked project (last in `ids`) until it fits in `max_pages` or only
    MIN_PROJECTS remain. Returns (kept, dropped, pages of the last compile).
    """
    kept, dropped = list(ids), []
    while True:
        _, pages = compile_latex(build_projects_tex(tex_base, kept, blocks), output_stem, passes=1)
        if pages <= max_pages or len(kept) <= MIN_PROJECTS:
            return kept, dropped, pages
        dropped.append(kept.pop())
        print(f"  ✂️  {pages} pages — dropping lowest-ranked project: {dropped[-1]}")


def run_tailor(jd_text: str, analysis: dict, base_key: str, project_ids: list[str] | None,
               output_stem: str, max_attempts: int = 4) -> tuple[Path, dict]:
    """
    Full build for one base + project list (best first):
      1. swap in the chosen projects, dropping the lowest-ranked until it fits
         the base's page target (1 page; PAGE_LIMIT allows more, e.g. research CV)
      2. keyword rewrites; if that overflows, retry with tighter word limits
    Empty / None project_ids -> the base's own projects.
    """
    tpl_path = TEMPLATES / TEMPLATE_MAP[base_key]
    if not tpl_path.exists():
        sys.exit(f"  ❌ Template not found: {tpl_path}")
    tex_base = tpl_path.read_text(encoding="utf-8")
    info = base_project_info(tex_base, load_projects())

    ids = [i for i in (project_ids or []) if i in info["blocks"]] or info["defaults"]
    max_pages = PAGE_LIMIT.get(base_key, 1)
    kept, dropped, fit_pages = fit_projects(tex_base, ids, info["blocks"], output_stem, max_pages)
    tex_content = build_projects_tex(tex_base, kept, info["blocks"])

    # ── One-page rule, step 2 ──────────────────────────────────────
    # A rewrite with the same word count can still overflow if the LLM swaps
    # in longer JD words, so compile, measure the real page count, and retry
    # with a tighter (eventually negative) word buffer until it fits.
    buffers = [3 - 4 * i for i in range(max_attempts)]   # +3, -1, -5, -9
    if fit_pages > max_pages and len(buffers) > 1:
        # Already over the page target with the original wording, so the +3 round
        # (bullets may grow) can't fit: skip it and start shrinking.
        buffers = buffers[1:]
    pdf_path, page_count = None, None
    for attempt, word_buffer in enumerate(buffers, 1):
        print(f"\n  Rewrites (attempt {attempt}/{len(buffers)})...")
        rewrites     = get_rewrites(tex_content, jd_text, analysis, word_buffer=word_buffer)
        tex_tailored = apply_changes(tex_content, analysis, rewrites)
        pdf_path, page_count = compile_latex(tex_tailored, output_stem)
        if page_count <= max_pages:
            break
        if attempt < len(buffers):
            print(f"  🔁 {page_count} pages — tightening word limits (next buffer: {buffers[attempt]:+d})...")
        else:
            print(f"  ⚠️  Still {page_count} pages after {len(buffers)} attempts.")

    return pdf_path, {
        "page_count": page_count,
        "kept":    [info["names"][i] for i in kept],
        "dropped": [info["names"][i] for i in dropped],
        "kept_ids":    kept,
        "dropped_ids": dropped,
    }


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def catalog() -> dict:
    """Bases and project ids for --list (no LLM call)."""
    library = load_projects()
    bases = []
    for key, fname in TEMPLATE_MAP.items():
        info = base_project_info((TEMPLATES / fname).read_text(encoding="utf-8"), library)
        bases.append({"key": key, "label": BASE_LABELS[key], "template": fname,
                      "default_projects": info["defaults"]})
    projects = [{"id": p["id"], "name": p.get("name", p["id"]), "tags": p.get("tags", [])}
                for p in library]
    return {"bases": bases, "projects": projects}


def main():
    ap = argparse.ArgumentParser(description="Tailor resume via keyword injection")
    ap.add_argument("--jd",       help="JD as a URL, a file path, or plain text")
    ap.add_argument("--company",  default=None)
    ap.add_argument("--base",     choices=list(TEMPLATE_MAP), help="base resume (default: the AI's pick)")
    ap.add_argument("--projects", help="comma-separated project ids, best first (default: the AI's picks)")
    ap.add_argument("--list",     action="store_true", help="print the bases and project ids as JSON and exit")
    ap.add_argument("--json",     action="store_true",
                    help="no UI: progress goes to stderr, one JSON result to stdout, the PDF is not opened")
    args = ap.parse_args()

    if args.list:
        print(json.dumps(catalog(), indent=2))
        return
    if not args.jd:
        ap.error("--jd is required (or use --list)")
    if not args.json:
        build(args)
        return

    real_stdout, code = sys.stdout, 0
    try:
        with contextlib.redirect_stdout(sys.stderr):
            out = {"ok": True, **build(args)}
    except SystemExit as e:                       # tailor's own failures call sys.exit("...")
        out, code = {"ok": False, "error": str(e.code).strip()}, 1
    except Exception as e:
        out, code = {"ok": False, "error": f"{type(e).__name__}: {e}"}, 1
    print(json.dumps(out, indent=2), file=real_stdout)
    sys.exit(code)


def build(args) -> dict:
    """The CLI build. Prints progress; returns the result dict that --json prints."""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Resume-Darji tailor.py")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    print("[1/5] Fetching JD...")
    jd_text, company_auto = fetch_jd(args.jd)
    company      = args.company or company_auto
    company_slug = re.sub(r"[^a-zA-Z0-9]+", "-", company).strip("-").lower()
    print(f"      Company: {company} | JD: {len(jd_text)} chars")

    print("\n[2/5] Analyzing JD...")
    analysis      = analyze_jd(jd_text)
    archetype     = analysis["role_archetype"]
    ai_base       = archetype if archetype in TEMPLATE_MAP else DEFAULT_BASE
    base_key      = args.base or ai_base
    template_name = TEMPLATE_MAP[base_key]
    print(f"      Archetype : {archetype}")
    print(f"      Template  : {template_name}")
    print(f"      Headline  : {analysis.get('headline', '')}")
    print(f"      Keywords  : {', '.join(analysis['keywords'][:5])}...")

    library = load_projects()
    info    = base_project_info((TEMPLATES / template_name).read_text(encoding="utf-8"), library)
    if args.projects:
        wanted      = [i.strip() for i in args.projects.split(",") if i.strip()]
        project_ids = [i for i in wanted if i in info["blocks"]]
        ignored     = [i for i in wanted if i not in info["blocks"]]
        reason      = ""
        print(f"\n[3/5] Using your projects for base: {BASE_LABELS[base_key]}")
        if ignored:
            print(f"      Unknown ids ignored: {', '.join(ignored)}")
    else:
        print(f"\n[3/5] Ranking projects for base: {BASE_LABELS[base_key]}")
        ranked      = rank_projects(jd_text, analysis, base_key, info, library)
        project_ids, ignored, reason = ranked["picks"], [], ranked["reason"]
        print(f"      AI picks  : {', '.join(ranked['picks'])}")

    today       = date.today().strftime("%Y-%m-%d")
    output_stem = f"cv-ashutosh-{company_slug}-{today}"

    print("\n[4/5] Fitting projects, rewriting and compiling...")
    pdf_path, result = run_tailor(jd_text, analysis, base_key, project_ids, output_stem)
    page_count = result["page_count"]
    print(f"\n[5/5] Projects  : {', '.join(result['kept'])}")
    if result["dropped"]:
        print(f"      Dropped   : {', '.join(result['dropped'])} (to fit one page)")

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  ✅ DONE" if page_count <= PAGE_LIMIT.get(base_key, 1) else "  ⚠️  DONE (with page-count warning)")
    print(f"  Template : {template_name}")
    print(f"  Archetype: {archetype}")
    print(f"  Keywords : {len(analysis['keywords'])} targeted")
    print(f"  Pages    : {page_count}")
    print(f"  PDF      : {pdf_path}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    if sys.platform == "win32" and not args.json:
        os.startfile(str(pdf_path))

    return {
        "pdf":               str(pdf_path),
        "tex":               str(pdf_path.with_suffix(".tex")),
        "page_count":        page_count,
        "page_limit":        PAGE_LIMIT.get(base_key, 1),
        "company":           company,
        "base":              base_key,
        "base_label":        BASE_LABELS[base_key],
        "ai_suggested_base": ai_base,
        "archetype_reason":  analysis.get("archetype_reason", ""),
        "headline":          analysis.get("headline", ""),
        "keywords":          analysis.get("keywords", []),
        "projects_kept":     result["kept_ids"],
        "projects_dropped":  result["dropped_ids"],
        "projects_ignored":  ignored,
        "project_reason":    reason,
        "model":             MODEL,
    }


if __name__ == "__main__":
    main()