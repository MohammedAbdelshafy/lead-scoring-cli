---
type: repository
status: active
owner_repo: MohammedAbdelshafy/lead-scoring-cli
product_name: Lead Priority Check
source_of_truth: https://github.com/MohammedAbdelshafy/lead-scoring-cli
---

# Lead Priority Check CONTEXT

One job: help a person sort supplied leads using a visible scoring rule and identify possible seller-to-buyer matches.

## Inputs
- Commands and scoring rules: [README](README.md)
- Implementation: [lead_scoring](lead_scoring/)
- Tests: [tests](tests/)

## Process
1. Read the supplied CSV and declared inputs.
2. Score records using the documented rubric.
3. Match seller opportunities to buyer criteria based on the supported fields.
4. Write the scored/matched output to a separate file.
5. Explain that ranking is a screening aid, not a guarantee.

## Output
A scored CSV and/or a match report based on the input records.

## Check
Run the repository tests. Use a synthetic dataset to check the scoring bounds, grade thresholds, missing data and seller/buyer matching. Do not claim a match proves a buyer will purchase.
