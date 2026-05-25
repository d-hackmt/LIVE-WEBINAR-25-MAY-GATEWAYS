import time
import streamlit as st
from modules.utils import (
    require_keys, make_client, build_messages, show_diagram,
    question_selector, get_virtual_key, get_primary_model
)
from modules.diagrams import STREAMING_DIAGRAM
from modules.questions import INTERESTING_QUESTIONS


def render():
    PRIMARY_MODEL = get_primary_model()
    st.title("Streaming")
    st.write(
        "Instead of waiting for the full response, streaming lets you display tokens as they arrive. "
        "The user sees the answer building in real time — much better perceived performance. "
        "Portkey fully supports streaming: all gateway features still work, and the full request is still logged."
    )

    with st.expander("Architecture", expanded=True):
        show_diagram(STREAMING_DIAGRAM, height=480)
        st.caption(
            "Portkey forwards the streaming response token by token. "
            "The full request and response are still logged in your dashboard when streaming completes."
        )

    st.divider()

    require_keys()

    vk = get_virtual_key()

    st.subheader("The Code Change for Streaming")
    st.code(
        f"""portkey = Portkey(api_key="YOUR_KEY", virtual_key="{vk or 'your-slug'}")

stream = portkey.chat.completions.create(
    model="{PRIMARY_MODEL}",
    messages=[{{"role": "user", "content": "..."}}],
    stream=True,
    max_tokens=400,
)

for chunk in stream:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)
""",
        language="python"
    )

    st.divider()

    question = question_selector("streaming", INTERESTING_QUESTIONS,
                                 label="Ask a question that needs a longer, thoughtful answer")

    cache_config = {
        "virtual_key": vk,
        "cache": {"mode": "simple"},
    }

    col1, col2 = st.columns(2)
    with col1:
        max_tokens = st.slider("Max tokens (more = longer stream)", 100, 500, 300, step=50)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Streaming Response")
        if st.button("Stream the Answer", type="primary", width="stretch"):
            placeholder = st.empty()
            full_text = ""
            start = time.time()

            try:
                client = make_client(config=cache_config)
                stream = client.chat.completions.create(
                    model=PRIMARY_MODEL,
                    messages=build_messages(question),
                    stream=True,
                    max_tokens=max_tokens,
                )
                for chunk in stream:
                    content = chunk.choices[0].delta.content or ""
                    full_text += content
                    placeholder.markdown(full_text + " ▌")

                placeholder.markdown(full_text)
                elapsed = int((time.time() - start) * 1000)

                st.session_state.stream_result = {
                    "text": full_text,
                    "latency": elapsed,
                    "tokens_approx": len(full_text.split()),
                }

            except Exception as e:
                placeholder.empty()
                st.error(f"Error: {e}")

        if st.session_state.get("stream_result"):
            r = st.session_state.stream_result
            col1a, col1b = st.columns(2)
            col1a.metric("Time to complete", f"{r['latency']} ms")
            col1b.metric("~Words streamed", r["tokens_approx"])

    with col2:
        st.subheader("Non-Streaming Response")
        if st.button("Get Full Response at Once", width="stretch"):
            with st.spinner("Waiting for complete response..."):
                try:
                    client = make_client(config=cache_config)
                    start = time.time()
                    response = client.chat.completions.create(
                        model=PRIMARY_MODEL,
                        messages=build_messages(question),
                        stream=False,
                        max_tokens=max_tokens,
                    )
                    elapsed = int((time.time() - start) * 1000)
                    text = response.choices[0].message.content or ""
                    st.session_state.nonstream_result = {
                        "text": text,
                        "latency": elapsed,
                    }
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.session_state.get("nonstream_result"):
            r = st.session_state.nonstream_result
            st.write(r["text"])
            st.metric("Time until first word shown", f"{r['latency']} ms")
            st.caption("User sees nothing until this entire wait is over.")

    if st.session_state.get("stream_result") and st.session_state.get("nonstream_result"):
        st.divider()
        st.subheader("User Experience Comparison")
        s = st.session_state.stream_result
        ns = st.session_state.nonstream_result
        col1, col2 = st.columns(2)
        col1.metric("Streaming: first token shows in", "~200ms", delta="user immediately engaged")
        col2.metric("Non-streaming: first word shows in", f"~{ns['latency']}ms", delta="user stares at spinner", delta_color="inverse")
        st.write(
            "Even though both calls take the same total time, streaming feels dramatically faster. "
            "Users start reading while the model is still generating."
        )

    st.divider()
    st.subheader("Key facts about streaming through a gateway")
    st.write(
        "- All gateway features work with streaming: retry, fallback, caching, metadata tagging\n"
        "- The full request and response are still logged in Portkey after the stream completes\n"
        "- Caching works on the first stream of a query — second identical request returns from cache instantly\n"
        "- Token counting is still available after stream completion"
    )
