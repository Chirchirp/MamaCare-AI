"""Warm response orchestration for MamaCare answers.

This module translates retrieved context and guardrail decisions into a
mother-friendly response format. It is where product tone, safety language, and
prototype fallback behavior come together.
"""

from __future__ import annotations

from dataclasses import dataclass

from mamacare_ai.models import GuardrailOutcome, RetrievalResult
from mamacare_ai.retriever import is_trusted_answer_source


LOW_CONFIDENCE_THRESHOLD = 0.6
WARM_CLOSINGS = [
    "You're doing an amazing job, mama 💛",
    "Every question you ask shows how much you care — keep going 🌸",
    "I'm right here whenever you need me 💙",
    "You've got this — and you're not alone on this journey 🌟",
    "Take good care of yourself and that little one 💛",
]
EMERGENCY_TEMPLATE = """⚠️ IMPORTANT — Please seek help immediately.

What you're describing needs urgent medical attention. 
Please do one of these right now:
🏥 Go to your nearest hospital emergency or maternity ward
📞 Call emergency services: 112 or 999
📞 Call your midwife or doctor directly

You and your baby matter. Please don't wait — go now. 
I'll be right here when you're safe. 💛"""
SELF_HARM_TEMPLATE = """⚠️ IMPORTANT — You deserve support right now.

I'm really glad you said this out loud. You should not have to carry this alone.

Please do one of these right now:
- Call emergency services: 112 or 999
- Go to the nearest hospital or emergency department
- Reach out to a trusted person and ask them to stay with you

If you feel you might act on these thoughts, please seek urgent in-person help now.
You matter, and your safety matters. 💛"""
REFERRAL_NOTE = """👩‍⚕️ I'd also gently suggest mentioning this to your midwife 
or doctor at your next visit — or sooner if it gets worse. 
They know your full history and can give you the most 
personalised advice."""
MEDICATION_NOTE = """The right dose for you is something only your doctor 
or midwife can decide — please check with them first."""
OUT_OF_SCOPE_NOTE = """I'm specially trained to support you through your pregnancy 
journey. For this question, a general doctor or specialist 
would be the right person to ask 😊"""
UNCERTAINTY_NOTE = """This question is out of context for the current MamaCare knowledge base.

It was not part of the knowledge used in this release, so I should not guess or give a generic answer.

It can be considered for the next release. For now, please speak with a qualified healthcare professional for personal guidance."""
PRIVACY_NOTE = """Just a little note — you don't need to share personal details 
with me. I'm here to help with general pregnancy guidance 💛"""
DIAGNOSIS_NOTE = """What you're describing could mean a few things, and the 
best way to know for sure is to see your healthcare provider."""
PREGNANCY_DECISION_NOTE = """I want to respond to this with care. Questions about continuing or ending a pregnancy can carry a lot of emotion, pressure, and personal circumstances.

In this prototype, I should not guide you through abortion or termination steps. The safest support I can give is to encourage you to speak with a qualified doctor, midwife, reproductive health professional, or counsellor who can talk through your situation, your wellbeing, and the care options legally and safely available to you.

If someone is pressuring you, you feel unsafe, or this question is connected to thoughts of harming yourself, please seek urgent in-person help right away."""
GREETING_RESPONSES = [
    "Hello mama, it's so lovely to hear from you 💛",
    "Hi there, and welcome. I'm really glad you reached out 💛",
    "Hello, mama. I'm here with you and ready to help 🌸",
]
CAPABILITY_RESPONSE = """I’m here to support you through pregnancy with warm, evidence-based guidance.

I can help with:
- common pregnancy symptoms by trimester
- food, hydration, and safe daily habits
- baby movement and fetal development questions
- antenatal visits and what to expect
- emotional wellbeing and reassurance
- birth preparation and early postpartum basics
- warning signs and when to seek care

If you want, you can ask me something like:
- "I’m 10 weeks pregnant and feel nauseated. What can help?"
- "What warning signs mean I should go to hospital?"
- "What should I pack for birth in the third trimester?"
"""


# ---------------------------------------------------------------------------
# Context Bundle
# ---------------------------------------------------------------------------
# This small structure keeps retrieved answer text, source summary, and scoring
# together while a response is being composed.
@dataclass
class ContextBundle:
    context_text: str
    source_line: str
    confidence: float


# ---------------------------------------------------------------------------
# Response Chain
# ---------------------------------------------------------------------------
# This class owns conversational behavior: greetings, capability prompts,
# uncertainty handling, and the warm evidence-grounded answer structure.
class MamaCareResponseChain:
    def __init__(self) -> None:
        self.prompt_template = None
        self.llm = None

    def generate(
        self,
        *,
        query: str,
        trimester: str,
        results: list[RetrievalResult],
        guardrails: GuardrailOutcome,
        conversation_history: list[dict] | None = None,
    ) -> str:
        history = conversation_history or []
        if guardrails.crisis_message:
            return SELF_HARM_TEMPLATE

        if guardrails.emergency_message:
            return EMERGENCY_TEMPLATE

        if guardrails.out_of_scope:
            return OUT_OF_SCOPE_NOTE

        if self._is_greeting(query):
            return self._render_greeting(history)

        if self._asks_capabilities(query):
            return self._render_capabilities(history)

        if self._is_gratitude(query):
            return self._render_gratitude()

        if "SENSITIVE_COUNSELLING" in guardrails.flags:
            return self._render_sensitive_counselling_response(
                trimester=trimester,
                guardrails=guardrails,
                results=results,
                query=query,
            )

        context = self._build_context(results)
        if context.confidence < LOW_CONFIDENCE_THRESHOLD:
            return self._render_uncertain_response(trimester, guardrails, query=query)

        return self._render_rule_based_response(
            query=query,
            trimester=trimester,
            results=results,
            guardrails=guardrails,
            history=history,
            context=context,
        )

    def _build_context(self, results: list[RetrievalResult]) -> ContextBundle:
        if not results:
            return ContextBundle(context_text="", source_line="", confidence=0.0)
        selected = self._preferred_results(results)
        if not selected:
            return ContextBundle(context_text="", source_line="", confidence=0.0)
        context_lines: list[str] = []
        sources: list[str] = []
        for index, result in enumerate(selected, start=1):
            chunk = result.chunk
            context_lines.append(
                f"[{index}] Title: {chunk.title}\n"
                f"Source: {chunk.source_name}\n"
                f"Trimester: {chunk.trimester}\n"
                f"Answer: {chunk.answer}"
            )
            if chunk.when_to_seek_care:
                context_lines.append(
                    "When to seek care: " + "; ".join(chunk.when_to_seek_care)
                )
            if chunk.danger_signs:
                context_lines.append(
                    "Danger signs: " + "; ".join(chunk.danger_signs)
                )
            sources.append(chunk.source_name)
        confidence = max(result.score for result in selected)
        source_line = ", ".join(dict.fromkeys(sources))
        return ContextBundle(
            context_text="\n\n".join(context_lines),
            source_line=source_line,
            confidence=confidence,
        )

    def _render_uncertain_response(
        self,
        trimester: str,
        guardrails: GuardrailOutcome,
        *,
        query: str,
    ) -> str:
        parts = [
            self._acknowledge(trimester, query, [], worried=True),
            UNCERTAINTY_NOTE,
        ]
        if "PRIVACY" in guardrails.flags:
            parts.append(PRIVACY_NOTE)
        if "MEDICATION_BLOCK" in guardrails.flags:
            parts.append(MEDICATION_NOTE)
        if "DOCTOR_REFERRAL" in guardrails.flags:
            parts.append(REFERRAL_NOTE)
        parts.append(self._closing("uncertain"))
        return "\n\n".join(parts)

    def _render_sensitive_counselling_response(
        self,
        *,
        trimester: str,
        guardrails: GuardrailOutcome,
        results: list[RetrievalResult],
        query: str,
    ) -> str:
        parts = [
            self._acknowledge(trimester, query, [], worried=True),
            PREGNANCY_DECISION_NOTE,
            "You deserve calm, non-judgmental support, and it would be a good next step to speak with a healthcare professional or counsellor who can support you properly.",
        ]
        trusted = self._preferred_results(results)
        if trusted:
            parts.append(f"(Source: {trusted[0].chunk.source_name})")
        if "PRIVACY" in guardrails.flags:
            parts.append(PRIVACY_NOTE)
        parts.append(self._closing("pregnancy-decision"))
        return "\n\n".join(parts)

    def _render_rule_based_response(
        self,
        *,
        query: str,
        trimester: str,
        results: list[RetrievalResult],
        guardrails: GuardrailOutcome,
        history: list[dict],
        context: ContextBundle,
    ) -> str:
        preferred = self._preferred_results(results)
        if not preferred:
            return self._render_uncertain_response(trimester, guardrails, query=query)
        primary = preferred[0].chunk
        worried = self._sounds_worried(query, guardrails)
        parts = [
            self._acknowledge(trimester, query, history, worried=worried),
            self._answer_from_results(preferred, guardrails),
            self._reassure(trimester, worried=worried),
            f"(Source: {primary.source_name})",
        ]
        if "PRIVACY" in guardrails.flags:
            parts.append(PRIVACY_NOTE)
        if "MEDICATION_BLOCK" in guardrails.flags:
            parts.append(MEDICATION_NOTE)
        if "DOCTOR_REFERRAL" in guardrails.flags:
            parts.append(REFERRAL_NOTE)
        parts.append(self._closing(query))
        return "\n\n".join(part for part in parts if part.strip())

    def _render_greeting(self, history: list[dict]) -> str:
        if history:
            opening = "Welcome back, mama 💛"
            follow_up = "How are you feeling today, and what stage of pregnancy are you in now?"
        else:
            opening = GREETING_RESPONSES[0]
            follow_up = (
                "I’m here to support you through pregnancy with gentle guidance, practical information, "
                "and help understanding warning signs."
            )
        return "\n\n".join(
            [
                opening,
                follow_up,
                "You can ask me about symptoms, food, baby movement, antenatal visits, birth preparation, or emotional wellbeing.",
                "I'm right here whenever you need me 💙",
            ]
        )

    def _render_capabilities(self, history: list[dict]) -> str:
        intro = "I’d be happy to help with that 💛" if not history else "Of course, mama — here’s how I can support you right now 💛"
        return "\n\n".join([intro, CAPABILITY_RESPONSE, "You're doing an amazing job, mama 💛"])

    @staticmethod
    def _render_gratitude() -> str:
        return (
            "You're so welcome 💛\n\n"
            "I'm glad I could be here for you. If anything else comes up about your pregnancy or your baby, just ask.\n\n"
            "You've got this — and you're not alone on this journey 🌟"
        )

    def _acknowledge(
        self,
        trimester: str,
        query: str,
        history: list[dict],
        *,
        worried: bool,
    ) -> str:
        if history:
            opener = "It's lovely to have you back, and I'm glad you reached out again."
        elif worried:
            opener = "That sounds really unsettling, and it makes sense that you'd want clarity right away."
        else:
            opener = "That's a really valid question, and so many mothers wonder about this."

        trimester_note = {
            "T1": "The first trimester can feel especially intense, so please be gentle with yourself.",
            "T2": "This stage often brings lots of new changes, and it's completely okay to check in about them.",
            "T3": "The third trimester can feel exciting and uncomfortable all at once, so your question makes perfect sense.",
        }.get(trimester, "You're doing the right thing by paying attention to your body and your baby.")
        return f"{opener} {trimester_note}"

    def _answer_from_results(self, results: list[RetrievalResult], guardrails: GuardrailOutcome) -> str:
        primary = results[0].chunk
        answer_lines = [self._clean_answer(primary.answer)]
        if primary.when_to_seek_care:
            answer_lines.append(
                "Please arrange a check sooner if:\n- " + "\n- ".join(primary.when_to_seek_care)
            )
        if primary.danger_signs:
            answer_lines.append(
                "Important warning signs:\n- " + "\n- ".join(primary.danger_signs)
            )
        if "MEDICATION_BLOCK" in guardrails.flags:
            answer_lines.append(MEDICATION_NOTE)
        answer_lines.append(DIAGNOSIS_NOTE)
        return "\n\n".join(answer_lines)

    @staticmethod
    def _preferred_results(results: list[RetrievalResult]) -> list[RetrievalResult]:
        trusted = [result for result in results if is_trusted_answer_source(result.chunk)]
        if trusted:
            return trusted[:3]
        return []

    @staticmethod
    def _clean_answer(answer: str) -> str:
        text = " ".join(answer.split())
        if len(text) <= 700:
            return text
        sentences = [sentence.strip() for sentence in text.split(". ") if sentence.strip()]
        if not sentences:
            return text[:700].rstrip() + "..."
        summary: list[str] = []
        total = 0
        for sentence in sentences:
            sentence_text = sentence if sentence.endswith(".") else f"{sentence}."
            summary.append(sentence_text)
            total += len(sentence_text)
            if len(summary) >= 3 or total >= 520:
                break
        return " ".join(summary)

    @staticmethod
    def _reassure(trimester: str, *, worried: bool) -> str:
        if trimester == "T1":
            return (
                "Early pregnancy can bring a lot of ups and downs, so you're not overreacting by checking in. "
                "Your midwife or doctor can help you feel more sure if anything changes."
            )
        if trimester == "T2":
            return (
                "You're in a stage where many mothers start feeling more connected to the journey, and it's still very okay to ask for reassurance. "
                "If something feels off, your care team is there to support you."
            )
        if trimester == "T3":
            return (
                "So much is happening as you get closer to meeting your baby, and it's completely normal to want extra reassurance. "
                "If anything feels stronger, new, or worrying, please let your care team know."
            )
        if worried:
            return "You are not alone in this, and reaching out early is always a wise thing to do."
        return "You're doing a lovely job staying informed and listening to your body."

    @staticmethod
    def _sounds_worried(query: str, guardrails: GuardrailOutcome) -> bool:
        lowered = query.lower()
        if any(flag in guardrails.flags for flag in ("DOCTOR_REFERRAL", "MEDICATION_BLOCK")):
            return True
        return any(word in lowered for word in ["worried", "scared", "afraid", "anxious", "pain", "bleeding"])

    @staticmethod
    def _closing(seed_text: str) -> str:
        index = sum(ord(character) for character in seed_text) % len(WARM_CLOSINGS)
        return WARM_CLOSINGS[index]

    @staticmethod
    def _history_to_text(history: list[dict]) -> str:
        if not history:
            return "No earlier conversation."
        lines: list[str] = []
        for item in history[-6:]:
            role = item.get("role", "user")
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            lines.append(f"{role.title()}: {content}")
        return "\n".join(lines) if lines else "No earlier conversation."

    @staticmethod
    def _is_greeting(query: str) -> bool:
        lowered = " ".join(query.lower().split())
        greetings = {
            "hi",
            "hello",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
            "hi mamacare ai",
            "hello mamacare ai",
            "hey mamacare ai",
        }
        return lowered in greetings

    @staticmethod
    def _asks_capabilities(query: str) -> bool:
        lowered = query.lower()
        patterns = [
            "what can you do",
            "how can you help",
            "who are you",
            "what do you help with",
            "what can i ask",
            "help me understand how you work",
        ]
        return any(pattern in lowered for pattern in patterns)

    @staticmethod
    def _is_gratitude(query: str) -> bool:
        lowered = " ".join(query.lower().split())
        gratitude = {"thanks", "thank you", "thankyou", "thanks mamacare", "okay thanks"}
        return lowered in gratitude


# ---------------------------------------------------------------------------
# Query-Mode Helper
# ---------------------------------------------------------------------------
# This helper lets the service treat greetings and lightweight meta-questions
# differently from medical or pregnancy guidance requests.
def detect_query_mode(query: str) -> str:
    lowered = " ".join(query.lower().split())
    greetings = {
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "hi mamacare ai",
        "hello mamacare ai",
        "hey mamacare ai",
    }
    gratitude = {"thanks", "thank you", "thankyou", "thanks mamacare", "okay thanks"}
    capability_patterns = [
        "what can you do",
        "how can you help",
        "who are you",
        "what do you help with",
        "what can i ask",
        "help me understand how you work",
    ]

    if lowered in greetings:
        return "greeting"
    if lowered in gratitude:
        return "gratitude"
    if any(pattern in lowered for pattern in capability_patterns):
        return "capabilities"
    return "normal"
