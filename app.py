"""
app.py
------
MediAudit – Streamlit Dashboard (v2)

Features
--------
• Two input modes  : Upload File  |  Capture from Camera
• Two-step flow    : Extract Details → Cross Check
• Generalised policy baseline (policy_engine.py) + optional uploaded policy
• Enriched output  : eligibility verdict, risk scores, next steps, line-item table
• CSV download

Run:
    streamlit run app.py
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import pandas as pd
import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────
st.set_page_config(
    page_title="MediAudit – Claim Validator",
    page_icon="🏥",
    layout="wide",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── Colour maps ───────────────────────────────────────────────────────────
STATUS_COLOURS: dict[str, str] = {
    "✅": "#d4edda",
    "⚠️": "#fff3cd",
    "❌": "#f8d7da",
}

RISK_COLOURS: dict[str, str] = {
    "Low":      "#28a745",
    "Medium":   "#fd7e14",
    "High":     "#dc3545",
    "Critical": "#7b0000",
}

VERDICT_COLOURS: dict[str, str] = {
    "Eligible":           "#d4edda",
    "Partially Eligible": "#fff3cd",
    "Not Eligible":       "#f8d7da",
}

VERDICT_ICONS: dict[str, str] = {
    "Eligible":           "✅",
    "Partially Eligible": "⚠️",
    "Not Eligible":       "❌",
}


# ── Helpers ───────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    try:
        return st.secrets["GROQ_API_KEY"]
    except (KeyError, FileNotFoundError):
        st.error(
            "❌ **GROQ_API_KEY not found.**\n\n"
            "Add it to `.streamlit/secrets.toml`:\n"
            "```toml\nGROQ_API_KEY = \"gsk_your_key_here\"\n```"
        )
        st.stop()


def _available_policies() -> list[Path]:
    return sorted(DATA_DIR.glob("*.pdf"))


def _colour_row(row: pd.Series) -> list[str]:
    status  = str(row.get("Status", "")).strip()
    bg      = STATUS_COLOURS.get(status, "#1e1e1e")
    # Always force dark text so it's readable on both light bg and fallback dark bg
    fg      = "#111111" if status in STATUS_COLOURS else "#ffffff"
    return [f"background-color: {bg}; color: {fg}"] * len(row)


def _risk_badge(label: str) -> str:
    colour = RISK_COLOURS.get(label, "#6c757d")
    return (
        f'<span style="background:{colour};color:white;padding:2px 8px;'
        f'border-radius:4px;font-size:0.8em;font-weight:bold">{label}</span>'
    )


def _image_bytes_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


# ── Session state init ────────────────────────────────────────────────────

def _init_state() -> None:
    defaults = {
        "bill_bytes": None,
        "bill_filename": None,
        "bill_text": None,
        "audit_result": None,
        "input_mode": "Upload File",
        "camera_active": False,
        "uploaded_file_id": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    _init_state()

    # ── Sidebar ───────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            "<h2 style='text-align:center'>🏥 MediAudit</h2>"
            "<p style='text-align:center;color:grey'>Insurance Claim Validator</p>",
            unsafe_allow_html=True,
        )
        st.divider()

        # Policy selector (optional uploaded PDF)
        policies = _available_policies()
        if not policies:
            st.info("No PDFs in `./data/`. Generalised baseline policy will be used.")
            policy_choice: Path | None = None
        else:
            policy_names = ["— Use generalised baseline only —"] + [p.name for p in policies]
            selected = st.selectbox("📋 Insurer Policy (optional)", policy_names)
            policy_choice = (
                None if selected.startswith("—")
                else DATA_DIR / selected
            )

        st.divider()

        # Show built-in policy summary
        with st.expander("📖 View Built-in Policy Rules", expanded=False):
            from processors.policy_engine import get_policy_markdown  # noqa: PLC0415
            st.markdown(get_policy_markdown())

        st.divider()
        st.markdown(
            "**Flow**\n"
            "1. Upload or capture the bill\n"
            "2. Click **Extract Details**\n"
            "3. Click **Cross Check**\n"
            "4. Review the Comparison Spec Sheet"
        )

    # ── Main header ───────────────────────────────────────────────────────
    st.title("🏥 MediAudit – Claim Validator")
    st.caption(
        "Upload or capture a medical bill, extract its details, then cross-check "
        "against insurance policy rules."
    )
    st.divider()

    # ── STEP 1 : Input ────────────────────────────────────────────────────
    st.subheader("Step 1 — Provide Medical Bill")

    tab_upload, tab_camera = st.tabs(["📁 Upload File", "📷 Capture from Camera"])

    with tab_upload:
        uploaded = st.file_uploader(
            "Upload a medical bill (PDF, PNG, JPG, TIFF)",
            type=["pdf", "png", "jpg", "jpeg", "tiff"],
            key="file_uploader",
        )
        if uploaded:
            # Only reset extracted text when a NEW file is uploaded.
            # Comparing file_id avoids clearing bill_text on every rerun
            # while the same file sits in the uploader widget.
            current_id = st.session_state.get("uploaded_file_id")
            new_id     = uploaded.file_id

            if new_id != current_id:
                # Genuinely new file — read bytes and reset downstream state
                st.session_state.bill_bytes      = uploaded.read()
                st.session_state.bill_filename   = uploaded.name
                st.session_state.bill_text       = None
                st.session_state.audit_result    = None
                st.session_state.uploaded_file_id = new_id

            # Preview (always show for whichever file is loaded)
            if uploaded.name.lower().endswith(".pdf"):
                st.info(f"📄 PDF loaded: **{uploaded.name}**")
            else:
                st.image(
                    st.session_state.bill_bytes,
                    caption=f"Preview – {uploaded.name}",
                    width="stretch",
                )

    with tab_camera:
        st.markdown("Click **Open Camera** when you're ready to capture the bill.")

        if not st.session_state.get("camera_active", False):
            # Show captured image preview if one already exists
            if (
                st.session_state.bill_bytes is not None
                and st.session_state.bill_filename == "camera_capture.jpg"
            ):
                st.image(
                    st.session_state.bill_bytes,
                    caption="📸 Last capture – click Open Camera to retake",
                    width="stretch",
                )

            if st.button("📷 Open Camera", key="open_camera_btn", type="primary"):
                st.session_state.camera_active = True
                st.rerun()
        else:
            col_close, _ = st.columns([1, 5])
            with col_close:
                if st.button("✖ Close", key="close_camera_btn"):
                    st.session_state.camera_active = False
                    st.rerun()

            camera_image = st.camera_input(
                "Point at the bill and click the shutter ⬤",
                key="camera_widget",
            )

            if camera_image:
                img_bytes = camera_image.getvalue()
                st.session_state.bill_bytes    = img_bytes
                st.session_state.bill_filename = "camera_capture.jpg"
                st.session_state.bill_text     = None
                st.session_state.audit_result  = None
                st.session_state.camera_active = False   # auto-close after capture
                st.rerun()  # rerun so preview shows in inactive state above


    # ── STEP 2 : Extract Details ──────────────────────────────────────────
    st.divider()
    st.subheader("Step 2 — Extract Details")

    has_bill = st.session_state.bill_bytes is not None

    if not has_bill:
        st.info("👆 Upload or capture a bill above to enable extraction.")

    extract_btn = st.button(
        "🔬 Extract Details",
        disabled=not has_bill,
        type="primary",
        key="extract_btn",
    )

    if extract_btn and has_bill:
        from processors.ocr_engine import extract_text_from_bytes  # noqa: PLC0415
        from processors.claim_auditor import configure_groq         # noqa: PLC0415
        from groq import Groq                                        # noqa: PLC0415

        api_key = _get_api_key()
        configure_groq(api_key)
        groq_client = Groq(api_key=api_key)

        with st.spinner("🤖 Groq Vision is reading your bill…"):
            try:
                text = extract_text_from_bytes(
                    st.session_state.bill_bytes,
                    st.session_state.bill_filename,
                    groq_client,
                )
                st.session_state.bill_text    = text
                st.session_state.audit_result = None
            except Exception as exc:
                st.error(f"Vision extraction failed: {exc}")
                st.stop()
        st.success("✅ Bill details extracted successfully!")

    if st.session_state.bill_text:
        st.markdown("### 📋 Extracted Bill Details")
        st.markdown(
            "<p style='color:grey;font-size:0.85em'>Review the details below. "
            "If everything looks correct, proceed to Cross Check.</p>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.markdown(st.session_state.bill_text)
        with st.expander("🔎 View raw extracted text", expanded=False):
            st.code(st.session_state.bill_text, language="markdown")

    # ── STEP 3 : Cross Check ─────────────────────────────────────────────
    st.divider()
    st.subheader("Step 3 — Cross Check Against Policy")

    has_extracted = bool(st.session_state.bill_text)

    if not has_extracted:
        st.info("👆 Extract details first to enable the cross-check.")

    crosscheck_btn = st.button(
        "⚖️ Cross Check",
        disabled=not has_extracted,
        type="primary",
        key="crosscheck_btn",
    )

    if crosscheck_btn and has_extracted:
        from processors.claim_auditor import configure_groq, audit_claim   # noqa: PLC0415
        from processors.policy_engine import get_policy_as_prompt_text     # noqa: PLC0415
        from processors.ocr_engine import extract_text_from_path           # noqa: PLC0415
        from groq import Groq                                               # noqa: PLC0415

        api_key = _get_api_key()
        configure_groq(api_key)
        groq_client = Groq(api_key=api_key)

        # Load uploaded policy text (if any) — also via Groq Vision for PDFs
        uploaded_policy_text = ""
        if policy_choice:
            with st.spinner(f"📖 Reading policy – {policy_choice.name}…"):
                try:
                    uploaded_policy_text = extract_text_from_path(
                        policy_choice, groq_client
                    )
                except Exception as exc:
                    st.warning(f"Could not read uploaded policy ({exc}). Using baseline only.")

        with st.spinner("⚖️ Groq is cross-checking against policy rules…"):
            try:
                result = audit_claim(
                    bill_text=st.session_state.bill_text,
                    policy_baseline_text=get_policy_as_prompt_text(),
                    uploaded_policy_text=uploaded_policy_text,
                )
                st.session_state.audit_result = result
            except Exception as exc:
                st.error(f"Audit failed: {exc}")
                st.stop()

    # ── STEP 4 : Results ─────────────────────────────────────────────────
    if st.session_state.audit_result:
        result   = st.session_state.audit_result
        rows     = result.get("rows", [])
        elig     = result.get("eligibility", {})
        verdict  = elig.get("verdict", "Unknown")
        summary  = elig.get("summary", "")
        steps    = elig.get("next_steps", [])

        st.divider()
        st.subheader("📊 Comparison Spec Sheet")

        # ── Eligibility verdict banner ──────────────────────────────────
        v_colour = VERDICT_COLOURS.get(verdict, "#e2e3e5")
        v_icon   = VERDICT_ICONS.get(verdict, "❓")
        st.markdown(
            f"""
            <div style="background:{v_colour};border-radius:8px;padding:16px 20px;margin-bottom:16px">
                <h3 style="margin:0;color:#111111">{v_icon} Insurance Eligibility: <strong>{verdict}</strong></h3>
                <p style="margin:8px 0 0;color:#222222">{summary}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Summary metrics ─────────────────────────────────────────────
        total = len(rows)
        ok    = sum(1 for r in rows if str(r.get("status","")).strip() == "✅")
        warn  = sum(1 for r in rows if str(r.get("status","")).strip() == "⚠️")
        fail  = sum(1 for r in rows if str(r.get("status","")).strip() == "❌")
        avg_risk = (
            round(sum(r.get("risk_score", 0) for r in rows) / total)
            if total else 0
        )

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Items",      total)
        c2.metric("✅ Admissible",    ok)
        c3.metric("⚠️ Partial",       warn)
        c4.metric("❌ Rejected",      fail)
        c5.metric("Avg Risk Score",   f"{avg_risk}/100")

        st.divider()

        # ── Line-item comparison table ──────────────────────────────────
        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                "parameter":    "Parameter",
                "bill_detail":  "Bill Detail",
                "policy_clause":"Policy Clause",
                "status":       "Status",
                "lag_reason":   "Lag Reason",
                "risk_score":   "Risk Score",
                "risk_label":   "Risk Level",
            })

            # Keep column order consistent
            display_cols = [
                "Parameter", "Bill Detail", "Policy Clause",
                "Status", "Lag Reason", "Risk Score", "Risk Level",
            ]
            df = df.reindex(columns=display_cols, fill_value="—")

            styled = (
                df.style
                .apply(_colour_row, axis=1)
                .set_properties(**{"text-align": "left", "vertical-align": "top"})
                .set_table_styles([
                    {"selector": "th", "props": [
                        ("background-color", "#1f3864"),
                        ("color", "#ffffff"),
                        ("font-weight", "bold"),
                        ("padding", "8px"),
                        ("font-size", "13px"),
                    ]},
                    {"selector": "td", "props": [
                        ("padding", "8px"),
                        ("font-size", "13px"),
                        ("border-bottom", "1px solid #333"),
                    ]},
                    # Override Streamlit dark theme leaking white into cells
                    {"selector": "table", "props": [
                        ("border-collapse", "collapse"),
                    ]},
                ])
            )
            st.dataframe(styled, width="stretch", height=480)
        else:
            st.info("No line items were parsed from the bill.")

        # ── Recommended next steps ──────────────────────────────────────
        if steps:
            st.divider()
            st.subheader("🗒️ Recommended Next Steps")
            for i, step in enumerate(steps, 1):
                st.markdown(f"**{i}.** {step}")

        # ── CSV download ────────────────────────────────────────────────
        if rows:
            st.divider()
            csv_df = pd.DataFrame(rows).rename(columns={
                "parameter":    "Parameter",
                "bill_detail":  "Bill Detail",
                "policy_clause":"Policy Clause",
                "status":       "Status",
                "lag_reason":   "Lag Reason",
                "risk_score":   "Risk Score",
                "risk_label":   "Risk Level",
            })
            csv_df["Eligibility Verdict"] = verdict
            csv_df["Summary"]             = summary

            st.download_button(
                "⬇️ Download Full Report (CSV)",
                data=csv_df.to_csv(index=False).encode("utf-8"),
                file_name="mediaudit_report.csv",
                mime="text/csv",
            )

        # ── Reset button ─────────────────────────────────────────────────
        st.divider()
        if st.button("🔄 Start New Audit", key="reset_btn"):
            for key in ["bill_bytes", "bill_filename", "bill_text", "audit_result"]:
                st.session_state[key] = None
            st.session_state.camera_active = False
            st.session_state.uploaded_file_id = None
            st.rerun()


if __name__ == "__main__":
    main()