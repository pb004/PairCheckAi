"""Connects the new front end to the PolyCheck models and data.
The logic is moved from the old app.py. Put these files in THIS folder:
  sev_model.ubj, type_model.ubj, polycheck_meta.joblib   (or polycheck_artifacts.joblib)
  polycheck_lookup.joblib, drug_mechanisms.json, drug_label_mech.json,
  drug_label_interactions.json
"""
import bisect
import json
import os
import re

import joblib
import numpy as np
import streamlit as st
import xgboost as xgb

DEMO_MODE = False
INCLUDE_ALIASES = False     # True adds alias names to the dropdown, but makes it slow
SEV_NAMES = ["Minor", "Moderate", "Major"]
BASE = os.path.dirname(os.path.abspath(__file__))
# Label sentences containing dosing or instruction wording are never shown.
_DOSING = re.compile(r"\b(dose|doses|dosage|dosing|mg|mcg|monitor\w*|avoid\w*|should|recommend\w*|"
                     r"reduc\w*|adjust\w*|titrat\w*|discontinu\w*|contraindicat\w*)\b", re.I)


def _p(name):
    return os.path.join(BASE, name)


def _load_art():
    if all(os.path.exists(_p(n)) for n in ("sev_model.ubj", "type_model.ubj", "polycheck_meta.joblib")):
        art = joblib.load(_p("polycheck_meta.joblib"))
        art["sev_model"] = xgb.Booster()
        art["sev_model"].load_model(_p("sev_model.ubj"))
        art["type_model"] = xgb.Booster()
        art["type_model"].load_model(_p("type_model.ubj"))
        return art
    return joblib.load(_p("polycheck_artifacts.joblib"))


@st.cache_resource(show_spinner="Loading models")
def _data():
    art = _load_art()
    lk = joblib.load(_p("polycheck_lookup.joblib"))
    with open(_p("drug_mechanisms.json")) as f:
        mech = json.load(f)
    with open(_p("drug_label_mech.json")) as f:
        lab = json.load(f)
    labint = {}
    if os.path.exists(_p("drug_label_interactions.json")):
        with open(_p("drug_label_interactions.json")) as f:
            labint = json.load(f)
    known = art["known"].drop_duplicates("pair_key").set_index("pair_key")
    return art, lk, mech, lab, labint, known


def _proba(model, x):
    if isinstance(model, xgb.Booster):
        return model.predict(xgb.DMatrix(x))[0]
    return model.predict_proba(x)[0]


def thresholds():
    art = _data()[0]
    return art["thr_sev"], art["thr_type"]


@st.cache_resource(show_spinner=False)
def drug_options():
    """{label shown in the dropdown: canonical drug name}. Built once and kept in memory."""
    art, lk = _data()[:2]
    opts = {d.title(): d for d in art["fp"]}
    if INCLUDE_ALIASES:
        for k, v in lk["aliases"].items():
            if v in art["fp"] and k not in art["fp"] and k != v:
                opts[f"{k.title()} ({v.title()})"] = v
    return dict(sorted(opts.items()))


def _record_ids(lk, key):
    out, ids = [], lk["record_ids"].get(key) or {}
    if ids.get("db"):
        out.append(f"DrugBank-style table IDs {ids['db'][0]}, {ids['db'][1]}")
    if ids.get("dd"):
        out.append(f"DDInter IDs {ids['dd'][0]}, {ids['dd'][1]}")
    return out


def lookup_pair(a, b):
    _, lk, _, _, _, known = _data()
    key = "|".join(sorted([a, b]))
    if key not in known.index:
        return None
    r = known.loc[key]
    types = list(r["interaction_types"])
    raw = lk["record_ids"].get(key) or {}
    return {"severity": r["Level"], "type": ", ".join(types), "types": types,
            "ids": "; ".join(_record_ids(lk, key)),
            "db_ids": list(raw.get("db") or []), "dd_ids": list(raw.get("dd") or [])}


def predict_pair(a, b):
    """Raw model output. The front end applies the abstention thresholds."""
    art = _data()[0]
    fa, fb = art["fp"][a].astype(int), art["fp"][b].astype(int)
    ea, eb = art["extra"][a], art["extra"][b]
    x = np.hstack([fa + fb, np.abs(fa - fb), ea + eb, np.abs(ea - eb)]).reshape(1, -1)
    ps, pt = _proba(art["sev_model"], x), _proba(art["type_model"], x)
    top = np.argsort(pt)[::-1][:3]
    return {"severity": SEV_NAMES[int(ps.argmax())], "sev_p": float(ps.max()),
            "types": [(art["type_names"][i], float(pt[i])) for i in top]}


def _terms(lk, d):
    return {d} | {k for k, v in lk["aliases"].items() if v == d}


def get_label_sentence(a, b):
    """Shortest complete label sentence that names the other drug, or None."""
    _, lk, _, _, labint, _ = _data()
    best = None
    for src, partner in ((a, b), (b, a)):
        rec = labint.get(src)
        if not rec:
            continue
        pat = re.compile(r"\b(" + "|".join(re.escape(t) for t in _terms(lk, partner)) + r")\b", re.I)
        text = re.sub(r"\s+", " ", rec["text"])
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text):
            m = pat.search(sent)
            if (m and 40 <= len(sent) <= 600 and sent[0].isupper() and sent.endswith(".")
                    and not re.search(r"Table \d|Drug Class", sent) and not _DOSING.search(sent)):
                if best is None or len(sent) < len(best["sentence"]):
                    best = {"sentence": sent, "partner": m.group(0), "set_id": rec["set_id"],
                            "cite": f"FDA label for {src.title()}, set ID {rec['set_id']}"}
                break
    return best


def get_mechanism(drug):
    _, _, mech, lab, _, _ = _data()
    info = mech.get(drug) or {}
    ms = info.get("mechanisms") or []
    if ms:
        txt = "; ".join(dict.fromkeys(m["text"] for m in ms))[:300]
        return {"text": txt, "source": f"ChEMBL {info.get('chembl_id')}", "chembl_id": info.get("chembl_id")}
    l = lab.get(drug)
    if l:
        return {"text": l["text"], "source": f"FDA label, set ID {l['set_id']}", "set_id": l["set_id"]}
    return None


def other_examples(n=5):
    """A few of the interaction types grouped under 'Other', read from other_types.json (optional)."""
    path = _p("other_types.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        items = json.load(f)
    return [x if isinstance(x, str) else x.get("type", "") for x in items][:n]


@st.cache_resource(show_spinner=False)
def _brands():
    path = _p("brand_map.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def brands_available():
    return bool(_brands())


_DROP = {"tab", "tabs", "tablet", "tablets", "cap", "caps", "capsule", "capsules", "syp", "syrup", "inj",
         "injection", "drops", "oint", "ointment", "cream", "gel", "susp", "od", "bd", "tds", "qid", "hs",
         "sos", "bid", "tid", "daily", "once", "twice"}


def brand_names():
    """All brand (trade) names, sorted, for the searchable dropdown."""
    return sorted(_brands())


def brand_matches(query, limit=10):
    """(matches, text used). Understands prescription-style input such as 'Tab. Atchol 10 mg OD':
    it drops words from the end until a brand name matches, and ignores spaces and hyphens as a last try."""
    b = _brands()
    toks = [t for t in re.sub(r"[().,;:/\\+-]", " ", query.lower()).split() if t not in _DROP]
    for n in range(len(toks), 0, -1):
        q = " ".join(toks[:n])
        if len(q) < 2:
            continue
        hit = ([q] if q in b else []) + sorted(k for k in b if k.startswith(q) and k != q)[:limit]
        if not hit:
            qn = q.replace(" ", "")
            hit = sorted(k for k in b if k.replace(" ", "").replace("-", "").startswith(qn))[:limit]
        if hit:
            return hit[:limit], q
    return [], ""


def brand_options(trade):
    """[{"drugs": [...], "unmatched": [...], "example": str, "n": int}, ...] for one brand name."""
    return _brands().get(trade, [])


@st.cache_resource(show_spinner=False)
def _index():
    """Sorted name lists, built once, so prefix searches take microseconds instead of scanning every name."""
    art, lk = _data()[:2]
    b = _brands()
    return {"fp": sorted(art["fp"]), "alias": sorted(lk["aliases"]), "brands": sorted(b),
            "nospace": sorted((k.replace(" ", "").replace("-", ""), k) for k in b)}


def _prefix(keys, q):
    lo = bisect.bisect_left(keys, q)
    return keys[lo:bisect.bisect_left(keys, q + "\uffff", lo)]


def name_matches(query, limit=10):
    """Generic names, alias names and brand names that match typed or pasted text.
    Returns ([(kind, key, label), ...], text used). Drops words from the end until something matches."""
    art, lk = _data()[:2]
    fp, alias, b, ix = art["fp"], lk["aliases"], _brands(), _index()
    toks = [t for t in re.sub(r"[().,;:/\\+-]", " ", query.lower()).split() if t not in _DROP]
    for n in range(len(toks), 0, -1):
        q = " ".join(toks[:n])
        if len(q) < 2:
            continue
        gen = ([q] if q in fp else []) + [d for d in _prefix(ix["fp"], q) if d != q]
        out = [("generic", d, f"{d.title()} (generic name)") for d in gen[:limit]]
        al = [a for a in _prefix(ix["alias"], q) if alias[a] in fp and alias[a] not in gen and a not in fp][:limit]
        out += [("generic", alias[a], f"{a.title()} \u2192 {alias[a].title()} (generic name)") for a in al]
        brands = ([q] if q in b else []) + [k for k in _prefix(ix["brands"], q) if k != q]
        if not (gen or al or brands):
            qn, ns = q.replace(" ", ""), ix["nospace"]
            lo = bisect.bisect_left(ns, (qn,))
            brands = sorted(k for _, k in ns[lo:bisect.bisect_left(ns, (qn + "\uffff",), lo)])
        out += [("brand", k, f"{k.title()} (brand)") for k in brands[:limit]]
        if out:
            return out[:limit], q
    return [], ""

def stats():
    """Headline numbers for the opening screen. Loads the models if they are not loaded yet."""
    art, _, _, _, _, known = _data()
    return {"drugs": len(art["fp"]), "pairs": len(known), "brands": len(_brands())}
