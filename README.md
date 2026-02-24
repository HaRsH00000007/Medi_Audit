# Medi_Audit

🏥 MediAudit – Insurance Claim Validator

MediAudit is an AI-powered Streamlit dashboard that extracts medical bill details and cross-checks them against insurance policy rules to determine claim eligibility, risk score, and recommended next steps.

Built using:

Streamlit

Groq Vision API

Python

Pandas

🚀 Features
📥 Dual Input Modes

Upload medical bill (PDF / PNG / JPG / TIFF)

Capture bill directly from camera

🔍 Two-Step Workflow

Extract bill details using Vision AI

Cross-check against:

Built-in generalized insurance policy baseline

Optional uploaded insurer policy PDF

📊 Smart Output

Eligibility Verdict (Eligible / Partially Eligible / Not Eligible)

Line-by-line comparison table

Risk score (0–100)

Risk level (Low / Medium / High / Critical)

Recommended next steps

CSV report download

🖥️ Demo Flow

Upload or capture medical bill

Click Extract Details

Click Cross Check

Review comparison spec sheet

Download full report

📁 Project Structure
## 📁 Project Structure

```
MediAudit/
│
├── app.py
├── requirements.txt
├── .streamlit/
├── data/                     # Optional uploaded policy PDFs
├── processors/
│   ├── claim_auditor.py
│   ├── ocr_engine.py
│   └── policy_engine.py
└── venv/                     # Ignored
```
## ⚙️ Installation

### Clone Repository

```bash
git clone https://github.com/HaRsH00000007/Medi_Audit.git
cd Medi_Audit
```

### Create Virtual Environment

```bash
python -m venv venv
```
