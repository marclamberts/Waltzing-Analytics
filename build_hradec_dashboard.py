"""
FC Hradec Králové — Jamestown Recruitment Dashboard
Generates a self-contained HTML file with embedded data + Chart.js + DataTables.
"""

import os, json
import numpy as np
import pandas as pd

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_FILE  = os.path.join(BASE_DIR, "hradec_recruitment_2526.xlsx")
SQUAD_FILE = os.path.join(BASE_DIR, "hradec_player_tracking.xlsx")
OUTPUT     = os.path.join(BASE_DIR, "hradec_recruitment_dashboard.html")


def load_data():
    df = pd.read_excel(DATA_FILE, sheet_name="All Targets (ranked)")
    squad = pd.read_excel(DATA_FILE, sheet_name="Hradec Squad")

    num_cols = ["Market value", "model_value", "value_ratio", "sqs_rank",
                "bloom_index", "vs_hradec_gap", "Age", "Minutes played",
                "Goals per 90", "xG per 90", "Assists per 90", "xA per 90",
                "Progressive passes per 90", "Progressive runs per 90",
                "Touches in box per 90", "Defensive duels won, %",
                "Aerial duels won, %", "Dribbles per 90",
                "Successful dribbles, %", "Key passes per 90",
                "PAdj Interceptions", "Save rate, %", "Prevented goals per 90"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df["contract_flag"] = df["Contract expires"].fillna("").astype(str).apply(
        lambda x: "2026" if "2026" in x else ("2027" if "2027" in x else ""))

    return df, squad


def player_records(df):
    rows = []
    for _, r in df.iterrows():
        bi = r.get("bloom_index", 0)
        tier = str(r.get("value_tier", ""))
        tier_short = ("ELITE" if "ELITE" in tier else
                      "HIGH"  if "HIGH"  in tier else
                      "VALUE" if tier == "VALUE" else
                      "FAIR"  if "FAIR"  in tier else "OVER")
        rows.append({
            "name":      str(r["Player"]),
            "team":      str(r["Team"]),
            "league":    str(r["league"]),
            "pos":       str(r["pos_group"]),
            "position":  str(r["Position"]),
            "age":       int(r["Age"]),
            "contract":  str(r.get("Contract expires", ""))[:10],
            "cflag":     str(r.get("contract_flag", "")),
            "mv":        int(r.get("Market value", 0)),
            "model_v":   int(r.get("model_value", 0)),
            "sqs":       round(float(r.get("sqs_rank", 0)), 1),
            "bi":        round(float(bi), 1),
            "tier":      tier_short,
            "upgrade":   str(r.get("upgrade_flag", "")),
            "gap":       round(float(r.get("vs_hradec_gap", 0)), 1),
            "starters":  str(r.get("hradec_starters", "")),
            "mins":      int(r.get("Minutes played", 0)),
            "g90":       round(float(r.get("Goals per 90", 0)), 2),
            "xg90":      round(float(r.get("xG per 90", 0)), 2),
            "a90":       round(float(r.get("Assists per 90", 0)), 2),
            "xa90":      round(float(r.get("xA per 90", 0)), 2),
            "pp90":      round(float(r.get("Progressive passes per 90", 0)), 2),
            "pr90":      round(float(r.get("Progressive runs per 90", 0)), 2),
            "tib90":     round(float(r.get("Touches in box per 90", 0)), 2),
            "ddw":       round(float(r.get("Defensive duels won, %", 0)), 1),
            "adw":       round(float(r.get("Aerial duels won, %", 0)), 1),
            "drib90":    round(float(r.get("Dribbles per 90", 0)), 2),
            "drib_pct":  round(float(r.get("Successful dribbles, %", 0)), 1),
            "kp90":      round(float(r.get("Key passes per 90", 0)), 2),
            "int90":     round(float(r.get("PAdj Interceptions", 0)), 2),
            "sv_pct":    round(float(r.get("Save rate, %", 0)), 1),
            "pg90":      round(float(r.get("Prevented goals per 90", 0)), 2),
        })
    return rows


def tier_counts(df):
    mapping = {"ELITE VALUE": "ELITE", "HIGH VALUE": "HIGH",
               "VALUE": "VALUE", "FAIR PRICE": "FAIR", "OVERVALUED": "OVER"}
    counts = {"ELITE": 0, "HIGH": 0, "VALUE": 0, "FAIR": 0, "OVER": 0}
    for v in df["value_tier"]:
        k = mapping.get(str(v), "FAIR")
        counts[k] += 1
    return counts


def upgrade_counts(df):
    uf = df["upgrade_flag"].value_counts().to_dict()
    return {str(k): int(v) for k, v in uf.items()}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FC Hradec Králové — Jamestown Recruitment 2025-26</title>

<!-- DataTables -->
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">
<!-- Fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

<style>
:root {
  --blue:   #1A56DB;
  --green:  #1E8449;
  --amber:  #D4700A;
  --red:    #C0392B;
  --black:  #111111;
  --grey1:  #444444;
  --grey2:  #666666;
  --grey3:  #AAAAAA;
  --grey4:  #F4F6F8;
  --white:  #FFFFFF;
  --border: #E2E8F0;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Inter', sans-serif; background: #F8FAFC; color: var(--black); font-size: 14px; }

/* ── Header ── */
.header { background: var(--blue); color: white; padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; }
.header h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.3px; }
.header .sub { font-size: 12px; opacity: 0.8; margin-top: 2px; }
.badge { background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }

/* ── KPI Row ── */
.kpi-row { display: flex; gap: 16px; padding: 20px 32px 0; flex-wrap: wrap; }
.kpi { background: white; border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; flex: 1; min-width: 140px; }
.kpi .val { font-size: 28px; font-weight: 700; line-height: 1; margin-bottom: 4px; }
.kpi .lbl { font-size: 11px; color: var(--grey2); text-transform: uppercase; letter-spacing: 0.5px; }
.kpi.blue  .val { color: var(--blue); }
.kpi.green .val { color: var(--green); }
.kpi.amber .val { color: var(--amber); }
.kpi.red   .val { color: var(--red); }

/* ── Charts row ── */
.charts-row { display: flex; gap: 16px; padding: 20px 32px; flex-wrap: wrap; }
.chart-card { background: white; border: 1px solid var(--border); border-radius: 10px; padding: 20px; flex: 1; min-width: 280px; }
.chart-card h3 { font-size: 13px; font-weight: 600; color: var(--grey1); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.4px; }
.chart-card .canvas-wrap { position: relative; }

/* ── Filter bar ── */
.filter-bar { padding: 0 32px 12px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.filter-bar label { font-size: 12px; color: var(--grey2); font-weight: 500; }
.pos-btn { padding: 5px 14px; border-radius: 20px; border: 1.5px solid var(--border); background: white; cursor: pointer; font-size: 12px; font-weight: 600; color: var(--grey2); transition: all 0.15s; }
.pos-btn:hover { border-color: var(--blue); color: var(--blue); }
.pos-btn.active { background: var(--blue); border-color: var(--blue); color: white; }
.tier-select, .upgrade-select { padding: 5px 10px; border-radius: 6px; border: 1.5px solid var(--border); font-size: 12px; font-family: inherit; }

/* ── Table section ── */
.table-wrap { padding: 0 32px 40px; }
.table-card { background: white; border: 1px solid var(--border); border-radius: 10px; padding: 20px; overflow: hidden; }
.table-card h3 { font-size: 13px; font-weight: 600; color: var(--grey1); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.4px; }

/* DataTables overrides */
table.dataTable thead th { background: #F1F5F9; color: var(--grey1); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; border-bottom: 2px solid var(--border) !important; padding: 10px 12px; }
table.dataTable tbody td { padding: 8px 12px; font-size: 13px; border-bottom: 1px solid #F1F5F9; vertical-align: middle; }
table.dataTable tbody tr:hover td { background: #F8FAFC; }
.dataTables_wrapper .dataTables_filter input { border: 1.5px solid var(--border); border-radius: 6px; padding: 4px 10px; font-family: inherit; font-size: 13px; }
.dataTables_wrapper .dataTables_length select { border: 1.5px solid var(--border); border-radius: 6px; font-family: inherit; font-size: 13px; }
.dataTables_wrapper .dataTables_paginate .paginate_button.current { background: var(--blue) !important; color: white !important; border-radius: 6px; border: none !important; }
.dataTables_wrapper .dataTables_paginate .paginate_button:hover { background: #EEF2FF !important; color: var(--blue) !important; border-radius: 6px; border: none !important; }

/* ── Chips / badges ── */
.tier-chip { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; }
.tier-ELITE { background: #D1FAE5; color: #065F46; }
.tier-HIGH  { background: #DCFCE7; color: #166534; }
.tier-VALUE { background: #DBEAFE; color: #1E40AF; }
.tier-FAIR  { background: #F3F4F6; color: #4B5563; }
.tier-OVER  { background: #FEE2E2; color: #991B1B; }

.upgrade-chip { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.up-CLEAR  { background: #D1FAE5; color: #065F46; }
.up-ROT    { background: #FEF3C7; color: #92400E; }
.up-DEPTH  { background: #F3F4F6; color: #4B5563; }

.num-green { color: var(--green); font-weight: 700; }
.num-amber { color: var(--amber); font-weight: 700; }
.num-red   { color: var(--red);   font-weight: 700; }
.num-blue  { color: var(--blue);  font-weight: 700; }
.cflag     { color: var(--red);   font-weight: 700; font-size: 11px; }

/* ── Tooltip ── */
#tooltip {
  position: fixed; display: none; background: white; border: 1px solid var(--border);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12); border-radius: 10px; padding: 14px 16px;
  z-index: 999; max-width: 260px; pointer-events: none; font-size: 13px;
}
#tooltip h4 { font-size: 14px; font-weight: 700; margin-bottom: 6px; color: var(--black); }
#tooltip .tt-row { display: flex; justify-content: space-between; gap: 20px; margin: 3px 0; font-size: 12px; }
#tooltip .tt-lbl { color: var(--grey2); }
#tooltip .tt-val { font-weight: 600; }

/* ── Footer ── */
.footer { padding: 20px 32px; font-size: 11px; color: var(--grey3); border-top: 1px solid var(--border); background: white; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>FC Hradec Králové &mdash; Jamestown Recruitment Model</h1>
    <div class="sub">2025&ndash;2026 Season &middot; CZ II + Slovakia + Slovakia II &middot; Budget cap €1M</div>
  </div>
  <div class="badge">__TOTAL__ candidates</div>
</div>

<!-- KPI row -->
<div class="kpi-row">
  <div class="kpi green"><div class="val" id="kpi-elite">—</div><div class="lbl">Elite Value picks</div></div>
  <div class="kpi blue"> <div class="val" id="kpi-upgrades">—</div><div class="lbl">Clear upgrades</div></div>
  <div class="kpi amber"><div class="val" id="kpi-u23">—</div><div class="lbl">Players ≤ 23</div></div>
  <div class="kpi red">  <div class="val" id="kpi-exp">—</div><div class="lbl">Expiring 2026 ✦</div></div>
  <div class="kpi blue"> <div class="val" id="kpi-avg-bi">—</div><div class="lbl">Avg Bloom Index (upgrades)</div></div>
  <div class="kpi green"><div class="val" id="kpi-avg-mv">—</div><div class="lbl">Avg mkt val (upgrades)</div></div>
</div>

<!-- Charts -->
<div class="charts-row">
  <div class="chart-card" style="flex:2; min-width:400px;">
    <h3>SQS Rank vs Market Value — coloured by Bloom Tier</h3>
    <div class="canvas-wrap"><canvas id="scatterChart" height="260"></canvas></div>
  </div>
  <div class="chart-card" style="flex:1;">
    <h3>Bloom Value Tier Breakdown</h3>
    <div class="canvas-wrap"><canvas id="donutChart" height="220"></canvas></div>
  </div>
  <div class="chart-card" style="flex:1;">
    <h3>Candidates by Position</h3>
    <div class="canvas-wrap"><canvas id="barChart" height="220"></canvas></div>
  </div>
</div>

<!-- Filter bar -->
<div class="filter-bar">
  <label>Position:</label>
  <button class="pos-btn active" data-pos="ALL">All</button>
  <button class="pos-btn" data-pos="GK">GK</button>
  <button class="pos-btn" data-pos="CB">CB</button>
  <button class="pos-btn" data-pos="FB">FB</button>
  <button class="pos-btn" data-pos="DM">DM</button>
  <button class="pos-btn" data-pos="CM">CM</button>
  <button class="pos-btn" data-pos="W">W</button>
  <button class="pos-btn" data-pos="FW">FW</button>
  &nbsp;&nbsp;
  <label>Tier:</label>
  <select class="tier-select" id="tierFilter">
    <option value="">All tiers</option>
    <option value="ELITE">Elite Value</option>
    <option value="HIGH">High Value</option>
    <option value="VALUE">Value</option>
    <option value="FAIR">Fair Price</option>
    <option value="OVER">Overvalued</option>
  </select>
  <label>Status:</label>
  <select class="upgrade-select" id="upgradeFilter">
    <option value="">All statuses</option>
    <option value="CLEAR UPGRADE">Clear Upgrade</option>
    <option value="ROTATIONAL / COVER">Rotational / Cover</option>
    <option value="DEPTH">Depth</option>
  </select>
</div>

<!-- Table -->
<div class="table-wrap">
  <div class="table-card">
    <h3>All Candidates &mdash; <span id="row-count">—</span> shown</h3>
    <table id="mainTable" class="dataTable" style="width:100%">
      <thead>
        <tr>
          <th>#</th>
          <th>Player</th>
          <th>Pos</th>
          <th>Team</th>
          <th>League</th>
          <th>Age</th>
          <th>Contract</th>
          <th>Mkt Val €</th>
          <th>SQS Rank</th>
          <th>Bloom Index</th>
          <th>Tier</th>
          <th>Status</th>
          <th>vs Hradec</th>
          <th>Mins</th>
          <th>G/90</th>
          <th>xG/90</th>
          <th>A/90</th>
          <th>PP/90</th>
          <th>PR/90</th>
          <th>DD Won%</th>
          <th>Int/90</th>
        </tr>
      </thead>
      <tbody id="tableBody"></tbody>
    </table>
  </div>
</div>

<!-- Tooltip -->
<div id="tooltip"></div>

<!-- Footer -->
<div class="footer">
  Jamestown Analytics methodology &mdash; Statistical Quality Score (SQS) is a position-weighted composite of per-90 Wyscout metrics, league-difficulty adjusted (CZ II ×0.82, Slovakia ×0.78, Slovakia II ×0.68). &nbsp;
  Bloom Index = SQS percentile rank − Market Value percentile rank. Positive values = underpriced. &nbsp;
  XGBoost out-of-fold predictions used to estimate model value independently. &nbsp;
  ✦ = contract expiring June 2026.
</div>

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>

<script>
const DATA = __DATA_JSON__;

const TIER_COLORS = {
  ELITE: "#1E8449", HIGH: "#27AE60", VALUE: "#1A56DB", FAIR: "#888888", OVER: "#C0392B"
};
const POS_ORDER = ["GK","CB","FB","DM","CM","W","FW"];

// ── KPIs ──
const upgrades = DATA.filter(d => d.upgrade === "CLEAR UPGRADE");
document.getElementById("kpi-elite").textContent    = DATA.filter(d => d.tier === "ELITE").length;
document.getElementById("kpi-upgrades").textContent = upgrades.length;
document.getElementById("kpi-u23").textContent      = DATA.filter(d => d.age <= 23).length;
document.getElementById("kpi-exp").textContent      = DATA.filter(d => d.cflag === "2026").length;
const avgBI = upgrades.length ? (upgrades.reduce((s,d)=>s+d.bi,0)/upgrades.length).toFixed(1) : "—";
const avgMV = upgrades.length ? "€" + Math.round(upgrades.reduce((s,d)=>s+d.mv,0)/upgrades.length/1000) + "k" : "—";
document.getElementById("kpi-avg-bi").textContent = avgBI;
document.getElementById("kpi-avg-mv").textContent = avgMV;

// ── Scatter chart ──
const scatterCtx = document.getElementById("scatterChart").getContext("2d");
const scatterDatasets = Object.entries(TIER_COLORS).map(([tier, color]) => ({
  label: tier,
  data: DATA.filter(d => d.tier === tier).map(d => ({
    x: d.mv / 1000,
    y: d.sqs,
    _d: d
  })),
  backgroundColor: color + "99",
  borderColor: color,
  pointRadius: 5,
  pointHoverRadius: 7,
}));

const scatterChart = new Chart(scatterCtx, {
  type: "scatter",
  data: { datasets: scatterDatasets },
  options: {
    responsive: true,
    plugins: {
      legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } },
      tooltip: { enabled: false }
    },
    scales: {
      x: { title: { display: true, text: "Market Value (€k)", font: { size: 11 } }, grid: { color: "#F1F5F9" } },
      y: { title: { display: true, text: "SQS Rank (0–100)", font: { size: 11 } }, min: 0, max: 100, grid: { color: "#F1F5F9" } }
    },
    onHover: (e, els) => {
      const tt = document.getElementById("tooltip");
      if (!els.length) { tt.style.display = "none"; return; }
      const pt = els[0];
      const d  = scatterChart.data.datasets[pt.datasetIndex].data[pt.index]._d;
      tt.innerHTML = `
        <h4>${d.name}</h4>
        <div class="tt-row"><span class="tt-lbl">Team</span><span class="tt-val">${d.team}</span></div>
        <div class="tt-row"><span class="tt-lbl">Position</span><span class="tt-val">${d.pos} &middot; Age ${d.age}</span></div>
        <div class="tt-row"><span class="tt-lbl">League</span><span class="tt-val">${d.league}</span></div>
        <div class="tt-row"><span class="tt-lbl">SQS Rank</span><span class="tt-val">${d.sqs}</span></div>
        <div class="tt-row"><span class="tt-lbl">Bloom Index</span><span class="tt-val">${d.bi > 0 ? '+' : ''}${d.bi}</span></div>
        <div class="tt-row"><span class="tt-lbl">Market Value</span><span class="tt-val">€${d.mv.toLocaleString()}</span></div>
        <div class="tt-row"><span class="tt-lbl">Status</span><span class="tt-val">${d.upgrade}</span></div>
        <div class="tt-row"><span class="tt-lbl">vs Hradec</span><span class="tt-val">${d.gap > 0 ? '+' : ''}${d.gap}</span></div>
      `;
      tt.style.display = "block";
      tt.style.left    = (e.native.clientX + 16) + "px";
      tt.style.top     = (e.native.clientY - 20) + "px";
    }
  }
});
document.addEventListener("mousemove", () => {});

// ── Donut chart ──
const tierCounts = __TIER_JSON__;
const donutCtx = document.getElementById("donutChart").getContext("2d");
new Chart(donutCtx, {
  type: "doughnut",
  data: {
    labels: ["Elite Value", "High Value", "Value", "Fair Price", "Overvalued"],
    datasets: [{
      data: [tierCounts.ELITE, tierCounts.HIGH, tierCounts.VALUE, tierCounts.FAIR, tierCounts.OVER],
      backgroundColor: ["#1E8449","#27AE60","#1A56DB","#AAAAAA","#C0392B"],
      borderWidth: 2, borderColor: "white"
    }]
  },
  options: {
    responsive: true, cutout: "62%",
    plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } }
  }
});

// ── Bar chart ──
const barCtx = document.getElementById("barChart").getContext("2d");
const posCounts = POS_ORDER.map(p => DATA.filter(d => d.pos === p).length);
new Chart(barCtx, {
  type: "bar",
  data: {
    labels: POS_ORDER,
    datasets: [{
      data: posCounts,
      backgroundColor: "#1A56DB88",
      borderColor: "#1A56DB",
      borderWidth: 1.5,
      borderRadius: 4,
    }]
  },
  options: {
    responsive: true, indexAxis: "y",
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { color: "#F1F5F9" } },
      y: { grid: { display: false } }
    }
  }
});

// ── Table ──
function tierChip(t) {
  const labels = {ELITE:"Elite Value",HIGH:"High Value",VALUE:"Value",FAIR:"Fair Price",OVER:"Overvalued"};
  return `<span class="tier-chip tier-${t}">${labels[t]||t}</span>`;
}
function upgradeChip(u) {
  if (u === "CLEAR UPGRADE") return `<span class="upgrade-chip up-CLEAR">Clear ▲</span>`;
  if (u.startsWith("ROT"))   return `<span class="upgrade-chip up-ROT">Rotational</span>`;
  return `<span class="upgrade-chip up-DEPTH">Depth</span>`;
}
function mvFmt(v) { return v > 0 ? "€" + v.toLocaleString() : "—"; }
function numCol(v, green_thresh, amber_thresh) {
  const cls = v >= green_thresh ? "num-green" : v >= amber_thresh ? "num-amber" : "num-red";
  return `<span class="${cls}">${v}</span>`;
}
function biCol(v) {
  const cls = v >= 20 ? "num-green" : v >= 10 ? "num-blue" : v >= 0 ? "num-amber" : "num-red";
  return `<span class="${cls}">${v > 0 ? '+' : ''}${v}</span>`;
}
function gapCol(v) {
  const cls = v > 0 ? "num-green" : "num-red";
  return `<span class="${cls}">${v > 0 ? '+' : ''}${v}</span>`;
}

let filteredData = [...DATA];
let activePos = "ALL";

function buildTable(data) {
  const sorted = [...data].sort((a,b) => b.bi - a.bi);
  const rows = sorted.map((d, i) => [
    i + 1,
    `<strong>${d.name}</strong><br><small style="color:#888">${d.position}</small>`,
    `<span class="num-blue" style="font-weight:700">${d.pos}</span>`,
    d.team,
    d.league,
    d.age <= 23 ? `<span class="num-green">${d.age}</span>` : d.age,
    d.cflag === "2026" ? `${d.contract} <span class="cflag">✦</span>` : d.contract,
    mvFmt(d.mv),
    numCol(d.sqs, 70, 40),
    biCol(d.bi),
    tierChip(d.tier),
    upgradeChip(d.upgrade),
    gapCol(d.gap),
    d.mins,
    d.g90, d.xg90, d.a90,
    d.pp90, d.pr90,
    d.ddw + "%",
    d.int90
  ]);

  if ($.fn.DataTable.isDataTable("#mainTable")) {
    const dt = $("#mainTable").DataTable();
    dt.clear();
    dt.rows.add(rows);
    dt.draw();
  } else {
    $("#mainTable").DataTable({
      data: rows,
      pageLength: 25,
      lengthMenu: [25, 50, 100, 551],
      order: [[9, "desc"]],
      columnDefs: [{ targets: [1,9,10,11], orderable: false }],
      language: { search: "Search players:" },
      drawCallback: function() {
        document.getElementById("row-count").textContent =
          this.api().rows({ filter: "applied" }).count();
      }
    });
  }
  document.getElementById("row-count").textContent = rows.length;
}

// Filters
function applyFilters() {
  const tier    = document.getElementById("tierFilter").value;
  const upgrade = document.getElementById("upgradeFilter").value;
  filteredData = DATA.filter(d => {
    if (activePos !== "ALL" && d.pos !== activePos) return false;
    if (tier    && d.tier    !== tier)    return false;
    if (upgrade && d.upgrade !== upgrade) return false;
    return true;
  });
  buildTable(filteredData);

  // Update scatter
  scatterChart.data.datasets.forEach(ds => {
    const tier_key = ds.label;
    ds.data = filteredData
      .filter(d => d.tier === tier_key)
      .map(d => ({ x: d.mv / 1000, y: d.sqs, _d: d }));
  });
  scatterChart.update();
}

document.querySelectorAll(".pos-btn").forEach(btn => {
  btn.addEventListener("click", function() {
    document.querySelectorAll(".pos-btn").forEach(b => b.classList.remove("active"));
    this.classList.add("active");
    activePos = this.dataset.pos;
    applyFilters();
  });
});
document.getElementById("tierFilter").addEventListener("change", applyFilters);
document.getElementById("upgradeFilter").addEventListener("change", applyFilters);

buildTable(DATA);
</script>
</body>
</html>
"""


def build():
    print("Loading data...")
    df, squad = load_data()

    records = player_records(df)
    tier_c  = tier_counts(df)
    total   = len(records)

    html = HTML_TEMPLATE
    html = html.replace("__DATA_JSON__", json.dumps(records, ensure_ascii=False))
    html = html.replace("__TIER_JSON__", json.dumps(tier_c))
    html = html.replace("__TOTAL__", str(total))

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Done → {OUTPUT}  ({total} players, {os.path.getsize(OUTPUT)//1024} KB)")


if __name__ == "__main__":
    build()
