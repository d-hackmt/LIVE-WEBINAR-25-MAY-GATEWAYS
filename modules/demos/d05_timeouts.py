import streamlit as st
from modules.utils import (
    require_keys, make_client, timed_call, extract_text,
    build_messages, show_diagram, question_selector, get_model_used,
    get_virtual_key, get_primary_model
)
from modules.diagrams import TIMEOUT_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


def render():
    PRIMARY_MODEL = get_primary_model()
    st.title("Request Timeouts")
    st.write(
        "Sometimes an LLM takes too long — a stuck request can hang your entire app indefinitely. "
        "Portkey's timeout config lets you set a hard time limit in milliseconds. "
        "If the model doesn't respond in time, Portkey returns a 408 error and you can handle it gracefully."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(TIMEOUT_DIAGRAM, height=440)
        st.caption(
            "The timer starts when Portkey receives your request. "
            "If the LLM hasn't responded by the deadline, Portkey cuts the connection and returns 408."
        )

    st.divider()

    require_keys()

    st.subheader("Set Timeout")

    timeout_ms = st.slider(
        "Timeout (milliseconds)",
        min_value=1000,
        max_value=60000,
        value=15000,
        step=1000,
        help="How long to wait before giving up. 15,000ms = 15 seconds."
    )

    col1, col2 = st.columns(2)
    col1.metric("Timeout", f"{timeout_ms} ms")
    col2.metric("Equals", f"{timeout_ms / 1000:.1f} seconds")

    timeout_config = {
        "virtual_key": get_virtual_key(),
        "request_timeout": timeout_ms,
    }

    with st.expander("Generated Config"):
        st.json(timeout_config)

    st.divider()

    st.subheader("Demo: Normal Request vs Tight Timeout")

    question = question_selector("timeouts", INTERESTING_QUESTIONS)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Run with Your Timeout", type="primary", width="stretch"):
            with st.spinner(f"Running with {timeout_ms / 1000:.0f}s timeout..."):
                try:
                    client = make_client(config=timeout_config)
                    response, elapsed = timed_call(client, build_messages(question))
                    st.session_state.timeout_normal = {
                        "text": extract_text(response),
                        "latency": elapsed,
                        "model": get_model_used(response),
                        "success": True,
                    }
                except Exception as e:
                    st.session_state.timeout_normal = {
                        "text": str(e),
                        "latency": timeout_ms,
                        "model": "—",
                        "success": False,
                    }

    with col2:
        if st.button("Force Timeout (1 second limit)", width="stretch"):
            with st.spinner("Running with 1s timeout (will timeout)..."):
                try:
                    tight_config = {
                        "virtual_key": get_virtual_key(),
                        "request_timeout": 1000,
                    }
                    client = make_client(config=tight_config)
                    response, elapsed = timed_call(client, build_messages(question))
                    st.session_state.timeout_tight = {
                        "text": extract_text(response),
                        "latency": elapsed,
                        "model": get_model_used(response),
                        "success": True,
                    }
                except Exception as e:
                    st.session_state.timeout_tight = {
                        "text": str(e),
                        "latency": 1000,
                        "model": "—",
                        "success": False,
                    }

    if st.session_state.get("timeout_normal") or st.session_state.get("timeout_tight"):
        st.divider()
        st.subheader("Results")

        r1 = st.session_state.get("timeout_normal")
        r2 = st.session_state.get("timeout_tight")

        c1, c2 = st.columns(2)
        with c1:
            if r1:
                if r1["success"]:
                    st.success(f"Normal timeout ({timeout_ms}ms): **Succeeded in {r1['latency']}ms**")
                    st.write(r1["text"])
                else:
                    st.error(f"Timed out at {timeout_ms}ms")
                    st.write(r1["text"])
        with c2:
            if r2:
                if r2["success"]:
                    st.success(f"Tight timeout (1000ms): Somehow succeeded in {r2['latency']}ms")
                    st.write(r2["text"])
                else:
                    st.error("1s timeout: Request exceeded time limit")
                    st.info("This is a 408 error — timeout triggered. In production, show the user a friendly message and retry.")

        st.divider()
        st.subheader("When to use timeouts")
        st.write(
            "- **User-facing features**: 10–15s max. Users abandon after 15 seconds.\n"
            "- **Background jobs**: 60–120s. More tolerance for slow responses.\n"
            "- **Combine with retry**: Timeout + retry means 'try fast, if too slow, try again.'\n"
            "- **Combine with fallback**: Timeout + fallback means 'if primary is slow, switch to faster model.'"
        )
