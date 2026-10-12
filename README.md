# Lead Scoring CLI

Transparent, dependency-free lead scoring + seller→buyer matching for real-estate wholesalers and agencies.

**New in 0.2.0:** property-level seller research scoring with signal-level explanations and explicit missing-data reporting. This is a transparent screening rubric, not a prediction of seller intent and not a substitute for DNC/suppression checks or call eligibility.

## Install

\`\`\`bash
pip install lead-scoring-cli
\`\`\`

## Usage

\`\`\`bash
# Existing generic/business lead score (unchanged)
lead-score score leads.csv --out scored.csv

# Property distress/equity/contact research score
lead-score property-score properties.csv --out property-ranked.csv

# Daily generic lead report
lead-score report buyers.csv

# Match sellers to the best buyers by market + type
lead-score match sellers.csv buyers.csv --out matches.csv
\`\`\`

Or without installing: \`python -m lead_scoring property-score properties.csv --out property-ranked.csv\`.

## Property scoring signals

The property scorer awards points only for explicit affirmative evidence. Missing or unrecognized inputs earn no points and are listed separately.

| Signal | Points | Minimum meaning |
|---|---:|---|
| Foreclosure notice | 22 | Explicit notice/status signal supplied |
| Tax delinquent | 18 | Explicit delinquent tax status |
| Probate/inherited | 12 | Explicit probate/inherited signal |
| Vacant | 12 | Explicit vacancy signal |
| High equity | 10 | Equity ≥70% or ratio ≥0.70 |
| Code violation | 8 | Explicit open/active violation |
| Absentee owner | 7 | Explicit absentee/out-of-state indicator |
| Long ownership | 6 | Ownership ≥10 years |
| Verified phone | 3 | Plausible phone format plus provider status marked verified/valid |
| Verified email | 2 | Valid email syntax plus provider status marked verified/valid |

The maximum score is 100. Grades use Platinum ≥85, Gold ≥70, Silver ≥55, otherwise Bronze. This initial rubric is rule-based and **not statistically calibrated**. Evaluate against actual conversation, offer and contract outcomes before describing it as predictive.

## Output fields

- \`property_score\`, \`property_grade\`: research score and grade.
- \`property_signals\`: semicolon-separated signals that earned points.
- \`property_missing_signals\`: distress/equity signals missing or not understood.
- \`property_queue\`: \`REVIEW_URGENT\`, \`PRIORITY_RESEARCH\`, \`STANDARD_RESEARCH\`, \`CONTACT_ENRICHMENT_REQUIRED\`, or \`LOW_EVIDENCE\`.
- \`property_score_version\`: rubric version for audit/reproducibility.
- \`property_score_note\`: explains the score is research priority only.

**Important:** \`REVIEW_URGENT\` means review the underlying source and dates promptly, not that the owner is motivated and not that the property should automatically be called. The scorer never authorizes calls, sends outreach, or writes to a CRM/lead database.

## Existing generic rubric

The generic \`score\` command remains unchanged for compatibility. It uses intent (0.40), confidence (0.30), channel presence (0.15) and email-field quality (0.15). It is a simple ranker, not a real-estate distress model.

## What it does not do

- No guaranteed ROI, lead quality or conversion prediction.
- No live property-data feed, skip tracing, ownership lookup or comparable-sale verification.
- No automatic outreach or suppression decision.
- No commitment of owner-level records to GitHub.
- Property comps, tax/legal status and contact verification remain operator responsibilities.

## License

MIT — Mohammed Abdelshafy.
