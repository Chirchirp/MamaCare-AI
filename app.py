"""Streamlit application entry point for the MamaCare AI prototype.

This file is intentionally UI-focused. It wires the local retrieval service into
an interface that is easy for mothers, reviewers, donors, and collaborators to
understand during demos and early pilot discussions.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    import streamlit as st
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Streamlit is required to run this app. Install dependencies with "
        "`pip install -r requirements.txt`."
    ) from exc

from mamacare_ai.service import MamaCareService


st.set_page_config(
    page_title="MamaCare AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)

@st.cache_resource(show_spinner=False)
def get_service() -> MamaCareService:
    return MamaCareService.from_repo_root(ROOT)


# ---------------------------------------------------------------------------
# Visual Design Layer
# ---------------------------------------------------------------------------
# These helpers define the premium, mother-friendly visual presentation for the
# landing area, top navigation, and chat surface.
def render_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 234, 223, 0.7), transparent 32%),
                linear-gradient(180deg, #fffaf6 0%, #fff8f3 52%, #fffdfb 100%);
            color: #2f231d;
        }
        .block-container {
            max-width: 1180px;
            padding-top: 1.1rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3 {
            font-family: "Iowan Old Style", "Palatino Linotype", serif;
            color: #4c2d22;
            letter-spacing: -0.02em;
        }
        p, li, label, div, span {
            font-family: "Aptos", "Trebuchet MS", sans-serif;
        }
        [data-testid="stSidebar"] {
            display: none;
        }
        button[title="View fullscreen"] {
            display: none;
        }
        .hero-card {
            border-radius: 24px;
            padding: 1.4rem 1.5rem;
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(179, 127, 96, 0.12);
            box-shadow: 0 14px 30px rgba(139, 88, 57, 0.06);
            margin-bottom: 0.75rem;
            max-width: 1080px;
            margin-left: auto;
            margin-right: auto;
        }
        .app-bar {
            position: sticky;
            top: 0.55rem;
            z-index: 1000;
            max-width: 1080px;
            margin: 0 auto 0.85rem;
            padding: 0.82rem 1.1rem;
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(179, 127, 96, 0.12);
            box-shadow: 0 10px 22px rgba(126, 83, 58, 0.08);
            backdrop-filter: blur(10px);
        }
        .app-bar-title {
            font-family: "Iowan Old Style", "Palatino Linotype", serif;
            font-size: 1.05rem;
            color: #4c2d22;
            font-weight: 700;
        }
        .hero-tag {
            display: inline-block;
            background: #f9e4d4;
            color: #77472c;
            border-radius: 999px;
            padding: 0.34rem 0.78rem;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            margin-bottom: 0.65rem;
        }
        .hero-copy {
            font-size: 0.98rem;
            line-height: 1.7;
            max-width: 42rem;
            color: #5e4436;
        }
        .hero-subcopy {
            margin-top: 0.85rem;
            color: #74584a;
            font-size: 0.93rem;
        }
        .top-nav {
            border-radius: 24px;
            padding: 0.95rem 1.1rem;
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid rgba(179, 127, 96, 0.12);
            box-shadow: 0 12px 26px rgba(126, 83, 58, 0.06);
            margin-bottom: 0.8rem;
            max-width: 1080px;
            margin-left: auto;
            margin-right: auto;
        }
        .top-nav-title {
            font-family: "Iowan Old Style", "Palatino Linotype", serif;
            font-size: 1.05rem;
            color: #4c2d22;
            font-weight: 700;
            margin-bottom: 0.18rem;
        }
        .top-nav-copy {
            color: #7a5b4a;
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .top-chip-row {
            margin-top: 0.55rem;
        }
        .chat-shell {
            position: relative;
            border-radius: 26px;
            padding: 1.15rem 1.2rem 0.8rem;
            background: #ffffff;
            border: 1px solid rgba(179,127,96,0.14);
            box-shadow: 0 14px 32px rgba(126, 83, 58, 0.08);
            margin-top: 0.95rem;
            margin-bottom: 0.85rem;
            max-width: 980px;
            margin-left: auto;
            margin-right: auto;
        }
        .chat-shell-head {
            margin-bottom: 0.35rem;
        }
        .chat-shell h3 {
            margin: 0;
            font-size: 1.4rem;
        }
        .chat-shell-copy {
            color: #6a4a3b;
            line-height: 1.55;
            max-width: 52rem;
            margin-top: 0.35rem;
            font-size: 0.95rem;
        }
        .history-note {
            margin: 0.55rem 0 0.1rem;
            color: #866554;
            font-size: 0.9rem;
        }
        div[data-testid="stExpander"] {
            border-radius: 18px;
            border: 1px solid rgba(179,127,96,0.14);
            background: rgba(255, 252, 248, 0.88);
        }
        div[data-testid="stChatMessageContainer"] {
            max-width: 980px;
            margin-left: auto;
            margin-right: auto;
        }
        div[data-testid="stChatMessage"] {
            border-radius: 22px;
            padding: 0.25rem 0.35rem;
            margin-bottom: 0.7rem;
        }
        div[data-testid="stChatMessage"][aria-label="Chat message from assistant"] {
            background: #ffffff;
            border: 1px solid rgba(179,127,96,0.14);
            box-shadow: 0 14px 28px rgba(126, 83, 58, 0.08);
            border-radius: 24px;
        }
        div[data-testid="stChatMessage"][aria-label="Chat message from user"] {
            background: linear-gradient(135deg, rgba(254, 243, 235, 0.98), rgba(255, 249, 244, 0.98));
            border: 1px solid rgba(217, 164, 129, 0.2);
            border-radius: 24px;
        }
        div[data-testid="stChatMessageContent"] p {
            color: #47342a;
            line-height: 1.7;
            font-size: 0.98rem;
        }
        div[data-testid="stChatMessageContent"] {
            background: transparent !important;
            padding: 0.28rem 0.38rem;
        }
        div[data-testid="stChatInput"] {
            background: rgba(255,255,255,0.98);
            border: 1px solid rgba(179,127,96,0.16);
            border-radius: 22px;
            box-shadow: 0 12px 26px rgba(126, 83, 58, 0.08);
            padding: 0.35rem 0.4rem;
            max-width: 980px;
            margin-left: auto;
            margin-right: auto;
        }
        div[data-testid="stChatInput"] textarea,
        div[data-testid="stChatInput"] input {
            background: white !important;
            color: #3e2a22 !important;
        }
        div[data-testid="stHorizontalBlock"] div[role="radiogroup"] {
            gap: 0.45rem;
        }
        div[role="radiogroup"] label {
            background: rgba(255, 247, 240, 0.98);
            border: 1px solid rgba(217, 164, 129, 0.18);
            border-radius: 999px;
            padding: 0.38rem 0.78rem;
        }
        div[role="radiogroup"] label[data-selected="true"] {
            background: #f7e0cf;
            border-color: rgba(177, 111, 74, 0.28);
        }
        div[data-testid="stButton"] > button {
            border-radius: 999px;
            border: 1px solid rgba(179, 127, 96, 0.14);
            background: white;
        }
        .prompt-note {
            color: #7a5b4a;
            font-size: 0.88rem;
            margin: 0.15rem 0 0.45rem;
        }
        @media (max-width: 900px) {
            .hero-card {
                padding: 1.2rem 1rem;
            }
            .app-bar {
                top: 0.3rem;
                padding: 0.72rem 0.9rem;
            }
            .top-nav {
                padding: 0.9rem 0.95rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <section class="hero-card">
            <div class="hero-tag">Maternal Care Prototype Powered by RAG and NLP Models</div>
            <h1>MamaCare AI</h1>
            <p class="hero-copy">
                A calm, stage-aware pregnancy companion designed to help mothers ask questions with confidence
                and receive grounded support across symptoms, nutrition, baby development, and birth preparation.
            </p>
            <div class="hero-subcopy">Warm support, clearer answers, and a simpler conversation space for every stage of pregnancy.</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_app_bar() -> None:
    st.markdown(
        """
        <section class="app-bar">
            <div class="app-bar-title">MamaCare AI</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_top_navigation() -> str:
    st.markdown(
        """
        <section class="top-nav">
            <div class="top-nav-title">Pregnancy guidance made simpler</div>
            <div class="top-nav-copy">
                Choose the pregnancy stage you want MamaCare to focus on, then ask your question in the chat below.
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    nav_col_1, nav_col_2 = st.columns([4.8, 1.4], vertical_alignment="center")
    with nav_col_1:
        trimester = st.radio(
            "Pregnancy stage",
            options=["all", "T1", "T2", "T3"],
            horizontal=True,
            label_visibility="collapsed",
            format_func=lambda value: {
                "all": "All stages",
                "T1": "Trimester 1",
                "T2": "Trimester 2",
                "T3": "Trimester 3",
            }[value],
        )
    with nav_col_2:
        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    st.markdown('<div class="prompt-note">Quick starts for common questions:</div>', unsafe_allow_html=True)
    prompt_col_1, prompt_col_2, prompt_col_3 = st.columns(3)
    with prompt_col_1:
        if st.button("Nausea support", use_container_width=True):
            st.session_state.pending_prompt = "I am in my first trimester and feel nauseated. What can help?"
    with prompt_col_2:
        if st.button("Healthy eating", use_container_width=True):
            st.session_state.pending_prompt = "How can I ensure I am eating healthy?"
    with prompt_col_3:
        if st.button("Reduced movement", use_container_width=True):
            st.session_state.pending_prompt = "The baby is moving less today at 31 weeks."

    return trimester


def render_chat_shell() -> None:
    st.markdown(
        """
        <section class="chat-shell" id="chat-box">
            <div class="chat-shell-head">
                <div>
                    <h3>MamaCare AI</h3>
                    <div class="chat-shell-copy">
                        Ask one question at a time. Older messages can be collapsed so you can focus on the latest response.
                    </div>
                </div>
            </div>
            <div class="history-note">Simple, warm support for pregnancy questions.</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Conversation Rendering
# ---------------------------------------------------------------------------
# The chat history is split into recent messages and collapsible older messages
# so the latest answer remains easy to read on small and large screens.
def render_messages() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Hello mama 💛\n\n"
                    "I’m MamaCare AI, and I’m here to support you with warm, grounded guidance through pregnancy.\n\n"
                    "You can ask me about symptoms, food, baby movement, antenatal visits, birth preparation, or warning signs."
                ),
                "sources": [],
                "flags": [],
            }
        ]

    message_count = len(st.session_state.messages)
    visible_start = max(0, message_count - 4)
    older_messages = st.session_state.messages[:visible_start]
    visible_messages = st.session_state.messages[visible_start:]

    if older_messages:
        with st.expander(f"Earlier conversation ({len(older_messages)} messages)", expanded=False):
            for message in older_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    if message["flags"]:
                        st.caption("Flags: " + ", ".join(message["flags"]))
                    if message["sources"]:
                        with st.expander("Sources"):
                            for source in message["sources"]:
                                st.markdown(
                                    f"- **{source['source_name']}**: "
                                    f"{source['title']} ({source['trimester']})"
                                )

    for message in visible_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["flags"]:
                st.caption("Flags: " + ", ".join(message["flags"]))
            if message["sources"]:
                with st.expander("Sources"):
                    for source in message["sources"]:
                        st.markdown(
                            f"- **{source['source_name']}**: "
                            f"{source['title']} ({source['trimester']})"
                        )


# ---------------------------------------------------------------------------
# Main App Flow
# ---------------------------------------------------------------------------
# This is the orchestration layer for the Streamlit page. It applies styles,
# renders the hero, captures user prompts, calls the service, and displays the
# returned answer with citations inside a focused chat-first interface.
def main() -> None:
    service = get_service()
    render_styles()
    render_app_bar()
    render_hero()
    trimester = render_top_navigation()

    render_chat_shell()
    render_messages()

    typed_prompt = st.chat_input(
        "Ask about symptoms, nutrition, antenatal visits, birth prep, or danger signs"
    )
    prompt = typed_prompt or st.session_state.pop("pending_prompt", None)
    if not prompt:
        return

    st.session_state.messages.append(
        {"role": "user", "content": prompt, "sources": [], "flags": []}
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state.messages[-6:]
    ]
    response = service.ask_with_history(
        prompt,
        trimester=trimester,
        conversation_history=history,
    )
    payload = {
        "role": "assistant",
        "content": response.answer,
        "sources": response.citations,
        "flags": response.flags,
    }
    st.session_state.messages.append(payload)

    with st.chat_message("assistant"):
        if "EMERGENCY" in response.flags:
            st.error(response.answer)
        elif "DOCTOR_REFERRAL" in response.flags:
            st.warning(response.answer)
        else:
            st.markdown(response.answer)

        if response.flags:
            st.caption("Flags: " + ", ".join(response.flags))
        if response.citations:
            with st.expander("Sources"):
                for source in response.citations:
                    st.markdown(
                        f"- **{source['source_name']}**: "
                        f"{source['title']} ({source['trimester']})"
                    )

if __name__ == "__main__":
    main()
