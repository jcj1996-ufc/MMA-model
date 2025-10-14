# full_roster_scraper.py — scrapes UFCStats A–Z into data/roster.csv
import re, time, csv, sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import os
QUICK = os.getenv("QUICK", "0") == "1"
LETTERS = os.getenv("LETTERS")
BASE = "http://ufcstats.com"
HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
COLS = ["Name","Age","Height_in","Reach_in","Stance","SSLpm","SSApm","Acc","Def","KDpm","TD15","TDAcc","TDD","TopCtl","BottomCtl","Sub15","OppEsc","Attpm","LateRet","KDtakenpm","KDlast12m","Whiff","WPA","Fouls","Camp","HeadRate","CARDIO_ret","FinishRate"]

def _get(url, to=25):
    r = requests.get(url, headers=HEADERS, timeout=to); r.raise_for_status(); return r.text

def iter_roster_urls():
    if LETTERS:
        letters = list(LETTERS)
    elif QUICK:
        letters = list("ab")
    else:
        letters = list("abcdefghijklmnopqrstuvwxyz") + ["other"]
    for c in letters:
        url = f"{BASE}/statistics/fighters?char={c}&page=all"
        try:
            soup = BeautifulSoup(_get(url), "lxml")
            for a in soup.select("td a[href*='/fighter-details/']"):
                yield a.get_text(strip=True), a["href"]
            time.sleep(0.4)
        except Exception as e:
            print(f"[warn] roster page {c}: {e}", file=sys.stderr)

def parse_profile(url):
    dat={"Height_in":"","Reach_in":"","Stance":"","Age":""}
    try:
        soup = BeautifulSoup(_get(url), "lxml")
        name = soup.select_one("span.b-content__title-highlight")
        dat["Name"] = name.get_text(strip=True) if name else ""
        for li in soup.select("ul.b-list__box-list li"):
            t = li.get_text(" ", strip=True)
            if "Height" in t:
                m=re.findall(r"(\d+)'(\d+)", t)
                if m: dat["Height_in"]=int(m[0][0])*12+int(m[0][1])
            if "Reach" in t:
                m=re.findall(r"(\d+)\s*in", t.lower())
                if m: dat["Reach_in"]=float(m[0])
            if "STANCE" in t.upper():
                dat["Stance"]=t.split(":")[-1].strip()
    except Exception as e:
        print(f"[warn] profile parse: {url}: {e}", file=sys.stderr)
    return dat

def default_stat_block():
    return {
        "SSLpm":3.0,"SSApm":3.0,"Acc":0.47,"Def":0.53,"KDpm":0.10,"TD15":1.5,"TDAcc":0.38,"TDD":0.65,
        "TopCtl":0.15,"BottomCtl":0.15,"Sub15":0.40,"OppEsc":0.50,"Attpm":8.0,"LateRet":0.75,
        "KDtakenpm":0.12,"KDlast12m":0.20,"Whiff":0.40,"WPA":0.00,"Fouls":0.10,"Camp":0.00,
        "HeadRate":0.70,"CARDIO_ret":0.75,"FinishRate":0.50
    }

def build_roster(out_csv: Path):
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader()
        for name, url in iter_roster_urls():
            row = parse_profile(url)
            if not row.get("Name"): row["Name"]=name
            row.update(default_stat_block())
            w.writerow({k: row.get(k, "") for k in COLS})
            time.sleep(0.35)
    print(f"[ok] wrote {out_csv}")

if __name__ == "__main__":
    build_roster(Path("data/roster.csv"))
