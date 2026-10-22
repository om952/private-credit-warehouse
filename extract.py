import os
import time
import requests
from dotenv import load_dotenv
from config import N_QUARTERS

load_dotenv()
HEADERS = {"User-Agent": os.environ["SEC_USER_AGENT"]}
CIKS = {"ARCC": 1287750}


def get(url):
    time.sleep(0.11)  # stay under SEC's 10 req/sec
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r


def recent_filings(cik, n):
    r = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()["filings"]["recent"]
    out = []
    for form, acc, rep, doc in zip(r["form"], r["accessionNumber"], r["reportDate"], r["primaryDocument"]):
        if form in ("10-Q", "10-K") and rep not in [f[1] for f in out]:
            out.append((acc.replace("-", ""), rep, doc))
    return out[:n]


def extract(ticker):
    cik = CIKS[ticker]
    folder = f"data/raw/{ticker}"
    os.makedirs(folder, exist_ok=True)
    for acc, period_end, doc in recent_filings(cik, N_QUARTERS):
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"
        xml_path, htm_path = f"{folder}/{period_end}.xml", f"{folder}/{period_end}.htm"
        if not os.path.exists(xml_path):
            items = get(f"{base}/index.json").json()["directory"]["item"]
            xml = next(i["name"] for i in items if i["name"].endswith("_htm.xml"))
            open(xml_path, "wb").write(get(f"{base}/{xml}").content)
        if not os.path.exists(htm_path):
            open(htm_path, "wb").write(get(f"{base}/{doc}").content)
        print(ticker, period_end, acc, doc)


if __name__ == "__main__":
    extract("ARCC")
