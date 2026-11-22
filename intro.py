"""Welcome screen: what the app does, how it works, and what the results mean.
No person names, database names, models or techniques are shown here."""
import html

import streamlit as st

import backend as B

PROJECT_TITLE = "PairCheck AI"
TAGLINE = "Understand potential drug interactions"
PURPOSE = ("Check what is known about two or more medicines taken together. Where a pair is on record you see "
           "the record. Where it is not, you see a clearly marked estimate, or an honest \u201cnot enough information\u201d.")
e = html.escape

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
.block-container { max-width: 860px; padding-top: 2rem; padding-bottom: 3rem; }
.w-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.w-title { font-size: 2.2rem; font-weight: 500; color: #12283F; margin: 0; }
.w-chip { font-size: .75rem; padding: 3px 10px; border-radius: 20px; background: #E6F1FB; color: #0C447C; }
.w-tag { font-size: 1.15rem; color: #5F5E5A; margin: .2rem 0 .9rem 0; }
.w-p { font-size: .95rem; line-height: 1.6; margin-bottom: .9rem; }
.w-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 1rem 0 .4rem; }
.w-stat { background: #F5F7FA; border-radius: 10px; padding: 10px 14px; }
.w-stat .v { font-size: 1.5rem; font-weight: 500; color: #12283F; }
.w-stat .k { font-size: .8rem; color: #5F5E5A; }
.w-load { color: #888780; font-size: .9rem; margin: 1rem 0 .4rem; }
.w-h { font-size: 1.05rem; font-weight: 500; margin: 1.6rem 0 .6rem; color: #12283F; }
.w-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
.w-card { border: .5px solid #D3D1C7; border-radius: 12px; padding: 14px 16px; background: #fff; font-size: .88rem; }
.w-card b { display: block; margin-bottom: 4px; color: #12283F; }
.w-card .d { color: #5F5E5A; }
.w-tagx { display: inline-block; padding: 3px 12px; border-radius: 8px; font-weight: 500; font-size: .85rem; }
.w-note { background: #FAEEDA; color: #633806; border-radius: 10px; padding: 12px 16px; font-size: .88rem; margin-top: 1.4rem; }
</style>"""

STEPS = [
    ("1. Add medicines", "Generic names, brand names, or a photo of a printed prescription."),
    ("2. Confirm", "Check that each medicine was identified correctly."),
    ("3. Check pairs", "Every pair among your medicines is checked."),
    ("4. Read results", "Severity first, then what it is based on."),
]
RESULTS = [
    ("Major", "background:#FCEBEB;color:#791F1F;border:1.5px solid #A32D2D", "Recorded",
     "This pair is on record. The result is looked up, not guessed."),
    ("Moderate", "color:#633806;border:1.5px dashed #BA7517", "Predicted",
     "No record exists. This is an estimate, shown with a dashed outline. Treat it as low confidence."),
    ("Not enough information", "background:#F1EFE8;color:#444441;border:1.5px solid #888780", "No answer",
     "No record and no reliable estimate. This never means the combination is safe."),
]
HOW_TO_READ = ("The coloured tag shows severity: red for major, amber for moderate, blue for minor. A solid tag means "
               "the result is on record. A dashed outline means an estimate. Below the tag you see what the result is "
               "based on, with links to the original records where they exist. A result describes a possible "
               "interaction, not what will happen to a particular person.")
NOTICE = ("Research and educational prototype. It does not confirm that an interaction will occur in any individual, "
          "gives no dosing or personal advice, and is not for clinical use. Please consult a pharmacist or physician.")


def finished():
    return st.session_state.get("intro_done", False) or st.query_params.get("skip") == "1"


def _start():
    st.session_state.intro_done = True


def show():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="w-head"><p class="w-title">{e(PROJECT_TITLE)}</p>'
                '<span class="w-chip">Research and educational</span></div>'
                f'<p class="w-tag">{e(TAGLINE)}</p><p class="w-p">{e(PURPOSE)}</p>', unsafe_allow_html=True)
    st.button("Get started", type="primary", on_click=_start, key="start_top")
    stats_box = st.empty()
    stats_box.markdown('<div class="w-load">Loading data\u2026</div>', unsafe_allow_html=True)

    st.markdown('<div class="w-h">How it works</div><div class="w-grid">'
                + "".join(f'<div class="w-card"><b>{e(t)}</b><span class="d">{e(d)}</span></div>' for t, d in STEPS)
                + "</div>", unsafe_allow_html=True)
    st.markdown('<div class="w-h">What the results mean</div><div class="w-grid">'
                + "".join(f'<div class="w-card"><span class="w-tagx" style="{style}">{e(tag)}</span>'
                          f'<b style="margin-top:10px">{e(name)}</b><span class="d">{e(text)}</span></div>'
                          for tag, style, name, text in RESULTS) + "</div>", unsafe_allow_html=True)
    with st.expander("How to read your results"):
        st.write(HOW_TO_READ)
    st.markdown(f'<div class="w-note">{e(NOTICE)}</div>', unsafe_allow_html=True)
    _, mid, _ = st.columns([3, 2, 3])
    mid.button("Get started", type="primary", on_click=_start, key="start_bottom", use_container_width=True)

    s = B.stats()   # loads the data while the viewer reads; everything above is already on screen
    stats_box.markdown(
        '<div class="w-stats">'
        f'<div class="w-stat"><div class="v">{s["drugs"]:,}</div><div class="k">drugs covered</div></div>'
        f'<div class="w-stat"><div class="v">{s["pairs"]:,}</div><div class="k">recorded pairs with severity</div></div>'
        f'<div class="w-stat"><div class="v">{s["brands"]:,}</div><div class="k">Indian brand names</div></div></div>',
        unsafe_allow_html=True)
