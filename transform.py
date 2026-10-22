import glob
import os
import re
import pandas as pd
from lxml import etree
from config import FACT_ELEMENTS, INVESTMENT_AXIS, ISSUER_AXIS, TOTAL_FV_ELEMENT

XI = "{http://www.xbrl.org/2003/instance}"
DI = "{http://xbrl.org/2006/xbrldi}"
XH = "{http://www.w3.org/1999/xhtml}"
IX = "{http://www.xbrl.org/2013/inlineXBRL}"
COLUMNS = ["ticker", "period_end", "borrower", "industry", "lien_type", "is_loan", "reference_rate",
           "spread", "interest_rate", "pik_rate", "maturity", "principal", "cost", "fair_value"]
LOAN_TYPES = {"First Lien", "Second Lien", "Unitranche", "Subordinated"}
EQUITY_WORDS = ["unit", "stock", "share", "interest", "warrant", "equity", "preferred", "common"]
DATE = re.compile(r"\d{2}/\d{4}")


def parse_xbrl(path, period_end):
    root = etree.parse(path, etree.XMLParser(huge_tree=True)).getroot()
    prefixes = {v: k for k, v in root.nsmap.items() if k}
    investments, no_dim = set(), set()
    for c in root.iter(XI + "context"):
        if c.findtext(f"{XI}period/{XI}instant") != period_end:
            continue
        dims = c.findall(f".//{DI}explicitMember") + c.findall(f".//{DI}typedMember")
        if not dims:
            no_dim.add(c.get("id"))
        elif len(dims) == 1 and dims[0].get("dimension") in (INVESTMENT_AXIS, ISSUER_AXIS):
            investments.add(c.get("id"))
    facts, totals = {}, []
    for el in root:
        if not isinstance(el.tag, str) or el.text is None:
            continue
        q = etree.QName(el)
        name, ctx = f"{prefixes.get(q.namespace)}:{q.localname}", el.get("contextRef")
        if ctx in investments and name in FACT_ELEMENTS:
            facts.setdefault(ctx, {})[FACT_ELEMENTS[name]] = float(el.text)
        elif ctx in no_dim and name == TOTAL_FV_ELEMENT:
            totals.append((int(el.get("decimals")), float(el.text)))
    df = pd.DataFrame.from_dict(facts, orient="index")
    df = df[df["fair_value"].notna() & df["cost"].notna()]
    return df, max(totals)[1]  # most precise reported total


def parse_html(path):
    # One SOI line item per <tr> that has a fair value fact and a MM/YYYY date (subtotal rows have no date).
    # Columns: [company, description,] instrument, coupon, reference (tenor), spread, acquired, maturity, ...
    root = etree.parse(path, etree.XMLParser(huge_tree=True, recover=True)).getroot()
    out, industry, company, instrument = {}, None, None, None
    for tr in root.iter(XH + "tr"):
        cells, stops, fv_ctx, spread_idx = [], [], None, None
        for td in tr.iter(XH + "td"):
            text = re.sub(r"\s+", " ", "".join(td.itertext())).strip()
            if not text:
                continue
            facts = list(td.iter(IX + "nonFraction"))
            for f in facts:
                if f.get("name") == "us-gaap:InvestmentOwnedAtFairValue":
                    fv_ctx = fv_ctx or f.get("contextRef")
                if f.get("name") == "us-gaap:InvestmentBasisSpreadVariableRate":
                    spread_idx = len(cells)
            stops.append(bool(facts) or bool(DATE.fullmatch(text)) or bool(re.match(r"\d+(\.\d+)?%", text)))
            cells.append(text)
        has_facts = next(tr.iter(IX + "nonFraction", IX + "nonNumeric"), None) is not None
        bold = any("font-weight:700" in (s.get("style") or "") for s in tr.iter(XH + "span"))
        if bold and len(cells) == 1 and not has_facts:
            industry = cells[0].replace("&", "and")
        dates = [c for c in cells if DATE.fullmatch(c)]
        if not (fv_ctx and dates):
            continue
        first_stop = stops.index(True)
        if first_stop >= 3:  # first row of a company carries its name and business description
            company = re.sub(r"(\s*\(\d+\))+$", "", cells[0])
        if first_stop >= 1:  # else the instrument text wrapped into the previous row
            instrument = cells[first_stop - 1]
        if fv_ctx in out:
            continue
        ref = re.fullmatch(r"([A-Za-z ]+?)\s*\([A-Z0-9]+\)", cells[spread_idx - 1]) if spread_idx else None
        out[fv_ctx] = {
            "industry": industry,
            "borrower": company,
            "lien_type": lien_type(instrument),
            "maturity": f"{dates[-1][3:]}-{dates[-1][:2]}-01" if len(dates) >= 2 else None,
            "reference_rate": ref.group(1).upper() if ref else None,
        }
    return out


def lien_type(instrument):
    s = instrument.lower()
    if "unitranche" in s or "one stop" in s:
        return "Unitranche"
    if "first lien" in s:
        return "First Lien"
    if "second lien" in s:
        return "Second Lien"
    if "subordinated" in s:
        return "Subordinated"
    if any(w in s for w in EQUITY_WORDS):
        return "Equity"
    return "Other"


def transform(ticker):
    loans, totals = [], []
    for xml_path in sorted(glob.glob(f"data/raw/{ticker}/*.xml")):
        period_end = os.path.basename(xml_path)[:-4]
        df, total = parse_xbrl(xml_path, period_end)
        html = pd.DataFrame.from_dict(parse_html(xml_path[:-4] + ".htm"), orient="index")
        df = df.join(html, how="inner")  # drops issuer subtotals and anything not on an SOI line
        df["is_loan"] = df["lien_type"].isin(LOAN_TYPES)
        df["ticker"], df["period_end"] = ticker, period_end
        loans.append(df.reindex(columns=COLUMNS))
        totals.append({"ticker": ticker, "period_end": period_end, "reported_total_fair_value": total})
    os.makedirs("data/clean", exist_ok=True)
    loans, totals = pd.concat(loans, ignore_index=True), pd.DataFrame(totals)
    loans.to_csv("data/clean/loans.csv", index=False)
    totals.to_csv("data/clean/reported_totals.csv", index=False)

    check = loans.groupby("period_end").agg(rows=("fair_value", "size"), fv_sum=("fair_value", "sum"))
    check = check.join(totals.set_index("period_end")["reported_total_fair_value"])
    check["diff_pct"] = (check["fv_sum"] / check["reported_total_fair_value"] - 1) * 100
    check["ok"] = check["diff_pct"].abs() <= 0.5
    print(check.to_string(float_format=lambda x: f"{x:,.2f}"))
    print("\nNull rate, all rows:\n" + loans.isna().mean().round(3).to_string())
    print("\nNull rate, is_loan rows:\n" + loans[loans["is_loan"]].isna().mean().round(3).to_string())


if __name__ == "__main__":
    transform("ARCC")
