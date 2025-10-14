# full_roster_scraper.py — builds data/roster.csv from UFCStats

import re, time, csv, sys, os
from pathlib import Path
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# ---------- Config ----------
BASE = "https://ufcstats.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

QUICK   = os.getenv("QUICK", "0") == "1"
LETTERS = os.getenv("LETTERS")
ACTIVE_YEARS = float(os.getenv("ACTIVE_YEARS", "3"))
MIN_BOUTS    = int(os.getenv("MIN_BOUTS", "1"))

BASE_COLS = [
    "Name","Age","Height_in","Reach_in","Stance",
    "SSLpm","SSApm","Acc","Def","KDpm",
    "TD15","TDAcc","TDD","Sub15",
    "LastFightDate","BoutCount"
]

def default_stat_block():
    # engineered defaults; scraped values will override them
    return {
        "SSLpm":3.0, "SSApm":3.0, "Acc":0.47, "Def":0.53, "KDpm":0.08,
        "TD15":1.3, "TDAcc":0.36, "TDD":0.60, "Sub15":0.40,
        "TopCtl":0.15, "BottomCtl":0.15, "OppEsc":0.30,
        "KDtakenpm":0.12, "KDlast12m":0.20, "Whiff":0.40, "WPA":0.50,
        "HeadRate":0.70, "CARDIO_ret":0.75, "FinishRate":0.50
    }

# build final column list (defaults union base)
COLS = BASE_COLS + [k for k in default_stat_block().keys() if k not in BASE_COLS]

# ---------- HTTP ----------
def _get(url, to=25):
    last_exc = None
    for _ in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=to, allow_redirects=True)
            if r.status_code == 200 and len(r.text) > 1000:
                return r.text
        except Exception as e:
            last_exc = e
        time.sleep(0.8)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"bad fetch {url}")

# ---------- Helpers ----------
def _parse_date(txt):
    for fmt in ["%b. %d, %Y", "%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(txt.strip(), fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None

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
            for a in soup.select("td a[href*='fighter-details']"):
                name = a.get_text(strip=True)
                href = a.get("href", "")
                if href:
                    yield name, href
            print(f"[info] roster page {c}: ok", file=sys.stderr)
        except Exception as e:
            print(f"[warn] roster page {c}: {e}", file=sys.stderr)
        time.sleep(0.4)

# ---------- Parse one profile ----------
def parse_profile(url):
    dat = {"Height_in":"", "Reach_in":"", "Stance":"", "Age":"", "LastFightDate":"", "BoutCount":0}
    try:
        html = _get(url)
        soup = BeautifulSoup(html, "lxml")

        # Title for debug
        title = soup.title.get_text(strip=True) if soup.title else "no-title"
        # Name
        name = soup.select_one("span.b-content__title-highlight")
        dat["Name"] = name.get_text(strip=True) if name else ""

        # Left box: physicals / stance
        for li in soup.select("ul.b-list__box-list li"):
            t = li.get_text(" ", strip=True)

            if "Height" in t:
                m = re.findall(r"(\d+)\s*'\s*(\d+)", t)
                if m:
                    dat["Height_in"] = int(m[0][0]) * 12 + int(m[0][1])

            if "Reach" in t:
                m = re.findall(r"(\d+)\s*(?:\"|in)", t.lower())
                if m:
                    dat["Reach_in"] = float(m[0])

            if "STANCE" in t.upper():
                dat["Stance"] = t.split(":")[-1].strip()

        # Right box: stats (try multiple list variants)
        stats_selectors = [
            "div.b-list__info-box.b-list__info-box--right ul.b-list__box-list li",
            "ul.b-list__box-list.b-list__box-list--style-none li",
            "ul.b-list__box-list.b-list__box-list--border-top li",
            "ul.b-list__box-list--right li",
            "ul.b-list__box-list li",
        ]

        def num_after(colon_text):
            m = re.search(r":\s*([-+]?\d+(?:\.\d+)?)", colon_text)
            return float(m.group(1)) if m else None

        got = set()
        for sel in stats_selectors:
            items = soup.select(sel)
            if not items:
                continue
            for li in items:
                t = li.get_text(" ", strip=True)

                if "SLpM" in t and "SSLpm" not in got:
                    v = num_after(t)
                    if v is not None: dat["SSLpm"] = v; got.add("SSLpm")

                elif "SApM" in t and "SSApm" not in got:
                    v = num_after(t)
                    if v is not None: dat["SSApm"] = v; got.add("SSApm")

                elif "Str. Acc." in t and "Acc" not in got:
                    m = re.search(r"(\d+)\s*%", t)
                    if m: dat["Acc"] = int(m.group(1))/100.0; got.add("Acc")

                elif "Str. Def." in t and "Def" not in got:
                    m = re.search(r"(\d+)\s*%", t)
                    if m: dat["Def"] = int(m.group(1))/100.0; got.add("Def")

                elif ("KD Avg." in t or "Knockdown Avg." in t) and "KDpm" not in got:
                    v = num_after(t)
                    if v is not None: dat["KDpm"] = v; got.add("KDpm")

                elif "TD Avg." in t and "TD15" not in got:
                    v = num_after(t)
                    if v is not None: dat["TD15"] = v; got.add("TD15")

                elif "TD Acc." in t and "TDAcc" not in got:
                    m = re.search(r"(\d+)\s*%", t)
                    if m: dat["TDAcc"] = int(m.group(1))/100.0; got.add("TDAcc")

                elif "TD Def." in t and "TDD" not in got:
                    m = re.search(r"(\d+)\s*%", t)
                    if m: dat["TDD"] = int(m.group(1))/100.0; got.add("TDD")

                elif "Sub. Avg." in t and "Sub15" not in got:
                    v = num_after(t)
                    if v is not None: dat["Sub15"] = v; got.add("Sub15")

            if len(got) >= 7:
                break

        if not got:
            print(f"[warn] no stats list for {dat.get('Name','?')} | {title} | {url}", file=sys.stderr)

        # Fight history: last fight date + bout count
        last_dt = None
        bouts = 0
        for row in soup.select("table.b-fight-details__table tbody tr"):
            cells = [c.get_text(" ", strip=True) for c in row.select("td")]
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

        print(f"[debug] parsed {dat.get('Name','?')} | got={sorted(list(got))}", file=sys.stderr)

    except Exception as e:
        print(f"[warn] profile parse: {url}: {e}", file=sys.stderr)

    return dat

# ---------- Build roster ----------
def build_roster(out_csv: Path):
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()

        for name, url in iter_roster_urls():
            row = parse_profile(url)
            if not row.get("Name"):
                row["Name"] = name

            # Active-only filter
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
                continue

            # Merge defaults first, then real values override
            row = {**default_stat_block(), **row}

            w.writerow({k: row.get(k, "") for k in COLS})
            print(f"[info] wrote: {row.get('Name','?')}", file=sys.stderr)
            time.sleep(0.35)

    print(f"[ok] wrote {out_csv}", file=sys.stderr)

# ---------- Main ----------
if __name__ == "__main__":
    build_roster(Path("data/roster.csv"))
