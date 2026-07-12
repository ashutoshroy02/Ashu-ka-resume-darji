# Career-Ops — AI Resume Tailor

Tired of rewriting your resume for every job? Paste a JD or URL → get a keyword-injected, ATS-optimized, 1-page PDF in seconds. Free. Local. No subscriptions.

Built on top of the open-source [career-ops](https://github.com/santifer/career-ops) CLI, with a Python tailoring pipeline, a Streamlit web UI, a FastAPI backend, a Telegram bot, Docker support for cloud deployment, and a one-click Windows launcher added on top.

---

## What I Built on Top of career-ops

| Addition | File | Description |
|----------|------|-------------|
| Resume Tailor CLI | `tailor.py` | Fetch JD → detect archetype → inject keywords via LLM → compile PDF |
| Debug version | `debug_tailor.py` | Same pipeline with verbose step-by-step logging |
| Streamlit Web UI | `app.py` | Browser UI: paste JD, see live logs, download PDF |
| FastAPI backend | `main.py` | REST API wrapping the tailor pipeline — for headless / cloud use |
| Telegram bot | `telegram_bot.py` | Send a JD to your private Telegram bot, get a PDF back |
| Docker | `dockerfile` + `requirements.txt` | Containerised deployment with tectonic + Playwright; ready for Render |
| One-click launcher | `launch_app.bat` | Double-click to start the Streamlit app on Windows |
| LaTeX templates | `templates/roles/*.tex` | 5 role-specific 1-page templates (Charter font, green headers) |
| Personal CV | `cv.md` | My canonical CV in markdown — tailor reads this at runtime |
| Profile config | `config/profile.yml` | Target roles, location policy, narrative, compensation |
| User data layer | `user_data/` | Gitignored folder for all personal output (PDFs, reports, JDs) |

---

## How the Tailor Pipeline Works

```
JD (URL or text)
      │
      ▼
Fetch & extract    →  Playwright renders JS SPAs; LLM strips nav/footer noise
      │
      ▼
Archetype detect   →  ML_AI / Data_Scientist / Python_Dev / CV_Researcher / AI_Agent
      │
      ▼
Template select    →  picks closest .tex from templates/roles/
      │
      ▼
LLM keyword inject →  Gemini rewrites summary + bullets, word-count bounded
      │
      ▼
LaTeX compile      →  pdflatex / tectonic → 1-page PDF (auto-retry if overflow)
```

Every entry point — CLI, Streamlit, FastAPI, Telegram — runs this same pipeline.

---

## Role Templates

Five LaTeX templates, one per archetype. The tailor auto-selects the best match:

| Template | Best for |
|----------|----------|
| `01_ML_AI_Engineer_Ashutosh.tex` | ML Engineer, AI Engineer, LLM, RAG, NLP, fine-tuning |
| `02_Data_Scientist_Ashutosh.tex` | Data Scientist, Data Analyst, EDA, SQL, Power BI |
| `03_Python_Developer_Ashutosh.tex` | Python Developer, Backend, FastAPI, SDE |
| `04_CV_Researcher_Ashutosh.tex` | Computer Vision, OCR, Research, multimodal |
| `05_AI_Agent_Ashutosh.tex` | AI Agents, LangGraph, MCP, tool-calling, multi-agent |

All templates are 1-page, Charter font, green headers, ATS-optimized (`\pdfgentounicode=1`).

---

## Quick Start (New User)

This repo has my CV, my templates, and my profile out of the box. Replace those three things and everything else just works.

```bash
# 1. Clone
git clone https://github.com/ashutoshroy02/career-ops-cli.git
cd career-ops-cli

# 2. Install Python deps
pip install -r requirements.txt
playwright install chromium

# 3. Install Node deps (for the broader career-ops CLI features)
npm install

# 4. Set your env variables
cp .env.example .env
# Edit .env and fill in:
#   OPENROUTER_API_KEY   — get a free key at https://openrouter.ai
#   GEMINI_API_KEY       — get a free key at https://aistudio.google.com/apikey
#   TAILOR_API_KEY       — any secret string, protects the /tailor endpoint
#   TELEGRAM_BOT_TOKEN   — from @BotFather on Telegram (optional, for bot)
#   TELEGRAM_ALLOWED_USER_ID — your numeric Telegram user ID (optional, for bot)

# 5. Add your data
#    - Replace cv.md with your CV in markdown
#    - Edit config/profile.yml with your name, roles, location
#    - Update the name/contact header in each templates/roles/*.tex

# 6. Install LaTeX (Windows)
#    Download MiKTeX: https://miktex.org/download
#    It auto-installs missing packages on first compile

# 7. Launch — pick any interface:
#    Streamlit UI:   streamlit run app.py
#    Windows:        double-click launch_app.bat
#    FastAPI server: uvicorn main:app --reload
#    Telegram bot:   python telegram_bot.py
#    CLI:            python tailor.py --jd "https://..." --company "Acme"
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | Powers the tailor pipeline. Free key at [openrouter.ai](https://openrouter.ai). Default model: `google/gemini-2.5-flash-lite` |
| `OPENROUTER_MODEL` | No | Override the model. Defaults to `google/gemini-2.5-flash-lite` |
| `GEMINI_API_KEY` | No | For the original `gemini-eval.mjs` script. Free key at [aistudio.google.com](https://aistudio.google.com/apikey) |
| `TAILOR_API_KEY` | For API | Any secret string. Required to call the `/tailor` FastAPI endpoint |
| `TELEGRAM_BOT_TOKEN` | For bot | From @BotFather on Telegram |
| `TELEGRAM_ALLOWED_USER_ID` | For bot | Your numeric Telegram user ID. Comma-separate multiple IDs |

---

## Streamlit Web App

```bash
streamlit run app.py
# or on Windows: double-click launch_app.bat
```

Open `http://localhost:8501`. Paste a JD (text or URL), optionally enter the company name, hit **Generate Tailored PDF**. Live pipeline logs stream in real time. Download or preview the PDF inline when done.

---

## FastAPI Backend

```bash
uvicorn main:app --reload
```

The API runs on `http://localhost:8000`. Every request to `/tailor` must include `X-API-Key`.

```bash
# Health check
curl http://localhost:8000/health

# Tailor a resume
curl -X POST http://localhost:8000/tailor \
  -H "X-API-Key: your_secret" \
  -H "Content-Type: application/json" \
  -d '{"jd": "https://company.com/job/ai-engineer", "company": "Acme"}' \
  --output tailored-resume.pdf
```

Response headers: `X-Page-Count`, `X-Archetype`, `X-Company`.

The API has a built-in one-page retry loop — if the compiled PDF overflows to 2 pages, it tightens the word budget and re-runs up to 4 times.

---

## Telegram Bot

Send your private bot a JD URL or pasted JD text. It runs the full pipeline and sends the PDF back in the same chat. No server needed — runs on long-polling from your laptop.

```bash
pip install python-telegram-bot --upgrade
python telegram_bot.py
```

Setup:
1. Message @BotFather on Telegram → `/newbot` → copy the token → set `TELEGRAM_BOT_TOKEN` in `.env`
2. Message @userinfobot to get your numeric user ID → set `TELEGRAM_ALLOWED_USER_ID` in `.env`
3. Run `python telegram_bot.py` and leave it running

Access is locked to `TELEGRAM_ALLOWED_USER_ID` — anyone else messaging the bot is silently ignored.

---

## CLI

```bash
# From a URL
python tailor.py --jd "https://company.com/job/senior-ml-engineer" --company "Acme"

# From plain text
python tailor.py --jd "We are hiring a Senior AI Engineer..."

# From a saved file
python tailor.py --jd jds/my-job.txt --company "Acme"

# With verbose debug logging
python debug_tailor.py --jd "..."
```

Output goes to `user_data/output/cv-{name}-{company}-{date}.pdf`.

---

## Docker / Deploy to Cloud

The `dockerfile` builds a self-contained image with tectonic (LaTeX) and Playwright/Chromium baked in. Auto-resolves the latest tectonic release at build time.

```bash
# Build
docker build -t career-ops-tailor .

# Run locally
docker run -p 8000:8000 \
  -e OPENROUTER_API_KEY=your_key \
  -e TAILOR_API_KEY=your_secret \
  -e PORT=8000 \
  career-ops-tailor
```

**Deploy to Render:**
1. Push this repo to GitHub
2. New Web Service → connect repo → Docker runtime
3. Set env vars: `OPENROUTER_API_KEY`, `TAILOR_API_KEY`
4. Render sets `PORT` automatically — the `dockerfile` CMD uses it

---

## Adapting This for Your Own CV

1. Replace `cv.md` with your CV in markdown (Summary, Experience, Projects, Skills, Education)
2. Edit `config/profile.yml` — your name, email, target roles, location policy
3. Update the name/contact header at the top of each `.tex` file in `templates/roles/`
4. Optionally rename the template files and update `TEMPLATE_MAP` in `tailor.py` and `debug_tailor.py`

~15 minutes of setup for free tailored resumes from then on.

---

## Project Structure

```
career-ops-cli/
├── app.py                        # Streamlit web UI
├── main.py                       # FastAPI backend (REST API)
├── tailor.py                     # Resume tailor pipeline
├── debug_tailor.py               # Tailor with verbose debug logging
├── telegram_bot.py               # Telegram bot (long-polling, local)
├── dockerfile                    # Docker image (tectonic + Playwright)
├── requirements.txt              # Python dependencies
├── launch_app.bat                # One-click Windows launcher (Streamlit)
├── .env.example                  # Env variable template — copy to .env
├── cv.md                         # My CV — replace with yours
├── config/
│   ├── profile.yml               # My profile config — replace with yours
│   └── profile.example.yml       # Template to start from
├── templates/
│   ├── roles/                    # 5 role-specific LaTeX templates
│   └── cv-template.html          # HTML template (original career-ops)
├── user_data/                    # Personal output (gitignored)
│   ├── output/                   # Generated PDFs
│   ├── reports/                  # Evaluation reports
│   └── jds/                      # Saved job descriptions
├── modes/                        # 14 original career-ops skill modes
├── batch/                        # Batch processing scripts
├── dashboard/                    # Go TUI pipeline viewer
├── data/                         # Application tracker (gitignored)
├── AGENTS.md                     # Agent instructions (all CLIs)
└── CLAUDE.md                     # Claude Code wrapper
```

---

## Tech Stack

- Tailor pipeline: Python, OpenRouter API (Gemini 2.5 Flash Lite — free tier)
- Web UI: Streamlit
- REST API: FastAPI + Uvicorn
- Telegram bot: python-telegram-bot (long-polling)
- Containerisation: Docker (tectonic + Playwright/Chromium)
- JD scraping: Playwright (JS SPAs) + BeautifulSoup fallback
- PDF: tectonic (Docker/Linux) or pdflatex/MiKTeX (Windows local)
- Original CLI: Claude Code / Gemini CLI with custom skill modes
- Dashboard: Go + Bubble Tea + Lipgloss

---

## Original career-ops CLI Features

All original features still work via Claude Code or Gemini CLI:

```bash
claude                              # open Claude Code in this directory
/career-ops "paste JD here"         # full auto-pipeline
/career-ops scan                    # scan 45+ company portals for new listings
/career-ops pdf                     # generate ATS-optimized CV
/career-ops tracker                 # view application status
/career-ops batch                   # batch evaluate multiple offers
```

---

## About

I'm Ashutosh Roy — AI/ML Engineer and published researcher based in Gurugram. I built this because I was tired of manually rewriting my resume for every application.

Portfolio → [mitovoid.netlify.app](https://mitovoid.netlify.app/)  
GitHub → [github.com/ashutoshroy02](https://github.com/ashutoshroy02)

---

## Disclaimer

Local, open-source tool — not a hosted service. Your CV and personal data stay on your machine and go directly to the AI provider you choose. The system never auto-submits applications. Always review AI-generated content before sending. See [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md) for full details.

MIT License. "career-ops" trademark governed by [TRADEMARK.md](TRADEMARK.md).
