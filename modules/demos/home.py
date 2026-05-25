import streamlit as st


def render():
    st.title("LLM Gateway Explorer")
    st.subheader("Hands-on experiments with Portkey — run real LLM calls, see everything live.")

    st.info(
        "This app teaches you how an LLM Gateway works by letting you run each concept yourself. "
        "Every button fires a real API call. Every result is logged to your Portkey dashboard."
    )

    st.divider()

    st.header("What is an LLM Gateway?")
    st.write(
        "When your app calls an LLM directly, you have no control over retries, no visibility into costs, "
        "no fallback when the model is down, and no caching to save money. "
        "An LLM Gateway sits between your app and the model, giving you all of that — transparently."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Without Gateway", "Blind", delta="no logs, no retries")
    with col2:
        st.metric("With Gateway", "Full Control", delta="logs, retries, cache, fallback")
    with col3:
        st.metric("Extra Cost", "$0", delta="Portkey free tier is generous")

    st.divider()

    st.header("Setup — 3 steps to get started")

    with st.expander("Step 1 — Create a Portkey account", expanded=True):
        st.write("Go to portkey.ai and sign up for a free account. You'll get a Portkey API Key from the dashboard.")

    with st.expander("Step 2 — Create a Virtual Key connecting your Groq API key"):
        st.write(
            "In the Portkey dashboard, go to **Virtual Keys** and click **Add Key**. "
            "Select Groq as the provider, paste your Groq API key, and give it a short slug like `my-groq`. "
            "This slug is your **Virtual Key Slug** — it hides your real Groq key from your code."
        )
        st.write("Get a free Groq API key at console.groq.com.")

    with st.expander("Step 3 — Enter your keys in the sidebar"):
        st.write(
            "Open the **API Keys** section in the sidebar (left panel). "
            "Enter your Portkey API Key and the Virtual Key Slug you just created. "
            "Once both are saved, the green checkmark appears and all demos are ready to run."
        )

    st.divider()

    st.header("Experiments in this app")

    experiments = [
        ("Baseline", "Direct Groq call with no gateway — your starting point for comparison."),
        ("Routing & Observability", "Route every call through Portkey. Every request appears in your dashboard automatically."),
        ("Metadata & Tracking", "Tag requests with your name, session, and feature. Filter analytics by these tags in the dashboard."),
        ("Automatic Retries", "Configure Portkey to retry on 429 or 500 errors. Your app never sees transient failures."),
        ("Request Timeouts", "Set a hard time limit. Portkey returns 408 if the LLM takes too long."),
        ("Fallback Routing", "If the primary model fails, Portkey auto-switches to the fallback. Zero code changes."),
        ("Load Balancing", "Split traffic across models by weight. Send 10 requests and watch the distribution."),
        ("Response Caching", "Cache exact-match queries. Second call returns instantly at near-zero cost."),
        ("Rate Limiting", "Fire rapid requests, see 429s get retried and fallen back automatically."),
        ("Streaming", "Stream tokens live through the gateway — full observability still works."),
        ("Production Config", "Combine everything: fallback + retry + timeout + cache. The real-world setup."),
    ]

    for i, (name, desc) in enumerate(experiments):
        with st.expander(f"{'Baseline' if i == 0 else str(i)}. {name}"):
            st.write(desc)

    st.divider()
    st.caption("Models used: llama-3.3-70b-versatile (primary) and llama-3.1-8b-instant (fallback) via Groq.")
    st.caption("Portkey is a free LLM gateway. No extra cost per request beyond your Groq API usage.")
