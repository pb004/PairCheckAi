"""PairCheck AI - multi-drug view. Checks every pair among 2 to 5 drugs, plus a printable sheet.
Run:  python -m streamlit run app_multi.py      (the single-pair app.py is unchanged)
"""
import html
import os
import itertools
import re
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

import backend as B
import ocr
from explain import type_meaning
from links import record_ids_html, cite_html, mechanism_source_html, has_other, other_body

import intro

st.set_page_config(page_title="PairCheck AI", layout="centered")
if not intro.finished():
    intro.show()
    st.stop()

SEV_T, TYPE_T = B.thresholds()
MAX_DRUGS = 5
DISCLAIMER = ("Research and educational prototype. This does not confirm that an interaction "
              "will occur in any individual. Please consult a pharmacist or physician.")
NOT_ASSESSED = ("Pairs are checked one at a time. Combinations of three or more drugs are not assessed, "
                "and nothing here replaces a pharmacist or physician.")
e = html.escape

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
.block-container { max-width: 860px; padding-top: 1rem; padding-bottom: 5rem; }
.brand { font-size: 1.35rem; font-weight: 500; color: #12283F; padding-top: .35rem; }
.sevrow { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.sevlbl { font-size: 1.1rem; color: #5F5E5A; }
.tag { display: inline-flex; align-items: center; gap: 8px; padding: 3px 12px; border-radius: 10px;
       font-size: 1rem; font-weight: 500; }
.tag.big { padding: 8px 18px; font-size: 1.5rem; gap: 10px; }
.glyph { width: 20px; height: 20px; border: 2px solid; border-radius: 50%; display: inline-flex;
         align-items: center; justify-content: center; font-size: .7rem; }
.big .glyph { width: 26px; height: 26px; font-size: .95rem; }
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 1rem 0 .3rem; }
.card { background: #F5F7FA; border-radius: 8px; padding: 10px 12px; }
.card .k { font-size: .8rem; color: #5F5E5A; } .card .v { font-size: 1.5rem; font-weight: 500; }
.note { background: #E6F1FB; color: #0C447C; border-radius: 8px; padding: 10px 14px; font-size: .88rem;
        margin: .8rem 0 1rem; }
.grp { font-size: .85rem; color: #5F5E5A; margin: 1rem 0 .4rem; }
.prow { display: flex; align-items: center; gap: 12px; border: .5px solid #D3D1C7; border-radius: 12px;
        padding: 9px 14px; background: #fff; margin-bottom: .3rem; }
.pname { flex: 1; } .pstat { font-size: .8rem; color: #5F5E5A; min-width: 70px; text-align: right; }
.diagram { display: flex; justify-content: center; align-items: center; gap: 10px; flex-wrap: wrap;
           margin-bottom: .8rem; }
.pill { padding: 5px 14px; border: .5px solid #B4B2A9; border-radius: 20px; background: #F5F7FA; }
.panel { border: .5px solid #D3D1C7; border-radius: 12px; padding: 14px 16px; background: #fff;
         height: 100%; margin-bottom: .6rem; }
.ph { font-size: .85rem; color: #5F5E5A; margin-bottom: 6px; }
.brow { display: flex; align-items: center; gap: 10px; margin-top: 6px; font-size: .85rem; }
.bn { width: 120px; } .bp { width: 36px; text-align: right; }
.bt { flex: 1; height: 8px; background: #EEF0F3; border-radius: 4px; }
.bt div { height: 8px; background: #185FA5; border-radius: 4px; }
mark { background: #FAEEDA; color: #633806; padding: 0 2px; border-radius: 3px; }
.empty { border: .5px dashed #B4B2A9; border-radius: 12px; padding: 1.4rem; color: #5F5E5A; }
.foot { position: fixed; left: 0; right: 0; bottom: 0; background: #12283F; color: #EEF2F7;
        font-size: .8rem; padding: .5rem 1rem; text-align: center; z-index: 99; }
</style>""", unsafe_allow_html=True)

STYLE = {"Major": ("#FCEBEB", "#791F1F", "#A32D2D", "!"), "Moderate": ("#FAEEDA", "#633806", "#BA7517", "!"),
         "Minor": ("#E6F1FB", "#0C447C", "#378ADD", "i"), None: ("#F1EFE8", "#444441", "#888780", "?")}
RANK = {"Major": 0, "Moderate": 1, "Minor": 2}


def tag(sev, predicted, big=False):
    bg, fg, bd, g = STYLE.get(sev, STYLE[None])
    fill, line = ("transparent", "dashed") if predicted else (bg, "solid")
    return (f'<span class="tag{" big" if big else ""}" style="background:{fill};color:{fg};'
            f'border:2px {line} {bd}"><span class="glyph" style="border-color:{fg}">{g}</span>'
            f'{e(sev or "Not enough information")}</span>')


def build(a, b):
    rec = B.lookup_pair(a, b)
    if rec:
        return dict(kind="rec", sev=rec["severity"], type=rec["type"], types=rec["types"],
                    ids=rec.get("ids", ""), db_ids=rec.get("db_ids", []), dd_ids=rec.get("dd_ids", []),
                    status="Recorded in source databases",
                    sub="Looked up, not predicted. Severity from DDInter.")
    p = B.predict_pair(a, b)
    sev_ok, type_ok = p["sev_p"] >= SEV_T, p["types"][0][1] >= TYPE_T
    if not (sev_ok or type_ok):
        return dict(kind="none", sev=None, status="No record found, and no reliable estimate is available",
                    sub="This does not mean the pair is safe.")
    return dict(kind="pred", sev=p["severity"] if sev_ok else None,
                type=p["types"][0][0] if type_ok else None, types=p["types"] if type_ok else [],
                status="Predicted. Treat as low confidence",
                sub="Not recorded in the source databases. Applies only if an interaction exists.")


def analyse(a, b):
    s = build(a, b)
    sent = B.get_label_sentence(a, b) if s["kind"] == "rec" else None
    return dict(a=a, b=b, na=a.title(), nb=b.title(), s=s, sent=sent)


def order(r):
    s = r["s"]
    return ({"rec": 0, "pred": 1, "none": 2}[s["kind"]], RANK.get(s["sev"], 3))


def highlight(text, partner):
    import re
    return re.sub(f"({re.escape(e(partner))})", r"<mark>\1</mark>", e(text), flags=re.I)


def meaning(s):
    if s["kind"] == "rec":
        return " ".join(type_meaning(t) for t in s["types"])
    return ("This estimate comes from chemical structure only, so there is no explanation "
            "of how the two drugs interact.")


def details(r):
    s = r["s"]
    if s.get("type"):
        arrow = '<span style="color:#5F5E5A;font-size:1.2rem">&#8596;</span>'
        st.markdown(f'<div class="diagram"><span class="pill">{e(r["na"])}</span>{arrow}'
                    f'<span class="pill">{e(s["type"])}</span>{arrow}<span class="pill">{e(r["nb"])}</span></div>',
                    unsafe_allow_html=True)
    body = f'<div>{e(meaning(s))}</div>'
    if s["kind"] == "pred" and s["types"]:
        body += '<div class="ph" style="margin-top:12px">Top three types, if an interaction exists</div>'
        for n, p in s["types"]:
            body += (f'<div class="brow"><span class="bn">{e(n)}</span><div class="bt">'
                     f'<div style="width:{p * 100:.0f}%"></div></div><span class="bp">{p:.0%}</span></div>')
    ids_line = record_ids_html(s.get("db_ids"), s.get("dd_ids")) or e(s.get("ids", ""))
    if s["kind"] == "rec" and ids_line:
        body += f'<div class="ph" style="margin-top:10px">Record IDs: {ids_line}</div>'
    st.markdown(f'<div class="panel"><div class="ph">What this means</div>{body}</div>', unsafe_allow_html=True)
    if r["sent"]:
        st.markdown(f'<div class="panel"><div class="ph">Source text</div>'
                    f'<div>{highlight(r["sent"]["sentence"], r["sent"]["partner"])}</div>'
                    f'<div class="ph" style="margin-top:6px">{cite_html(r["sent"]["cite"], r["sent"].get("set_id"))}</div></div>',
                    unsafe_allow_html=True)
    show_other = has_other(s.get("types"))
    cols = st.columns(3 if show_other else 2)
    for col, d, name in zip(cols, (r["a"], r["b"]), (r["na"], r["nb"])):
        m = B.get_mechanism(d)
        txt = (f'<div>{e(m["text"])}</div><div class="ph" style="margin-top:6px">{mechanism_source_html(m)}</div>'
               if m else '<div class="ph">Not available</div>')
        col.markdown(f'<div class="panel"><div class="ph">{e(name)}</div>{txt}</div>', unsafe_allow_html=True)
    if show_other:
        cols[2].markdown(f'<div class="panel"><div class="ph">What \u201cOther\u201d means</div>'
                         f'{other_body(B.other_examples())}</div>', unsafe_allow_html=True)


SHEET_CSS = """
body{font-family:Arial,Helvetica,sans-serif;color:#1F2937;margin:18px;font-size:14px}
.top{display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid #12283F;
 padding-bottom:6px;margin-bottom:12px}.top b{font-size:20px}.dt{font-size:12px;color:#5F5E5A}
.k{font-size:12px;color:#5F5E5A;margin-top:8px}.pair{border-top:1px solid #D3D1C7;padding:12px 0;
 page-break-inside:avoid}.pn{font-size:16px;font-weight:bold;margin-bottom:6px}
.sevrow{display:flex;align-items:center;gap:10px}.sevlbl{color:#5F5E5A}
.tag{display:inline-flex;align-items:center;gap:8px;padding:3px 12px;border-radius:8px;font-weight:bold}
.glyph{width:18px;height:18px;border:2px solid;border-radius:50%;display:inline-flex;align-items:center;
 justify-content:center;font-size:11px}.st{font-weight:bold;margin-top:6px}.sb{font-size:12px;color:#5F5E5A}
.box{border:1px solid #888;padding:10px 12px;margin:14px 0;font-size:13px;page-break-inside:avoid}
.foot{font-size:11px;color:#5F5E5A;border-top:1px solid #D3D1C7;padding-top:8px}
button{padding:8px 18px;background:#12283F;color:#fff;border:0;border-radius:6px;font-size:14px;cursor:pointer;
 margin-bottom:12px}
@media print{.noprint{display:none}body{margin:0}}
"""


def sheet_html(rows, names, notes=()):
    when = datetime.now().strftime("%d %b %Y, %H:%M")
    shown = [r for r in rows if r["s"]["kind"] != "none"]
    none = [r for r in rows if r["s"]["kind"] == "none"]
    out = ['<button class="noprint" onclick="window.print()">Print this sheet</button>',
           f'<div class="top"><b>PairCheck AI</b><span class="dt">Result sheet &middot; {when}</span></div>',
           '<div class="k">Medicines checked</div>',
           f'<div>{e(", ".join(n.title() for n in names))}</div>']
    if notes:
        out.append('<div class="k">Entered as brand names</div><div>' + e("; ".join(notes)) + '</div>')
    for r in shown:
        s = r["s"]
        blk = (f'<div class="pair"><div class="pn">{e(r["na"])} + {e(r["nb"])}</div><div class="sevrow">'
               f'<span class="sevlbl">Severity:</span>{tag(s["sev"], s["kind"] == "pred" and s["sev"] is not None)}</div>'
               f'<div class="st">{e(s["status"])}</div><div class="sb">{e(s["sub"])}</div>')
        if s.get("type"):
            blk += f'<div class="k">Interaction type</div><div>{e(s["type"])}</div>'
        blk += f'<div class="k">What this means</div><div>{e(meaning(s))}</div>'
        if s["kind"] == "pred" and s["types"]:
            blk += ('<div class="k">Most likely types, if an interaction exists</div><div>'
                    + e(", ".join(f"{n} ({p:.0%})" for n, p in s["types"])) + '</div>')
        if r["sent"]:
            blk += (f'<div class="k">Source text</div><div>{e(r["sent"]["sentence"])}</div>'
                    f'<div class="sb">{cite_html(r["sent"]["cite"], r["sent"].get("set_id"))}</div>')
        if s["kind"] == "rec" and s.get("ids"):
            blk += f'<div class="k">Record IDs</div><div class="sb">{record_ids_html(s.get("db_ids"), s.get("dd_ids")) or e(s["ids"])}</div>'
        out.append(blk + '</div>')
    if none:
        out.append('<div class="pair"><div class="pn">Not enough information</div><div>'
                   + e("; ".join(f'{r["na"]} + {r["nb"]}' for r in none))
                   + '</div><div class="sb">No record was found and no reliable estimate is available. '
                     'This does not mean these combinations are safe.</div></div>')
    out.append(f'<div class="box">{e(DISCLAIMER)} {e(NOT_ASSESSED)} This sheet is not medical advice, and a '
               'missing result never means a combination is safe.</div>')
    out.append('<div class="foot">Data: DrugBank-style table, DDInter, PubChem, ChEMBL, openFDA labels. '
               'Nothing about this check is stored.</div>')
    return f"<html><head><style>{SHEET_CSS}</style></head><body>{''.join(out)}</body></html>"


def results(names, notes=()):
    rows = sorted((analyse(a, b) for a, b in itertools.combinations(names, 2)), key=order)
    n = {k: sum(r["s"]["kind"] == k for r in rows) for k in ("rec", "pred", "none")}
    st.markdown(f'<div class="cards"><div class="card"><div class="k">Recorded</div><div class="v">{n["rec"]}</div></div>'
                f'<div class="card"><div class="k">Predicted</div><div class="v">{n["pred"]}</div></div>'
                f'<div class="card"><div class="k">Not enough information</div><div class="v">{n["none"]}</div></div></div>'
                f'<div class="ph">{len(rows)} pairs checked. There is no overall verdict, and a missing result '
                f'never means safe.</div><div class="note">{e(NOT_ASSESSED)}</div>', unsafe_allow_html=True)
    heads = {"rec": "Recorded, shown first", "pred": "Predicted. Treat as low confidence",
             "none": "Not enough information"}
    last = None
    for r in rows:
        s = r["s"]
        if s["kind"] != last:
            st.markdown(f'<div class="grp">{heads[s["kind"]]}</div>', unsafe_allow_html=True)
            last = s["kind"]
        stat = {"rec": "Recorded", "pred": "Predicted", "none": ""}[s["kind"]]
        st.markdown(f'<div class="prow"><span class="pname">{e(r["na"])} + {e(r["nb"])}</span>'
                    f'{tag(s["sev"], s["kind"] == "pred" and s["sev"] is not None)}'
                    f'<span class="pstat">{stat}</span></div>', unsafe_allow_html=True)
        if s["kind"] != "none":
            with st.expander("Details"):
                details(r)
    with st.expander("Print sheet"):
        components.html(sheet_html(rows, names, notes), height=640, scrolling=True)


c1, c2, c3 = st.columns([6, 1.7, 2], vertical_alignment="center")
c1.markdown('<div class="brand">PairCheck AI</div>', unsafe_allow_html=True)
HOW_IT_WORKS = """**What this app does**

You tell it which medicines a person takes. It looks at every pair of those medicines and shows what is known about taking them together.

**When the pair is on record**

Some medicine pairs have been written down in published records. For these, the app shows what the record says: how serious the interaction is (minor, moderate or major) and what kind of effect it has. This is simply looked up, so nothing is guessed.

**When the pair is not on record**

Many pairs have never been written down. For those, the app may give a rough estimate, marked clearly as *Predicted*. It is a careful guess based on what the medicines are made of, so please treat it with caution. If the app cannot make a reasonable guess, it says *Not enough information* instead.

**When you add several medicines**

The app checks them two at a time and lists the pairs that are on record first. It does not give one overall answer, because that could be misleading. If a medicine shows no warning, that does not mean it is safe."""

DATA_AND_LIMITS = """- The app never says a combination is safe. If nothing is shown, it may simply be that nobody has studied that pair.
- It checks medicines two at a time. It does not look at what happens when three or more are taken together.
- A *Predicted* result is only an estimate. It can be wrong, and it cannot say what will happen to any one person.
- The app does not know the dose, a person's age or their health conditions, and it gives no personal medical advice.
- It is meant for learning and research, not for deciding on treatment. Please ask a doctor or pharmacist."""
with c2.popover("How it works"):
    st.markdown(HOW_IT_WORKS)
with c3.popover("Data and limits"):
    st.markdown(DATA_AND_LIMITS)

opts = B.drug_options()


def add_brand(labels, drugs, text):
    cur = list(st.session_state.get("sel", []))
    new = [x for x in labels if x in opts and x not in cur]
    if len(cur) + len(new) > MAX_DRUGS:
        st.session_state.brand_msg = f"Not added: the list holds at most {MAX_DRUGS} drugs. Remove one first."
        return
    st.session_state.sel = cur + new
    if text:
        st.session_state.notes = st.session_state.get("notes", []) + [{"text": text, "drugs": drugs}]
    st.session_state.brand_msg = "Added. Verify the ingredients against the prescription."


def use_line(text):
    st.session_state.med_q = text


if ocr.available():
    with st.expander("Read from a prescription image"):
        source = st.radio("Source", ["Upload", "Camera"], horizontal=True, label_visibility="collapsed", key="rx_src")
        if source == "Upload":
            up = st.file_uploader("Prescription photo", type=["png", "jpg", "jpeg"], key="rx_file")
        else:
            up = st.camera_input("Take a photo of the prescription", key="rx_cam")
        st.caption("Printed text only. The image is processed on the server and is not saved by the app. "
                   "Use sample prescriptions, not real patient details."
                   if os.getenv("PAIRCHECK_ONLINE") else
                   "Printed text only. The image is read on this computer and is not saved by the app.")
        if up is not None:
            try:
                with st.spinner("Reading the image"):
                    scored = ocr.read_scored(up.getvalue())
                    lines = [t for t, _ in scored]
            except Exception:
                scored, lines = [], []
                st.warning("The image could not be read. Try a clearer photo or type the names below.")
            hits = ocr.find_medicines(lines)
            if hits:
                st.markdown("**Medicines found**")
                for i, (raw, text, label) in enumerate(hits):
                    c1, c2 = st.columns([5, 1.4], vertical_alignment="center")
                    c1.markdown(f"{e(raw)} \u2192 **{e(label)}**" + (" (low confidence read)" if dict(scored).get(raw, 1) < 0.85 else ""))
                    c2.button("Review", key=f"rx_use_{i}", on_click=use_line, args=(text,))
                st.caption("Select Review to check a medicine, then add it from the box below.")
            elif lines:
                st.caption("No medicine names were recognised. Check the photo or type the names below.")
            maybe = ocr.find_candidates(scored, {t.lower() for _, t, _ in hits})
            if maybe:
                st.markdown("**Check these. The reader was not sure.**")
                for j, (raw, _text, names, _conf) in enumerate(maybe):
                    cols = st.columns([4] + [1.6] * len(names), vertical_alignment="center")
                    cols[0].markdown(e(raw))
                    for k, n in enumerate(names):
                        cols[k + 1].button(n.title(), key=f"rx_fz_{j}_{k}", on_click=use_line, args=(n,))
                st.caption("Select the name that matches the prescription. Nothing is added until you confirm.")
            if lines:
                st.text_area("Text read from the image", "\n".join(lines), height=140, disabled=True)

elif not os.getenv("PAIRCHECK_ONLINE"):   # on a hosted copy, hide the setup notice
    with st.expander("Read from a prescription image"):
        st.info("Image reading is not installed on this computer. In the terminal, run "
                "`python -m pip install -r requirements-ocr.txt`, then restart the app.")

with st.expander("Add by brand or generic name", expanded=bool(st.session_state.get("med_q"))):
    q = st.text_input("Medicine name", key="med_q",
                      placeholder="e.g. Tegretol, Atchol 10 or Warfarin")
    found, used = B.name_matches(q) if q else ([], "")
    if q and not found:
        st.caption("No match found. Try the generic name or check the spelling.")
    choice = None
    if found:
        if used != q.strip().lower():
            left = [t for t in re.sub(r"[().,;:/\\+-]", " ", q.lower()).split()
                    if t not in used.split() and t not in B._DROP]
            suffix = [t for t in left if re.search(r"[a-z]", t) and not re.fullmatch(r"\d+(\.\d+)?[a-z%]{0,3}", t)]
            if suffix:
                st.warning(f"\u201c{q.strip()}\u201d was not found. Showing \u201c{used.title()}\u201d instead. "
                           "A suffix such as D, M or XR can mean different or extra ingredients, so verify the "
                           "ingredients against the prescription.")
            else:
                st.caption(f"Showing results for \u201c{used.title()}\u201d. Strength and dosage text were ignored.")
        kinds = {t[0] for t in found}

        def match_label(t):
            base = t[2].replace(" (generic name)", "").replace(" (brand)", "")
            return f"{base} ({t[0]})" if len(kinds) > 1 else base

        choice = st.selectbox("Matches", found, format_func=match_label, key="med_pick")
    if choice and choice[0] == "generic":
        st.markdown(f"**{choice[1].title()}** (generic name)")
        st.button("Add to my medicines", key="med_add", on_click=add_brand,
                  args=([choice[1].title()], [choice[1]], None))
    elif choice:
        trade = choice[1]
        variants = B.brand_options(trade)
        idx = 0
        if len(variants) > 1:
            idx = st.radio("More than one medicine uses this brand name. Select the one on the prescription.",
                           list(range(len(variants))), key=f"brand_opt_{trade}",
                           format_func=lambda i: ", ".join(d.title() for d in variants[i]["drugs"])
                           + (f" (also contains {', '.join(variants[i]['unmatched'])})"
                              if variants[i]["unmatched"] else ""))
        v = variants[idx]
        titles = [d.title() for d in v["drugs"]]
        st.markdown(f"**{trade.title()}** contains: {', '.join(titles)}")
        if v["unmatched"]:
            st.warning("Not in the interaction data, so pairs with it cannot be checked: " + ", ".join(v["unmatched"]))
        st.caption("Example product: " + v["example"])
        st.button("Add to my medicines", key="brand_add", on_click=add_brand,
                  args=(titles, v["drugs"], f"{trade.title()}: {', '.join(titles)}"))
    if st.session_state.get("brand_msg"):
        st.caption(st.session_state.brand_msg)

sel = st.multiselect(f"Your medicines (2 to {MAX_DRUGS})", list(opts), max_selections=MAX_DRUGS,
                     placeholder="Search to add a drug", key="sel")
shown = [n["text"] for n in st.session_state.get("notes", [])
         if set(n["drugs"]) <= {opts[x] for x in sel}]
if shown:
    st.caption("Entered as brand names: " + "; ".join(shown))
if st.button("Check all pairs", type="primary"):
    names = list(dict.fromkeys(opts[x] for x in sel))
    st.session_state.checked = names if len(names) >= 2 else "few"
    st.session_state.merged = len(sel) - len(names)
    st.session_state.notes_shown = [n["text"] for n in st.session_state.get("notes", [])
                                    if set(n["drugs"]) <= set(names)]

ck = st.session_state.get("checked")
if ck == "few":
    st.markdown('<div class="empty">Choose at least two different drugs, then select Check all pairs.</div>',
                unsafe_allow_html=True)
elif ck:
    if st.session_state.get("merged"):
        st.caption("Two entries were the same drug and were merged.")
    results(ck, st.session_state.get("notes_shown", []))
else:
    st.markdown('<div class="empty"><b>Pick two to five medicines to begin</b><br>Every pair among them is '
                'checked, and recorded results are listed first.</div>', unsafe_allow_html=True)

st.markdown(f'<div class="foot">{e(DISCLAIMER)}</div>', unsafe_allow_html=True)
