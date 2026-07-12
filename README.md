# Career-Ops — AI Resume Tailor

Tired of rewriting your resume for every job? Paste a JD or URL → get a keyword-injected, ATS-optimized, 1-page PDF in seconds. Free. Local. No subscriptions.

Built on top of the open-source [career-ops](https://github.com/santifer/career-ops) CLI, with a Python tailoring pipeline, a Streamlit web UI, and a one-click Windows launcher added on top.

---

## What I Built on Top of career-ops

The original career-ops is a Claude Code-powered job search CLI. I extended it with a Python-native resume tailoring layer:

| Addition | File | Description |
|----------|------|-------------|
| Resume Tailor CLI | `tailor.py` | Fetch JD → detect archetype → inject keywords via LLM → compile PDF |
| Debug version | `debug_tailor.py` | Same pipeline with verbose step-by-step logging |
| Streamlit Web UI | `app.py` | Browser UI: paste JD, see live logs, download PDF |
| One-click launcher | `launch_app.bat` | Double-click to start the app on Windows, no terminal needed |
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
LaTeX compile      →  pdflatex / tectonic → 1-page PDF
```

The Streamlit app wraps this entire pipeline in a browser UI with live log streaming.

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

This system is mine out of the box — my CV, my templates, my profile. To use it for yourself, replace those three things and everything else just works.

```bash
# 1. Clone
git clone https://github.com/ashutoshroy02/career-ops-cli.git
cd career-ops-cli

# 2. Install Python deps
pip install streamlit requests beautifulsoup4 python-dotenv openai playwright pyyaml
playwright install chromium

# 3. Install Node deps (for the broader career-ops CLI features)
npm install

# 4. Set your API key
cp .env.example .env
# Edit .env → set OPENROUTER_API_KEY=your_key_here
# Free key at https://openrouter.ai  (Gemini Flash is free tier)

# 5. Add your data
#    - Replace cv.md with your CV in markdown
#    - Edit config/profile.yml with your name, roles, location
#    - Update the name/contact header in each templates/roles/*.tex

# 6. Install LaTeX (Windows)
#    Download MiKTeX: https://miktex.org/download
#    It auto-installs missing packages on first compile

# 7. Launch
#    Windows: double-click launch_app.bat
#    Terminal: streamlit run app.py
#    CLI:      python tailor.py --jd "https://company.com/job/..." --company "Acme"
```

---

## Running the Web App

```bash
streamlit run app.py
```

Or on Windows, double-click `launch_app.bat`.

Open `http://localhost:8501`. Paste a JD (text or URL), optionally enter the company name, hit **Generate Tailored PDF**. Live pipeline logs stream in real time. When done, download or preview the PDF inline.

---

## Running via CLI

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

## Adapting This for Your Own CV

1. Replace `cv.md` with your CV in markdown (Summary, Experience, Projects, Skills, Education)
2. Edit `config/profile.yml` — your name, email, target roles, location policy
3. Update the name/contact header at the top of each `.tex` file in `templates/roles/`
4. Optionally rename the template files and update the `TEMPLATE_MAP` dict in `tailor.py`

That's it. ~15 minutes of setup for free tailored resumes from then on.

---

## Project Structure

```
career-ops-cli/
├── app.py                        # Streamlit web UI
├── tailor.py                     # Resume tailor pipeline
├── debug_tailor.py               # Tailor with verbose debug logging
├── launch_app.bat                # One-click Windows launcher
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
├── output/                       # PDFs (gitignored)
├── AGENTS.md                     # Agent instructions (all CLIs)
└── CLAUDE.md                     # Claude Code wrapper
```

---

## Tech Stack

- Tailor pipeline: Python, OpenRouter API (Gemini 2.5 Flash Lite — free tier)
- Web UI: Streamlit
- JD scraping: Playwright (JS SPAs) + BeautifulSoup fallback
- PDF: pdflatex (MiKTeX) or tectonic
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

The scanner has 45+ pre-configured companies across Ashby, Greenhouse, Lever, and Wellfound.

---

## About

I'm Ashutosh Roy — AI/ML Engineer and published researcher based in Gurugram. I built this because I was tired of manually rewriting my resume for every application.

Portfolio → [mitovoid.netlify.app](https://mitovoid.netlify.app/)  
GitHub → [github.com/ashutoshroy02](https://github.com/ashutoshroy02)

---

## Disclaimer

Local, open-source tool — not a hosted service. Your CV and personal data stay on your machine and go directly to the AI provider you choose. The system never auto-submits applications. Always review AI-generated content before sending. See [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md) for full details.

MIT License. "career-ops" trademark governed by [TRADEMARK.md](TRADEMARK.md).
