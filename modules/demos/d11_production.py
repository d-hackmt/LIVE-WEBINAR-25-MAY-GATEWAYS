import time
import streamlit as st
from modules.utils import (
    require_keys, make_client, extract_text, build_messages,
    show_diagram, get_model_used, get_virtual_key,
    get_primary_model, get_fallback_model, get_fallback_key
)
from modules.diagrams import PRODUCTION_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


def _build_production_config(vk: str, fvk: str, timeout_ms: int, retry_attempts: int,
                              weight_primary: float, enable_cache: bool,
                              primary_model: str, fallback_model: str) -> dict:
    config = {
        "strategy": {"mode": "fallback"},
        "request_timeout": timeout_ms,
        "retry": {
            "attempts": retry_attempts,
            "on_status_codes": [429, 500, 503],
        },
        "targets": [
            {
                "virtual_key": vk,
                "weight": weight_primary,
                "override_params": {"model": primary_model},
            },
            {
                "virtual_key": fvk,
                "weight": round(1.0 - weight_primary, 2),
                "override_params": {"model": fallback_model},
            },
        ],
    }
    if enable_cache:
        config["cache"] = {"mode": "simple"}
    return config


def render():
    PRIMARY_MODEL = get_primary_model()
    FALLBACK_MODEL = get_fallback_model()
    vk = get_virtual_key()
    fvk = get_fallback_key()
    st.title("Production Config — Everything Combined")
    st.write(
        "Real production apps need all of these features working together. "
        "This experiment lets you configure the full stack — fallback, retry, timeout, and cache — "
        "and run requests against it. This is the config you'd actually deploy."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(PRODUCTION_DIAGRAM, height=540)
        st.caption(
            "Every request passes through the full pipeline. Portkey handles all failure modes "
            "transparently. Your app code remains clean and simple."
        )

    st.divider()

    require_keys()

    st.subheader("Configure Your Production Stack")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Resilience**")
        timeout_ms = st.slider("Request timeout (ms)", 5000, 60000, 30000, step=5000,
                                help="Hard limit before Portkey gives up")
        retry_attempts = st.slider("Retry attempts", 1, 4, 2,
                                    help="Retries per target on 429/500/503")

    with col2:
        st.write("**Routing**")
        weight_pct = st.slider("Primary model traffic %", 0, 100, 80, step=10,
                                help="Rest goes to fallback model")
        enable_cache = st.toggle("Enable caching", value=True,
                                  help="Cache exact-match queries")

    production_config = _build_production_config(
        vk=vk, fvk=fvk,
        timeout_ms=timeout_ms,
        retry_attempts=retry_attempts,
        weight_primary=weight_pct / 100,
        enable_cache=enable_cache,
        primary_model=PRIMARY_MODEL,
        fallback_model=FALLBACK_MODEL,
    )

    with st.expander("Full Production Config JSON"):
        st.json(production_config)
        st.code(
            f"""from portkey_ai import Portkey

portkey = Portkey(
    api_key="YOUR_PORTKEY_KEY",
    config={production_config}
)

response = portkey.chat.completions.create(
    model="{PRIMARY_MODEL}",
    messages=[{{"role": "user", "content": "..."}}]
)""",
            language="python"
        )
        st.caption(
            "This is all you need. Portkey handles fallback, retry, timeout, and caching. "
            "Your business logic doesn't change at all."
        )

    st.divider()

    st.subheader("Feature Summary")
    feature_cols = st.columns(4)
    feature_cols[0].metric("Timeout", f"{timeout_ms // 1000}s")
    feature_cols[1].metric("Retry", f"{retry_attempts}x")
    feature_cols[2].metric("Traffic split", f"{weight_pct}/{100 - weight_pct}")
    feature_cols[3].metric("Cache", "On" if enable_cache else "Off")

    st.divider()

    st.subheader("Run Production Requests")

    question = st.selectbox("Question:", INTERESTING_QUESTIONS, key="prod_question")
    custom_q = st.text_input("Or type your own:", key="prod_custom_q", placeholder="Any question...")
    active_q = custom_q.strip() if custom_q.strip() else question

    add_metadata = st.toggle("Add metadata tags (user, session, feature)", value=True)

    if add_metadata:
        mc1, mc2 = st.columns(2)
        with mc1:
            meta_user = st.text_input("Your name:", value="demo-user", key="prod_meta_user")
            meta_feature = st.text_input("Feature:", value="production-demo", key="prod_meta_feature")
        with mc2:
            meta_env = st.selectbox("Environment:", ["production", "staging", "development"], key="prod_meta_env")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Run Request", type="primary", width="stretch"):
            with st.spinner("Running through production config..."):
                try:
                    client = make_client(config=production_config)
                    if add_metadata:
                        metadata = {
                            "_user": meta_user,
                            "feature": meta_feature,
                            "environment": meta_env,
                        }
                        client = client.with_options(metadata=metadata)

                    start = time.time()
                    response = client.chat.completions.create(
                        model=PRIMARY_MODEL,
                        messages=build_messages(active_q),
                        max_tokens=250,
                    )
                    elapsed = int((time.time() - start) * 1000)
                    text = extract_text(response)
                    model = get_model_used(response)
                    tokens = getattr(getattr(response, "usage", None), "total_tokens", "—")

                    result = {
                        "text": text,
                        "latency": elapsed,
                        "model": model,
                        "tokens": tokens,
                        "question": active_q,
                        "cache_likely_hit": False,
                    }
                    if "prod_first_latency" not in st.session_state:
                        st.session_state.prod_first_latency = elapsed
                    elif elapsed < st.session_state.prod_first_latency * 0.4 and enable_cache:
                        result["cache_likely_hit"] = True

                    st.session_state.prod_result = result
                    st.session_state.prod_run_count = st.session_state.get("prod_run_count", 0) + 1
                    st.session_state.prod_latencies = st.session_state.get("prod_latencies", []) + [elapsed]

                except Exception as e:
                    st.error(f"Error: {e}")
                    return

    with col2:
        if st.button("Run Same Question Again (test cache)", width="stretch"):
            if not st.session_state.get("prod_result"):
                st.warning("Run at least one request first.")
            else:
                cached_q = st.session_state.prod_result["question"]
                with st.spinner("Running again (same question)..."):
                    try:
                        client = make_client(config=production_config)
                        start = time.time()
                        response = client.chat.completions.create(
                            model=PRIMARY_MODEL,
                            messages=build_messages(cached_q),
                            max_tokens=250,
                        )
                        elapsed = int((time.time() - start) * 1000)
                        first = st.session_state.prod_first_latency or elapsed
                        hit = enable_cache and elapsed < first * 0.5
                        st.session_state.prod_repeat = {
                            "latency": elapsed,
                            "text": extract_text(response),
                            "model": get_model_used(response),
                            "cache_hit": hit,
                            "first_latency": first,
                        }
                        st.session_state.prod_latencies = st.session_state.get("prod_latencies", []) + [elapsed]
                    except Exception as e:
                        st.error(f"Error: {e}")

    if st.session_state.get("prod_result"):
        r = st.session_state.prod_result
        st.divider()
        st.subheader("Latest Result")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Latency", f"{r['latency']} ms")
        m2.metric("Model Used", "70b" if PRIMARY_MODEL in str(r['model']) else "8b")
        m3.metric("Tokens", r["tokens"])
        m4.metric("Requests Run", st.session_state.get("prod_run_count", 1))

        st.write(r["text"])
        st.caption(f"Model: {r['model']}")

    if st.session_state.get("prod_repeat"):
        rep = st.session_state.prod_repeat
        st.divider()
        st.subheader("Repeat Request Result")

        col1, col2, col3 = st.columns(3)
        col1.metric("First request", f"{rep['first_latency']} ms")
        col2.metric("Repeat request", f"{rep['latency']} ms",
                    delta=f"-{rep['first_latency'] - rep['latency']}ms" if rep['latency'] < rep['first_latency'] else None)
        col3.metric("Cache", "Likely HIT" if rep["cache_hit"] else "Check dashboard",
                    delta="fast!" if rep["cache_hit"] else None)

        if rep["cache_hit"] and enable_cache:
            st.success("Repeat request was significantly faster — likely served from cache.")
        elif enable_cache:
            st.info("Repeat request ran. Check your Portkey dashboard logs for cache_status: HIT.")

    if st.session_state.get("prod_latencies") and len(st.session_state.prod_latencies) > 1:
        st.divider()
        st.subheader("Latency Trend")
        latencies = st.session_state.prod_latencies
        st.line_chart({"Latency (ms)": latencies})
        st.caption("Watch how latency drops when cache kicks in after the first request.")

    st.divider()
    st.subheader("What this config does for you in production")

    c1, c2 = st.columns(2)
    with c1:
        st.write("**Reliability**")
        st.write(
            f"- Timeout of {timeout_ms // 1000}s prevents hanging requests\n"
            f"- {retry_attempts} retries absorb transient errors automatically\n"
            "- Fallback to smaller model if primary is unavailable\n"
            "- Your app stays running through outages"
        )
    with c2:
        st.write("**Cost & Performance**")
        st.write(
            f"- {weight_pct}% traffic to high-quality primary, {100 - weight_pct}% to cheaper fallback\n"
            + ("- Cache eliminates repeat LLM calls entirely\n" if enable_cache else "- Enable cache to eliminate repeat calls\n")
            + "- All requests logged: full cost visibility\n"
            "- No infra to manage — Portkey handles everything"
        )
