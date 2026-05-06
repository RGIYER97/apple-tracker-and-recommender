import os
import re
import json
import datetime
from pathlib import Path
from collections import Counter

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE       = Path(__file__).parent / "recommendations_cache.json"
SMART_CACHE_FILE = Path(__file__).parent / "smart_recommendations_cache.json"


def _load_rec_cache() -> tuple[list[dict], str | None, int | None]:
    try:
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data, None, None
            return data.get("recs", []), data.get("generated_at"), data.get("entry_count")
    except Exception:
        pass
    return [], None, None


def _save_rec_cache(recs: list[dict], entry_count: int = 0) -> None:
    try:
        payload = {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "entry_count": entry_count,
            "recs": recs,
        }
        CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_smart_cache() -> tuple[list[dict], str | None, int | None]:
    try:
        if SMART_CACHE_FILE.exists():
            data = json.loads(SMART_CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data, None, None
            return data.get("recs", []), data.get("generated_at"), data.get("entry_count")
    except Exception:
        pass
    return [], None, None


def _save_smart_cache(recs: list[dict], entry_count: int = 0) -> None:
    try:
        payload = {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "entry_count": entry_count,
            "recs": recs,
        }
        SMART_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Apple Tracker",
    page_icon="🍎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design tokens ──────────────────────────────────────────────────────────────
# Palette: warm off-white main · deep forest-green sidebar · red-apple accent
BG_APP      = "#FAF7F2"   # warm off-white
BG_CARD     = "#FFFFFF"   # pure white cards
BG_PLOT     = "#FFFFFF"   # chart canvas
BG_PAPER    = "#FAF7F2"   # chart surround matches page
BG_SIDEBAR  = "#1A3B2A"   # deep forest green
ACCENT      = "#C0392B"   # red apple
ACCENT_DARK = "#922B21"   # darker red for hover/pressed
TEXT_MAIN   = "#1A1208"   # near-black
TEXT_MUTED  = "#4A3728"   # warm dark brown — readable at small sizes
GRID        = "#D8CEBC"   # slightly darker warm grid — visible in charts

st.markdown(
    f"""
    <style>

    /* ═══════════════════════════════════════════════════════════
       APP SHELL
    ═══════════════════════════════════════════════════════════ */
    .stApp {{ background: {BG_APP} !important; }}
    [data-testid="stHeader"] {{ background: {BG_APP} !important; border-bottom: 1px solid {GRID}; }}
    .block-container {{ padding-top: 1.4rem; max-width: 1200px; }}

    /* ═══════════════════════════════════════════════════════════
       GLOBAL TEXT
    ═══════════════════════════════════════════════════════════ */
    .stApp, .stApp p, .stApp span, .stApp div, .stApp label,
    .stApp li, .stApp td, .stApp th, .stApp small,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] * {{
        color: {TEXT_MAIN};
    }}
    h1 {{ color: {TEXT_MAIN} !important; font-weight: 700; letter-spacing: -0.5px; }}
    h2, h3 {{ color: {TEXT_MAIN} !important; font-weight: 600; }}
    p, li {{ color: {TEXT_MAIN} !important; }}
    a {{ color: {ACCENT_DARK} !important; }}

    [data-testid="stCaptionContainer"] p,
    [data-testid="stCaptionContainer"] span,
    .stCaption, small {{
        color: {TEXT_MUTED} !important;
        font-size: 0.875rem !important;
    }}

    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stMarkdownContainer"] span {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       SIDEBAR
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stSidebar"] {{
        background: {BG_SIDEBAR} !important;
    }}
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] li,
    [data-testid="stSidebar"] small {{
        color: #D4EDD8 !important;
    }}
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{ color: #A8D5AA !important; font-size: 1rem !important; }}
    [data-testid="stSidebar"] hr {{ border-color: #4A7A5A !important; border-width: 1px !important; opacity: 1 !important; }}
    [data-testid="stSidebar"] a {{ color: #A8D5AA !important; }}
    [data-testid="stSidebar"] strong {{ color: #E8F5E9 !important; }}

    /* Captions inside sidebar — global rule sets dark brown, override to light */
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] span {{
        color: #B8D0BB !important;
        font-size: 0.82rem !important;
    }}

    /* Widget labels inside sidebar — global rule sets near-black, override to light */
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] span,
    [data-testid="stSidebar"] label {{ color: #D4EDD8 !important; }}

    /* Inline code in sidebar (e.g. `.env.example`) — override dark browser default */
    [data-testid="stSidebar"] code {{
        color: #D4EDD8 !important;
        background: rgba(255,255,255,0.15) !important;
        border-radius: 3px !important;
        padding: 1px 5px !important;
    }}

    /* Expander inside sidebar — use <details> selector + test-id fallback.
       The `*` child beats per-element global rules on specificity (0,2,0 > 0,1,1). */
    [data-testid="stSidebar"] details,
    [data-testid="stSidebar"] [data-testid="stExpander"] {{
        background: #243F2F !important;
        border: 1px solid #4A7A5A !important;
        border-radius: 8px !important;
    }}
    [data-testid="stSidebar"] details *,
    [data-testid="stSidebar"] [data-testid="stExpander"] * {{
        color: #D4EDD8 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpanderDetails"],
    [data-testid="stSidebar"] .streamlit-expanderContent {{
        background: #243F2F !important;
    }}
    [data-testid="stSidebar"] details a,
    [data-testid="stSidebar"] [data-testid="stExpander"] a {{ color: #A8D5AA !important; }}
    [data-testid="stSidebar"] details code,
    [data-testid="stSidebar"] [data-testid="stExpander"] code {{
        background: rgba(255,255,255,0.12) !important;
    }}

    /* Sidebar action button (.stButton scopes to st.button() only, not expander toggles).
       Target the span directly to beat the broad [stSidebar] span rule (specificity 0,1,2 > 0,1,1). */
    [data-testid="stSidebar"] .stButton button {{
        background: #E8F5E9 !important;
        border: 2px solid #2E5C3A !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        padding: 0.5rem 1rem !important;
        width: 100% !important;
    }}
    [data-testid="stSidebar"] .stButton button:hover {{
        background: #ffffff !important;
        border-color: #1A3B2A !important;
    }}
    [data-testid="stSidebar"] .stButton button span,
    [data-testid="stSidebar"] .stButton button p,
    [data-testid="stSidebar"] .stButton button * {{
        color: #1A3B2A !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       WIDGET LABELS
    ═══════════════════════════════════════════════════════════ */
    label, [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] span {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       TEXT INPUTS & TEXT AREAS
    ═══════════════════════════════════════════════════════════ */
    input, textarea {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
        border-color: #C8A878 !important;
    }}
    input::placeholder, textarea::placeholder {{
        color: {TEXT_MUTED} !important;
    }}
    [data-baseweb="input"],
    [data-baseweb="input"] > div,
    [data-baseweb="textarea"],
    [data-baseweb="textarea"] > div {{
        background: {BG_CARD} !important;
        border-color: #C8A878 !important;
    }}
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       SELECT / DROPDOWN
    ═══════════════════════════════════════════════════════════ */
    [data-baseweb="select"] > div {{
        background: {BG_CARD} !important;
        border-color: #C8A878 !important;
    }}
    [data-baseweb="select"] span,
    [data-baseweb="select"] div {{
        color: {TEXT_MAIN} !important;
    }}
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [data-baseweb="menu"] ul,
    [role="listbox"],
    [role="option"] {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
    }}
    [role="option"]:hover,
    [data-baseweb="menu"] li:hover {{
        background: {GRID} !important;
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       MULTISELECT
    ═══════════════════════════════════════════════════════════ */
    [data-baseweb="tag"] {{
        background: #FFF0EE !important;
        border: 1px solid #E8A09A !important;
    }}
    [data-baseweb="tag"] span {{
        color: #6B1208 !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       SLIDER
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stSlider"] p,
    [data-testid="stSlider"] span,
    [data-testid="stSlider"] div {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       CHECKBOX & RADIO
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stCheckbox"] label,
    [data-testid="stCheckbox"] p,
    [data-testid="stRadio"] label,
    [data-testid="stRadio"] p {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       DATE INPUT
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stDateInput"] input {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
        border-color: #C8A878 !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       BUTTONS
    ═══════════════════════════════════════════════════════════ */
    .stButton > button {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
        border: 1px solid #C8A878 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }}
    .stButton > button:hover {{
        background: {GRID} !important;
        border-color: {ACCENT} !important;
    }}
    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"] {{
        background: {ACCENT} !important;
        color: #fff !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.45rem 1.2rem !important;
    }}
    .stButton > button[kind="primary"]:hover,
    [data-testid="baseButton-primary"]:hover {{
        background: {ACCENT_DARK} !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18) !important;
    }}
    .stButton > button[kind="secondary"],
    [data-testid="baseButton-secondary"] {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
        border: 1px solid #C8A878 !important;
    }}
    [data-testid="stFormSubmitButton"] > button {{
        background: {ACCENT} !important;
        color: #fff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.45rem 1.4rem !important;
    }}
    [data-testid="stFormSubmitButton"] > button:hover {{
        background: {ACCENT_DARK} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       FORMS
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stForm"] {{
        background: {BG_CARD} !important;
        border: 1px solid {GRID} !important;
        border-radius: 12px !important;
        padding: 16px !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       EXPANDERS
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stExpander"] {{
        background: {BG_CARD} !important;
        border: 1px solid {GRID} !important;
        border-radius: 8px !important;
    }}
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span,
    .streamlit-expanderHeader,
    .streamlit-expanderHeader p {{
        color: {TEXT_MAIN} !important;
        background: {BG_CARD} !important;
    }}
    .streamlit-expanderContent,
    [data-testid="stExpanderDetails"] {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
    }}
    [data-testid="stExpanderDetails"] p,
    [data-testid="stExpanderDetails"] li,
    [data-testid="stExpanderDetails"] a {{
        color: {TEXT_MAIN} !important;
    }}
    [data-testid="stExpanderDetails"] a {{
        color: {ACCENT_DARK} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       ALERT BOXES
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stAlert"] {{
        border-radius: 8px !important;
    }}
    [data-testid="stAlert"] p,
    [data-testid="stAlert"] span,
    [data-testid="stAlert"] div {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       METRIC CARDS
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stMetric"] {{
        background: {BG_CARD} !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        border: 1px solid {GRID} !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
    }}
    [data-testid="stMetricValue"] {{ color: {TEXT_MAIN} !important; font-weight: 700 !important; }}
    [data-testid="stMetricLabel"] {{ color: {TEXT_MAIN} !important; font-size: 0.88rem !important; font-weight: 500 !important; }}
    [data-testid="stMetricDelta"] {{ font-size: 0.85rem !important; color: {TEXT_MUTED} !important; }}

    /* ═══════════════════════════════════════════════════════════
       TABS
    ═══════════════════════════════════════════════════════════ */
    .stTabs [data-baseweb="tab-list"] {{
        background: {GRID} !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 2px !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {TEXT_MAIN} !important;
        font-weight: 500 !important;
        border-radius: 8px !important;
        padding: 6px 18px !important;
        background: transparent !important;
        opacity: 0.6;
    }}
    .stTabs [aria-selected="true"] {{
        background: {BG_CARD} !important;
        color: {TEXT_MAIN} !important;
        font-weight: 600 !important;
        opacity: 1 !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.10) !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       DATAFRAME / TABLE
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stDataFrame"] {{ border-radius: 10px !important; overflow: hidden !important; }}
    [data-testid="stDataFrame"] th,
    [data-testid="stDataFrame"] td {{
        color: {TEXT_MAIN} !important;
        background: {BG_CARD} !important;
        font-size: 0.92rem !important;
    }}
    [data-testid="stDataFrame"] thead th {{
        background: {GRID} !important;
        color: {TEXT_MAIN} !important;
        font-weight: 700 !important;
        font-size: 0.92rem !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       PROGRESS BAR
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stProgress"] > div {{
        background: {GRID} !important;
        border-radius: 4px !important;
    }}
    [data-testid="stProgress"] > div > div {{
        background: {ACCENT} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       SPINNER
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stSpinner"] p,
    [data-testid="stSpinner"] span {{
        color: {TEXT_MAIN} !important;
    }}

    /* ═══════════════════════════════════════════════════════════
       DIVIDERS
    ═══════════════════════════════════════════════════════════ */
    hr {{ border-color: {GRID} !important; }}

    /* ═══════════════════════════════════════════════════════════
       CUSTOM COMPONENTS
    ═══════════════════════════════════════════════════════════ */
    .apple-card {{
        background: {BG_CARD};
        border-radius: 14px;
        padding: 20px 22px;
        margin-bottom: 12px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.07);
        border-left: 5px solid {ACCENT};
    }}
    .apple-card h3 {{ margin: 0 0 4px 0; color: {TEXT_MAIN} !important; font-size: 1.05rem !important; }}
    .apple-card small {{ color: {TEXT_MUTED} !important; font-size: 0.85rem !important; }}

    .tag {{
        background: #FFF0EE;
        border: 1px solid #D4786E;
        color: #6B1208 !important;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.84em;
        font-weight: 500;
        margin: 3px 2px;
        display: inline-block;
    }}

    </style>
    """,
    unsafe_allow_html=True,
)

# ── Flavor axes (Taste Fingerprint) ───────────────────────────────────────────
FLAVOR_AXES: dict[str, list[str]] = {
    "Sweet":   ["sweet", "sugar", "honey", "caramel", "syrup", "mild", "honeyed", "sugary"],
    "Tart":    ["tart", "tangy", "acidic", "sharp", "sour", "zesty", "bright", "acidity"],
    "Crisp":   ["crisp", "crunchy", "firm", "snappy", "hard", "dense", "crunch", "snap"],
    "Juicy":   ["juicy", "juice", "moist", "wet", "succulent", "tender", "watery"],
    "Floral":  ["floral", "flower", "rose", "blossom", "fragrant", "perfume", "aromatic", "anise"],
    "Earthy":  ["earthy", "earth", "herbal", "grassy", "hay", "rustic", "mineral", "russet"],
    "Spiced":  ["spice", "spiced", "cinnamon", "nutmeg", "clove", "warm", "complex", "vanilla"],
    "Bitter":  ["bitter", "astringent", "tannic", "dry", "puckering", "tannin"],
}

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "must", "and", "but", "or", "for", "in", "on", "at", "to",
    "from", "by", "of", "with", "as", "it", "its", "this", "that", "very",
    "quite", "really", "super", "much", "more", "less", "not", "no", "good",
    "great", "like", "similar", "than", "some", "bit", "hint", "hints",
    "slightly", "light", "heavy", "texture", "textured", "flavor", "taste",
    "tastes", "tasting", "notes", "apple", "apples", "variety", "varieties",
    "nice", "end", "big", "when", "well", "also", "real", "nice",
}

PLOT_LAYOUT = dict(
    plot_bgcolor=BG_PLOT,
    paper_bgcolor=BG_PAPER,
    font=dict(color=TEXT_MAIN, family="Segoe UI, Arial, sans-serif", size=13),
    title_font=dict(color=TEXT_MAIN, size=17, family="Segoe UI, Arial, sans-serif"),
    legend=dict(font=dict(color=TEXT_MAIN, size=12)),
    title_x=0.0,
    margin=dict(l=0, r=0, t=40, b=0),
)


def apply_axes(fig, x_grid=True, y_grid=True):
    _tick = dict(color=TEXT_MAIN, size=12)
    _label = dict(color=TEXT_MAIN, size=13)
    if x_grid:
        fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, tickfont=_tick, title_font=_label)
    else:
        fig.update_xaxes(showgrid=False, zerolinecolor=GRID, tickfont=_tick, title_font=_label)
    if y_grid:
        fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, tickfont=_tick, title_font=_label)
    else:
        fig.update_yaxes(showgrid=False, zerolinecolor=GRID, tickfont=_tick, title_font=_label)
    return fig


# ── Helpers ────────────────────────────────────────────────────────────────────

def _flavor_scores(notes: str) -> dict[str, float]:
    text = notes.lower()
    return {
        axis: min(sum(1 for kw in keywords if kw in text) * 3.0, 10.0)
        for axis, keywords in FLAVOR_AXES.items()
    }


def _user_fingerprint(df: pd.DataFrame) -> dict[str, float]:
    totals = {ax: 0.0 for ax in FLAVOR_AXES}
    weight_sum = 0.0
    for _, row in df.iterrows():
        notes = str(row.get("Tasting Notes") or "")
        w = float(row["Score"]) if pd.notna(row.get("Score")) else 5.0
        for ax, val in _flavor_scores(notes).items():
            totals[ax] += val * w
        weight_sum += w
    if weight_sum == 0:
        return {ax: 0.0 for ax in FLAVOR_AXES}
    return {ax: totals[ax] / weight_sum for ax in FLAVOR_AXES}


def _make_radar(series: dict[str, dict[str, float]], title: str = "") -> go.Figure:
    axes = list(FLAVOR_AXES.keys())
    palette = [ACCENT, "#2E8B40", "#4A7FD9", "#9B59B6", "#E67E22"]
    fig = go.Figure()
    for i, (label, scores) in enumerate(series.items()):
        vals = [scores.get(ax, 0) for ax in axes]
        color = palette[i % len(palette)]
        fig.add_trace(go.Scatterpolar(
            r=vals + [vals[0]],
            theta=axes + [axes[0]],
            fill="toself",
            name=label,
            line=dict(color=color, width=2),
            fillcolor=color,
            opacity=0.22,
        ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 10], tickfont=dict(color=TEXT_MAIN, size=11), gridcolor=GRID),
            angularaxis=dict(tickfont=dict(color=TEXT_MAIN, size=13)),
            bgcolor=BG_PLOT,
        ),
        title=dict(text=title, font=dict(color=TEXT_MAIN, size=17)),
        paper_bgcolor=BG_PAPER,
        font=dict(color=TEXT_MAIN, size=13),
        showlegend=True,
        legend=dict(font=dict(color=TEXT_MAIN, size=12)),
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def _parse_image_url(formula: str) -> str:
    m = re.match(r'=IMAGE\("([^"]+)"', formula.strip())
    return m.group(1) if m else ""


def flavor_keywords(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    notes = " ".join(df["Tasting Notes"].fillna("").tolist()).lower()
    tokens = re.findall(r"[a-z]+", notes)
    counts = Counter(t for t in tokens if t not in STOP_WORDS and len(t) > 2)
    rows = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return pd.DataFrame(rows, columns=["Keyword", "Count"])


def score_style(val):
    if pd.isna(val):
        return f"color: {TEXT_MUTED}"
    if val >= 9:
        return "color: #1B6B30; font-weight: 700"
    if val >= 7:
        return f"color: {ACCENT_DARK}; font-weight: 700"
    return "color: #B71C1C; font-weight: 700"


def render_rec_card(rec: dict, card_idx: int, df: pd.DataFrame, is_pinned: bool = False):
    from recommendations import _local_confidence
    model_conf = rec.get("confidence", "")
    local_conf = _local_confidence(rec, df)

    ar_real = rec.get("ar_score")
    ar_est  = rec.get("ar_score_estimate", "")
    conf_parts: list[str] = []
    if ar_real:
        conf_parts.append(f"AR {ar_real}/100")
    elif ar_est:
        conf_parts.append(f"AR ~{ar_est}/100")
    if model_conf:
        conf_parts.append(f"Model: {model_conf}/10")
    if local_conf is not None:
        conf_parts.append(f"Your match: {local_conf}/10")
    conf_str = "  ·  " + "  ·  ".join(conf_parts) if conf_parts else ""

    apple_type = rec.get("type", "")
    season     = rec.get("season", "")
    meta_parts = [p for p in [rec.get("origin", ""), apple_type, season] if p]

    st.markdown(
        f"""<div class="apple-card">
            <h3>{rec['name']}</h3>
            <small>{"  ·  ".join(meta_parts)}{conf_str}</small>
        </div>""",
        unsafe_allow_html=True,
    )

    pic = rec.get("picture_url", "")
    if pic:
        try:
            st.image(pic, width=300)
        except Exception:
            pass

    st.markdown(f"**Flavor Profile:** {rec.get('flavor_profile', '')}")
    st.markdown(f"**Why you'll love it:** _{rec.get('why_youll_love_it', '')}_")

    notes = rec.get("tasting_notes", [])
    if notes:
        st.markdown("".join(f'<span class="tag">{n}</span>' for n in notes), unsafe_allow_html=True)

    if price := rec.get("price_range", ""):
        st.markdown(f"💰 **{price}**")

    if pairs := rec.get("pairs_with", []):
        st.markdown("🥧 **Pairs with:** " + ", ".join(pairs))

    if stores := rec.get("stores", []):
        st.markdown("📍 **Where to find it:**")
        for store in stores:
            loc  = store.get("location", "")
            note = store.get("notes", "")
            line = f"**{store['name']}** — {loc}"
            if note:
                line += f" · _{note}_"
            st.markdown(f"- {line}")

    if link := rec.get("link", ""):
        st.markdown(f"[Learn more ↗]({link})")

    if is_pinned:
        st.markdown("✅ **Saved to your Apple Wishlist**")
        if st.button("☑️ Mark as Tried", key=f"tried_{card_idx}", help="Pre-fill the Add Entry form"):
            st.session_state["prefill_from_rec"] = rec
            st.toast(f"Switch to Add Entry to log '{rec.get('name', '')}'!")
            st.rerun()
    else:
        if st.button("📌 Save to Wishlist", key=f"pin_{card_idx}", type="secondary"):
            try:
                from sheets import pin_to_wishlist
                pin_to_wishlist(rec)
                st.session_state["pinned_names"].add(rec.get("name", ""))
                st.toast(f"'{rec.get('name', '')}' saved to your wishlist!")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save to sheet: {exc}")

    st.markdown("---")


# ── Data loading ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner="Loading apple data from Google Sheets…")
def load_data() -> pd.DataFrame:
    from sheets import load_apple_data
    return load_apple_data()


@st.cache_data(ttl=60, show_spinner="Loading wishlist…")
def load_wishlist_data() -> list[dict]:
    from sheets import load_wishlist
    return load_wishlist()


try:
    df = load_data()
except EnvironmentError:
    st.error("**Google Sheets credentials not configured.**")
    st.info(
        "Set `GOOGLE_SERVICE_ACCOUNT_JSON` in your `.env` file to the path of your "
        "service-account JSON key. See `.env.example` for details."
    )
    st.stop()
except Exception as exc:
    st.error(f"Failed to load sheet data: {exc}")
    st.stop()


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🍎 Apple Tracker & Discovery Engine")
st.caption("Tracking preferences · Enriching data · Finding new favourites")
st.divider()

# ── Top-level metrics ──────────────────────────────────────────────────────────
_scored = df.dropna(subset=["Score"])
if not _scored.empty:
    best_row   = _scored.loc[_scored["Score"].idxmax()]
    _has_store = "From Where" in df.columns
    _mcols     = st.columns(4 if _has_store else 3)
    _mcols[0].metric("🍎 Varieties Tried", len(df))
    _mcols[1].metric("⭐ Average Score",    f"{_scored['Score'].mean():.1f} / 10")
    _mcols[2].metric("🏆 Top Apple",        best_row["Apple Variety"], f"{best_row['Score']}/10")
    if _has_store:
        top_store = _scored.groupby("From Where")["Score"].mean().idxmax()
        _mcols[3].metric("🏪 Best Source (avg)", top_store)
    st.divider()

if "recommendations" not in st.session_state:
    _init_recs, _init_rec_at, _init_rec_count = _load_rec_cache()
    st.session_state["recommendations"] = _init_recs
    st.session_state["rec_generated_at"] = _init_rec_at
    st.session_state["rec_entry_count"] = _init_rec_count

if "smart_recs" not in st.session_state:
    _init_smart, _init_smart_at, _init_smart_count = _load_smart_cache()
    st.session_state["smart_recs"] = _init_smart
    st.session_state["smart_generated_at"] = _init_smart_at
    st.session_state["smart_entry_count"] = _init_smart_count


# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_dash, tab_collection, tab_add, tab_recs, tab_wishlist, tab_planner = st.tabs(
    ["📊 Dashboard", "🍎 My Collection", "➕ Add Entry", "✨ Recommendations", "📋 Wishlist", "🛒 Store Planner"]
)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
with tab_dash:
    scored_df = df.dropna(subset=["Score"])

    st.subheader("Score Distribution")
    fig_hist = px.histogram(
        scored_df,
        x="Score",
        nbins=14,
        color_discrete_sequence=[ACCENT],
        labels={"Score": "Score (out of 10)", "count": "# Varieties"},
        title="How I've rated my apples",
    )
    fig_hist.update_layout(bargap=0.12, **PLOT_LAYOUT)
    apply_axes(fig_hist, x_grid=False, y_grid=True)
    st.plotly_chart(fig_hist, use_container_width=True)

    col_left, col_right = st.columns(2)

    with col_left:
        if "From Where" in scored_df.columns:
            st.subheader("Average Score by Store / Source")
            store_avg = (
                scored_df.groupby("From Where")["Score"]
                .agg(["mean", "count"])
                .rename(columns={"mean": "Avg Score", "count": "Varieties Tried"})
                .sort_values("Avg Score", ascending=True)
                .reset_index()
            )
            fig_store = px.bar(
                store_avg,
                x="Avg Score",
                y="From Where",
                orientation="h",
                color="Avg Score",
                color_continuous_scale=[[0, "#D9534F"], [0.5, "#F0AD4E"], [1, "#2E8B40"]],
                range_color=[4, 10],
                hover_data={"Varieties Tried": True},
                title="Which shops score best?",
            )
            fig_store.update_layout(coloraxis_showscale=False, **PLOT_LAYOUT)
            apply_axes(fig_store, x_grid=True, y_grid=False)
            st.plotly_chart(fig_store, use_container_width=True)

    with col_right:
        st.subheader("Top Flavor Keywords")
        kw_df = flavor_keywords(df, top_n=18)
        fig_kw = px.bar(
            kw_df,
            x="Count",
            y="Keyword",
            orientation="h",
            color="Count",
            color_continuous_scale=[[0, "#FAB8A8"], [1, ACCENT_DARK]],
            title="Most common tasting-note words",
        )
        fig_kw.update_layout(
            coloraxis_showscale=False,
            yaxis={"categoryorder": "total ascending"},
            **PLOT_LAYOUT,
        )
        apply_axes(fig_kw, x_grid=True, y_grid=False)
        st.plotly_chart(fig_kw, use_container_width=True)

    if "Date" in df.columns:
        df_time = df.dropna(subset=["Date", "Score"]).sort_values("Date")
        if not df_time.empty:
            st.subheader("Score Over Time")
            _hov = {k: True for k in ["Tasting Notes", "From Where"] if k in df_time.columns}
            fig_time = px.scatter(
                df_time,
                x="Date",
                y="Score",
                hover_name="Apple Variety",
                hover_data=_hov,
                color="Score",
                color_continuous_scale=[[0, "#D9534F"], [0.5, "#F0AD4E"], [1, "#2E8B40"]],
                range_color=[3, 10],
                size_max=14,
                title="My apple journey",
            )
            try:
                fig_time.add_traces(
                    px.scatter(df_time, x="Date", y="Score", trendline="lowess").data[1:]
                )
                fig_time.data[-1].update(line=dict(color=ACCENT, width=2.5))
            except Exception:
                pass
            fig_time.update_layout(coloraxis_showscale=True, **PLOT_LAYOUT)
            apply_axes(fig_time)
            st.plotly_chart(fig_time, use_container_width=True)

    if "AR Score" in df.columns:
        _ar_df = df.copy()
        _ar_df["_ar"] = pd.to_numeric(_ar_df["AR Score"], errors="coerce")
        _ar_df = _ar_df.dropna(subset=["Score", "_ar"])
        if not _ar_df.empty:
            st.divider()
            st.subheader("You vs. AppleRankings.com")
            st.caption(
                "Each dot is a variety you've enriched with AR data. "
                "Top-right = you both love it · Top-left = your hidden gem · "
                "Bottom-right = overhyped by AR · dashed lines at your score 7 and AR 70."
            )

            def _quad(row):
                if row["Score"] >= 7 and row["_ar"] >= 70:
                    return "Both love it"
                if row["Score"] >= 7:
                    return "Your hidden gem"
                if row["_ar"] >= 70:
                    return "Overhyped"
                return "Both pass"

            _ar_df["Quadrant"] = _ar_df.apply(_quad, axis=1)
            _qcolor = {
                "Both love it":    "#2E8B40",
                "Your hidden gem": "#4A7FD9",
                "Overhyped":       ACCENT,
                "Both pass":       TEXT_MUTED,
            }
            _hov_ar = {k: True for k in ["Tasting Notes", "From Where"] if k in _ar_df.columns}
            fig_ar = px.scatter(
                _ar_df,
                x="_ar",
                y="Score",
                hover_name="Apple Variety",
                hover_data=_hov_ar,
                color="Quadrant",
                color_discrete_map=_qcolor,
                labels={"_ar": "AppleRankings Score (1–100)", "Score": "Your Score (1–10)"},
                title="Agreement with AppleRankings.com",
            )
            fig_ar.add_hline(y=7,  line_dash="dot", line_color=GRID, line_width=1.5)
            fig_ar.add_vline(x=70, line_dash="dot", line_color=GRID, line_width=1.5)
            fig_ar.update_layout(**PLOT_LAYOUT)
            apply_axes(fig_ar)
            st.plotly_chart(fig_ar, use_container_width=True)

            if len(_ar_df) >= 3:
                _corr = _ar_df[["Score", "_ar"]].corr().iloc[0, 1]
                st.caption(
                    f"Pearson correlation with AR: **{_corr:.2f}** "
                    f"across {len(_ar_df)} enriched varieties"
                )

    st.divider()
    st.subheader("Your Taste Fingerprint")
    st.caption(
        "Weighted average of all your flavor axes, scaled by score — "
        "higher-rated apples pull the shape more strongly."
    )
    fingerprint = _user_fingerprint(df)
    _, col_fp, _ = st.columns([1, 2, 1])
    with col_fp:
        st.plotly_chart(_make_radar({"My Palate": fingerprint}), use_container_width=True)

    if "Country" in df.columns:
        map_df = (
            df[df["Country"].str.strip() != ""]
            .groupby("Country")["Score"]
            .agg(avg_score="mean", count="count")
            .reset_index()
        )
        if not map_df.empty:
            st.divider()
            st.subheader("Origin Map")
            st.caption("Countries you've tried, shaded by average score.")
            fig_map = px.choropleth(
                map_df,
                locations="Country",
                locationmode="country names",
                color="avg_score",
                hover_name="Country",
                hover_data={"count": True, "avg_score": ":.1f"},
                color_continuous_scale=[[0, "#D9534F"], [0.5, "#F0AD4E"], [1, "#2E8B40"]],
                range_color=[4, 10],
                labels={"avg_score": "Avg Score", "count": "# Varieties"},
                title="Average score by country of origin",
            )
            fig_map.update_layout(
                geo=dict(showframe=False, showcoastlines=True, bgcolor=BG_PAPER),
                coloraxis_colorbar=dict(title="Avg Score"),
                **PLOT_LAYOUT,
            )
            st.plotly_chart(fig_map, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — MY COLLECTION
# ─────────────────────────────────────────────────────────────────────────────
with tab_collection:
    st.subheader("All Apple Varieties")

    col_sort, col_order = st.columns([2, 1])
    with col_sort:
        _sort_opts = ["Score"] + (["Date"] if "Date" in df.columns else []) + ["Apple Variety"]
        sort_col = st.selectbox("Sort by", _sort_opts, index=0)
    with col_order:
        sort_asc = st.checkbox("Ascending", value=False)

    display_df = df.sort_values(sort_col, ascending=sort_asc, na_position="last")

    def _fmt_source(v: object) -> str:
        s = str(v).strip() if v and str(v).strip() else ""
        return {"web": "🌐 web", "LLM": "🤖 LLM"}.get(s, s)

    fmt: dict = {
        "Score": lambda v: f"{v:.1f}" if pd.notna(v) else "",
        "Date":  lambda d: d.strftime("%b %Y") if pd.notna(d) else "",
    }
    if "Notes Source" in display_df.columns:
        fmt["Notes Source"] = _fmt_source

    styled = (
        display_df.style
        .map(score_style, subset=["Score"])
        .format(fmt)
    )
    st.dataframe(styled, use_container_width=True, height=540)

    st.divider()
    st.subheader("Enrich with Links, Prices & Images")
    st.caption(
        "Fetches an image, applerankings.com score & notes, and professional tasting notes "
        "for each variety, then writes them back to your Google Sheet."
    )

    if st.button("🔍 Enrich All Varieties", type="primary"):
        if not os.environ.get("TAVILY_API_KEY"):
            st.error("TAVILY_API_KEY is not set. Add it to your .env file.")
        else:
            from enrichment import enrich_dataframe
            from sheets import update_enrichment

            pbar   = st.progress(0.0)
            status = st.empty()

            def on_progress(frac: float, name: str):
                pbar.progress(frac)
                status.text(f"Searching: {name}")

            enriched = enrich_dataframe(df, progress_cb=on_progress)
            pbar.progress(1.0)
            status.text("Writing back to Google Sheet…")
            update_enrichment(enriched)
            status.empty()
            pbar.empty()
            st.success("Done! Reload the page to see enriched columns.")
            st.cache_data.clear()

    # ── Compare ───────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🔍 Compare Varieties")
    st.caption("Select 2 or 3 apple varieties to compare their scores and flavor profiles side by side.")

    selected = st.multiselect(
        "Choose varieties to compare",
        options=df["Apple Variety"].tolist(),
        max_selections=3,
        placeholder="Pick 2–3 varieties…",
    )

    if len(selected) >= 2:
        cmp_df = (
            df[df["Apple Variety"].isin(selected)]
            .drop_duplicates("Apple Variety")
            .set_index("Apple Variety")
            .loc[selected]
            .reset_index()
        )

        cmp_cols = st.columns(len(selected))
        for col, (_, row) in zip(cmp_cols, cmp_df.iterrows()):
            with col:
                date_val = row["Date"].strftime("%b %Y") if pd.notna(row.get("Date")) else "—"
                st.markdown(
                    f"""<div class="apple-card">
                        <h3 style="font-size:1rem;margin-bottom:2px">{row['Apple Variety']}</h3>
                        <small>{row.get('From Where','—')} · {date_val}</small>
                    </div>""",
                    unsafe_allow_html=True,
                )
                score_val = f"{row['Score']:.1f} / 10" if pd.notna(row.get("Score")) else "—"
                st.metric("Score", score_val)
                st.markdown(f"_{row.get('Tasting Notes', '—')}_")

        radar_series = {
            row["Apple Variety"]: _flavor_scores(str(row.get("Tasting Notes") or ""))
            for _, row in cmp_df.iterrows()
        }
        st.plotly_chart(_make_radar(radar_series, title="Flavor Comparison"), use_container_width=True)
    elif selected:
        st.caption("Select at least one more variety to compare.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — ADD ENTRY
# ─────────────────────────────────────────────────────────────────────────────
with tab_add:
    st.subheader("Log a New Apple Variety")
    st.caption("Appends a new row directly to your Google Sheet and refreshes the app.")

    if "prefill_from_rec" in st.session_state:
        rec_p = st.session_state.pop("prefill_from_rec")
        st.session_state["add_auto_name"] = rec_p.get("name", "")
        tags_prefill: dict = {}
        if rec_p.get("type"):
            tags_prefill["type"] = rec_p["type"]
        if rec_p.get("origin"):
            tags_prefill["origin"] = rec_p["origin"]
        if rec_p.get("country") or (rec_p.get("origin") or "").split(",")[0]:
            tags_prefill["country"] = rec_p.get("country") or (rec_p.get("origin") or "").split(",")[0].strip()
        if tags_prefill:
            st.session_state["add_tags"] = tags_prefill
        st.session_state["_prefill_source"] = rec_p.get("name", "")

    if prefill_source := st.session_state.get("_prefill_source"):
        st.info(f"Pre-filling from your wishlist: **{prefill_source}** — review the details below and click Add to Sheet.")

    tag_col_name, tag_col_btn = st.columns([3, 1])
    with tag_col_name:
        auto_name = st.text_input(
            "Apple Variety *",
            key="add_auto_name",
            placeholder="e.g. Honeycrisp",
        )
    with tag_col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        autofill_clicked = st.button(
            "🔍 Auto-fill details",
            disabled=not auto_name.strip(),
            help="Uses AI to look up type, origin, and country",
        )

    if autofill_clicked:
        if not os.environ.get("OPENROUTER_API_KEY"):
            st.warning("OPENROUTER_API_KEY not set — auto-fill unavailable.")
        else:
            from recommendations import tag_apple
            with st.spinner(f"Looking up details for {auto_name.strip()}…"):
                tags = tag_apple(auto_name.strip())
            st.session_state["add_tags"] = tags
            st.rerun()

    tags: dict = st.session_state.get("add_tags", {})
    if tags:
        apple_type = tags.get("type") or "?"
        origin     = tags.get("origin") or "?"
        country    = tags.get("country") or "?"
        st.caption(f"Auto-detected: **{apple_type}** · **{origin}** · **{country}**")

    if auto_name.strip():
        _existing = df[df["Apple Variety"].str.strip().str.lower() == auto_name.strip().lower()]
        if not _existing.empty:
            _ex = _existing.iloc[0]
            _score_str  = f"{_ex['Score']:.1f}/10" if pd.notna(_ex.get("Score")) else "?"
            _date_str   = _ex["Date"].strftime("%b %Y") if pd.notna(_ex.get("Date")) else "?"
            _source_str = f" from {_ex.get('From Where', '')}" if _ex.get("From Where") else ""
            st.warning(
                f"⚠️ You've already logged **{_ex['Apple Variety']}** — "
                f"scored {_score_str} in {_date_str}{_source_str}. "
                "Submit anyway to add a second entry."
            )

    st.divider()

    with st.form("add_apple_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)

        with col_a:
            new_name = st.text_input(
                "Apple Variety *",
                value=st.session_state.get("add_auto_name", ""),
                placeholder="e.g. Honeycrisp",
            )
            new_score = st.slider("Score", min_value=1.0, max_value=10.0, value=7.0, step=0.5)

        with col_b:
            new_date  = st.date_input("Date Tried")
            new_notes = st.text_area(
                "Tasting Notes",
                placeholder="Describe the flavor, texture, crunch, aroma…",
                height=120,
            )

        st.markdown("**Details** — auto-filled from lookup, or edit manually")
        det_a, det_b, det_c = st.columns(3)

        type_options = ["", "eating", "cooking", "cider", "dual-purpose"]
        detected_type = tags.get("type", "")
        type_idx = type_options.index(detected_type) if detected_type in type_options else 0

        with det_a:
            new_type = st.selectbox("Type", type_options, index=type_idx)
        with det_b:
            new_origin = st.text_input("Origin Region", value=tags.get("origin", ""), placeholder="e.g. Pacific Northwest")
        with det_c:
            new_country = st.text_input("Country", value=tags.get("country", ""), placeholder="e.g. United States")

        submitted = st.form_submit_button("➕ Add to Sheet", type="primary")

    if submitted:
        if not new_name.strip():
            st.error("Apple variety name is required.")
        else:
            from sheets import append_apple
            try:
                extra: dict[str, str] = {}
                if new_type:
                    extra["Type"] = new_type
                if new_origin.strip():
                    extra["Origin"] = new_origin.strip()
                if new_country.strip():
                    extra["Country"] = new_country.strip()
                append_apple(
                    name=new_name.strip(),
                    date=new_date.strftime("%B %Y"),
                    from_where="",
                    score=new_score,
                    tasting_notes=new_notes.strip(),
                    extra_fields=extra or None,
                )
                st.session_state.pop("add_tags", None)
                st.session_state.pop("_prefill_source", None)
                st.success(f"✅ **{new_name.strip()}** added! Use the sidebar refresh to reload your collection.")
                st.cache_data.clear()
            except Exception as exc:
                st.error(f"Could not save to sheet: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — RECOMMENDATIONS
# ─────────────────────────────────────────────────────────────────────────────
with tab_recs:
    st.subheader("AI-Powered Apple Recommendations")
    st.caption(
        "An OpenRouter model analyses your highest-rated apple varieties and tasting notes to surface "
        "varieties you'll love, with specific stores and orchards near Harrison, NJ."
    )

    if "pinned_names" not in st.session_state:
        with st.spinner("Loading your saved recommendations…"):
            try:
                from sheets import load_pinned_apples
                st.session_state["pinned_names"] = set(load_pinned_apples())
            except Exception:
                st.session_state["pinned_names"] = set()

    pinned_names: set[str] = st.session_state["pinned_names"]

    num_recs = st.slider("Number of recommendations", min_value=3, max_value=10, value=6)

    col_gen, col_clear = st.columns([3, 1])
    with col_gen:
        gen_clicked = st.button("✨ Generate New Recommendations", type="primary")
    with col_clear:
        if st.button("🗑 Clear Cache", help="Remove locally cached recommendations"):
            st.session_state["recommendations"] = []
            st.session_state["rec_entry_count"] = None
            _save_rec_cache([], 0)
            st.rerun()

    if gen_clicked:
        if not os.environ.get("OPENROUTER_API_KEY"):
            st.error("OPENROUTER_API_KEY is not set. Add it to your .env file.")
        else:
            from recommendations import get_recommendations, add_images, add_ar_scores, RecommendationError
            try:
                with st.spinner("Analysing your apple preferences…"):
                    recs = get_recommendations(
                        df,
                        num_recs=num_recs,
                        already_pinned=sorted(pinned_names),
                    )

                with st.spinner("Fetching AR scores from applerankings.com…"):
                    recs = add_ar_scores(recs)

                if os.environ.get("TAVILY_API_KEY"):
                    with st.spinner("Fetching variety images…"):
                        recs = add_images(recs)

                st.session_state["recommendations"] = recs
                st.session_state["rec_entry_count"] = len(df)
                _save_rec_cache(recs, len(df))
            except RecommendationError as exc:
                st.error(
                    "The recommendation engine returned an unexpected response — please try again.\n\n"
                    f"Detail: {exc}"
                )

    recs: list[dict] = st.session_state.get("recommendations", [])

    _rec_entry_count = st.session_state.get("rec_entry_count")
    if recs and _rec_entry_count is not None and _rec_entry_count != len(df):
        st.info(
            f"Your collection has changed since these recommendations were generated "
            f"({_rec_entry_count} → {len(df)} varieties). "
            "Regenerate for up-to-date results."
        )

    if recs:
        n_pinned = sum(1 for r in recs if r.get("name", "") in pinned_names)
        st.markdown(f"### {len(recs)} Varieties You Should Try  &nbsp;·&nbsp; {n_pinned} saved")
        for chunk_i in range(0, len(recs), 2):
            pair = recs[chunk_i: chunk_i + 2]
            cols = st.columns(len(pair))
            for j, (col, rec) in enumerate(zip(cols, pair)):
                with col:
                    render_rec_card(
                        rec,
                        card_idx=chunk_i + j,
                        df=df,
                        is_pinned=rec.get("name", "") in pinned_names,
                    )
    elif not gen_clicked:
        st.info("No recommendations yet — click **Generate New Recommendations** to get started.")

    # ── Smart Match: AR + Your Taste ─────────────────────────────────────────
    st.divider()
    st.subheader("🎯 Smart Match: AR + Your Taste")
    st.caption(
        "Compares your personal scores with AppleRankings.com (AR) scores for varieties you've "
        "tried. Apples where both agree are the strongest signal of your taste. The model then "
        "finds untried AR-catalog varieties with similar profiles that are also likely to rate "
        "highly on AR. Run **Enrich All Varieties** first for the best results."
    )

    col_smart, col_smart_clear = st.columns([3, 1])
    with col_smart:
        smart_clicked = st.button("🎯 Find Smart Matches", type="primary", key="smart_recs_btn")
    with col_smart_clear:
        if st.button("🗑 Clear", key="smart_recs_clear", help="Remove cached Smart Match results"):
            st.session_state["smart_recs"] = []
            st.session_state["smart_entry_count"] = None
            _save_smart_cache([], 0)
            st.rerun()

    if smart_clicked:
        if not os.environ.get("OPENROUTER_API_KEY"):
            st.error("OPENROUTER_API_KEY is not set. Add it to your .env file.")
        else:
            has_ar = (
                "AR Score" in df.columns
                and df["AR Score"].astype(str).str.strip().replace("", pd.NA).notna().any()
            )
            if not has_ar:
                st.warning(
                    "No AR scores found in your collection yet. "
                    "Go to **My Collection → Enrich All Varieties** to fetch them, "
                    "then come back here for the best Smart Match results. "
                    "Generating recommendations from your personal scores only for now…"
                )
            from recommendations import get_ar_smart_recommendations, add_images as _add_images_smart, add_ar_scores as _add_ar_smart, RecommendationError as _SmartRecError
            try:
                with st.spinner("Analysing your AR + taste profile…"):
                    smart_recs_new = get_ar_smart_recommendations(
                        df,
                        num_recs=num_recs,
                        already_pinned=sorted(pinned_names),
                    )

                with st.spinner("Fetching AR scores from applerankings.com…"):
                    smart_recs_new = _add_ar_smart(smart_recs_new)

                if os.environ.get("TAVILY_API_KEY"):
                    with st.spinner("Fetching variety images…"):
                        smart_recs_new = _add_images_smart(smart_recs_new)

                st.session_state["smart_recs"] = smart_recs_new
                st.session_state["smart_entry_count"] = len(df)
                _save_smart_cache(smart_recs_new, len(df))
            except _SmartRecError as exc:
                st.error(
                    "Smart Match returned an unexpected response — please try again.\n\n"
                    f"Detail: {exc}"
                )

    smart_recs: list[dict] = st.session_state.get("smart_recs", [])

    _smart_entry_count = st.session_state.get("smart_entry_count")
    if smart_recs and _smart_entry_count is not None and _smart_entry_count != len(df):
        st.info(
            f"Your collection has changed since Smart Match was generated "
            f"({_smart_entry_count} → {len(df)} varieties). "
            "Re-run Smart Match for up-to-date results."
        )

    if smart_recs:
        n_smart_pinned = sum(1 for r in smart_recs if r.get("name", "") in pinned_names)
        st.markdown(f"### {len(smart_recs)} Smart Matches  &nbsp;·&nbsp; {n_smart_pinned} saved")
        for chunk_i in range(0, len(smart_recs), 2):
            pair = smart_recs[chunk_i: chunk_i + 2]
            cols = st.columns(len(pair))
            for j, (col, rec) in enumerate(zip(cols, pair)):
                with col:
                    render_rec_card(
                        rec,
                        card_idx=2000 + chunk_i + j,
                        df=df,
                        is_pinned=rec.get("name", "") in pinned_names,
                    )
    elif not smart_clicked:
        st.info("Click **Find Smart Matches** to get AR-aligned recommendations.")

    st.divider()
    st.subheader("🔎 Find Me Something Like…")
    st.caption("Pick an apple from your collection and get 3 closely matched alternatives you haven't tried.")

    apple_choices = sorted(df["Apple Variety"].dropna().unique().tolist())
    sim_col_a, sim_col_b = st.columns([3, 1])
    with sim_col_a:
        similar_to = st.selectbox(
            "Base variety",
            options=[""] + apple_choices,
            format_func=lambda x: "— choose a variety —" if x == "" else x,
            label_visibility="collapsed",
        )
    with sim_col_b:
        find_similar_clicked = st.button(
            "Find Similar",
            type="primary",
            disabled=not similar_to,
        )

    if find_similar_clicked and similar_to:
        if not os.environ.get("OPENROUTER_API_KEY"):
            st.error("OPENROUTER_API_KEY is not set.")
        else:
            from recommendations import get_similar_recommendations, add_images as _add_images, add_ar_scores as _add_ar_sim, RecommendationError as _SimRecError
            try:
                with st.spinner(f"Finding apples similar to {similar_to}…"):
                    sim_recs = get_similar_recommendations(
                        similar_to,
                        df,
                        num_recs=3,
                        already_pinned=sorted(pinned_names),
                    )

                with st.spinner("Fetching AR scores from applerankings.com…"):
                    sim_recs = _add_ar_sim(sim_recs)

                if os.environ.get("TAVILY_API_KEY"):
                    with st.spinner("Fetching images…"):
                        sim_recs = _add_images(sim_recs)
                st.session_state["similar_recs"] = sim_recs
                st.session_state["similar_to"] = similar_to
            except _SimRecError as exc:
                st.error(
                    "Find Similar returned an unexpected response — please try again.\n\n"
                    f"Detail: {exc}"
                )

    sim_recs: list[dict] = st.session_state.get("similar_recs", [])
    if sim_recs:
        base = st.session_state.get("similar_to", "")
        st.markdown(f"**Varieties similar to {base}:**")
        sim_cols = st.columns(min(len(sim_recs), 3))
        for j, (col, rec) in enumerate(zip(sim_cols, sim_recs)):
            with col:
                render_rec_card(
                    rec,
                    card_idx=1000 + j,
                    df=df,
                    is_pinned=rec.get("name", "") in pinned_names,
                )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — WISHLIST
# ─────────────────────────────────────────────────────────────────────────────
with tab_wishlist:
    st.subheader("My Apple Wishlist")
    st.caption("Varieties you've pinned to try. Mark as Tried to pre-fill the Add Entry form, or remove ones you've decided against.")

    col_wl_refresh, _ = st.columns([1, 5])
    with col_wl_refresh:
        if st.button("🔄 Refresh", key="wl_refresh"):
            load_wishlist_data.clear()
            st.rerun()

    wishlist = load_wishlist_data()

    if not wishlist:
        st.info("No varieties pinned yet — go to the **Recommendations** tab and hit **Save to Wishlist**.")
    else:
        st.caption(f"{len(wishlist)} variet{'ies' if len(wishlist) != 1 else 'y'} on your list")
        st.divider()

        for i in range(0, len(wishlist), 3):
            row_cols = st.columns(3)
            for j, col in enumerate(row_cols):
                idx = i + j
                if idx >= len(wishlist):
                    break
                item    = wishlist[idx]
                name    = item.get("Name", "")
                notes   = item.get("Tasting Notes", "")
                price   = item.get("Price", "")
                where   = item.get("Where to Find It", "")
                link    = item.get("Link", "")
                img_url = _parse_image_url(item.get("Image", ""))

                with col:
                    price_line = f"<small>💰 {price}</small>" if price else ""
                    st.markdown(
                        f"""<div class="apple-card">
                            <h3>{name}</h3>
                            {price_line}
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    if img_url:
                        try:
                            st.image(img_url, width=260)
                        except Exception:
                            pass
                    if notes:
                        st.caption(notes)
                    if where:
                        st.markdown("📍 **Where to find it:**")
                        for line in where.splitlines():
                            if line.strip():
                                st.markdown(f"- {line.strip()}")
                    if link:
                        st.markdown(f"[🔗 More info]({link})")

                    btn_a, btn_b = st.columns(2)
                    with btn_a:
                        if st.button("☑️ Mark as Tried", key=f"wl_tried_{idx}", type="primary"):
                            st.session_state["prefill_from_rec"] = {"name": name}
                            st.session_state["_prefill_source"] = name
                            st.toast(f"Switch to Add Entry to log '{name}'!")
                            st.rerun()
                    with btn_b:
                        if st.button("🗑 Remove", key=f"wl_remove_{idx}"):
                            try:
                                from sheets import remove_from_wishlist
                                remove_from_wishlist(name)
                                load_wishlist_data.clear()
                                st.session_state.get("pinned_names", set()).discard(name)
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not remove: {exc}")
                    st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 6 — STORE PLANNER
# ─────────────────────────────────────────────────────────────────────────────
with tab_planner:
    from planner import (
        KNOWN_STORES, UNION_SQUARE_VENDORS,
        MONTH_NAMES as _MONTH_NAMES, STORE_TYPE_LABELS,
        available_at, plan_visit,
    )

    st.subheader("🛒 Store Visit Planner")
    st.caption(
        "Choose a store and month to see which wishlist varieties are available right now, "
        "which top-rated favorites to re-stock, and which new varieties to scout. "
        "★ = within 5 miles of South Orange NJ or Flatiron Manhattan."
    )

    # ── Union Square Greenmarket callout (always visible) ────────────────────
    with st.expander("★★ Union Square Greenmarket — orchard vendors to know", expanded=False):
        st.markdown(
            "**14th St & Broadway, Manhattan** (Flatiron District)  \n"
            "Open year-round · **Mon · Wed · Fri · Sat**  \n"
            "These Hudson Valley and NY orchards sell varieties you won't find in any supermarket. "
            "Ask vendors what came off the tree most recently."
        )
        usq_cols = st.columns(2)
        for i, vendor in enumerate(UNION_SQUARE_VENDORS):
            with usq_cols[i % 2]:
                st.markdown(
                    f'<div class="apple-card" style="border-left-color:#2E8B40">'
                    f'<h3 style="font-size:0.9rem;margin-bottom:2px">{vendor["name"]}</h3>'
                    f'<small>{vendor["origin"]}</small>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.caption(vendor["notes"])

    st.divider()

    # ── Store + month selectors ───────────────────────────────────────────────
    tried_sources: list[str] = (
        sorted(df["From Where"].dropna().str.strip().replace("", pd.NA).dropna().unique().tolist())
        if "From Where" in df.columns else []
    )
    # Strip ★ markers for dedup comparison
    known_clean = {re.sub(r"^★+\s*", "", k).lower() for k in KNOWN_STORES}
    extra_sources = [s for s in tried_sources if re.sub(r"^★+\s*", "", s).lower() not in known_clean]

    # Build grouped option list with section headers as non-selectable separators
    _so_stores  = [k for k in KNOWN_STORES
                   if any(x in k for x in ("South Orange", "Maplewood", "Millburn", "Short Hills"))
                   and "at Union Square" not in k]
    _nyc_stores = [k for k in KNOWN_STORES
                   if "Manhattan" in k and "at Union Square" not in k]
    _nj_orchards = [k for k in KNOWN_STORES
                    if "NJ —" in k and "at Union Square" not in k
                    and not any(x in k for x in ("South Orange", "Maplewood", "Millburn", "Short Hills"))]
    _usq_vendors = [k for k in KNOWN_STORES if "at Union Square Greenmarket" in k]
    store_options = (
        ["── Within 5 miles of South Orange, NJ ──"] + _so_stores
        + ["── Within 5 miles of Flatiron, Manhattan ──"] + _nyc_stores
        + ["── NJ Orchards (day trips) ──"] + _nj_orchards
        + ["── Union Square Greenmarket Vendors ──"] + _usq_vendors
        + (["── Your History ──"] + extra_sources if extra_sources else [])
    )

    col_store, col_month = st.columns([3, 1])
    with col_store:
        chosen_store = st.selectbox(
            "Which store are you visiting?",
            options=[""] + store_options,
            format_func=lambda x: "— choose a store —" if x == "" else x,
        )
    with col_month:
        _cur_month = pd.Timestamp.now().month
        chosen_month = st.selectbox(
            "Month",
            options=list(range(1, 13)),
            index=_cur_month - 1,
            format_func=lambda m: _MONTH_NAMES[m],
        )

    _is_separator = lambda s: s.startswith("──")
    if not chosen_store or _is_separator(chosen_store):
        st.info("Choose a store above to generate your visit plan.")
    else:
        # Strip ★ markers before passing to plan logic
        store_clean = re.sub(r"^★+\s*", "", chosen_store)
        plan = plan_visit(store_clean, chosen_month, df, load_wishlist_data())
        visit_type = plan["visit_type"]
        type_label = STORE_TYPE_LABELS.get(visit_type, "🏪 Store")

        # Highlight badge for close stores
        is_close = chosen_store.startswith("★")
        proximity_badge = "&nbsp;★ Close" if is_close else ""
        st.markdown(
            f"**{type_label}**{proximity_badge} &nbsp;·&nbsp; {plan['month_name']} "
            f"&nbsp;·&nbsp; {plan['available_count']} varieties tracked in season"
        )

        # ── Section 1: Wishlist hits ──────────────────────────────────────────
        st.divider()
        wl = plan["wishlist_hits"]
        wl_count = len(wl)
        st.subheader(f"🎯 From Your Wishlist  ({wl_count} {'item' if wl_count == 1 else 'items'})")
        if wl:
            for item in wl:
                c1, c2 = st.columns([2, 3])
                with c1:
                    st.markdown(f"**{item['name']}**")
                    if item["price"]:
                        st.caption(f"💰 {item['price']}")
                with c2:
                    st.caption(item["notes"])
                    if item["tasting_notes"]:
                        st.caption(f"_{item['tasting_notes'][:140]}_")
        else:
            st.caption(
                "None of your wishlist varieties are available at this store type in "
                f"{plan['month_name']}. Try switching to a different store type or month."
            )

        # ── Section 2: Restock favorites ─────────────────────────────────────
        st.divider()
        rs = plan["restock"]
        rs_count = len(rs)
        st.subheader(f"⭐ Favorites to Re-stock  ({rs_count} {'variety' if rs_count == 1 else 'varieties'})")
        if rs:
            rs_cols = st.columns(3)
            for i, item in enumerate(rs):
                with rs_cols[i % 3]:
                    source_str = f" · last from {item['from_where']}" if item["from_where"] else ""
                    st.markdown(
                        f'<div class="apple-card">'
                        f'<h3 style="font-size:0.95rem;margin-bottom:2px">{item["name"]}</h3>'
                        f'<small>⭐ {item["score"]:.0f}/10{source_str}</small>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.caption(item["notes"])
        else:
            st.caption(
                "None of your 8+ rated varieties are available at this store type "
                f"in {plan['month_name']}."
            )

        # ── Section 3: Scout ─────────────────────────────────────────────────
        st.divider()
        sc = plan["scout"]
        sc_count = len(sc)
        st.subheader(f"🔍 Varieties to Scout  ({sc_count} untried)")
        st.caption(
            "Untried, non-wishlisted varieties available now — sorted shortest season first "
            "so the fleeting ones are at the top."
        )
        _TIER_BADGE = {
            "all":          "🛒 Any supermarket",
            "premium":      "🏪 Premium / specialty",
            "specialty":    "🌿 Specialty / greenmarket",
            "orchard-only": "🌳 Orchard or greenmarket only",
        }
        if sc:
            show_sc = sc[:12]
            overflow = sc[12:]
            for chunk_start in range(0, len(show_sc), 3):
                chunk = show_sc[chunk_start: chunk_start + 3]
                sc_cols = st.columns(3)
                for col, item in zip(sc_cols, chunk):
                    with col:
                        badge = _TIER_BADGE.get(item["stores"], "")
                        st.markdown(f"**{item['name']}**")
                        st.caption(f"{badge} · {item['notes']}")
            if overflow:
                with st.expander(f"Show all {sc_count} scoutable varieties"):
                    for item in overflow:
                        badge = _TIER_BADGE.get(item["stores"], "")
                        st.markdown(f"**{item['name']}** — {badge} — _{item['notes']}_")
        else:
            st.caption("All tracked varieties for this store type and month are already tried or wishlisted.")

        # ── Section 4: Coming up ──────────────────────────────────────────────
        st.divider()
        with st.expander("📅 New arrivals in the next 2 months"):
            current_avail = set(available_at(visit_type, chosen_month).keys())
            for offset in (1, 2):
                next_m = chosen_month % 12 + offset
                if next_m > 12:
                    next_m -= 12
                next_avail = set(available_at(visit_type, next_m).keys())
                arrivals = sorted(next_avail - current_avail)
                if arrivals:
                    st.markdown(f"**{_MONTH_NAMES[next_m]}:** " + ", ".join(v.title() for v in arrivals))
                else:
                    st.markdown(f"**{_MONTH_NAMES[next_m]}:** No new arrivals tracked")

        # ── Shopping list export ──────────────────────────────────────────────
        st.divider()
        with st.expander("📋 Copy shopping list"):
            lines = [f"Apple shopping list — {store_clean} · {plan['month_name']}", ""]
            if wl:
                lines.append("WISHLIST:")
                lines.extend(f"  ☐ {item['name']}" for item in wl)
                lines.append("")
            if rs:
                lines.append("RE-STOCK FAVORITES:")
                lines.extend(f"  ☐ {item['name']}  ({item['score']:.0f}/10)" for item in rs)
                lines.append("")
            if sc:
                lines.append("SCOUT (new varieties):")
                lines.extend(f"  ☐ {item['name']}  — {item['notes']}" for item in sc[:8])
            st.code("\n".join(lines), language=None)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🔄 Refresh Sheet Data"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("### API Status")
    for label, env_key in [
        ("Google Sheets",    "GOOGLE_SERVICE_ACCOUNT_JSON"),
        ("OpenRouter",       "OPENROUTER_API_KEY"),
        ("Tavily (enrich)",  "TAVILY_API_KEY"),
    ]:
        icon = "✅" if os.environ.get(env_key) else "❌"
        st.markdown(f"{icon} {label}")

    try:
        from planner import available_at
        _now_month = pd.Timestamp.now().month
        _wl_names = {
            item.get("Name", "").strip().lower()
            for item in load_wishlist_data()
            if item.get("Name", "").strip()
        }
        if _wl_names:
            _avail_now: set[str] = set()
            for _stype in ("orchard", "farmers_market", "premium", "supermarket"):
                _avail_now |= set(available_at(_stype, _now_month).keys())
            _hits = sorted(n for n in _wl_names if n in _avail_now)
            if _hits:
                st.divider()
                _hit_count = len(_hits)
                st.markdown(
                    f"🍎 **{_hit_count} wishlist "
                    f"{'variety' if _hit_count == 1 else 'varieties'} in season now**"
                )
                for _h in _hits[:5]:
                    st.markdown(f"· {_h.title()}")
                if _hit_count > 5:
                    st.caption(f"+ {_hit_count - 5} more — see Store Planner")
    except Exception:
        pass

    st.divider()
    st.markdown("**First run?** Copy `.env.example` → `.env` and fill in your keys.")
    with st.expander("Google Sheets setup"):
        st.markdown(
            """
1. [Google Cloud Console](https://console.cloud.google.com/) → enable **Sheets API** + **Drive API**
2. Create a **Service Account** → download JSON key
3. Set `GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/key.json` in `.env`
4. Share your spreadsheet with the service-account email (Editor role)
5. Set `APPLE_SPREADSHEET_ID=<your-sheet-id>` in `.env`
            """
        )
