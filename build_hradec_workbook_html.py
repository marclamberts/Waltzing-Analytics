"""
FC Hradec Králové — Jamestown Workbook HTML
Excel-style bottom tabs, document layout, full methodology.
"""
import os, json
import pandas as pd

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "hradec_recruitment_2526.xlsx")
OUTPUT    = os.path.join(BASE_DIR, "hradec_workbook.html")

STAT_COLS = [
    "Goals per 90","xG per 90","Assists per 90","xA per 90",
    "Progressive passes per 90","Progressive runs per 90","Touches in box per 90",
    "Defensive duels won, %","Aerial duels won, %","Dribbles per 90",
    "Successful dribbles, %","Key passes per 90","PAdj Interceptions",
    "Save rate, %","Prevented goals per 90",
]

PIZZA_METRICS = {
    "GK":[{"key":"sv_pct","label":"Save Rate %","cat":"gk"},{"key":"pg90","label":"Prev Goals/90","cat":"gk"},
          {"key":"adw","label":"Aerial Won %","cat":"def"},{"key":"ddw","label":"Def Duels Won %","cat":"def"},
          {"key":"int90","label":"Interceptions/90","cat":"def"},{"key":"pp90","label":"Prog Passes/90","cat":"pass"}],
    "CB":[{"key":"ddw","label":"Def Duels Won %","cat":"def"},{"key":"adw","label":"Aerial Won %","cat":"def"},
          {"key":"int90","label":"Interceptions/90","cat":"def"},{"key":"pp90","label":"Prog Passes/90","cat":"pass"},
          {"key":"pr90","label":"Prog Runs/90","cat":"pass"},{"key":"kp90","label":"Key Passes/90","cat":"pass"},{"key":"xg90","label":"xG/90","cat":"att"}],
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
            pc=col+"_pct"
            rec[key+"_pct"]=round(float(r.get(pc,0) if pc in r.index else 0),1)
        rows.append(rec)
    return rows

def build():
    print("Loading data...")
    df = load_data()
    records = player_records(df)
    tier_counts={t:sum(1 for r in records if r["tier"]==t) for t in ["ELITE","HIGH","VALUE","FAIR","OVER"]}
    pos_counts={p:sum(1 for r in records if r["pos"]==p) for p in ["GK","CB","FB","DM","CM","W","FW"]}
    pizza_meta={pos:[{"key":m["key"],"label":m["label"],"cat":m["cat"]} for m in ms]
                for pos,ms in PIZZA_METRICS.items()}

    with open(os.path.join(BASE_DIR,"workbook_template.html"), encoding="utf-8") as f:
        html = f.read()

    html = html.replace("__DATA_JSON__",   json.dumps(records, ensure_ascii=False))
    html = html.replace("__TIER_JSON__",   json.dumps(tier_counts))
    html = html.replace("__POS_JSON__",    json.dumps(pos_counts))
    html = html.replace("__PIZZA_JSON__",  json.dumps(pizza_meta))
    html = html.replace("__TOTAL__",       str(len(records)))

    with open(OUTPUT,"w",encoding="utf-8") as f:
        f.write(html)
    print(f"Done → {OUTPUT}  ({len(records)} players, {os.path.getsize(OUTPUT)//1024} KB)")

if __name__=="__main__":
    build()
