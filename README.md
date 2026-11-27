# PairCheck AI

**A lookup-first drug-pair interaction checker that separates recorded facts from model estimates.**

**Live app:** [https://paircheckai.streamlit.app](https://paircheckai.streamlit.app)

> **Research and educational prototype.** PairCheck AI does not confirm that an interaction will or will not occur in any individual, provide dosing or personal medical advice, or replace professional medical assessment. It has not been clinically validated. Combinations of three or more drugs are not assessed, and a missing result never means a combination is safe.

**Developed by:** Prameet Basu Ray Chaudhury  

---

## What it does

Drug–drug interaction databases only answer for the pairs they list, and a missing entry can be mistaken for safety. In the data used here, only **34,370** of the **625,521** possible pairs among **1,119 drugs** have both a recorded interaction type and a known severity.

PairCheck AI handles each pair in one of three clearly labelled ways:

| Result | Meaning |
|---|---|
| **Recorded** | The pair is found in the source data. Its stored severity, interaction type, record IDs and available FDA label sentence are displayed. No model is used. |
| **Predicted** | The pair is not recorded. Two XGBoost models estimate severity and interaction type from chemical structure. The result is clearly marked as a low-confidence prediction. |
| **Not enough information** | The model confidence does not meet the required threshold. The application abstains from providing a prediction. |

### How a query works

1. The two drug names are sorted into one order-independent key.
2. The key is looked up in the recorded-pairs table. If found, that is the answer.
3. If not found, a 2,398-feature vector is built from the two drugs' chemical structures using RDKit, and both XGBoost models are run.
4. Severity is shown only if its confidence is at least **0.75**; interaction type only if its confidence is at least **0.60**.
5. If neither threshold is met, the tool shows "Not enough information".
6. Every result also shows a plain-language meaning, drug mechanisms (when available) and the disclaimer.

### Features

- Single-pair checking and a **multi-drug view** (2 to 5 drugs, up to 10 pairs, listed recorded-first, with Major before Moderate).
- **Printable results sheet.**
- **Indian brand-name search** using the ABDM / NRCeS Common Drug Codes for India (1,000 of the 1,119 drugs have at least one Indian brand; 60,460 brand names saved). The user confirms the final generic ingredient list.
- **Preliminary prescription image reading (OCR)** for printed and handwritten prescriptions; extracted names require user confirmation.
- Clickable DrugBank, DDInter, ChEMBL and DailyMed record IDs.
- Plain-language explanations for interaction types, with rare types grouped as "Other".

---

## Results summary

| Evaluation | Severity macro-F1 | Interaction-type top-3 accuracy |
|---|---:|---:|
| Majority-class baseline | About 0.28 | – |
| S2: One drug unseen | 0.626 ± 0.010 (5 seeds) | 0.891 |
| S3: Both drugs unseen | 0.435 ± 0.032 (5 seeds) | 0.772 |

- Under S2, Major-interaction recall is **0.588 ± 0.031**, and **57.0%** of true Major pairs are withheld by the 0.75 confidence threshold. Therefore, the model can miss serious interactions.
- At the 0.75 severity threshold, the tool answers 56.1% of pairs, and macro-F1 on those answered pairs is 0.663 (0.567 across all pairs).
- A matching FDA label sentence was found for 4 of 300 sampled recorded pairs (approximately 1.3%).
- The tool has been functionally tested on selected workflows but **has not been clinically validated**.

Full methods, tables and figures are available in the project report.

---

## Run it locally

```bash
git clone https://github.com/pb004/PairCheckAi.git
cd PairCheckAi

python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
streamlit run app_multi.py
```

**Note:** The repository must contain the required `.joblib`, `.ubj` model files and JSON data files. The application will not start without its required artefacts.

---

## Repository contents

| File | Purpose |
|---|---|
| `app_multi.py` | Streamlit interface (multi-drug view) |
| `backend.py` | Core logic: `drug_options`, `lookup_pair`, `predict_pair`, `get_label_sentence`, `get_mechanism` |
| `explain.py` | Plain-language meaning texts for interaction types |
| `ocr.py` | Prescription-image text extraction |
| `build_brand_map.py` | Builds `brand_map.json` from ABDM flat files |
| `brand_map.json` | Indian brand-name to generic ingredient mapping |
| `sev_model.ubj` | Trained XGBoost severity model |
| `type_model.ubj` | Trained XGBoost interaction-type model |
| `polycheck_artifacts.joblib` | Stored molecular features and model artefacts |
| `polycheck_lookup.joblib` | Recorded-pair lookup table |
| `polycheck_meta.joblib` | Model and application metadata |
| `polycheck_clean_pairs.csv` | Cleaned interaction-pair data |
| `polycheck_drugs_with_fp.csv` | Drug feature information |
| `drug_smiles.csv` | Drug SMILES structures |
| `drug_label_interactions.json` | FDA label interaction information |
| `drug_label_mech.json` | Drug-label mechanism information |
| `drug_mechanisms.json` | Drug mechanism text |
| `other_types.json` | Examples for the "Other" interaction-type group |
| `severity_baseline_results.csv` | Baseline comparison results |
| `intro.py` | Introduction-related application content |
| `links.py` | External resource links |
| `.streamlit/` | Streamlit configuration |
| `requirements.txt` | Python dependencies |

---

## Data sources

| Source | Used for |
|---|---|
| DDInter | Severity of recorded pairs |
| DrugBank-derived interaction table | Interaction types and descriptions |
| PubChem | Chemical structures (SMILES) |
| ChEMBL | Drug mechanism information |
| openFDA drug labels | Label sentences and mechanism information |
| ABDM / NRCeS Common Drug Codes for India (release of 31 August 2026) | Indian brand-name mapping |

The datasets used in this project were obtained from publicly accessible sources and cleaned and preprocessed for research and educational purposes. Each source remains subject to its own licence and terms of use. No ownership of the original source data is claimed.

---

## Limitations

- Predictions are weakest when both drugs are unseen (severity macro-F1 approximately 0.435).
- Confident severity predictions are concentrated in the Moderate class (88% in a 3,000-pair analysis).
- 187,674 pairs have a recorded type but no known severity; these are predicted rather than treated as complete recorded entries.
- Combined effects of three or more drugs are not assessed.
- Brand-name coverage is partial.
- OCR performance is preliminary and has not been systematically evaluated across handwriting styles and image quality.
- The plain-language texts were not reviewed by a pharmacist, and no formal user study was carried out.
- The application has not undergone clinical validation.

---

## Tech stack

Python, Streamlit, XGBoost, scikit-learn, RDKit, pandas, NumPy, joblib and JSON.

---

## Citation

If you refer to this project:

> Basu Ray Chaudhury P. *PairCheck AI: A lookup-first drug-pair interaction checker.* 2026. GitHub repository: https://github.com/pb004/PairCheckAi

---

## Licence

The original code developed for PairCheck AI is made available for educational and research purposes. Third-party datasets and derived data remain subject to the licences and terms of their respective providers.

For permissions relating to the reuse or redistribution of third-party data, please refer to the original sources.
