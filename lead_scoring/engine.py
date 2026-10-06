#!/usr/bin/env python3
"""MBM Lead Intelligence Engine — scoring + buyer-matching (dependency-free, config-driven).

  python3 Scripts/lead_engine.py score  <leads.csv> [--out scored.csv]
  python3 Scripts/lead_engine.py match  <sellers.csv> <buyers.csv> [--out matches.csv]

score : transparent weighted rubric -> adds `lead_score` (0-100) + `grade`.
match : the dispo engine — pairs each seller to the best buyers by market + type,
        the MaxDispo model in code (Reports/research/MaxDier_Enhancements.md).
Weights are config, not hardcoded logic — edit WEIGHTS / INTENT to retune."""
import csv, sys, argparse

INTENT = {"high":1.0,"med":0.6,"medium":0.6,"low":0.3,"":0.4}
WEIGHTS = {          # buyer scoring signals -> weight (sum ~1.0)
    "intent":0.40, "confidence":0.30, "has_channel":0.15, "domain_ok":0.15,
}
def _f(v,d=0.0):
    try: return float(v)
    except: return d
def grade(s):
    return "Platinum" if s>=85 else "Gold" if s>=70 else "Silver" if s>=55 else "Bronze"

def score_row(r):
    intent = INTENT.get(str(r.get("intent","")).strip().lower(),0.4)
    conf   = _f(r.get("confidence"),0.5)
    chan   = 1.0 if str(r.get("contact_channel","")).strip() else 0.0
    dom    = 1.0 if str(r.get("email","")).strip() and "needs" not in r.get("email","") else 0.5
    s = 100*(WEIGHTS["intent"]*intent + WEIGHTS["confidence"]*conf
             + WEIGHTS["has_channel"]*chan + WEIGHTS["domain_ok"]*dom)
    return round(s,1)

def cmd_score(a):
    rows=list(csv.DictReader(open(a.file)))
    if not rows: sys.exit("empty input")
    for r in rows:
        r["lead_score"]=score_row(r); r["grade"]=grade(r["lead_score"])
    rows.sort(key=lambda r:-r["lead_score"])
    out=open(a.out,"w",newline="",encoding="utf-8") if a.out else sys.stdout
    w=csv.DictWriter(out,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    if a.out: print(f"scored {len(rows)} -> {a.out} (top: {rows[0].get('company',rows[0])} {rows[0]['lead_score']})")

def _markets(v):  # normalize a market string to comparable tokens
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
    pr=sub.add_parser("report"); pr.add_argument("file"); pr.add_argument("--out"); pr.set_defaults(fn=cmd_report)
    pm=sub.add_parser("match"); pm.add_argument("sellers"); pm.add_argument("buyers"); pm.add_argument("--out"); pm.set_defaults(fn=cmd_match)
    a=p.parse_args(argv); a.fn(a)

if __name__=="__main__":
    main()
