import time
import streamlit as st
from portkey_ai import Portkey

# These defaults can be overridden at the module level by app.py after
# reading the user's session-state model preferences.
PRIMARY_MODEL = "llama-3.3-70b-versatile"
FALLBACK_MODEL = "llama-3.1-8b-instant"
DEFAULT_MAX_TOKENS = 250


def get_primary_model() -> str:
    return st.session_state.get("primary_model") or PRIMARY_MODEL


def get_fallback_model() -> str:
    return st.session_state.get("fallback_model") or FALLBACK_MODEL


def get_portkey_key() -> str:
    return st.session_state.get("portkey_api_key", "")


def get_virtual_key() -> str:
    return st.session_state.get("virtual_key", "")


def get_fallback_key() -> str:
    fk = st.session_state.get("fallback_virtual_key", "")
    return fk if fk else get_virtual_key()


def get_groq_key() -> str:
    return st.session_state.get("groq_api_key", "")


def keys_ready() -> bool:
    return bool(get_portkey_key() and get_virtual_key())


def require_keys():
    if not keys_ready():
        st.warning("Configure your Portkey API Key and Virtual Key Slug in the sidebar to run this demo.")
        st.stop()


def make_client(config: dict | None = None) -> Portkey:
    pk = get_portkey_key()
    vk = get_virtual_key()
    if config:
        return Portkey(api_key=pk, config=config)
    return Portkey(api_key=pk, virtual_key=vk)


def build_messages(question: str) -> list:
    return [{"role": "user", "content": question}]


def timed_call(client: Portkey, messages: list, model: str | None = None,
               extra_kwargs: dict | None = None) -> tuple:
    model = model or get_primary_model()
    kwargs = {
        "messages": messages,
        "model": model,  # already resolved above
        "max_tokens": DEFAULT_MAX_TOKENS,
    }
    if extra_kwargs:
        kwargs.update(extra_kwargs)
    start = time.time()
    response = client.chat.completions.create(**kwargs)
    elapsed_ms = int((time.time() - start) * 1000)
    return response, elapsed_ms


def extract_text(response) -> str:
    return response.choices[0].message.content or ""


def get_model_used(response) -> str:
    return getattr(response, "model", "unknown")


def show_diagram(diagram_text: str, height: int = 450):
    safe = diagram_text.strip()
    html = f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:transparent;overflow:hidden;">
  <div style="position:relative;height:{height}px;">
    <div style="position:absolute;top:6px;right:6px;z-index:99;display:flex;gap:4px;">
      <button onclick="z(1.25)">+</button>
      <button onclick="z(0.8)">-</button>
      <button onclick="r()">Reset</button>
    </div>
    <div id="wrap" style="height:100%;overflow:auto;padding:8px;box-sizing:border-box;">
      <div id="content"><pre class="mermaid">{safe}</pre></div>
    </div>
  </div>
  <style>
    button {{
      background:#3a3a3a;color:#ddd;border:1px solid #555;
      border-radius:3px;padding:3px 10px;cursor:pointer;font-size:13px;
    }}
    button:hover {{ background:#555; }}
  </style>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{startOnLoad:true, theme:'dark'}});
    let s = 1;
    const c = document.getElementById('content');
    window.z = (f) => {{
      s = Math.max(0.3, Math.min(s * f, 5));
      c.style.transform = 'scale(' + s + ')';
      c.style.transformOrigin = 'top left';
    }};
    window.r = () => {{ s = 1; c.style.transform = ''; }};
  </script>
</body>
</html>"""
    st.iframe(html, height=height + 10)


def question_selector(key: str, questions: list, label: str = "Pick a question or write your own") -> str:
    st.caption(label)
    col1, col2 = st.columns([3, 2])
    with col1:
        custom = st.text_input("Write your own question:", key=f"custom_{key}",
                               placeholder="Type anything you're curious about...")
    with col2:
        preset = st.selectbox("Or choose a preset:", questions, key=f"preset_{key}")
    return custom.strip() if custom.strip() else preset
