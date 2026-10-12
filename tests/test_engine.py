"""Tests for the lead scoring CLI — stdlib only."""
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
    r = {"intent": "high", "confidence": "0.9", "contact_channel": "email", "email": "a@b.com"}
    assert 85 <= score_row(r) <= 100


def test_score_row_low_intent():
    r = {"intent": "low", "confidence": "0.1", "contact_channel": "", "email": ""}
    assert score_row(r) < 55


def test_score_row_defaults_missing_fields():
    assert 0 <= score_row({}) <= 100


def test_markets_normalization():
    assert _markets("Dallas / Fort Worth, TX") == {"dallas", "fort", "worth"}
    assert _markets("") == set()
    assert _markets("US") == set()


def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def test_cli_score_e2e(tmp_path):
    src = tmp_path / "leads.csv"
    _write_csv(str(src), [
        {"company": "Acme", "intent": "high", "confidence": "0.9",
         "contact_channel": "email", "email": "x@acme.com"},
        {"company": "Zed", "intent": "low", "confidence": "0.1",
         "contact_channel": "", "email": ""},
    ])
    out = tmp_path / "scored.csv"
    main(["score", str(src), "--out", str(out)])
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert len(rows) == 2
    assert "lead_score" in rows[0] and "grade" in rows[0]
    assert float(rows[0]["lead_score"]) >= float(rows[1]["lead_score"])
    assert rows[0]["grade"] == "Platinum"


def test_property_score_rewards_distress_and_equity_signals():
    weak = score_property_row({"address": "123 Sample St", "state": "TX"})
    strong = score_property_row({
        "address": "123 Sample St", "state": "TX",
        "tax_delinquent": "yes", "vacant": "true", "absentee_owner": "yes",
        "equity_pct": "82", "years_owned": "14",
        "phone": "+1 (713) 555-0101", "phone_verified": "verified",
    })
    assert strong["property_score"] > weak["property_score"]
    assert "tax_delinquent" in strong["property_signals"]
    assert strong["property_queue"] == "REVIEW_URGENT"


def test_unknown_property_data_never_earns_distress_points():
    missing = score_property_row({})
    negative = score_property_row({
        "tax_delinquent": "no", "foreclosure_notice": "no", "vacant": "no",
        "absentee_owner": "no", "high_equity": "no",
    })
    assert missing["property_score"] == 0
    assert negative["property_score"] == 0
    assert missing["property_missing_signals"]


def test_high_equity_boolean_and_percent_units():
    assert "high_equity" in score_property_row({"high_equity": "yes"})["property_signals"]
    assert "high_equity" not in score_property_row({"equity_pct": "0.8%"})["property_signals"]
    assert "high_equity" in score_property_row({"equity_pct": "0.8"})["property_signals"]


def test_unverified_contact_does_not_get_contact_points():
    row = {"tax_delinquent": "yes", "phone": "+1 713 555 0101", "email": "owner@example.com"}
    scored = score_property_row(row)
    assert "valid_phone" not in scored["property_signals"]
    assert "valid_email" not in scored["property_signals"]
    assert scored["property_queue"] == "CONTACT_ENRICHMENT_REQUIRED"


def test_property_score_cli(tmp_path):
    src, out = tmp_path / "properties.csv", tmp_path / "ranked.csv"
    _write_csv(str(src), [
        {"address": "1 Test St", "tax_delinquent": "yes", "equity_pct": "80",
         "phone": "+1 713 555 0101", "phone_verified": "verified"},
        {"address": "2 Test St", "tax_delinquent": "no", "equity_pct": "10",
         "phone": "", "phone_verified": ""},
    ])
    main(["property-score", str(src), "--out", str(out)])
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert len(rows) == 2
    assert float(rows[0]["property_score"]) >= float(rows[1]["property_score"])
    assert {"property_signals", "property_missing_signals", "property_queue"} <= set(rows[0])


def test_cli_match_e2e(tmp_path):
    sellers, buyers = tmp_path / "sellers.csv", tmp_path / "buyers.csv"
    _write_csv(str(sellers), [{"id": "S1", "market": "Dallas TX"}])
    _write_csv(str(buyers), [{"company": "BuyCo", "type": "investor", "market": "Dallas",
                              "confidence": "0.8", "contact_channel": "phone"}])
    out = tmp_path / "matches.csv"
    main(["match", str(sellers), str(buyers), "--out", str(out)])
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["seller"] == "S1"
    assert rows[0]["buyer"] == "BuyCo"


def test_cli_report_e2e(tmp_path):
    src = tmp_path / "buyers.csv"
    _write_csv(str(src), [{"company": "Acme", "intent": "high", "confidence": "0.9",
                           "contact_channel": "email", "email": "x@acme.com"}])
    main(["report", str(src)])
    assert (tmp_path / "buyers_scored.csv").exists()
