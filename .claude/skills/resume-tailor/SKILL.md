---
name: resume-tailor
description: >
  Builds Ashutosh's one-page tailored resume PDF for a job, with no UI: runs the local
  Resume-Darji tailor (6 LaTeX base resumes + a project library + an OpenRouter LLM) and
  returns the PDF path as JSON. Use when the user says "make/build/tailor my resume for this
  job", "resume for <job URL>", pastes a job description and wants a resume, or asks which
  base resume or projects fit a JD. Input: a JD URL, a JD file, or pasted JD text.
domain: process
composable: true
yields_to: [voice, density]
---

# resume-tailor

One command builds one resume: it reads the JD, picks a base and projects (unless told),
rewrites bullets around the JD's keywords, fits one page, and compiles the PDF.

## Where things are

- **Repo:** `Z:\TO DO\codes\projects\saas\career_ops\career-ops-cli`. If this skill was
  loaded from inside a clone of the repo, use that clone's root instead.
- **Python:** `C:\Program Files\Python314\python.exe`. Its packages are in user
  site-packages, so don't add `-I`.
- **Needs:** `.env` in the repo root with `OPENROUTER_API_KEY` (see `.env.example`), and
  MiKTeX `pdflatex` on PATH. Never print or copy `.env` values.
- **Output:** `user_data/output/cv-ashutosh-<company>-<date>.pdf` (plus `.tex`). A second run
  for the same company on the same day overwrites it.

## Steps

1. **Get the JD into a form the CLI takes.**
   - A URL: pass it as is.
   - Pasted text: write it to a file in your scratchpad named after the company and role,
     e.g. `acme-ai-engineer.md`, and pass that path. The file name becomes the company
     name; or add `--company "Acme"`. Don't pass long JD text as an argument: Windows
     command lines break on length and quotes.
2. **Base and projects (optional).** By default the AI picks both, which is what the user
   usually wants. Only if the user names a base or projects, run `--list` first (free, no
   LLM call) to get the exact keys and ids, then pass `--base` / `--projects`.
3. **Build** (30-90 s; give the command a timeout of at least 300000 ms):

   ```bash
   cd "/z/TO DO/codes/projects/saas/career_ops/career-ops-cli" && "/c/Program Files/Python314/python.exe" tailor.py --jd "<url-or-file>" --json 2>/dev/null
   ```

   PowerShell:

   ```powershell
   Set-Location "Z:\TO DO\codes\projects\saas\career_ops\career-ops-cli"; & "C:\Program Files\Python314\python.exe" tailor.py --jd "<url-or-file>" --json 2>$null
   ```

   Optional flags: `--base ML_AI|Data_Scientist|Python_Dev|CV_Researcher|AI_Agent|AI_Builder`,
   `--projects id1,id2,id3` (best first; the last ones get dropped if the page overflows),
   `--company "Name"`. To see progress when debugging, drop the `2>/dev/null` / `2>$null`.
4. **Read the JSON on stdout** and report to the user: the PDF path, base, projects kept and
   dropped, and the page count.

## Result JSON

Success (exit code 0):

```json
{
  "ok": true,
  "pdf": "Z:\\...\\user_data\\output\\cv-ashutosh-acme-2026-11-23.pdf",
  "tex": "...same path, .tex",
  "page_count": 1,
  "company": "Acme",
  "base": "AI_Agent",
  "base_label": "AI Agent Engineer",
  "ai_suggested_base": "AI_Agent",
  "archetype_reason": "...",
  "headline": "...",
  "keywords": ["..."],
  "projects_kept": ["skills-for-agents", "exam-helper"],
  "projects_dropped": ["shopping-agent"],
  "projects_ignored": [],
  "project_reason": "...",
  "model": "google/gemini-2.5-flash-lite"
}
```

Failure (exit code 1): `{"ok": false, "error": "..."}`.

## Rules

- **Don't retry in a loop.** Each run costs a few LLM calls. On a 429 / rate-limit error,
  wait about 60 s and retry once; if it fails again, tell the user.
- **`page_count` above 1:** say so plainly. The `CV_Researcher` base is known to compile to
  2 pages.
- **`projects_ignored` not empty:** those ids don't exist; tell the user and show valid ids
  from `--list`.
- Don't edit the templates, `templates/projects.yml` or `tailor.py` unless the user asks.
- Don't open the PDF unless the user asks (`--json` never opens it).
