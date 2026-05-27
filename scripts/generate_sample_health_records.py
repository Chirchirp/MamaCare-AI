"""Generate sample health record datasets for demos, testing, and analytics prototyping.

The output files mimic maternal-health records without exposing real patient
data. They help the team test ingestion, dashboards, and retrieval behavior
before governed clinical data is available.
"""

from __future__ import annotations

import csv
import hashlib
import random
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "sample_health_records"
RANDOM = random.Random(42)


# ---------------------------------------------------------------------------
# Output and Utility Helpers
# ---------------------------------------------------------------------------
# These helpers manage deterministic paths, IDs, and timestamps so generated
# data stays reproducible across runs.
def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def random_date(start_days_ago: int = 365) -> date:
    offset = RANDOM.randint(0, start_days_ago)
    return date.today() - timedelta(days=offset)


def random_timestamp() -> str:
    base = datetime.now(tz=UTC) - timedelta(days=RANDOM.randint(0, 180))
    base = base.replace(
        hour=RANDOM.randint(0, 23),
        minute=RANDOM.choice([0, 15, 30, 45]),
        second=0,
        microsecond=0,
    )
    return base.isoformat().replace("+00:00", "Z")


def hashed_id(prefix: str) -> str:
    raw = f"{prefix}-{uuid.uuid4()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Dataset Builders
# ---------------------------------------------------------------------------
# Each function produces one sample dataset aligned to a specific use case:
# visit records, chatbot logs, or longitudinal pregnancy risk summaries.
def build_antenatal_visits(count: int = 2000) -> list[dict]:
    records = []
    patient_ids = [hashed_id("patient") for _ in range(max(1, count // 4))]

    for index in range(count):
        gestational_age = RANDOM.randint(8, 42)
        if gestational_age <= 13:
            trimester = "T1"
        elif gestational_age <= 26:
            trimester = "T2"
        else:
            trimester = "T3"

        maternal_age = RANDOM.randint(16, 45)
        weight_kg = round(max(40, RANDOM.gauss(65, 12)), 1)
        height_cm = round(max(140, RANDOM.gauss(162, 8)), 1)
        bmi = round(weight_kg / ((height_cm / 100) ** 2), 1)
        bp_systolic = min(180, max(80, int(RANDOM.gauss(118, 14))))
        bp_diastolic = min(120, max(50, int(RANDOM.gauss(76, 10))))
        haemoglobin = round(max(5.0, min(16.0, RANDOM.gauss(11.2, 1.8))), 1)
        risk_level = "low"
        if bp_systolic >= 140 or bp_diastolic >= 90:
            risk_level = "high"
        elif haemoglobin < 9.0 or maternal_age < 18 or maternal_age > 40:
            risk_level = "moderate"

        records.append(
            {
                "visit_id": f"v-{index:04d}-2026",
                "patient_id": RANDOM.choice(patient_ids),
                "visit_date": random_date().isoformat(),
                "gestational_age_weeks": gestational_age,
                "trimester": trimester,
                "maternal_age": maternal_age,
                "weight_kg": weight_kg,
                "height_cm": height_cm,
                "bmi": bmi,
                "bp_systolic": bp_systolic,
                "bp_diastolic": bp_diastolic,
                "haemoglobin_g_dl": haemoglobin,
                "urine_protein": RANDOM.choices(
                    ["negative", "trace", "1+", "2+", "3+"],
                    weights=[70, 15, 8, 5, 2],
                )[0],
                "fetal_heart_rate": RANDOM.randint(120, 160),
                "fundal_height_cm": round(max(12, min(42, RANDOM.gauss(gestational_age, 2))), 1),
                "fetal_presentation": RANDOM.choice(["cephalic", "breech", "transverse"]),
                "gravida": RANDOM.randint(1, 8),
                "parity": RANDOM.randint(0, 7),
                "risk_level": risk_level,
                "referred_to_hospital": RANDOM.random() < 0.18,
                "iron_supplement_given": RANDOM.random() > 0.2,
                "tt_vaccination": RANDOM.choice(["TT1", "TT2", "complete", "none"]),
                "clinician_notes": RANDOM.choice(
                    [
                        "Routine antenatal review completed.",
                        "Mild swelling discussed. Follow-up advised.",
                        "Nutrition counselling provided.",
                        "Blood pressure to be reviewed at next visit.",
                        "Referred for additional review due to symptoms.",
                    ]
                ),
                "facility_code": f"KE-NRB-{RANDOM.randint(1, 50):03d}",
            }
        )

    return records


def build_symptom_query_logs(count: int = 1000) -> list[dict]:
    prompts = [
        ("symptoms", "Is it normal to feel cramping at 11 weeks?"),
        ("nutrition", "What foods can I manage if I feel nauseated?"),
        ("emergency", "I have heavy bleeding and dizziness."),
        ("birth_prep", "What should I prepare before labour starts?"),
        ("mental_health", "I feel anxious most days. What should I do?"),
    ]
    records = []
    for index in range(count):
        topic, text = RANDOM.choice(prompts)
        trimester = RANDOM.choice(["T1", "T2", "T3"])
        emergency = topic == "emergency"
        records.append(
            {
                "query_id": f"q-{index:04d}-2026",
                "session_id": hashed_id("session"),
                "timestamp": random_timestamp(),
                "trimester": trimester,
                "query_text": text,
                "topic_category": topic,
                "guardrail_triggered": emergency,
                "guardrail_type": "emergency" if emergency else "",
                "response_quality": RANDOM.choice(["positive", "negative", ""]),
                "language": RANDOM.choice(["en", "sw"]),
                "country_region": RANDOM.choice(["KE-NRB", "KE-MSA", "UG-C", "TZ-DAR"]),
            }
        )
    return records


def build_risk_profiles(count: int = 750) -> list[dict]:
    records = []
    for _ in range(count):
        records.append(
            {
                "profile_id": str(uuid.uuid4()),
                "age_group": RANDOM.choice(["<18", "18-24", "25-34", "35+"]),
                "gravida_para": f"G{RANDOM.randint(1, 6)}P{RANDOM.randint(0, 5)}",
                "total_anc_visits": RANDOM.randint(1, 10),
                "gestational_diabetes": RANDOM.random() < 0.12,
                "hypertension_disorder": RANDOM.choice(
                    ["none", "chronic", "gestational", "pre-eclampsia", "eclampsia"]
                ),
                "anaemia_severity": RANDOM.choice(["none", "mild", "moderate", "severe"]),
                "hiv_status_disclosed": RANDOM.random() < 0.7,
                "mode_of_delivery": RANDOM.choice(["vaginal", "caesarean", "assisted"]),
                "birth_outcome": RANDOM.choice(
                    ["live_birth", "stillbirth", "neonatal_death"]
                ),
                "birth_weight_kg": round(RANDOM.uniform(1.8, 4.4), 2),
                "preterm_birth": RANDOM.random() < 0.14,
                "composite_risk_score": round(RANDOM.random(), 2),
            }
        )
    return records


# ---------------------------------------------------------------------------
# File Writer and Script Entry Point
# ---------------------------------------------------------------------------
# These helpers persist the generated rows and provide a simple CLI workflow.
def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ensure_output_dir()
    visits = build_antenatal_visits()
    queries = build_symptom_query_logs()
    profiles = build_risk_profiles()

    write_csv(OUTPUT_DIR / "antenatal_visits.csv", visits)
    write_csv(OUTPUT_DIR / "symptom_query_logs.csv", queries)
    write_csv(OUTPUT_DIR / "pregnancy_risk_profiles.csv", profiles)

    print(f"Wrote sample health record datasets to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
