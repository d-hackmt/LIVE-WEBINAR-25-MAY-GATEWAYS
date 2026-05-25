import time
import concurrent.futures
import streamlit as st
from modules.utils import (
    require_keys, make_client, extract_text, build_messages,
    show_diagram, get_model_used, get_virtual_key,
    get_primary_model, get_fallback_model, get_fallback_key
)
from modules.diagrams import RATE_LIMIT_DIAGRAM
from modules.questions import RAPID_FIRE_QUESTIONS


def _fire_request(args):
    client, question, idx, delay, model = args
    time.sleep(delay)
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question}],
            max_tokens=60,
        )
        elapsed = int((time.time() - start) * 1000)
        return {
            "idx": idx + 1,
            "question": question,
            "status": "success",
            "model": get_model_used(response),
            "latency": elapsed,
            "answer": (extract_text(response) or "")[:80],
        }
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        err_str = str(e)
        return {
            "idx": idx + 1,
            "question": question,
            "status": "error",
            "model": "—",
            "latency": elapsed,
            "answer": err_str[:120],
        }


def render():
    PRIMARY_MODEL = get_primary_model()
    FALLBACK_MODEL = get_fallback_model()
    st.title("Rate Limiting & Resilience")
    st.write(
        "Groq and other LLM APIs enforce rate limits — too many requests per minute and you get 429 errors. "
        "In a production app with multiple users, this happens constantly. "
        "Combining Portkey's retry with fallback gives you a resilience stack: "
        "retry the same model first, then fall back to an alternative if retries fail."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(RATE_LIMIT_DIAGRAM, height=560)
        st.caption(
            "Portkey absorbs 429s transparently. Your app only sees the final successful response "
            "— or a clear error after all retry and fallback options are exhausted."
        )

    st.divider()

    require_keys()

    vk = get_virtual_key()
    fvk = get_fallback_key()

    st.subheader("Configure: Retry + Fallback Combined")

    col1, col2 = st.columns(2)
    with col1:
        retry_attempts = st.slider("Retry attempts on 429/500", 1, 4, 2)
    with col2:
        num_requests = st.slider("Number of rapid-fire requests", 3, 8, 5)

    resilience_config = {
        "strategy": {"mode": "fallback"},
        "retry": {
            "attempts": retry_attempts,
            "on_status_codes": [429, 500, 503],
        },
        "targets": [
            {
                "virtual_key": vk,
                "override_params": {"model": PRIMARY_MODEL},
            },
            {
                "virtual_key": fvk,
                "override_params": {"model": FALLBACK_MODEL},
            },
        ],
    }

    with st.expander("Generated Resilience Config (Retry + Fallback)"):
        st.json(resilience_config)
        st.write(
            "This config gives each request up to:\n"
            f"1. {retry_attempts} attempts on the primary model (70b)\n"
            f"2. If all retries fail, {retry_attempts} more attempts on the fallback model (8b)\n"
            "Any 429 or 500 from either triggers the next attempt."
        )

    st.divider()

    st.subheader(f"Fire {num_requests} Rapid Requests")
    st.write(
        "These requests are fired with zero delay between them. "
        "On a free-tier Groq account, rapid bursts may trigger 429s — "
        "watch how Portkey handles them."
    )

    questions_to_use = RAPID_FIRE_QUESTIONS[:num_requests]

    for i, q in enumerate(questions_to_use):
        st.text(f"Request {i + 1}: {q}")

    if st.button(f"Fire {num_requests} Requests Now", type="primary", width="stretch"):
        client = make_client(config=resilience_config)
        args_list = [(client, q, i, 0, PRIMARY_MODEL) for i, q in enumerate(questions_to_use)]

        progress = st.progress(0, text="Firing all requests...")
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_fire_request, args): args[2] for args in args_list}
            done = 0
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
                done += 1
                progress.progress(done / len(args_list), text=f"{done}/{len(args_list)} complete")

        progress.empty()
        results.sort(key=lambda x: x["idx"])
        st.session_state.rate_limit_results = results

    if st.session_state.get("rate_limit_results"):
        results = st.session_state.rate_limit_results
        st.divider()
        st.subheader("Results")

        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = len(results) - success_count

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Requests", len(results))
        col2.metric("Successful", success_count)
        col3.metric("Failed (after retries)", error_count)

        for r in results:
            if r["status"] == "success":
                with st.expander(f"Request {r['idx']} — Success in {r['latency']}ms — {r['question']}"):
                    st.write(r["answer"])
                    st.caption(f"Model: {r['model']} | Latency: {r['latency']}ms")
            else:
                with st.expander(f"Request {r['idx']} — Failed after all retries — {r['question']}"):
                    st.error(r["answer"])
                    st.caption("All retry attempts and fallback attempts were exhausted.")

        if error_count == 0:
            st.success(
                "All requests succeeded! If any hit 429s, Portkey retried automatically. "
                "Try increasing the number of requests or reducing your Groq rate limit quota to see retries in action."
            )
        else:
            st.warning(
                f"{error_count} request(s) failed after exhausting all retries and fallback. "
                "In production, you'd add more fallback targets or queue failed requests."
            )

        st.divider()
        st.subheader("The resilience stack explained")
        st.write(
            f"For each request, Portkey runs through this sequence:\n\n"
            f"1. Try primary model (70b) — attempt 1 of {retry_attempts}\n"
            f"2. If 429/500 → wait and retry — attempt 2 of {retry_attempts}\n"
            f"3. If still failing after {retry_attempts} attempts → switch to fallback (8b)\n"
            f"4. Try fallback model — up to {retry_attempts} attempts\n"
            f"5. If everything fails → return error to your app\n\n"
            "Your application code has zero awareness of any of this."
        )
