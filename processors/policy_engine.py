"""
policy_engine.py
----------------
Generalised built-in insurance policy baseline.

This module defines common insurance underwriting rules that apply across
most standard health insurance policies in India. These rules act as the
ground-truth baseline; Groq then fills contextual gaps the rules don't
explicitly cover.

Structure
---------
GENERALISED_POLICY  –  dict consumed by claim_auditor.py and injected
                        into the Groq prompt as <policy_baseline> XML.

get_policy_markdown()  –  returns a formatted Markdown string for display
                           in the UI.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Core policy definition
# ---------------------------------------------------------------------------

GENERALISED_POLICY: dict[str, Any] = {

    "policy_name": "MediAudit Generalised Health Insurance Baseline v1.0",
    "effective_date": "2024-01-01",

    # ── Eligibility ──────────────────────────────────────────────────────
    "eligibility": {
        "min_age_years": 18,
        "max_age_years": 65,
        "bmi_range": {"min": 15.0, "max": 40.0},
        "notes": (
            "Applicants outside the age or BMI range require specialist "
            "underwriting approval and are not auto-approved."
        ),
    },

    # ── Waiting Periods ──────────────────────────────────────────────────
    "waiting_periods": {
        "initial_waiting_days": 30,          # No claims in first 30 days
        "pre_existing_disease_years": 2,     # PED covered after 2 years
        "specific_illness_months": {
            "cataract": 24,
            "hernia": 24,
            "knee_replacement": 24,
            "hip_replacement": 24,
            "varicose_veins": 12,
            "sinusitis": 12,
            "piles_fistula": 12,
            "kidney_stones": 12,
            "hysterectomy": 24,
            "joint_replacement": 24,
        },
        "maternity_months": 9,
        "notes": (
            "Waiting periods are counted from the first policy inception date, "
            "not renewal dates."
        ),
    },

    # ── Coverage Sub-limits ──────────────────────────────────────────────
    "sub_limits": {
        "room_rent_per_day_inr": 5_000,
        "icu_rent_per_day_inr": 10_000,
        "ambulance_per_event_inr": 2_000,
        "cataract_per_eye_inr": 40_000,
        "dental_treatment_inr": 0,           # Excluded unless accident
        "cosmetic_surgery_inr": 0,           # Excluded
        "ayush_treatment_inr": 20_000,       # Ayurveda/Yoga/Unani/Siddha/Homeopathy
        "mental_health_inr": 50_000,
        "organ_donor_inr": 1_00_000,
        "domiciliary_treatment_inr": 20_000,
    },

    # ── Co-pay Rules ─────────────────────────────────────────────────────
    "copay": {
        "default_copay_percent": 0,
        "senior_citizen_copay_percent": 20,  # Age > 60
        "non_network_hospital_copay_percent": 20,
        "pre_existing_copay_percent": 10,    # During PED waiting period
    },

    # ── Exclusions ───────────────────────────────────────────────────────
    "exclusions": [
        "Cosmetic or aesthetic treatments",
        "Self-inflicted injuries",
        "War, terrorism, or nuclear hazard injuries",
        "Dental treatment (except accidental)",
        "Obesity treatment or weight-loss surgery",
        "Experimental or unproven treatments",
        "Substance abuse or alcoholism treatment",
        "Fertility treatments and IVF",
        "Spectacles, contact lenses, hearing aids",
        "Non-allopathic treatment beyond AYUSH sub-limit",
        "Refractive error correction (LASIK) below -7.5 dioptre",
        "Pregnancy termination (unless medically necessary)",
        "Congenital external diseases (if detected at birth)",
        "HIV/AIDS and sexually transmitted diseases",
    ],

    # ── Pre-existing Conditions (PED) ────────────────────────────────────
    "pre_existing_conditions": {
        "definition": (
            "Any condition, ailment, or injury or related condition(s) for "
            "which the insured had signs/symptoms, or was diagnosed, or received "
            "medical advice / treatment within 48 months prior to policy inception."
        ),
        "common_peds": [
            "Diabetes Mellitus (Type 1 & 2)",
            "Hypertension / High Blood Pressure",
            "Asthma",
            "Chronic Obstructive Pulmonary Disease (COPD)",
            "Thyroid disorders",
            "Cardiac conditions (IHD, heart attack history)",
            "Chronic kidney disease",
            "Cancer (within 5 years of remission)",
            "Epilepsy",
            "Arthritis (Rheumatoid)",
        ],
        "waiting_period_years": 2,
        "notes": (
            "PEDs are covered after the waiting period with standard benefits. "
            "Undisclosed PEDs may result in claim repudiation."
        ),
    },

    # ── Network & Reimbursement ──────────────────────────────────────────
    "network": {
        "cashless_at_network_hospitals": True,
        "reimbursement_timeline_days": 15,
        "pre_auth_required_above_inr": 25_000,
        "post_hospitalisation_days": 60,
        "pre_hospitalisation_days": 30,
    },

    # ── Deductibles ──────────────────────────────────────────────────────
    "deductible_inr": 0,   # Standard zero-deductible plan

    # ── Sum Insured ──────────────────────────────────────────────────────
    "sum_insured_options_inr": [2_00_000, 3_00_000, 5_00_000, 10_00_000, 25_00_000],
    "default_sum_insured_inr": 5_00_000,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_policy_markdown() -> str:
    """Return a human-readable Markdown summary of the generalised policy."""
    p = GENERALISED_POLICY
    e = p["eligibility"]
    w = p["waiting_periods"]
    s = p["sub_limits"]
    c = p["copay"]

    illness_rows = "\n".join(
        f"| {k.replace('_', ' ').title()} | {v} months |"
        for k, v in w["specific_illness_months"].items()
    )

    exclusions = "\n".join(f"- {x}" for x in p["exclusions"])
    peds = "\n".join(f"- {x}" for x in p["pre_existing_conditions"]["common_peds"])

    return f"""
## {p['policy_name']}

### Eligibility
| Parameter | Value |
|-----------|-------|
| Minimum Age | {e['min_age_years']} years |
| Maximum Age | {e['max_age_years']} years |
| BMI Range | {e['bmi_range']['min']} – {e['bmi_range']['max']} |

### Waiting Periods
| Condition | Period |
|-----------|--------|
| Initial (all claims) | {w['initial_waiting_days']} days |
| Pre-existing diseases | {w['pre_existing_disease_years']} years |
| Maternity | {w['maternity_months']} months |

#### Specific Illness Waiting Periods
| Illness | Waiting Period |
|---------|---------------|
{illness_rows}

### Sub-limits
| Item | Limit (₹) |
|------|-----------|
| Room Rent / Day | ₹{s['room_rent_per_day_inr']:,} |
| ICU Rent / Day | ₹{s['icu_rent_per_day_inr']:,} |
| Ambulance / Event | ₹{s['ambulance_per_event_inr']:,} |
| Cataract / Eye | ₹{s['cataract_per_eye_inr']:,} |
| Mental Health | ₹{s['mental_health_inr']:,} |
| AYUSH Treatment | ₹{s['ayush_treatment_inr']:,} |
| Dental | Excluded |
| Cosmetic Surgery | Excluded |

### Co-pay Rules
| Scenario | Co-pay % |
|----------|----------|
| Standard | {c['default_copay_percent']}% |
| Senior Citizen (>60 yrs) | {c['senior_citizen_copay_percent']}% |
| Non-network Hospital | {c['non_network_hospital_copay_percent']}% |
| Pre-existing Disease Claims | {c['pre_existing_copay_percent']}% |

### Common Pre-existing Conditions
{peds}

### Exclusions
{exclusions}
""".strip()


def get_policy_as_prompt_text() -> str:
    """
    Return a compact policy summary optimised for injection into the
    Groq prompt. Avoids heavy Markdown tables to save tokens.
    """
    p = GENERALISED_POLICY
    e = p["eligibility"]
    w = p["waiting_periods"]
    s = p["sub_limits"]
    c = p["copay"]

    illness_list = "; ".join(
        f"{k.replace('_',' ')} ({v}m)"
        for k, v in w["specific_illness_months"].items()
    )

    return f"""
POLICY: {p['policy_name']}

ELIGIBILITY:
- Age: {e['min_age_years']}–{e['max_age_years']} years
- BMI: {e['bmi_range']['min']}–{e['bmi_range']['max']}

WAITING PERIODS:
- Initial waiting: {w['initial_waiting_days']} days (no claims)
- Pre-existing diseases (PED): {w['pre_existing_disease_years']} years
- Maternity: {w['maternity_months']} months
- Specific illnesses: {illness_list}

SUB-LIMITS (INR):
- Room rent: ₹{s['room_rent_per_day_inr']:,}/day
- ICU: ₹{s['icu_rent_per_day_inr']:,}/day
- Ambulance: ₹{s['ambulance_per_event_inr']:,}/event
- Cataract: ₹{s['cataract_per_eye_inr']:,}/eye
- Mental health: ₹{s['mental_health_inr']:,}
- AYUSH: ₹{s['ayush_treatment_inr']:,}
- Dental: EXCLUDED
- Cosmetic: EXCLUDED

CO-PAY:
- Standard: {c['default_copay_percent']}%
- Senior citizen (>60): {c['senior_citizen_copay_percent']}%
- Non-network hospital: {c['non_network_hospital_copay_percent']}%
- PED claims: {c['pre_existing_copay_percent']}%

PRE-EXISTING CONDITIONS (PED) — covered after 2 years:
{', '.join(p['pre_existing_conditions']['common_peds'])}

EXCLUSIONS:
{chr(10).join('- ' + x for x in p['exclusions'])}

SUM INSURED OPTIONS: {', '.join(f"₹{x:,}" for x in p['sum_insured_options_inr'])}
DEFAULT SUM INSURED: ₹{p['default_sum_insured_inr']:,}
""".strip()