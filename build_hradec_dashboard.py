"""
FC Hradec Králové — Jamestown Recruitment Dashboard v3
Pizza · Beeswarm · Quadrant Scatter · Waffle · Comparison · Shortlist · Spark bars
"""
import os, json
import pandas as pd

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "hradec_recruitment_2526.xlsx")
OUTPUT    = os.path.join(BASE_DIR, "hradec_recruitment_dashboard.html")

STAT_COLS = [
    "Goals per 90","xG per 90","Assists per 90","xA per 90",
    "Progressive passes per 90","Progressive runs per 90","Touches in box per 90",
    "Defensive duels won, %","Aerial duels won, %","Dribbles per 90",
    "Successful dribbles, %","Key passes per 90","PAdj Interceptions",
    "Save rate, %","Prevented goals per 90",
]

PIZZA_METRICS = {
    "GK":[{"key":"sv_pct","label":"Save Rate %","cat":"gk"},{"key":"pg90","label":"Prevented Goals/90","cat":"gk"},
          {"key":"adw","label":"Aerial Won %","cat":"def"},{"key":"ddw","label":"Def Duels Won %","cat":"def"},
          {"key":"int90","label":"Interceptions/90","cat":"def"},{"key":"pp90","label":"Prog Passes/90","cat":"pass"}],
    "CB":[{"key":"ddw","label":"Def Duels Won %","cat":"def"},{"key":"adw","label":"Aerial Won %","cat":"def"},
          {"key":"int90","label":"Interceptions/90","cat":"def"},{"key":"pp90","label":"Prog Passes/90","cat":"pass"},
          {"key":"pr90","label":"Prog Runs/90","cat":"pass"},{"key":"kp90","label":"Key Passes/90","cat":"pass"},
          {"key":"xg90","label":"xG/90","cat":"att"}],
    "FB":[{"key":"ddw","label":"Def Duels Won %","cat":"def"},{"key":"adw","label":"Aerial Won %","cat":"def"},
          {"key":"int90","label":"Interceptions/90","cat":"def"},{"key":"pr90","label":"Prog Runs/90","cat":"pass"},
          {"key":"pp90","label":"Prog Passes/90","cat":"pass"},{"key":"kp90","label":"Key Passes/90","cat":"pass"},
          {"key":"xa90","label":"xA/90","cat":"att"},{"key":"a90","label":"Assists/90","cat":"att"}],
    "DM":[{"key":"int90","label":"Interceptions/90","cat":"def"},{"key":"ddw","label":"Def Duels Won %","cat":"def"},
          {"key":"adw","label":"Aerial Won %","cat":"def"},{"key":"pp90","label":"Prog Passes/90","cat":"pass"},
          {"key":"kp90","label":"Key Passes/90","cat":"pass"},{"key":"pr90","label":"Prog Runs/90","cat":"pass"},
          {"key":"xa90","label":"xA/90","cat":"att"},{"key":"xg90","label":"xG/90","cat":"att"}],
    "CM":[{"key":"pp90","label":"Prog Passes/90","cat":"pass"},{"key":"kp90","label":"Key Passes/90","cat":"pass"},
          {"key":"pr90","label":"Prog Runs/90","cat":"pass"},{"key":"xg90","label":"xG/90","cat":"att"},
          {"key":"xa90","label":"xA/90","cat":"att"},{"key":"g90","label":"Goals/90","cat":"att"},
          {"key":"a90","label":"Assists/90","cat":"att"},{"key":"int90","label":"Interceptions/90","cat":"def"},
          {"key":"ddw","label":"Def Duels Won %","cat":"def"}],
    "W": [{"key":"g90","label":"Goals/90","cat":"att"},{"key":"xg90","label":"xG/90","cat":"att"},
          {"key":"a90","label":"Assists/90","cat":"att"},{"key":"xa90","label":"xA/90","cat":"att"},
          {"key":"drib90","label":"Dribbles/90","cat":"att"},{"key":"drib_pct","label":"Dribble Succ %","cat":"att"},
          {"key":"tib90","label":"Box Touches/90","cat":"att"},{"key":"pr90","label":"Prog Runs/90","cat":"pass"},
          {"key":"kp90","label":"Key Passes/90","cat":"pass"},{"key":"ddw","label":"Def Duels Won %","cat":"def"}],
    "FW":[{"key":"g90","label":"Goals/90","cat":"att"},{"key":"xg90","label":"xG/90","cat":"att"},
          {"key":"a90","label":"Assists/90","cat":"att"},{"key":"xa90","label":"xA/90","cat":"att"},
          {"key":"tib90","label":"Box Touches/90","cat":"att"},{"key":"drib90","label":"Dribbles/90","cat":"att"},
          {"key":"adw","label":"Aerial Won %","cat":"def"},{"key":"kp90","label":"Key Passes/90","cat":"pass"}],
}

KEY_MAP = {
    "g90":"Goals per 90","xg90":"xG per 90","a90":"Assists per 90","xa90":"xA per 90",
    "pp90":"Progressive passes per 90","pr90":"Progressive runs per 90",
    "tib90":"Touches in box per 90","ddw":"Defensive duels won, %",
    "adw":"Aerial duels won, %","drib90":"Dribbles per 90",
    "drib_pct":"Successful dribbles, %","kp90":"Key passes per 90",
    "int90":"PAdj Interceptions","sv_pct":"Save rate, %","pg90":"Prevented goals per 90",
}

def load_data():
    df = pd.read_excel(DATA_FILE, sheet_name="All Targets (ranked)")
    for c in STAT_COLS+["Market value","model_value","value_ratio","sqs_rank",
                         "bloom_index","vs_hradec_gap","Age","Minutes played"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["contract_flag"] = df["Contract expires"].fillna("").astype(str).apply(
        lambda x: "2026" if "2026" in x else ("2027" if "2027" in x else ""))
    for pos in df["pos_group"].unique():
        mask = df["pos_group"]==pos
        for col in STAT_COLS:
            if col in df.columns:
                df.loc[mask, col+"_pct"] = df.loc[mask,col].rank(pct=True).mul(100).round(1)
    return df

def player_records(df):
    rows=[]
    for _,r in df.iterrows():
        bi=float(r.get("bloom_index",0))
        tier=str(r.get("value_tier",""))
        ts=("ELITE" if "ELITE" in tier else "HIGH" if "HIGH" in tier
            else "VALUE" if tier=="VALUE" else "FAIR" if "FAIR" in tier else "OVER")
        rec={"name":str(r["Player"]),"team":str(r["Team"]),"league":str(r["league"]),
             "pos":str(r["pos_group"]),"position":str(r["Position"]),"age":int(r["Age"]),
             "contract":str(r.get("Contract expires",""))[:10],"cflag":str(r.get("contract_flag","")),
             "mv":int(r.get("Market value",0)),"model_v":int(r.get("model_value",0)),
             "sqs":round(float(r.get("sqs_rank",0)),1),"bi":round(bi,1),"tier":ts,
             "upgrade":str(r.get("upgrade_flag","")),"gap":round(float(r.get("vs_hradec_gap",0)),1),
             "starters":str(r.get("hradec_starters","")),"mins":int(r.get("Minutes played",0)),
             "g90":round(float(r.get("Goals per 90",0)),2),"xg90":round(float(r.get("xG per 90",0)),2),
             "a90":round(float(r.get("Assists per 90",0)),2),"xa90":round(float(r.get("xA per 90",0)),2),
             "pp90":round(float(r.get("Progressive passes per 90",0)),2),
             "pr90":round(float(r.get("Progressive runs per 90",0)),2),
             "tib90":round(float(r.get("Touches in box per 90",0)),2),
             "ddw":round(float(r.get("Defensive duels won, %",0)),1),
             "adw":round(float(r.get("Aerial duels won, %",0)),1),
             "drib90":round(float(r.get("Dribbles per 90",0)),2),
             "drib_pct":round(float(r.get("Successful dribbles, %",0)),1),
             "kp90":round(float(r.get("Key passes per 90",0)),2),
             "int90":round(float(r.get("PAdj Interceptions",0)),2),
             "sv_pct":round(float(r.get("Save rate, %",0)),1),
             "pg90":round(float(r.get("Prevented goals per 90",0)),2)}
        for key,col in KEY_MAP.items():
            rec[key+"_pct"]=round(float(r.get(col+"_pct",0) if col+"_pct" in r.index else 0),1)
        rows.append(rec)
    return rows

def build():
    print("Loading & computing percentiles...")
    df = load_data()
    records = player_records(df)
    tier_counts={t:sum(1 for r in records if r["tier"]==t) for t in ["ELITE","HIGH","VALUE","FAIR","OVER"]}
    pos_counts={p:sum(1 for r in records if r["pos"]==p) for p in ["GK","CB","FB","DM","CM","W","FW"]}
    pizza_meta={pos:[{"key":m["key"],"label":m["label"],"cat":m["cat"]} for m in ms]
                for pos,ms in PIZZA_METRICS.items()}
    html = HTML_TEMPLATE
    html = html.replace("__DATA_JSON__",   json.dumps(records, ensure_ascii=False))
    html = html.replace("__TIER_JSON__",   json.dumps(tier_counts))
    html = html.replace("__POS_JSON__",    json.dumps(pos_counts))
    html = html.replace("__PIZZA_JSON__",  json.dumps(pizza_meta))
    html = html.replace("__TOTAL__",       str(len(records)))
    with open(OUTPUT,"w",encoding="utf-8") as f:
        f.write(html)
    print(f"Done → {OUTPUT}  ({len(records)} players, {os.path.getsize(OUTPUT)//1024} KB)")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FC Hradec Králové — Jamestown Recruitment 2025-26</title>
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
:root{--blue:#1A56DB;--green:#1E8449;--amber:#D4700A;--red:#C0392B;--purple:#7C3AED;
      --k:#111;--g1:#374151;--g2:#6B7280;--g3:#9CA3AF;--g4:#F3F4F6;--g5:#F9FAFB;
      --border:#E5E7EB;--white:#fff;--shadow:0 1px 3px rgba(0,0,0,.06),0 4px 14px rgba(0,0,0,.05)}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'Inter',sans-serif;background:#F1F5F9;color:var(--k);font-size:14px;min-height:100vh}

/* ── HEADER ── */
.hdr{background:linear-gradient(135deg,#1A56DB 0%,#1E3A8A 100%);color:#fff;
     padding:20px 32px;display:flex;align-items:center;justify-content:space-between;
     position:sticky;top:0;z-index:200;box-shadow:0 2px 12px rgba(0,0,0,.15)}
.hdr-left{display:flex;align-items:center;gap:16px}
.hdr-logo{width:42px;height:42px;border-radius:50%;background:rgba(255,255,255,.15);
          display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:900;letter-spacing:-1px}
.hdr h1{font-size:18px;font-weight:800;letter-spacing:-.4px}
.hdr .sub{font-size:11px;opacity:.7;margin-top:1px}
.hdr-right{display:flex;align-items:center;gap:10px}
.hdr-pill{background:rgba(255,255,255,.15);backdrop-filter:blur(4px);padding:5px 14px;
          border-radius:20px;font-size:12px;font-weight:700;border:1px solid rgba(255,255,255,.2)}
.shortlist-btn{cursor:pointer;position:relative;font-size:20px;line-height:1;background:none;border:none;color:#fff;padding:4px}
#shortlist-count{position:absolute;top:-3px;right:-3px;background:#EF4444;color:#fff;
                 border-radius:50%;width:16px;height:16px;font-size:9px;font-weight:700;
                 display:none;align-items:center;justify-content:center}

/* ── NAV ── */
.nav{background:#fff;border-bottom:1px solid var(--border);display:flex;padding:0 32px;
     gap:2px;position:sticky;top:82px;z-index:190;box-shadow:0 1px 4px rgba(0,0,0,.04)}
.nav-btn{padding:13px 22px;font-size:13px;font-weight:600;color:var(--g2);border:none;
         background:none;cursor:pointer;border-bottom:3px solid transparent;margin-bottom:-1px;
         transition:.2s;display:flex;align-items:center;gap:7px}
.nav-btn .nb-icon{font-size:14px}
.nav-btn:hover{color:var(--blue);background:#F8FAFF}
.nav-btn.active{color:var(--blue);border-bottom-color:var(--blue)}

/* ── PANELS ── */
.tab-panel{display:none;padding:24px 32px 48px;animation:fadeIn .25s ease}
.tab-panel.active{display:block}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

/* ── CARDS ── */
.card{background:#fff;border:1px solid var(--border);border-radius:12px;padding:20px;box-shadow:var(--shadow)}
.card-title{font-size:11px;font-weight:700;color:var(--g2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:16px;display:flex;align-items:center;gap:8px}
.card-title::before{content:"";width:3px;height:14px;background:var(--blue);border-radius:2px}

/* ── GRIDS ── */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.g3{display:grid;grid-template-columns:2fr 1fr 1fr;gap:16px}
.g4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}

/* ── KPI ── */
.kpi-row{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:20px}
.kpi{background:#fff;border:1px solid var(--border);border-radius:12px;padding:16px 18px;
     position:relative;overflow:hidden;box-shadow:var(--shadow);transition:.2s}
.kpi::after{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--blue);border-radius:12px 12px 0 0}
.kpi.g::after{background:var(--green)} .kpi.a::after{background:var(--amber)} .kpi.r::after{background:var(--red)}
.kpi:hover{transform:translateY(-2px);box-shadow:0 4px 20px rgba(0,0,0,.1)}
.kpi .val{font-size:28px;font-weight:900;line-height:1;letter-spacing:-1px;margin-bottom:4px}
.kpi .lbl{font-size:10px;color:var(--g3);text-transform:uppercase;letter-spacing:.5px}
.kpi:not(.g):not(.a):not(.r) .val{color:var(--blue)}
.kpi.g .val{color:var(--green)} .kpi.a .val{color:var(--amber)} .kpi.r .val{color:var(--red)}

/* ── PLAYER CARDS (Top Picks) ── */
.picks-row{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}
.pick-card{background:#fff;border:1px solid var(--border);border-radius:12px;padding:16px;
           cursor:pointer;transition:.2s;position:relative;box-shadow:var(--shadow);overflow:hidden}
.pick-card::before{content:"";position:absolute;top:0;left:0;right:0;height:44px;
                   background:linear-gradient(135deg,#1A56DB,#1E3A8A)}
.pick-card.tier-ELITE::before{background:linear-gradient(135deg,#1E8449,#166534)}
.pick-card.tier-HIGH::before{background:linear-gradient(135deg,#16A34A,#166534)}
.pick-card.tier-VALUE::before{background:linear-gradient(135deg,#1A56DB,#1E3A8A)}
.pick-avatar{width:44px;height:44px;border-radius:50%;border:2.5px solid #fff;
             display:flex;align-items:center;justify-content:center;font-size:14px;
             font-weight:900;color:#fff;margin:0 auto 8px;position:relative;z-index:1;margin-top:10px}
.pick-name{font-size:12px;font-weight:700;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pick-meta{font-size:10px;color:var(--g3);text-align:center;margin-top:2px}
.pick-stats{display:flex;justify-content:space-around;margin-top:10px;border-top:1px solid var(--border);padding-top:8px}
.pick-stat .ps-val{font-size:14px;font-weight:800;text-align:center}
.pick-stat .ps-lbl{font-size:9px;color:var(--g3);text-align:center;text-transform:uppercase;letter-spacing:.3px}
.pick-badge{position:absolute;top:6px;right:8px;font-size:8px;font-weight:700;
            background:rgba(255,255,255,.25);color:#fff;padding:2px 6px;border-radius:10px}
.pick-star{position:absolute;top:6px;left:8px;font-size:14px;cursor:pointer;color:rgba(255,255,255,.5);z-index:2;transition:.2s}
.pick-star.saved{color:#FCD34D}

/* ── SCATTER ── */
.scatter-wrap{position:relative}
.quadrant-labels{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:10}

/* ── BEESWARM ── */
#beeswarmSvg{width:100%;overflow:visible}

/* ── WAFFLE ── */
.waffle-grid{display:flex;flex-wrap:wrap;gap:3px}
.wsq{width:16px;height:16px;border-radius:3px;cursor:default;transition:.15s}
.wsq:hover{transform:scale(1.4);border-radius:2px}
.wlegend{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
.wleg-item{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--g1)}
.wleg-dot{width:10px;height:10px;border-radius:2px}

/* ── SCOUT ── */
.scout-search-wrap{position:relative;margin-bottom:24px}
.scout-search-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:center}
.search-box{padding:12px 16px 12px 40px;border:2px solid var(--border);border-radius:10px;
            font-size:14px;font-family:inherit;width:100%;outline:none;transition:.2s;background:#fff;
            background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236B7280' stroke-width='2'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.35-4.35'/%3E%3C/svg%3E");
            background-repeat:no-repeat;background-position:12px center}
.search-box:focus{border-color:var(--blue);box-shadow:0 0 0 3px rgba(26,86,219,.1)}
.ac-dropdown{position:absolute;background:#fff;border:1px solid var(--border);border-radius:10px;
             box-shadow:0 12px 32px rgba(0,0,0,.12);z-index:300;width:100%;max-height:300px;overflow-y:auto;top:calc(100% + 4px)}
.ac-item{padding:10px 14px;cursor:pointer;border-bottom:1px solid #F9FAFB;transition:.1s}
.ac-item:last-child{border-bottom:none}
.ac-item:hover{background:#F8FAFF}
.ac-item .ac-name{font-weight:700;font-size:13px}
.ac-item .ac-meta{font-size:11px;color:var(--g3);margin-top:2px}
.scout-header-card{border-radius:12px;padding:20px 24px;color:#fff;margin-bottom:16px;
                   background:linear-gradient(135deg,#1A56DB,#1E3A8A)}
.scout-header-card.tier-ELITE{background:linear-gradient(135deg,#1E8449,#14532D)}
.scout-header-card.tier-HIGH{background:linear-gradient(135deg,#16A34A,#14532D)}
.scout-header-card.tier-OVER{background:linear-gradient(135deg,#C0392B,#7F1D1D)}
.sh-top{display:flex;align-items:center;gap:16px;margin-bottom:14px}
.sh-avatar{width:52px;height:52px;border-radius:50%;background:rgba(255,255,255,.2);
           display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:900;flex-shrink:0}
.sh-name{font-size:22px;font-weight:900;letter-spacing:-.5px}
.sh-meta{font-size:12px;opacity:.75;margin-top:3px}
.sh-nums{display:flex;gap:0;border-top:1px solid rgba(255,255,255,.2);padding-top:12px}
.sh-num{flex:1;text-align:center;border-right:1px solid rgba(255,255,255,.15)}
.sh-num:last-child{border-right:none}
.sh-num .n{font-size:20px;font-weight:900}
.sh-num .l{font-size:9px;opacity:.65;text-transform:uppercase;letter-spacing:.4px;margin-top:2px}
.scout-layout{display:grid;grid-template-columns:460px 1fr;gap:20px;align-items:start}
.pizza-wrap svg{max-width:460px;width:100%;display:block;margin:0 auto}
.pizza-legend{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:10px}
.pl-item{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--g2)}
.pl-dot{width:10px;height:10px;border-radius:50%}
.metric-row{display:flex;align-items:center;padding:7px 0;border-bottom:1px solid #F9FAFB}
.metric-row:last-child{border-bottom:none}
.m-lbl{font-size:12px;color:var(--g2);flex:1}
.m-bar-wrap{width:100px;height:5px;background:#F1F5F9;border-radius:3px;overflow:hidden;margin:0 10px}
.m-bar-fill{height:100%;border-radius:3px}
.m-pct{font-size:12px;font-weight:700;min-width:30px;text-align:right}
.m-raw{font-size:10px;color:var(--g3);min-width:28px;text-align:right}
.compare-mode{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px}
.compare-pizza-card{padding:16px}

/* ── POSITION TAB ── */
.pos-selector{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px;align-items:center}
.pos-btn{padding:6px 16px;border-radius:20px;border:1.5px solid var(--border);background:#fff;
         cursor:pointer;font-size:12px;font-weight:700;color:var(--g2);transition:.15s}
.pos-btn:hover,.pos-btn.active{background:var(--blue);border-color:var(--blue);color:#fff}

/* ── TABLE ── */
.tbl-filters{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.filter-sel{padding:6px 10px;border-radius:8px;border:1.5px solid var(--border);
            font-size:12px;font-family:inherit;background:#fff;cursor:pointer}
.filter-sel:focus{border-color:var(--blue);outline:none}
table.dataTable thead th{background:#F8FAFC;color:var(--g1);font-size:11px;font-weight:700;
  text-transform:uppercase;letter-spacing:.4px;border-bottom:2px solid var(--border)!important;padding:10px 10px}
table.dataTable tbody td{padding:7px 10px;font-size:12px;border-bottom:1px solid #F9FAFB;vertical-align:middle}
table.dataTable tbody tr:hover td{background:#F8FAFF}
.dataTables_wrapper .dataTables_filter input{border:1.5px solid var(--border);border-radius:8px;
  padding:5px 12px;font-family:inherit;font-size:12px}
.dataTables_wrapper .dataTables_length select{border:1.5px solid var(--border);border-radius:8px;font-family:inherit}
.dataTables_wrapper .dataTables_paginate .paginate_button.current{background:var(--blue)!important;
  color:#fff!important;border-radius:8px;border:none!important}
.dataTables_wrapper .dataTables_paginate .paginate_button:hover{background:#EEF2FF!important;
  color:var(--blue)!important;border-radius:8px;border:none!important}

/* ── CHIPS / COLORS ── */
.chip{display:inline-block;padding:2px 7px;border-radius:5px;font-size:10px;font-weight:700}
.te{background:#D1FAE5;color:#065F46} .th{background:#DCFCE7;color:#166534}
.tv{background:#DBEAFE;color:#1E40AF} .tf{background:#F3F4F6;color:#6B7280} .to{background:#FEE2E2;color:#991B1B}
.uc{background:#D1FAE5;color:#065F46} .ur{background:#FEF3C7;color:#92400E} .ud{background:#F3F4F6;color:#6B7280}
.cflag{color:var(--red);font-weight:700;font-size:10px}

/* ── SPARK BAR ── */
.spark{display:inline-block;height:4px;border-radius:2px;vertical-align:middle;margin-left:4px}

/* ── TOOLTIP ── */
#tt{position:fixed;display:none;background:#fff;border:1px solid var(--border);
    box-shadow:0 12px 32px rgba(0,0,0,.14);border-radius:12px;padding:14px 16px;
    z-index:999;max-width:240px;pointer-events:none;font-size:12px}
#tt h4{font-size:13px;font-weight:800;margin-bottom:7px;color:var(--k)}
.tt-r{display:flex;justify-content:space-between;gap:16px;margin:3px 0}
.tt-l{color:var(--g3)} .tt-v{font-weight:700}

/* ── SHORTLIST PANEL ── */
#shortlist-panel{position:fixed;right:-360px;top:0;width:360px;height:100vh;background:#fff;
  box-shadow:-4px 0 24px rgba(0,0,0,.12);z-index:500;transition:.3s;overflow-y:auto;border-left:1px solid var(--border)}
#shortlist-panel.open{right:0}
.sl-header{padding:18px 20px;background:linear-gradient(135deg,#1A56DB,#1E3A8A);color:#fff;
           display:flex;align-items:center;justify-content:space-between}
.sl-header h3{font-size:16px;font-weight:800}
.sl-close{background:none;border:none;color:#fff;font-size:20px;cursor:pointer;line-height:1}
.sl-player{padding:14px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px}
.sl-avatar{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;
           font-size:12px;font-weight:900;color:#fff;flex-shrink:0}
.sl-info .sl-name{font-size:13px;font-weight:700}
.sl-info .sl-meta{font-size:11px;color:var(--g3)}
.sl-remove{margin-left:auto;background:none;border:none;color:var(--g3);cursor:pointer;font-size:16px;padding:4px}
.sl-empty{padding:40px 20px;text-align:center;color:var(--g3)}
#overlay{position:fixed;inset:0;background:rgba(0,0,0,.3);z-index:499;display:none}

/* ── FOOTER ── */
.footer{padding:16px 32px;font-size:10px;color:var(--g3);border-top:1px solid var(--border);
        background:#fff;margin-top:4px;line-height:1.7}
</style>
</head>
<body>

<header class="hdr">
  <div class="hdr-left">
    <div class="hdr-logo">HK</div>
    <div>
      <h1>FC Hradec Králové &mdash; Jamestown Recruitment Model</h1>
      <div class="sub">2025&ndash;26 &middot; CZ II &middot; Slovakia &middot; Slovakia II &middot; Budget cap &euro;1M</div>
    </div>
  </div>
  <div class="hdr-right">
    <div class="hdr-pill">__TOTAL__ candidates</div>
    <button class="shortlist-btn" onclick="toggleShortlist()" title="View shortlist">
      ★<span id="shortlist-count"></span>
    </button>
  </div>
</header>

<nav class="nav">
  <button class="nav-btn active" data-tab="overview"><span class="nb-icon">📊</span> Overview</button>
  <button class="nav-btn" data-tab="scout"><span class="nb-icon">🔍</span> Player Scout</button>
  <button class="nav-btn" data-tab="compare"><span class="nb-icon">⚖️</span> Compare</button>
  <button class="nav-btn" data-tab="positions"><span class="nb-icon">📍</span> By Position</button>
  <button class="nav-btn" data-tab="table"><span class="nb-icon">📋</span> All Players</button>
</nav>

<!-- ══ OVERVIEW ══ -->
<div id="tab-overview" class="tab-panel active">
  <div class="kpi-row">
    <div class="kpi g"><div class="val" id="k-elite">—</div><div class="lbl">Elite Value</div></div>
    <div class="kpi" ><div class="val" id="k-upgr">—</div><div class="lbl">Clear Upgrades</div></div>
    <div class="kpi a"><div class="val" id="k-u23">—</div><div class="lbl">Players ≤ 23</div></div>
    <div class="kpi r"><div class="val" id="k-exp">—</div><div class="lbl">Expiring 2026 ✦</div></div>
    <div class="kpi" ><div class="val" id="k-avgbi">—</div><div class="lbl">Avg Bloom (upgrades)</div></div>
    <div class="kpi g"><div class="val" id="k-avgmv">—</div><div class="lbl">Avg Value (upgrades)</div></div>
  </div>

  <div style="margin-bottom:8px;font-size:11px;font-weight:700;color:var(--g2);text-transform:uppercase;letter-spacing:.5px">
    ⭐ Top Elite Value &mdash; Clear Upgrades
  </div>
  <div class="picks-row" id="top-picks"></div>

  <div class="g2" style="margin-bottom:16px">
    <div class="card">
      <div class="card-title">SQS Rank vs Market Value &mdash; opportunity quadrant highlighted</div>
      <div style="position:relative">
        <canvas id="scatterChart" height="290"></canvas>
        <div id="quadrant-lbl" style="position:absolute;pointer-events:none;font-size:10px;font-weight:700;
          color:#1E8449;border:1.5px dashed #1E8449;padding:3px 8px;border-radius:6px;opacity:0.6;top:22px;left:60px">
          OPPORTUNITY ZONE
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Bloom Index distribution by position</div>
      <svg id="beeswarmSvg" height="290" style="width:100%;overflow:visible"></svg>
    </div>
  </div>

  <div class="g3">
    <div class="card">
      <div class="card-title">Bloom value tier breakdown — each square ≈ 5 players</div>
      <div class="waffle-grid" id="waffleGrid"></div>
      <div class="wlegend" id="waffleLegend"></div>
    </div>
    <div class="card">
      <div class="card-title">Candidates by position</div>
      <canvas id="posBar" height="230"></canvas>
    </div>
    <div class="card">
      <div class="card-title">League distribution</div>
      <canvas id="leagueDonut" height="230"></canvas>
    </div>
  </div>
</div>

<!-- ══ SCOUT ══ -->
<div id="tab-scout" class="tab-panel">
  <div class="scout-search-wrap">
    <input class="search-box" id="scoutSearch" type="text" placeholder="Search player by name…" autocomplete="off">
    <div class="ac-dropdown" id="scoutAC" style="display:none"></div>
  </div>
  <div id="scout-empty" style="text-align:center;padding:70px 0;color:var(--g3)">
    <div style="font-size:52px;margin-bottom:14px">⚽</div>
    <div style="font-size:17px;font-weight:700;color:var(--g2)">Search for a player to see their full profile</div>
    <div style="font-size:13px;margin-top:6px">Pizza plot · percentile bars · Jamestown scouting summary</div>
  </div>
  <div id="scout-content" style="display:none">
    <div class="scout-header-card" id="scoutHdr"></div>
    <div class="scout-layout">
      <div>
        <div class="card">
          <div class="card-title" id="pizza-title">Position profile</div>
          <div class="pizza-wrap"><svg id="pizzaSvg" viewBox="0 0 500 500"></svg></div>
          <div class="pizza-legend" id="pizzaLegend"></div>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:16px">
        <div class="card">
          <div class="card-title">Metrics vs position peers</div>
          <div id="metricsPanel"></div>
        </div>
        <div class="card">
          <div class="card-title">Jamestown scout report</div>
          <div id="scoutReport" style="font-size:13px;line-height:1.75;color:var(--g1)"></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ══ COMPARE ══ -->
<div id="tab-compare" class="tab-panel">
  <div class="scout-search-row" style="margin-bottom:20px">
    <div style="position:relative">
      <input class="search-box" id="cmpSearchA" type="text" placeholder="Player A — search name…" autocomplete="off">
      <div class="ac-dropdown" id="cmpACA" style="display:none"></div>
    </div>
    <div style="position:relative">
      <input class="search-box" id="cmpSearchB" type="text" placeholder="Player B — search name…" autocomplete="off">
      <div class="ac-dropdown" id="cmpACB" style="display:none"></div>
    </div>
  </div>
  <div id="cmp-empty" style="text-align:center;padding:60px;color:var(--g3)">
    <div style="font-size:48px;margin-bottom:12px">⚖️</div>
    <div style="font-size:16px;font-weight:600;color:var(--g2)">Search two players to compare them side by side</div>
  </div>
  <div id="cmp-content" style="display:none">
    <div class="compare-mode">
      <div class="card compare-pizza-card">
        <div class="card-title" id="cmp-title-a">Player A</div>
        <div class="pizza-wrap"><svg id="pizzaA" viewBox="0 0 500 500"></svg></div>
        <div class="pizza-legend" id="cmp-leg-a"></div>
      </div>
      <div class="card compare-pizza-card">
        <div class="card-title" id="cmp-title-b">Player B</div>
        <div class="pizza-wrap"><svg id="pizzaB" viewBox="0 0 500 500"></svg></div>
        <div class="pizza-legend" id="cmp-leg-b"></div>
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="card-title">Head-to-head metrics</div>
      <div id="h2h-table"></div>
    </div>
  </div>
</div>

<!-- ══ POSITIONS ══ -->
<div id="tab-positions" class="tab-panel">
  <div class="pos-selector">
    <span style="font-size:12px;font-weight:600;color:var(--g2)">Position:</span>
    <button class="pos-btn active" data-pos="W">W</button>
    <button class="pos-btn" data-pos="FW">FW</button>
    <button class="pos-btn" data-pos="CM">CM</button>
    <button class="pos-btn" data-pos="DM">DM</button>
    <button class="pos-btn" data-pos="FB">FB</button>
    <button class="pos-btn" data-pos="CB">CB</button>
    <button class="pos-btn" data-pos="GK">GK</button>
  </div>
  <div class="g2" style="margin-bottom:16px">
    <div class="card">
      <div class="card-title" id="pos-bar-title">Top 20 by Bloom Index</div>
      <canvas id="posTopBar" height="360"></canvas>
    </div>
    <div class="card">
      <div class="card-title" id="pos-scatter-title">SQS vs Market Value</div>
      <canvas id="posScatter" height="360"></canvas>
    </div>
  </div>
  <div class="g2">
    <div class="card">
      <div class="card-title" id="pos-age-title">Age distribution</div>
      <canvas id="posAgeBar" height="200"></canvas>
    </div>
    <div class="card">
      <div class="card-title" id="pos-tier-title">Value tier breakdown</div>
      <canvas id="posTierDonut" height="200"></canvas>
    </div>
  </div>
</div>

<!-- ══ TABLE ══ -->
<div id="tab-table" class="tab-panel">
  <div class="tbl-filters">
    <span style="font-size:12px;font-weight:600;color:var(--g2)">Position:</span>
    <button class="tbl-pos pos-btn active" data-pos="ALL">All</button>
    <button class="tbl-pos pos-btn" data-pos="GK">GK</button>
    <button class="tbl-pos pos-btn" data-pos="CB">CB</button>
    <button class="tbl-pos pos-btn" data-pos="FB">FB</button>
    <button class="tbl-pos pos-btn" data-pos="DM">DM</button>
    <button class="tbl-pos pos-btn" data-pos="CM">CM</button>
    <button class="tbl-pos pos-btn" data-pos="W">W</button>
    <button class="tbl-pos pos-btn" data-pos="FW">FW</button>
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
    <span style="font-size:12px;color:var(--g2);margin-left:4px" id="tbl-count"></span>
  </div>
  <div class="card">
    <table id="mainTable" style="width:100%">
      <thead><tr>
        <th>#</th><th>Player</th><th>Pos</th><th>Team</th><th>League</th>
        <th>Age</th><th>Contract</th><th>Mkt Val</th><th>SQS</th><th>Bloom</th>
        <th>Tier</th><th>Status</th><th>vs HK</th><th>Mins</th>
        <th>G/90</th><th>xG/90</th><th>A/90</th><th>PP/90</th><th>DD%</th><th>Int/90</th><th>★</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>
</div>

<div id="tt"></div>

<!-- Shortlist panel -->
<div id="shortlist-panel">
  <div class="sl-header">
    <h3>⭐ Shortlist</h3>
    <button class="sl-close" onclick="toggleShortlist()">✕</button>
  </div>
  <div id="sl-body"></div>
</div>
<div id="overlay" onclick="toggleShortlist()"></div>

<footer class="footer">
  <strong>Methodology:</strong> Statistical Quality Score (SQS) = position-weighted per-90 Wyscout metrics, league-difficulty adjusted (CZ II ×0.82 · Slovakia ×0.78 · Slovakia II ×0.68).
  Bloom Index = SQS percentile − Market Value percentile. Positive = underpriced player. XGBoost out-of-fold predictions for model value.
  Percentiles computed within position group. ✦ = contract expiring June 2026.
  &nbsp;&middot;&nbsp; Waltzing Analytics &middot; FC Hradec Králové 2025-26 &middot; Jamestown Analytics methodology
</footer>

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>

<script>
// ── Data ──────────────────────────────────────────────────────────────────
const DATA       = __DATA_JSON__;
const TIER_CNT   = __TIER_JSON__;
const POS_CNT    = __POS_JSON__;
const PIZZA_META = __PIZZA_JSON__;

const TC = {ELITE:"#1E8449",HIGH:"#27AE60",VALUE:"#1A56DB",FAIR:"#888",OVER:"#C0392B"};
const TL = {ELITE:"Elite Value",HIGH:"High Value",VALUE:"Value",FAIR:"Fair Price",OVER:"Overvalued"};
const CC = {att:"#1E8449",def:"#1A56DB",pass:"#D4700A",gk:"#7C3AED"};
const CL = {att:"Attacking",def:"Defending",pass:"Progression",gk:"Goalkeeping"};
const POS = ["GK","CB","FB","DM","CM","W","FW"];
const LC  = {"CZ II":"#1A56DB","Slovakia":"#1E8449","Slovakia II":"#D4700A"};

// ── Shortlist (localStorage) ───────────────────────────────────────────────
let shortlist = JSON.parse(localStorage.getItem("hk_shortlist")||"[]");
function saveShortlist(){ localStorage.setItem("hk_shortlist",JSON.stringify(shortlist)); updateShortlistUI(); }
function inShortlist(name){ return shortlist.includes(name); }
function toggleStar(name){
  if(inShortlist(name)) shortlist=shortlist.filter(n=>n!==name);
  else shortlist.push(name);
  saveShortlist();
  document.querySelectorAll(`.pick-star,.tbl-star`).forEach(el=>{
    if(el.dataset.name===name) el.textContent=inShortlist(name)?"★":"☆";
    if(el.classList.contains("pick-star")) el.classList.toggle("saved",inShortlist(name));
  });
}
function updateShortlistUI(){
  const cnt=shortlist.length;
  const el=document.getElementById("shortlist-count");
  el.textContent=cnt; el.style.display=cnt>0?"flex":"none";
  const body=document.getElementById("sl-body");
  if(!cnt){ body.innerHTML='<div class="sl-empty">No players saved yet.<br>Click ★ on any player card or table row.</div>'; return; }
  body.innerHTML=shortlist.map(name=>{
    const d=DATA.find(p=>p.name===name);
    if(!d) return "";
    const initials=name.split(" ").slice(0,2).map(w=>w[0]).join("").toUpperCase();
    return `<div class="sl-player">
      <div class="sl-avatar" style="background:${TC[d.tier]||"#888"}">${initials}</div>
      <div class="sl-info"><div class="sl-name">${d.name}</div>
        <div class="sl-meta">${d.pos} · ${d.team} · BI ${fmt_bi(d.bi)} · ${fmt_mv(d.mv)}</div></div>
      <button class="sl-remove" onclick="toggleStar('${name.replace(/'/g,"\\'")}')">✕</button>
    </div>`;
  }).join("");
}
function toggleShortlist(){
  document.getElementById("shortlist-panel").classList.toggle("open");
  document.getElementById("overlay").style.display=
    document.getElementById("shortlist-panel").classList.contains("open")?"block":"none";
  updateShortlistUI();
}

// ── Helpers ────────────────────────────────────────────────────────────────
const tt=document.getElementById("tt");
function showTT(html,e){ tt.innerHTML=html; tt.style.display="block";
  tt.style.left=(e.clientX+14)+"px"; tt.style.top=(e.clientY-14)+"px"; }
document.addEventListener("mousemove",e=>{
  if(tt.style.display==="block"){tt.style.left=(e.clientX+14)+"px";tt.style.top=(e.clientY-14)+"px";}});
function fmt_mv(v){ return v>0?"€"+v.toLocaleString():"—" }
function fmt_bi(v){ return (v>0?"+":"")+v }
function sqs_col(v){ return v>=70?"#1E8449":v>=40?"#D4700A":"#C0392B" }
function bi_col(v){ return v>=20?"#1E8449":v>=10?"#1A56DB":v>=0?"#D4700A":"#C0392B" }
function initials(name){ return name.split(" ").slice(0,2).map(w=>w[0]||"").join("").toUpperCase(); }
function tier_chip(t){
  const l={ELITE:"Elite",HIGH:"High",VALUE:"Value",FAIR:"Fair",OVER:"Over"};
  const c={ELITE:"te",HIGH:"th",VALUE:"tv",FAIR:"tf",OVER:"to"};
  return `<span class="chip ${c[t]||"tf"}">${l[t]||t}</span>`;
}
function upg_chip(u){
  if(u==="CLEAR UPGRADE") return `<span class="chip uc">▲ Clear</span>`;
  if(u.startsWith("ROT"))  return `<span class="chip ur">Rot.</span>`;
  return `<span class="chip ud">Depth</span>`;
}
function spark(pct, color){ return `<span class="spark" style="width:${pct}px;background:${color}"></span>`; }

// ── Tab nav ────────────────────────────────────────────────────────────────
document.querySelectorAll(".nav-btn").forEach(btn=>{
  btn.addEventListener("click",()=>{
    document.querySelectorAll(".nav-btn").forEach(b=>b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p=>p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-"+btn.dataset.tab).classList.add("active");
    if(btn.dataset.tab==="positions") renderPosTab(activePosTab);
  });
});

// ── KPIs ──────────────────────────────────────────────────────────────────
const upgrades=DATA.filter(d=>d.upgrade==="CLEAR UPGRADE");
document.getElementById("k-elite").textContent  = DATA.filter(d=>d.tier==="ELITE").length;
document.getElementById("k-upgr").textContent   = upgrades.length;
document.getElementById("k-u23").textContent    = DATA.filter(d=>d.age<=23).length;
document.getElementById("k-exp").textContent    = DATA.filter(d=>d.cflag==="2026").length;
document.getElementById("k-avgbi").textContent  = upgrades.length
  ? (upgrades.reduce((s,d)=>s+d.bi,0)/upgrades.length).toFixed(1):"—";
document.getElementById("k-avgmv").textContent  = upgrades.length
  ? "€"+Math.round(upgrades.reduce((s,d)=>s+d.mv,0)/upgrades.length/1000)+"k":"—";

// ── Top Picks ──────────────────────────────────────────────────────────────
const topPicks = DATA.filter(d=>d.tier==="ELITE"&&d.upgrade==="CLEAR UPGRADE")
                     .sort((a,b)=>b.bi-a.bi).slice(0,5);
document.getElementById("top-picks").innerHTML = topPicks.map(d=>`
  <div class="pick-card tier-${d.tier}" onclick="goScout('${d.name.replace(/'/g,"\\'")}')">
    <span class="pick-badge">${d.pos}</span>
    <span class="pick-star${inShortlist(d.name)?" saved":""}" data-name="${d.name}"
      onclick="event.stopPropagation();toggleStar('${d.name.replace(/'/g,"\\'")}')">
      ${inShortlist(d.name)?"★":"☆"}
    </span>
    <div class="pick-avatar" style="background:rgba(255,255,255,.2)">${initials(d.name)}</div>
    <div class="pick-name" title="${d.name}">${d.name}</div>
    <div class="pick-meta">${d.team} · ${d.league}</div>
    <div class="pick-stats">
      <div class="pick-stat"><div class="ps-val" style="color:${bi_col(d.bi)}">${fmt_bi(d.bi)}</div><div class="ps-lbl">Bloom</div></div>
      <div class="pick-stat"><div class="ps-val" style="color:${sqs_col(d.sqs)}">${d.sqs}</div><div class="ps-lbl">SQS</div></div>
      <div class="pick-stat"><div class="ps-val">${d.age}</div><div class="ps-lbl">Age</div></div>
    </div>
  </div>`).join("");
updateShortlistUI();

function goScout(name){
  document.querySelector('[data-tab="scout"]').click();
  document.getElementById("scoutSearch").value=name;
  const d=DATA.find(p=>p.name===name);
  if(d) renderScout(d);
}

// ══════════════════════════════════════════════════════════════════════════
// SCATTER with quadrant
// ══════════════════════════════════════════════════════════════════════════
const medMV = d3.median(DATA.map(d=>d.mv/1000));
const medSQS = d3.median(DATA.map(d=>d.sqs));

const scatterDS = POS.map((pos,pi)=>{
  const hue=[210,180,150,100,240,30,0][pi];
  return {
    label:pos,
    data:DATA.filter(d=>d.pos===pos).map(d=>({
      x:d.mv/1000, y:d.sqs, r:Math.max(3,Math.min(12,d.mins/280)), _d:d
    })),
    backgroundColor:`hsla(${hue},65%,45%,0.55)`,
    borderColor:`hsla(${hue},65%,35%,0.8)`,
    borderWidth:1
  };
});

const scatterPlugin = {
  id:"quadrant",
  beforeDraw(chart){
    const {ctx,chartArea:{left,right,top,bottom},scales:{x,y}}=chart;
    const mx=x.getPixelForValue(medMV), my=y.getPixelForValue(medSQS);
    ctx.save();
    ctx.fillStyle="rgba(30,132,73,0.04)";
    ctx.fillRect(left, top, mx-left, my-top);
    ctx.strokeStyle="rgba(150,150,150,0.25)";
    ctx.setLineDash([4,4]);
    ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(mx,top);ctx.lineTo(mx,bottom);ctx.stroke();
    ctx.beginPath();ctx.moveTo(left,my);ctx.lineTo(right,my);ctx.stroke();
    ctx.restore();
  }
};

const scatterChart = new Chart(document.getElementById("scatterChart").getContext("2d"),{
  type:"bubble",
  data:{datasets:scatterDS},
  plugins:[scatterPlugin],
  options:{
    responsive:true,
    plugins:{
      legend:{position:"top",labels:{boxWidth:9,font:{size:10}}},
      tooltip:{enabled:false}
    },
    scales:{
      x:{title:{display:true,text:"Market Value (€k)",font:{size:10}},grid:{color:"#F9FAFB"},min:0},
      y:{title:{display:true,text:"SQS Rank (0–100)",font:{size:10}},min:0,max:100,grid:{color:"#F9FAFB"}}
    },
    onHover:(e,els)=>{
      if(!els.length){tt.style.display="none";return;}
      const el=els[0],d=scatterChart.data.datasets[el.datasetIndex].data[el.index]._d;
      showTT(`<h4>${d.name}</h4>
        <div class="tt-r"><span class="tt-l">Team/League</span><span class="tt-v">${d.team} · ${d.league}</span></div>
        <div class="tt-r"><span class="tt-l">SQS / BI</span><span class="tt-v">${d.sqs} / ${fmt_bi(d.bi)}</span></div>
        <div class="tt-r"><span class="tt-l">Market val</span><span class="tt-v">${fmt_mv(d.mv)}</span></div>
        <div class="tt-r"><span class="tt-l">Age</span><span class="tt-v">${d.age}${d.cflag==="2026"?" ✦":""}</span></div>
        <div class="tt-r"><span class="tt-l">Status</span><span class="tt-v">${d.upgrade}</span></div>`,e.native);
    }
  }
});

// ══════════════════════════════════════════════════════════════════════════
// BEESWARM (D3 force)
// ══════════════════════════════════════════════════════════════════════════
function drawBeeswarm(){
  const svgEl=document.getElementById("beeswarmSvg");
  const W=svgEl.getBoundingClientRect().width||520, H=290;
  const svg=d3.select(svgEl).attr("viewBox",`0 0 ${W} ${H}`);
  svg.selectAll("*").remove();
  const M={l:46,r:10,t:8,b:28};
  const iW=W-M.l-M.r, iH=H-M.t-M.b;
  const g=svg.append("g").attr("transform",`translate(${M.l},${M.t})`);
  const laneH=iH/POS.length;
  const xSc=d3.scaleLinear().domain([-35,85]).range([0,iW]);
  const laneY=pos=>POS.indexOf(pos)*laneH+laneH/2;

  // Grid lines + axis
  g.append("g").attr("transform",`translate(0,${iH})`)
   .call(d3.axisBottom(xSc).ticks(7).tickFormat(d=>(d>0?"+":"")+d).tickSize(-iH))
   .selectAll("line").attr("stroke","#F1F5F9");
  g.select(".domain").remove();
  g.append("text").attr("x",iW/2).attr("y",iH+24).attr("text-anchor","middle")
   .attr("font-size",10).attr("fill","#9CA3AF").text("Bloom Index");

  // Bands
  POS.forEach((pos,i)=>{
    if(i%2===0) g.append("rect").attr("x",0).attr("y",i*laneH).attr("width",iW).attr("height",laneH)
      .attr("fill","#F9FAFB").attr("rx",0);
  });

  // Zero line
  g.append("line").attr("x1",xSc(0)).attr("x2",xSc(0)).attr("y1",0).attr("y2",iH)
   .attr("stroke","#CBD5E0").attr("stroke-dasharray","3,3").attr("stroke-width",1);

  // Pos labels
  POS.forEach(pos=>{
    g.append("text").attr("x",-5).attr("y",laneY(pos)).attr("text-anchor","end")
     .attr("dy","0.35em").attr("font-size",10).attr("font-weight","700").attr("fill","#374151").text(pos);
  });

  // Nodes
  const nodes=DATA.map(d=>({...d,
    fx_target:xSc(Math.max(-35,Math.min(85,d.bi))),
    fy_target:laneY(d.pos)
  })).map(d=>({...d,x:d.fx_target,y:d.fy_target}));

  const sim=d3.forceSimulation(nodes)
    .force("x",d3.forceX(n=>n.fx_target).strength(0.9))
    .force("y",d3.forceY(n=>n.fy_target).strength(3.5))
    .force("collide",d3.forceCollide(3.5))
    .stop();
  for(let i=0;i<200;i++) sim.tick();

  // Top 3 per position name labels
  const top3 = {};
  POS.forEach(pos=>{
    top3[pos]=DATA.filter(d=>d.pos===pos).sort((a,b)=>b.bi-a.bi).slice(0,3).map(d=>d.name);
  });

  const circles=g.selectAll("circle.bee").data(nodes).join("circle")
    .attr("class","bee")
    .attr("cx",n=>Math.max(3,Math.min(iW-3,n.x)))
    .attr("cy",n=>Math.max(4,Math.min(iH-4,n.y)))
    .attr("r",n=>n.tier==="ELITE"?4.5:3.5)
    .attr("fill",n=>TC[n.tier]||"#888")
    .attr("opacity",n=>n.upgrade==="CLEAR UPGRADE"?0.9:0.55)
    .attr("stroke",n=>n.upgrade==="CLEAR UPGRADE"?"#fff":"none")
    .attr("stroke-width",n=>n.upgrade==="CLEAR UPGRADE"?1.2:0)
    .on("mouseover",function(e,n){
      d3.select(this).attr("r",6.5).attr("opacity",1);
      showTT(`<h4>${n.name}</h4>
        <div class="tt-r"><span class="tt-l">Pos</span><span class="tt-v">${n.pos}</span></div>
        <div class="tt-r"><span class="tt-l">BI</span><span class="tt-v">${fmt_bi(n.bi)}</span></div>
        <div class="tt-r"><span class="tt-l">SQS</span><span class="tt-v">${n.sqs}</span></div>
        <div class="tt-r"><span class="tt-l">Tier</span><span class="tt-v">${TL[n.tier]}</span></div>
        <div class="tt-r"><span class="tt-l">Status</span><span class="tt-v">${n.upgrade}</span></div>`,e);
    })
    .on("mouseout",function(n){ d3.select(this).attr("r",n.tier==="ELITE"?4.5:3.5).attr("opacity",n.upgrade==="CLEAR UPGRADE"?0.9:0.55); tt.style.display="none"; })
    .on("click",function(e,n){ goScout(n.name); });

  // Labels for top 3 Elite per position
  nodes.filter(n=>n.tier==="ELITE").forEach(n=>{
    if(top3[n.pos]&&top3[n.pos].includes(n.name)){
      const nx=Math.max(3,Math.min(iW-3,n.x)), ny=Math.max(4,Math.min(iH-4,n.y));
      g.append("text").attr("x",nx).attr("y",ny-7)
       .attr("text-anchor","middle").attr("font-size",7).attr("font-weight","700").attr("fill","#374151")
       .text(n.name.split(" ").slice(-1)[0].substring(0,10));
    }
  });

  // Legend (inline)
  const legG=svg.append("g").attr("transform",`translate(${M.l},${H-6})`);
  let lx=0;
  [["ELITE",TC.ELITE],["HIGH",TC.HIGH],["VALUE",TC.VALUE],["FAIR",TC.FAIR],["OVER",TC.OVER]].forEach(([t,c])=>{
    legG.append("circle").attr("cx",lx+5).attr("cy",0).attr("r",4).attr("fill",c);
    legG.append("text").attr("x",lx+12).attr("y",1).attr("font-size",9).attr("fill","#6B7280").attr("dy","0.35em").text(TL[t]);
    lx+=TL[t].length*5.5+18;
  });
}
drawBeeswarm();
window.addEventListener("resize",()=>{d3.select("#beeswarmSvg").selectAll("*").remove();drawBeeswarm();});

// ══════════════════════════════════════════════════════════════════════════
// WAFFLE
// ══════════════════════════════════════════════════════════════════════════
(function(){
  const total=DATA.length, cells=100;
  const tiers=["ELITE","HIGH","VALUE","FAIR","OVER"];
  const sq=[];
  tiers.forEach(t=>{
    const n=Math.round((TIER_CNT[t]/total)*cells);
    for(let i=0;i<n;i++) sq.push(t);
  });
  while(sq.length<cells) sq.push("FAIR");
  const grid=document.getElementById("waffleGrid");
  sq.forEach((t,i)=>{
    const d=document.createElement("div");
    d.className="wsq"; d.style.background=TC[t]; d.style.opacity=".85";
    d.title=`${TL[t]} (${TIER_CNT[t]} players)`;
    grid.appendChild(d);
  });
  const leg=document.getElementById("waffleLegend");
  tiers.forEach(t=>{
    const pct=((TIER_CNT[t]/total)*100).toFixed(1);
    leg.innerHTML+=`<div class="wleg-item"><div class="wleg-dot" style="background:${TC[t]}"></div>
      ${TL[t]} <strong style="color:${TC[t]}">${TIER_CNT[t]}</strong>
      <span style="color:var(--g3)">(${pct}%)</span></div>`;
  });
})();

// ══════════════════════════════════════════════════════════════════════════
// POS BAR + LEAGUE DONUT
// ══════════════════════════════════════════════════════════════════════════
new Chart(document.getElementById("posBar").getContext("2d"),{
  type:"bar",
  data:{labels:POS,datasets:[{
    data:POS.map(p=>POS_CNT[p]||0),
    backgroundColor:POS.map((_,i)=>`hsla(${[210,180,150,100,240,30,0][i]},60%,50%,0.75)`),
    borderRadius:6,borderSkipped:false
  }]},
  options:{indexAxis:"y",responsive:true,plugins:{legend:{display:false}},
    scales:{x:{grid:{color:"#F9FAFB"}},y:{grid:{display:false},ticks:{font:{size:11,weight:"700"}}}}}
});
const lCnts={};
DATA.forEach(d=>{lCnts[d.league]=(lCnts[d.league]||0)+1});
new Chart(document.getElementById("leagueDonut").getContext("2d"),{
  type:"doughnut",
  data:{labels:Object.keys(lCnts),datasets:[{
    data:Object.values(lCnts),
    backgroundColor:Object.keys(lCnts).map(l=>LC[l]||"#888"),
    borderWidth:2,borderColor:"#fff"
  }]},
  options:{cutout:"60%",responsive:true,plugins:{legend:{position:"bottom",labels:{boxWidth:10,font:{size:10}}}}}
});

// ══════════════════════════════════════════════════════════════════════════
// PIZZA PLOT — mplsoccer style
// ══════════════════════════════════════════════════════════════════════════
function arcPath(cx,cy,r1,r2,a1,a2){
  const cos=Math.cos,sin=Math.sin;
  const x1=cx+r1*cos(a1),y1=cy+r1*sin(a1);
  const x2=cx+r2*cos(a1),y2=cy+r2*sin(a1);
  const x3=cx+r2*cos(a2),y3=cy+r2*sin(a2);
  const x4=cx+r1*cos(a2),y4=cy+r1*sin(a2);
  const big=(a2-a1)>Math.PI?1:0;
  return `M${x1},${y1}L${x2},${y2}A${r2},${r2},0,${big},1,${x3},${y3}L${x4},${y4}A${r1},${r1},0,${big},0,${x1},${y1}Z`;
}

function drawPizzaSVG(svgId, player, legId, titleId){
  const metrics = PIZZA_META[player.pos]||[];
  if(!metrics.length) return;
  const svg = d3.select("#"+svgId);
  svg.selectAll("*").remove();

  const VW=500,VH=500,cx=250,cy=250;
  const innerR=42, outerR=175, labelRing=195;
  const n=metrics.length, step=(2*Math.PI)/n, start=-Math.PI/2;

  svg.append("rect").attr("width",VW).attr("height",VH).attr("fill","#FAFBFC").attr("rx",12);

  // Subtle ring grid at 25/50/75
  [25,50,75].forEach(pct=>{
    const r=innerR+(outerR-innerR)*(pct/100);
    svg.append("circle").attr("cx",cx).attr("cy",cy).attr("r",r)
       .attr("fill","none").attr("stroke","#D1D5DB").attr("stroke-width",.7).attr("stroke-dasharray","2,4");
  });
  svg.append("circle").attr("cx",cx).attr("cy",cy).attr("r",outerR)
     .attr("fill","none").attr("stroke","#E5E7EB").attr("stroke-width",1);

  // Slice backgrounds (alternating)
  metrics.forEach((_,i)=>{
    const a1=start+i*step, a2=start+(i+1)*step;
    svg.append("path").attr("d",arcPath(cx,cy,innerR,outerR,a1,a2))
       .attr("fill",i%2===0?"#F0F4FA":"#E8EDF5").attr("stroke","#fff").attr("stroke-width",2);
  });

  // Filled slices with gradient simulation (two-tone)
  metrics.forEach((m,i)=>{
    const a1=start+i*step, a2=start+(i+1)*step;
    const pct=parseFloat(player[m.key+"_pct"])||0;
    const fillR=innerR+(outerR-innerR)*(pct/100);
    const col=CC[m.cat]||"#1A56DB";
    if(fillR>innerR+2){
      // Outer darker layer
      const outerFill=innerR+(fillR-innerR)*0.5;
      svg.append("path").attr("d",arcPath(cx,cy,outerFill,fillR,a1,a2))
         .attr("fill",col).attr("opacity",0.9).attr("stroke","#fff").attr("stroke-width",1.5);
      // Inner lighter layer
      svg.append("path").attr("d",arcPath(cx,cy,innerR,outerFill,a1,a2))
         .attr("fill",col).attr("opacity",0.5).attr("stroke","#fff").attr("stroke-width",1.5);
    }
    // Percentile label
    const midA=(a1+a2)/2;
    const labelR2=innerR+(fillR-innerR)*0.6;
    if(pct>15 && fillR-innerR>18){
      svg.append("text").attr("x",cx+labelR2*Math.cos(midA)).attr("y",cy+labelR2*Math.sin(midA))
         .attr("text-anchor","middle").attr("dy","0.35em")
         .attr("font-size",8).attr("font-weight","800").attr("fill","#fff")
         .text(Math.round(pct));
    }
  });

  // Outer label ticks + labels
  metrics.forEach((m,i)=>{
    const a1=start+i*step, a2=start+(i+1)*step;
    const midA=(a1+a2)/2;
    const pct=parseFloat(player[m.key+"_pct"])||0;
    const col=CC[m.cat]||"#1A56DB";
    const lx=cx+labelRing*Math.cos(midA), ly=cy+labelRing*Math.sin(midA);
    const anchor=Math.abs(Math.cos(midA))<0.15?"middle":Math.cos(midA)<0?"end":"start";

    // Tick
    svg.append("line")
       .attr("x1",cx+(outerR+1)*Math.cos(midA)).attr("y1",cy+(outerR+1)*Math.sin(midA))
       .attr("x2",cx+(outerR+10)*Math.cos(midA)).attr("y2",cy+(outerR+10)*Math.sin(midA))
       .attr("stroke",col).attr("stroke-width",1.5).attr("opacity",0.6);

    svg.append("text").attr("x",lx).attr("y",ly-5).attr("text-anchor",anchor)
       .attr("font-size",9).attr("font-weight","600").attr("fill","#374151").text(m.label);
    svg.append("text").attr("x",lx).attr("y",ly+7).attr("text-anchor",anchor)
       .attr("font-size",8.5).attr("font-weight","800").attr("fill",col)
       .text(Math.round(pct)+"th");
  });

  // Centre
  svg.append("circle").attr("cx",cx).attr("cy",cy).attr("r",innerR)
     .attr("fill","#fff").attr("stroke","#E5E7EB").attr("stroke-width",2);
  const lastName=player.name.split(" ").slice(-1)[0].substring(0,9);
  svg.append("text").attr("x",cx).attr("y",cy-13).attr("text-anchor","middle")
     .attr("font-size",10).attr("font-weight","900").attr("fill","#111").text(lastName);
  svg.append("text").attr("x",cx).attr("y",cy+1).attr("text-anchor","middle")
     .attr("font-size",9).attr("fill","#6B7280").text(player.pos);
  svg.append("text").attr("x",cx).attr("y",cy+15).attr("text-anchor","middle")
     .attr("font-size",9).attr("font-weight","800").attr("fill","#1A56DB")
     .text(Math.round(player.sqs)+" SQS");

  if(titleId) document.getElementById(titleId).textContent=`${player.name} — ${player.pos} profile vs position peers`;
  if(legId){
    const cats=[...new Set(metrics.map(m=>m.cat))];
    document.getElementById(legId).innerHTML=cats.map(c=>
      `<div class="pl-item"><div class="pl-dot" style="background:${CC[c]}"></div>${CL[c]}</div>`
    ).join("");
  }
}

// ══════════════════════════════════════════════════════════════════════════
// SCOUT TAB
// ══════════════════════════════════════════════════════════════════════════
function setupAutocomplete(inputId, acId, onSelect){
  const inp=document.getElementById(inputId), ac=document.getElementById(acId);
  inp.addEventListener("input",function(){
    const q=this.value.toLowerCase().trim();
    ac.innerHTML=""; if(q.length<2){ac.style.display="none";return;}
    const hits=DATA.filter(d=>d.name.toLowerCase().includes(q)).slice(0,12);
    if(!hits.length){ac.style.display="none";return;}
    hits.forEach(d=>{
      const item=document.createElement("div"); item.className="ac-item";
      item.innerHTML=`<div class="ac-name">${d.name}</div>
        <div class="ac-meta">${d.pos} · ${d.team} · ${d.league} · BI ${fmt_bi(d.bi)} · ${fmt_mv(d.mv)}</div>`;
      item.addEventListener("click",()=>{inp.value=d.name;ac.style.display="none";onSelect(d);});
      ac.appendChild(item);
    });
    ac.style.display="block";
  });
  document.addEventListener("click",e=>{if(!e.target.closest("#"+inputId)&&!e.target.closest("#"+acId)) ac.style.display="none";});
}

function renderScout(d){
  document.getElementById("scout-empty").style.display="none";
  document.getElementById("scout-content").style.display="block";

  // Header card
  const col=d.tier==="ELITE"||d.tier==="HIGH"?"tier-ELITE":(d.tier==="OVER"?"tier-OVER":"");
  const biC=bi_col(d.bi), sqsC=sqs_col(d.sqs);
  const vratio=d.model_v>0?(d.model_v/Math.max(d.mv,1)).toFixed(1)+"×":"n/a";
  document.getElementById("scoutHdr").className="scout-header-card "+col;
  document.getElementById("scoutHdr").innerHTML=`
    <div class="sh-top">
      <div class="sh-avatar">${initials(d.name)}</div>
      <div>
        <div class="sh-name">${d.name}${d.cflag==="2026"?'<span style="font-size:13px;margin-left:8px;color:#FCD34D">✦ 2026</span>':""}</div>
        <div class="sh-meta">${d.pos} · ${d.position} · ${d.team} · ${d.league} · Age ${d.age}</div>
      </div>
      <button onclick="toggleStar('${d.name.replace(/'/g,"\\'")}');this.textContent=inShortlist('${d.name.replace(/'/g,"\\'")}')&&'★ Saved'||'☆ Save'"
        style="margin-left:auto;padding:7px 16px;border-radius:20px;border:1.5px solid rgba(255,255,255,.4);
               background:rgba(255,255,255,.15);color:#fff;font-size:12px;font-weight:700;cursor:pointer">
        ${inShortlist(d.name)?"★ Saved":"☆ Save"}
      </button>
    </div>
    <div class="sh-nums">
      <div class="sh-num"><div class="n">${d.sqs}</div><div class="l">SQS Rank</div></div>
      <div class="sh-num"><div class="n" style="color:${biC}">${fmt_bi(d.bi)}</div><div class="l">Bloom Index</div></div>
      <div class="sh-num"><div class="n">${fmt_mv(d.mv)}</div><div class="l">Market Value</div></div>
      <div class="sh-num"><div class="n">${fmt_mv(d.model_v)}</div><div class="l">Model Value</div></div>
      <div class="sh-num"><div class="n">${vratio}</div><div class="l">Value Ratio</div></div>
      <div class="sh-num"><div class="n" style="color:${d.gap>0?"#86EFAC":"#FCA5A5"}">${fmt_bi(d.gap)}</div><div class="l">vs Hradec</div></div>
      <div class="sh-num"><div class="n">${d.mins.toLocaleString()}</div><div class="l">Minutes</div></div>
    </div>`;

  drawPizzaSVG("pizzaSvg",d,"pizzaLegend","pizza-title");

  // Metrics panel
  const metrics=PIZZA_META[d.pos]||[];
  document.getElementById("metricsPanel").innerHTML=metrics.map(m=>{
    const pct=parseFloat(d[m.key+"_pct"])||0;
    const raw=d[m.key]!==undefined?d[m.key]:"—";
    const col=pct>=70?"#1E8449":pct>=40?"#D4700A":"#C0392B";
    return `<div class="metric-row">
      <span class="m-lbl">${m.label}</span>
      <div class="m-bar-wrap"><div class="m-bar-fill" style="width:${pct}%;background:${col}"></div></div>
      <span class="m-pct" style="color:${col}">${Math.round(pct)}<sup style="font-size:8px">th</sup></span>
      <span class="m-raw">${raw}</span>
    </div>`;
  }).join("");

  // Scout report
  const uLabel=d.upgrade==="CLEAR UPGRADE"?"a <strong style='color:#1E8449'>clear upgrade</strong>":
               d.upgrade.startsWith("ROT")?"a <strong>rotational option</strong>":"a <strong>depth option</strong>";
  const contractNote=d.cflag==="2026"
    ?` Contract expires <strong>June 2026</strong> — potential cut-price or free acquisition.</p><p>`:"";
  document.getElementById("scoutReport").innerHTML=`
    <p><strong>${d.name}</strong> plays as ${d.position} at <strong>${d.team}</strong> (${d.league}).
    Rated <strong>${TL[d.tier]}</strong> with a Bloom Index of
    <strong style="color:${biC}">${fmt_bi(d.bi)}</strong> — statistical output is
    <strong>${d.bi>0?"statistically underpriced relative to":"overpriced relative to"}</strong> market valuation.</p>
    <p style="margin-top:8px">Represents ${uLabel} on current Hradec <strong>${d.pos}</strong> starters
    (<strong>${d.starters}</strong>), with an SQS gap of <strong style="color:${d.gap>0?"#1E8449":"#C0392B"}">${fmt_bi(d.gap)}</strong> ranks.
    ${contractNote}
    Market value <strong>${fmt_mv(d.mv)}</strong> vs model estimate <strong>${fmt_mv(d.model_v)}</strong>
    (${vratio} — ${+vratio.replace("×","")>1.5?"significant undervaluation":"close to fair value"}).</p>`;
}

setupAutocomplete("scoutSearch","scoutAC",renderScout);

// ══════════════════════════════════════════════════════════════════════════
// COMPARE TAB
// ══════════════════════════════════════════════════════════════════════════
let cmpA=null, cmpB=null;
function renderCompare(){
  if(!cmpA||!cmpB) return;
  document.getElementById("cmp-empty").style.display="none";
  document.getElementById("cmp-content").style.display="block";
  drawPizzaSVG("pizzaA",cmpA,"cmp-leg-a","cmp-title-a");
  drawPizzaSVG("pizzaB",cmpB,"cmp-leg-b","cmp-title-b");
  // H2H
  const metricsA=PIZZA_META[cmpA.pos]||[], metricsB=PIZZA_META[cmpB.pos]||[];
  const allMetrics=[...new Set([...metricsA,...metricsB].map(m=>m.key))];
  const metaMap={};
  [...metricsA,...metricsB].forEach(m=>{metaMap[m.key]=m;});
  const h2h=allMetrics.map(key=>{
    const m=metaMap[key];
    if(!m) return "";
    const pA=parseFloat(cmpA[key+"_pct"])||0, pB=parseFloat(cmpB[key+"_pct"])||0;
    const rA=cmpA[key]!==undefined?cmpA[key]:"—", rB=cmpB[key]!==undefined?cmpB[key]:"—";
    const wA=pA>=pB?"#D1FAE5":"#FEE2E2", wB=pB>pA?"#D1FAE5":"#FEE2E2";
    return `<tr>
      <td style="background:${wA};font-weight:700;color:${pA>=pB?"#065F46":"#991B1B"};text-align:right;padding:7px 12px">${Math.round(pA)}th <small style="color:#9CA3AF">(${rA})</small></td>
      <td style="text-align:center;font-size:11px;color:var(--g2);padding:7px 8px;border-left:1px solid #F3F4F6;border-right:1px solid #F3F4F6">${m.label}</td>
      <td style="background:${wB};font-weight:700;color:${pB>pA?"#065F46":"#991B1B"};padding:7px 12px">${Math.round(pB)}th <small style="color:#9CA3AF">(${rB})</small></td>
    </tr>`;
  }).join("");
  document.getElementById("h2h-table").innerHTML=`
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <thead><tr>
        <th style="text-align:right;padding:8px 12px;background:#F8FAFC;font-size:11px;font-weight:700;color:var(--g2)">${cmpA.name}</th>
        <th style="text-align:center;padding:8px;background:#F8FAFC;font-size:11px;font-weight:700;color:var(--g2)">Metric</th>
        <th style="padding:8px 12px;background:#F8FAFC;font-size:11px;font-weight:700;color:var(--g2)">${cmpB.name}</th>
      </tr></thead><tbody>${h2h}</tbody>
    </table>`;
}

setupAutocomplete("cmpSearchA","cmpACA",d=>{cmpA=d;renderCompare();});
setupAutocomplete("cmpSearchB","cmpACB",d=>{cmpB=d;renderCompare();});

// ══════════════════════════════════════════════════════════════════════════
// POSITIONS TAB
// ══════════════════════════════════════════════════════════════════════════
let activePosTab="W", posCharts={};
function renderPosTab(pos){
  activePosTab=pos;
  document.querySelectorAll("#tab-positions .pos-btn").forEach(b=>b.classList.toggle("active",b.dataset.pos===pos));
  const pd=DATA.filter(d=>d.pos===pos).sort((a,b)=>b.bi-a.bi);
  ["posTopBar","posScatter","posAgeBar","posTierDonut"].forEach(id=>{if(posCharts[id]){posCharts[id].destroy();delete posCharts[id];}});
  document.getElementById("pos-bar-title").textContent=`${pos} — Top 20 by Bloom Index`;
  document.getElementById("pos-scatter-title").textContent=`${pos} — SQS vs Market Value`;
  document.getElementById("pos-age-title").textContent=`${pos} — Age distribution`;
  document.getElementById("pos-tier-title").textContent=`${pos} — Value tier breakdown`;
  const top20=pd.slice(0,20);
  posCharts.posTopBar=new Chart(document.getElementById("posTopBar").getContext("2d"),{
    type:"bar",
    data:{labels:top20.map(d=>d.name.split(" ").slice(-1)[0].substring(0,12)),
      datasets:[{label:"Bloom Index",data:top20.map(d=>d.bi),
        backgroundColor:top20.map(d=>d.bi>=20?"#1E8449CC":d.bi>=10?"#1A56DBCC":d.bi>=0?"#D4700ACC":"#C0392BCC"),
        borderRadius:5,borderSkipped:false}]},
    options:{indexAxis:"y",responsive:true,
      plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>{
        const d=top20[ctx.dataIndex];
        return [`BI: ${fmt_bi(d.bi)}`,`SQS: ${d.sqs}`,fmt_mv(d.mv),d.upgrade];
      }}}},
      scales:{x:{grid:{color:"#F9FAFB"},title:{display:true,text:"Bloom Index",font:{size:10}}},
              y:{grid:{display:false},ticks:{font:{size:10}}}}}
  });
  const tDS=["ELITE","HIGH","VALUE","FAIR","OVER"].map(t=>({
    label:TL[t],
    data:DATA.filter(d=>d.pos===pos&&d.tier===t).map(d=>({x:d.mv/1000,y:d.sqs,r:Math.max(3,Math.min(10,d.mins/300)),_d:d})),
    backgroundColor:TC[t]+"88",borderColor:TC[t],borderWidth:1
  }));
  posCharts.posScatter=new Chart(document.getElementById("posScatter").getContext("2d"),{
    type:"bubble",data:{datasets:tDS},
    options:{responsive:true,
      plugins:{legend:{position:"top",labels:{boxWidth:9,font:{size:9}}},
               tooltip:{callbacks:{label:ctx=>{const d=ctx.raw._d;return [`${d.name}`,`SQS ${d.sqs}  BI ${fmt_bi(d.bi)}`,fmt_mv(d.mv)];} }}},
      scales:{x:{grid:{color:"#F9FAFB"},title:{display:true,text:"Mkt Val (€k)",font:{size:10}},min:0},
              y:{min:0,max:100,grid:{color:"#F9FAFB"},title:{display:true,text:"SQS",font:{size:10}}}}}
  });
  const ages={};
  DATA.filter(d=>d.pos===pos).forEach(d=>{ages[d.age]=(ages[d.age]||0)+1;});
  const ageKeys=Object.keys(ages).sort((a,b)=>+a-+b);
  posCharts.posAgeBar=new Chart(document.getElementById("posAgeBar").getContext("2d"),{
    type:"bar",
    data:{labels:ageKeys,datasets:[{data:ageKeys.map(k=>ages[k]),
      backgroundColor:ageKeys.map(k=>+k<=23?"#1E8449AA":+k<=27?"#1A56DBAA":"#D4700AAA"),borderRadius:4}]},
    options:{responsive:true,plugins:{legend:{display:false}},scales:{x:{grid:{display:false}},y:{grid:{color:"#F9FAFB"}}}}
  });
  const ptC={};
  DATA.filter(d=>d.pos===pos).forEach(d=>{ptC[d.tier]=(ptC[d.tier]||0)+1;});
  const tKeys=["ELITE","HIGH","VALUE","FAIR","OVER"].filter(t=>ptC[t]>0);
  posCharts.posTierDonut=new Chart(document.getElementById("posTierDonut").getContext("2d"),{
    type:"doughnut",
    data:{labels:tKeys.map(t=>TL[t]),datasets:[{data:tKeys.map(t=>ptC[t]),
      backgroundColor:tKeys.map(t=>TC[t]),borderWidth:2,borderColor:"#fff"}]},
    options:{cutout:"58%",responsive:true,plugins:{legend:{position:"bottom",labels:{boxWidth:9,font:{size:10}}}}}
  });
}
document.querySelectorAll("#tab-positions .pos-btn").forEach(b=>b.addEventListener("click",()=>renderPosTab(b.dataset.pos)));
renderPosTab("W");

// ══════════════════════════════════════════════════════════════════════════
// TABLE
// ══════════════════════════════════════════════════════════════════════════
let tblPos="ALL",tblTier="",tblUpgrade="";
function buildRows(data){
  return data.sort((a,b)=>b.bi-a.bi).map((d,i)=>[
    i+1,
    `<strong>${d.name}</strong><br><small style="color:#9CA3AF">${d.position}</small>`,
    `<strong style="color:var(--blue)">${d.pos}</strong>`,
    d.team, d.league,
    d.age<=23?`<strong style="color:var(--green)">${d.age}</strong>`:
    d.age>=28?`<span style="color:var(--g3)">${d.age}</span>`:d.age,
    d.cflag==="2026"?`${d.contract} <span class="cflag">✦</span>`:d.contract,
    fmt_mv(d.mv),
    `<strong style="color:${sqs_col(d.sqs)}">${d.sqs}</strong>${spark(d.sqs*.7,sqs_col(d.sqs))}`,
    `<strong style="color:${bi_col(d.bi)}">${fmt_bi(d.bi)}</strong>${spark(Math.max(0,d.bi+30)*0.7,bi_col(d.bi))}`,
    tier_chip(d.tier), upg_chip(d.upgrade),
    `<strong style="color:${d.gap>0?"var(--green)":"var(--red)"}">${fmt_bi(d.gap)}</strong>`,
    d.mins.toLocaleString(),
    d.g90,d.xg90,d.a90,d.pp90,d.ddw+"%",d.int90,
    `<span class="tbl-star" data-name="${d.name}" onclick="toggleStar('${d.name.replace(/'/g,"\\'")}');this.textContent=inShortlist('${d.name.replace(/'/g,"\\'")}')&&'★'||'☆'"
     style="cursor:pointer;font-size:14px">${inShortlist(d.name)?"★":"☆"}</span>`
  ]);
}
function applyTblFilters(){
  const data=DATA.filter(d=>{
    if(tblPos!=="ALL"&&d.pos!==tblPos) return false;
    if(tblTier&&d.tier!==tblTier) return false;
    if(tblUpgrade&&d.upgrade!==tblUpgrade) return false;
    return true;
  });
  if($.fn.DataTable.isDataTable("#mainTable")){
    const dt=$("#mainTable").DataTable();
    dt.clear();dt.rows.add(buildRows(data));dt.draw();
  } else {
    $("#mainTable").DataTable({
      data:buildRows(data),pageLength:25,lengthMenu:[25,50,100,551],
      columnDefs:[{targets:[1,9,10,11,20],orderable:false}],
      language:{search:"Search:"},
      drawCallback:function(){
        document.getElementById("tbl-count").textContent=
          this.api().rows({filter:"applied"}).count()+" players";
      }
    });
  }
  document.getElementById("tbl-count").textContent=data.length+" players";
}
document.querySelectorAll(".tbl-pos").forEach(b=>b.addEventListener("click",()=>{
  document.querySelectorAll(".tbl-pos").forEach(x=>x.classList.remove("active"));
  b.classList.add("active"); tblPos=b.dataset.pos; applyTblFilters();
}));
document.getElementById("tblTier").addEventListener("change",e=>{tblTier=e.target.value;applyTblFilters();});
document.getElementById("tblUpgrade").addEventListener("change",e=>{tblUpgrade=e.target.value;applyTblFilters();});
applyTblFilters();
</script>
</body>
</html>"""

if __name__ == "__main__":
    build()
