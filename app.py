"""Streamlit application entry point for the MamaCare AI prototype.

This file is intentionally UI-focused. It wires the local retrieval service into
an interface that is easy for mothers, reviewers, donors, and collaborators to
understand during demos and early pilot discussions.
"""

from __future__ import annotations

import sys
import time
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
    initial_sidebar_state="expanded",
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
            background: linear-gradient(180deg, #fffaf6 0%, #fff8f3 100%);
            color: #2f231d;
        }
        .block-container {
            max-width: 900px;
            padding-top: 0.08rem;
            padding-bottom: 1rem;
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
        h1, h2, h3 {
            font-family: "Iowan Old Style", "Palatino Linotype", serif;
            color: #4c2d22;
        }
        p, li, label, div, span {
            font-family: "Aptos", "Trebuchet MS", sans-serif;
        }
        [data-testid="stSidebar"] {
            background: rgba(255, 255, 255, 0.9);
            border-right: 1px solid rgba(179, 127, 96, 0.12);
        }
        button[title="View fullscreen"] {
            display: none;
        }
        [data-testid="stSidebarContent"] {
            padding-top: 0.8rem;
        }
        .sidebar-card {
            border-radius: 16px;
            padding: 0.9rem 1rem;
            background: rgba(255, 250, 246, 0.96);
            border: 1px solid rgba(179, 127, 96, 0.12);
            margin-bottom: 0.8rem;
            box-shadow: 0 4px 12px rgba(126, 83, 58, 0.04);
        }
        .sidebar-title {
            font-family: "Iowan Old Style", "Palatino Linotype", serif;
            font-size: 1rem;
            color: #4c2d22;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }
        .sidebar-copy {
            color: #5e4436;
            font-size: 0.88rem;
            line-height: 1.6;
        }
        .sidebar-note {
            color: #7a5b4a;
            font-size: 0.82rem;
            line-height: 1.55;
        }
        .hero-card {
            border-radius: 16px;
            padding: 0.8rem 1rem;
            background: rgba(255, 255, 255, 0.8);
            border: 1px solid rgba(179, 127, 96, 0.1);
            margin-bottom: 0.5rem;
            max-width: 900px;
            margin-left: auto;
            margin-right: auto;
        }
        .app-bar {
            position: sticky;
            top: 0.15rem;
            z-index: 1000;
            max-width: 900px;
            margin: 0 auto 0.3rem;
            padding: 0.5rem 0.9rem;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(179, 127, 96, 0.1);
            box-shadow: 0 4px 12px rgba(126, 83, 58, 0.05);
            backdrop-filter: blur(8px);
        }
        .app-bar-title {
            font-family: "Iowan Old Style", "Palatino Linotype", serif;
            font-size: 1.1rem;
            color: #4c2d22;
            font-weight: 700;
            margin: 0;
        }
        .hero-tag {
            display: inline-block;
            background: rgba(249, 228, 212, 0.6);
            color: #77472c;
            border-radius: 999px;
            padding: 0.25rem 0.6rem;
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 0.4rem;
        }
        .hero-copy {
            font-size: 0.9rem;
            line-height: 1.5;
            color: #5e4436;
            margin: 0;
        }
        .hero-subcopy {
            margin: 0;
            color: #74584a;
            font-size: 0.88rem;
        }
        div[data-testid="stChatMessageContainer"] {
            max-width: 900px;
            margin-left: auto;
            margin-right: auto;
        }
        div[data-testid="stChatMessage"] {
            border-radius: 16px;
            padding: 0.2rem 0.25rem;
            margin-bottom: 0.6rem;
        }
        div[data-testid="stChatMessage"][aria-label="Chat message from assistant"] {
            background: linear-gradient(180deg, #fff6cc 0%, #fff8da 100%);
            border: 1px solid rgba(215, 187, 92, 0.32);
            box-shadow: 0 6px 14px rgba(126, 83, 58, 0.05);
            border-radius: 18px;
        }
        div[data-testid="stChatMessage"][aria-label="Chat message from user"] {
            background: rgba(254, 243, 235, 0.95);
            border: 1px solid rgba(217, 164, 129, 0.15);
        }
        div[data-testid="stChatMessageContent"] p {
            color: #47342a;
            line-height: 1.6;
            font-size: 0.95rem;
            margin: 0.3rem 0;
        }
        div[data-testid="stChatMessage"][aria-label="Chat message from assistant"] div[data-testid="stMarkdownContainer"] {
            color: #4b3624;
        }
        div[data-testid="stChatMessage"][aria-label="Chat message from assistant"] ul,
        div[data-testid="stChatMessage"][aria-label="Chat message from assistant"] li {
            color: #9a6a00;
        }
        div[data-testid="stChatMessageContent"] {
            background: transparent !important;
            padding: 0.35rem 0.45rem;
        }
        div[data-testid="stChatInput"] {
            background: rgba(255,255,255,0.95);
            border: 1px solid rgba(179,127,96,0.14);
            border-radius: 16px;
            box-shadow: 0 6px 16px rgba(126, 83, 58, 0.06);
            padding: 0.3rem 0.35rem;
            max-width: 900px;
            margin-left: auto;
            margin-right: auto;
        }
        div[data-testid="stChatInput"] textarea,
        div[data-testid="stChatInput"] input {
            background: white !important;
            color: #3e2a22 !important;
        }
        div[role="radiogroup"] label {
            background: rgba(255, 247, 240, 0.9);
            border: 1px solid rgba(217, 164, 129, 0.15);
            border-radius: 999px;
            padding: 0.35rem 0.75rem;
            font-size: 0.85rem;
            font-weight: 500;
        }
        div[role="radiogroup"] label[data-selected="true"] {
            background: rgba(247, 224, 207, 0.8);
            border-color: rgba(177, 111, 74, 0.25);
        }
        div[data-testid="stButton"] > button {
            border-radius: 999px;
            border: 1px solid rgba(179, 127, 96, 0.12);
            background: white;
            font-size: 0.9rem;
            font-weight: 500;
            padding: 0.35rem 0.8rem;
        }
        div[data-testid="stExpander"] {
            border-radius: 12px;
            border: 1px solid rgba(179,127,96,0.1);
            background: rgba(255, 252, 248, 0.8);
        }
        .status-note {
            color: #7a5b4a;
            font-size: 0.85rem;
            margin-top: 0.3rem;
            padding: 0.35rem 0.6rem;
            background: rgba(249, 228, 212, 0.2);
            border-radius: 6px;
        }
        @media (max-width: 900px) {
            .block-container {
                padding-left: 0.3rem;
                padding-right: 0.3rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <section class="sidebar-card">
                <div class="sidebar-title">About This Prototype</div>
                <div class="sidebar-copy">
                    MamaCare AI is a prototype that shows how AI can use a RAG model to answer pregnancy-related questions
                    from a grounded local knowledge base.
                </div>
                <div class="sidebar-note" style="margin-top: 0.55rem;">
                    It is not a real medical tool and should not replace doctors, midwives, or any qualified healthcare professional.
                    For urgent symptoms, emergencies, diagnosis, treatment, or personal medical decisions, please contact your care team directly.
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <section class="sidebar-card">
                <div class="sidebar-title">Acknowledgement</div>
                <div class="sidebar-copy">
                    With appreciation to the AI Everything GITEX Summit and the International Telecommunication Union (ITU)
                    for giving the NexaMom team the opportunity to present this AI use case during the hackathon challenge.
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <section class="sidebar-card">
                <div class="sidebar-title">What MamaCare Can Answer</div>
                <div class="sidebar-note">
                    Symptoms and warning signs<br/>
                    Nutrition and hydration<br/>
                    Baby movement and development<br/>
                    Antenatal care and tests<br/>
                    Emotional wellbeing<br/>
                    Birth preparation and postpartum basics
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )


def render_hero() -> None:
    st.markdown(
        """
        <section class="hero-card">
            <div class="hero-tag">Pregnancy Guidance - Created by Team NexaMom</div>
            <h1 style="font-size: 1.8rem; margin: 0.3rem 0; line-height: 1.2;">MamaCare AI</h1>
            <p class="hero-copy">A prototype showing how AI and RAG can support grounded answers to pregnancy-related questions.</p>
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
    col_1, col_2, col_3 = st.columns([3, 1, 1], vertical_alignment="center")
    
    with col_1:
        trimester = st.radio(
            "Pregnancy stage",
            options=["all", "T1", "T2", "T3"],
            horizontal=True,
            label_visibility="collapsed",
            format_func=lambda value: {
                "all": "All stages",
                "T1": "1st Tri",
                "T2": "2nd Tri",
                "T3": "3rd Tri",
            }[value],
        )
    with col_2:
        if st.button("Clear", use_container_width=True, key="clear_btn"):
            st.session_state.messages = []
            st.rerun()
    with col_3:
        pass

    st.markdown(
        "<div class='status-note'><strong>Popular questions:</strong> tap one below or type your own question in the chat box.</div>",
        unsafe_allow_html=True,
    )
    starter_rows = [
        [
            ("First-trimester nausea", "I am in my first trimester and feel nauseated. What can help?"),
            ("Headache in pregnancy", "I am having headache, what can I do?"),
            ("Healthy eating", "How can I ensure I am eating healthy during pregnancy?"),
        ],
        [
            ("Baby moving less", "The baby is moving less today at 31 weeks. Should I be concerned?"),
            ("First antenatal visit", "What happens at the first antenatal visit?"),
            ("Postpartum depression", "Tell me more about postpartum depression."),
        ],
    ]
    for row_index, row in enumerate(starter_rows):
        row_columns = st.columns(len(row), gap="small")
        for column, (label, prompt_text) in zip(row_columns, row):
            with column:
                if st.button(label, key=f"starter_{row_index}_{label}", use_container_width=True):
                    st.session_state.pending_prompt = prompt_text

    return trimester


def render_chat_shell() -> None:
    st.markdown(
        """
        <section class="hero-card" style="padding: 0.85rem 1rem; margin-top: 0.8rem; margin-bottom: 0.8rem;">
            <div style="font-size: 1rem; font-weight: 700; color: #4c2d22; margin-bottom: 0.2rem;">Your conversation</div>
            <div style="font-size: 0.92rem; color: #6a4a3b; line-height: 1.6;">
                Ask one clear pregnancy question at a time. The more specific the symptom or topic, the more focused the answer can be.
            </div>
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
                    "I'm MamaCare AI. Ask me anything about pregnancy - symptoms, nutrition, baby development, birth prep, or warning signs.\n\n"
                    "For emergencies, contact your healthcare provider immediately."
                ),
                "sources": [],
                "flags": [],
                "out_of_context": False,
                "supported_topics": [],
            }
        ]

    message_count = len(st.session_state.messages)
    visible_start = max(0, message_count - 2)
    older_messages = st.session_state.messages[:visible_start]
    visible_messages = st.session_state.messages[visible_start:]

    if older_messages:
        with st.expander(f"Earlier conversation ({len(older_messages)} messages)", expanded=False):
            for message in older_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    if message["flags"]:
                        st.caption("Flags: " + ", ".join(message["flags"]))
                    if message.get("out_of_context") and message.get("supported_topics"):
                        with st.expander("Current build topics"):
                            for topic in message["supported_topics"]:
                                st.markdown(f"- {topic}")
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
            if message.get("out_of_context") and message.get("supported_topics"):
                with st.expander("Current build topics"):
                    for topic in message["supported_topics"]:
                        st.markdown(f"- {topic}")
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
    render_sidebar()
    render_app_bar()
    render_hero()
    trimester = render_top_navigation()

    render_chat_shell()
    render_messages()

    typed_prompt = st.chat_input(
        "Ask your pregnancy question here..."
    )
    prompt = typed_prompt or st.session_state.pop("pending_prompt", None)
    if not prompt:
        return

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt,
            "sources": [],
            "flags": [],
            "out_of_context": False,
            "supported_topics": [],
        }
    )
    with st.chat_message("user"):
        st.markdown(prompt)

    history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state.messages[-6:]
    ]
    with st.chat_message("assistant"):
        with st.status("Searching...", expanded=False) as status:
            started_at = time.perf_counter()
            response = service.ask_with_history(
                prompt,
                trimester=trimester,
                conversation_history=history,
            )
            elapsed = time.perf_counter() - started_at
            if elapsed < 0.45:
                time.sleep(0.18)
            status.update(label="Complete", state="complete", expanded=False)
        if "EMERGENCY" in response.flags:
            st.error(response.answer)
        elif "DOCTOR_REFERRAL" in response.flags:
            st.warning(response.answer)
        else:
            st.markdown(response.answer)

        if response.flags:
            st.caption("Flags: " + ", ".join(response.flags))
        if response.out_of_context and response.supported_topics:
            with st.expander("Current build topics"):
                for topic in response.supported_topics:
                    st.markdown(f"- {topic}")
        if response.citations:
            with st.expander("Sources"):
                for source in response.citations:
                    st.markdown(
                        f"- **{source['source_name']}**: "
                        f"{source['title']} ({source['trimester']})"
                    )
    payload = {
        "role": "assistant",
        "content": response.answer,
        "sources": response.citations,
        "flags": response.flags,
        "out_of_context": response.out_of_context,
        "supported_topics": response.supported_topics,
    }
    st.session_state.messages.append(payload)

if __name__ == "__main__":
    main()
