import streamlit as st

st.set_page_config(
    page_title="LLM Gateway Explorer",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ──────────────────────────────────────────────────
_DEFAULTS = {
    "portkey_api_key": "",
    "virtual_key": "",
    "fallback_virtual_key": "",
    "groq_api_key": "",
    "primary_model": "llama-3.3-70b-versatile",
    "fallback_model": "llama-3.1-8b-instant",
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("LLM Gateway Explorer")
    st.caption("Hands-on experiments with Portkey")
    st.divider()

    # ── API Keys ──────────────────────────────────────────────────────────
    with st.expander("API Keys", expanded=not bool(st.session_state.portkey_api_key)):
        st.session_state.portkey_api_key = st.text_input(
            "Portkey API Key",
            value=st.session_state.portkey_api_key,
            type="password",
            placeholder="pk-...",
            key="_pk_input",
            help="Get from portkey.ai → Settings → API Keys",
        )
        st.session_state.groq_api_key = st.text_input(
            "Groq API Key (Baseline demo only)",
            value=st.session_state.groq_api_key,
            type="password",
            placeholder="gsk_...",
            key="_groq_input",
            help="Get from console.groq.com — only needed for the Baseline experiment",
        )

    # ── Virtual Key Slugs ─────────────────────────────────────────────────
    with st.expander("Virtual Key Slugs", expanded=not bool(st.session_state.virtual_key)):
        st.caption(
            "Create virtual keys at portkey.ai → Virtual Keys. "
            "A slug is the short name you give your key, e.g. `my-groq`."
        )
        st.session_state.virtual_key = st.text_input(
            "Primary Virtual Key Slug",
            value=st.session_state.virtual_key,
            placeholder="e.g. my-groq-primary",
            key="_vk_input",
            help="The Portkey virtual key that connects to your primary Groq API key.",
        )
        st.session_state.fallback_virtual_key = st.text_input(
            "Fallback Virtual Key Slug",
            value=st.session_state.fallback_virtual_key,
            placeholder="e.g. my-groq-fallback (or same as primary)",
            key="_fvk_input",
            help="Used in fallback/load-balance demos. Leave blank to reuse the primary slug.",
        )
        if not st.session_state.fallback_virtual_key:
            st.caption("Fallback slug not set — using primary slug for fallback demos.")

    # ── Model Selection ───────────────────────────────────────────────────
    # Source: console.groq.com/docs/models — verified May 2026
    _GROQ_MODELS = [
        # — Production models —
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "groq/compound",
        "groq/compound-mini",
        # — Preview models —
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "qwen/qwen3-32b",
    ]

    def _model_idx(model_name: str) -> int:
        try:
            return _GROQ_MODELS.index(model_name)
        except ValueError:
            return 0

    with st.expander("Model Selection", expanded=False):
        st.caption("Choose which models power the primary and fallback slots in every demo.")
        st.session_state.primary_model = st.selectbox(
            "Primary Model",
            options=_GROQ_MODELS,
            index=_model_idx(st.session_state.primary_model),
            key="_pm_select",
            help="Used as the main model in all routing, retry, caching, and streaming demos.",
        )
        st.session_state.fallback_model = st.selectbox(
            "Fallback Model",
            options=_GROQ_MODELS,
            index=_model_idx(st.session_state.fallback_model),
            key="_fm_select",
            help="Used as the backup in fallback, load-balance, rate-limit, and production demos.",
        )
        if st.session_state.primary_model == st.session_state.fallback_model:
            st.caption("Primary and fallback are the same model — fallback will still activate on errors, but responses will be identical.")

    # ── Status indicator ──────────────────────────────────────────────────
    st.divider()
    if st.session_state.portkey_api_key and st.session_state.virtual_key:
        st.success("Ready to run demos", icon="✅")
    else:
        st.warning("Configure keys above to start", icon="⚠️")

    # ── Navigation ────────────────────────────────────────────────────────
    st.divider()

    _PAGES = [
        ("Home", "home"),
        ("Baseline (No Gateway)", "baseline"),
        ("Routing & Observability", "routing"),
        ("Metadata & Tracking", "metadata"),
        ("Automatic Retries", "retries"),
        ("Request Timeouts", "timeouts"),
        ("Fallback Routing", "fallbacks"),
        ("Retry + Timeout + Fallback", "resilience"),
        ("Load Balancing", "load_balancing"),
        ("Response Caching", "caching"),
        ("Rate Limiting", "rate_limiting"),
        ("Streaming", "streaming"),
        ("Production Config", "production"),
    ]
    _LABELS = [p[0] for p in _PAGES]
    _KEYS = [p[1] for p in _PAGES]

    selected_idx = st.radio(
        "Experiments",
        range(len(_LABELS)),
        format_func=lambda i: _LABELS[i],
        label_visibility="visible",
    )
    current_page = _KEYS[selected_idx]


# ── Route to selected demo ───────────────────────────────────────────────────
from modules.demos import (
    home,
    d01_baseline,
    d02_routing,
    d03_metadata,
    d04_retries,
    d05_timeouts,
    d06_fallbacks,
    d_resilience,
    d07_load_balancing,
    d08_caching,
    d09_rate_limiting,
    d10_streaming,
    d11_production,
)

_PAGE_MAP = {
    "home":            home.render,
    "baseline":        d01_baseline.render,
    "routing":         d02_routing.render,
    "metadata":        d03_metadata.render,
    "retries":         d04_retries.render,
    "timeouts":        d05_timeouts.render,
    "fallbacks":       d06_fallbacks.render,
    "resilience":      d_resilience.render,
    "load_balancing":  d07_load_balancing.render,
    "caching":         d08_caching.render,
    "rate_limiting":   d09_rate_limiting.render,
    "streaming":       d10_streaming.render,
    "production":      d11_production.render,
}

_PAGE_MAP[current_page]()
