import time
import streamlit as st
from modules.utils import show_diagram, question_selector, get_primary_model
from modules.diagrams import BASELINE_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


def render():
    PRIMARY_MODEL = get_primary_model()
    st.title("Baseline — Direct API Call (No Gateway)")
    st.write(
        "This is what most apps start with: calling the LLM directly. "
        "It works, but you have zero visibility, no retries, and no fallback. "
        "We'll use this as our benchmark to compare against gateway-enabled experiments."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(BASELINE_DIAGRAM, height=220)
        st.caption("Your app talks directly to Groq. No middleware, no logging, no safety net.")

    st.divider()

    st.subheader("Configure")

    groq_key = st.text_input(
        "Groq API Key (for this baseline demo only)",
        value=st.session_state.get("groq_api_key", ""),
        type="password",
        placeholder="gsk_...",
        help="Get a free key at console.groq.com"
    )
    if groq_key:
        st.session_state.groq_api_key = groq_key

    question = question_selector("baseline", INTERESTING_QUESTIONS)

    st.divider()

    if st.button("Run Baseline Call", type="primary", width="stretch"):
        if not st.session_state.get("groq_api_key"):
            st.warning("Enter your Groq API Key above to run the baseline demo.")
            return

        with st.spinner("Calling Groq directly..."):
            try:
                from groq import Groq
                client = Groq(api_key=st.session_state.groq_api_key)
                start = time.time()
                response = client.chat.completions.create(
                    model=PRIMARY_MODEL,
                    messages=[{"role": "user", "content": question}],
                    max_tokens=250,
                )
                elapsed_ms = int((time.time() - start) * 1000)
                text = response.choices[0].message.content or ""
                st.session_state.baseline_result = {
                    "text": text,
                    "latency": elapsed_ms,
                    "model": response.model,
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }
            except Exception as e:
                st.error(f"Error: {e}")
                return

    if st.session_state.get("baseline_result"):
        r = st.session_state.baseline_result
        st.divider()
        st.subheader("Result")

        col1, col2, col3 = st.columns(3)
        col1.metric("Latency", f"{r['latency']} ms")
        col2.metric("Prompt Tokens", r["prompt_tokens"])
        col3.metric("Completion Tokens", r["completion_tokens"])

        st.write(r["text"])
        st.caption(f"Model: {r['model']}")

        st.divider()
        st.subheader("What you can't see from this call")
        st.write(
            "- No log of what was asked or answered\n"
            "- No cost tracking\n"
            "- If this fails with a 429, your app crashes\n"
            "- If Groq is down, users see an error\n"
            "- No caching — same question costs the same every time"
        )
        st.info("In the next experiment, we add Portkey as a gateway. The call looks identical — but now you get full observability.")
