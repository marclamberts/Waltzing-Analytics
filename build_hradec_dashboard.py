"""
FC Hradec Králové — Enhanced Jamestown Recruitment Dashboard v2
Pizza plots · Beeswarm · Scatter · Waffle · Bar graphs
Self-contained HTML, no server required.
"""

import os, json
import numpy as np
import pandas as pd

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "hradec_recruitment_2526.xlsx")
OUTPUT    = os.path.join(BASE_DIR, "hradec_recruitment_dashboard.html")

STAT_COLS = [
    "Goals per 90", "xG per 90", "Assists per 90", "xA per 90",
    "Progressive passes per 90", "Progressive runs per 90",
    "Touches in box per 90", "Defensive duels won, %",
    "Aerial duels won, %", "Dribbles per 90", "Successful dribbles, %",
    "Key passes per 90", "PAdj Interceptions",
    "Save rate, %", "Prevented goals per 90",
]

PIZZA_METRICS = {
    "GK": [
        {"key":"sv_pct",  "label":"Save Rate %",    "cat":"gk"},
        {"key":"pg90",    "label":"Prev Goals/90",   "cat":"gk"},
        {"key":"adw",     "label":"Aerial Won %",    "cat":"def"},
        {"key":"ddw",     "label":"Def Duels Won %", "cat":"def"},
        {"key":"pp90",    "label":"Prog Passes/90",  "cat":"pass"},
        {"key":"int90",   "label":"Interceptions/90","cat":"def"},
    ],
    "CB": [
        {"key":"ddw",     "label":"Def Duels Won %", "cat":"def"},
        {"key":"adw",     "label":"Aerial Won %",    "cat":"def"},
        {"key":"int90",   "label":"Interceptions/90","cat":"def"},
        {"key":"pp90",    "label":"Prog Passes/90",  "cat":"pass"},
        {"key":"pr90",    "label":"Prog Runs/90",    "cat":"pass"},
        {"key":"kp90",    "label":"Key Passes/90",   "cat":"pass"},
        {"key":"xg90",    "label":"xG/90",           "cat":"att"},
    ],
    "FB": [
        {"key":"ddw",     "label":"Def Duels Won %", "cat":"def"},
        {"key":"adw",     "label":"Aerial Won %",    "cat":"def"},
        {"key":"int90",   "label":"Interceptions/90","cat":"def"},
        {"key":"pr90",    "label":"Prog Runs/90",    "cat":"pass"},
        {"key":"pp90",    "label":"Prog Passes/90",  "cat":"pass"},
        {"key":"kp90",    "label":"Key Passes/90",   "cat":"pass"},
        {"key":"xa90",    "label":"xA/90",           "cat":"att"},
        {"key":"a90",     "label":"Assists/90",      "cat":"att"},
    ],
    "DM": [
        {"key":"int90",   "label":"Interceptions/90","cat":"def"},
        {"key":"ddw",     "label":"Def Duels Won %", "cat":"def"},
        {"key":"adw",     "label":"Aerial Won %",    "cat":"def"},
        {"key":"pp90",    "label":"Prog Passes/90",  "cat":"pass"},
        {"key":"kp90",    "label":"Key Passes/90",   "cat":"pass"},
        {"key":"pr90",    "label":"Prog Runs/90",    "cat":"pass"},
        {"key":"xa90",    "label":"xA/90",           "cat":"att"},
        {"key":"xg90",    "label":"xG/90",           "cat":"att"},
    ],
    "CM": [
        {"key":"pp90",    "label":"Prog Passes/90",  "cat":"pass"},
        {"key":"kp90",    "label":"Key Passes/90",   "cat":"pass"},
        {"key":"pr90",    "label":"Prog Runs/90",    "cat":"pass"},
        {"key":"xg90",    "label":"xG/90",           "cat":"att"},
        {"key":"xa90",    "label":"xA/90",           "cat":"att"},
        {"key":"g90",     "label":"Goals/90",        "cat":"att"},
        {"key":"a90",     "label":"Assists/90",      "cat":"att"},
        {"key":"int90",   "label":"Interceptions/90","cat":"def"},
        {"key":"ddw",     "label":"Def Duels Won %", "cat":"def"},
    ],
    "W": [
        {"key":"g90",     "label":"Goals/90",        "cat":"att"},
        {"key":"xg90",    "label":"xG/90",           "cat":"att"},
        {"key":"a90",     "label":"Assists/90",      "cat":"att"},
        {"key":"xa90",    "label":"xA/90",           "cat":"att"},
        {"key":"drib90",  "label":"Dribbles/90",     "cat":"att"},
        {"key":"drib_pct","label":"Dribble Succ %",  "cat":"att"},
        {"key":"tib90",   "label":"Touches Box/90",  "cat":"att"},
        {"key":"pr90",    "label":"Prog Runs/90",    "cat":"pass"},
        {"key":"kp90",    "label":"Key Passes/90",   "cat":"pass"},
        {"key":"ddw",     "label":"Def Duels Won %", "cat":"def"},
    ],
    "FW": [
        {"key":"g90",     "label":"Goals/90",        "cat":"att"},
        {"key":"xg90",    "label":"xG/90",           "cat":"att"},
        {"key":"a90",     "label":"Assists/90",      "cat":"att"},
        {"key":"xa90",    "label":"xA/90",           "cat":"att"},
        {"key":"tib90",   "label":"Touches Box/90",  "cat":"att"},
        {"key":"drib90",  "label":"Dribbles/90",     "cat":"att"},
        {"key":"adw",     "label":"Aerial Won %",    "cat":"def"},
        {"key":"kp90",    "label":"Key Passes/90",   "cat":"pass"},
    ],
}


def load_data():
    df = pd.read_excel(DATA_FILE, sheet_name="All Targets (ranked)")
    for c in STAT_COLS + ["Market value","model_value","value_ratio",
                           "sqs_rank","bloom_index","vs_hradec_gap","Age","Minutes played"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df["contract_flag"] = df["Contract expires"].fillna("").astype(str).apply(
        lambda x: "2026" if "2026" in x else ("2027" if "2027" in x else ""))

    # Compute per-position percentiles for each stat
    pct_cols = {}
    for pos in df["pos_group"].unique():
        mask = df["pos_group"] == pos
        for col in STAT_COLS:
            if col in df.columns:
                out_col = col + "_pct"
                if out_col not in pct_cols:
                    pct_cols[out_col] = pd.Series(0.0, index=df.index)
                vals = df.loc[mask, col]
                pct_cols[out_col].loc[mask] = vals.rank(pct=True).mul(100)

    for col, series in pct_cols.items():
        df[col] = series.round(1)

    return df


KEY_MAP = {
    "g90":     "Goals per 90",
    "xg90":    "xG per 90",
    "a90":     "Assists per 90",
    "xa90":    "xA per 90",
    "pp90":    "Progressive passes per 90",
    "pr90":    "Progressive runs per 90",
    "tib90":   "Touches in box per 90",
    "ddw":     "Defensive duels won, %",
    "adw":     "Aerial duels won, %",
    "drib90":  "Dribbles per 90",
    "drib_pct":"Successful dribbles, %",
    "kp90":    "Key passes per 90",
    "int90":   "PAdj Interceptions",
    "sv_pct":  "Save rate, %",
    "pg90":    "Prevented goals per 90",
}


def player_records(df):
    rows = []
    for _, r in df.iterrows():
        bi   = float(r.get("bloom_index", 0))
        tier = str(r.get("value_tier", ""))
        ts   = ("ELITE" if "ELITE" in tier else "HIGH" if "HIGH" in tier
                else "VALUE" if tier == "VALUE" else "FAIR" if "FAIR" in tier else "OVER")
        rec = {
            "name":     str(r["Player"]),
            "team":     str(r["Team"]),
            "league":   str(r["league"]),
            "pos":      str(r["pos_group"]),
            "position": str(r["Position"]),
            "age":      int(r["Age"]),
            "contract": str(r.get("Contract expires",""))[:10],
            "cflag":    str(r.get("contract_flag","")),
            "mv":       int(r.get("Market value",0)),
            "model_v":  int(r.get("model_value",0)),
            "sqs":      round(float(r.get("sqs_rank",0)),1),
            "bi":       round(bi, 1),
            "tier":     ts,
            "upgrade":  str(r.get("upgrade_flag","")),
            "gap":      round(float(r.get("vs_hradec_gap",0)),1),
            "starters": str(r.get("hradec_starters","")),
            "mins":     int(r.get("Minutes played",0)),
            # raw stats
            "g90":      round(float(r.get("Goals per 90",0)),2),
            "xg90":     round(float(r.get("xG per 90",0)),2),
            "a90":      round(float(r.get("Assists per 90",0)),2),
            "xa90":     round(float(r.get("xA per 90",0)),2),
            "pp90":     round(float(r.get("Progressive passes per 90",0)),2),
            "pr90":     round(float(r.get("Progressive runs per 90",0)),2),
            "tib90":    round(float(r.get("Touches in box per 90",0)),2),
            "ddw":      round(float(r.get("Defensive duels won, %",0)),1),
            "adw":      round(float(r.get("Aerial duels won, %",0)),1),
            "drib90":   round(float(r.get("Dribbles per 90",0)),2),
            "drib_pct": round(float(r.get("Successful dribbles, %",0)),1),
            "kp90":     round(float(r.get("Key passes per 90",0)),2),
            "int90":    round(float(r.get("PAdj Interceptions",0)),2),
            "sv_pct":   round(float(r.get("Save rate, %",0)),1),
            "pg90":     round(float(r.get("Prevented goals per 90",0)),2),
        }
        # percentile stats
        for key, col in KEY_MAP.items():
            pct_col = col + "_pct"
            rec[key + "_pct"] = round(float(r.get(pct_col, 0)), 1)

        rows.append(rec)
    return rows


def build():
    print("Loading & computing percentiles...")
    df = load_data()
    records = player_records(df)

    tier_counts = {}
    for t in ["ELITE","HIGH","VALUE","FAIR","OVER"]:
        tier_counts[t] = sum(1 for r in records if r["tier"] == t)

    pos_counts = {p: sum(1 for r in records if r["pos"] == p)
                  for p in ["GK","CB","FB","DM","CM","W","FW"]}

    pizza_meta = {pos: [{"key": m["key"], "label": m["label"], "cat": m["cat"]}
                        for m in metrics]
                  for pos, metrics in PIZZA_METRICS.items()}

    html = HTML_TEMPLATE
    html = html.replace("__DATA_JSON__",     json.dumps(records, ensure_ascii=False))
    html = html.replace("__TIER_JSON__",     json.dumps(tier_counts))
    html = html.replace("__POS_JSON__",      json.dumps(pos_counts))
    html = html.replace("__PIZZA_JSON__",    json.dumps(pizza_meta))
    html = html.replace("__TOTAL__",         str(len(records)))

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Done → {OUTPUT}  ({len(records)} players, {os.path.getsize(OUTPUT)//1024} KB)")


# ─────────────────────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FC Hradec Králové — Jamestown Recruitment 2025-26</title>
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {
  --blue:#1A56DB; --green:#1E8449; --amber:#D4700A; --red:#C0392B;
  --black:#111; --g1:#444; --g2:#666; --g3:#AAA; --g4:#F4F6F8;
  --white:#FFF; --border:#E2E8F0; --bg:#F8FAFC;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--black);font-size:14px}
a{color:var(--blue);text-decoration:none}

/* ── Header ── */
.hdr{background:var(--blue);color:#fff;padding:18px 32px;display:flex;align-items:center;justify-content:space-between}
.hdr h1{font-size:19px;font-weight:800;letter-spacing:-.3px}
.hdr .sub{font-size:11px;opacity:.75;margin-top:2px}
.hdr-badge{background:rgba(255,255,255,.18);padding:4px 14px;border-radius:20px;font-size:12px;font-weight:700}

/* ── Nav tabs ── */
.nav{background:#fff;border-bottom:2px solid var(--border);display:flex;padding:0 32px;gap:4px}
.nav-btn{padding:12px 20px;font-size:13px;font-weight:600;color:var(--g2);border:none;background:none;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-2px;transition:.15s}
.nav-btn:hover{color:var(--blue)}
.nav-btn.active{color:var(--blue);border-bottom-color:var(--blue)}

/* ── Tab panels ── */
.tab-panel{display:none;padding:20px 32px 40px}
.tab-panel.active{display:block}

/* ── KPI row ── */
.kpi-row{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:20px}
.kpi{background:#fff;border:1px solid var(--border);border-radius:10px;padding:16px 20px;flex:1;min-width:130px;border-top:3px solid var(--blue)}
.kpi.g{border-top-color:var(--green)}
.kpi.a{border-top-color:var(--amber)}
.kpi.r{border-top-color:var(--red)}
.kpi .val{font-size:26px;font-weight:800;line-height:1;margin-bottom:3px}
.kpi .lbl{font-size:10px;color:var(--g2);text-transform:uppercase;letter-spacing:.5px}
.kpi.g .val{color:var(--green)} .kpi.a .val{color:var(--amber)} .kpi.r .val{color:var(--red)}
.kpi:not(.g):not(.a):not(.r) .val{color:var(--blue)}

/* ── Cards ── */
.card{background:#fff;border:1px solid var(--border);border-radius:10px;padding:20px}
.card h3{font-size:11px;font-weight:700;color:var(--g1);text-transform:uppercase;letter-spacing:.5px;margin-bottom:16px}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid-3{display:grid;grid-template-columns:2fr 1fr 1fr;gap:16px}
.grid-4{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:16px}

/* ── Pos filter buttons ── */
.pos-row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;align-items:center}
.pos-btn{padding:5px 14px;border-radius:20px;border:1.5px solid var(--border);background:#fff;cursor:pointer;font-size:12px;font-weight:700;color:var(--g2);transition:.15s}
.pos-btn:hover,.pos-btn.active{background:var(--blue);border-color:var(--blue);color:#fff}
.filter-sel{padding:5px 10px;border-radius:6px;border:1.5px solid var(--border);font-size:12px;font-family:inherit;background:#fff}

/* ── Table ── */
table.dataTable thead th{background:#F1F5F9;color:var(--g1);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;border-bottom:2px solid var(--border)!important;padding:9px 10px}
table.dataTable tbody td{padding:7px 10px;font-size:12px;border-bottom:1px solid #F1F5F9;vertical-align:middle}
table.dataTable tbody tr:hover td{background:#F8FAFC}
.dataTables_wrapper .dataTables_filter input{border:1.5px solid var(--border);border-radius:6px;padding:4px 10px;font-family:inherit;font-size:12px}
.dataTables_wrapper .dataTables_length select{border:1.5px solid var(--border);border-radius:6px;font-family:inherit}
.dataTables_wrapper .dataTables_paginate .paginate_button.current{background:var(--blue)!important;color:#fff!important;border-radius:6px;border:none!important}
.dataTables_wrapper .dataTables_paginate .paginate_button:hover{background:#EEF2FF!important;color:var(--blue)!important;border-radius:6px;border:none!important}

/* ── Chips ── */
.chip{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700}
.te{background:#D1FAE5;color:#065F46} .th{background:#DCFCE7;color:#166534}
.tv{background:#DBEAFE;color:#1E40AF} .tf{background:#F3F4F6;color:#4B5563} .to{background:#FEE2E2;color:#991B1B}
.uc{background:#D1FAE5;color:#065F46} .ur{background:#FEF3C7;color:#92400E} .ud{background:#F3F4F6;color:#4B5563}
.cg{color:var(--green);font-weight:700} .ca{color:var(--amber);font-weight:700}
.cr{color:var(--red);font-weight:700}  .cb{color:var(--blue);font-weight:700}
.cflag{color:var(--red);font-weight:700;font-size:10px}

/* ── Scout tab ── */
.scout-search{display:flex;gap:10px;margin-bottom:20px;align-items:center}
.scout-search input{flex:1;padding:10px 16px;border:2px solid var(--border);border-radius:8px;font-size:14px;font-family:inherit;outline:none}
.scout-search input:focus{border-color:var(--blue)}
#autocomplete-list{position:absolute;background:#fff;border:1px solid var(--border);border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.1);z-index:100;max-height:280px;overflow-y:auto;min-width:320px}
#autocomplete-list .ac-item{padding:10px 14px;cursor:pointer;font-size:13px;border-bottom:1px solid #F1F5F9}
#autocomplete-list .ac-item:hover{background:#F8FAFC}
#autocomplete-list .ac-item .ac-name{font-weight:600}
#autocomplete-list .ac-item .ac-meta{color:var(--g3);font-size:11px}
.scout-grid{display:grid;grid-template-columns:420px 1fr;gap:20px;align-items:start}
.pizza-wrap{display:flex;justify-content:center}
#pizzaSvg{max-width:420px;width:100%}
.scout-stats{display:flex;flex-direction:column;gap:12px}
.stat-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #F1F5F9}
.stat-row .s-lbl{font-size:12px;color:var(--g2)}
.stat-row .s-val{font-size:13px;font-weight:700}
.stat-bar-wrap{width:120px;height:6px;background:#F1F5F9;border-radius:3px;overflow:hidden}
.stat-bar-fill{height:100%;border-radius:3px}
.scout-header{background:var(--blue);color:#fff;border-radius:10px;padding:18px 22px;margin-bottom:14px}
.scout-header .sh-name{font-size:20px;font-weight:800;margin-bottom:4px}
.scout-header .sh-meta{font-size:12px;opacity:.8}
.scout-header .sh-nums{display:flex;gap:20px;margin-top:12px}
.scout-header .sh-num .n{font-size:22px;font-weight:800}
.scout-header .sh-num .l{font-size:10px;opacity:.7;text-transform:uppercase;letter-spacing:.4px}

/* ── Pizza legend ── */
.pizza-legend{display:flex;gap:14px;justify-content:center;margin-top:8px;flex-wrap:wrap}
.pl-item{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--g2)}
.pl-dot{width:10px;height:10px;border-radius:50%}

/* ── Tooltip ── */
#tt{position:fixed;display:none;background:#fff;border:1px solid var(--border);box-shadow:0 8px 24px rgba(0,0,0,.12);border-radius:10px;padding:13px 16px;z-index:999;max-width:250px;pointer-events:none;font-size:12px}
#tt h4{font-size:13px;font-weight:700;margin-bottom:6px}
.tt-r{display:flex;justify-content:space-between;gap:18px;margin:2px 0}
.tt-l{color:var(--g2)} .tt-v{font-weight:700}

/* ── Waffle ── */
#waffleContainer{display:flex;gap:4px;flex-wrap:wrap;line-height:1}
.waffle-sq{width:14px;height:14px;border-radius:2px;transition:.1s}
.waffle-sq:hover{transform:scale(1.3)}

/* ── Beeswarm ── */
#beeswarmSvg{width:100%;overflow:visible}

/* ── Comparison ── */
.comp-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
</style>
</head>
<body>

<div class="hdr">
  <div>
    <h1>FC Hradec Králové &mdash; Jamestown Recruitment Model</h1>
    <div class="sub">2025&ndash;2026 &middot; CZ II + Slovakia + Slovakia II &middot; Budget cap &euro;1M &middot; Jamestown Analytics methodology</div>
  </div>
  <div class="hdr-badge">__TOTAL__ candidates</div>
</div>

<nav class="nav">
  <button class="nav-btn active" data-tab="overview">Overview</button>
  <button class="nav-btn" data-tab="scout">Player Scout</button>
  <button class="nav-btn" data-tab="positions">Position Analysis</button>
  <button class="nav-btn" data-tab="table">All Players</button>
</nav>

<!-- ════════════════ TAB: OVERVIEW ════════════════ -->
<div id="tab-overview" class="tab-panel active">

  <div class="kpi-row">
    <div class="kpi g"><div class="val" id="k-elite">—</div><div class="lbl">Elite Value picks</div></div>
    <div class="kpi"  ><div class="val" id="k-upgrades">—</div><div class="lbl">Clear Upgrades</div></div>
    <div class="kpi a"><div class="val" id="k-u23">—</div><div class="lbl">Players ≤ 23</div></div>
    <div class="kpi r"><div class="val" id="k-exp">—</div><div class="lbl">Expiring 2026 ✦</div></div>
    <div class="kpi"  ><div class="val" id="k-avgbi">—</div><div class="lbl">Avg Bloom (upgrades)</div></div>
    <div class="kpi g"><div class="val" id="k-avgmv">—</div><div class="lbl">Avg value (upgrades)</div></div>
  </div>

  <!-- Row 1: Scatter + Beeswarm -->
  <div class="grid-2" style="margin-bottom:16px">
    <div class="card">
      <h3>SQS Rank vs Market Value &mdash; bubble size = minutes played</h3>
      <canvas id="scatterChart" height="280"></canvas>
    </div>
    <div class="card">
      <h3>Bloom Index distribution by position</h3>
      <svg id="beeswarmSvg" height="280"></svg>
      <div id="beeswarm-legend" style="display:flex;gap:12px;flex-wrap:wrap;margin-top:10px"></div>
    </div>
  </div>

  <!-- Row 2: Waffle + Tier bar + League donut -->
  <div class="grid-3">
    <div class="card">
      <h3>Bloom Value Tier breakdown &mdash; each square = ~5 players</h3>
      <div id="waffleContainer" style="margin-bottom:10px"></div>
      <div id="waffle-legend" style="display:flex;gap:12px;flex-wrap:wrap;margin-top:6px"></div>
    </div>
    <div class="card">
      <h3>Candidates by position</h3>
      <canvas id="posBar" height="220"></canvas>
    </div>
    <div class="card">
      <h3>League distribution</h3>
      <canvas id="leagueDonut" height="220"></canvas>
    </div>
  </div>
</div>

<!-- ════════════════ TAB: SCOUT ════════════════ -->
<div id="tab-scout" class="tab-panel">
  <div style="position:relative">
    <div class="scout-search">
      <input type="text" id="playerSearch" placeholder="Search player by name…" autocomplete="off">
    </div>
    <div id="autocomplete-list" style="display:none"></div>
  </div>

  <div id="scout-content" style="display:none">
    <div class="scout-header" id="scoutHeader"></div>
    <div class="scout-grid">
      <div>
        <div class="card">
          <h3 id="pizza-title">Position profile</h3>
          <div class="pizza-wrap">
            <svg id="pizzaSvg" viewBox="0 0 440 440"></svg>
          </div>
          <div class="pizza-legend" id="pizzaLegend"></div>
        </div>
      </div>
      <div>
        <div class="card" style="margin-bottom:16px">
          <h3>Key metrics vs position peers</h3>
          <div id="metricsTable"></div>
        </div>
        <div class="card">
          <h3>Scout summary</h3>
          <div id="scoutSummary" style="font-size:13px;line-height:1.7;color:var(--g1)"></div>
        </div>
      </div>
    </div>
  </div>

  <div id="scout-empty" style="text-align:center;padding:60px;color:var(--g3)">
    <div style="font-size:48px;margin-bottom:12px">⚽</div>
    <div style="font-size:16px;font-weight:600;color:var(--g2)">Search for a player to see their profile</div>
    <div style="font-size:13px;margin-top:6px">Pizza plot · metrics percentiles · Jamestown score</div>
  </div>
</div>

<!-- ════════════════ TAB: POSITIONS ════════════════ -->
<div id="tab-positions" class="tab-panel">
  <div class="pos-row">
    <span style="font-size:12px;font-weight:600;color:var(--g2)">Position:</span>
    <button class="pos-btn active" data-pos="W">W</button>
    <button class="pos-btn" data-pos="FW">FW</button>
    <button class="pos-btn" data-pos="CM">CM</button>
    <button class="pos-btn" data-pos="DM">DM</button>
    <button class="pos-btn" data-pos="FB">FB</button>
    <button class="pos-btn" data-pos="CB">CB</button>
    <button class="pos-btn" data-pos="GK">GK</button>
  </div>

  <div class="grid-2" style="margin-bottom:16px">
    <div class="card">
      <h3 id="pos-bar-title">Top players by Bloom Index</h3>
      <canvas id="posTopBar" height="340"></canvas>
    </div>
    <div class="card">
      <h3 id="pos-scatter-title">SQS vs Market Value</h3>
      <canvas id="posScatter" height="340"></canvas>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h3 id="pos-age-title">Age distribution</h3>
      <canvas id="posAgeBar" height="200"></canvas>
    </div>
    <div class="card">
      <h3 id="pos-tier-title">Value tier breakdown</h3>
      <canvas id="posTierDonut" height="200"></canvas>
    </div>
  </div>
</div>

<!-- ════════════════ TAB: TABLE ════════════════ -->
<div id="tab-table" class="tab-panel">
  <div class="pos-row" style="margin-bottom:14px">
    <span style="font-size:12px;font-weight:600;color:var(--g2)">Position:</span>
    <button class="tbl-pos-btn pos-btn active" data-pos="ALL">All</button>
    <button class="tbl-pos-btn pos-btn" data-pos="GK">GK</button>
    <button class="tbl-pos-btn pos-btn" data-pos="CB">CB</button>
    <button class="tbl-pos-btn pos-btn" data-pos="FB">FB</button>
    <button class="tbl-pos-btn pos-btn" data-pos="DM">DM</button>
    <button class="tbl-pos-btn pos-btn" data-pos="CM">CM</button>
    <button class="tbl-pos-btn pos-btn" data-pos="W">W</button>
    <button class="tbl-pos-btn pos-btn" data-pos="FW">FW</button>
    <select class="filter-sel" id="tblTier">
      <option value="">All tiers</option>
      <option value="ELITE">Elite Value</option><option value="HIGH">High Value</option>
      <option value="VALUE">Value</option><option value="FAIR">Fair</option><option value="OVER">Overvalued</option>
    </select>
    <select class="filter-sel" id="tblUpgrade">
      <option value="">All statuses</option>
      <option value="CLEAR UPGRADE">Clear Upgrade</option>
      <option value="ROTATIONAL / COVER">Rotational</option>
    </select>
    <span style="font-size:12px;color:var(--g2);margin-left:6px" id="tbl-count"></span>
  </div>
  <div class="card">
    <table id="mainTable" style="width:100%">
      <thead><tr>
        <th>#</th><th>Player</th><th>Pos</th><th>Team</th><th>League</th>
        <th>Age</th><th>Contract</th><th>Mkt Val</th><th>SQS</th><th>Bloom</th>
        <th>Tier</th><th>Status</th><th>vs HK</th><th>Mins</th>
        <th>G/90</th><th>xG/90</th><th>A/90</th><th>PP/90</th><th>DD%</th><th>Int/90</th>
      </tr></thead>
      <tbody id="tableBody"></tbody>
    </table>
  </div>
</div>

<div id="tt"></div>

<!-- ═══════════ Scripts ═══════════ -->
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>

<script>
// ── Data ──────────────────────────────────────────────────────────────────
const DATA        = __DATA_JSON__;
const TIER_COUNTS = __TIER_JSON__;
const POS_COUNTS  = __POS_JSON__;
const PIZZA_META  = __PIZZA_JSON__;

const TIER_COLOR = {ELITE:"#1E8449",HIGH:"#27AE60",VALUE:"#1A56DB",FAIR:"#888",OVER:"#C0392B"};
const CAT_COLOR  = {att:"#1E8449", def:"#1A56DB", pass:"#D4700A", gk:"#8B5CF6"};
const CAT_LABEL  = {att:"Attacking", def:"Defending", pass:"Progression", gk:"Goalkeeping"};
const POS_ORDER  = ["GK","CB","FB","DM","CM","W","FW"];
const TIER_LABEL = {ELITE:"Elite Value",HIGH:"High Value",VALUE:"Value",FAIR:"Fair Price",OVER:"Overvalued"};
const LEAGUE_COLORS = {"CZ II":"#1A56DB","Slovakia":"#1E8449","Slovakia II":"#D4700A"};

// ── Tab navigation ─────────────────────────────────────────────────────────
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "positions") renderPositionTab(activePos);
  });
});

// ── Helpers ────────────────────────────────────────────────────────────────
const tt = document.getElementById("tt");
function showTT(html, e) {
  tt.innerHTML = html; tt.style.display = "block";
  tt.style.left = (e.clientX + 14) + "px"; tt.style.top = (e.clientY - 16) + "px";
}
document.addEventListener("mousemove", e => {
  if (tt.style.display === "block") { tt.style.left=(e.clientX+14)+"px"; tt.style.top=(e.clientY-16)+"px"; }
});

function fmt_mv(v){ return v>0 ? "€"+v.toLocaleString() : "—" }
function fmt_bi(v){ return (v>0?"+":"")+v }
function tier_chip(t){
  const lbl={ELITE:"Elite",HIGH:"High",VALUE:"Value",FAIR:"Fair",OVER:"Over"};
  const cls={ELITE:"te",HIGH:"th",VALUE:"tv",FAIR:"tf",OVER:"to"};
  return `<span class="chip ${cls[t]||"tf"}">${lbl[t]||t}</span>`;
}
function upg_chip(u){
  if(u==="CLEAR UPGRADE")       return `<span class="chip uc">▲ Clear</span>`;
  if(u.startsWith("ROT"))       return `<span class="chip ur">Rot.</span>`;
  return `<span class="chip ud">Depth</span>`;
}
function sqs_color(v){ return v>=70?"#1E8449":v>=40?"#D4700A":"#C0392B" }
function bi_color(v){  return v>=20?"#1E8449":v>=10?"#1A56DB":v>=0?"#D4700A":"#C0392B" }

// ── KPIs ──────────────────────────────────────────────────────────────────
const upgrades = DATA.filter(d=>d.upgrade==="CLEAR UPGRADE");
document.getElementById("k-elite").textContent    = DATA.filter(d=>d.tier==="ELITE").length;
document.getElementById("k-upgrades").textContent = upgrades.length;
document.getElementById("k-u23").textContent      = DATA.filter(d=>d.age<=23).length;
document.getElementById("k-exp").textContent      = DATA.filter(d=>d.cflag==="2026").length;
document.getElementById("k-avgbi").textContent    = upgrades.length
  ? (upgrades.reduce((s,d)=>s+d.bi,0)/upgrades.length).toFixed(1) : "—";
document.getElementById("k-avgmv").textContent    = upgrades.length
  ? "€"+Math.round(upgrades.reduce((s,d)=>s+d.mv,0)/upgrades.length/1000)+"k" : "—";

// ══════════════════════════════════════════════════════════════════════════
// SCATTER (Chart.js)
// ══════════════════════════════════════════════════════════════════════════
const scatterCtx = document.getElementById("scatterChart").getContext("2d");
const scatterDS = POS_ORDER.map((pos,pi) => {
  const hue = [210,180,150,100,240,30,0][pi];
  return {
    label: pos,
    data: DATA.filter(d=>d.pos===pos).map(d=>({
      x: d.mv/1000, y: d.sqs,
      r: Math.max(3, Math.min(12, d.mins/250)),
      _d: d
    })),
    backgroundColor: `hsla(${hue},65%,45%,0.55)`,
    borderColor:     `hsla(${hue},65%,35%,0.8)`,
    borderWidth: 1,
  };
});
const scatterChart = new Chart(scatterCtx, {
  type:"bubble",
  data:{datasets:scatterDS},
  options:{
    responsive:true,
    plugins:{
      legend:{position:"top",labels:{boxWidth:10,font:{size:10}}},
      tooltip:{enabled:false}
    },
    scales:{
      x:{title:{display:true,text:"Market Value (€k)",font:{size:10}},grid:{color:"#F1F5F9"}},
      y:{title:{display:true,text:"SQS Rank (0–100)",font:{size:10}},min:0,max:100,grid:{color:"#F1F5F9"}}
    },
    onHover:(e,els)=>{
      if(!els.length){tt.style.display="none";return}
      const el=els[0], d=scatterChart.data.datasets[el.datasetIndex].data[el.index]._d;
      showTT(`<h4>${d.name}</h4>
        <div class="tt-r"><span class="tt-l">Team</span><span class="tt-v">${d.team}</span></div>
        <div class="tt-r"><span class="tt-l">League</span><span class="tt-v">${d.league}</span></div>
        <div class="tt-r"><span class="tt-l">SQS / BI</span><span class="tt-v">${d.sqs} / ${fmt_bi(d.bi)}</span></div>
        <div class="tt-r"><span class="tt-l">Market val</span><span class="tt-v">${fmt_mv(d.mv)}</span></div>
        <div class="tt-r"><span class="tt-l">Status</span><span class="tt-v">${d.upgrade}</span></div>`, e.native);
    }
  }
});

// ══════════════════════════════════════════════════════════════════════════
// BEESWARM (D3)
// ══════════════════════════════════════════════════════════════════════════
function drawBeeswarm() {
  const svg = d3.select("#beeswarmSvg");
  const W = svg.node().getBoundingClientRect().width || 500;
  const H = 280;
  svg.attr("viewBox",`0 0 ${W} ${H}`);

  const margin = {left:46, right:16, top:10, bottom:30};
  const iW = W - margin.left - margin.right;
  const iH = H - margin.top - margin.bottom;

  const g = svg.append("g").attr("transform",`translate(${margin.left},${margin.top})`);

  const xScale = d3.scaleLinear().domain([-30, 80]).range([0, iW]);

  // Lane y for each position
  const laneH = iH / POS_ORDER.length;
  const laneY = pos => POS_ORDER.indexOf(pos) * laneH + laneH / 2;

  // X axis
  g.append("g").attr("transform",`translate(0,${iH})`).call(
    d3.axisBottom(xScale).ticks(6).tickFormat(d=>(d>0?"+":"")+d)
      .tickSize(-iH)
  ).selectAll("line").attr("stroke","#F1F5F9");
  g.select(".domain").remove();
  g.append("text").attr("x",iW/2).attr("y",iH+26).attr("text-anchor","middle")
   .attr("font-size",10).attr("fill","#888").text("Bloom Index");

  // Zero line
  g.append("line")
   .attr("x1",xScale(0)).attr("x2",xScale(0))
   .attr("y1",0).attr("y2",iH)
   .attr("stroke","#CBD5E0").attr("stroke-dasharray","3,3").attr("stroke-width",1);

  // Position labels
  POS_ORDER.forEach(pos => {
    g.append("text").attr("x",-4).attr("y",laneY(pos)).attr("text-anchor","end")
     .attr("dy","0.35em").attr("font-size",10).attr("font-weight","700").attr("fill","#555")
     .text(pos);
  });

  // Beeswarm using d3-force
  const nodes = DATA.map(d => ({
    pos: d.pos, bi: d.bi, tier: d.tier, name: d.name,
    mv: d.mv, _d: d,
    x: xScale(Math.max(-30, Math.min(80, d.bi))),
    y: laneY(d.pos)
  }));

  const sim = d3.forceSimulation(nodes)
    .force("x", d3.forceX(n => xScale(Math.max(-30, Math.min(80, n.bi)))).strength(0.9))
    .force("y", d3.forceY(n => laneY(n.pos)).strength(3))
    .force("collide", d3.forceCollide(3.2))
    .stop();

  for (let i = 0; i < 180; i++) sim.tick();

  g.selectAll("circle.bee").data(nodes).join("circle")
    .attr("class","bee")
    .attr("cx", n => Math.max(2, Math.min(iW-2, n.x)))
    .attr("cy", n => Math.max(4, Math.min(iH-4, n.y)))
    .attr("r",  3.5)
    .attr("fill", n => TIER_COLOR[n.tier] || "#888")
    .attr("opacity", 0.75)
    .attr("stroke", "#fff").attr("stroke-width", 0.5)
    .on("mouseover", function(e, n) {
      d3.select(this).attr("r", 5.5).attr("opacity", 1);
      showTT(`<h4>${n.name}</h4>
        <div class="tt-r"><span class="tt-l">Pos</span><span class="tt-v">${n.pos}</span></div>
        <div class="tt-r"><span class="tt-l">BI</span><span class="tt-v">${fmt_bi(n.bi)}</span></div>
        <div class="tt-r"><span class="tt-l">SQS</span><span class="tt-v">${n._d.sqs}</span></div>
        <div class="tt-r"><span class="tt-l">Tier</span><span class="tt-v">${TIER_LABEL[n.tier]}</span></div>`, e);
    })
    .on("mouseout", function(){ d3.select(this).attr("r",3.5).attr("opacity",0.75); tt.style.display="none"; });

  // Legend
  const leg = document.getElementById("beeswarm-legend");
  leg.innerHTML = Object.entries(TIER_COLOR).map(([t,c])=>
    `<div style="display:flex;align-items:center;gap:5px;font-size:11px;color:#666">
      <div style="width:10px;height:10px;border-radius:50%;background:${c}"></div>${TIER_LABEL[t]}
    </div>`).join("");
}
drawBeeswarm();
window.addEventListener("resize", () => { d3.select("#beeswarmSvg").selectAll("*").remove(); drawBeeswarm(); });

// ══════════════════════════════════════════════════════════════════════════
// WAFFLE (D3)
// ══════════════════════════════════════════════════════════════════════════
(function(){
  const total = DATA.length;
  const tiers = ["ELITE","HIGH","VALUE","FAIR","OVER"];
  const cells = 100;
  const sqData = [];
  let acc = 0;
  tiers.forEach(t => {
    const n = Math.round((TIER_COUNTS[t] / total) * cells);
    for (let i = 0; i < n; i++) sqData.push(t);
    acc += n;
  });
  while (sqData.length < cells) sqData.push("FAIR");

  const wrap = document.getElementById("waffleContainer");
  sqData.forEach((t, i) => {
    const sq = document.createElement("div");
    sq.className = "waffle-sq";
    sq.style.background = TIER_COLOR[t];
    sq.style.opacity = "0.85";
    sq.title = TIER_LABEL[t];
    wrap.appendChild(sq);
  });

  const leg = document.getElementById("waffle-legend");
  tiers.forEach(t => {
    const pct = ((TIER_COUNTS[t]/total)*100).toFixed(1);
    leg.innerHTML += `<div style="display:flex;align-items:center;gap:5px;font-size:11px;color:#555">
      <div style="width:10px;height:10px;border-radius:2px;background:${TIER_COLOR[t]}"></div>
      <span>${TIER_LABEL[t]}</span><strong>${TIER_COUNTS[t]}</strong><span style="color:#aaa">(${pct}%)</span>
    </div>`;
  });
})();

// ══════════════════════════════════════════════════════════════════════════
// POS BAR + LEAGUE DONUT
// ══════════════════════════════════════════════════════════════════════════
new Chart(document.getElementById("posBar").getContext("2d"), {
  type:"bar",
  data:{
    labels: POS_ORDER,
    datasets:[{
      data: POS_ORDER.map(p=>POS_COUNTS[p]||0),
      backgroundColor: POS_ORDER.map((_,i)=>`hsla(${[210,180,150,100,240,30,0][i]},60%,50%,0.7)`),
      borderRadius: 5, borderSkipped: false
    }]
  },
  options:{
    indexAxis:"y", responsive:true,
    plugins:{legend:{display:false}},
    scales:{x:{grid:{color:"#F1F5F9"}},y:{grid:{display:false}}}
  }
});

const leagueCounts = {};
DATA.forEach(d => { leagueCounts[d.league] = (leagueCounts[d.league]||0)+1; });
new Chart(document.getElementById("leagueDonut").getContext("2d"), {
  type:"doughnut",
  data:{
    labels: Object.keys(leagueCounts),
    datasets:[{
      data: Object.values(leagueCounts),
      backgroundColor: Object.keys(leagueCounts).map(l=>LEAGUE_COLORS[l]||"#888"),
      borderWidth:2, borderColor:"#fff"
    }]
  },
  options:{
    cutout:"62%", responsive:true,
    plugins:{legend:{position:"bottom",labels:{boxWidth:10,font:{size:10}}}}
  }
});

// ══════════════════════════════════════════════════════════════════════════
// PIZZA PLOT (D3 SVG)
// ══════════════════════════════════════════════════════════════════════════
function arcPath(cx, cy, r1, r2, a1, a2) {
  const cos = Math.cos, sin = Math.sin;
  const x1=cx+r1*cos(a1), y1=cy+r1*sin(a1);
  const x2=cx+r2*cos(a1), y2=cy+r2*sin(a1);
  const x3=cx+r2*cos(a2), y3=cy+r2*sin(a2);
  const x4=cx+r1*cos(a2), y4=cy+r1*sin(a2);
  const big = (a2-a1) > Math.PI ? 1 : 0;
  return `M${x1},${y1} L${x2},${y2} A${r2},${r2},0,${big},1,${x3},${y3} L${x4},${y4} A${r1},${r1},0,${big},0,${x1},${y1}Z`;
}

function drawPizza(player) {
  const metrics = PIZZA_META[player.pos] || [];
  if (!metrics.length) return;

  const svg = d3.select("#pizzaSvg");
  svg.selectAll("*").remove();

  const VW=440, VH=440, cx=220, cy=220;
  const innerR=34, outerR=155, labelR=178;
  const n = metrics.length;
  const step = (2*Math.PI)/n;
  const start = -Math.PI/2;

  // Background
  svg.append("rect").attr("width",VW).attr("height",VH).attr("fill","#FAFBFC");

  // Reference rings at 25, 50, 75
  [25,50,75].forEach(pct => {
    const r = innerR + (outerR-innerR)*(pct/100);
    svg.append("circle").attr("cx",cx).attr("cy",cy).attr("r",r)
       .attr("fill","none").attr("stroke","#DDE2EA").attr("stroke-width",0.6)
       .attr("stroke-dasharray","2,3");
    svg.append("text").attr("x",cx+3).attr("y",cy-r-3)
       .attr("font-size",7).attr("fill","#BBC").attr("text-anchor","middle").text(pct+"%");
  });

  // Slice backgrounds
  metrics.forEach((m,i) => {
    const a1=start+i*step, a2=start+(i+1)*step;
    svg.append("path").attr("d", arcPath(cx,cy,innerR,outerR,a1,a2))
       .attr("fill", i%2===0 ? "#F0F4FA" : "#E8EDF6")
       .attr("stroke","#fff").attr("stroke-width",1.5);
  });

  // Outer ring background
  svg.append("circle").attr("cx",cx).attr("cy",cy).attr("r",outerR)
     .attr("fill","none").attr("stroke","#CDD5E0").attr("stroke-width",1);

  // Filled slices
  metrics.forEach((m,i) => {
    const a1=start+i*step, a2=start+(i+1)*step;
    const pct = parseFloat(player[m.key+"_pct"])||0;
    const fillR = innerR + (outerR-innerR)*(pct/100);
    if(fillR > innerR+1) {
      svg.append("path").attr("d", arcPath(cx,cy,innerR,fillR,a1,a2))
         .attr("fill", CAT_COLOR[m.cat]||"#1A56DB")
         .attr("opacity", 0.82)
         .attr("stroke","#fff").attr("stroke-width",1.5);
    }
    // Percentile label inside slice
    const midA = (a1+a2)/2;
    const labelInsideR = innerR + (outerR-innerR)*(pct/100) - 10;
    if(pct>18 && labelInsideR>innerR+6){
      svg.append("text")
         .attr("x", cx+labelInsideR*Math.cos(midA))
         .attr("y", cy+labelInsideR*Math.sin(midA))
         .attr("text-anchor","middle").attr("dy","0.35em")
         .attr("font-size", 7.5).attr("font-weight","700").attr("fill","#fff")
         .text(Math.round(pct));
    }
  });

  // Outer labels
  metrics.forEach((m,i) => {
    const a1=start+i*step, a2=start+(i+1)*step;
    const midA=(a1+a2)/2;
    const lx=cx+labelR*Math.cos(midA), ly=cy+labelR*Math.sin(midA);
    const anchor = Math.abs(Math.cos(midA))<0.1 ? "middle" : Math.cos(midA)<0 ? "end" : "start";
    const pct = parseFloat(player[m.key+"_pct"])||0;

    // Tick from outer ring to label area
    svg.append("line")
       .attr("x1",cx+(outerR+2)*Math.cos(midA)).attr("y1",cy+(outerR+2)*Math.sin(midA))
       .attr("x2",cx+(outerR+8)*Math.cos(midA)).attr("y2",cy+(outerR+8)*Math.sin(midA))
       .attr("stroke","#CDD5E0").attr("stroke-width",1);

    svg.append("text").attr("x",lx).attr("y",ly-4)
       .attr("text-anchor",anchor).attr("font-size",8.5).attr("font-weight","600")
       .attr("fill","#333").text(m.label);
    svg.append("text").attr("x",lx).attr("y",ly+7)
       .attr("text-anchor",anchor).attr("font-size",7.5)
       .attr("fill", CAT_COLOR[m.cat]||"#888").attr("font-weight","700")
       .text(Math.round(pct)+"th");
  });

  // Centre circle
  svg.append("circle").attr("cx",cx).attr("cy",cy).attr("r",innerR)
     .attr("fill","#fff").attr("stroke","#CDD5E0").attr("stroke-width",1.5);
  svg.append("text").attr("x",cx).attr("y",cy-10).attr("text-anchor","middle")
     .attr("font-size",9).attr("font-weight","800").attr("fill","#111")
     .text(player.name.split(" ").slice(-1)[0].substring(0,10));
  svg.append("text").attr("x",cx).attr("y",cy+3).attr("text-anchor","middle")
     .attr("font-size",8).attr("fill","#666").text(player.pos);
  svg.append("text").attr("x",cx).attr("y",cy+15).attr("text-anchor","middle")
     .attr("font-size",8).attr("font-weight","700").attr("fill","#1A56DB")
     .text(Math.round(player.sqs)+" SQS");

  // Update pizza title
  document.getElementById("pizza-title").textContent =
    `${player.name} — ${player.pos} profile vs position peers`;

  // Legend
  const cats = [...new Set(metrics.map(m=>m.cat))];
  document.getElementById("pizzaLegend").innerHTML = cats.map(c =>
    `<div class="pl-item"><div class="pl-dot" style="background:${CAT_COLOR[c]}"></div>${CAT_LABEL[c]}</div>`
  ).join("");
}

// ══════════════════════════════════════════════════════════════════════════
// SCOUT TAB
// ══════════════════════════════════════════════════════════════════════════
const searchInput = document.getElementById("playerSearch");
const acList      = document.getElementById("autocomplete-list");

searchInput.addEventListener("input", function() {
  const q = this.value.toLowerCase().trim();
  acList.innerHTML = "";
  if (q.length < 2) { acList.style.display="none"; return; }
  const matches = DATA.filter(d => d.name.toLowerCase().includes(q)).slice(0,12);
  if (!matches.length) { acList.style.display="none"; return; }
  matches.forEach(d => {
    const item = document.createElement("div");
    item.className = "ac-item";
    item.innerHTML = `<div class="ac-name">${d.name}</div>
      <div class="ac-meta">${d.pos} &middot; ${d.team} &middot; ${d.league} &middot; BI ${fmt_bi(d.bi)}</div>`;
    item.addEventListener("click", () => {
      searchInput.value = d.name;
      acList.style.display = "none";
      renderScout(d);
    });
    acList.appendChild(item);
  });
  acList.style.display = "block";
});
document.addEventListener("click", e => { if(!e.target.closest("#playerSearch")&&!e.target.closest("#autocomplete-list")) acList.style.display="none"; });

function renderScout(d) {
  document.getElementById("scout-empty").style.display = "none";
  document.getElementById("scout-content").style.display = "block";

  // Header
  const biCol = bi_color(d.bi);
  document.getElementById("scoutHeader").innerHTML = `
    <div class="sh-name">${d.name}</div>
    <div class="sh-meta">${d.pos} &middot; ${d.position} &middot; ${d.team} &middot; ${d.league} &middot; Age ${d.age}${d.cflag==="2026"?' <span style="color:#FFD700;font-weight:700">✦ 2026</span>':''}</div>
    <div class="sh-nums">
      <div class="sh-num"><div class="n">${d.sqs}</div><div class="l">SQS Rank</div></div>
      <div class="sh-num"><div class="n" style="color:${biCol}">${fmt_bi(d.bi)}</div><div class="l">Bloom Index</div></div>
      <div class="sh-num"><div class="n">${fmt_mv(d.mv)}</div><div class="l">Market Value</div></div>
      <div class="sh-num"><div class="n" style="color:${d.gap>0?"#7CFC00":"#FF6B6B"}">${fmt_bi(d.gap)}</div><div class="l">vs Hradec</div></div>
      <div class="sh-num"><div class="n">${d.mins}</div><div class="l">Minutes</div></div>
    </div>`;

  // Pizza
  drawPizza(d);

  // Metrics table
  const metrics = PIZZA_META[d.pos] || [];
  const statRows = metrics.map(m => {
    const pct = parseFloat(d[m.key+"_pct"])||0;
    const raw = d[m.key] !== undefined ? d[m.key] : "—";
    const barColor = pct>=70 ? "#1E8449" : pct>=40 ? "#D4700A" : "#C0392B";
    return `<div class="stat-row">
      <span class="s-lbl">${m.label}</span>
      <div style="display:flex;align-items:center;gap:10px">
        <div class="stat-bar-wrap"><div class="stat-bar-fill" style="width:${pct}%;background:${barColor}"></div></div>
        <span class="s-val" style="color:${barColor};min-width:36px;text-align:right">${Math.round(pct)}th</span>
        <span style="font-size:11px;color:#aaa;min-width:30px;text-align:right">${raw}</span>
      </div>
    </div>`;
  }).join("");
  document.getElementById("metricsTable").innerHTML = statRows;

  // Scout summary
  const tierFull = {ELITE:"Elite Value",HIGH:"High Value",VALUE:"Value",FAIR:"Fair Price",OVER:"Overvalued"};
  const upgrade  = d.upgrade === "CLEAR UPGRADE" ? "a <strong>clear upgrade</strong>" :
                   d.upgrade.startsWith("ROT")    ? "a <strong>rotational option</strong>" :
                                                    "a <strong>depth option</strong>";
  const contract_note = d.cflag==="2026" ? " Contract expires June 2026 — <strong>potential cut-price acquisition</strong>." : "";
  document.getElementById("scoutSummary").innerHTML = `
    <strong>${d.name}</strong> is rated <strong>${tierFull[d.tier]||d.tier}</strong> with a Bloom Index of
    <strong style="color:${bi_color(d.bi)}">${fmt_bi(d.bi)}</strong>, meaning their statistical output is
    <strong>${d.bi>0?"underpriced relative to":"overpriced relative to"}</strong> their market value.
    They represent ${upgrade} on current Hradec ${d.pos} starters (gap: <strong>${fmt_bi(d.gap)}</strong> SQS ranks).
    Current starters: ${d.starters}.${contract_note}
    <br><br>Market value <strong>${fmt_mv(d.mv)}</strong> vs model estimate <strong>${fmt_mv(d.model_v)}</strong>
    — value ratio <strong>${d.model_v>0?(d.model_v/Math.max(d.mv,1)).toFixed(1)+"×":"n/a"}</strong>.`;
}

// ══════════════════════════════════════════════════════════════════════════
// POSITION TAB
// ══════════════════════════════════════════════════════════════════════════
let activePos = "W";
let posCharts = {};

function renderPositionTab(pos) {
  activePos = pos;
  document.querySelectorAll("#tab-positions .pos-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.pos===pos));

  const posData = DATA.filter(d=>d.pos===pos)
                      .sort((a,b)=>b.bi-a.bi).slice(0,20);

  document.getElementById("pos-bar-title").textContent  = `${pos} — Top 20 by Bloom Index`;
  document.getElementById("pos-scatter-title").textContent = `${pos} — SQS vs Market Value`;
  document.getElementById("pos-age-title").textContent  = `${pos} — Age distribution`;
  document.getElementById("pos-tier-title").textContent = `${pos} — Value tier breakdown`;

  // Destroy old charts
  ["posTopBar","posScatter","posAgeBar","posTierDonut"].forEach(id => {
    if(posCharts[id]) { posCharts[id].destroy(); delete posCharts[id]; }
  });

  // Top bar
  posCharts.posTopBar = new Chart(document.getElementById("posTopBar").getContext("2d"),{
    type:"bar",
    data:{
      labels: posData.map(d=>d.name.split(" ").slice(-1)[0].substring(0,12)),
      datasets:[{
        label:"Bloom Index",
        data: posData.map(d=>d.bi),
        backgroundColor: posData.map(d=>
          d.bi>=20?"#1E8449AA":d.bi>=10?"#1A56DBAA":d.bi>=0?"#D4700AAA":"#C0392BAA"),
        borderRadius:4, borderSkipped:false
      }]
    },
    options:{
      indexAxis:"y",responsive:true,
      plugins:{legend:{display:false},tooltip:{callbacks:{
        label: ctx => {
          const d=posData[ctx.dataIndex];
          return [`BI: ${fmt_bi(d.bi)}`, `SQS: ${d.sqs}`, fmt_mv(d.mv), d.upgrade];
        }
      }}},
      scales:{
        x:{grid:{color:"#F1F5F9"},title:{display:true,text:"Bloom Index",font:{size:10}}},
        y:{grid:{display:false},ticks:{font:{size:10}}}
      }
    }
  });

  // Pos scatter
  const tierDS = ["ELITE","HIGH","VALUE","FAIR","OVER"].map(t=>({
    label: TIER_LABEL[t],
    data: DATA.filter(d=>d.pos===pos&&d.tier===t).map(d=>({
      x:d.mv/1000, y:d.sqs, r:Math.max(3,Math.min(10,d.mins/300)), _d:d
    })),
    backgroundColor: TIER_COLOR[t]+"88",
    borderColor: TIER_COLOR[t],
    borderWidth:1
  }));
  posCharts.posScatter = new Chart(document.getElementById("posScatter").getContext("2d"),{
    type:"bubble",
    data:{datasets:tierDS},
    options:{
      responsive:true,
      plugins:{
        legend:{position:"top",labels:{boxWidth:10,font:{size:9}}},
        tooltip:{callbacks:{label:ctx=>{
          const d=ctx.raw._d;
          return [`${d.name}`,`SQS ${d.sqs}  BI ${fmt_bi(d.bi)}`,fmt_mv(d.mv)];
        }}}
      },
      scales:{
        x:{title:{display:true,text:"Market Value (€k)",font:{size:10}},grid:{color:"#F1F5F9"}},
        y:{min:0,max:100,title:{display:true,text:"SQS Rank",font:{size:10}},grid:{color:"#F1F5F9"}}
      }
    }
  });

  // Age distribution
  const allAges = DATA.filter(d=>d.pos===pos).map(d=>d.age);
  const ageBins = {};
  allAges.forEach(a => { ageBins[a]=(ageBins[a]||0)+1; });
  const ageKeys = Object.keys(ageBins).sort((a,b)=>+a-+b);
  posCharts.posAgeBar = new Chart(document.getElementById("posAgeBar").getContext("2d"),{
    type:"bar",
    data:{
      labels:ageKeys,
      datasets:[{
        data:ageKeys.map(k=>ageBins[k]),
        backgroundColor: ageKeys.map(k=>+k<=23?"#1E8449AA":+k<=27?"#1A56DBAA":"#D4700AAA"),
        borderRadius:3, borderSkipped:false
      }]
    },
    options:{
      responsive:true,
      plugins:{legend:{display:false}},
      scales:{x:{grid:{display:false}},y:{grid:{color:"#F1F5F9"}}}
    }
  });

  // Tier donut
  const posTiers = {};
  DATA.filter(d=>d.pos===pos).forEach(d=>{ posTiers[d.tier]=(posTiers[d.tier]||0)+1; });
  posCharts.posTierDonut = new Chart(document.getElementById("posTierDonut").getContext("2d"),{
    type:"doughnut",
    data:{
      labels:["ELITE","HIGH","VALUE","FAIR","OVER"].filter(t=>posTiers[t]>0).map(t=>TIER_LABEL[t]),
      datasets:[{
        data:["ELITE","HIGH","VALUE","FAIR","OVER"].filter(t=>posTiers[t]>0).map(t=>posTiers[t]),
        backgroundColor:["ELITE","HIGH","VALUE","FAIR","OVER"].filter(t=>posTiers[t]>0).map(t=>TIER_COLOR[t]),
        borderWidth:2,borderColor:"#fff"
      }]
    },
    options:{cutout:"58%",responsive:true,plugins:{legend:{position:"bottom",labels:{boxWidth:10,font:{size:10}}}}}
  });
}

document.querySelectorAll("#tab-positions .pos-btn").forEach(btn => {
  btn.addEventListener("click", () => renderPositionTab(btn.dataset.pos));
});
renderPositionTab("W");

// ══════════════════════════════════════════════════════════════════════════
// FULL TABLE
// ══════════════════════════════════════════════════════════════════════════
let tblPos="ALL", tblTier="", tblUpgrade="";

function buildTableRows(data){
  return data.sort((a,b)=>b.bi-a.bi).map((d,i)=>[
    i+1,
    `<strong>${d.name}</strong><br><small style="color:#aaa">${d.position}</small>`,
    `<span class="cb" style="font-weight:700">${d.pos}</span>`,
    d.team, d.league,
    d.age<=23?`<span class="cg">${d.age}</span>`:d.age,
    d.cflag==="2026"?`${d.contract} <span class="cflag">✦</span>`:d.contract,
    fmt_mv(d.mv),
    `<span style="font-weight:700;color:${sqs_color(d.sqs)}">${d.sqs}</span>`,
    `<span style="font-weight:700;color:${bi_color(d.bi)}">${fmt_bi(d.bi)}</span>`,
    tier_chip(d.tier), upg_chip(d.upgrade),
    `<span style="font-weight:700;color:${d.gap>0?"#1E8449":"#C0392B"}">${fmt_bi(d.gap)}</span>`,
    d.mins, d.g90, d.xg90, d.a90, d.pp90, d.ddw+"%", d.int90
  ]);
}

function applyTableFilters(){
  const data = DATA.filter(d => {
    if(tblPos!=="ALL"&&d.pos!==tblPos) return false;
    if(tblTier&&d.tier!==tblTier) return false;
    if(tblUpgrade&&d.upgrade!==tblUpgrade) return false;
    return true;
  });
  if($.fn.DataTable.isDataTable("#mainTable")){
    const dt=$("#mainTable").DataTable();
    dt.clear(); dt.rows.add(buildTableRows(data)); dt.draw();
  } else {
    $("#mainTable").DataTable({
      data:buildTableRows(data), pageLength:25,
      lengthMenu:[25,50,100,551],
      columnDefs:[{targets:[1,9,10,11],orderable:false}],
      language:{search:"Search:"},
      drawCallback:function(){
        document.getElementById("tbl-count").textContent=
          this.api().rows({filter:"applied"}).count()+" players";
      }
    });
  }
  document.getElementById("tbl-count").textContent=data.length+" players";
}

document.querySelectorAll(".tbl-pos-btn").forEach(btn => {
  btn.addEventListener("click",()=>{
    document.querySelectorAll(".tbl-pos-btn").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active"); tblPos=btn.dataset.pos; applyTableFilters();
  });
});
document.getElementById("tblTier").addEventListener("change",e=>{tblTier=e.target.value;applyTableFilters();});
document.getElementById("tblUpgrade").addEventListener("change",e=>{tblUpgrade=e.target.value;applyTableFilters();});
applyTableFilters();
</script>

<div style="padding:16px 32px;font-size:10px;color:#AAA;border-top:1px solid var(--border);background:#fff;margin-top:8px">
  <strong>Methodology:</strong> Statistical Quality Score (SQS) = position-weighted per-90 Wyscout metrics, league-difficulty adjusted (CZ II ×0.82 · Slovakia ×0.78 · Slovakia II ×0.68).
  Bloom Index = SQS percentile &minus; Market Value percentile. Positive = underpriced. XGBoost OOF predictions for model value.
  Pizza percentiles computed within position group. ✦ = contract expiring June 2026.
  &nbsp;&middot;&nbsp; Waltzing Analytics &middot; FC Hradec Králové 2025-26
</div>
</body>
</html>"""


if __name__ == "__main__":
    build()
