"""
Generates hradec_scout_hub.html — a self-contained scouting dashboard for FC Hradec Kralove.
Run:  python generate_hradec_hub.py
"""
import requests, json, numpy as np, pandas as pd
from datetime import date
from pathlib import Path

# ── Auth ──────────────────────────────────────────────────────────────────────
USERNAME = "marclambertsmedia@gmail.com"
PASSWORD = "Meneertosti@1!"
BASE_URL = "https://api.impect.com/v5/customerapi"
AUTH_URL = "https://login.impect.com/auth/realms/production/protocol/openid-connect/token"

resp = requests.post(AUTH_URL, data={"grant_type":"password","client_id":"api","username":USERNAME,"password":PASSWORD})
resp.raise_for_status()
HEADERS = {"Authorization": f"Bearer {resp.json()['access_token']}"}
print("✓ Authenticated")

def unwrap(r):
    r.raise_for_status()
    return r.json()["data"]

HK_ITERATION  = 1421
REC_ITERATION = 1454
HK_SQUAD_ID   = 3636

ALL_POSITIONS = ",".join([
    "GOALKEEPER","CENTRAL_DEFENDER","RIGHT_WINGBACK_DEFENDER","LEFT_WINGBACK_DEFENDER",
    "DEFENSE_MIDFIELD","CENTRAL_MIDFIELD","RIGHT_WINGER","LEFT_WINGER",
    "ATTACKING_MIDFIELD","CENTER_FORWARD"
])

RADAR_LABELS = ["Overall","Offensive","Defensive","Progression","Receiving","Duels","Scoring"]
RADAR_COLS   = ["IMPECT_SCORE_PACKING","OFFENSIVE_IMPECT_SCORE_PACKING","DEFENSIVE_IMPECT_SCORE_PACKING",
                "PROGRESSION_SCORE_PACKING","RECEIVING_SCORE_PACKING","INTERVENTIONS_SCORE_PACKING","SCORER_SCORE"]

POSITION_METRICS = {
    "GOALKEEPER":              ["IMPECT_SCORE_PACKING","DEFENSIVE_IMPECT_SCORE_PACKING","INTERVENTIONS_SCORE_PACKING"],
    "CENTRAL_DEFENDER":        ["DEFENSIVE_IMPECT_SCORE_PACKING","INTERVENTIONS_SCORE_PACKING","PROGRESSION_SCORE_PACKING","GROUND_DUEL_SCORE"],
    "RIGHT_WINGBACK_DEFENDER": ["PROGRESSION_SCORE_PACKING","OFFENSIVE_IMPECT_SCORE_PACKING","DEFENSIVE_IMPECT_SCORE_PACKING","LOW_CROSS_SCORE"],
    "LEFT_WINGBACK_DEFENDER":  ["PROGRESSION_SCORE_PACKING","OFFENSIVE_IMPECT_SCORE_PACKING","DEFENSIVE_IMPECT_SCORE_PACKING","LOW_CROSS_SCORE"],
    "DEFENSE_MIDFIELD":        ["IMPECT_SCORE_PACKING","INTERVENTIONS_SCORE_PACKING","LOW_PASS_SCORE","RECEIVING_SCORE_PACKING"],
    "CENTRAL_MIDFIELD":        ["IMPECT_SCORE_PACKING","PROGRESSION_SCORE_PACKING","LOW_PASS_SCORE","RECEIVING_SCORE_PACKING"],
    "RIGHT_WINGER":            ["OFFENSIVE_IMPECT_SCORE_PACKING","PROGRESSION_SCORE_PACKING","DRIBBLE_SCORE","SCORER_SCORE"],
    "LEFT_WINGER":             ["OFFENSIVE_IMPECT_SCORE_PACKING","PROGRESSION_SCORE_PACKING","DRIBBLE_SCORE","SCORER_SCORE"],
    "ATTACKING_MIDFIELD":      ["OFFENSIVE_IMPECT_SCORE_PACKING","PROGRESSION_SCORE_PACKING","LOW_PASS_SCORE","SCORER_SCORE"],
    "CENTER_FORWARD":          ["OFFENSIVE_IMPECT_SCORE_PACKING","SCORER_SCORE","IMPECT_SCORE_PACKING","RECEIVING_SCORE_PACKING"],
}

# ── Helpers ───────────────────────────────────────────────────────────────────
kpi_names   = {k["id"]: k["name"] for k in unwrap(requests.get(f"{BASE_URL}/kpis",         headers=HEADERS))}
score_names = {s["id"]: s["name"] for s in unwrap(requests.get(f"{BASE_URL}/player-scores", headers=HEADERS))}

def expand_nested(raw, id_col, val_col, names):
    rows = []
    for rec in raw:
        for item in rec.get(val_col, []):
            rows.append({"playerId": rec["playerId"], "col": names.get(item[id_col], str(item[id_col])), "value": item["value"]})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).groupby(["playerId","col"])["value"].mean().unstack("col").reset_index()

def fetch_league(iteration_id, squad_map):
    all_kpis, all_scores, all_pos, dur = [], [], [], []
    for i, (squad_id, squad_name) in enumerate(squad_map.items()):
        print(f"  [{i+1}/{len(squad_map)}] {squad_name}", end="\r")
        base = f"{BASE_URL}/iterations/{iteration_id}/squads/{squad_id}"
        try:
            raw = unwrap(requests.get(f"{base}/player-kpis", headers=HEADERS))
            dur.append(pd.DataFrame([{"playerId": r["playerId"], "squadId": squad_id, "squadName": squad_name,
                "playDuration": r["playDuration"], "matchShare": r["matchShare"], "position": r.get("position")} for r in raw]))
            df = expand_nested(raw, "kpiId", "kpis", kpi_names); df["squadId"] = squad_id; all_kpis.append(df)
        except: pass
        try:
            raw = unwrap(requests.get(f"{base}/player-scores", headers=HEADERS))
            df = expand_nested(raw, "playerScoreId", "playerScores", score_names); df["squadId"] = squad_id; all_scores.append(df)
        except: pass
        try:
            raw = unwrap(requests.get(f"{base}/positions/{ALL_POSITIONS}/player-scores", headers=HEADERS))
            df = expand_nested(raw, "playerScoreId", "playerScores", score_names); df["squadId"] = squad_id; all_pos.append(df)
        except: pass

    print()
    dur_df  = pd.concat(dur, ignore_index=True)
    base_df = dur_df.groupby("playerId", as_index=False).agg(
        playDuration=("playDuration","sum"), matchShare=("matchShare","sum"),
        squadId=("squadId","last"), squadName=("squadName","last"), position=("position","last"))

    def avg_wide(frames, suffix=""):
        df = pd.concat(frames, ignore_index=True)
        cols = [c for c in df.columns if c not in ("playerId","squadId")]
        out = df.groupby("playerId", as_index=False)[cols].mean()
        if suffix: out.columns = ["playerId"] + [f"{c}{suffix}" for c in out.columns[1:]]
        return out

    out = base_df
    if all_kpis:   out = out.merge(avg_wide(all_kpis),        on="playerId", how="left")
    if all_scores: out = out.merge(avg_wide(all_scores),       on="playerId", how="left")
    if all_pos:    out = out.merge(avg_wide(all_pos, "_pos"),  on="playerId", how="left")
    return out

def get_player_info(iteration_id):
    raw = unwrap(requests.get(f"{BASE_URL}/iterations/{iteration_id}/players", headers=HEADERS))
    df  = pd.json_normalize(raw)[["id","firstname","lastname","commonname","birthdate","leg"]]
    df["age"] = pd.to_datetime(df["birthdate"], errors="coerce").apply(
        lambda b: (date.today() - b.date()).days // 365 if pd.notna(b) else None)
    return df.rename(columns={"id":"playerId"})

def add_percentiles(df, cols):
    for col in cols:
        if col in df.columns:
            df[f"{col}_pct"] = df.groupby("position")[col].rank(pct=True).round(3)
    return df

def recruitment_score(row):
    metrics = POSITION_METRICS.get(row["position"], [])
    vals = [row.get(f"{m}_pct") for m in metrics if pd.notna(row.get(f"{m}_pct"))]
    return round(float(np.mean(vals)), 3) if vals else None

# ── Fetch Recruitment pool (2nd div) ─────────────────────────────────────────
print(f"\nFetching recruitment pool (iteration {REC_ITERATION})...")
rec_squads = {s["id"]: s["name"] for s in unwrap(requests.get(f"{BASE_URL}/iterations/{REC_ITERATION}/squads", headers=HEADERS))}
rec_df     = fetch_league(REC_ITERATION, rec_squads)
rec_df     = rec_df.merge(get_player_info(REC_ITERATION), on="playerId", how="left")
rec_df     = add_percentiles(rec_df, RADAR_COLS)
rec_df["recruitment_score"]     = rec_df.apply(recruitment_score, axis=1)
rec_df["recruitment_score_pct"] = rec_df.groupby("position")["recruitment_score"].rank(pct=True).round(3)
print(f"✓ {len(rec_df)} recruitment players")

# ── Fetch Tracking pool (Czech top flight) ────────────────────────────────────
print(f"\nFetching tracking pool (iteration {HK_ITERATION})...")
hk_squads  = {s["id"]: s["name"] for s in unwrap(requests.get(f"{BASE_URL}/iterations/{HK_ITERATION}/squads", headers=HEADERS))}
hk_df      = fetch_league(HK_ITERATION, hk_squads)
hk_df      = hk_df.merge(get_player_info(HK_ITERATION), on="playerId", how="left")
hk_df      = add_percentiles(hk_df, RADAR_COLS)
print(f"✓ {len(hk_df)} league players for tracking")

# ── Serialize to JSON ─────────────────────────────────────────────────────────
def safe_val(v):
    if isinstance(v, float) and np.isnan(v): return None
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating,)): return round(float(v), 4)
    return v

def df_to_records(df, cols):
    rows = []
    for _, row in df[cols].iterrows():
        rows.append({c: safe_val(row[c]) for c in cols})
    return rows

# Columns for recruitment table
rec_cols = ["playerId","commonname","age","leg","position","squadName","playDuration","matchShare",
            "recruitment_score","recruitment_score_pct"] + \
           [f"{c}_pct" for c in RADAR_COLS if f"{c}_pct" in rec_df.columns] + \
           [c for c in RADAR_COLS if c in rec_df.columns]
rec_cols = [c for c in dict.fromkeys(rec_cols) if c in rec_df.columns]

# Columns for tracking (Hradec only vs full league)
hk_only = hk_df[hk_df["squadId"] == HK_SQUAD_ID].copy()
track_cols = ["playerId","commonname","age","leg","position","squadName","playDuration","matchShare"] + \
             [f"{c}_pct" for c in RADAR_COLS if f"{c}_pct" in hk_only.columns] + \
             [c for c in RADAR_COLS if c in hk_only.columns]
track_cols = [c for c in dict.fromkeys(track_cols) if c in hk_only.columns]

recruitment_json = json.dumps(df_to_records(rec_df, rec_cols))
tracking_json    = json.dumps(df_to_records(hk_only, track_cols))
squad_list_json  = json.dumps(sorted(rec_squads.values()))
position_list_json = json.dumps([
    "GOALKEEPER","CENTRAL_DEFENDER","RIGHT_WINGBACK_DEFENDER","LEFT_WINGBACK_DEFENDER",
    "DEFENSE_MIDFIELD","CENTRAL_MIDFIELD","RIGHT_WINGER","LEFT_WINGER",
    "ATTACKING_MIDFIELD","CENTER_FORWARD"
])
radar_labels_json = json.dumps(RADAR_LABELS)
radar_cols_json   = json.dumps([f"{c}_pct" for c in RADAR_COLS])
pos_metrics_json  = json.dumps({k: [f"{m}_pct" for m in v] for k, v in POSITION_METRICS.items()})

print("✓ Data serialized")

# ── HTML ──────────────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FC Hradec Králové — Scout Hub</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0f1117;color:#e2e8f0;min-height:100vh}}
  ::-webkit-scrollbar{{width:6px;height:6px}} ::-webkit-scrollbar-track{{background:#1a1f2e}} ::-webkit-scrollbar-thumb{{background:#3b4563;border-radius:3px}}

  /* Header */
  header{{background:linear-gradient(135deg,#1a237e,#283593);padding:18px 24px;display:flex;align-items:center;gap:16px;box-shadow:0 2px 12px rgba(0,0,0,.4)}}
  header h1{{font-size:1.4rem;font-weight:700;letter-spacing:.5px}}
  header span{{font-size:.85rem;color:#90caf9;margin-left:auto}}

  /* Tabs */
  nav{{background:#161b2e;border-bottom:1px solid #2a3150;padding:0 24px;display:flex;gap:4px}}
  nav button{{padding:14px 22px;background:none;border:none;border-bottom:3px solid transparent;color:#8892b0;cursor:pointer;font-size:.9rem;font-weight:600;transition:all .2s}}
  nav button.active{{color:#64b5f6;border-bottom-color:#64b5f6}}
  nav button:hover:not(.active){{color:#cdd6f4}}

  /* Sections */
  .section{{display:none;padding:24px}} .section.active{{display:block}}

  /* Filters */
  .filters{{background:#161b2e;border:1px solid #2a3150;border-radius:10px;padding:16px;display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px;align-items:flex-end}}
  .filter-group{{display:flex;flex-direction:column;gap:4px}}
  .filter-group label{{font-size:.75rem;color:#8892b0;text-transform:uppercase;letter-spacing:.5px}}
  .filters select,.filters input{{background:#0f1117;border:1px solid #2a3150;color:#e2e8f0;padding:7px 10px;border-radius:6px;font-size:.85rem;min-width:140px}}
  .filters input[type=range]{{padding:8px 0;min-width:120px}}
  .filter-val{{font-size:.8rem;color:#64b5f6;text-align:center}}
  .filters button{{background:#1565c0;color:#fff;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:.85rem;font-weight:600}}
  .filters button:hover{{background:#1976d2}}

  /* Summary cards */
  .cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:20px}}
  .card{{background:#161b2e;border:1px solid #2a3150;border-radius:10px;padding:14px;cursor:pointer;transition:border-color .2s}}
  .card:hover{{border-color:#64b5f6}}
  .card .pos{{font-size:.7rem;color:#8892b0;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}}
  .card .name{{font-size:.95rem;font-weight:700;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .card .club{{font-size:.78rem;color:#8892b0;margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .card .score-bar{{height:6px;background:#1e2a45;border-radius:3px;overflow:hidden}}
  .card .score-bar-fill{{height:100%;border-radius:3px;background:linear-gradient(90deg,#1565c0,#42a5f5)}}
  .card .score-val{{font-size:.78rem;color:#64b5f6;margin-top:4px}}

  /* Table */
  .table-wrap{{overflow-x:auto;border-radius:10px;border:1px solid #2a3150}}
  table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  thead th{{background:#1a1f2e;padding:10px 12px;text-align:left;color:#8892b0;font-weight:600;text-transform:uppercase;font-size:.72rem;letter-spacing:.5px;white-space:nowrap;cursor:pointer;user-select:none;position:sticky;top:0}}
  thead th:hover{{color:#e2e8f0}} thead th .sort-icon{{margin-left:4px;opacity:.4}}
  thead th.sorted .sort-icon{{opacity:1;color:#64b5f6}}
  tbody tr{{border-bottom:1px solid #1a1f2e;cursor:pointer;transition:background .15s}}
  tbody tr:hover{{background:#1a1f2e}}
  tbody tr.highlighted{{background:#1e2d4d}}
  td{{padding:9px 12px;white-space:nowrap}}
  .pct-cell{{position:relative}} .pct-bar{{position:absolute;left:0;top:0;bottom:0;opacity:.15;border-radius:0}}
  .pct-text{{position:relative;z-index:1;font-weight:600}}
  .green{{color:#4caf50}} .amber{{color:#ffa726}} .red{{color:#ef5350}} .blue{{color:#64b5f6}}
  .badge{{display:inline-block;padding:2px 7px;border-radius:4px;font-size:.72rem;font-weight:600;background:#1a237e;color:#90caf9}}

  /* Radar modal */
  .modal-bg{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100;align-items:center;justify-content:center}}
  .modal-bg.open{{display:flex}}
  .modal{{background:#161b2e;border:1px solid #2a3150;border-radius:14px;padding:28px;max-width:680px;width:95%;position:relative;max-height:90vh;overflow-y:auto}}
  .modal-close{{position:absolute;top:14px;right:16px;background:none;border:none;color:#8892b0;font-size:1.4rem;cursor:pointer}}
  .modal-close:hover{{color:#e2e8f0}}
  .modal h2{{font-size:1.2rem;margin-bottom:4px}} .modal .sub{{color:#8892b0;font-size:.85rem;margin-bottom:20px}}
  .modal-grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;align-items:start}}
  @media(max-width:560px){{.modal-grid{{grid-template-columns:1fr}}}}
  .stat-row{{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid #1e2540;font-size:.83rem}}
  .stat-row:last-child{{border-bottom:none}}
  .pct-pill{{padding:2px 8px;border-radius:10px;font-size:.75rem;font-weight:700}}

  /* Tracking cards */
  .track-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
  .track-card{{background:#161b2e;border:1px solid #2a3150;border-radius:10px;padding:16px;cursor:pointer;transition:border-color .2s}}
  .track-card:hover{{border-color:#64b5f6}}
  .track-card .tc-head{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px}}
  .track-card .tc-name{{font-size:1rem;font-weight:700}} .track-card .tc-pos{{font-size:.75rem;color:#8892b0}}
  .track-card .tc-age{{font-size:.78rem;color:#8892b0}}
  .metric-row{{display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:.78rem}}
  .metric-label{{width:110px;color:#8892b0;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .metric-bar-bg{{flex:1;height:6px;background:#1e2a45;border-radius:3px;overflow:hidden}}
  .metric-bar-fill{{height:100%;border-radius:3px}}
  .metric-val{{width:36px;text-align:right;font-weight:600}}

  /* Scouting search */
  .scout-search{{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}}
  .scout-search input{{flex:1;min-width:220px;background:#161b2e;border:1px solid #2a3150;color:#e2e8f0;padding:10px 14px;border-radius:8px;font-size:.9rem}}
  .scout-results{{background:#161b2e;border:1px solid #2a3150;border-radius:8px;max-height:240px;overflow-y:auto;display:none}}
  .scout-results.open{{display:block}}
  .scout-result-item{{padding:10px 14px;cursor:pointer;border-bottom:1px solid #1e2540;display:flex;gap:10px;align-items:center;font-size:.85rem}}
  .scout-result-item:hover{{background:#1a1f2e}}
  .scout-result-item .ri-name{{font-weight:600}} .scout-result-item .ri-meta{{color:#8892b0;font-size:.78rem}}
  .scout-panel{{background:#161b2e;border:1px solid #2a3150;border-radius:10px;padding:24px;display:none}}
  .scout-panel.open{{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:start}}
  @media(max-width:600px){{.scout-panel.open{{grid-template-columns:1fr}}}}
  .scout-panel h2{{grid-column:1/-1;font-size:1.2rem;margin-bottom:4px}}
  .scout-panel .sp-meta{{grid-column:1/-1;color:#8892b0;font-size:.85rem;margin-bottom:8px}}

  /* Util */
  .empty{{text-align:center;padding:48px;color:#4a5568}}
  .tag{{background:#1a237e;color:#90caf9;padding:2px 8px;border-radius:4px;font-size:.72rem;font-weight:600;display:inline-block}}
  .section-title{{font-size:1.05rem;font-weight:700;color:#90caf9;margin-bottom:14px;display:flex;align-items:center;gap:8px}}
  .count-badge{{background:#1e2a45;color:#8892b0;padding:2px 8px;border-radius:10px;font-size:.75rem}}
</style>
</head>
<body>

<header>
  <div>
    <div style="font-size:.75rem;color:#90caf9;text-transform:uppercase;letter-spacing:1px">FC Hradec Králové</div>
    <h1>Scout Hub</h1>
  </div>
  <span>Chance Národní Liga 25/26 &nbsp;|&nbsp; Czech Fortuna Liga 25/26</span>
</header>

<nav>
  <button class="active" onclick="switchTab('recruitment',this)">⚡ Recruitment</button>
  <button onclick="switchTab('tracking',this)">📊 Player Tracking</button>
  <button onclick="switchTab('scouting',this)">🔍 Scouting</button>
</nav>

<!-- ═══════════════════════ RECRUITMENT ═══════════════════════ -->
<div id="tab-recruitment" class="section active">
  <div class="filters">
    <div class="filter-group">
      <label>Position</label>
      <select id="f-pos" onchange="applyFilters()">
        <option value="">All positions</option>
      </select>
    </div>
    <div class="filter-group">
      <label>Max age</label>
      <input type="range" id="f-age" min="16" max="35" value="28" oninput="document.getElementById('f-age-v').textContent=this.value;applyFilters()">
      <div class="filter-val" id="f-age-v">28</div>
    </div>
    <div class="filter-group">
      <label>Min minutes</label>
      <input type="range" id="f-min" min="0" max="9000" step="270" value="2700" oninput="document.getElementById('f-min-v').textContent=Math.round(this.value/60)+'m';applyFilters()">
      <div class="filter-val" id="f-min-v">45m</div>
    </div>
    <div class="filter-group">
      <label>Club</label>
      <select id="f-club" onchange="applyFilters()"><option value="">All clubs</option></select>
    </div>
    <div class="filter-group">
      <label>Search name</label>
      <input type="text" id="f-name" placeholder="Player name…" oninput="applyFilters()">
    </div>
    <button onclick="resetFilters()">Reset</button>
  </div>

  <div id="pos-cards" class="cards"></div>

  <div class="section-title">
    All candidates <span class="count-badge" id="rec-count"></span>
  </div>
  <div class="table-wrap">
    <table id="rec-table">
      <thead>
        <tr>
          <th onclick="sortTable('rec',0,'s')">Name <span class="sort-icon">↕</span></th>
          <th onclick="sortTable('rec',1,'n')">Age <span class="sort-icon">↕</span></th>
          <th onclick="sortTable('rec',2,'s')">Pos <span class="sort-icon">↕</span></th>
          <th onclick="sortTable('rec',3,'s')">Club <span class="sort-icon">↕</span></th>
          <th onclick="sortTable('rec',4,'n')">Min <span class="sort-icon">↕</span></th>
          <th onclick="sortTable('rec',5,'n')">Rec Score <span class="sort-icon">↕</span></th>
          <th onclick="sortTable('rec',6,'n')">Overall <span class="sort-icon">↕</span></th>
          <th onclick="sortTable('rec',7,'n')">Offensive <span class="sort-icon">↕</span></th>
          <th onclick="sortTable('rec',8,'n')">Defensive <span class="sort-icon">↕</span></th>
          <th onclick="sortTable('rec',9,'n')">Progression <span class="sort-icon">↕</span></th>
          <th onclick="sortTable('rec',10,'n')">Scoring <span class="sort-icon">↕</span></th>
        </tr>
      </thead>
      <tbody id="rec-tbody"></tbody>
    </table>
  </div>
</div>

<!-- ═══════════════════════ TRACKING ═══════════════════════ -->
<div id="tab-tracking" class="section">
  <div class="filters">
    <div class="filter-group">
      <label>Position</label>
      <select id="t-pos" onchange="renderTracking()"><option value="">All</option></select>
    </div>
    <div class="filter-group">
      <label>Sort by</label>
      <select id="t-sort" onchange="renderTracking()">
        <option value="IMPECT_SCORE_PACKING_pct">Overall Impact</option>
        <option value="OFFENSIVE_IMPECT_SCORE_PACKING_pct">Offensive</option>
        <option value="DEFENSIVE_IMPECT_SCORE_PACKING_pct">Defensive</option>
        <option value="PROGRESSION_SCORE_PACKING_pct">Progression</option>
        <option value="SCORER_SCORE_pct">Scoring</option>
      </select>
    </div>
  </div>
  <div class="section-title">FC Hradec Králové — Player Tracking vs Czech Fortuna Liga</div>
  <div id="track-grid" class="track-grid"></div>
</div>

<!-- ═══════════════════════ SCOUTING ═══════════════════════ -->
<div id="tab-scouting" class="section">
  <div class="section-title">Individual Player Scout Report</div>
  <div class="scout-search">
    <input type="text" id="scout-input" placeholder="Search any player from either league…" oninput="scoutSearch(this.value)" autocomplete="off">
  </div>
  <div id="scout-results" class="scout-results"></div>
  <div id="scout-panel" class="scout-panel">
    <h2 id="sp-name"></h2>
    <div class="sp-meta" id="sp-meta"></div>
    <div style="max-width:340px"><canvas id="radar-canvas"></canvas></div>
    <div id="sp-stats"></div>
  </div>
</div>

<!-- ═══════════════════════ MODAL ═══════════════════════ -->
<div class="modal-bg" id="modal-bg" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <button class="modal-close" onclick="closeModal()">✕</button>
    <h2 id="m-name"></h2>
    <div class="sub" id="m-meta"></div>
    <div class="modal-grid">
      <div style="max-width:280px"><canvas id="modal-radar"></canvas></div>
      <div id="m-stats"></div>
    </div>
  </div>
</div>

<script>
// ── Data ─────────────────────────────────────────────────────────────────────
const REC_DATA     = {recruitment_json};
const TRACK_DATA   = {tracking_json};
const SQUADS       = {squad_list_json};
const POSITIONS    = {position_list_json};
const RADAR_LABELS = {radar_labels_json};
const RADAR_COLS   = {radar_cols_json};
const POS_METRICS  = {pos_metrics_json};
const ALL_PLAYERS  = [...REC_DATA.map(p=>{{...p,_league:'2nd div'}}),
                       ...TRACK_DATA.map(p=>{{...p,_league:'Fortuna Liga'}})];

// ── Populate filters ──────────────────────────────────────────────────────────
const posFilter = document.getElementById('f-pos');
POSITIONS.forEach(p=>{{ const o=document.createElement('option');o.value=p;o.text=posLabel(p);posFilter.appendChild(o); }});
const clubFilter = document.getElementById('f-club');
SQUADS.forEach(s=>{{ const o=document.createElement('option');o.value=s;o.text=s;clubFilter.appendChild(o); }});
const tPosFilter = document.getElementById('t-pos');
POSITIONS.forEach(p=>{{ const o=document.createElement('option');o.value=p;o.text=posLabel(p);tPosFilter.appendChild(o); }});

function posLabel(p){{
  return {{GOALKEEPER:'GK',CENTRAL_DEFENDER:'CB',RIGHT_WINGBACK_DEFENDER:'RWB',LEFT_WINGBACK_DEFENDER:'LWB',
           DEFENSE_MIDFIELD:'DM',CENTRAL_MIDFIELD:'CM',RIGHT_WINGER:'RW',LEFT_WINGER:'LW',
           ATTACKING_MIDFIELD:'AM',CENTER_FORWARD:'CF'}}[p] || p;
}}

// ── Utils ─────────────────────────────────────────────────────────────────────
function pctColor(v){{ if(v==null) return ''; if(v>=.7) return 'green'; if(v>=.4) return 'amber'; return 'red'; }}
function pctBg(v){{ if(v==null) return '#333'; if(v>=.7) return '#2e7d32'; if(v>=.4) return '#e65100'; return '#b71c1c'; }}
function fmtPct(v){{ return v==null ? '—' : Math.round(v*100); }}
function fmtMin(s){{ return s==null ? '—' : Math.round(s/60)+"'"; }}
function posShort(p){{ return posLabel(p); }}

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(id, btn){{
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  btn.classList.add('active');
}}

// ── Recruitment ───────────────────────────────────────────────────────────────
let recData = [...REC_DATA];
let recSort = {{col:5, dir:-1, type:'n'}};

function applyFilters(){{
  const pos   = document.getElementById('f-pos').value;
  const maxAge= +document.getElementById('f-age').value;
  const minMin= +document.getElementById('f-min').value;
  const club  = document.getElementById('f-club').value;
  const name  = document.getElementById('f-name').value.toLowerCase();
  recData = REC_DATA.filter(p=>
    (!pos  || p.position===pos) &&
    (!p.age|| p.age<=maxAge) &&
    (p.playDuration==null||p.playDuration>=minMin) &&
    (!club || p.squadName===club) &&
    (!name || (p.commonname||'').toLowerCase().includes(name))
  );
  renderRecTable();
  renderPosCards();
}}

function resetFilters(){{
  document.getElementById('f-pos').value='';
  document.getElementById('f-age').value=28; document.getElementById('f-age-v').textContent=28;
  document.getElementById('f-min').value=2700; document.getElementById('f-min-v').textContent="45m";
  document.getElementById('f-club').value='';
  document.getElementById('f-name').value='';
  applyFilters();
}}

function renderPosCards(){{
  const el = document.getElementById('pos-cards');
  const pos = document.getElementById('f-pos').value;
  const positions = pos ? [pos] : POSITIONS;
  const best = {{}};
  positions.forEach(p=>{{
    const players = recData.filter(x=>x.position===p).sort((a,b)=>(b.recruitment_score_pct||0)-(a.recruitment_score_pct||0));
    if(players.length) best[p]=players[0];
  }});
  el.innerHTML = Object.entries(best).map(([p,pl])=>{{
    const pct = pl.recruitment_score_pct||0;
    return `<div class="card" onclick="openModal(REC_DATA.find(x=>x.playerId===${{pl.playerId}}))">
      <div class="pos">${{posLabel(p)}}</div>
      <div class="name">${{pl.commonname||'Unknown'}}</div>
      <div class="club">${{pl.squadName||''}}</div>
      <div class="score-bar"><div class="score-bar-fill" style="width:${{Math.round(pct*100)}}%"></div></div>
      <div class="score-val">${{Math.round(pct*100)}}th pct · age ${{pl.age||'?'}}</div>
    </div>`;
  }}).join('');
}}

function rowData(p){{
  return [
    p.commonname||'', p.age, posShort(p.position), p.squadName,
    Math.round((p.playDuration||0)/60),
    p.recruitment_score_pct, p.IMPECT_SCORE_PACKING_pct,
    p.OFFENSIVE_IMPECT_SCORE_PACKING_pct, p.DEFENSIVE_IMPECT_SCORE_PACKING_pct,
    p.PROGRESSION_SCORE_PACKING_pct, p.SCORER_SCORE_pct
  ];
}}

function pctCell(v){{
  if(v==null) return '<td>—</td>';
  const pct=Math.round(v*100);
  return `<td class="pct-cell">
    <div class="pct-bar" style="width:${{pct}}%;background:${{pctBg(v)}}"></div>
    <span class="pct-text ${{pctColor(v)}}">${{pct}}</span>
  </td>`;
}}

function renderRecTable(){{
  const sorted = [...recData].sort((a,b)=>{{
    const av=rowData(a)[recSort.col], bv=rowData(b)[recSort.col];
    if(av==null&&bv==null) return 0; if(av==null) return 1; if(bv==null) return -1;
    return recSort.type==='n' ? (bv-av)*recSort.dir : av.localeCompare(bv)*recSort.dir;
  }});
  document.getElementById('rec-count').textContent = sorted.length+' players';
  document.getElementById('rec-tbody').innerHTML = sorted.map(p=>{{
    const d=rowData(p);
    return `<tr onclick="openModal(REC_DATA.find(x=>x.playerId===${{p.playerId}}))">
      <td><strong>${{d[0]}}</strong></td>
      <td>${{d[1]||'?'}}</td>
      <td><span class="badge">${{d[2]}}</span></td>
      <td style="color:#8892b0">${{d[3]||''}}</td>
      <td style="color:#8892b0">${{d[4]}}'</td>
      ${{pctCell(d[5])}}${{pctCell(d[6])}}${{pctCell(d[7])}}${{pctCell(d[8])}}${{pctCell(d[9])}}${{pctCell(d[10])}}
    </tr>`;
  }}).join('');
  // update sort icons
  document.querySelectorAll('#rec-table thead th').forEach((th,i)=>{{
    th.classList.toggle('sorted',i===recSort.col);
    const icon=th.querySelector('.sort-icon');
    if(icon) icon.textContent = i===recSort.col ? (recSort.dir===-1?'↓':'↑') : '↕';
  }});
}}

let recSortDirs = [1,1,1,1,1,-1,-1,-1,-1,-1,-1];
function sortTable(tbl,col,type){{
  if(tbl==='rec'){{
    recSortDirs[col]*=-1;
    recSort={{col,dir:recSortDirs[col],type}};
    renderRecTable();
  }}
}}

// ── Tracking ──────────────────────────────────────────────────────────────────
const METRIC_LABELS = {{
  IMPECT_SCORE_PACKING_pct:'Overall',OFFENSIVE_IMPECT_SCORE_PACKING_pct:'Offensive',
  DEFENSIVE_IMPECT_SCORE_PACKING_pct:'Defensive',PROGRESSION_SCORE_PACKING_pct:'Progression',
  RECEIVING_SCORE_PACKING_pct:'Receiving',INTERVENTIONS_SCORE_PACKING_pct:'Duels',
  SCORER_SCORE_pct:'Scoring'
}};

function renderTracking(){{
  const pos  = document.getElementById('t-pos').value;
  const sort = document.getElementById('t-sort').value;
  let data = pos ? TRACK_DATA.filter(p=>p.position===pos) : [...TRACK_DATA];
  data.sort((a,b)=>(b[sort]||0)-(a[sort]||0));
  document.getElementById('track-grid').innerHTML = data.map(p=>{{
    const overall = p.IMPECT_SCORE_PACKING_pct;
    const metrics = Object.entries(METRIC_LABELS).map(([k,label])=>{{
      const v = p[k];
      const pct = v!=null ? Math.round(v*100) : 0;
      return `<div class="metric-row">
        <div class="metric-label">${{label}}</div>
        <div class="metric-bar-bg"><div class="metric-bar-fill" style="width:${{pct}}%;background:${{pctBg(v)}}"></div></div>
        <div class="metric-val ${{pctColor(v)}}">${{pct}}</div>
      </div>`;
    }}).join('');
    return `<div class="track-card" onclick="scoutPlayer(TRACK_DATA.find(x=>x.playerId===${{p.playerId}}))">
      <div class="tc-head">
        <div>
          <div class="tc-name">${{p.commonname||'Unknown'}}</div>
          <div class="tc-pos"><span class="badge">${{posShort(p.position)}}</span></div>
        </div>
        <div class="tc-age">${{p.age||'?'}} yrs · ${{fmtMin(p.playDuration)}}</div>
      </div>
      ${{metrics}}
    </div>`;
  }}).join('') || '<div class="empty">No players found.</div>';
}}

// ── Scouting ──────────────────────────────────────────────────────────────────
let radarChart = null;

function scoutSearch(q){{
  const el = document.getElementById('scout-results');
  if(!q || q.length<2){{ el.classList.remove('open'); el.innerHTML=''; return; }}
  const matches = ALL_PLAYERS.filter(p=>(p.commonname||'').toLowerCase().includes(q.toLowerCase())).slice(0,20);
  el.innerHTML = matches.map(p=>`
    <div class="scout-result-item" onclick="scoutPlayer(p=${{JSON.stringify(p).replace(/"/g,'&quot;')}})">
      <div><div class="ri-name">${{p.commonname}}</div>
      <div class="ri-meta">${{posLabel(p.position)}} · ${{p.squadName||''}} · ${{p._league}}</div></div>
      <div class="tag">${{p.age||'?'}}</div>
    </div>`).join('');
  el.classList.toggle('open', matches.length>0);
}}

function scoutPlayer(p){{
  if(typeof p === 'string') p = JSON.parse(p);
  document.getElementById('scout-results').classList.remove('open');
  document.getElementById('scout-input').value = p.commonname||'';
  const panel = document.getElementById('scout-panel');
  panel.classList.add('open');
  document.getElementById('sp-name').textContent = p.commonname||'Unknown';
  document.getElementById('sp-meta').textContent =
    `${{posLabel(p.position)}} · ${{p.squadName||''}} · Age ${{p.age||'?'}} · ${{fmtMin(p.playDuration)}} played`;

  // Radar
  const radarData = RADAR_COLS.map(c=>Math.round((p[c]||0)*100));
  if(radarChart) radarChart.destroy();
  radarChart = buildRadar('radar-canvas', radarData);

  // Stats
  document.getElementById('sp-stats').innerHTML = Object.entries(METRIC_LABELS).map(([k,label])=>{{
    const v=p[k]; const pct=fmtPct(v);
    return `<div class="stat-row">
      <span>${{label}}</span>
      <span class="pct-pill" style="background:${{pctBg(v)}}20;color:${{pctColor(v)==='green'?'#4caf50':pctColor(v)==='amber'?'#ffa726':'#ef5350'}}">${{pct}}th</span>
    </div>`;
  }}).join('');
}}

// ── Modal (from recruitment table) ───────────────────────────────────────────
let modalChart = null;
function openModal(p){{
  if(!p) return;
  document.getElementById('m-name').textContent = p.commonname||'Unknown';
  document.getElementById('m-meta').textContent =
    `${{posLabel(p.position)}} · ${{p.squadName||''}} · Age ${{p.age||'?'}} · ${{fmtMin(p.playDuration)}} played`;
  const radarData = RADAR_COLS.map(c=>Math.round((p[c]||0)*100));
  if(modalChart) modalChart.destroy();
  modalChart = buildRadar('modal-radar', radarData);
  document.getElementById('m-stats').innerHTML = Object.entries(METRIC_LABELS).map(([k,label])=>{{
    const v=p[k]; const pct=fmtPct(v);
    return `<div class="stat-row">
      <span>${{label}}</span>
      <span class="pct-pill" style="background:${{pctBg(v)}}20;color:${{pctColor(v)==='green'?'#4caf50':pctColor(v)==='amber'?'#ffa726':'#ef5350'}}">${{pct}}th</span>
    </div>`;
  }}).join('');
  document.getElementById('modal-bg').classList.add('open');
}}
function closeModal(){{ document.getElementById('modal-bg').classList.remove('open'); }}

// ── Chart.js radar ────────────────────────────────────────────────────────────
function buildRadar(canvasId, data){{
  const ctx = document.getElementById(canvasId).getContext('2d');
  return new Chart(ctx,{{
    type:'radar',
    data:{{
      labels: RADAR_LABELS,
      datasets:[{{
        data, fill:true,
        backgroundColor:'rgba(100,181,246,.15)',
        borderColor:'#64b5f6',
        pointBackgroundColor:'#64b5f6',
        pointBorderColor:'#fff',
        pointRadius:4
      }}]
    }},
    options:{{
      animation:{{duration:400}},
      scales:{{r:{{
        min:0,max:100,
        grid:{{color:'rgba(255,255,255,.08)'}},
        angleLines:{{color:'rgba(255,255,255,.08)'}},
        ticks:{{stepSize:25,color:'#4a5568',backdropColor:'transparent',font:{{size:10}}}},
        pointLabels:{{color:'#90caf9',font:{{size:11}}}}
      }}}},
      plugins:{{legend:{{display:false}}}}
    }}
  }});
}}

// ── Init ──────────────────────────────────────────────────────────────────────
applyFilters();
renderTracking();
</script>
</body>
</html>"""

out = Path("/Users/marclamberts/Event data/hradec_scout_hub.html")
out.write_text(html, encoding="utf-8")
print(f"\n✓ Generated → {out}  ({out.stat().st_size//1024} KB)")
