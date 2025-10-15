# app.py — one-file FastAPI app with mobile UI + JSON API
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import pandas as pd
from pathlib import Path
import numpy as np
app = FastAPI(title="MMA Model")
# --- ADMIN SCRAPE ENDPOINT (FastAPI) ---
import os, base64, json
from pathlib import Path
import requests
from fastapi import HTTPException, Request
from full_roster_scraper import build_roster  # uses your existing scraper

def _upload_to_github(path: Path):
    repo   = os.environ["GH_REPO"]      # e.g. "yourname/MMA-model"
    branch = os.environ.get("GH_BRANCH", "main")
    token  = os.environ["GH_PAT"]
    api = f"https://api.github.com/repos/{repo}/contents/data/roster.csv"

    # get current sha (if file exists)
    sha = None
    r = requests.get(api, params={"ref": branch},
                     headers={"Authorization": f"token {token}",
                              "Accept": "application/vnd.github+json"})
    if r.status_code == 200:
        sha = r.json().get("sha")

    content = base64.b64encode(path.read_bytes()).decode("utf-8")
    body = {"message": "Update roster.csv via Render scraper",
            "content": content, "branch": branch}
    if sha: body["sha"] = sha

    r = requests.put(api, headers={"Authorization": f"token {token}",
                                   "Accept": "application/vnd.github+json"},
                     data=json.dumps(body))
    r.raise_for_status()

@app.get("/admin/scrape")
async def admin_scrape(request: Request):
    if request.query_params.get("key") != os.environ.get("ADMIN_KEY"):
        raise HTTPException(status_code=403, detail="forbidden")

    out = Path("/tmp/roster.csv")
    build_roster(out)
    _upload_to_github(out)
    return {"ok": True, "wrote": str(out)}

DATA = Path("data")
DATA.mkdir(exist_ok=True)
ROSTER = DATA / "roster.csv"

# Seed roster so it works instantly; daily workflow will overwrite with full roster
if not ROSTER.exists():
    ROSTER.write_text(
        "Name,Age,Height_in,Reach_in,Stance,SSLpm,SSApm,Acc,Def,KDpm,TD15,TDAcc,TDD,TopCtl,BottomCtl,Sub15,OppEsc,Attpm,LateRet,KDtakenpm,KDlast12m,Whiff,WPA,Fouls,Camp,HeadRate,CARDIO_ret,FinishRate\n"
        "Reinier de Ridder,33,76,78,Orthodox,2.9,1.7,0.48,0.58,0.05,3.8,0.62,0.68,0.60,0.10,2.5,0.40,8.0,0.80,0.04,0.05,0.35,0.40,0.05,0.10,0.70,0.85,0.75\n"
        "Dricus Du Plessis,30,72,76,Switch,4.9,3.7,0.49,0.50,0.29,1.7,0.46,0.50,0.26,0.18,0.5,0.55,9.2,0.75,0.09,0.10,0.42,0.35,0.05,0.00,0.71,0.78,0.70\n"
        "Robert Whittaker,34,72,73,Orthodox,4.5,3.1,0.41,0.61,0.24,0.6,0.37,0.84,0.22,0.13,0.1,0.60,9.5,0.82,0.07,0.08,0.44,0.30,0.04,0.00,0.74,0.83,0.55\n"
        "Brendan Allen,29,74,75,Orthodox,4.3,3.5,0.54,0.47,0.16,1.4,0.44,0.55,0.28,0.22,1.7,0.52,8.5,0.76,0.10,0.12,0.38,0.28,0.05,0.00,0.68,0.80,0.65\n"
    )

DIV_BENCH = [
    ("SSLpm",3.00,1.20),("SSApm",3.00,1.20),("Acc",0.47,0.08),("Def",0.53,0.08),("KDpm",0.15,0.20),
    ("TD15",1.50,1.50),("TDAcc",0.38,0.15),("TDD",0.65,0.20),("TopCtl",0.15,0.15),("BottomCtl",0.15,0.15),
    ("Sub15",0.40,0.60),("OppEsc",0.50,0.25),("Attpm",8.00,2.50),("LateRet",0.75,0.20),
    ("KDtakenpm",0.12,0.18),("KDlast12m",0.20,0.40),("Whiff",0.40,0.15),("WPA",0.00,1.00),("Fouls",0.10,0.20),
    ("Camp",0.00,1.00),("HeadRate",0.70,0.15),("CARDIO_ret",0.75,0.20),("FinishRate",0.50,0.25),
]
ZMAP = {m:(mu,sd) for m,mu,sd in DIV_BENCH}

HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MMA Model</title>
<style>body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:20px}
.card{border:1px solid #ddd;border-radius:10px;padding:16px;margin-bottom:16px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pill{display:inline-block;padding:4px 10px;border-radius:999px;background:#f3f3f3;margin-right:6px}
.big{font-size:28px;font-weight:700}.muted{color:#666;font-size:12px}
input,button{padding:10px;border-radius:8px;border:1px solid #ccc}button{border:0;background:#111;color:#fff;font-weight:600}
</style></head><body>
<div class="card"><h2>MMA Predictions (Mobile)</h2>
<p class="muted">Pick fighters and tap Predict. Data auto-updates daily.</p>
<div class="grid"><div><label>Fighter A</label><input id="a" list="fighters" placeholder="Type fighter name"></div>
<div><label>Fighter B</label><input id="b" list="fighters" placeholder="Type fighter name"></div></div>
<div style="margin-top:12px;"><button onclick="predict()">Predict</button></div>
<datalist id="fighters"></datalist></div>
<div id="out" class="card" style="display:none;">
<div class="grid"><div><div class="big" id="pA">--%</div><div class="muted">P(A) win</div></div>
<div><div class="big" id="pB">--%</div><div class="muted">P(B) win</div></div></div><hr/>
<div><div class="pill">A KO: <span id="a_ko">--%</span></div>
<div class="pill">A SUB: <span id="a_sub">--%</span></div>
<div class="pill">A DEC: <span id="a_dec">--%</span></div></div>
<div style="margin-top:8px;"><div class="pill">B KO: <span id="b_ko">--%</span></div>
<div class="pill">B SUB: <span id="b_sub">--%</span></div>
<div class="pill">B DEC: <span id="b_dec">--%</span></div></div></div>
<script>
async function loadRoster(){const r=await fetch('/api/roster');const names=await r.json();
const dl=document.getElementById('fighters');dl.innerHTML='';names.forEach(n=>{const o=document.createElement('option');o.value=n;dl.appendChild(o);});}
async function predict(){const a=document.getElementById('a').value,b=document.getElementById('b').value;
const r=await fetch(`/api/predict?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);const js=await r.json();
document.getElementById('out').style.display='block';
document.getElementById('pA').innerText=Math.round(js.P_A*100)+'%';
document.getElementById('pB').innerText=Math.round((1-js.P_A)*100)+'%';
document.getElementById('a_ko').innerText=Math.round(js.P_A_KO*100)+'%';
document.getElementById('a_sub').innerText=Math.round(js.P_A_SUB*100)+'%';
document.getElementById('a_dec').innerText=Math.round(js.P_A_DEC*100)+'%';
document.getElementById('b_ko').innerText=Math.round(js.P_B_KO*100)+'%';
document.getElementById('b_sub').innerText=Math.round(js.P_B_SUB*100)+'%';
document.getElementById('b_dec').innerText=Math.round(js.P_B_DEC*100)+'%';}
loadRoster();
</script></body></html>"""

def z(x, mu, sd):
    try: return max(-3.0, min(3.0, (float(x)-mu)/sd)) if sd else 0.0
    except: return 0.0

def rating(a, b):
    ZA = lambda m: z(a.get(m,0), *ZMAP.get(m,(0,1)))
    ZB = lambda m: z(b.get(m,0), *ZMAP.get(m,(0,1)))
    STR_A = 0.50*(ZA("SSLpm")-ZA("SSApm")) + 0.20*ZA("Acc") + 0.20*ZA("Def") + 0.10*ZA("KDpm")
    STR_B = 0.50*(ZB("SSLpm")-ZB("SSApm")) + 0.20*ZB("Acc") + 0.20*ZB("Def") + 0.10*ZB("KDpm")
    GRP_A = 0.35*ZA("TD15") + 0.20*ZA("TDAcc") + 0.25*ZA("TopCtl") + 0.20*ZA("Sub15") - 0.15*ZA("OppEsc")
    GRP_B = 0.35*ZB("TD15") + 0.20*ZB("TDAcc") + 0.25*ZB("TopCtl") + 0.20*ZB("Sub15") - 0.15*ZB("OppEsc")
    GRP_DA= 0.55*ZA("TDD") + 0.20*ZA("BottomCtl")
    GRP_DB= 0.55*ZB("TDD") + 0.20*ZB("BottomCtl")
    PACE_A= 0.60*ZA("Attpm") + 0.40*ZA("LateRet")
    PACE_B= 0.60*ZB("Attpm") + 0.40*ZB("LateRet")
    DUR_A = 0.55*(-ZA("KDtakenpm")) + 0.25*(-ZA("KDlast12m")) + 0.20*(-ZA("SSApm"))
    DUR_B = 0.55*(-ZB("KDtakenpm")) + 0.25*(-ZB("KDlast12m")) + 0.20*(-ZB("SSApm"))
    IQ_A  = 0.40*ZA("Acc") - 0.20*ZA("Whiff") + 0.40*ZA("WPA") - 0.20*ZA("Fouls")
    IQ_B  = 0.40*ZB("Acc") - 0.20*ZB("Whiff") + 0.40*ZB("WPA") - 0.20*ZB("Fouls")
    CTX_A = 0.25*ZA("Camp"); CTX_B = 0.25*ZB("Camp")
    R_A = 0.28*STR_A + 0.24*(GRP_A - 0.6*GRP_DA) + 0.14*PACE_A + 0.16*DUR_A + 0.12*IQ_A + 0.06*CTX_A
    R_B = 0.28*STR_B + 0.24*(GRP_B - 0.6*GRP_DB) + 0.14*PACE_B + 0.16*DUR_B + 0.12*IQ_B + 0.06*CTX_B
    return R_A, R_B

def softmax3(e1,e2,e3):
    mx=max(e1,e2,e3); a=np.exp(e1-mx); b=np.exp(e2-mx); c=np.exp(e3-mx); s=a+b+c; return a/s,b/s,c/s

def methods(a,b):
    ZA = lambda m: z(a.get(m,0), *ZMAP.get(m,(0,1)))
    ZB = lambda m: z(b.get(m,0), *ZMAP.get(m,(0,1)))
    eta_A_KO  = -0.30 + 0.55*ZA("KDpm") - 0.45*(0.55*(-ZB("KDtakenpm")) + 0.25*(-ZB("KDlast12m")) + 0.20*(-ZB("SSApm"))) + 0.20*ZA("HeadRate")
    eta_A_SUB = -0.50 + 0.60*ZA("Sub15") + 0.45*ZA("TDAcc") - 0.55*ZB("TDD") + 0.25*ZA("TopCtl")
    eta_A_DEC = -0.10 + 0.40*(0.60*ZA("Attpm") + 0.40*ZA("LateRet")) + 0.30*ZA("CARDIO_ret") - 0.25*(ZA("FinishRate")+ZB("FinishRate"))
    qA_KO,qA_SUB,qA_DEC = softmax3(eta_A_KO,eta_A_SUB,eta_A_DEC)

    eta_B_KO  = -0.30 + 0.55*ZB("KDpm") - 0.45*(0.55*(-ZA("KDtakenpm")) + 0.25*(-ZA("KDlast12m")) + 0.20*(-ZA("SSApm"))) + 0.20*ZB("HeadRate")
    eta_B_SUB = -0.50 + 0.60*ZB("Sub15") + 0.45*ZB("TDAcc") - 0.55*ZA("TDD") + 0.25*ZB("TopCtl")
    eta_B_DEC = -0.10 + 0.40*(0.60*ZB("Attpm") + 0.40*ZB("LateRet")) + 0.30*ZB("CARDIO_ret") - 0.25*(ZA("FinishRate")+ZB("FinishRate"))
    qB_KO,qB_SUB,qB_DEC = softmax3(eta_B_KO,eta_B_SUB,eta_B_DEC)
    return dict(qA_KO=qA_KO,qA_SUB=qA_SUB,qA_DEC=qA_DEC,qB_KO=qB_KO,qB_SUB=qB_SUB,qB_DEC=qB_DEC)

def pick(df, name):
    r = df[df["Name"].str.lower()==name.lower()]
    if r.empty: raise ValueError(f"Fighter not found: {name}")
    return {k:(v if pd.notna(v) else 0) for k,v in r.iloc[0].to_dict().items()}

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(HTML)

@app.get("/api/roster")
def api_roster():
    df = pd.read_csv(ROSTER)
    names = sorted(df["Name"].dropna().astype(str).unique().tolist())
    return JSONResponse(names)

@app.get("/api/predict")
def api_predict(a: str, b: str):
    df = pd.read_csv(ROSTER)
    A, B = pick(df, a), pick(df, b)
    R_A, R_B = rating(A,B)
    P_A = 1/(1+np.exp(-1.35*(0.80*(R_A-R_B))))
    m = methods(A,B)
    out = dict(
        P_A=float(P_A),
        P_A_KO=float(P_A*m["qA_KO"]), P_A_SUB=float(P_A*m["qA_SUB"]), P_A_DEC=float(P_A*m["qA_DEC"]),
        P_B_KO=float((1-P_A)*m["qB_KO"]), P_B_SUB=float((1-P_A)*m["qB_SUB"]), P_B_DEC=float((1-P_A)*m["qB_DEC"]),
        R_A=float(R_A), R_B=float(R_B),
    )
    return JSONResponse(out)
# --- ADMIN SCRAPER (FastAPI) ---
import os, base64, json
from pathlib import Path
import requests
from fastapi import HTTPException, Request
from full_roster_scraper import build_roster

# Use your existing FastAPI instance (usually called "app" or "api")
try:
    app  # if "app" exists, use it
except NameError:
    try:
        app = api  # if "api" exists, use it
    except NameError:
        from fastapi import FastAPI
        app = FastAPI()  # fallback (rarely needed)

def _upload_to_github(path: Path):
    repo   = os.environ["GH_REPO"]         # e.g. "jcj1996-ufc/MMA-model"
    branch = os.environ.get("GH_BRANCH", "main")
    token  = os.environ["GH_PAT"]

    api_url = f"https://api.github.com/repos/{repo}/contents/data/roster.csv"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    # get current SHA if file exists
    sha = None
    r = requests.get(api_url, params={"ref": branch}, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")

    content = base64.b64encode(path.read_bytes()).decode("utf-8")
    body = {
        "message": "Update roster.csv via Render scraper",
        "content": content,
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    r = requests.put(api_url, headers=headers, data=json.dumps(body))
    r.raise_for_status()

@app.post("/admin/scrape")
async def admin_scrape(request: Request):
    # Require secret key
    if request.query_params.get("key") != os.environ.get("ADMIN_KEY"):
        raise HTTPException(status_code=403, detail="forbidden")

    # Run scraper
    out = Path("/tmp/roster.csv")
    build_roster(out)

    # Upload to GitHub
    _upload_to_github(out)

    return {"ok": True, "wrote": str(out)}
