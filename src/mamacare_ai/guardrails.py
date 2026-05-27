"""Safety and scope guardrails for MamaCare.

This module applies deterministic rules before answer generation so the
prototype can reliably prioritize emergencies, avoid unsafe medication advice,
and refuse unrelated questions.
"""

from __future__ import annotations

import re

from mamacare_ai.models import GuardrailOutcome


EMERGENCY_PATTERNS = [
    r"heavy bleeding",
    r"severe bleeding",
    r"no fetal movement",
    r"baby not moving",
    r"convulsions?",
    r"chest pain",
    r"difficulty breathing",
    r"blurred vision",
    r"severe headache",
    r"water broke",
    r"water breaking",
    r"high fever",
    r"severe abdominal pain",
]

SELF_HARM_PATTERNS = [
    r"\bsuicid(al|e)\b",
    r"\bkill myself\b",
    r"\bend my life\b",
    r"\bdon't want to live\b",
    r"\bdo not want to live\b",
    r"\bharm myself\b",
    r"\bself harm\b",
    r"\bwant to die\b",
    r"\bfeel like dying\b",
]

PREGNANCY_DECISION_PATTERNS = [
    r"\babort\b",
    r"\babortion\b",
    r"\bterminate\b",
    r"\btermination\b",
    r"\bend this pregnancy\b",
    r"\bnot continue this pregnancy\b",
    r"\bdo not want this pregnancy\b",
    r"\bunplanned pregnancy\b",
    r"\bthinking about ending (my|this) pregnancy\b",
    r"\babortion pills?\b",
]

DOCTOR_REFERRAL_PATTERNS = [
    r"pain",
    r"fever",
    r"swelling",
    r"spotting",
    r"cramping",
    r"unusual discharge",
    r"headache",
    r"vomiting",
]

MEDICATION_PATTERNS = [
    r"\b\d+\s?(mg|mcg|ml)\b",
    r"\btwice daily\b",
    r"\bonce daily\b",
    r"\bparacetamol\b",
    r"\baspirin\b",
    r"\bantibiotic\b",
    r"\btablet\b",
    r"\bmedicine\b",
]

OUT_OF_SCOPE_PATTERNS = [
    r"\bpython\b",
    r"\bjavascript\b",
    r"\blaptop\b",
    r"\bfootball\b",
    r"\belection\b",
    r"\btax\b",
    r"\bmovie\b",
    r"\bpassword\b",
]

PII_PATTERNS = [
    r"\bmy name is\b",
    r"\bi am called\b",
    r"\b\d{7,}\b",
    r"@",
]


# ---------------------------------------------------------------------------
# Guardrail Engine
# ---------------------------------------------------------------------------
# This small rule engine is intentionally explicit. It is easier to review with
# clinicians and safety stakeholders than a hidden black-box classifier.
class GuardrailEngine:
    def __init__(self, emergency_number: str = "999") -> None:
        self.emergency_number = emergency_number

    def analyze(self, query: str) -> GuardrailOutcome:
        lowered = query.lower()
        outcome = GuardrailOutcome()

        if any(re.search(pattern, lowered) for pattern in SELF_HARM_PATTERNS):
            outcome.flags.extend(["SELF_HARM_CRISIS", "EMERGENCY"])
            outcome.crisis_message = (
                "If you feel you might act on these thoughts or you are not safe right now, "
                f"please call {self.emergency_number} or 112 now, go to the nearest hospital, "
                "or ask a trusted person to stay with you and help you get urgent support."
            )
            return outcome

        if any(re.search(pattern, lowered) for pattern in EMERGENCY_PATTERNS):
            outcome.flags.append("EMERGENCY")
            outcome.emergency_message = (
                "EMERGENCY: Your symptoms may need urgent medical attention. "
                f"Please call {self.emergency_number} or go to the nearest "
                "hospital or maternity facility immediately."
            )
            return outcome

        if any(re.search(pattern, lowered) for pattern in PREGNANCY_DECISION_PATTERNS):
            outcome.flags.append("SENSITIVE_COUNSELLING")
            outcome.notes.append(
                "For pregnancy-decision support, the prototype should respond with emotional support and referral to a qualified healthcare professional or counsellor rather than procedural guidance."
            )

        if any(re.search(pattern, lowered) for pattern in DOCTOR_REFERRAL_PATTERNS):
            outcome.flags.append("DOCTOR_REFERRAL")
            outcome.notes.append(
                "Please contact your midwife or visit your nearest antenatal clinic "
                "as soon as possible if symptoms continue or worsen."
            )

        if any(re.search(pattern, lowered) for pattern in MEDICATION_PATTERNS):
            outcome.flags.append("MEDICATION_BLOCK")
            outcome.medication_blocked = True
            outcome.notes.append(
                "I can give general pregnancy guidance, but medication and dosage "
                "decisions must be made by your doctor or midwife."
            )

        if any(re.search(pattern, lowered) for pattern in PII_PATTERNS):
            outcome.flags.append("PRIVACY")
            outcome.notes.append(
                "Please avoid sharing names, phone numbers, ID numbers, or exact "
                "locations in chat."
            )

        if any(re.search(pattern, lowered) for pattern in OUT_OF_SCOPE_PATTERNS):
            outcome.flags.append("OUT_OF_SCOPE")
            outcome.out_of_scope = True

        return outcome
