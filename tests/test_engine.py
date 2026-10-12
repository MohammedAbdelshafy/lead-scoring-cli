"""Tests for generic and property-level lead scoring."""
import csv

from lead_scoring import grade, score_property_row, score_row
from lead_scoring.engine import _markets, main


def test_grade_bands():
    assert grade(95) == "Platinum"
    assert grade(85) == "Platinum"
    assert grade(84.9) == "Gold"
    assert grade(70) == "Gold"
    assert grade(55) == "Silver"
    assert grade(54.9) == "Bronze"
    assert grade(0) == "Bronze"


def test_score_row_high_intent():
    row = {"intent": "high", "confidence": "0.9", "contact_channel": "email", "email": "a@b.com"}
    assert 85 <= score_row(row) <= 100


def test_score_row_low_intent():
    row = {"intent": "low", "confidence": "0.1", "contact_channel": "", "email": ""}
    assert score_row(row) < 55


def test_score_row_missing_fields_is_bounded():
    assert 0 <= score_row({}) <= 100


def test_generic_invalid_email_does_not_get_full_email_points():
    good = {"intent": "high", "confidence": "0.9", "contact_channel": "email", "email": "a@b.com"}
    bad = {**good, "email": "not-an-email"}
    assert score_row(good) > score_row(bad)


def test_markets_normalization():
    assert _markets("Dallas / Fort Worth, TX") == {"dallas", "fort", "worth"}
    assert _markets("") == set()
    assert _markets("US") == set()


def test_property_score_rewards_documented_distress_and_equity():
    base = {"address": "123 Sample St", "state": "TX", "zip": "77002"}
    weak = score_property_row(base)
    strong = score_property_row({
        **base,
        "tax_delinquent": "yes",
        "vacant": "true",
        "absentee_owner": "yes",
        "equity_pct": "82",
        "years_owned": "14",
        "phone": "+1 (713) 555-0101",
        "phone_verified": "verified",
    })
    assert strong["property_score"] > weak["property_score"]
    assert "tax_delinquent" in strong["property_signals"]
    assert strong["property_queue"] == "REVIEW_URGENT"


def test_unknown_property_data_never_earns_distress_points():
    missing = score_property_row({})
    negative = score_property_row({
        "tax_delinquent": "no",
        "foreclosure_notice": "no",
        "vacant": "no",
        "absentee_owner": "no",
        "high_equity": "no",
    })
    assert missing["property_score"] == 0
    assert negative["property_score"] == 0
    assert missing["property_missing_signals"]


def test_unverified_contact_does_not_count_as_verified():
    row = {
        "tax_delinquent": "yes",
        "phone": "+1 713 555 0101",
        "email": "owner@example.com",
    }
    scored = score_property_row(row)
    assert "valid_phone" not in scored["property_signals"]
    assert "valid_email" not in scored["property_signals"]
    assert scored["property_queue"] == "CONTACT_ENRICHMENT_REQUIRED"


def test_property_score_cli(tmp_path):
    src = tmp_path / "properties.csv"
    out = tmp_path / "scored.csv"
    with src.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["address", "tax_delinquent", "equity_pct", "phone", "phone_verified"])
        writer.writeheader()
        writer.writerow({
            "address": "1 Test St", "tax_delinquent": "yes", "equity_pct": "80",
            "phone": "+1 713 555 0101", "phone_verified": "verified",
        })
        writer.writerow({"address": "2 Test St", "tax_delinquent": "no", "equity_pct": "10"})
    main(["property-score", str(src), "--out", str(out)])
    with out.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert float(rows[0]["property_score"]) >= float(rows[1]["property_score"])
    assert {"property_signals", "property_missing_signals", "property_queue"} <= set(rows[0])


def test_generic_score_e2e(tmp_path):
    src, out = tmp_path / "leads.csv", tmp_path / "scored.csv"
    with src.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["company", "intent", "confidence", "contact_channel", "email"])
        writer.writeheader()
        writer.writerow({"company": "Acme", "intent": "high", "confidence": "0.9", "contact_channel": "email", "email": "x@acme.com"})
        writer.writerow({"company": "Zed", "intent": "low", "confidence": "0.1", "contact_channel": "", "email": ""})
    main(["score", str(src), "--out", str(out)])
    with out.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert "lead_score" in rows[0] and "grade" in rows[0]
    assert float(rows[0]["lead_score"]) >= float(rows[1]["lead_score"])


def test_match_cli_e2e(tmp_path):
    sellers, buyers, out = tmp_path / "sellers.csv", tmp_path / "buyers.csv", tmp_path / "matches.csv"
    for path, rows in (
        (sellers, [{"id": "S1", "market": "Dallas TX"}]),
        (buyers, [{"company": "BuyCo", "type": "investor", "market": "Dallas", "confidence": "0.8", "contact_channel": "phone"}]),
    ):
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    main(["match", str(sellers), str(buyers), "--out", str(out)])
    with out.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1 and rows[0]["buyer"] == "BuyCo"


def test_report_e2e(tmp_path):
    src = tmp_path / "buyers.csv"
    with src.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["company", "intent", "confidence", "contact_channel", "email"])
        writer.writeheader()
        writer.writerow({"company": "Acme", "intent": "high", "confidence": "0.9", "contact_channel": "email", "email": "x@acme.com"})
    main(["report", str(src)])
    assert (tmp_path / "buyers_scored.csv").exists()
