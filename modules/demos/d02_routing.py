import streamlit as st
from modules.utils import (
    require_keys, make_client, timed_call, extract_text,
    build_messages, show_diagram, question_selector, get_model_used,
    get_primary_model, get_virtual_key
)
from modules.diagrams import ROUTING_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


def render():
    PRIMARY_MODEL = get_primary_model()
    st.title("Routing & Observability")
    st.write(
        "Every request now passes through Portkey before reaching Groq. "
        "Your code barely changes — but every call is automatically logged to your Portkey dashboard "
        "with token counts, latency, cost, and the full prompt and response."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(ROUTING_DIAGRAM, height=300)
        st.caption("Portkey acts as a transparent proxy. Same API shape — full visibility added.")

    st.divider()

    require_keys()

    st.subheader("The Code Change")
    st.code(
        f"""from portkey_ai import Portkey

portkey = Portkey(
    api_key="YOUR_PORTKEY_KEY",
    virtual_key="{get_virtual_key() or 'your-virtual-key-slug'}"
)

response = portkey.chat.completions.create(
    model="{PRIMARY_MODEL}",
    messages=[{{"role": "user", "content": "..."}}]
)
print(response.choices[0].message.content)
""",
        language="python"
    )
    st.caption("That's the entire change. Same response format as OpenAI SDK. Everything else happens automatically.")

    st.divider()

    question = question_selector("routing", INTERESTING_QUESTIONS)

    if st.button("Run Through Gateway", type="primary", width="stretch"):
        with st.spinner("Routing through Portkey..."):
            try:
                client = make_client()
                response, elapsed = timed_call(client, build_messages(question))
                text = extract_text(response)
                model = get_model_used(response)
                st.session_state.routing_result = {
                    "text": text,
                    "latency": elapsed,
                    "model": model,
                    "tokens": getattr(getattr(response, "usage", None), "total_tokens", "—"),
                }
            except Exception as e:
                st.error(f"Error: {e}")
                return

    if st.session_state.get("routing_result"):
        r = st.session_state.routing_result
        st.divider()
        st.subheader("Result")

        col1, col2, col3 = st.columns(3)
        col1.metric("Latency", f"{r['latency']} ms")
        col2.metric("Total Tokens", r["tokens"])
        col3.metric("Gateway", "Portkey", delta="logged")

        st.write(r["text"])
        st.caption(f"Model: {r['model']}")

        st.divider()
        st.subheader("What just happened in your dashboard")
        st.write(
            "Open your Portkey dashboard and you'll see this request logged with:\n\n"
            "- Full prompt and response text\n"
            "- Token counts and estimated cost\n"
            "- Latency in milliseconds\n"
            "- The model used\n"
            "- Timestamp and request ID\n\n"
            "No code changes needed to get all of this."
        )
        st.success("Check portkey.ai > Logs to see this request appear.")
