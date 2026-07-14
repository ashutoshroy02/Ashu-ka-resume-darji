#!/usr/bin/env python3
"""
tailor.py — Resume tailoring via keyword injection into existing .tex templates.
"""

import argparse
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
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    sys.exit("❌  OPENROUTER_API_KEY not set in .env")

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)
MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")

# ─── Template map ──────────────────────────────────────────────────────
TEMPLATE_MAP = {
    "ML_AI":          "01_ML_AI_Engineer_Ashutosh.tex",
    "Data_Scientist": "02_Data_Scientist_Ashutosh.tex",
    "Python_Dev":     "03_Python_Developer_Ashutosh.tex",
    "CV_Researcher":  "04_CV_Researcher_Ashutosh.tex",
    "AI_Agent":       "05_AI_Agent_Ashutosh.tex",
}


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
        messages=[{"role": "user", "content": prompt}],
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
  "role_archetype": "one of: ML_AI | Data_Scientist | Python_Dev | CV_Researcher | AI_Agent",
  "keywords": ["15-20 exact keyword phrases from the JD"],
  "headline": "tailored job title line, max 8 words",
  "archetype_reason": "1 sentence why"
}}

Archetype guide:
- ML_AI: LLM, RAG, fine-tuning, MLOps, speech/audio AI
- Data_Scientist: data analysis, EDA, SQL, statistics, Power BI, Tableau
- Python_Dev: backend, FastAPI, REST API, system design, SWE
- CV_Researcher: computer vision, OCR, research, multimodal, publications focus
- AI_Agent: agents, LangGraph, MCP, tool calling, multi-agent

Job Description:
{jd_text}"""

    raw = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
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
    prompt = f"""You are a resume expert. Inject JD keywords into resume text.

CRITICAL RULES:
1. Output PLAIN TEXT ONLY — absolutely no LaTeX, no backslashes, no \\textbf, no \\href
2. Each item MUST stay within its word limit — this is a 1-page resume, overflow = broken
3. Only swap existing words for JD vocabulary — never invent new experience
4. Keep all numbers/metrics exactly as-is (35%, 40%, 10,000+)
5. Return null for bullets that don't need changes

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
        messages=[{"role": "user", "content": prompt}],
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

    def trim(text: str, limit: int) -> str:
        words = text.split()
        return " ".join(words[:limit]) if len(words) > limit else text

    if new_summary:
        new_summary = trim(new_summary, max(1, summary_wc + word_buffer))

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
def compile_latex(tex_content: str, output_stem: str) -> tuple[Path, int]:
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

    engine = None
    for candidate in ["tectonic", "pdflatex"]:
        try:
            subprocess.run([candidate, "--version"], capture_output=True, check=True, **_subprocess_kwargs)
            engine = candidate
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    if not engine:
        sys.exit("  ❌ No LaTeX engine found. Install pdflatex (MiKTeX) or tectonic.")

    print(f"  ⚙️  Compiling with {engine}...")
    try:
        if engine == "pdflatex":
            args = ["pdflatex", "-interaction=nonstopmode",
                    f"-output-directory={OUTPUT_DIR}", str(tex_path)]
            r1 = subprocess.run(args, capture_output=True, timeout=120, **_subprocess_kwargs)
            r2 = subprocess.run(args, capture_output=True, timeout=120, **_subprocess_kwargs)
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
# MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description="Tailor resume via keyword injection")
    ap.add_argument("--jd",      required=True)
    ap.add_argument("--company", default=None)
    args = ap.parse_args()

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  career-ops tailor.py")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    print("[1/5] Fetching JD...")
    jd_text, company_auto = fetch_jd(args.jd)
    company      = args.company or company_auto
    company_slug = re.sub(r"[^a-zA-Z0-9]+", "-", company).strip("-").lower()
    print(f"      Company: {company} | JD: {len(jd_text)} chars")

    print("\n[2/5] Analyzing JD...")
    analysis      = analyze_jd(jd_text)
    archetype     = analysis["role_archetype"]
    template_name = TEMPLATE_MAP.get(archetype, TEMPLATE_MAP["ML_AI"])
    print(f"      Archetype : {archetype}")
    print(f"      Template  : {template_name}")
    print(f"      Headline  : {analysis.get('headline', '')}")
    print(f"      Keywords  : {', '.join(analysis['keywords'][:5])}...")

    print(f"\n[3/5] Loading template: {template_name}")
    tpl_path = TEMPLATES / template_name
    if not tpl_path.exists():
        sys.exit(f"  ❌ Template not found: {tpl_path}")
    tex_content = tpl_path.read_text(encoding="utf-8")
    print(f"      Loaded {len(tex_content)} chars")

    today       = date.today().strftime("%Y-%m-%d")
    output_stem = f"cv-ashutosh-{company_slug}-{today}"

    # ── One-page enforcement loop ───────────────────────────────────
    # The source templates are exactly one page. A rewrite that matches the
    # original word count can still overflow the page if the LLM swaps in
    # longer JD-vocabulary words (equal word count, more characters). So
    # instead of trusting word count alone, we compile, actually measure
    # the resulting PDF's page count, and if it's >1 we re-run the rewrite
    # with a tighter (eventually negative) word buffer — forcing bullets
    # and the summary to get shorter than the original, not just "not
    # longer" — until it fits on one page or we exhaust retries.
    MAX_PAGE_ATTEMPTS = 4
    word_buffer = 3
    pdf_path = None
    page_count = None

    for attempt in range(1, MAX_PAGE_ATTEMPTS + 1):
        print(f"\n[4/5] Getting rewrites (attempt {attempt}/{MAX_PAGE_ATTEMPTS})...")
        rewrites     = get_rewrites(tex_content, jd_text, analysis, word_buffer=word_buffer)
        tex_tailored = apply_changes(tex_content, analysis, rewrites)

        print("\n[5/5] Compiling PDF...")
        pdf_path, page_count = compile_latex(tex_tailored, output_stem)

        if page_count <= 1:
            break

        if attempt < MAX_PAGE_ATTEMPTS:
            print(f"  🔁 {page_count} pages — tightening word limits and retrying "
                  f"(next buffer: {word_buffer - 4:+d})...")
            word_buffer -= 4  # push below zero to force shrinkage below original length
        else:
            print(f"  ⚠️  Still {page_count} pages after {MAX_PAGE_ATTEMPTS} attempts.")
            print(f"      Automatic shrinking has a limit — the template itself may need "
                  f"trimming (fewer bullets, smaller margins) for this JD's keyword set.")

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  ✅ DONE" if page_count == 1 else "  ⚠️  DONE (with page-count warning)")
    print(f"  Template : {template_name}")
    print(f"  Archetype: {archetype}")
    print(f"  Keywords : {len(analysis['keywords'])} targeted")
    print(f"  Pages    : {page_count}")
    print(f"  PDF      : {pdf_path}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    if sys.platform == "win32":
        os.startfile(str(pdf_path))


if __name__ == "__main__":
    main()