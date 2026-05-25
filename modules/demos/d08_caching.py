import streamlit as st
from modules.utils import (
    require_keys, make_client, extract_text, build_messages,
    show_diagram, get_model_used, get_virtual_key, get_primary_model
)
from modules.diagrams import CACHE_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS
import time


def render():
    PRIMARY_MODEL = get_primary_model()
    st.title("Response Caching")
    st.write(
        "Portkey can cache responses to identical requests. "
        "The first call goes to the LLM and takes normal time. "
        "The second identical call returns the cached response almost instantly — "
        "with zero LLM cost and a fraction of the latency."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(CACHE_DIAGRAM, height=400)
        st.caption(
            "Portkey hashes the request (model + messages). On cache hit, it returns the stored response. "
            "On cache miss, it calls the LLM, stores the response, then returns it."
        )

    st.divider()

    require_keys()

    vk = get_virtual_key()

    cache_config = {
        "virtual_key": vk,
        "cache": {"mode": "simple"},
    }

    with st.expander("Cache Config"):
        st.json(cache_config)
        st.caption(
            "`simple` mode: exact-match cache. "
            "Same model + same messages = cache hit. "
            "Change even one character → cache miss."
        )

    st.divider()

    st.subheader("Pick a Question")
    st.write("Choose or write a question. You'll run it twice — first for the cache miss, then for the cache hit.")

    question = st.selectbox("Choose a question:", INTERESTING_QUESTIONS, key="cache_question_select")
    custom_q = st.text_input("Or type your own:", placeholder="Be exact — the cache matches character-for-character")
    active_question = custom_q.strip() if custom_q.strip() else question

    st.info(f"Active question: **{active_question}**")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Run 1 — Cache Miss")
        st.write("This will call the LLM because nothing is cached yet.")

        if st.button("Run First Request (Cold)", width="stretch"):
            with st.spinner("Calling LLM (cache miss expected)..."):
                try:
                    client = make_client(config=cache_config)
                    tagged = client.with_options(cache_force_refresh=True)
                    start = time.time()
                    response = tagged.chat.completions.create(
                        model=PRIMARY_MODEL,
                        messages=build_messages(active_question),
                        max_tokens=250,
                    )
                    elapsed = int((time.time() - start) * 1000)
                    st.session_state.cache_miss = {
                        "text": extract_text(response),
                        "latency": elapsed,
                        "model": get_model_used(response),
                        "question": active_question,
                    }
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.session_state.get("cache_miss"):
            r = st.session_state.cache_miss
            st.metric("Latency (Miss)", f"{r['latency']} ms")
            st.write(r["text"])
            st.caption(f"Model: {r['model']}")

    with col2:
        st.subheader("Run 2 — Cache Hit")
        st.write("Send the same question again. Portkey should return the cached response instantly.")

        cache_question = st.session_state.get("cache_miss", {}).get("question", active_question)

        if not st.session_state.get("cache_miss"):
            st.info("Run the first request first.")
        else:
            if st.button("Run Second Request (Cached)", type="primary", width="stretch"):
                with st.spinner("Checking cache..."):
                    try:
                        client = make_client(config=cache_config)
                        start = time.time()
                        response = client.chat.completions.create(
                            model=PRIMARY_MODEL,
                            messages=build_messages(cache_question),
                            max_tokens=250,
                        )
                        elapsed = int((time.time() - start) * 1000)
                        st.session_state.cache_hit = {
                            "text": extract_text(response),
                            "latency": elapsed,
                            "model": get_model_used(response),
                        }
                    except Exception as e:
                        st.error(f"Error: {e}")

            if st.session_state.get("cache_hit"):
                r = st.session_state.cache_hit
                miss_latency = st.session_state.cache_miss["latency"]
                speedup = miss_latency / r["latency"] if r["latency"] > 0 else 1
                st.metric(
                    "Latency (Hit)",
                    f"{r['latency']} ms",
                    delta=f"-{miss_latency - r['latency']}ms vs cold",
                )
                st.write(r["text"])
                st.caption(f"Model: {r['model']}")

    if st.session_state.get("cache_miss") and st.session_state.get("cache_hit"):
        st.divider()
        st.subheader("Comparison")

        miss_l = st.session_state.cache_miss["latency"]
        hit_l = st.session_state.cache_hit["latency"]
        speedup = miss_l / hit_l if hit_l > 0 else 1

        col1, col2, col3 = st.columns(3)
        col1.metric("Cold (Miss)", f"{miss_l} ms")
        col2.metric("Cached (Hit)", f"{hit_l} ms")
        col3.metric("Speedup", f"{speedup:.1f}x faster")

        st.write(
            "The cached response is identical to the original. "
            "The LLM was not called for the second request — "
            "Portkey returned the stored result instantly."
        )

        st.divider()
        st.subheader("When caching pays off")
        st.write(
            "- **FAQ bots**: Users ask the same questions repeatedly\n"
            "- **Search assistants**: Common queries hit cache, rare ones miss\n"
            "- **Report generation**: Same report template processed multiple times\n"
            "- **Dev / test environments**: Run tests without burning API quota every time\n\n"
            "To bypass the cache for a specific request, use `cache_force_refresh=True`."
        )
