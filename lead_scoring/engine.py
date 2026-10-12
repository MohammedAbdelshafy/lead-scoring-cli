#!/usr/bin/env python3
"""Transparent lead scoring and seller-to-buyer matching.

The legacy generic score remains stable for buyer/business records. Property
records should use score_property_row(), which returns an explainable score,
signals, missing evidence, and a non-binding queue recommendation.
"""
import csv
import sys
import argparse
import re
from datetime import date, datetime

INTENT = {"high": 1.0, "med": 0.6, "medium": 0.6, "low": 0.3, "": 0.4}
WEIGHTS = {"intent": 0.40, "confidence": 0.30, "has_channel": 0.15, "domain_ok": 0.15}

# A transparent starting rubric, not a statistically calibrated prediction.
# Only explicit, evidence-bearing fields earn distress points.
PROPERTY_WEIGHTS = {
    "tax_delinquent": 18,
    "foreclosure_notice": 22,
    "probate_or_inherited": 12,
    "vacant": 12,
    "code_violation": 8,
    "absentee_owner": 7,
    "long_ownership": 6,
    "high_equity": 10,
    "valid_phone": 3,
    "valid_email": 2,
}
PROPERTY_SIGNAL_FIELDS = {
    "tax_delinquent": ("tax_delinquent", "delinquent_taxes", "tax_status"),
    "foreclosure_notice": ("foreclosure_notice", "preforeclosure", "notice_of_default"),
    "probate_or_inherited": ("probate_or_inherited", "probate", "inherited"),
    "vacant": ("vacant", "vacancy_status"),
    "code_violation": ("code_violation", "open_code_violation"),
    "absentee_owner": ("absentee_owner", "out_of_state_owner"),
    "long_ownership": ("long_ownership", "years_owned"),
    "high_equity": ("high_equity", "equity_pct"),
    "valid_phone": ("phone_valid", "phone_verified", "phone_status"),
    "valid_email": ("email_valid", "email_verified", "email_status"),
}
_TRUE = {"1", "true", "yes", "y", "verified", "valid", "confirmed", "delinquent", "active", "open"}
_FALSE = {"0", "false", "no", "n", "invalid", "unverified", "none", "clear", "paid", "closed"}
_PHONE_RE = re.compile(r"^\+?[0-9().\-\s]{7,}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _f(v, d=0.0):
    try:
        n = float(v)
        return n if n == n and abs(n) != float("inf") else d
    except (TypeError, ValueError):
        return d


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _truth(v):
    return str(v or "").strip().lower() in _TRUE


def _first(r, names):
    for name in names:
        v = r.get(name)
        if v is not None and str(v).strip() != "":
            return v
    return ""


def _explicit_signal(r, aliases):
    """Interpret affirmative/negative values; unknown and missing earn no points."""
    value = str(_first(r, aliases)).strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    # Numeric-like domain-specific aliases.
    if value in {"tax delinquent", "foreclosure", "vacant", "absentee"}:
        return True
    return None


def _verified_phone(r):
    raw = str(_first(r, ("phone", "phone_number", "mobile", "primary_phone"))).strip()
    status = str(_first(r, ("phone_valid", "phone_verified", "phone_status"))).strip().lower()
    digits = re.sub(r"\D", "", raw)
    format_ok = bool(_PHONE_RE.fullmatch(raw)) and 7 <= len(digits) <= 15
    # A plausible format is not proof of reachability; score only provider-verified contacts.
    return format_ok and status in _TRUE


def _verified_email(r):
    raw = str(_first(r, ("email", "email_address"))).strip()
    status = str(_first(r, ("email_valid", "email_verified", "email_status"))).strip().lower()
    return bool(_EMAIL_RE.fullmatch(raw)) and status in _TRUE


def grade(s):
    return "Platinum" if s >= 85 else "Gold" if s >= 70 else "Silver" if s >= 55 else "Bronze"


def score_row(r):
    """Legacy score for general/business leads. Preserved for compatibility."""
    intent = INTENT.get(str(r.get("intent", "")).strip().lower(), 0.4)
    conf = _clamp(_f(r.get("confidence"), 0.5))
    chan = 1.0 if str(r.get("contact_channel", "")).strip() else 0.0
    email = str(r.get("email", "")).strip().lower()
    dom = 1.0 if email and "needs" not in email and _EMAIL_RE.fullmatch(email) else 0.5
    s = 100 * (WEIGHTS["intent"] * intent + WEIGHTS["confidence"] * conf
               + WEIGHTS["has_channel"] * chan + WEIGHTS["domain_ok"] * dom)
    return round(_clamp(s, 0, 100), 1)


def score_property_row(r):
    """Score observable property distress/equity/contact signals with reasons.

    Missing/unrecognized values do not earn points. No personal attributes are
    used. A score ranks research priority only; it does not assert owner intent.
    """
    score = 0.0
    signals = []
    missing = []
    for signal, aliases in PROPERTY_SIGNAL_FIELDS.items():
        # Years owned accepts a numeric threshold. Equity accepts a percentage.
        raw = _first(r, aliases)
        active = None
        if signal == "long_ownership" and raw != "":
            years = _f(raw, -1)
            if years >= 0:
                active = years >= 10
        elif signal == "high_equity" and raw != "":
            val = str(raw).strip().replace("%", "")
            pct = _f(val, -1)
            if pct >= 0:
                # Accept 0-1 ratios and 0-100 percentages consistently.
                if pct <= 1:
                    pct *= 100
                active = pct >= 70
        elif signal == "valid_phone":
            active = _verified_phone(r)
        elif signal == "valid_email":
            active = _verified_email(r)
        else:
            active = _explicit_signal(r, aliases) if raw != "" else None

        if active is True:
            score += PROPERTY_WEIGHTS[signal]
            signals.append(signal)
        elif active is None and signal in {
            "tax_delinquent", "foreclosure_notice", "probate_or_inherited",
            "vacant", "code_violation", "absentee_owner", "long_ownership", "high_equity"
        }:
            missing.append(signal)

    score = round(_clamp(score, 0, 100), 1)
    if "foreclosure_notice" in signals or "tax_delinquent" in signals:
        queue = "REVIEW_URGENT"
    elif score >= 45:
        queue = "PRIORITY_RESEARCH"
    elif score >= 25:
        queue = "STANDARD_RESEARCH"
    else:
        queue = "LOW_EVIDENCE"
    if not _verified_phone(r) and not _verified_email(r):
        queue = "CONTACT_ENRICHMENT_REQUIRED" if score >= 15 else "LOW_EVIDENCE"
    return {
        "property_score": score,
        "property_grade": grade(score),
        "property_signals": ";".join(signals),
        "property_missing_signals": ";".join(missing),
        "property_queue": queue,
        "property_score_version": "property-v1",
        "property_score_note": "Research priority only; not a prediction of seller intent or a call-eligibility decision.",
    }


def _read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _write_csv(path, rows):
    if not rows:
        raise ValueError("No rows to write.")
    fieldnames = list(rows[0].keys())
    if path:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    else:
        w = csv.DictWriter(sys.stdout, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def cmd_score(a):
    rows = _read_csv(a.file)
    if not rows:
        sys.exit("empty input")
    for r in rows:
        r["lead_score"] = score_row(r)
        r["grade"] = grade(r["lead_score"])
    rows.sort(key=lambda r: -float(r["lead_score"]))
    _write_csv(a.out, rows)
    if a.out:
        print(f"scored {len(rows)} -> {a.out} (top score: {rows[0]['lead_score']})")


def cmd_property_score(a):
    rows = _read_csv(a.file)
    if not rows:
        sys.exit("empty input")
    for r in rows:
        r.update(score_property_row(r))
    rows.sort(key=lambda r: -float(r["property_score"]))
    _write_csv(a.out, rows)
    if a.out:
        print(f"property-scored {len(rows)} -> {a.out} (top score: {rows[0]['property_score']})")


def _markets(v):
    return set(t.strip().lower() for t in str(v).replace("/", " ").replace(",", " ").split() if len(t) > 2)


def cmd_match(a):
    sellers = _read_csv(a.sellers)
    buyers = _read_csv(a.buyers)
    out = []
    for s in sellers:
        sm = _markets(s.get("market") or s.get("geography") or s.get("state") or s.get("zip") or "")
        ranked = []
        for b in buyers:
            bm = _markets(b.get("market", ""))
            overlap = bool(sm & bm) or any(t in bm for t in ("us", "usa", "nationwide"))
            if not overlap:
                continue
            # Buyer confidence affects rank only when a usable value is present.
            conf_raw = str(b.get("confidence", "")).strip()
            conf = _clamp(_f(conf_raw, 0.5)) if conf_raw else 0.5
            ranked.append((conf, b))
        ranked.sort(key=lambda x: -x[0])
        for conf, b in ranked[:3]:
            out.append({
                "seller": s.get("id") or s.get("address") or s.get("company", "?"),
                "seller_market": s.get("market") or s.get("geography") or s.get("state") or s.get("zip", ""),
                "buyer": b.get("company"), "buyer_type": b.get("type"),
                "buyer_market": b.get("market"), "buyer_conf": b.get("confidence"),
                "buyer_channel": b.get("contact_channel"),
            })
    if out:
        _write_csv(a.out, out)
    else:
        print("No seller/buyer market matches found.", file=sys.stderr)


def cmd_report(a):
    import collections
    from datetime import date
    rows = _read_csv(a.file)
    if not rows:
        sys.exit("empty input")
    for r in rows:
        r["lead_score"] = score_row(r)
        r["grade"] = grade(r["lead_score"])
    rows.sort(key=lambda r: -float(r["lead_score"]))
    out = a.out or a.file.replace(".csv", "_scored.csv")
    _write_csv(out, rows)
    g = collections.Counter(r["grade"] for r in rows)
    print(f"# Lead report {date.today()} — {len(rows)} buyers -> {out}")
    print(f"# grades: Platinum {g['Platinum']} · Gold {g['Gold']} · Silver {g['Silver']} · Bronze {g['Bronze']}")
    print("# top 5:")
    for r in rows[:5]:
        print(f"# {r['lead_score']:>5} {r.get('grade', ''):8} {r.get('company', r.get('address', '?'))}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="lead-score")
    sub = p.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("score", help="Score general/business leads (legacy rubric).")
    ps.add_argument("file")
    ps.add_argument("--out")
    ps.set_defaults(fn=cmd_score)
    pp = sub.add_parser("property-score", help="Score property-seller research leads with explanations.")
    pp.add_argument("file")
    pp.add_argument("--out")
    pp.set_defaults(fn=cmd_property_score)
    pr = sub.add_parser("report", help="Write a scored CSV and daily summary.")
    pr.add_argument("file")
    pr.add_argument("--out")
    pr.set_defaults(fn=cmd_report)
    pm = sub.add_parser("match", help="Match seller markets to relevant buyers.")
    pm.add_argument("sellers")
    pm.add_argument("buyers")
    pm.add_argument("--out")
    pm.set_defaults(fn=cmd_match)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
