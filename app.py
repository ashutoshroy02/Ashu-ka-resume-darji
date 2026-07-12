"""
app.py — Minimal Streamlit UI wrapper for debug_tailor.py
Run: streamlit run app.py
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import streamlit as st

ROOT       = Path(__file__).parent
SCRIPT     = ROOT / "debug_tailor.py"          # <-- was tailor.py
OUTPUT_DIR = ROOT / "user_data" / "output"

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

# ─── Page config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Career-Ops Tailor",
    page_icon="📄",
    layout="centered",
)

# ─── Minimal CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { max-width: 720px; padding-top: 2rem; }
    .stTextArea textarea { font-size: 0.9rem; }
    .log-box {
        background: #0e1117;
        color: #c9d1d9;
        font-family: monospace;
        font-size: 0.8rem;
        padding: 1rem;
        border-radius: 6px;
        white-space: pre-wrap;
        max-height: 320px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# ─── Header ────────────────────────────────────────────────────────────
st.title("📄 Ashu ka resume Darji")
st.caption("Paste a JD or URL → get a tailored PDF resume in seconds.")
st.divider()

# ─── Inputs ────────────────────────────────────────────────────────────
jd_input = st.text_area(
    "Job Description",
    placeholder="Paste the full JD text here, or enter a URL (https://...)",
    height=200,
)

company = st.text_input(
    "Company name  *(optional — used in filename)*",
    placeholder="e.g. Sparrow, Google, Razorpay",
)

run_btn = st.button("⚡ Generate Tailored PDF", type="primary", use_container_width=True)

# ─── Run ───────────────────────────────────────────────────────────────
if run_btn:
    jd_input_stripped = jd_input.strip()

    if not jd_input_stripped:
        st.error("Please enter a JD or URL.")
        st.stop()

    if not SCRIPT.exists():
        st.error(f"❌ Could not find {SCRIPT.name} next to app.py. "
                  f"Make sure both files are in the same folder.")
        st.stop()

    is_url = bool(_URL_RE.match(jd_input_stripped))
    jd_file = None  # only set if we actually create a temp file

    if is_url:
        # Pass the URL straight through — do NOT wrap it in a file, or
        # fetch_jd() will see an existing file path first and just read
        # the URL string back as literal text instead of fetching it.
        jd_arg = jd_input_stripped
    else:
        # Plain-text JD: write to a temp file to avoid shell-quoting issues
        # with long/multiline text.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                         delete=False, encoding="utf-8") as f:
            f.write(jd_input_stripped)
            jd_file = f.name
        jd_arg = jd_file

    cmd = [sys.executable, str(SCRIPT), "--jd", jd_arg]
    if company.strip():
        cmd += ["--company", company.strip()]

    log_placeholder = st.empty()
    spinner_placeholder = st.empty()

    with spinner_placeholder:
        with st.spinner("Running tailoring pipeline..."):
            log_lines = []
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,          # line-buffered so logs stream live
                cwd=str(ROOT),
            )
            for line in proc.stdout:
                log_lines.append(line.rstrip())
                log_placeholder.markdown(
                    f'<div class="log-box">' + "\n".join(log_lines) + "</div>",
                    unsafe_allow_html=True,
                )
            proc.wait()

    if jd_file:
        Path(jd_file).unlink(missing_ok=True)

    # ─── Result ────────────────────────────────────────────────────────
    st.divider()

    if proc.returncode == 0:
        # Find latest PDF in output dir
        pdfs = sorted(OUTPUT_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        if pdfs:
            latest_pdf = pdfs[0]
            pdf_bytes  = latest_pdf.read_bytes()

            st.success(f"✅ Done — **{latest_pdf.name}**")

            import base64
            b64 = base64.b64encode(pdf_bytes).decode()

            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_bytes,
                    file_name=latest_pdf.name,
                    mime="application/pdf",
                    use_container_width=True,
                )
            with col2:
                st.markdown(
                    f'<a href="data:application/pdf;base64,{b64}" '
                    f'target="_blank">🔗 Open in browser</a>',
                    unsafe_allow_html=True,
                )

            # Inline PDF preview
            st.markdown("### Preview")
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{b64}" '
                f'width="100%" height="700px" style="border:none;border-radius:6px;"></iframe>',
                unsafe_allow_html=True,
            )
        else:
            st.warning("Pipeline finished but no PDF found in output/")
    else:
        st.error("❌ Pipeline failed. Check the log above.")