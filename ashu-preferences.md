# Ashu's Preferences & Customizations

Summary of all changes made to the `career-ops` repository to personalize it for Ashutosh Roy.

## 👤 Profile & Identity
- **Candidate Data**: Updated `config/profile.yml` with full name, contact info, and Gurugram location.
- **Target Roles**: Expanded to include AI/ML Engineer, Deep Learning Researcher, Computer Vision Engineer, Data Scientist, and Data Analyst.
- **Location Policy**: 
  - **Priority**: Gurugram > Delhi > Noida > Pune > Bangalore > Hyderabad > Raipur.
  - **Global Remote**: High preference (4.5/5).
  - **Outside India Onsite**: Low preference (2.0/5), but no automatic rejection.

## 📄 CV & Design
- **Default Format**: Switched from `html` to `latex` in `config/profile.yml`.
- **Green Theme**: Replaced `templates/cv-template.tex` with a custom Charter-font, green-header design.
- **ATS Optimization**: Added `\pdfgentounicode=1` to the LaTeX template for machine readability.
- **1-Page Layout**: Tightened vertical margins and section spacing in the template to ensure dense content fits on a single page.

## 🛠️ System & Tools
- **LaTeX Engine**: Installed **MiKTeX** via winget and configured it for headless auto-installation of missing packages.
- **Validation**: Updated `generate-latex.mjs` to support flexible section names like "Experience" and "Projects" instead of just the system defaults.
- **Scanner**: Updated `portals.yml` with keywords for Computer Vision (CV, OCR), Data Science, and Data Analysis.
- **Tracker**: Initialized `data/applications.md` and `data/pipeline.md`.

## 📂 File Summary
| Category | Files Modified |
|----------|----------------|
| **Config** | `config/profile.yml`, `portals.yml` |
| **Templates** | `templates/cv-template.tex` |
| **System** | `generate-latex.mjs` |
| **Data** | `data/applications.md`, `data/pipeline.md`, `modes/_profile.md` |
| **Output** | `output/cv-ashutosh-roy-researcher.pdf` |

*Last Updated: 2026-05-08*

## ⚠️ LaTeX Spacing Rule (CRITICAL — NEVER BREAK)
The **only** proven spacing values that don't overlap are from the original `03_Python_Developer` template:
- **Section title**: `\vspace{-5pt}` before, `\vspace{-5pt}` after titlerule
- **Subheading**: `\vspace{-1pt}` before, `\vspace{-6pt}` after tabular
- **ProjectHeading**: `\item` (no extra vspace), `\vspace{-6pt}` after tabular
- **Geometry**: `top=0.38in, bottom=0.38in`
- **NEVER use** `-10pt`, `-12pt`, or anything more aggressive — it causes text overlap
- To fill page: **add more content**, don't compress spacing
- resume should be in 1 page only
- no compromise in quality.

## 🎯 Role Templates (ALWAYS use these as base)
When tailoring a CV for a JD, **ALWAYS** start by copying the closest matching `.tex` file from `templates/roles/` and modifying it. NEVER generate from scratch.

| JD matches... | Use this base template |
|---|---|
| ML Engineer, AI Engineer, LLM, RAG, NLP | `01_ML_AI_Engineer_Ashutosh.tex` |
| Data Scientist, Data Analyst, Analytics | `02_Data_Scientist_Ashutosh.tex` |
| Python Developer, Backend, SDE | `03_Python_Developer_Ashutosh.tex` |
| Computer Vision, OCR, Researcher | `04_CV_Researcher_Ashutosh.tex` |
| AI Agent, Agentic AI, LangGraph, MCP | `05_AI_Agent_Ashutosh.tex` |

**Workflow**: Copy template → change headline → rewrite summary with JD keywords → swap/reorder projects → adjust skills → compile.
