import uuid
import streamlit as st
from modules.utils import (
    require_keys, make_client, timed_call, extract_text,
    build_messages, show_diagram, question_selector, get_model_used,
    get_primary_model
)
from modules.diagrams import METADATA_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


FEATURE_OPTIONS = [
    "general-chat",
    "customer-support",
    "content-generation",
    "code-assistant",
    "data-analysis",
    "onboarding-flow",
]

ENV_OPTIONS = ["development", "staging", "production"]


def render():
    PRIMARY_MODEL = get_primary_model()
    st.title("Metadata & Observability")
    st.write(
        "Portkey logs every request automatically — but with metadata, you can tag each request "
        "with context like which user sent it, which feature it came from, and which environment it ran in. "
        "This turns raw logs into actionable analytics you can filter and slice in the dashboard."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(METADATA_DIAGRAM, height=320)
        st.caption(
            "Metadata flows alongside every request. In the dashboard, filter by user, session, "
            "feature, or environment to understand exactly where your costs and latency come from."
        )

    st.divider()

    require_keys()

    st.subheader("Create Your Profile")
    st.write("Fill in your details below. These will be attached to your request as metadata. Check your Portkey dashboard after running to find yourself there!")

    col1, col2 = st.columns(2)
    with col1:
        user_name = st.text_input(
            "Your Name (this becomes your user ID)",
            value=st.session_state.get("meta_user", ""),
            placeholder="e.g. alice, rahul, student-42"
        )
        if user_name:
            st.session_state.meta_user = user_name

        feature = st.selectbox(
            "Feature / Context",
            FEATURE_OPTIONS,
            index=FEATURE_OPTIONS.index(st.session_state.get("meta_feature", FEATURE_OPTIONS[0]))
            if st.session_state.get("meta_feature") in FEATURE_OPTIONS else 0
        )
        st.session_state.meta_feature = feature

    with col2:
        session_id = st.text_input(
            "Session ID",
            value=st.session_state.get("meta_session", ""),
            placeholder="leave blank to auto-generate"
        )
        if not session_id:
            if "meta_session" not in st.session_state or not st.session_state.meta_session:
                st.session_state.meta_session = f"session-{str(uuid.uuid4())[:8]}"
            session_id = st.session_state.meta_session
        else:
            st.session_state.meta_session = session_id

        environment = st.selectbox(
            "Environment",
            ENV_OPTIONS,
            index=ENV_OPTIONS.index(st.session_state.get("meta_env", "development"))
            if st.session_state.get("meta_env") in ENV_OPTIONS else 0
        )
        st.session_state.meta_env = environment

    metadata_preview = {
        "_user": user_name or "anonymous",
        "session_id": session_id,
        "feature": feature,
        "environment": environment,
    }

    with st.expander("Preview metadata that will be sent"):
        st.json(metadata_preview)
        st.caption(
            "`_user` is a special Portkey key that enables per-user analytics. "
            "You can filter the entire dashboard by this value."
        )

    st.divider()

    question = question_selector("metadata", INTERESTING_QUESTIONS)

    if st.button("Send Tagged Request", type="primary", width="stretch"):
        with st.spinner("Sending with metadata..."):
            try:
                client = make_client()
                tagged_client = client.with_options(metadata=metadata_preview)
                messages = build_messages(question)
                import time
                start = time.time()
                response = tagged_client.chat.completions.create(
                    model=PRIMARY_MODEL,
                    messages=messages,
                    max_tokens=250,
                )
                elapsed = int((time.time() - start) * 1000)
                st.session_state.metadata_result = {
                    "text": extract_text(response),
                    "latency": elapsed,
                    "model": get_model_used(response),
                    "metadata": metadata_preview,
                }
            except Exception as e:
                st.error(f"Error: {e}")
                return

    if st.session_state.get("metadata_result"):
        r = st.session_state.metadata_result
        st.divider()
        st.subheader("Result")

        col1, col2 = st.columns(2)
        col1.metric("Latency", f"{r['latency']} ms")
        col2.metric("Tagged As", r["metadata"]["_user"])

        st.write(r["text"])
        st.caption(f"Model: {r['model']}")

        st.divider()
        st.subheader("What to look for in your dashboard")
        st.write(
            f"In Portkey > Logs, find this request and you'll see all metadata tags attached to it.\n\n"
            f"In Portkey > Analytics, you can now:\n\n"
            f"- Filter all requests by `_user = {r['metadata']['_user']}`\n"
            f"- See total cost broken down by `feature = {r['metadata']['feature']}`\n"
            f"- Track latency trends per `environment = {r['metadata']['environment']}`\n\n"
            "As you send more requests, patterns emerge. Which user is most expensive? "
            "Which feature has the highest latency? Metadata makes this answerable."
        )
        st.success(f"Your request is tagged. Search for user '{r['metadata']['_user']}' in the Portkey dashboard.")
