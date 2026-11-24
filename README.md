# Resume-Darji: AI Resume Tailor

Send a job description (URL or text) and get back a tailored, ATS-friendly LaTeX resume PDF. It runs locally through a Telegram bot, a CLI, or Claude Code. Your data stays on your machine; only the JD and resume text go to the LLM provider you choose.

---

## How it works

```
JD (URL, file or text)
      │
      ▼
Fetch & extract    →  Playwright renders JS job pages; the LLM strips nav/footer noise
      │
      ▼
Pick a base        →  the LLM picks one of 3 base resumes (AI/ML Engineer, AI-First Builder, Research CV)
      │
      ▼
Pick projects      →  from 16 projects in templates/projects.yml (fixed for AI/ML, AI-ranked for the others)
      │
      ▼
Fit the page       →  drop the last project until the untailored resume fits its page target
      │
      ▼
Keyword rewrite    →  the LLM rewrites the summary and bullets for the JD, word-count bounded
      │
      ▼
Compile            →  pdflatex → PDF; tighten word limits and retry if it overflows
```

The bot, the CLI and the Claude Code skill all run this same pipeline in `tailor.py`.

## Base resumes

| Template | Best for | Pages |
|----------|----------|-------|
| `07_AI_ML_Engineer_Ashutosh.tex` | Default: AI / ML / LLM / agent / backend / SDE roles | 1 |
| `06_AI_Builder_Ashutosh.tex` | Full-stack / product / founding engineer roles | 1 |
| `04_CV_Researcher_Ashutosh.tex` | Research roles, publications | 2 |

- The AI/ML base always pre-picks its own projects (Saylo, Exam-Helper, Chronic Compounder); see `FIXED_PICK_BASES` in `tailor.py`.
- Page targets per base: `PAGE_LIMIT` in `tailor.py`.
- Older bases (ML/AI, Data Scientist, Python/Backend, AI Agent) are in `templates/roles/archive/`.

## Setup (Windows)

1. Python 3.14 and the packages: `pip install -r requirements.txt`, then `playwright install chromium`
2. MiKTeX (`pdflatex` on PATH): https://miktex.org/download
3. Copy `.env.example` to `.env` and fill it in:
   - an LLM key: `OPENROUTER_API_KEY`, or the `LLM_*` settings (e.g. Groq's free tier)
   - `TELEGRAM_BOT_TOKEN` (from @BotFather) and `TELEGRAM_ALLOWED_USER_ID` (from @userinfobot)

### LLM provider

| Setting | Meaning |
|---|---|
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Default provider. Model default: `google/gemini-2.5-flash-lite` |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Any OpenAI-compatible API instead, e.g. Groq: `https://api.groq.com/openai/v1`, `qwen/qwen3.8-27b` |
| `LLM_EXTRA_BODY` | Extra request fields as JSON. Qwen on Groq: `{"reasoning_effort": "none"}` (thinking off) |

## Telegram bot

```bash
python telegram_bot.py          # with a console
pythonw run_bot_hidden.py       # hidden, logs to logs/bot.log and logs/stdout.log
```

Send the bot a JD URL or text. Pick a base (the AI's pick is marked ⭐), tick projects, then 🚀 Build. Or tap **⚡ Just build it** to let the AI pick everything. Only `TELEGRAM_ALLOWED_USER_ID` can use it; everyone else is ignored. Restart the bot after changing `.py` files or `.env`. Template and project edits apply on the next build.

## CLI

```bash
python tailor.py --jd "https://company.com/jobs/123"          # URL
python tailor.py --jd jds/005-vapi-agent-engineer.md            # file (name = company)
python tailor.py --jd jds/my-job.md --company "Acme"

# No UI (scripts / Claude Code): progress on stderr, one JSON result on stdout
python tailor.py --jd jds/my-job.md --json
python tailor.py --jd jds/my-job.md --json --base AI_ML_Engineer --projects saylo,exam-helper
python tailor.py --list       # base keys and project ids as JSON (no LLM call)
```

PDFs go to `user_data/output/`.

## Claude Code skill

`.claude/skills/resume-tailor/SKILL.md` teaches Claude Code to build a resume from a JD URL or pasted text with the `--json` mode. Copy the folder to `~/.claude/skills/` to use it from any folder.

## Files

| Path | What it is |
|---|---|
| `tailor.py` | The pipeline and the CLI |
| `telegram_bot.py` | Telegram bot (long polling, no server) |
| `run_bot_hidden.py` | Hidden launcher with log files |
| `templates/roles/*.tex` | Base resumes |
| `templates/projects.yml` | Project library (add a project = add an entry) |
| `jds/` | Sample JDs for test builds |
| `AGENTS.md` | Notes for coding agents working on this repo |

## Origin

This started from a copy of [career-ops](https://github.com/career-ops-hq/career-ops) (MIT, see `LICENSE`). The career-ops job-search tooling was removed to keep only the tailor and bot; the full original copy is preserved at the git tag `before-cleanup`.

## About

Ashutosh Roy, AI/ML Engineer. Portfolio: [mitovoid.netlify.app](https://mitovoid.netlify.app/) · GitHub: [ashutoshroy02](https://github.com/ashutoshroy02)

Always review generated resumes before sending; the tool never submits applications.
