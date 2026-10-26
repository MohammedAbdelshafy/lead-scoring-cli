# Lead Priority Check

A clear, rules-based tool for ranking the real-estate leads you already have and matching seller records to buyer criteria. The scoring rubric is visible and configurable.
It ranks supplied records. It does not find buyers, verify every underlying fact, or promise conversions.

Customer-facing name: **Lead Priority Check**. The repository, package and command identifiers remain unchanged.

## Install

```bash
pip install lead-scoring-cli
```

## Usage

```bash
# Score a lead CSV (adds lead_score 0-100 + Platinum/Gold/Silver/Bronze grade)
lead-score score leads.csv --out scored.csv

# Score + print a daily summary report
lead-score report buyers.csv

# Match sellers to the best buyers by market + type
lead-score match sellers.csv buyers.csv --out matches.csv
```

Or without installing: `python -m lead_scoring score leads.csv`.

## Scoring rubric

Weights sum to ~1.0 and are plain config in `lead_scoring/engine.py` (`WEIGHTS`, `INTENT`):

| signal            | weight |
|-------------------|--------|
| intent            | 0.40   |
| confidence        | 0.30   |
| has_channel       | 0.15   |
| domain_ok         | 0.15   |

Grades: Platinum ≥ 85, Gold ≥ 70, Silver ≥ 55, else Bronze.

## What it does not do

No guaranteed ROI, revenue, or leads. It ranks the leads you already have with a
transparent rubric — it does not find buyers for you or promise conversions.

## License

MIT — Mohammed Abdelshafy.
