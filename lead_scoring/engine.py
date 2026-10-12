#!/usr/bin/env python3
"""MBM Lead Intelligence Engine — scoring + buyer-matching (dependency-free, config-driven).

  python3 Scripts/lead_engine.py score  <leads.csv> [--out scored.csv]
  python3 Scripts/lead_engine.py property-score <properties.csv> [--out ranked.csv]
  python3 Scripts/lead_engine.py match  <sellers.csv> <buyers.csv> [--out matches.csv]

The legacy generic scoring and matching interfaces remain unchanged. Property
scores are transparent research-priority heuristics, not seller-intent predictions.
"""
import csv, sys, argparse, re

INTENT = {"high":1.0,"med":0.6,"medium":0.6,"low":0.3,"":0.4}
WEIGHTS = {"intent":0.40, "confidence":0.30, "has_channel":0.15, "domain_ok":0.15}

PROPERTY_WEIGHTS = {
    "tax_delinquent": 18, "foreclosure_notice": 22, "probate_or_inherited": 12,
    "vacant": 12, "code_violation": 8, "absentee_owner": 7,
    "long_ownership": 6, "high_equity": 10, "valid_phone": 3, "valid_email": 2,
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

def _f(v,d=0.0):
    try:
        n = float(v)
        return n if n == n and abs(n) != float("inf") else d
    except (TypeError, ValueError):
        return d

def grade(s):
    return "Platinum" if s>=85 else "Gold" if s>=70 else "Silver" if s>=55 else "Bronze"

def score_row(r):
    """Legacy general/business lead score; kept backward-compatible."""
    intent = INTENT.get(str(r.get("intent","")).strip().lower(),0.4)
    conf   = _f(r.get("confidence"),0.5)
    chan   = 1.0 if str(r.get("contact_channel","")).strip() else 0.0
    dom    = 1.0 if str(r.get("email","")).strip() and "needs" not in r.get("email","") else 0.5
    s = 100*(WEIGHTS["intent"]*intent + WEIGHTS["confidence"]*conf
             + WEIGHTS["has_channel"]*chan + WEIGHTS["domain_ok"]*dom)
    return round(s,1)

def _first(r, names):
    for name in names:
        value = r.get(name)
        if value is not None and str(value).strip() != "":
            return value
    return ""

def _signal_value(r, aliases):
    value = str(_first(r, aliases)).strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    return None

def _verified_phone(r):
    raw = str(_first(r, ("phone", "phone_number", "mobile", "primary_phone"))).strip()
    status = str(_first(r, ("phone_valid", "phone_verified", "phone_status"))).strip().lower()
    digits = re.sub(r"\D", "", raw)
    return bool(_PHONE_RE.fullmatch(raw)) and 7 <= len(digits) <= 15 and status in _TRUE

def _verified_email(r):
    raw = str(_first(r, ("email", "email_address"))).strip()
    status = str(_first(r, ("email_valid", "email_verified", "email_status"))).strip().lower()
    return bool(_EMAIL_RE.fullmatch(raw)) and status in _TRUE

def score_property_row(r):
    """Return property research score, earned/missing signals, and a non-binding queue."""
    score = 0
    signals, missing = [], []
    for signal, aliases in PROPERTY_SIGNAL_FIELDS.items():
        raw = _first(r, aliases)
        active = None
        if signal == "long_ownership" and raw != "":
            years = _f(raw, -1)
            active = years >= 10 if years >= 0 else None
        elif signal == "high_equity" and raw != "":
            raw_equity = str(raw).strip().lower()
            if raw_equity in _TRUE:
                active = True
            elif raw_equity in _FALSE:
                active = False
            else:
                has_percent = raw_equity.endswith("%")
                pct = _f(raw_equity.replace("%", ""), -1)
                if pct >= 0:
                    # Explicit percent strings stay percentages; bare 0-1 numbers are ratios.
                    if not has_percent and pct <= 1:
                        pct *= 100
                    active = pct >= 70
        elif signal == "valid_phone":
            active = _verified_phone(r)
        elif signal == "valid_email":
            active = _verified_email(r)
        else:
            active = _signal_value(r, aliases) if raw != "" else None

        if active is True:
            score += PROPERTY_WEIGHTS[signal]
            signals.append(signal)
        elif active is None and signal in {
            "tax_delinquent", "foreclosure_notice", "probate_or_inherited", "vacant",
            "code_violation", "absentee_owner", "long_ownership", "high_equity"
        }:
            missing.append(signal)

    score = round(min(100, max(0, score)), 1)
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
        "property_score_note": "Research priority only; not a seller-intent prediction or call-eligibility decision.",
    }

def cmd_score(a):
    rows=list(csv.DictReader(open(a.file)))
    if not rows: sys.exit("empty input")
    for r in rows:
        r["lead_score"]=score_row(r); r["grade"]=grade(r["lead_score"])
    rows.sort(key=lambda r:-r["lead_score"])
    out=open(a.out,"w",newline="",encoding="utf-8") if a.out else sys.stdout
    w=csv.DictWriter(out,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    if a.out: print(f"scored {len(rows)} -> {a.out} (top: {rows[0].get('company',rows[0])} {rows[0]['lead_score']})")

def cmd_property_score(a):
    with open(a.file, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows: sys.exit("empty input")
    for r in rows:
        r.update(score_property_row(r))
    rows.sort(key=lambda r: -float(r["property_score"]))
    out = open(a.out,"w",newline="",encoding="utf-8") if a.out else sys.stdout
    writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
    writer.writeheader(); writer.writerows(rows)
    if a.out:
        out.close()
        print(f"property-scored {len(rows)} -> {a.out} (top score: {rows[0]['property_score']})")

def _markets(v):
    return set(t.strip().lower() for t in str(v).replace("/"," ").replace(",", " ").split() if len(t)>2)

def cmd_match(a):
    sellers=list(csv.DictReader(open(a.sellers)))
    buyers=list(csv.DictReader(open(a.buyers)))
    for b in buyers: b["_m"]=_markets(b.get("market",""))
    out=[]
    for s in sellers:
        sm=_markets(s.get("market") or s.get("geography") or s.get("state") or "")
        ranked=[]
        for b in buyers:
            overlap = 1 if (sm & b["_m"] or "us" in b["_m"] or "nationwide" in b["_m"]) else 0
            if not overlap: continue
            ranked.append((_f(b.get("confidence"),0.5), b))
        ranked.sort(key=lambda x:-x[0])
        for conf,b in ranked[:3]:
            out.append({"seller":s.get("id") or s.get("address") or s.get("company","?"),
                        "seller_market":s.get("market") or s.get("geography",""),
                        "buyer":b.get("company"),"buyer_type":b.get("type"),
                        "buyer_market":b.get("market"),"buyer_conf":b.get("confidence"),
                        "buyer_channel":b.get("contact_channel")})
    dst=open(a.out,"w",newline="",encoding="utf-8") if a.out else sys.stdout
    if out:
        w=csv.DictWriter(dst,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print(f"# {len(out)} seller→buyer matches from {len(sellers)} sellers × {len(buyers)} buyers", file=sys.stderr)

def cmd_report(a):
    """Daily automation: score the buyer CSV, write sorted output + print summary."""
    import collections, datetime
    rows=list(csv.DictReader(open(a.file)))
    if not rows: sys.exit("empty input")
    for r in rows:
        r["lead_score"]=score_row(r); r["grade"]=grade(r["lead_score"])
    rows.sort(key=lambda r:-r["lead_score"])
    out=a.out or a.file.replace(".csv","_scored.csv")
    with open(out,"w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    g=collections.Counter(r["grade"] for r in rows)
    print(f"# Lead report {datetime.date.today()} — {len(rows)} buyers -> {out}")
    print(f"# grades: Platinum {g['Platinum']} · Gold {g['Gold']} · Silver {g['Silver']} · Bronze {g['Bronze']}")
    print("# top 5:")
    for r in rows[:5]:
        print(f"#   {r['lead_score']:>5}  {r.get('grade'):8}  {r.get('company','?')}")

def main(argv=None):
    p=argparse.ArgumentParser(prog="lead-score")
    sub=p.add_subparsers(dest="cmd",required=True)
    ps=sub.add_parser("score"); ps.add_argument("file"); ps.add_argument("--out"); ps.set_defaults(fn=cmd_score)
    pp=sub.add_parser("property-score", help="Score property-level seller research signals.")
    pp.add_argument("file"); pp.add_argument("--out"); pp.set_defaults(fn=cmd_property_score)
    pr=sub.add_parser("report"); pr.add_argument("file"); pr.add_argument("--out"); pr.set_defaults(fn=cmd_report)
    pm=sub.add_parser("match"); pm.add_argument("sellers"); pm.add_argument("buyers"); pm.add_argument("--out"); pm.set_defaults(fn=cmd_match)
    a=p.parse_args(argv); a.fn(a)

if __name__=="__main__":
    main()
