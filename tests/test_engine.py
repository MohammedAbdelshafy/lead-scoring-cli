"""Tests for the lead scoring CLI — stdlib only."""
import csv
import os
import subprocess
import sys
import tempfile

import pytest

from lead_scoring import grade, score_row
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
    s = score_row(r)
    assert 85 <= s <= 100, s


def test_score_row_low_intent():
    r = {"intent": "low", "confidence": "0.1", "contact_channel": "", "email": ""}
    s = score_row(r)
    assert s < 55, s


def test_score_row_defaults_missing_fields():
    s = score_row({})
    assert 0 <= s <= 100


def test_markets_normalization():
    assert _markets("Dallas / Fort Worth, TX") == {"dallas", "fort", "worth"}
    assert _markets("") == set()
    assert _markets("US") == set()  # tokens <= 2 chars dropped


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


def test_cli_match_e2e(tmp_path):
    sellers = tmp_path / "sellers.csv"
    buyers = tmp_path / "buyers.csv"
    _write_csv(str(sellers), [{"id": "S1", "market": "Dallas TX"}])
    _write_csv(str(buyers), [{"company": "BuyCo", "type": "investor",
                              "market": "Dallas", "confidence": "0.8",
                              "contact_channel": "phone"}])
    out = tmp_path / "matches.csv"
    main(["match", str(sellers), str(buyers), "--out", str(out)])
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["seller"] == "S1"
    assert rows[0]["buyer"] == "BuyCo"


def test_cli_report_e2e(tmp_path):
    src = tmp_path / "buyers.csv"
    _write_csv(str(src), [
        {"company": "Acme", "intent": "high", "confidence": "0.9",
         "contact_channel": "email", "email": "x@acme.com"},
    ])
    main(["report", str(src)])
    assert (tmp_path / "buyers_scored.csv").exists()
