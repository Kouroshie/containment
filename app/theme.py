"""Visual theme for the browser app.

The palette is not invented here: it is read from :mod:`containment.viz`, so the
page chrome and the figures drawn into it are one system rather than two that
happen to sit next to each other.  Only the page furniture lives in this
module; figure styling stays in ``viz``.

Two things are deliberately not done here.

Headings are not restyled in CSS.  Streamlit sets heading fonts through its
own theme with a specificity a plain ``h1`` selector cannot beat, so the
display face is set in ``.streamlit/config.toml`` as ``headingFont``, which is
the supported lever.  ``serif`` there means the Source Serif that Streamlit
already ships, so nothing is fetched from a font CDN at page load.

No web fonts are loaded.  An ``@import`` of Google Fonts here looked fine and
silently did nothing, leaving every rule that named those families on its
fallback.  Both faces below ship with Streamlit itself.

A note on selectors.  Streamlit's internal class names move between versions,
so everything below keys off ``data-testid`` hooks, and where a hook has been
renamed the old spelling is listed alongside the new one: 1.63 moved the tab
strip from BaseWeb to React Aria, renaming ``[data-baseweb="tab"]`` to
``[data-testid="stTab"]``.  The styling is additive, so a hook that is renamed
again leaves that element stock rather than breaking the page.
"""

from __future__ import annotations

import streamlit as st

from containment import viz

_UI = "'Source Sans', 'Segoe UI', system-ui, -apple-system, sans-serif"
_DISPLAY = "'Source Serif', Georgia, 'Times New Roman', serif"


def css() -> str:
    """The stylesheet, built from the figure palette."""
    p = viz.palette("light")
    return f"""
:root {{
  --surface: {p["surface"]};
  --panel: #ffffff;
  --panel-2: #f4f3f0;
  --line: {p["grid"]};
  --ink: {p["ink"]};
  --ink-2: {p["ink_2"]};
  --ink-3: {p["ink_3"]};
  --brand: {p["series"][0]};
  --brand-deep: {p["seq"][5]};
  --brand-wash: rgba(42, 120, 214, 0.08);
  --accent: {p["series"][1]};
  --good: {p["good"]};
  --warn: {p["warning"]};
  --bad: {p["critical"]};
  --radius: 12px;
  --shadow: 0 1px 2px rgba(16, 24, 40, 0.05), 0 1px 3px rgba(16, 24, 40, 0.04);
}}

.block-container {{ padding-top: 2.4rem; max-width: 1500px; }}

/* ---------------------------------------------------------- typography */
/* The face itself comes from theme.headingFont in config.toml; only the
   spacing is set here, which Streamlit leaves alone. */
h1, h2, h3, h4 {{ letter-spacing: -0.012em; color: var(--ink); }}
h1 {{ line-height: 1.15; margin-bottom: .15rem; }}
h2 {{ margin-top: 1.6rem; }}
[data-testid="stCaptionContainer"] p, .stCaption p {{
  color: var(--ink-2); font-size: .88rem; line-height: 1.5;
}}

/* The page header: eyebrow, title, standfirst, rule. */
.aor-hero {{
  border-bottom: 2px solid var(--line); padding-bottom: 1rem; margin-bottom: 1.4rem;
}}
.aor-eyebrow {{
  font-size: .74rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
  color: var(--brand); margin-bottom: .5rem;
}}
.aor-standfirst {{
  color: var(--ink-2); font-size: 1.02rem; max-width: 68ch; margin-top: .45rem;
}}
.aor-chip {{
  display: inline-block; margin: .7rem .4rem 0 0; padding: .2rem .6rem;
  border: 1px solid var(--line); border-radius: 999px; background: var(--panel);
  font-size: .76rem; font-weight: 600; color: var(--ink-2);
}}

/* --------------------------------------------------------------- tabs */
/* The result panels are the point of the page, so the tab strip reads as a
   real control: a segmented bar, with the open panel as a card beneath it. */
.stTabs [role="tablist"], .stTabs [data-baseweb="tab-list"] {{
  gap: .25rem; padding: .3rem; background: var(--panel-2);
  border: 1px solid var(--line); border-radius: 14px; flex-wrap: wrap;
}}
.stTabs [data-testid="stTab"], .stTabs [data-baseweb="tab"] {{
  height: auto; padding: .55rem 1.05rem; border-radius: 10px;
  font-family: {_UI}; font-size: .95rem; font-weight: 600; color: var(--ink-2);
  cursor: pointer; transition: background .15s ease, color .15s ease;
}}
.stTabs [data-testid="stTab"] p, .stTabs [data-baseweb="tab"] p {{
  font-size: .95rem; font-weight: 600; margin: 0; color: inherit;
}}
.stTabs [data-testid="stTab"]:hover, .stTabs [data-baseweb="tab"]:hover {{
  background: var(--brand-wash); color: var(--brand-deep);
}}
.stTabs [aria-selected="true"] {{
  background: var(--brand); color: #fff; box-shadow: 0 1px 3px rgba(16, 24, 40, .18);
}}
.stTabs [aria-selected="true"] p {{ color: #fff; }}
/* The open tab is a filled pill, so the underline marking it is redundant. */
.stTabs .react-aria-SelectionIndicator,
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{
  display: none;
}}
.stTabs [data-testid="stTabPanel"], .stTabs [data-baseweb="tab-panel"] {{
  border: 1px solid var(--line); border-radius: 16px; background: var(--panel);
  padding: 1.35rem 1.35rem .6rem; margin-top: .9rem; box-shadow: var(--shadow);
}}

/* ------------------------------------------------------------ metrics */
[data-testid="stMetric"], [data-testid="metric-container"] {{
  background: var(--panel); border: 1px solid var(--line);
  border-left: 4px solid var(--brand); border-radius: var(--radius);
  padding: .9rem 1.05rem; box-shadow: var(--shadow);
}}
[data-testid="stMetricValue"] {{
  font-family: {_DISPLAY}; font-size: 1.65rem; font-weight: 700;
  font-variant-numeric: tabular-nums; color: var(--ink);
}}
[data-testid="stMetricLabel"] p {{
  font-size: .76rem; font-weight: 700; letter-spacing: .07em;
  text-transform: uppercase; color: var(--ink-3);
}}
/* Our deltas are descriptions ("11.4 sq mi", "Method 1"), not changes. The
   call site passes delta_color="off"; the arrow and the green "this went up"
   wash survive that, and both state something untrue, so they go here. */
[data-testid="stMetricDelta"] svg {{ display: none; }}
[data-testid="stMetricDelta"] {{
  background: transparent !important; padding-left: 0;
  color: var(--ink-2) !important; font-size: .82rem; font-weight: 500;
}}
[data-testid="stMetricDelta"] div {{ color: var(--ink-2) !important; }}
[data-testid="stMetric"] div, [data-testid="stMetric"] p {{
  white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
}}

/* ------------------------------------------------------------ sidebar */
[data-testid="stSidebar"] {{
  background: var(--panel-2); border-right: 1px solid var(--line);
}}
[data-testid="stSidebar"] h2 {{
  font-family: {_UI}; font-size: .78rem; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; color: var(--brand-deep);
  border-bottom: 1px solid var(--line); padding-bottom: .4rem;
  margin: 1.5rem 0 .35rem;
}}
[data-testid="stSidebar"] label p {{
  font-size: .84rem; color: var(--ink-2); font-weight: 500;
}}

/* ------------------------------------------------- alerts and panels */
[data-testid="stAlert"], .stAlert {{
  border-radius: var(--radius); border: 1px solid var(--line);
  border-left-width: 4px; box-shadow: none;
}}
[data-testid="stExpander"] details {{
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--panel); box-shadow: var(--shadow);
}}
[data-testid="stExpander"] summary {{ font-weight: 600; font-size: .95rem; }}
[data-testid="stJson"] {{
  border: 1px solid var(--line); border-radius: 10px; padding: .5rem .7rem;
  background: var(--panel-2);
}}
[data-testid="stDataFrame"] {{
  border-radius: 10px; overflow: hidden; border: 1px solid var(--line);
}}
[data-testid="stTooltipIcon"] svg {{ color: var(--brand); }}

/* ------------------------------------------------------------ buttons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  border-radius: 10px; font-family: {_UI}; font-weight: 600; letter-spacing: .01em;
  transition: transform .12s ease, box-shadow .12s ease, background .12s ease;
}}
.stButton > button[kind="primary"] {{
  background: linear-gradient(180deg, #3d8ae2, var(--brand));
  border: none; padding: .62rem 1.1rem; font-size: 1rem;
  box-shadow: 0 1px 2px rgba(16, 24, 40, .14);
}}
.stButton > button[kind="primary"]:hover {{
  box-shadow: 0 3px 10px rgba(42, 120, 214, .3); transform: translateY(-1px);
}}
.stDownloadButton > button {{
  border: 1px solid var(--line); background: var(--panel); color: var(--ink);
}}
.stDownloadButton > button:hover {{
  border-color: var(--brand); color: var(--brand-deep); background: var(--brand-wash);
}}

/* A lead paragraph at the top of a result panel: what the panel is for. */
.aor-lead {{
  border-left: 3px solid var(--brand); background: var(--brand-wash);
  border-radius: 0 10px 10px 0; padding: .7rem .95rem; margin-bottom: 1.1rem;
  color: var(--ink-2); font-size: .92rem; line-height: 1.55;
}}
.aor-lead b {{ color: var(--ink); }}

/* Glossary entries on the Help panel. */
.aor-term {{ margin: .1rem 0 .9rem; }}
.aor-term dt {{ font-weight: 700; color: var(--ink); font-size: .95rem; }}
.aor-term dd {{
  margin: .15rem 0 0; color: var(--ink-2); font-size: .92rem; line-height: 1.55;
}}

/* --------------------------------------------------- banner (start page) */
.ct-banner {{
  position: relative; overflow: hidden; border-radius: 20px; padding: 2.1rem 2.2rem 1.9rem;
  margin-bottom: 1.4rem; color: #fff;
  background: radial-gradient(1200px 400px at 85% -10%, rgba(255,255,255,.18), transparent 60%),
              linear-gradient(120deg, #0f3d57 0%, #1f6f8b 45%, #2a78d6 100%);
  box-shadow: 0 10px 30px rgba(15, 61, 87, .25);
}}
.ct-banner h1 {{ color: #fff; font-size: 2.5rem; margin: .1rem 0 .4rem; }}
.ct-banner .ct-eyebrow {{
  font-size: .75rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
  color: rgba(255,255,255,.8);
}}
.ct-banner p {{ color: rgba(255,255,255,.92); font-size: 1.05rem; max-width: 70ch; margin: 0; }}
.ct-banner .ct-chip {{
  display: inline-block; margin: .9rem .45rem 0 0; padding: .22rem .7rem; border-radius: 999px;
  background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.28);
  font-size: .76rem; font-weight: 600; color: #fff;
}}
.ct-banner .ct-wave {{
  position: absolute; right: -40px; bottom: -60px; width: 340px; height: 340px; border-radius: 50%;
  border: 46px solid rgba(255,255,255,.07);
}}

/* ------------------------------------------------------- page header */
.ct-head {{ display: flex; align-items: center; gap: .9rem; margin: .2rem 0 1.1rem; }}
.ct-head .ct-icon {{
  width: 46px; height: 46px; border-radius: 12px; display: flex; align-items: center;
  justify-content: center; font-size: 1.45rem; color: #fff;
  background: linear-gradient(135deg, #1f6f8b, #2a78d6); box-shadow: 0 4px 12px rgba(42,120,214,.3);
}}
.ct-head h2 {{ margin: 0 !important; font-size: 1.65rem; }}
.ct-head .ct-sub {{ color: var(--ink-2); font-size: .95rem; margin-top: .1rem; }}
.ct-step {{
  font-size: .72rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
  color: var(--brand);
}}

/* ------------------------------------------------------------- cards */
.ct-card {{
  border: 1px solid var(--line); border-radius: 16px; background: var(--panel);
  padding: 1.15rem 1.2rem 1rem; box-shadow: var(--shadow); height: 100%;
  transition: transform .15s ease, box-shadow .15s ease;
}}
.ct-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 22px rgba(16,24,40,.08); }}
.ct-card .ct-ci {{ font-size: 1.8rem; }}
.ct-card h4 {{ margin: .35rem 0 .3rem; font-size: 1.08rem; }}
.ct-card p {{ color: var(--ink-2); font-size: .9rem; margin: 0; line-height: 1.5; }}
.ct-flow {{ display: flex; gap: .6rem; flex-wrap: wrap; margin: .4rem 0 1rem; }}
.ct-flow span {{
  flex: 1 1 140px; text-align: center; padding: .6rem .5rem; border-radius: 12px;
  background: var(--brand-wash); color: var(--brand-deep); font-weight: 600; font-size: .9rem;
}}
.ct-flow b {{
  display: inline-block; width: 1.5rem; height: 1.5rem; line-height: 1.5rem; border-radius: 50%;
  background: var(--brand); color: #fff; margin-right: .35rem; font-size: .8rem;
}}

/* ----------------------------------------------------- review flags */
.ct-flag {{
  display: flex; gap: .6rem; align-items: flex-start; padding: .6rem .75rem; margin-bottom: .45rem;
  border-radius: 10px; border: 1px solid var(--line); background: var(--panel); font-size: .9rem;
}}
.ct-flag .ct-dot {{ width: .7rem; height: .7rem; border-radius: 50%; margin-top: .3rem; flex: none; }}
.ct-flag.ok .ct-dot {{ background: var(--good); }}
.ct-flag.warn .ct-dot {{ background: var(--warn); }}
.ct-flag.bad .ct-dot {{ background: var(--bad); }}
.ct-flag.info .ct-dot {{ background: var(--brand); }}
.ct-flag b {{ color: var(--ink); }}

/* ------------------------------------------- segmented view selectors */
.st-key-map_view [role="radiogroup"], .st-key-source [role="radiogroup"] {{
  gap: .4rem; flex-wrap: wrap;
}}
.st-key-map_view label[data-testid="stRadioOption"], .st-key-source label[data-testid="stRadioOption"] {{
  margin: 0; padding: .45rem 1rem; border-radius: 999px; border: 1px solid var(--line);
  background: var(--panel); font-weight: 600; cursor: pointer;
}}
.st-key-map_view label[data-testid="stRadioOption"] > div > div > div:not([data-testid="stMarkdownContainer"]),
.st-key-source label[data-testid="stRadioOption"] > div > div > div:not([data-testid="stMarkdownContainer"]) {{ display: none; }}
.st-key-map_view label[data-testid="stRadioOption"]:has(input:checked),
.st-key-source label[data-testid="stRadioOption"]:has(input:checked) {{
  background: linear-gradient(90deg, #1f6f8b, #2a78d6); border-color: transparent;
}}
.st-key-map_view label[data-testid="stRadioOption"]:has(input:checked) p,
.st-key-source label[data-testid="stRadioOption"]:has(input:checked) p {{ color: #fff; }}

/* ---------------------------------------------------- sidebar frame */
.ct-brand {{ display: flex; align-items: center; gap: .55rem; margin: -.4rem 0 .6rem; }}
.ct-brand .ct-logo {{
  width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center;
  justify-content: center; color: #fff; font-weight: 800;
  background: linear-gradient(135deg, #0f3d57, #2a78d6);
}}
.ct-brand .ct-name {{ font-weight: 800; font-size: 1.15rem; color: var(--ink); line-height: 1.1; }}
.ct-brand .ct-tag {{ font-size: .72rem; color: var(--ink-3); }}
.ct-status {{
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  padding: .6rem .75rem; font-size: .84rem; margin-bottom: .6rem;
}}
.ct-status .ct-pill {{
  display: inline-block; padding: .08rem .5rem; border-radius: 999px; font-size: .74rem;
  font-weight: 700; margin-top: .3rem;
}}
.ct-pill.ok {{ background: rgba(46,160,67,.12); color: #1d7a33; }}
.ct-pill.warn {{ background: rgba(219,140,20,.14); color: #9a5c00; }}
.ct-pill.none {{ background: var(--panel-2); color: var(--ink-3); }}
.ct-navhead {{
  font-size: .7rem; font-weight: 800; letter-spacing: .14em; text-transform: uppercase;
  color: var(--ink-3); margin: .9rem 0 .25rem .2rem;
}}
[data-testid="stSidebar"] .stButton > button {{
  justify-content: flex-start; text-align: left; border-radius: 10px; padding: .42rem .7rem;
  border: 1px solid transparent; background: transparent; color: var(--ink-2);
  font-weight: 600; font-size: .92rem; box-shadow: none;
}}
[data-testid="stSidebar"] [class*="st-key-nav_"] .stButton > button > div {{
  justify-content: flex-start; width: 100%;
}}
[data-testid="stSidebar"] [class*="st-key-nav_"] {{ margin-top: -.55rem; }}
[data-testid="stSidebar"] .stButton > button:hover {{
  background: var(--brand-wash); color: var(--brand-deep); transform: none;
}}
[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] {{
  background: var(--brand-wash); color: var(--brand-deep); border: none;
  border-left: 3px solid var(--brand); border-radius: 4px 10px 10px 4px;
}}
[data-testid="stSidebar"] .st-key-runbox .stButton > button {{
  justify-content: center; text-align: center; padding: .6rem .7rem; margin: .2rem 0 .3rem;
  background: linear-gradient(90deg, #1f6f8b, #2a78d6); color: #fff; border: none;
  border-radius: 12px; font-size: 1rem; box-shadow: 0 4px 12px rgba(42,120,214,.3);
}}
[data-testid="stSidebar"] .st-key-runbox .stButton > button:hover {{
  filter: brightness(1.08); color: #fff;
}}
[data-testid="stSidebar"] .stDownloadButton > button {{
  justify-content: flex-start; font-size: .85rem;
}}
[data-testid="stSidebar"] .stButton > button:disabled {{ opacity: .45; }}
"""


def apply() -> None:
    """Inject the stylesheet.  Call once, right after ``set_page_config``."""
    st.markdown(f"<style>{css()}</style>", unsafe_allow_html=True)


def hero(title: str, standfirst: str, chips: tuple = ()) -> None:
    """The page header block."""
    tags = "".join(f'<span class="aor-chip">{c}</span>' for c in chips)
    st.markdown(
        f'<div class="aor-hero">'
        f'<div class="aor-eyebrow">UIC Class VI</div>'
        f'<h1>{title}</h1>'
        f'<div class="aor-standfirst">{standfirst}</div>{tags}</div>',
        unsafe_allow_html=True)


def lead(text: str) -> None:
    """A short "what this panel is for" note at the top of a result tab."""
    st.markdown(f'<div class="aor-lead">{text}</div>', unsafe_allow_html=True)


def banner(title: str, text: str, chips: tuple = ()) -> None:
    """The start page's gradient banner."""
    tags = "".join(f'<span class="ct-chip">{c}</span>' for c in chips)
    st.markdown(f'<div class="ct-banner"><div class="ct-wave"></div>'
                f'<div class="ct-eyebrow">UIC Class VI review</div><h1>{title}</h1>'
                f'<p>{text}</p>{tags}</div>', unsafe_allow_html=True)


def page_header(icon: str, title: str, sub: str = "", step: str = "") -> None:
    """Icon badge, title and one-line subtitle at the top of every page."""
    st.markdown(
        f'<div class="ct-head"><div class="ct-icon">{icon}</div><div>'
        + (f'<div class="ct-step">{step}</div>' if step else "")
        + f'<h2>{title}</h2>' + (f'<div class="ct-sub">{sub}</div>' if sub else "")
        + '</div></div>', unsafe_allow_html=True)


def card(icon: str, title: str, text: str) -> None:
    st.markdown(f'<div class="ct-card"><div class="ct-ci">{icon}</div><h4>{title}</h4>'
                f'<p>{text}</p></div>', unsafe_allow_html=True)


def flow(steps: list[str]) -> None:
    st.markdown('<div class="ct-flow">' + "".join(
        f'<span><b>{i}</b>{s}</span>' for i, s in enumerate(steps, 1)) + '</div>',
        unsafe_allow_html=True)


def flag(kind: str, text: str) -> None:
    """One review flag: kind is ok, warn, bad or info (colour plus words)."""
    st.markdown(f'<div class="ct-flag {kind}"><div class="ct-dot"></div><div>{text}</div></div>',
                unsafe_allow_html=True)


def brand() -> None:
    st.markdown('<div class="ct-brand"><div class="ct-logo">C</div><div>'
                '<div class="ct-name">Containment</div>'
                '<div class="ct-tag">Class VI AoR, corrective action, PISC</div></div></div>',
                unsafe_allow_html=True)


def status(project_line: str, pill_kind: str, pill_text: str) -> None:
    st.markdown(f'<div class="ct-status">{project_line}<br>'
                f'<span class="ct-pill {pill_kind}">{pill_text}</span></div>',
                unsafe_allow_html=True)


def navhead(text: str) -> None:
    st.markdown(f'<div class="ct-navhead">{text}</div>', unsafe_allow_html=True)
