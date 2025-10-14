# full_roster_scraper.py — scrapes UFCStats A–Z into data/roster.csv
import re, time, csv, sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import os
QUICK = os.getenv("QUICK", "0") == "1"
LETTERS = os.getenv("LETTERS")
from datetime import datetime, timezone

ACTIVE_YEARS = float(os.getenv("ACTIVE_YEARS", "3"))     # keep fighters with a UFC bout in last N years
MIN_BOUTS    = int(os.getenv("MIN_BOUTS", "1"))          # require at least N UFC bouts

def _parse_date(txt):
    for fmt in ["%b. %d, %Y", "%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(txt.strip(), fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None
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
        print(f"[info] letter: {c}", file=sys.stderr)
        url = f"{BASE}/statistics/fighters?char={c}&page=all"
        try:
            soup = BeautifulSoup(_get(url), "lxml")
            for a in soup.select("td a[href*='/fighter-details/']"):
                yield a.get_text(strip=True), a["href"]
            time.sleep(0.4)
        except Exception as e:
            print(f"[warn] roster page {c}: {e}", file=sys.stderr)
def parse_profile(url):
    import re
    dat = {"Height_in":"", "Reach_in":"", "Stance":"", "Age":"", "LastFightDate":"", "BoutCount":0}
    try:
        html = _get(url)
        soup = BeautifulSoup(html, "lxml")

        # ---- Name ----
        name = soup.select_one("span.b-content__title-highlight")
        dat["Name"] = name.get_text(strip=True) if name else ""

        # ---- Physicals / stance (left box) ----
        for li in soup.select("ul.b-list__box-list li"):
            t = li.get_text(" ", strip=True)

            # Height "6' 2""
            if "Height" in t:
                m = re.findall(r"(\d+)\s*'\s*(\d+)", t)
                if m:
                    dat["Height_in"] = int(m[0][0]) * 12 + int(m[0][1])

            # Reach "74\"" or "74 in"
            if "Reach" in t:
                m = re.findall(r"(\d+)\s*(?:\"|in)", t.lower())
                if m:
                    dat["Reach_in"] = float(m[0])

            # Stance
            if "STANCE" in t.upper():
                dat["Stance"] = t.split(":")[-1].strip()

                # ---- Main Stats (works on modern UFCStats layout) ----
        # Format example:
        # SLpM: 2.46
        # Str. Acc.: 59%
        # SApM: 1.27
        # Str. Def.: 64%
        # TD Avg.: 3.17
        # TD Acc.: 62%
        # TD Def.: 90%
        # Sub. Avg.: 1.00

        for li in soup.select("ul.b-list__box-list li"):
            t = li.get_text(" ", strip=True)

            def num_after(colon_text):
                m = re.search(r":\s*([-+]?\d+(?:\.\d+)?)", colon_text)
                return float(m.group(1)) if m else None

            # SLpM
            if "SLpM" in t:
                v = num_after(t)
                if v is not None:
                    dat["SSLpm"] = v

            # SApM
            if "SApM" in t:
                v = num_after(t)
                if v is not None:
                    dat["SSApm"] = v

            # Str. Acc. %
            if "Str. Acc." in t:
                m = re.search(r"(\d+)\s*%", t)
                if m:
                    dat["Acc"] = int(m.group(1)) / 100.0

            # Str. Def. %
            if "Str. Def." in t:
                m = re.search(r"(\d+)\s*%", t)
                if m:
                    dat["Def"] = int(m.group(1)) / 100.0

            # Takedown Avg (per 15)
            if "TD Avg." in t:
                v = num_after(t)
                if v is not None:
                    dat["TD15"] = v

            # Takedown Accuracy %
            if "TD Acc." in t:
                m = re.search(r"(\d+)\s*%", t)
                if m:
                    dat["TDAcc"] = int(m.group(1)) / 100.0

            # Takedown Defense %
            if "TD Def." in t:
                m = re.search(r"(\d+)\s*%", t)
                if m:
                    dat["TDD"] = int(m.group(1)) / 100.0

            # Knockdown Avg (per 15)
            if "KD Avg." in t or "Knockdown Avg." in t:
                v = num_after(t)
                if v is not None:
                    dat["KDpm"] = v

            # Submission Avg (per 15)
            if "Sub. Avg." in t:
                v = num_after(t)
                if v is not None:
                    dat["Sub15"] = v

        # ---- Fight History Table: get most recent fight date + bout count ----
        last_dt = None
        bouts = 0
        for row in soup.select("table.b-fight-details__table tbody tr"):
            cells = [c.get_text(" ", strip=True) for c in row.select("td")]
            # look for any cell that parses as a date
            for c in reversed(cells):
                dt = _parse_date(c)
                if dt:
                    bouts += 1
                    if (last_dt is None) or (dt > last_dt):
                        last_dt = dt
                    break
        if last_dt:
            dat["LastFightDate"] = last_dt.isoformat()
        dat["BoutCount"] = bouts

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
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()

        for name, url in iter_roster_urls():
            row = parse_profile(url)
            if not row.get("Name"):
                row["Name"] = name

            # ---- Active filter ----
            is_active = True
            try:
                if row.get("LastFightDate"):
                    last_dt = datetime.fromisoformat(row["LastFightDate"])
                    years = (datetime.now(timezone.utc) - last_dt).days / 365.25
                    if years > ACTIVE_YEARS:
                        is_active = False
                else:
                    is_active = False

                if int(row.get("BoutCount", 0)) < MIN_BOUTS:
                    is_active = False
            except Exception:
                pass

            if not is_active:
                continue  # skip retired/inactive fighters

            # ---- Merge defaults FIRST, then real stats OVERRIDE ----
            row = {**default_stat_block(), **row}

            # ---- Write row ----
            w.writerow({k: row.get(k, "") for k in COLS})
            print(f"[info] wrote: {row.get('Name','?')}")
            time.sleep(0.35)

    print(f"[ok] wrote {out_csv}")
    build_roster(Path("data/roster.csv"))
