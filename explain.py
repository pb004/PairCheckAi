"""Explanations: fixed plain-language meaning per type, plus an optional AI summary
that is only requested when a label sentence exists and is checked before display."""
import os
import re
import streamlit as st

TYPE_MEANING = {
    "serum concentration": "May change the blood level of one or both drugs (the record does not state whether higher or lower).",
    "metabolism": "May change how quickly one of the drugs is broken down by the body.",
    "risk or severity of adverse effects": "May increase the risk or severity of side effects.",
    "QTc-prolonging activities": "May add to effects on heart rhythm (QT interval prolongation).",
    "therapeutic efficacy": "May change how well one of the drugs works.",
    "central nervous system depressant (CNS depressant) activities": "May increase sedation and slowing of the nervous system.",
    "hypoglycemic activities": "May increase blood-sugar-lowering effects.",
    "hypotensive activities": "May increase blood-pressure-lowering effects.",
    "anticoagulant activities": "May change the blood-thinning effect, which can affect bleeding risk.",
    "absorption": "May change how much of a drug is absorbed.",
    "risk or severity of QTc prolongation": "May increase the risk of heart rhythm changes (QTc prolongation).",
    "immunosuppressive activities": "May increase immune-suppressing effects.",
    "hypokalemic activities": "May increase potassium-lowering effects.",
    "excretion rate of higher serum level": "May change how fast a drug is cleared, affecting its blood level.",
    "antihypertensive activities": "May increase blood-pressure-lowering effects.",
    "bradycardic activities": "May increase slowing of the heart rate.",
    "serotonergic activities": "May increase serotonergic effects.",
    "vasoconstricting activities": "May increase blood-vessel-narrowing effects.",
    "bronchodilatory activities": "May change airway-widening (bronchodilator) effects.",
    "nephrotoxic activities": "May increase the risk of kidney toxicity.",
    "anticholinergic activities": "May increase anticholinergic effects.",
    "neuroexcitatory activities": "May increase nervous-system excitation.",
    "sedative activities": "May increase sedative effects.",
    "Other": "A less common interaction category; no general description is available.",
}
_LOWER = {k.lower(): v for k, v in TYPE_MEANING.items()}


def type_meaning(t):
    return _LOWER.get(t.lower(), "No general description is available.")


SYSTEM = (
    "You rewrite one drug label sentence for a student audience. Use ONLY the facts in the "
    "provided source text. Add no new facts, mechanisms, drug names, numbers, doses or advice. "
    "Say 'may' and 'can', never 'will'. Write at most two plain sentences. "
    "Never say a combination is safe or tell the reader what to do. "
    "If the source does not support a clear statement, reply with exactly: NONE"
)
BANNED = re.compile(r"\d|\b(safe|avoid|should|must|dose|dosage|mg|stop|will|recommend\w*)\b", re.I)


def _key():
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return os.getenv("ANTHROPIC_API_KEY")


@st.cache_data(show_spinner=False)
def ai_summary(a, b, rtype, severity, sentence, cite, mech_a, mech_b):
    """Returns the summary text, or None when it cannot be shown safely."""
    key = _key()
    if not key or not sentence:
        return None
    src = (f"Drug A: {a}\nDrug B: {b}\nRecorded type: {rtype}\nRecorded severity: {severity}\n"
           f"Label sentence ({cite}): {sentence}\n"
           f"Mechanism of {a}: {mech_a or 'not available'}\n"
           f"Mechanism of {b}: {mech_b or 'not available'}")
    try:
        import anthropic
        r = anthropic.Anthropic(api_key=key).messages.create(
            model=os.getenv("PAIRCHECK_MODEL", "claude-sonnet-5-5"), max_tokens=200,
            system=SYSTEM, messages=[{"role": "user", "content": src}])
        text = r.content[0].text.strip()
    except Exception:
        return None
    named = a.lower() in text.lower() or b.lower() in text.lower()
    if text == "NONE" or len(text) > 450 or BANNED.search(text) or not named:
        return None
    return text
