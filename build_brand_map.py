"""Run from this folder:
    python build_brand_map.py "D:\\path\\to\\CommonDrugCodesForIndia_FlatFilePackage"
Builds brand_map.json: brand (trade) names -> generic ingredients that exist in PairCheck AI's drug list.
Read License.txt in the package before you use or share the output."""
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

import backend as B

folder = sys.argv[1] if len(sys.argv) > 1 else "."
art, lk = B._data()[:2]
ours, aliases = set(art["fp"]), lk["aliases"]
SALTS = set("""hydrochloride hydrobromide mesylate mesilate sodium potassium calcium magnesium sulfate sulphate
phosphate maleate tartrate bitartrate succinate besylate besilate acetate citrate fumarate nitrate tosylate
disodium dihydrate monohydrate trihydrate anhydrous hydrate hemihydrate hcl dipropionate valerate propionate
furoate bromide chloride lactate gluconate oxalate pamoate stearate palmitate decanoate enanthate cypionate
benzoate hemifumarate dimesylate medoxomil axetil hyclate trometamol tromethamine embonate napsylate
mononitrate dinitrate sesquihydrate micronised micronized dihydrochloride proxetil pivoxil etabonate disoproxil
cilexetil diethylamine dimeglumine meglumine erbumine lysine arginine olamine monosodium dipotassium hydrochloride""".split())


def read(name):
    with open(os.path.join(folder, name), encoding="utf-8-sig", errors="replace", newline="") as f:
        rows = list(csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
    head = [h.strip() for h in rows[0]]
    return [dict(zip(head, r)) for r in rows[1:] if r]


def to_ours(name):
    words = re.sub(r"\(.*?\)", " ", name.lower()).replace(",", " ").split()
    while words:
        cand = " ".join(words)
        if cand in ours:
            return cand
        if aliases.get(cand) in ours:
            return aliases[cand]
        if len(words) > 1 and words[-1] in SALTS:
            words = words[:-1]
            continue
        break
    return None


sub = {r["Identifier"]: r["Substance Name"] for r in read("SubstanceMaster.txt")}
gen = {r["Identifier"]: [s for s in r["Substance Identifier"].split("+") if s] for r in read("GenericMaster.txt")}
prod = {r["Identifier"]: r["Product Name"].strip() for r in read("ProductMaster.txt")}
sub_to_ours = {i: to_ours(n) for i, n in sub.items()}

options = defaultdict(Counter)       # trade name -> Counter of (matched, unmatched) option
example = {}
unmatched_brands = Counter()
for b in read("BrandMaster.txt"):
    trade = prod.get(b["Product Identifier"])
    sids = gen.get(b["Generic Identifier"], [])
    if not trade or not sids:
        continue
    matched = tuple(sorted({sub_to_ours.get(s) for s in sids if sub_to_ours.get(s)}))
    unmatched = tuple(sorted({sub.get(s, s) for s in sids if not sub_to_ours.get(s)}))
    for u in unmatched:
        unmatched_brands[u] += 1
    if matched:
        key = trade.lower()
        options[key][(matched, unmatched)] += 1
        example.setdefault((key, matched, unmatched), b["Brand Name"])

out = {}
for trade, ctr in options.items():
    out[trade] = [{"drugs": list(m), "unmatched": list(u), "example": example[(trade, m, u)], "n": n}
                  for (m, u), n in ctr.most_common()]
with open("brand_map.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)

matched_subs = {v for v in sub_to_ours.values() if v}
print(f"\nSubstances in the ABDM file: {len(sub)}; matched to your drug list: {sum(bool(v) for v in sub_to_ours.values())}")
print(f"Your drugs that have at least one Indian brand: {len(matched_subs)} of {len(ours)}")
print(f"Brand (trade) names saved to brand_map.json: {len(out)}")
print(f"  with more than one possible meaning: {sum(len(v) > 1 for v in out.values())}")
print(f"  combination products (2 or more of your drugs): {sum(any(len(o['drugs']) > 1 for o in v) for v in out.values())}")
print("\nSubstances with many brands that did not match your drug list (top 25):")
for name, n in unmatched_brands.most_common(25):
    print(f"  {n:5d}  {name}")
print("\nSpot check of well-known brand names:")
for t in ["Tegretol", "Ecosprin", "Althrocin", "Dolo", "Crocin", "Combiflam", "Xarelto", "Prozac", "Coumadin",
          "Flagyl", "Uniwarfin", "Warf", "Zyrtec", "Brufen", "Glycomet", "Augmentin", "Pan", "Rantac"]:
    hit = out.get(t.lower())
    if hit:
        print(f"  {t}: " + " | ".join(f"{', '.join(o['drugs'])} (x{o['n']})" for o in hit[:3]))
    else:
        near = [k for k in out if k.startswith(t.lower())][:3]
        print(f"  {t}: not found" + (f"; similar: {', '.join(near)}" if near else ""))
print("\nSaved brand_map.json. Read License.txt before using it in your project or repository.")
