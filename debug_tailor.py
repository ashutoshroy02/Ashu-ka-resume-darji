#!/usr/bin/env python3
"""
tailor.py — Resume tailoring via keyword injection into existing .tex templates.
DEBUG-INSTRUMENTED VERSION — prints intermediate output at every step.

Set DEBUG=0 env var to silence the verbose blocks and keep only the normal
progress lines, e.g.  DEBUG=0 python tailor_debug.py --jd jd.txt
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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
# ─── Debug toggle ──────────────────────────────────────────────────────
DEBUG = os.getenv("DEBUG", "1") != "0"

def dbg(label: str, content: str = "", max_chars: int = 1500):
    """Print a clearly-delimited debug block."""
    if not DEBUG:
        return
    print(f"\n┌─── 🔍 DEBUG: {label} " + "─" * max(0, 40 - len(label)))
    if content != "":
        text = str(content)
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [truncated, {len(text)} chars total]"
        for line in text.splitlines() or [""]:
            print(f"│ {line}")
    print("└" + "─" * 50)


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
        dbg("_fetch_rendered_html() — ⚠️ Playwright not installed",
            "Falling back to plain requests.get(). JS-rendered SPA content "
            "(Eightfold/Workday/etc.) will likely be missed.\n"
            "Fix: pip install playwright && playwright install chromium")
        return _fetch_html_requests(url)

    print("  🧭 Rendering page with your installed Chrome (Playwright)...")
    try:
        with sync_playwright() as p:
            try:
                # Use the system-installed Chrome — no separate download needed.
                browser = p.chromium.launch(headless=True, channel="chrome")
            except Exception as e:
                dbg("_fetch_rendered_html() — ⚠️ system Chrome not found by Playwright",
                    f"{e}\nFalling back to Playwright's bundled Chromium. "
                    "If that's also missing, run: playwright install chromium")
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
        dbg("_fetch_rendered_html() — rendered HTML", f"length={len(html)} chars")
        return html
    except Exception as e:
        dbg("_fetch_rendered_html() — ⚠️ Playwright render failed, falling back",
            f"{e}\nFalling back to plain requests.get()")
        return _fetch_html_requests(url)


def _fetch_html_requests(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        sys.exit(f"  ❌ Failed to fetch URL: {e}")
    dbg("_fetch_html_requests() — raw HTTP response",
        f"status={resp.status_code}\ncontent-length={len(resp.text)} chars")
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
    dbg("_raw_text_dump() — full untruncated page text",
        f"word_count={len(text.split())} char_count={len(text)}\n\n{text}",
        max_chars=8000)
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

    dbg("extract_jd_from_raw_text() — prompt sent to model (raw text portion truncated in this box only)",
        prompt, max_chars=3000)

    raw = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    ).choices[0].message.content.strip()

    dbg("extract_jd_from_raw_text() — model response (extracted JD)", raw, max_chars=6000)

    if raw.startswith("JD_NOT_FOUND"):
        dbg("extract_jd_from_raw_text() — ⚠️ JD NOT FOUND", raw)
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
        dbg("fetch_jd() — from file", f"path={p}\ncompany_guess={company}\n\n{text}")
        return text, company

    if re.match(r"^https?://", jd_input):
        print(f"  🌐 Fetching JD from URL: {jd_input}")
        domain  = re.sub(r"https?://(www\.)?", "", jd_input).split("/")[0]
        company = domain.split(".")[0].title()

        html     = _fetch_rendered_html(jd_input)
        raw_text = _raw_text_dump(html)
        text     = extract_jd_from_raw_text(raw_text)

        dbg("fetch_jd() — final extracted JD", f"company_guess={company}\n\n{text}")

        if text.startswith("JD_NOT_FOUND"):
            sys.exit(f"  ❌ Could not find a real JD on this page: {text}\n"
                      f"      Re-check the URL, or paste the JD as plain text/file instead.")

        return text, company

    print("  📝 Using JD as plain text")
    dbg("fetch_jd() — plain text input", jd_input)
    return jd_input, "Company"


# ══════════════════════════════════════════════════════════════════════
# STEP 2 — Analyze JD → archetype + keywords
# ══════════════════════════════════════════════════════════════════════
def analyze_jd(jd_text: str) -> dict:
    print("  🤖 Analyzing JD — choosing template & extracting keywords...")

    prompt = f"""Analyze this job description and return JSON.

Job Description:
{jd_text}

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
- AI_Agent: agents, LangGraph, MCP, tool calling, multi-agent"""

    dbg("analyze_jd() — prompt sent to model", prompt)

    raw = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    ).choices[0].message.content.strip()

    dbg("analyze_jd() — raw model response (before cleanup)", raw)

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()

    dbg("analyze_jd() — cleaned response (fence-stripped)", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        dbg("analyze_jd() — ❌ JSON PARSE FAILED", f"{e}\n\nRaw:\n{raw}")
        sys.exit(f"  ❌ Could not parse analysis JSON: {e}\nRaw:\n{raw}")

    dbg("analyze_jd() — parsed result", json.dumps(result, indent=2))
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
def get_rewrites(tex_content: str, jd_text: str, analysis: dict) -> dict:
    print("  🤖 Getting keyword-injected rewrites...")

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

    dbg("get_rewrites() — extracted SUMMARY (latex)", existing_summary_latex)
    dbg("get_rewrites() — extracted SUMMARY (plain, stripped)",
        f"word_count={summary_wc}\n\n{existing_summary_plain}")
    if not sec_match:
        dbg("get_rewrites() — ⚠️ WARNING", "Summary regex found NOTHING. Check template structure.")

    # Extract bullets as plain text with original index
    item_occurrences = find_all_command_args(tex_content, r"\resumeItem")
    bullets_latex = [content for _, _, content in item_occurrences]
    bullets_plain = [_strip_latex(b) for b in bullets_latex]
    bullet_wcs    = [len(b.split()) for b in bullets_plain]

    dbg("get_rewrites() — extracted BULLETS (latex vs plain)",
        "\n".join(
            f"[{i}] wc={wc}\n     latex: {lat[:120]}{'...' if len(lat) > 120 else ''}\n     plain: {pl}"
            for i, (lat, pl, wc) in enumerate(zip(bullets_latex, bullets_plain, bullet_wcs))
        ),
        max_chars=4000)
    print(f"      🔍 Extracted {len(bullets_latex)} bullets total")
    # Flag bullets that look like they may have been truncated by the non-greedy regex
    suspicious = [i for i, b in enumerate(bullets_latex) if "\\" in b]
    if suspicious:
        dbg("get_rewrites() — ⚠️ POSSIBLE TRUNCATED BULLETS",
            f"Bullets {suspicious} still contain a backslash after extraction — "
            f"the non-greedy \\resumeItem{{(.*?)}} regex may have stopped at an "
            f"inner '}}' (e.g. from \\textbf{{}} or \\href{{}}{{}}) instead of the "
            f"bullet's real closing brace. Inspect these closely.")

    bullets_str = "\n".join(
        f"[{i}] (limit {wc + 5} words) {b}"
        for i, (b, wc) in enumerate(zip(bullets_plain, bullet_wcs))
    )

    prompt = f"""You are a resume expert. Inject JD keywords into resume text.

CRITICAL RULES:
1. Output PLAIN TEXT ONLY — absolutely no LaTeX, no backslashes, no \\textbf, no \\href
2. Each item MUST stay within its word limit — this is a 1-page resume, overflow = broken
3. Only swap existing words for JD vocabulary — never invent new experience
4. Keep all numbers/metrics exactly as-is (35%, 40%, 10,000+)
5. Return null for bullets that don't need changes

JD Keywords to use:
{keywords_str}

Job Description:
{jd_text}

Current Summary (plain text, {summary_wc} words, limit {summary_wc + 5} words):
{existing_summary_plain}

Current Bullets (plain text):
{bullets_str}

Return ONLY this JSON structure (no markdown):
{{
  "new_summary": "plain text summary within word limit",
  "bullets": {{
    "0": "plain text rewrite or null",
    "1": "plain text rewrite or null"
  }}
}}"""

    dbg("get_rewrites() — prompt sent to model", prompt, max_chars=3000)

    raw = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    ).choices[0].message.content.strip()

    dbg("get_rewrites() — raw model response (before cleanup)", raw)

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        dbg("get_rewrites() — ⚠️ first JSON parse failed, attempting backslash fix", raw)
        raw2 = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
        try:
            result = json.loads(raw2)
        except json.JSONDecodeError as e:
            dbg("get_rewrites() — ❌ JSON PARSE FAILED (both attempts)", f"{e}\n\nRaw:\n{raw}")
            sys.exit(f"  ❌ Could not parse rewrite JSON: {e}\nRaw:\n{raw}")

    dbg("get_rewrites() — parsed result (pre word-limit trimming)", json.dumps(result, indent=2))

    new_summary     = result.get("new_summary", "")
    changed_bullets = result.get("bullets", {})

    def trim(text: str, limit: int) -> str:
        words = text.split()
        return " ".join(words[:limit]) if len(words) > limit else text

    if new_summary:
        before = new_summary
        new_summary = trim(new_summary, summary_wc + 5)
        if before != new_summary:
            dbg("get_rewrites() — summary TRIMMED for overflow",
                f"before ({len(before.split())}w): {before}\nafter  ({len(new_summary.split())}w): {new_summary}")

    for k, v in changed_bullets.items():
        if v is None:
            continue
        try:
            idx = int(k)
            if idx < len(bullet_wcs):
                before = v
                changed_bullets[k] = trim(v, bullet_wcs[idx] + 5)
                if before != changed_bullets[k]:
                    dbg(f"get_rewrites() — bullet [{k}] TRIMMED for overflow",
                        f"before ({len(before.split())}w): {before}\nafter  ({len(changed_bullets[k].split())}w): {changed_bullets[k]}")
        except (ValueError, IndexError):
            pass

    changed_cnt = sum(1 for v in changed_bullets.values() if v is not None)
    print(f"      Summary rewritten : {'yes' if new_summary else 'no'}")
    print(f"      Bullets changed   : {changed_cnt} / {len(bullets_latex)}")

    dbg("get_rewrites() — FINAL rewrite decisions",
        f"new_summary: {new_summary}\n\n" +
        "\n".join(f"[{k}] -> {v}" for k, v in changed_bullets.items()))

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
        before_len = len(tex_content)
        tex_content, n = re.subn(
            r"(\\Large \\textbf\{)[^}]+(})",
            lambda m: m.group(1) + _esc(headline) + m.group(2),
            tex_content, count=1
        )
        dbg("apply_changes() — headline swap",
            f"headline='{headline}'\nreplacements_made={n}\nchars_before={before_len} chars_after={len(tex_content)}")
        if n == 0:
            dbg("apply_changes() — ⚠️ WARNING", "Headline regex matched 0 times. Headline NOT updated.")

    # 2. Summary
    new_summary = rewrites.get("new_summary", "")
    if new_summary:
        before_len = len(tex_content)
        tex_content, n = re.subn(
            r"(\\section\{Summary\}.*?\\small\{)(.*?)(\}\s*\\vspace)",
            lambda m: m.group(1) + "\n" + _esc(new_summary) + "\n" + m.group(3),
            tex_content, count=1, flags=re.DOTALL
        )
        dbg("apply_changes() — summary swap",
            f"replacements_made={n}\nchars_before={before_len} chars_after={len(tex_content)}\n\nnew_summary:\n{new_summary}")
        if n == 0:
            dbg("apply_changes() — ⚠️ WARNING", "Summary regex matched 0 times. Summary NOT updated.")

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

        orig_latex = bullets_latex[idx].strip()
        orig_plain = bullets_plain[idx].strip()
        new_plain  = new_plain.strip()

        if not orig_plain or orig_plain == new_plain:
            skipped_same.append(idx)
            continue

        escaped_orig = re.escape(orig_plain[:40])
        new_latex_bullet = re.sub(
            escaped_orig,
            _esc(new_plain[:len(orig_plain)]) if len(new_plain) <= len(orig_plain) + 30
            else _esc(new_plain),
            orig_latex, count=1
        )

        if new_latex_bullet != orig_latex:
            old_item = f"\\resumeItem{{{orig_latex}}}"
            new_item = f"\\resumeItem{{{new_latex_bullet}}}"
            if old_item in tex_content:
                tex_content = tex_content.replace(old_item, new_item, 1)
                applied.append(idx)
            else:
                skipped_nomatch.append(idx)  # substituted locally but not found in full tex
        else:
            skipped_nomatch.append(idx)  # first-40-chars pattern never matched orig_latex

    dbg("apply_changes() — bullet substitution summary",
        f"applied (actually changed in PDF): {applied}\n"
        f"skipped (model said no change needed): {skipped_same}\n"
        f"skipped (pattern didn't match / silently failed): {skipped_nomatch}")

    if skipped_nomatch:
        dbg("apply_changes() — ⚠️ BULLETS THAT SILENTLY FAILED TO APPLY",
            "These bullets were intended to change but the LaTeX-vs-plain-text "
            "matching failed (commonly because \\textbf{}/\\href{}{} sits inside "
            "the first 40 chars, or because the extraction in get_rewrites() "
            "already truncated the bullet at an inner brace). Indexes: "
            f"{skipped_nomatch}")

    return tex_content


# ══════════════════════════════════════════════════════════════════════
# STEP 6 — Compile
# ══════════════════════════════════════════════════════════════════════
def compile_latex(tex_content: str, output_stem: str) -> Path:
    tex_path = OUTPUT_DIR / f"{output_stem}.tex"
    pdf_path = OUTPUT_DIR / f"{output_stem}.pdf"

    tex_path.write_text(tex_content, encoding="utf-8")
    print(f"  📝 LaTeX saved: {tex_path.name}")
    dbg("compile_latex() — final .tex written", f"path={tex_path}\nchars={len(tex_content)}")

    engine = None
    for candidate in ["tectonic", "pdflatex"]:
        try:
            subprocess.run([candidate, "--version"], capture_output=True, check=True)
            engine = candidate
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    dbg("compile_latex() — engine selection", f"engine={engine}")

    if not engine:
        sys.exit("  ❌ No LaTeX engine found. Install pdflatex (MiKTeX) or tectonic.")

    print(f"  ⚙️  Compiling with {engine}...")
    try:
        if engine == "pdflatex":
            args = ["pdflatex", "-interaction=nonstopmode",
                    f"-output-directory={OUTPUT_DIR}", str(tex_path)]
            r1 = subprocess.run(args, capture_output=True, timeout=120)
            r2 = subprocess.run(args, capture_output=True, timeout=120)
            dbg("compile_latex() — pdflatex pass 1 stdout (tail)", r1.stdout.decode(errors="replace")[-1500:])
            dbg("compile_latex() — pdflatex pass 2 stdout (tail)", r2.stdout.decode(errors="replace")[-1500:])
        else:
            r = subprocess.run(["tectonic", "--outdir", str(OUTPUT_DIR), str(tex_path)],
                           capture_output=True, timeout=120, check=True)
            dbg("compile_latex() — tectonic output", r.stdout.decode(errors="replace") + r.stderr.decode(errors="replace"))
    except subprocess.TimeoutExpired:
        sys.exit("  ❌ Compilation timed out")

    if pdf_path.exists():
        kb = pdf_path.stat().st_size / 1024
        pdf_data   = pdf_path.read_bytes().decode("latin-1", errors="replace")
        page_count = len(re.findall(r"/Type\s*/Page[^s]", pdf_data))
        status     = "✅" if page_count == 1 else "⚠️ "
        print(f"  {status} PDF: {pdf_path}  ({kb:.1f} KB, {page_count} page{'s' if page_count != 1 else ''})")
        if page_count > 1:
            print(f"  ⚠️  WARNING: {page_count} pages. Target is 1. Shorten content in template.")
        return pdf_path
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
    print("  career-ops tailor.py  [DEBUG MODE: %s]" % ("ON" if DEBUG else "OFF"))
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
    dbg("main() — raw template loaded", tex_content, max_chars=2000)

    print("\n[4/5] Getting rewrites...")
    rewrites     = get_rewrites(tex_content, jd_text, analysis)
    tex_tailored = apply_changes(tex_content, analysis, rewrites)

    dbg("main() — diff length check",
        f"original chars: {len(tex_content)}\ntailored chars: {len(tex_tailored)}\n"
        f"identical: {tex_content == tex_tailored}")

    print("\n[5/5] Compiling PDF...")
    today       = date.today().strftime("%Y-%m-%d")
    output_stem = f"cv-ashutosh-{company_slug}-{today}"
    pdf_path    = compile_latex(tex_tailored, output_stem)

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  ✅ DONE")
    print(f"  Template : {template_name}")
    print(f"  Archetype: {archetype}")
    print(f"  Keywords : {len(analysis['keywords'])} targeted")
    print(f"  PDF      : {pdf_path}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    if sys.platform == "win32":
        os.startfile(str(pdf_path))


if __name__ == "__main__":
    main()