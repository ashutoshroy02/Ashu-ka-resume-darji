#!/usr/bin/env python3
"""
tailor.py — Resume tailoring via keyword injection into existing .tex templates.

Approach:
  1. Pick best template out of 5 based on JD archetype
  2. Ask Gemini for plain-text rewrites of Summary + bullets (word-count bounded)
  3. Swap text inside existing LaTeX structure using balanced-brace parser
  4. Compile → PDF

Usage:
    python tailor.py --jd "https://company.com/job/ai-engineer"
    python tailor.py --jd "plain text JD"
    python tailor.py --jd jd.txt
    python tailor.py --jd "..." --company "Acme"
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
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

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
# BALANCED-BRACE PARSER  (Fix #1)
# ══════════════════════════════════════════════════════════════════════
def extract_braced(text: str, start_idx: int) -> tuple[str, int]:
    """
    Given index of '{', return (content_inside_braces, index_after_closing_brace).
    Handles arbitrarily nested braces correctly.
    """
    assert text[start_idx] == "{", f"Expected '{{' at {start_idx}, got {text[start_idx]!r}"
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
    r"""
    Find every occurrence of \command{...} using balanced-brace extraction.
    Returns list of (brace_open_idx, brace_close_idx, content).
    brace_open_idx  = index of '{'
    brace_close_idx = index AFTER closing '}'
    """
    results = []
    search_from = 0
    pattern = re.compile(re.escape(command) + r"\s*\{")
    while True:
        m = pattern.search(tex, search_from)
        if not m:
            break
        open_idx = m.end() - 1          # position of '{'
        content, close_idx = extract_braced(tex, open_idx)
        results.append((open_idx, close_idx, content))
        search_from = close_idx
    return results


# ══════════════════════════════════════════════════════════════════════
# LATEX UTILITIES
# ══════════════════════════════════════════════════════════════════════
def _strip_latex(text: str) -> str:
    """Strip LaTeX commands, keep inner text."""
    # \href{url}{display} → display  (two-arg command)
    text = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", text)
    # single-arg display commands
    text = re.sub(
        r"\\(?:textbf|textit|emph|small|large|Large|"
        r"textasciitilde|textasciicircum|textbackslash)\{([^}]*)\}",
        r"\1", text
    )
    # remaining \cmd{...}
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    # standalone commands
    text = re.sub(r"\\[a-zA-Z]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _word_count(text: str) -> int:
    return len(_strip_latex(text).split())


def _esc(text: str) -> str:
    """Escape special LaTeX chars in plain text (no regex involved)."""
    for ch, repl in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                     ("#", r"\#"), ("_", r"\_")]:
        text = text.replace(ch, repl)
    return text


# ══════════════════════════════════════════════════════════════════════
# STEP 1 — Fetch JD
# ══════════════════════════════════════════════════════════════════════
def fetch_jd(jd_input: str) -> tuple[str, str]:
    p = Path(jd_input)
    if p.exists() and p.is_file():
        print(f"  📄 Reading JD from file: {p}")
        return p.read_text(encoding="utf-8"), p.stem.replace("-", " ").replace("_", " ").title()

    if re.match(r"^https?://", jd_input):
        print(f"  🌐 Fetching JD from URL: {jd_input}")
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        try:
            resp = requests.get(jd_input, headers=headers, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            sys.exit(f"  ❌ Failed to fetch URL: {e}")
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text    = re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n", strip=True)).strip()
        domain  = re.sub(r"https?://(www\.)?", "", jd_input).split("/")[0]
        company = domain.split(".")[0].title()
        return text, company

    print("  📝 Using JD as plain text")
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

    raw = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    ).choices[0].message.content.strip()

    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"  ❌ Could not parse analysis JSON: {e}\nRaw:\n{raw}")


# ══════════════════════════════════════════════════════════════════════
# STEP 3 — Extract summary + bullets using balanced-brace parser (Fix #1)
# ══════════════════════════════════════════════════════════════════════
def extract_resume_parts(tex_content: str) -> dict:
    """
    Extract Summary text and all \resumeItem contents using balanced-brace parser.
    Returns:
      summary_latex  : raw LaTeX content of \small{...} in Summary section
      summary_start  : index of '{' of that \small{
      summary_end    : index after '}' of that \small{
      items          : list of dicts with keys: latex, plain, open_idx, close_idx
    """
    # ── Summary: find \section{Summary} then the first \small{ after it ──
    sec_match = re.search(r"\\section\{Summary\}", tex_content)
    summary_latex = ""
    summary_open  = -1
    summary_close = -1

    if sec_match:
        # Find \small{ starting from after \section{Summary}
        small_pat = re.compile(r"\\small\s*\{")
        sm = small_pat.search(tex_content, sec_match.end())
        if sm:
            open_idx = sm.end() - 1          # index of '{'
            content, close_idx = extract_braced(tex_content, open_idx)
            summary_latex = content
            summary_open  = open_idx
            summary_close = close_idx

    # ── Bullets: all \resumeItem{...} ────────────────────────────────
    item_occurrences = find_all_command_args(tex_content, r"\resumeItem")
    items = []
    for open_idx, close_idx, content in item_occurrences:
        items.append({
            "latex":      content,
            "plain":      _strip_latex(content),
            "open_idx":   open_idx,   # index of '{'
            "close_idx":  close_idx,  # index after '}'
        })

    return {
        "summary_latex":  summary_latex,
        "summary_plain":  _strip_latex(summary_latex),
        "summary_open":   summary_open,
        "summary_close":  summary_close,
        "items":          items,
    }


# ══════════════════════════════════════════════════════════════════════
# STEP 4 — Gemini: plain-text rewrites (word-count bounded)
# ══════════════════════════════════════════════════════════════════════
def get_rewrites(parts: dict, jd_text: str, analysis: dict) -> dict:
    print("  🤖 Getting keyword-injected rewrites...")

    keywords_str = "\n".join(f"- {kw}" for kw in analysis["keywords"])

    summary_plain = parts["summary_plain"]
    summary_wc    = len(summary_plain.split())
    items         = parts["items"]
    bullet_wcs    = [len(it["plain"].split()) for it in items]

    bullets_str = "\n".join(
        f"[{i}] (limit {wc + 5} words) {it['plain']}"
        for i, (it, wc) in enumerate(zip(items, bullet_wcs))
    )

    prompt = f"""You are a resume expert. Inject JD keywords into resume text.

CRITICAL RULES:
1. Output PLAIN TEXT ONLY — no LaTeX, no backslashes, no \\textbf, no \\href
2. Each item MUST stay within its word limit — 1-page resume, overflow = broken
3. Only swap existing words for JD vocabulary — never invent new experience
4. Keep all numbers/metrics exactly (35%, 40%, 10,000+)
5. Return null for bullets that don't need changes

JD Keywords:
{keywords_str}

Job Description:
{jd_text}

Current Summary ({summary_wc} words, limit {summary_wc + 5} words):
{summary_plain}

Current Bullets:
{bullets_str}

Return ONLY this JSON (no markdown):
{{
  "new_summary": "plain text, within word limit",
  "bullets": {{
    "0": "plain text rewrite or null",
    "1": "plain text rewrite or null"
  }}
}}"""

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

    new_summary     = result.get("new_summary", "") or ""
    changed_bullets = result.get("bullets", {}) or {}

    # Trim to word limit (safe — plain text, no LaTeX)
    def trim(text: str, limit: int) -> str:
        words = text.split()
        return " ".join(words[:limit]) if len(words) > limit else text

    if new_summary:
        new_summary = trim(new_summary, summary_wc + 5)

    for k, v in list(changed_bullets.items()):
        if v is None:
            continue
        try:
            idx = int(k)
            if idx < len(bullet_wcs):
                changed_bullets[k] = trim(v, bullet_wcs[idx] + 5)
        except (ValueError, IndexError):
            pass

    changed_cnt = sum(1 for v in changed_bullets.values() if v is not None)
    print(f"      Summary rewritten : {'yes' if new_summary else 'no'}")
    print(f"      Bullets changed   : {changed_cnt} / {len(items)}")

    return {
        "new_summary":    new_summary,
        "changed_bullets": changed_bullets,
    }


# ══════════════════════════════════════════════════════════════════════
# STEP 5 — Apply rewrites back into LaTeX  (Fix #2 + Fix #3)
# ══════════════════════════════════════════════════════════════════════
def apply_changes(tex_content: str, analysis: dict, parts: dict, rewrites: dict) -> str:
    print("  ✏️  Applying changes to template...")
    applied_bullets = 0

    # ── 1. Headline ──────────────────────────────────────────────────
    headline = (analysis.get("headline") or "").strip()
    if headline:
        # \Large \textbf{...}  — single-level braces, safe to regex
        tex_content = re.sub(
            r"(\\Large \\textbf\{)[^}]+(})",
            lambda m: m.group(1) + _esc(headline) + m.group(2),
            tex_content, count=1
        )

    # ── 2. Summary — replace using stored span positions ─────────────
    new_summary = rewrites.get("new_summary", "")
    s_open  = parts["summary_open"]
    s_close = parts["summary_close"]

    if new_summary and s_open >= 0:
        replacement = "\n" + _esc(new_summary) + "\n"
        # Rebuild tex: everything before '{', replacement, everything after '}'
        tex_content = (
            tex_content[: s_open + 1]   # include the '{'
            + replacement
            + tex_content[s_close - 1 :]  # include the closing '}'
        )
        # Recompute item positions after summary replacement (offset shift)
        delta = len(replacement) - len(parts["summary_latex"])
        for it in parts["items"]:
            if it["open_idx"] > s_open:
                it["open_idx"]  += delta
                it["close_idx"] += delta

    # ── 3. Bullets — replace using stored span positions  ────────────
    #    Process in REVERSE order so earlier replacements don't shift
    #    the indices of later ones.
    changed = rewrites.get("changed_bullets", {})
    items   = parts["items"]

    # Build list of (index_in_items, new_plain_text), sorted reverse by position
    to_replace = []
    for idx_str, new_plain in changed.items():
        if new_plain is None:
            continue
        try:
            idx = int(idx_str)
        except ValueError:
            continue
        if idx >= len(items):
            continue
        new_plain = new_plain.strip()
        if new_plain:
            to_replace.append((idx, new_plain))

    # Sort by open_idx descending so we replace from end → start
    to_replace.sort(key=lambda x: items[x[0]]["open_idx"], reverse=True)

    for item_idx, new_plain in to_replace:
        it = items[item_idx]
        open_idx  = it["open_idx"]
        close_idx = it["close_idx"]

        # new content: just the escaped plain text (LaTeX \textbf etc. dropped,
        # but the bullet was plain text to begin with in the original template
        # for the sections Gemini rewrites)
        new_content = _esc(new_plain)

        # Fix #3: use str.replace on the exact span — no re.sub, no group refs
        tex_content = (
            tex_content[: open_idx + 1]    # include '{'
            + new_content
            + tex_content[close_idx - 1 :] # include '}'
        )
        applied_bullets += 1

    print(f"      Bullets applied   : {applied_bullets}")
    return tex_content


# ══════════════════════════════════════════════════════════════════════
# STEP 6 — Compile
# ══════════════════════════════════════════════════════════════════════
def compile_latex(tex_content: str, output_stem: str) -> Path:
    tex_path = OUTPUT_DIR / f"{output_stem}.tex"
    pdf_path = OUTPUT_DIR / f"{output_stem}.pdf"

    tex_path.write_text(tex_content, encoding="utf-8")
    print(f"  📝 LaTeX saved: {tex_path.name}")

    engine = None
    for candidate in ["tectonic", "pdflatex"]:
        try:
            subprocess.run([candidate, "--version"], capture_output=True, check=True)
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
            subprocess.run(args, capture_output=True, timeout=120)
            subprocess.run(args, capture_output=True, timeout=120)
        else:
            subprocess.run(
                ["tectonic", "--outdir", str(OUTPUT_DIR), str(tex_path)],
                capture_output=True, timeout=120, check=True,
            )
    except subprocess.TimeoutExpired:
        sys.exit("  ❌ Compilation timed out")

    if pdf_path.exists():
        kb         = pdf_path.stat().st_size / 1024
        pdf_data   = pdf_path.read_bytes().decode("latin-1", errors="replace")
        page_count = len(re.findall(r"/Type\s*/Page[^s]", pdf_data))
        status     = "✅" if page_count == 1 else "⚠️ "
        print(f"  {status} PDF: {pdf_path}  ({kb:.1f} KB, {page_count} page{'s' if page_count != 1 else ''})")
        if page_count > 1:
            print(f"  ⚠️  WARNING: {page_count} pages. Target is 1. Reduce content in template.")
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

    print("\n[3b] Extracting resume parts (balanced-brace parser)...")
    parts = extract_resume_parts(tex_content)
    print(f"      Summary: {len(parts['summary_plain'].split())} words")
    print(f"      Bullets: {len(parts['items'])} items")

    print("\n[4/5] Getting rewrites from Gemini...")
    rewrites     = get_rewrites(parts, jd_text, analysis)
    tex_tailored = apply_changes(tex_content, analysis, parts, rewrites)

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
