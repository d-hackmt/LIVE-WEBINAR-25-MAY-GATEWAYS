import streamlit as st
from modules.utils import (
    require_keys, make_client, extract_text, build_messages,
    show_diagram, question_selector, get_model_used, get_virtual_key,
    get_primary_model, get_fallback_model, get_fallback_key
)
from modules.diagrams import FALLBACK_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS
import time


def render():
    PRIMARY_MODEL = get_primary_model()
    FALLBACK_MODEL = get_fallback_model()
    st.title("Fallback Routing")
    st.write(
        "What happens when your primary LLM goes down or hits its quota? "
        "With fallback routing, Portkey automatically switches to a backup model — "
        "no code changes, no downtime, no user-visible errors. "
        "The fallback can be a different model, a different provider, or just a smaller, cheaper version."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(FALLBACK_DIAGRAM, height=300)
        st.caption(
            "Portkey tries the primary target first. On any failure (4xx, 5xx), it immediately "
            "routes the same request to the next target in the list."
        )

    st.divider()

    require_keys()

    vk = get_virtual_key()
    fvk = get_fallback_key()

    st.subheader("Fallback Setup")

    col1, col2 = st.columns(2)
    with col1:
        st.write("**Primary target**")
        st.write(f"Model: `{PRIMARY_MODEL}`")
        st.write(f"Virtual Key: `{vk}`")

    with col2:
        st.write("**Fallback target**")
        st.write(f"Model: `{FALLBACK_MODEL}`")
        st.write(f"Virtual Key: `{fvk}`" + (" *(same as primary)*" if fvk == vk else ""))

    simulate_failure = st.toggle(
        "Simulate primary failure (force fallback to activate)",
        value=False,
        help="When ON, the primary target uses an invalid key so Portkey is forced to fall back to the secondary."
    )

    if simulate_failure:
        st.warning(
            "Primary will use an invalid virtual key. Portkey will get an auth error from the primary, "
            "then automatically route to the fallback model. Watch which model appears in the result."
        )
        primary_target = {"override_params": {"model": f"@invalid-key-for-demo/{PRIMARY_MODEL}"}}
    else:
        primary_target = {"override_params": {"model": f"@{vk}/{PRIMARY_MODEL}"}}

    fallback_config = {
        "strategy": {"mode": "fallback"},
        "targets": [
            primary_target,
            {"override_params": {"model": f"@{fvk}/{FALLBACK_MODEL}"}},
        ],
    }

    with st.expander("Generated Config"):
        st.json(fallback_config)

    st.divider()

    question = question_selector("fallbacks", INTERESTING_QUESTIONS)

    if st.button("Run with Fallback Config", type="primary", width="stretch"):
        label = "Testing fallback (primary will fail, fallback will answer)..." if simulate_failure else "Running with fallback config..."
        with st.spinner(label):
            try:
                client = make_client(config=fallback_config)
                start = time.time()
                response = client.chat.completions.create(
                    model=PRIMARY_MODEL,
                    messages=build_messages(question),
                    max_tokens=250,
                )
                elapsed = int((time.time() - start) * 1000)
                model_used = get_model_used(response)
                st.session_state.fallback_result = {
                    "text": extract_text(response),
                    "latency": elapsed,
                    "model": model_used,
                    "was_fallback": simulate_failure,
                    "expected_fallback": FALLBACK_MODEL in model_used,
                }
            except Exception as e:
                st.error(f"Error: {e}")
                return

    if st.session_state.get("fallback_result"):
        r = st.session_state.fallback_result
        st.divider()
        st.subheader("Result")

        col1, col2, col3 = st.columns(3)
        col1.metric("Latency", f"{r['latency']} ms")
        col2.metric("Model Used", r["model"].split("-")[0] + "..." if len(r["model"]) > 15 else r["model"])
        with col3:
            if r["was_fallback"]:
                if FALLBACK_MODEL in r["model"] or "8b" in r["model"]:
                    st.metric("Fallback", "Activated", delta="primary failed")
                else:
                    st.metric("Result", "Unexpected", delta="check model")
            else:
                st.metric("Primary", "Answered", delta="no failure")

        st.write(r["text"])
        st.caption(f"Answered by: {r['model']}")

        if r["was_fallback"]:
            st.success(
                f"The primary target failed. Portkey automatically routed to `{FALLBACK_MODEL}` and got a response. "
                "Your application received a valid response without any error handling code."
            )
        else:
            st.info(
                "Primary model answered successfully. Toggle 'Simulate primary failure' above to see "
                "what happens when the primary is unavailable and the fallback kicks in."
            )

        st.divider()
        st.subheader("Real-world fallback scenarios")
        st.write(
            "- **Model unavailable**: Provider maintenance, outages\n"
            "- **Rate limit exceeded**: Primary quota exhausted, fallback has fresh quota\n"
            "- **Cost control**: Fallback to cheaper model when budget is tight\n"
            "- **Cross-provider**: Primary is Groq, fallback is OpenAI or Anthropic\n"
            "- **Latency spike**: Primary is slow, fallback (smaller model) is faster"
        )
