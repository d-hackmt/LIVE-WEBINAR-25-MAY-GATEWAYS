import time
import streamlit as st
from modules.utils import (
    require_keys, make_client, extract_text, build_messages,
    show_diagram, get_model_used, get_virtual_key,
    get_primary_model, get_fallback_model, get_fallback_key
)
from modules.diagrams import RESILIENCE_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


def render():
    PRIMARY_MODEL = get_primary_model()
    FALLBACK_MODEL = get_fallback_model()
    vk = get_virtual_key()
    fvk = get_fallback_key()

    st.title("Timeout → Retry → Fallback")
    st.write(
        "The primary model is too slow and keeps timing out. "
        "Watch Portkey retry it, exhaust all attempts, "
        "then automatically route to the faster fallback model — "
        "with no changes to your app code."
    )

    with st.expander("How they chain together", expanded=True):
        show_diagram(RESILIENCE_DIAGRAM, height=520)
        st.caption(
            "Tight timeout → primary times out → Portkey retries → times out again → "
            "all retries exhausted → fallback model activated → response delivered."
        )

    st.divider()
    require_keys()

    st.subheader("Configure")

    col1, col2 = st.columns(2)
    with col1:
        timeout_ms = st.slider(
            "Timeout per attempt (ms)", 500, 8000, 2000, 250,
            help=(
                "How long to wait before declaring a timeout. "
                "The large 70B model usually needs 3–8s, so 2s will reliably time it out. "
                "The small 8B fallback usually responds in under 2s."
            )
        )
        retry_count = st.slider(
            "Retries on primary before fallback", 1, 3, 2,
            help="How many total attempts on the primary (1 original + N retries) before switching to fallback."
        )
    with col2:
        st.write("**Models**")
        st.write(f"Primary: `{PRIMARY_MODEL}`")
        st.caption("Large model — slower, high quality")
        st.write(f"Fallback: `{FALLBACK_MODEL}`")
        st.caption("Small model — faster, will respond within the timeout")
        if timeout_ms <= 3000:
            st.info(
                f"At {timeout_ms}ms the large model will almost certainly time out. "
                "The small fallback model usually responds in 1–2s."
            )

    portkey_config = {
        "strategy": {"mode": "fallback"},
        "request_timeout": timeout_ms,
        "retry": {
            "attempts": retry_count,
            "on_status_codes": [408, 429, 500, 502, 503],
        },
        "targets": [
            {"virtual_key": vk, "override_params": {"model": PRIMARY_MODEL}},
            {"virtual_key": fvk, "override_params": {"model": FALLBACK_MODEL}},
        ],
    }

    with st.expander("Portkey config for this scenario"):
        st.json(portkey_config)
        st.caption(
            "In production this single config handles everything automatically. "
            "Below we step through each attempt live so you can see exactly what Portkey does internally."
        )

    st.divider()

    question = st.selectbox("Question:", INTERESTING_QUESTIONS, key="resilience_q")
    custom_q = st.text_input("Or type your own:", key="resilience_custom", placeholder="Ask anything...")
    active_q = custom_q.strip() if custom_q.strip() else question

    if st.button("▶  Run — Watch It Fall Back", type="primary", width="stretch"):
        _run_demo(PRIMARY_MODEL, FALLBACK_MODEL, vk, fvk, timeout_ms, retry_count, active_q)

    if st.session_state.get("resilience_result"):
        _show_results()


def _run_demo(primary_model, fallback_model, vk, fvk, timeout_ms, retry_count, question):
    total_start = time.time()
    attempts = []
    final_text = None
    final_model = None
    used_fallback = False

    # Tight-timeout client for primary — forces timeout so fallback activates
    primary_client = make_client(config={
        "virtual_key": vk,
        "request_timeout": timeout_ms,
    })
    # Generous timeout for fallback — small model is fast, give it enough room
    fallback_client = make_client(config={
        "virtual_key": fvk,
        "request_timeout": max(timeout_ms * 6, 15000),
    })

    num_primary_attempts = retry_count + 1  # 1 original + N retries

    with st.status("Running resilience sequence...", expanded=True) as status:

        for i in range(num_primary_attempts):
            label = "Request" if i == 0 else f"Retry {i}"
            is_last = (i == num_primary_attempts - 1)

            st.write(f"**{label}** — calling primary `{primary_model}`...")
            start = time.time()

            try:
                response = primary_client.chat.completions.create(
                    model=primary_model,
                    messages=build_messages(question),
                    max_tokens=200,
                )
                elapsed = int((time.time() - start) * 1000)
                final_text = extract_text(response)
                final_model = get_model_used(response)
                st.write(f"✅ Primary responded in {elapsed}ms — no fallback needed.")
                attempts.append({
                    "label": label, "result": "success",
                    "model": primary_model, "ms": elapsed,
                })
                status.update(label="Primary responded — no fallback triggered", state="complete")
                break

            except Exception as e:
                elapsed = int((time.time() - start) * 1000)
                err_hint = str(e)[:80] if str(e) else "timeout"
                if not is_last:
                    st.write(
                        f"⏱ **Timed out** after {elapsed}ms "
                        f"(limit: {timeout_ms}ms). Retrying..."
                    )
                else:
                    st.write(
                        f"⏱ **Timed out** after {elapsed}ms. "
                        f"All {num_primary_attempts} primary attempts exhausted."
                    )
                attempts.append({
                    "label": label, "result": "timeout",
                    "model": primary_model, "ms": elapsed, "error": err_hint,
                })
                time.sleep(0.3)

        if final_text is None:
            # All primary attempts failed — activate fallback
            time.sleep(0.3)
            st.write(f"🔀 **Activating fallback** — switching to `{fallback_model}`...")
            start = time.time()
            try:
                response = fallback_client.chat.completions.create(
                    model=fallback_model,
                    messages=build_messages(question),
                    max_tokens=200,
                )
                elapsed = int((time.time() - start) * 1000)
                final_text = extract_text(response)
                final_model = get_model_used(response)
                used_fallback = True
                st.write(f"✅ **Fallback responded** in {elapsed}ms!")
                attempts.append({
                    "label": "Fallback", "result": "success",
                    "model": fallback_model, "ms": elapsed,
                })
                status.update(
                    label="Fallback delivered the response — user got an answer",
                    state="complete",
                )
            except Exception as e:
                st.error(f"Fallback also failed: {e}")
                status.update(label="All attempts failed", state="error")
                return

    st.session_state.resilience_result = {
        "attempts": attempts,
        "text": final_text,
        "model": final_model,
        "total_ms": int((time.time() - total_start) * 1000),
        "timeout_ms": timeout_ms,
        "used_fallback": used_fallback,
    }


def _show_results():
    r = st.session_state.resilience_result
    st.divider()
    st.subheader("What happened — step by step")

    for a in r["attempts"]:
        if a["result"] == "timeout":
            st.error(
                f"⏱ **{a['label']}** — `{a['model']}` "
                f"timed out after **{a['ms']}ms** (limit: {r['timeout_ms']}ms)"
            )
        elif a["label"] == "Fallback":
            st.success(
                f"✅ **{a['label']}** — `{a['model']}` responded in **{a['ms']}ms**"
            )
        else:
            st.success(
                f"✅ **{a['label']}** — `{a['model']}` responded in **{a['ms']}ms** "
                f"(no fallback needed)"
            )

    st.divider()

    timeout_count = sum(1 for a in r["attempts"] if a["result"] == "timeout")
    fallback_ms = next((a["ms"] for a in r["attempts"] if a["label"] == "Fallback"), None)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total time", f"{r['total_ms']}ms")
    col2.metric("Primary timeouts", timeout_count)
    col3.metric("Answered by", "Fallback" if r["used_fallback"] else "Primary")
    col4.metric("Timeout per attempt", f"{r['timeout_ms']}ms")

    if r["text"]:
        st.write(r["text"])
        st.caption(f"Model: {r['model']}")

    if r["used_fallback"]:
        st.success(
            f"Primary timed out **{timeout_count}x** in a row "
            f"(each attempt exceeded {r['timeout_ms']}ms). "
            "Portkey automatically switched to the fallback — "
            "user got an answer, zero errors shown to them."
        )
    else:
        st.info(
            "Primary model responded before the timeout. "
            "To see the fallback activate, reduce the timeout slider and run again."
        )

    st.divider()
    st.subheader("The Portkey config that does this in production")
    st.write(
        "You don't write this loop in production. "
        "One config object tells Portkey to do exactly what you just watched:"
    )
    st.code(
        f"""from portkey_ai import Portkey

portkey = Portkey(
    api_key="YOUR_PORTKEY_KEY",
    config={{
        "strategy": {{"mode": "fallback"}},
        "request_timeout": {r["timeout_ms"]},          # cut off slow requests
        "retry": {{
            "attempts": {timeout_count},                # retry primary N times
            "on_status_codes": [408, 429, 500, 502, 503],
        }},
        "targets": [
            {{"virtual_key": "your-primary-slug",  "override_params": {{"model": "llama-3.3-70b-versatile"}}}},
            {{"virtual_key": "your-fallback-slug", "override_params": {{"model": "llama-3.1-8b-instant"}}}},
        ],
    }}
)

# One call — Portkey handles timeout, retry, and fallback transparently
response = portkey.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{{"role": "user", "content": "..."}}]
)""",
        language="python",
    )
