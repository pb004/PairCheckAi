"""Reads printed text from a prescription image on this computer and finds lines that name a medicine.
The image is not uploaded anywhere and not saved. Handwriting is not supported."""
import io
import re

import streamlit as st

import backend as B

_LEAD = re.compile(r"^\s*(?:\d{1,2}\s*[.)\-:]\s*|rx\s*[:.]?\s*)", re.I)
_FORM = re.compile(r"^(?:t|c|tab|tabs|cap|caps|syp|syr|inj)\b\.?\s*", re.I)


def _flavour():
    """'new' = the rapidocr package (works on newer Python), 'old' = rapidocr-onnxruntime (Python 3.12 or older)."""
    try:
        from rapidocr import RapidOCR  # noqa: F401
        return "new"
    except Exception:
        pass
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return "old"
    except Exception:
        return None


def available():
    return _flavour() is not None


@st.cache_resource(show_spinner=False)
def _engine():
    if _flavour() == "new":
        from rapidocr import RapidOCR
    else:
        from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


@st.cache_data(show_spinner=False, max_entries=6)
def read_scored(data):
    """Image bytes -> [(text line, lowest reading confidence 0-1)], top to bottom."""
    import numpy as np
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if max(im.size) > 1800:
        im.thumbnail((1800, 1800))
    img = np.array(im)
    if _flavour() == "new":
        out = _engine()(img)
        result = list(zip(out.boxes, out.txts, out.scores)) if out.boxes is not None else []
    else:
        result, _ = _engine()(img)
    boxes = []
    for box, text, _score in result or []:
        ys, xs = [p[1] for p in box], [p[0] for p in box]
        boxes.append((sum(ys) / 4, min(xs), max(ys) - min(ys), text, float(_score)))
    if not boxes:
        return []
    boxes.sort()
    tol = 0.6 * sorted(b[2] for b in boxes)[len(boxes) // 2]
    groups, line_y = [], None
    for yc, x, _h, text, conf in boxes:
        if line_y is None or abs(yc - line_y) > tol:
            groups.append([])
            line_y = yc
        groups[-1].append((x, text, conf))
    return [(" ".join(t for _, t, _ in sorted(g)), min(c for _, _, c in g)) for g in groups]


def read_lines(data):
    return [t for t, _ in read_scored(data)]


def clean_line(line):
    """Drops list numbers and form words, for example '2. Cap. Tegretol 200 mg BD' -> 'Tegretol 200 mg BD'."""
    return _FORM.sub("", _LEAD.sub("", line.strip())).strip()


@st.cache_data(show_spinner=False, max_entries=20)
def find_medicines(lines):
    """[(original line, cleaned line, name shown)] for lines that start with a known medicine name.
    Only exact name matches are listed, to avoid picking up words like patient or date."""
    found, seen = [], set()
    for raw in lines:
        text = clean_line(raw)
        if len(text) < 3 or text.lower() in seen:
            continue
        matches, used = B.name_matches(text)
        if not (matches and used):
            continue
        kind, key, label = matches[0]
        if key == used or label.lower().startswith(used + " \u2192"):
            seen.add(text.lower())
            found.append((raw, text, label.replace(" (generic name)", "").replace(" (brand)", "")))
    return found


_STOP = {"patient", "name", "age", "date", "dr", "mbbs", "md", "clinic", "hospital", "signature", "regn", "reg",
         "phone", "address", "sex", "weight", "diagnosis", "advice", "follow", "review", "mob", "male", "female"}
_UNIT = re.compile(r"^\d+(\.\d+)?(mg|mcg|ml|gm|g|iu|%)?$", re.I)
_FIX = str.maketrans({"1": "l", "0": "o", "5": "s", "|": "l"})


@st.cache_resource(show_spinner=False)
def _keys():
    return list(B._data()[0]["fp"]) + list(B._brands())


@st.cache_data(show_spinner=False, max_entries=300)
def suggest(text, limit=3):
    """Closest known generic or brand names for a line the reader was not sure about (catches Atcho1, Tegretal)."""
    try:
        from rapidfuzz import fuzz, process
    except Exception:
        return []
    toks = [t for t in re.sub(r"[().,;:/\\+-]", " ", clean_line(text).lower()).split()
            if t not in B._DROP and not _UNIT.match(t)]
    if not toks or toks[0] in _STOP or len(toks[0]) < 4:
        return []
    best = {}
    for cand in {toks[0], toks[0].translate(_FIX), " ".join(toks[:2])}:
        cutoff = 85 if len(cand) <= 5 else 80
        for name, score, _ in process.extract(cand, _keys(), scorer=fuzz.ratio, limit=limit, score_cutoff=cutoff):
            best[name] = max(best.get(name, 0), score)
    return sorted(best, key=lambda n: -best[n])[:limit]


def find_candidates(scored, exact_texts):
    """[(original line, cleaned line, [suggested names], reading confidence)] for lines with no exact match."""
    out = []
    for raw, conf in scored:
        text = clean_line(raw)
        if text.lower() in exact_texts:
            continue
        names = suggest(text)
        if names:
            out.append((raw, text, names, conf))
    return out
