import time
import streamlit as st
from modules.utils import (
    require_keys, make_client, extract_text, build_messages,
    show_diagram, get_model_used, get_virtual_key,
    get_primary_model, get_fallback_model, get_fallback_key
)
from modules.diagrams import RESILIENCE_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


_SCENARIOS = {
    "Happy Path — primary succeeds": "happy",
    "Tight Timeout — primary times out, retries, then fallback": "timeout",
    "Force Failure — invalid primary key triggers fallback": "force",
}


def render():
    PRIMARY_MODEL = get_primary_model()
    FALLBACK_MODEL = get_fallback_model()
    vk = get_virtual_key()
    fvk = get_fallback_key()

    st.title("Retry + Timeout + Fallback — Combined Resilience")
    st.write(
        "Each of these three features is useful alone. Together they form a complete resilience stack: "
        "**Timeout** prevents hanging requests, **Retry** handles transient blips, "
        "and **Fallback** saves the day when the primary model is persistently unavailable. "
        "This is what you actually deploy in production."
    )

    with st.expander("How they chain together", expanded=True):
        show_diagram(RESILIENCE_DIAGRAM, height=520)
        st.caption(
            "When a request fails: Portkey first retries the same model with backoff. "
            "If all retries are exhausted, it routes to the fallback model. "
            "A timeout counts as a failure — it triggers the same retry → fallback chain."
        )

    st.divider()

    require_keys()

    st.subheader("Configure the Resilience Stack")

    col1, col2, col3 = st.columns(3)
    with col1:
        timeout_ms = st.slider(
            "Timeout per attempt (ms)",
            min_value=1000, max_value=30000, value=10000, step=1000,
            help="Each attempt (including retries) has this hard time limit."
        )
    with col2:
        retry_attempts = st.slider(
            "Retry attempts on primary",
            min_value=1, max_value=4, value=2,
            help="How many times to retry the primary model before giving up and switching to fallback."
        )
    with col3:
        st.write("**Models**")
        st.write(f"Primary: `{PRIMARY_MODEL}`")
        st.write(f"Fallback: `{FALLBACK_MODEL}`")

    st.divider()

    st.subheader("Choose a Scenario")
    scenario_label = st.radio(
        "What do you want to demonstrate?",
        list(_SCENARIOS.keys()),
        label_visibility="collapsed",
    )
    scenario = _SCENARIOS[scenario_label]

    if scenario == "happy":
        st.info(
            "Primary model is called normally. If it succeeds (which it should), "
            "you see the result from the primary. The resilience config is in place but never triggered."
        )
        primary_vk = vk
        effective_timeout = timeout_ms

    elif scenario == "timeout":
        effective_timeout = 2000
        primary_vk = vk
        st.warning(
            "Timeout is forced to **2 seconds** — the primary model will almost certainly time out. "
            "Portkey will retry it, time out again, then fall back to the smaller (faster) model "
            "which usually responds in time. Watch which model answers."
        )

    else:  # force
        primary_vk = "invalid-demo-key"
        effective_timeout = timeout_ms
        st.error(
            "The primary virtual key is deliberately set to an **invalid slug**. "
            "Portkey will get an auth error immediately, retry, keep failing, "
            "then route to the fallback model using your real key."
        )

    combined_config = {
        "strategy": {"mode": "fallback"},
        "request_timeout": effective_timeout,
        "retry": {
            "attempts": retry_attempts,
            "on_status_codes": [408, 429, 500, 502, 503],
        },
        "targets": [
            {
                "virtual_key": primary_vk,
                "override_params": {"model": PRIMARY_MODEL},
            },
            {
                "virtual_key": fvk,
                "override_params": {"model": FALLBACK_MODEL},
            },
        ],
    }

    with st.expander("Full config being sent to Portkey"):
        st.json(combined_config)
        st.caption(
            f"Timeout: {effective_timeout}ms per attempt | "
            f"Retry: {retry_attempts} attempts on primary | "
            f"Fallback: {FALLBACK_MODEL}"
        )

    st.divider()

    question = st.selectbox("Question:", INTERESTING_QUESTIONS, key="resilience_q")
    custom_q = st.text_input("Or type your own:", key="resilience_custom", placeholder="Ask anything...")
    active_q = custom_q.strip() if custom_q.strip() else question

    if st.button("Run with Full Resilience Stack", type="primary", width="stretch"):
        if scenario == "timeout":
            spinner_msg = "Running with 2s timeout — expect retries and fallback activation..."
        elif scenario == "force":
            spinner_msg = "Running with invalid primary key — fallback will activate..."
        else:
            spinner_msg = "Running through full resilience config..."

        with st.spinner(spinner_msg):
            try:
                client = make_client(config=combined_config)
                start = time.time()
                response = client.chat.completions.create(
                    model=PRIMARY_MODEL,
                    messages=build_messages(active_q),
                    max_tokens=250,
                )
                elapsed = int((time.time() - start) * 1000)
                model_used = get_model_used(response)
                text = extract_text(response)

                used_fallback = FALLBACK_MODEL in model_used or (
                    PRIMARY_MODEL not in model_used and "8b" in model_used
                )

                st.session_state.resilience_result = {
                    "text": text,
                    "latency": elapsed,
                    "model": model_used,
                    "used_fallback": used_fallback,
                    "scenario": scenario,
                    "timeout_used": effective_timeout,
                }
            except Exception as e:
                st.error(f"All attempts failed: {e}")
                st.info(
                    "Every retry and fallback attempt was exhausted. "
                    "In production, add more fallback targets or queue the request."
                )
                return

    if st.session_state.get("resilience_result"):
        r = st.session_state.resilience_result
        st.divider()
        st.subheader("Result")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Latency", f"{r['latency']} ms")
        col2.metric("Answered By", "Fallback" if r["used_fallback"] else "Primary")
        col3.metric("Timeout Per Attempt", f"{r['timeout_used']} ms")
        col4.metric("Max Retries", retry_attempts)

        st.write(r["text"])
        st.caption(f"Model: {r['model']}")

        if r["used_fallback"]:
            if r["scenario"] == "timeout":
                st.success(
                    f"Primary timed out (>{r['timeout_used']}ms). "
                    f"Portkey retried {retry_attempts} time(s), then fell back to `{FALLBACK_MODEL}`. "
                    "Your app got a response — no error shown to the user."
                )
            elif r["scenario"] == "force":
                st.success(
                    f"Primary returned auth errors (invalid key). "
                    f"After {retry_attempts} retry attempt(s), Portkey switched to `{FALLBACK_MODEL}`. "
                    "Zero code changes in your app."
                )
        else:
            st.info(
                f"Primary model answered successfully in {r['latency']}ms. "
                "The resilience config is active but no failures occurred. "
                "Try the 'Tight Timeout' or 'Force Failure' scenario to see fallback activate."
            )

        st.divider()
        st.subheader("Why this combination matters")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.write("**Timeout alone**")
            st.write("Prevents hangs. But if it triggers, your app gets an error and the user sees it.")
        with c2:
            st.write("**Retry alone**")
            st.write("Handles blips. But if the model is down for minutes, retries keep failing and waste time.")
        with c3:
            st.write("**All three together**")
            st.write(
                "Timeout cuts slow requests quickly. "
                "Retry catches brief failures. "
                "Fallback handles prolonged outages. "
                "Your app stays up through all of it."
            )
