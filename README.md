# Career-Ops — AI Resume Tailor

[English](README.md) | [Español](README.es.md) | [Português (Brasil)](README.pt-BR.md) | [한국어](README.ko-KR.md) | [日本語](README.ja.md) | [Русский](README.ru.md) | [简体中文](README.cn.md) | [繁體中文](README.zh-TW.md)

<p align="center">
  <a href="https://github.com/ashutoshroy02"><img src="docs/hero-banner.jpg" alt="Career-Ops — AI Resume Tailor" width="800"></a>
</p>

<p align="center">
  <em>Tired of rewriting your resume for every job? I built a pipeline that does it for you.</em><br>
  Paste a JD or URL → get a keyword-injected, ATS-optimized, 1-page PDF in seconds.<br>
  <strong>Free. Local. No subscriptions. Open source.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Built_on-career--ops-black?style=flat" alt="Built on career-ops">
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/LaTeX-008080?style=flat&logo=latex&logoColor=white" alt="LaTeX">
  <img src="https://img.shields.io/badge/OpenRouter-000?style=flat" alt="OpenRouter">
  <img src="https://img.shields.io/badge/Node.js-339933?style=flat&logo=node.js&logoColor=white" alt="Node.js">
  <img src="https://img.shields.io/badge/Go-00ADD8?style=flat&logo=go&logoColor=white" alt="Go">
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=flat&logo=playwright&logoColor=white" alt="Playwright">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT">
  <a href="TRADEMARK.md"><img src="https://img.shields.io/badge/Trademark-Policy-blue.svg" alt="Trademark Policy"></a>
  <a href="https://discord.gg/8pRpHETxa4"><img src="https://img.shields.io/badge/Discord-5865F2?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
</p>

---

<p align="center">
  <img src="docs/demo.gif" alt="Career-Ops Demo" width="800">
</p>

<p align="center"><strong>2 published research papers · 5 role-specific LaTeX templates · 1-click resume tailor</strong></p>

<p align="center"><a href="https://discord.gg/8pRpHETxa4"><img src="https://img.shields.io/badge/Join_the_community-Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a></p>

---

## What Is This

This is a **personalized fork** of the open-source [career-ops](https://github.com/ashutoshroy02/career-ops-cli) job search pipeline. On top of the original CLI system, I built:

- **`tailor.py`** — a fully automated resume tailoring pipeline: reads a JD (URL or plain text), picks the best matching LaTeX template, asks an LLM (via OpenRouter/Gemini) to inject keywords, and compiles a PDF
- **`app.py`** — a Streamlit web UI wrapping the tailor pipeline, with live log streaming, inline PDF preview, and one-click download
- **`launch_app.bat`** — a Windows batch file to launch the Streamlit app with a double-click, no terminal needed
- **5 role-specific LaTeX templates** in `templates/roles/` — one per target archetype, each pre-tuned to a 1-page layout
- **Personal data files** (`cv.md`, `config/profile.yml`, `modes/_profile.md`) — my own CV and profile, which the pipeline reads at tailoring time

> This setup is mine. But the system is built so **any new user can clone it, swap in their own data, and get free tailored resumes**. No SaaS, no subscriptions, just your own API key.

---

## How I Built This

The original `career-ops` is a CLI-first, Claude Code-powered job search automation system. I took it and extended it with a Python-native tailoring layer:

```
You paste a JD (text or URL)
        │
        ▼
┌──────────────────────┐
│  JD Fetch & Extract  │  Playwright renders JS SPAs; LLM strips nav/footer noise
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  Archetype Detection │  Classifies: ML_AI / Data_Scientist / Python_Dev /
│  + Keyword Extract   │             CV_Researcher / AI_Agent
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  Template Selection  │  Picks closest .tex from templates/roles/
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  LLM Keyword Inject  │  Gemini rewrites summary + bullets, word-count bounded
│  (OpenRouter API)    │  to never overflow the 1-page layout
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  LaTeX Compile       │  pdflatex / tectonic → 1-page PDF
└──────────┬───────────┘
           │
        PDF out
```

The Streamlit app wraps this entire pipeline with a browser UI — paste JD, hit button, see live logs, download PDF.

---

## What I Added on Top of career-ops

| What | File(s) | Description |
|------|---------|-------------|
| **Resume Tailor CLI** | `tailor.py` | Full pipeline: fetch JD → detect archetype → inject keywords → compile PDF |
| **Debug Version** | `debug_tailor.py` | Same pipeline with verbose step-by-step logging at every stage |
| **Streamlit Web UI** | `app.py` | Browser UI with live log streaming, inline PDF preview, download button |
| **One-click launcher** | `launch_app.bat` | Double-click to start the Streamlit app on Windows, no terminal needed |
| **LaTeX Templates** | `templates/roles/*.tex` | 5 role-specific 1-page templates with green-header Charter font design |
| **Personal CV** | `cv.md` | My canonical CV in markdown — the source of truth for all evaluations |
| **Profile Config** | `config/profile.yml` | My target roles, location policy, narrative, and compensation preferences |
| **User Data Layer** | `user_data/` | Gitignored folder holding all personal output (PDFs, reports, JDs) |

---

## Role Templates

Five LaTeX templates, each pre-tuned for a different archetype. The tailor auto-selects the best match:

| Template | Best For |
|----------|----------|
| `01_ML_AI_Engineer_Ashutosh.tex` | ML Engineer, AI Engineer, LLM, RAG, NLP, fine-tuning |
| `02_Data_Scientist_Ashutosh.tex` | Data Scientist, Data Analyst, EDA, SQL, Power BI |
| `03_Python_Developer_Ashutosh.tex` | Python Developer, Backend, FastAPI, SDE |
| `04_CV_Researcher_Ashutosh.tex` | Computer Vision, OCR, Research, multimodal |
| `05_AI_Agent_Ashutosh.tex` | AI Agents, LangGraph, MCP, tool-calling, multi-agent |

All templates share the same 1-page layout rules (Charter font, green headers, `top=0.38in, bottom=0.38in`) and compile clean with pdflatex/MiKTeX.

---

## Quick Start (New User)

> **You'll replace my data files with yours. Everything else just works.**

```bash
# 1. Clone
git clone https://github.com/ashutoshroy02/career-ops-cli.git
cd career-ops-cli

# 2. Install Python dependencies
pip install streamlit requests beautifulsoup4 python-dotenv openai playwright pyyaml
playwright install chromium   # for JS-rendered job pages

# 3. Install Node dependencies (for the broader career-ops CLI)
npm install

# 4. Set up your API key
cp .env.example .env
# Edit .env → set OPENROUTER_API_KEY=your_key_here
# Get a free key at https://openrouter.ai  (Gemini Flash is free tier)

# 5. Add YOUR data
#    Replace cv.md with your own CV in markdown
#    Edit config/profile.yml with your name, roles, location

# 6. Rename the templates to your name (optional but recommended)
#    Edit templates/roles/*.tex → change the name/contact header section

# 7. Launch
#    Option A — double-click launch_app.bat  (Windows)
#    Option B — terminal: streamlit run app.py
#    Option C — CLI: python tailor.py --jd "https://company.com/job/..." --company "Acme"
```

You'll have a working resume tailor running on your machine in under 10 minutes.

---

## Running the Web App

```bash
streamlit run app.py
# or on Windows: double-click launch_app.bat
```

Open `http://localhost:8501`. Paste a JD (or a direct job URL). Optionally enter the company name. Hit **Generate Tailored PDF**.

You'll see live pipeline logs as it runs, then an inline preview and download button when done.

---

## Running via CLI

```bash
# From a URL
python tailor.py --jd "https://company.com/job/senior-ml-engineer" --company "Acme"

# From plain text
python tailor.py --jd "We are hiring a Senior AI Engineer..."

# From a file
python tailor.py --jd jds/my-job.txt --company "Acme"

# Debug mode (verbose step-by-step logs)
python debug_tailor.py --jd "..."
```

Output goes to `user_data/output/cv-{name}-{company}-{date}.pdf`.

---

## Adapting This for Your Own CV

This system is built around my CV and templates, but swapping it out for yours takes about 15 minutes:

1. **Replace `cv.md`** with your CV in clean markdown (Summary, Experience, Projects, Skills, Education)
2. **Edit `config/profile.yml`** — your name, email, target roles, location policy
3. **Update the `.tex` templates** in `templates/roles/` — change the name/contact header at the top of each file
4. **Rename template files** if you want (update the `TEMPLATE_MAP` dict in `tailor.py` / `debug_tailor.py` to match)
5. That's it. Run the app and paste your first JD.

> If you don't have LaTeX installed, install [MiKTeX](https://miktex.org/download) on Windows. It auto-installs missing packages on first compile.

---

## Original career-ops Features (Still Fully Available)

This is built on top of the full career-ops system. All original features still work via Claude Code / Gemini CLI:

| Feature | Description |
|---------|-------------|
| **Auto-Pipeline** | Paste a URL, get a full evaluation + PDF + tracker entry |
| **6-Block Evaluation** | Role summary, CV match, level strategy, comp research, personalization, interview prep (STAR+R) |
| **Interview Story Bank** | Accumulates STAR+Reflection stories across evaluations |
| **Negotiation Scripts** | Salary negotiation frameworks, geographic discount pushback |
| **Portal Scanner** | 45+ companies pre-configured + custom queries across Ashby, Greenhouse, Lever, Wellfound |
| **Batch Processing** | Parallel evaluation with `claude -p` workers |
| **Dashboard TUI** | Terminal UI to browse, filter, and sort your pipeline (Go + Bubble Tea) |
| **Human-in-the-Loop** | AI evaluates and recommends, you decide. Never auto-submits. |

```bash
# Claude Code (original CLI interface)
claude
/career-ops "Senior AI Engineer at Anthropic..."
/career-ops scan
/career-ops pdf
/career-ops tracker
```

---

## Pre-configured Portals

The scanner comes with **45+ companies** and **19 search queries** across major job boards:

**AI Labs:** Anthropic, OpenAI, Mistral, Cohere, LangChain, Pinecone  
**Voice AI:** ElevenLabs, PolyAI, Parloa, Hume AI, Deepgram, Vapi, Bland AI  
**AI Platforms:** Retool, Airtable, Vercel, Temporal, Glean, Arize AI  
**Contact Center:** Ada, LivePerson, Sierra, Decagon, Talkdesk, Genesys  
**Enterprise:** Salesforce, Twilio, Gong, Dialpad  
**LLMOps:** Langfuse, Weights & Biases, Lindy, Cognigy, Speechmatics  
**Automation:** n8n, Zapier, Make.com  

**Job boards searched:** Ashby, Greenhouse, Lever, Wellfound, Workable, RemoteFront

---

## Project Structure

```
career-ops-cli/
├── app.py                       # ★ Streamlit web UI (NEW)
├── tailor.py                    # ★ Resume tailor pipeline (NEW)
├── debug_tailor.py              # ★ Tailor with verbose debug logging (NEW)
├── launch_app.bat               # ★ One-click Windows launcher (NEW)
├── cv.md                        # ★ My CV (replace with yours)
├── config/profile.yml           # ★ My profile config (replace with yours)
├── templates/roles/             # ★ 5 role-specific LaTeX templates (NEW)
│   ├── 01_ML_AI_Engineer_Ashutosh.tex
│   ├── 02_Data_Scientist_Ashutosh.tex
│   ├── 03_Python_Developer_Ashutosh.tex
│   ├── 04_CV_Researcher_Ashutosh.tex
│   └── 05_AI_Agent_Ashutosh.tex
├── user_data/                   # ★ Personal output folder (gitignored)
│   ├── output/                  # Generated PDFs
│   ├── reports/                 # Evaluation reports
│   └── jds/                     # Saved job descriptions
├── AGENTS.md                    # Canonical agent instructions (all CLIs)
├── CLAUDE.md                    # Claude Code wrapper
├── modes/                       # 14 original career-ops skill modes
├── batch/                       # Batch processing scripts
├── dashboard/                   # Go TUI pipeline viewer
├── data/                        # Application tracker (gitignored)
├── reports/                     # Reports (gitignored)
├── output/                      # PDFs (gitignored)
├── fonts/                       # Space Grotesk + DM Sans
└── docs/                        # Setup, customization, architecture
```

Items marked ★ are additions/customizations on top of the original career-ops.

---

## Tech Stack

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![LaTeX](https://img.shields.io/badge/LaTeX-008080?style=flat&logo=latex&logoColor=white)
![OpenRouter](https://img.shields.io/badge/OpenRouter_API-000?style=flat)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=flat&logo=playwright&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-339933?style=flat&logo=node.js&logoColor=white)
![Go](https://img.shields.io/badge/Go-00ADD8?style=flat&logo=go&logoColor=white)

- **Tailor pipeline**: Python + OpenRouter API (Gemini 2.5 Flash Lite by default — free tier)
- **Web UI**: Streamlit with live subprocess log streaming
- **PDF generation**: pdflatex (MiKTeX) or tectonic
- **JD scraping**: Playwright (JS-rendered SPAs) + BeautifulSoup fallback
- **Original CLI**: Claude Code / Gemini CLI with custom skill modes
- **Dashboard**: Go + Bubble Tea + Lipgloss (Catppuccin Mocha theme)

---

## Also Open Source by Me

- **[skills-for-agents](https://github.com/ashutoshroy02/skills-for-agents)** — An open-source ecosystem of composable, conflict-free instruction sets for multi-task LLM agents, implementing the Skills Interoperability Protocol (SIP).
- **[InterviewPrep](https://github.com/ashutoshroy02/InterviewPrep)** — Full-stack interview prep platform with 700+ curated questions, company tracks (FAANG, OpenAI, NVIDIA), and a 12-week roadmap. Fork it and make it yours.

---

## About Me

I'm Ashutosh Roy — AI/ML Engineer, Deep Learning Researcher, and Full Stack Developer based in Gurugram. I built this tailoring layer because I was tired of manually rewriting my resume for every application.

Published researcher (RECCAP 2026, IIT Palakkad — first author; co-author with IIT Delhi on multimodal archaeological search). Work spans LLM fine-tuning (QLoRA), RAG pipelines, autonomous agents (LangGraph, MCP), speech/affective computing, and computer vision.

Portfolio → [mitovoid.netlify.app](https://mitovoid.netlify.app/)  
GitHub → [github.com/ashutoshroy02](https://github.com/ashutoshroy02)

---

## Star History

<a href="https://www.star-history.com/?repos=ashutoshroy02%2Fcareer-ops-cli&type=timeline&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=ashutoshroy02/career-ops-cli&type=timeline&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=ashutoshroy02/career-ops-cli&type=timeline&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=ashutoshroy02/career-ops-cli&type=timeline&legend=top-left" />
 </picture>
</a>

---

## Disclaimer

**career-ops is a local, open-source tool — NOT a hosted service.** By using this software, you acknowledge:

1. **You control your data.** Your CV, contact info, and personal data stay on your machine and are sent directly to the AI provider you choose (OpenRouter, Anthropic, Google, etc.). No data is collected or stored by this project.
2. **You control the AI.** The system never submits applications automatically. AI-generated content may be inaccurate — always review before sending.
3. **You comply with third-party ToS.** Use in accordance with the Terms of Service of job portals you interact with. Do not use this to spam employers.
4. **No guarantees.** Evaluations are recommendations, not truth. The authors are not liable for employment outcomes or any other consequences.

See [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md) for full details. Provided under the [MIT License](LICENSE) "as is", without warranty.

---

## Contributors

<a href="https://github.com/ashutoshroy02/career-ops-cli/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=ashutoshroy02/career-ops-cli" />
</a>

Got hired using career-ops? [Share your story!](https://github.com/ashutoshroy02/career-ops-cli/issues/new?template=i-got-hired.yml)

---

## License & Trademark

The code is licensed under [MIT](LICENSE). The "career-ops" name and brand are governed by the [Trademark Policy](TRADEMARK.md) — permissive for community use, reserved for commercial product naming and endorsement.

---

## Let's Connect

[![Portfolio](https://img.shields.io/badge/mitovoid.netlify.app-000?style=for-the-badge&logo=safari&logoColor=white)](https://mitovoid.netlify.app/)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/ashutosh-roy-02)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/ashutoshroy02)
[![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/8pRpHETxa4)
[![Email](https://img.shields.io/badge/Email-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:ashu2003roy@gmail.com)
