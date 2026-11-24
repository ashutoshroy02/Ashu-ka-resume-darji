# AGENTS.md: notes for coding agents

Resume-Darji is a small Python resume tailor: JD in, tailored LaTeX resume PDF out, via a Telegram bot, a CLI, or the Claude Code skill. See README.md for usage.

## Map

- `tailor.py`: the whole pipeline and the CLI.
  - `fetch_jd` (Playwright + LLM extraction) → `analyze_jd` (base + keywords) → `rank_projects` → `run_tailor` (`fit_projects` → `get_rewrites` → `apply_changes` → `compile_latex`).
  - `main()` / `build()` handle CLI args, `--json` and `--list`.
- `telegram_bot.py`: bot UI on top of `tailor` (session per user, inline buttons, background pre-ranking, ⚡ auto build).
- `run_bot_hidden.py`: pythonw launcher; logging to `logs/bot.log`, prints to `logs/stdout.log`.
- `templates/roles/*.tex`: 3 live bases; `archive/` holds retired ones (not loaded).
- `templates/projects.yml`: project library (`id`, `name`, `tags`, `match`, optional `hide_if`, `latex`).
- `.claude/skills/resume-tailor/SKILL.md`: Claude Code skill (keep `~/.claude/skills/resume-tailor/` in sync when editing).

## Config knobs (tailor.py)

`TEMPLATE_MAP`, `BASE_LABELS`, `DEFAULT_BASE`, `PAGE_LIMIT` (research CV = 2), `FIXED_PICK_BASES` (AI/ML base always uses its own projects, no ranking call), `MIN_PROJECTS`. LLM provider from `.env`: `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` / `LLM_EXTRA_BODY`, falling back to `OPENROUTER_API_KEY` / `OPENROUTER_MODEL`.

## Template rules (the regexes depend on them)

- Headline: `{\Large \textbf{...}}` with no nested braces inside (use `$|$`, not `\textbar{}`).
- Summary: first `\small{...}` after `\section{Summary}`.
- Projects: the first `\section{...Projects...}`; each project is a `\resumeProjectHeading ... \resumeItemListEnd` block. A block's project id comes from `match` substrings in its heading. Base wording wins over the library's.
- Projects shown in another section (e.g. Publications) are hidden from the picker; `hide_if` hides a project when its text appears elsewhere in the base.

## Content rules

- Never invent metrics. Every number must come from the owner and be explainable in an interview.
- After any template edit, compile all 3 bases with their default projects: page targets met, 0 LaTeX errors (`\n! ` in the log), 0 `Overfull` lines.

## Testing

- `python tailor.py --list` (no LLM call).
- Real build: `python tailor.py --jd jds/005-vapi-agent-engineer.md --json`, then delete the test outputs from `user_data/output/`.
- Offline: monkeypatch `tailor.client` / `fit_projects` / `compile_latex`, and point `tailor.OUTPUT_DIR` at a temp folder.

## Operations

- Restart the bot after `.py` or `.env` changes; templates and projects.yml are read on every build.
- Git: branch + PR into `main`. The `gh` CLI must use the `ashutoshroy02` account (`gh auth switch -u ashutoshroy02`).
