#!/usr/bin/env python3
"""Construye la base de datos estática de la Liga MX en data/*.json.

Solo usa la librería estándar de Python. Fuentes:
  1) CSV abiertos (CC0) de footballcsv en GitHub: resultados históricos.
  2) Archivos .csv que tú pongas en data/raw/ (por ejemplo el dataset CC0 de Kaggle).
  3) API pública de ESPN: partidos recientes + detalle (formaciones, jugadores, tarjetas).
Es incremental: solo descarga el detalle de los partidos que aún no tiene.
"""
import csv, io, json, os, re, sys, time, unicodedata, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, RAW = ROOT / "data", ROOT / "data" / "raw"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1"
CSV_REPOS = [r for r in os.environ.get("CSV_REPOS", "footballcsv/mexico").split(",") if r]
ESPN_FROM = int(os.environ.get("ESPN_FROM_YEAR", "2024"))
HEAD = {"User-Agent": "liga-mx-dashboard/1.0"}
if os.environ.get("GITHUB_TOKEN"):
    GH = dict(HEAD, Authorization="Bearer " + os.environ["GITHUB_TOKEN"])
else:
    GH = HEAD

def log(*a): print(*a, file=sys.stderr)

def fetch(url, headers=HEAD, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40) as r:
                return r.read()
        except Exception:
            if i == tries - 1: raise
            time.sleep(2 * (i + 1))

def jget(url, headers=HEAD): return json.loads(fetch(url, headers))

def norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))

ALIAS = {
 "america": "América", "clubamerica": "América", "guadalajara": "Guadalajara", "chivas": "Guadalajara",
 "cdguadalajara": "Guadalajara", "chivasguadalajara": "Guadalajara", "tigres": "Tigres UANL", "tigresuanl": "Tigres UANL",
 "uanl": "Tigres UANL", "monterrey": "Monterrey", "cfmonterrey": "Monterrey", "rayados": "Monterrey", "cruzazul": "Cruz Azul",
 "pumas": "Pumas UNAM", "pumasunam": "Pumas UNAM", "unam": "Pumas UNAM", "toluca": "Toluca", "pachuca": "Pachuca",
 "cfpachuca": "Pachuca", "leon": "León", "clubleon": "León", "santoslaguna": "Santos Laguna", "santos": "Santos Laguna",
 "atlas": "Atlas", "necaxa": "Necaxa", "clubnecaxa": "Necaxa", "puebla": "Puebla", "clubpuebla": "Puebla",
 "queretaro": "Querétaro", "queretarofc": "Querétaro", "mazatlan": "Mazatlán", "mazatlanfc": "Mazatlán",
 "juarez": "FC Juárez", "fcjuarez": "FC Juárez", "atleticosanluis": "Atlético San Luis", "sanluis": "Atlético San Luis",
 "tijuana": "Tijuana", "xolos": "Tijuana", "clubtijuana": "Tijuana", "clubtijuanaxoloitzcuintles": "Tijuana",
 "atlante": "Atlante", "veracruz": "Veracruz", "morelia": "Morelia", "lobosbuap": "Lobos BUAP", "dorados": "Dorados",
}
def canon(name):
    n = norm(name)
    return ALIAS.get(n) or ALIAS.get(re.sub(r"^(club|cf|fc|cd)", "", n)) or str(name).strip()

FORMATS = ["%Y-%m-%d", "%a %b %d %Y", "%a %b/%d %Y", "%b %d %Y", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%Y/%m/%d", "%d %b %Y", "%B %d, %Y"]
def parse_date(s):
    s = (s or "").strip().split("T")[0]
    for f in FORMATS:
        try: return datetime.strptime(s, f).date().isoformat()
        except ValueError: pass
    return None

def pick(h, names):
    for n in names:
        if h.get(n): return h[n]
    return ""

def parse_csv(text, season):
    out = []
    for r in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
        h = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        home = pick(h, ["home_team", "team 1", "team1", "home", "local"])
        away = pick(h, ["away_team", "team 2", "team2", "away", "visitante"])
        d = parse_date(pick(h, ["date", "fecha"]))
        hg, ag = pick(h, ["home_goals_fulltime", "home_goals"]), pick(h, ["away_goals_fulltime", "away_goals"])
        if not (hg.isdigit() and ag.isdigit()):
            m = re.search(r"(\d+)\s*[-–:]\s*(\d+)", pick(h, ["ft", "score", "resultado"]))
            if not m: continue
            hg, ag = m.group(1), m.group(2)
        if home and away and d:
            out.append([d, season or h.get("season") or d[:4], canon(home), canon(away), int(hg), int(ag), "c"])
    return out

def github_csvs(repo):
    tree = None
    for br in ("master", "main"):
        try:
            tree = jget(f"https://api.github.com/repos/{repo}/git/trees/{br}?recursive=1", GH)
            break
        except Exception: continue
    if not tree:
        log(f"AVISO: no pude listar {repo}"); return
    for t in tree.get("tree", []):
        p, base = t["path"], os.path.basename(t["path"]).lower()
        if not p.endswith(".csv"): continue
        if re.search(r"mx2|ascenso|copa|cup|femenil|expansion|premier|tdp|supercopa", p.lower()): continue
        if base.startswith(("mx1", "1-liga", "liga")) or "mx1" in base:
            yield p, f"https://raw.githubusercontent.com/{repo}/{br}/{p}"

def historical():
    rows = []
    for repo in CSV_REPOS:
        for p, url in github_csvs(repo):
            try:
                season = p.split("/")[0] if "/" in p else ""
                got = parse_csv(fetch(url).decode("utf-8", "replace"), season)
                log(f"  {p}: {len(got)} partidos"); rows += got
            except Exception as e: log(f"  AVISO {p}: {e}")
    for f in sorted(RAW.glob("*.csv")):
        got = parse_csv(f.read_text("utf-8", "replace"), "")
        log(f"  raw/{f.name}: {len(got)} partidos"); rows += got
    return rows

def tournaments():
    for y in range(ESPN_FROM, date.today().year + 1):
        yield f"Clausura {y}", f"{y}0101-{y}0630"
        yield f"Apertura {y}", f"{y}0701-{y}1231"

def espn_events():
    for name, rng in tournaments():
        try: j = jget(f"{ESPN}/scoreboard?dates={rng}&limit=1000")
        except Exception as e: log(f"AVISO ESPN {name}: {e}"); continue
        for e in j.get("events", []):
            if not e.get("status", {}).get("type", {}).get("completed"): continue
            c = e["competitions"][0]["competitors"]
            h = next(x for x in c if x["homeAway"] == "home"); a = next(x for x in c if x["homeAway"] == "away")
            yield e["id"], [e["date"][:10], name, canon(h["team"]["displayName"]), canon(a["team"]["displayName"]),
                            int(h.get("score") or 0), int(a.get("score") or 0), "e"]

def summarize(eid):
    j = jget(f"{ESPN}/summary?event={eid}"); out = {"t": {}, "p": []}; bs = {}
    for t in j.get("boxscore", {}).get("teams", []):
        bs[t["team"]["id"]] = {s["name"]: float(re.sub(r"[^0-9.]", "", s.get("displayValue", "") or "") or 0) for s in t.get("statistics", [])}
    for r in j.get("rosters", []):
        tid, m = r["team"]["id"], bs.get(r["team"]["id"], {})
        out["t"][tid] = {"f": r.get("formation") or "?", "pos": m.get("possessionPct", 0), "sh": m.get("totalShots", 0),
                         "sot": m.get("shotsOnTarget", 0), "co": m.get("wonCorners", 0), "fo": m.get("foulsCommitted", 0)}
        for p in r.get("roster", []):
            s = {x["name"]: float(x.get("value") or 0) for x in p.get("stats", [])}
            if not (p.get("starter") or s.get("subIns", 0) > 0 or s.get("appearances", 0) > 0): continue
            out["p"].append([p["athlete"]["id"], p["athlete"]["displayName"], tid, (p.get("position") or {}).get("abbreviation", ""),
                             int(s.get("totalGoals", 0)), int(s.get("goalAssists", 0)), int(s.get("yellowCards", 0)),
                             int(s.get("redCards", 0)), int(s.get("shotsOnTarget", 0)), int(s.get("saves", 0))])
    return out

def dump(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

def main():
    DATA.mkdir(exist_ok=True); RAW.mkdir(parents=True, exist_ok=True)
    log("1) Históricos abiertos"); merged = {(r[0], r[2], r[3]): r for r in historical()}
    log("2) Partidos recientes de ESPN"); ev = dict(espn_events())
    for r in ev.values(): merged[(r[0], r[2], r[3])] = r
    matches = sorted(merged.values(), key=lambda r: (r[0], r[2]))
    dump("matches.json", matches)
    teams = {}
    for d, s, h, a, hg, ag, _ in matches:
        for n, f, c in ((h, hg, ag), (a, ag, hg)):
            t = teams.setdefault(n, {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0})
            t["pj"] += 1; t["gf"] += f; t["gc"] += c
            t["g" if f > c else "p" if f < c else "e"] += 1
    dump("teams.json", teams)
    log("3) Detalle de partidos (formaciones, jugadores, tarjetas)")
    dpath = DATA / "details.json"
    details = json.loads(dpath.read_text("utf-8")) if dpath.exists() else {}
    todo = [i for i in ev if i not in details]; log(f"  {len(todo)} por descargar")
    def work(i):
        try: time.sleep(0.2); return i, summarize(i)
        except Exception as e: log(f"  fallo {i}: {e}"); return i, None
    with ThreadPoolExecutor(4) as ex:
        for n, (i, s) in enumerate(ex.map(work, todo), 1):
            if s: details[i] = s
            if n % 50 == 0: dump("details.json", details)
    dump("details.json", details)
    dump("meta.json", {"updated": datetime.now(timezone.utc).isoformat(timespec="minutes"), "matches": len(matches), "details": len(details),
        "schema": "matches=[fecha,temporada,local,visitante,golesLocal,golesVisita,fuente(c=csv,e=espn)]",
        "sources": ["footballcsv (CC0)", "data/raw (tus CSV)", "ESPN API pública no oficial"]})
    log(f"Listo: {len(matches)} partidos, {len(details)} con detalle")

if __name__ == "__main__": main()
