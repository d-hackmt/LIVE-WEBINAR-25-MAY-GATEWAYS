import time
import concurrent.futures
import streamlit as st
from modules.utils import (
    require_keys, make_client, extract_text, build_messages,
    show_diagram, get_model_used, get_virtual_key,
    get_primary_model, get_fallback_model, get_fallback_key
)
from modules.diagrams import LOAD_BALANCE_DIAGRAM
from modules.questions import LOAD_BALANCE_QUESTIONS


def _single_request(args):
    client, question, idx, model = args
    try:
        start = time.time()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question}],
            max_tokens=80,
        )
        elapsed = int((time.time() - start) * 1000)
        return {
            "idx": idx,
            "question": question[:60] + ("..." if len(question) > 60 else ""),
            "model": get_model_used(response),
            "latency": elapsed,
            "answer": (extract_text(response) or "")[:100],
            "error": None,
        }
    except Exception as e:
        return {
            "idx": idx,
            "question": question[:60] + ("..." if len(question) > 60 else ""),
            "model": "error",
            "latency": 0,
            "answer": "",
            "error": str(e),
        }


def render():
    PRIMARY_MODEL = get_primary_model()
    FALLBACK_MODEL = get_fallback_model()
    st.title("Load Balancing")
    st.write(
        "Instead of sending all requests to one model, load balancing distributes traffic by weight. "
        "Useful for A/B testing models, gradual migration to a new model, "
        "managing quota across accounts, or blending cost vs quality."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(LOAD_BALANCE_DIAGRAM, height=320)
        st.caption(
            "Each incoming request is probabilistically routed to a target based on weight. "
            "With 70/30, about 7 out of 10 requests go to the large model and 3 to the small model."
        )

    st.divider()

    require_keys()

    vk = get_virtual_key()
    fvk = get_fallback_key()

    st.subheader("Configure Traffic Split")

    weight_large = st.slider(
        f"Weight for {PRIMARY_MODEL} (large, slower, higher quality)",
        min_value=0,
        max_value=100,
        value=70,
        step=10,
    )
    weight_small = 100 - weight_large

    col1, col2 = st.columns(2)
    col1.metric(f"Large model ({PRIMARY_MODEL.split('-')[2]})", f"{weight_large}%")
    col2.metric(f"Small model ({FALLBACK_MODEL.split('-')[2]})", f"{weight_small}%")

    load_balance_config = {
        "strategy": {"mode": "loadbalance"},
        "targets": [
            {
                "virtual_key": vk,
                "weight": weight_large / 100,
                "override_params": {"model": PRIMARY_MODEL},
            },
            {
                "virtual_key": fvk,
                "weight": weight_small / 100,
                "override_params": {"model": FALLBACK_MODEL},
            },
        ],
    }

    with st.expander("Generated Config"):
        st.json(load_balance_config)

    st.divider()

    st.subheader("Questions to Fire")
    st.write("Edit or add questions below. All of them will be fired simultaneously.")

    if "lb_questions" not in st.session_state:
        st.session_state.lb_questions = LOAD_BALANCE_QUESTIONS.copy()

    new_q = st.text_input("Add a question:", placeholder="Type anything and press Enter")
    if new_q and new_q not in st.session_state.lb_questions:
        if st.button("Add Question"):
            st.session_state.lb_questions.append(new_q)
            st.rerun()

    edited_questions = st.data_editor(
        [{"question": q} for q in st.session_state.lb_questions],
        num_rows="dynamic",
        width="stretch",
        key="lb_questions_editor",
    )
    active_questions = [row["question"] for row in edited_questions if row.get("question", "").strip()]

    st.metric("Total requests to fire", len(active_questions))

    st.divider()

    if st.button("Fire All Requests", type="primary", width="stretch"):
        if not active_questions:
            st.warning("Add at least one question.")
            return

        client = make_client(config=load_balance_config)
        args_list = [(client, q, i, PRIMARY_MODEL) for i, q in enumerate(active_questions)]

        progress = st.progress(0, text="Firing requests in parallel...")
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_single_request, args): args[2] for args in args_list}
            done_count = 0
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
                done_count += 1
                progress.progress(done_count / len(active_questions),
                                   text=f"Completed {done_count}/{len(active_questions)} requests...")

        progress.empty()
        results.sort(key=lambda x: x["idx"])
        st.session_state.lb_results = results
        st.session_state.lb_weights = (weight_large, weight_small)

    if st.session_state.get("lb_results"):
        results = st.session_state.lb_results
        w_large, w_small = st.session_state.get("lb_weights", (70, 30))

        st.divider()
        st.subheader("Results")

        large_count = sum(1 for r in results if FALLBACK_MODEL not in r["model"] and r["error"] is None)
        small_count = sum(1 for r in results if FALLBACK_MODEL in r["model"] and r["error"] is None)
        error_count = sum(1 for r in results if r["error"])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Requests", len(results))
        col2.metric(f"Large model (70b)", large_count)
        col3.metric(f"Small model (8b)", small_count)
        col4.metric("Errors", error_count)

        if large_count + small_count > 0:
            actual_split = large_count / (large_count + small_count) * 100
            st.write(f"Actual distribution: **{actual_split:.0f}% large / {100 - actual_split:.0f}% small** (configured: {w_large}% / {w_small}%)")
            st.caption("Distribution is probabilistic — with more requests, it converges to the configured weights.")

        for r in results:
            if r["error"]:
                st.error(f"**Q{r['idx'] + 1}**: {r['question']} — Error: {r['error']}")
            else:
                is_small = FALLBACK_MODEL in r["model"]
                prefix = "Small" if is_small else "Large"
                with st.expander(f"Q{r['idx'] + 1} → {prefix} model ({r['latency']}ms): {r['question']}"):
                    st.write(r["answer"])
                    st.caption(f"Model: {r['model']} | Latency: {r['latency']}ms")

        st.divider()
        st.subheader("When to use load balancing")
        st.write(
            "- **A/B testing**: Compare quality/cost of two models with real traffic\n"
            "- **Gradual migration**: Start 90/10 on old model, shift slowly to new model\n"
            "- **Quota management**: Split load across two API keys to double your rate limit\n"
            "- **Zero-downtime maintenance**: Set weight=0 on target being updated, restore after"
        )
