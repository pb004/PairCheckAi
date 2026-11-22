"""Clickable links to the original records, and the small 'Other' explainer card.
If a website changes its address, edit the URL templates below."""
import html
import re

e = html.escape
DRUGBANK = "https://go.drugbank.com/drugs/{}"
DDINTER = "https://ddinter2.scbdd.com/server/drug-detail/{}/"   # pattern not confirmed: open one link to check
# If this ChEMBL link fails, try one of these instead and keep the one that opens:
#   "https://www.ebi.ac.uk/chembl/compound_report_card/{}/"
#   "https://identifiers.org/chembl.compound:{}"
CHEMBL = "https://www.ebi.ac.uk/chembl/explore/compound/{}"
DAILYMED = "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={}"
_UUID = re.compile(r"[0-9a-fA-F-]{36}")


def link(template, ident, text=None):
    url = template.format(ident)
    return (f'<a href="{e(url, quote=True)}" target="_blank" rel="noopener noreferrer">'
            f'{e(text or str(ident))}</a>')


def record_ids_html(db_ids, dd_ids):
    db = [link(DRUGBANK, i) if re.fullmatch(r"DB\d{5}", str(i)) else e(str(i)) for i in db_ids or []]
    dd = [link(DDINTER, i) if re.fullmatch(r"DDInter\d+", str(i)) else e(str(i)) for i in dd_ids or []]
    parts = []
    if db:
        parts.append("DrugBank-style table IDs " + ", ".join(db))
    if dd:
        parts.append("DDInter IDs " + ", ".join(dd))
    return "; ".join(parts)


def cite_html(cite, set_id):
    """'FDA label for X, set ID abc' with the set ID as a DailyMed link."""
    if not set_id or not _UUID.fullmatch(str(set_id)):
        return e(cite)
    return e(cite.rsplit("set ID", 1)[0]) + "set ID " + link(DAILYMED, set_id)


def mechanism_source_html(m):
    if m.get("chembl_id") and re.fullmatch(r"CHEMBL\d+", str(m["chembl_id"])):
        return "Source: " + link(CHEMBL, m["chembl_id"], "ChEMBL " + str(m["chembl_id"]))
    if m.get("set_id") and _UUID.fullmatch(str(m["set_id"])):
        return "Source: FDA label, set ID " + link(DAILYMED, m["set_id"])
    return "Source: " + e(m["source"])


def has_other(types):
    names = [t[0] if isinstance(t, (tuple, list)) else t for t in types or []]
    return "Other" in names


def other_body(examples):
    text = ("A group of less common interaction types from the source data. Each has fewer than 100 "
            "recorded pairs, so they are combined into one class.")
    if examples:
        text += " A few of them: " + ", ".join(examples) + "."
    return f"<div>{e(text)}</div>"
