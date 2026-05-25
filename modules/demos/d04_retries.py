import streamlit as st
from modules.utils import (
    require_keys, make_client, timed_call, extract_text,
    build_messages, show_diagram, question_selector, get_model_used,
    get_virtual_key, get_primary_model
)
from modules.diagrams import RETRY_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


def render():
    PRIMARY_MODEL = get_primary_model()
    st.title("Automatic Retries")
    st.write(
        "LLMs hit rate limits (429) and occasionally throw 500 errors. "
        "Without a gateway, your app crashes and the user sees an error. "
        "With Portkey's retry config, failed requests are automatically retried with exponential backoff "
        "— your app never knows anything went wrong."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(RETRY_DIAGRAM, height=520)
        st.caption(
            "Portkey catches error status codes and retries with increasing delays. "
            "After all attempts are exhausted, it returns the error — but most transient failures resolve before then."
        )

    st.divider()

    require_keys()

    st.subheader("Configure Retry Behavior")

    col1, col2 = st.columns(2)
    with col1:
        attempts = st.slider("Max retry attempts", min_value=1, max_value=5, value=3)
    with col2:
        status_codes = st.multiselect(
            "Retry on these status codes",
            options=[429, 500, 502, 503, 504],
            default=[429, 500, 503],
        )

    if not status_codes:
        status_codes = [429, 500, 503]

    retry_config = {
        "virtual_key": get_virtual_key(),
        "retry": {
            "attempts": attempts,
            "on_status_codes": status_codes,
        },
    }

    with st.expander("Generated Portkey Config"):
        st.json(retry_config)
        st.code(
            f"""portkey = Portkey(
    api_key="YOUR_PORTKEY_KEY",
    config={retry_config}
)""",
            language="python"
        )

    st.divider()

    question = question_selector("retries", INTERESTING_QUESTIONS)

    if st.button("Send Request with Retry Config", type="primary", width="stretch"):
        with st.spinner("Sending (Portkey will retry automatically if any failures occur)..."):
            try:
                client = make_client(config=retry_config)
                response, elapsed = timed_call(client, build_messages(question))
                text = extract_text(response)
                st.session_state.retry_result = {
                    "text": text,
                    "latency": elapsed,
                    "model": get_model_used(response),
                    "config": retry_config,
                }
            except Exception as e:
                st.error(f"Error after all retry attempts: {e}")
                st.info("This error appeared because all retry attempts were exhausted. In production, you'd also add a fallback.")
                return

    if st.session_state.get("retry_result"):
        r = st.session_state.retry_result
        st.divider()
        st.subheader("Result")

        col1, col2, col3 = st.columns(3)
        col1.metric("Latency", f"{r['latency']} ms")
        col2.metric("Max Attempts", attempts)
        col3.metric("Retry Codes", str(status_codes))

        st.write(r["text"])
        st.caption(f"Model: {r['model']}")

        st.divider()
        st.subheader("How Retry Protects Your App")

        col1, col2 = st.columns(2)
        with col1:
            st.write("**Without retry**")
            st.write(
                "- First 429 or 500 → your app throws an exception\n"
                "- User sees an error message\n"
                "- You lose the request\n"
                "- You have to build retry logic yourself"
            )
        with col2:
            st.write("**With Portkey retry**")
            st.write(
                f"- First failure → wait 1s → try again\n"
                f"- Second failure → wait 2s → try again\n"
                f"- Up to {attempts} attempts total\n"
                "- Your app receives the successful response\n"
                "- Zero custom retry code needed"
            )

        st.info(
            "Retry pairs well with fallback. If all retries fail, Portkey can then route to a backup model. "
            "See the Fallback experiment to combine these."
        )
