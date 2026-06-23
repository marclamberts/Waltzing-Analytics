"""
Jamestown Analytics-Style Recruitment Model — FC Hradec Králové
2025-2026 Season | Budget cap: €1,000,000 | Recruitment focus

Methodology:
  1. Statistical Quality Score (SQS) per position from Wyscout per-90 metrics
  2. Lamberts Index = SQS rank − Market Value rank (positive = underpriced)
  3. Each candidate benchmarked against the current Hradec starter at that role
  4. Universe: CZ II + Slovak leagues 2025-2026 only (not top-flight rivals)
"""

import os
import warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score
import xgboost as xgb

warnings.filterwarnings("ignore")

DATA_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Market I")
OUTPUT    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hradec_recruitment_2526.xlsx")
SQUAD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hradec_player_tracking.xlsx")

BUDGET_CAP = 1_000_000
ACTIVE_SEASON = "2025-2026"

# Files to INCLUDE in the recruitment universe (exclude Czech top-flight)
RECRUITMENT_LEAGUES = [
    "CZ II",
    "Slovakia",
    "Slovakia II",
]

# Age ceiling for recruits (Hradec won't chase 35-year-olds as improvements)
MAX_AGE = 30
MIN_MINUTES = 900  # ~10 full matches minimum

# ---------------------------------------------------------------------------
# Position mappings
# ---------------------------------------------------------------------------
POSITION_GROUPS = {
    "GK": ["GK"],
    "CB": ["CB", "RCB", "LCB", "RCB3", "LCB3"],
    "FB": ["RB", "LB", "RWB", "LWB", "RB5", "LB5"],
    "DM": ["DMF", "LDMF", "RDMF"],
    "CM": ["CMF", "LCMF", "RCMF", "AMF"],
    "W":  ["LW", "RW", "LWF", "RWF", "LAMF", "RAMF"],
    "FW": ["CF", "SS"],
}

# Impect position → our position group (for squad baseline lookup)
IMPECT_TO_GROUP = {
    "GOALKEEPER":                "GK",
    "CENTRAL_DEFENDER":          "CB",
    "RIGHT_CENTRAL_DEFENDER":    "CB",
    "LEFT_CENTRAL_DEFENDER":     "CB",
    "RIGHT_DEFENDER":            "FB",
    "LEFT_DEFENDER":             "FB",
    "RIGHT_WINGBACK_DEFENDER":   "FB",
    "LEFT_WINGBACK_DEFENDER":    "FB",
    "DEFENSE_MIDFIELD":          "DM",
    "CENTRAL_MIDFIELD":          "CM",
    "ATTACKING_MIDFIELD":        "CM",
    "RIGHT_WINGER":              "W",
    "LEFT_WINGER":               "W",
    "CENTER_FORWARD":            "FW",
    "SECOND_STRIKER":            "FW",
}

# League difficulty weights (relative to Czech I = 1.0)
LEAGUE_WEIGHTS = {
    "CZ":          1.00,   # Czech top-flight (excluded from targets but used for reference)
    "CZ II":       0.82,
    "Slovakia":    0.78,
    "Slovakia II": 0.68,
    "CZ U19":      0.55,
    "CZ U17":      0.50,
    "Slovakia U19":0.55,
}

# ---------------------------------------------------------------------------
# Weighted feature sets per position
# ---------------------------------------------------------------------------
POSITION_WEIGHTS = {
    "GK": {
        "Save rate, %": 3.0,
        "Prevented goals per 90": 3.0,
        "xG against per 90": -2.5,
        "Conceded goals per 90": -2.5,
        "Exits per 90": 1.5,
        "Accurate passes, %": 1.0,
        "Long passes per 90": 0.5,
    },
    "CB": {
        "Defensive duels won, %": 3.0,
        "Aerial duels won, %": 2.5,
        "PAdj Interceptions": 2.5,
        "Sliding tackles per 90": 1.0,
        "Progressive passes per 90": 1.5,
        "Accurate long passes, %": 1.0,
        "Fouls per 90": -1.0,
    },
    "FB": {
        "Defensive duels won, %": 2.0,
        "PAdj Interceptions": 1.5,
        "Crosses per 90": 2.0,
        "Accurate crosses, %": 2.0,
        "Progressive runs per 90": 2.0,
        "Assists per 90": 1.5,
        "xA per 90": 1.5,
        "Dribbles per 90": 1.0,
    },
    "DM": {
        "PAdj Interceptions": 3.0,
        "Defensive duels won, %": 2.5,
        "Aerial duels won, %": 1.5,
        "Progressive passes per 90": 2.0,
        "Accurate passes, %": 1.5,
        "Smart passes per 90": 1.0,
        "Fouls per 90": -1.5,
    },
    "CM": {
        "Progressive passes per 90": 2.5,
        "Key passes per 90": 2.5,
        "xA per 90": 2.0,
        "Deep completions per 90": 1.5,
        "Passes to final third per 90": 1.5,
        "Defensive duels won, %": 1.5,
        "Goals per 90": 1.0,
        "Through passes per 90": 1.5,
        "Smart passes per 90": 1.5,
    },
    "W": {
        "Goals per 90": 2.5,
        "xG per 90": 2.0,
        "Assists per 90": 2.0,
        "xA per 90": 2.0,
        "Dribbles per 90": 2.5,
        "Successful dribbles, %": 1.5,
        "Touches in box per 90": 2.5,
        "Progressive runs per 90": 1.5,
        "Deep completions per 90": 1.5,
    },
    "FW": {
        "Goals per 90": 3.5,
        "xG per 90": 3.0,
        "Non-penalty goals per 90": 2.0,
        "Shots on target, %": 2.0,
        "Goal conversion, %": 2.0,
        "Touches in box per 90": 2.0,
        "Assists per 90": 1.5,
        "xA per 90": 1.0,
        "Aerial duels won, %": 1.0,
    },
}

BASE_FEATURES = [
    "Age", "Minutes played",
    "Goals per 90", "xG per 90", "Assists per 90", "xA per 90",
    "Key passes per 90", "Progressive passes per 90",
    "Accurate progressive passes, %", "Progressive runs per 90",
    "Dribbles per 90", "Successful dribbles, %",
    "Touches in box per 90", "Deep completions per 90",
    "Defensive duels per 90", "Defensive duels won, %",
    "PAdj Interceptions", "Aerial duels won, %",
    "Shot assists per 90", "Smart passes per 90",
    "Accurate passes, %", "Fouls per 90",
    "Passes to final third per 90",
    "Accurate passes to final third, %",
]
GK_FEATURES = [
    "Age", "Minutes played",
    "Save rate, %", "Prevented goals per 90", "xG against per 90",
    "Conceded goals per 90", "Exits per 90",
    "Accurate passes, %", "Long passes per 90", "Accurate long passes, %",
    "Back passes received as GK per 90",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    dfs = []
    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith(".xlsx"):
            continue
        stem = fname.replace(".xlsx", "")
        parts = stem.rsplit(" ", 1)
        league = parts[0] if len(parts) == 2 else stem
        season = parts[1] if len(parts) == 2 else "unknown"
        df = pd.read_excel(os.path.join(DATA_DIR, fname))
        df["league"] = league
        df["season"] = season
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def assign_pos_group(pos_str) -> str:
    if not isinstance(pos_str, str):
        return "CM"
    primary = pos_str.split(",")[0].strip()
    for group, codes in POSITION_GROUPS.items():
        if primary in codes:
            return group
    for group, codes in POSITION_GROUPS.items():
        for code in codes:
            if code in primary:
                return group
    return "CM"


def clean_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def get_model_features(pos_group):
    return GK_FEATURES if pos_group == "GK" else BASE_FEATURES


# ---------------------------------------------------------------------------
# Load Hradec squad baseline
# ---------------------------------------------------------------------------

def load_hradec_squad() -> pd.DataFrame:
    sq = pd.read_excel(SQUAD_FILE)
    sq["pos_group"] = sq["position"].map(IMPECT_TO_GROUP).fillna("CM")
    # Use IMPECT_SCORE_PACKING_pct as the overall quality percentile (0–1 → 0–100)
    sq["hradec_quality_pct"] = (sq["IMPECT_SCORE_PACKING_pct"] * 100).round(1)
    return sq[["commonname", "position", "pos_group", "age", "hradec_quality_pct",
               "IMPECT_SCORE_PACKING_pct", "playDuration"]].copy()


def squad_baseline(squad: pd.DataFrame) -> dict:
    """
    For each position group, return the average and min quality pct of
    current Hradec starters (players with >10% match share, i.e. playDuration-based).
    """
    # Approximate starters: top-2 by playDuration per position group
    baseline = {}
    for pg in POSITION_GROUPS:
        grp = squad[squad["pos_group"] == pg].nlargest(2, "playDuration")
        if len(grp) == 0:
            baseline[pg] = {"avg_pct": 50.0, "min_pct": 50.0, "names": []}
        else:
            baseline[pg] = {
                "avg_pct": grp["hradec_quality_pct"].mean(),
                "min_pct": grp["hradec_quality_pct"].min(),
                "names": grp["commonname"].tolist(),
            }
    return baseline


# ---------------------------------------------------------------------------
# SQS with league adjustment
# ---------------------------------------------------------------------------

def compute_sqs(df: pd.DataFrame) -> pd.Series:
    scores = pd.Series(0.0, index=df.index)
    for pos_group, weights in POSITION_WEIGHTS.items():
        mask = df["pos_group"] == pos_group
        if mask.sum() == 0:
            continue
        raw = pd.Series(0.0, index=df[mask].index)
        for col, w in weights.items():
            if col not in df.columns:
                continue
            vals = pd.to_numeric(df.loc[mask, col], errors="coerce").fillna(0)
            raw += (-vals * abs(w)) if w < 0 else (vals * w)
        # Apply league difficulty multiplier
        lw = df.loc[mask, "league"].map(LEAGUE_WEIGHTS).fillna(0.7)
        raw = raw * lw
        scores.loc[mask] = raw.rank(pct=True) * 100
    return scores


# ---------------------------------------------------------------------------
# OOF XGBoost market-value model
# ---------------------------------------------------------------------------

def oof_predict_market_value(df: pd.DataFrame) -> pd.Series:
    model_values = pd.Series(np.nan, index=df.index)
    for pos_group in POSITION_GROUPS:
        pg_mask = df["pos_group"] == pos_group
        pg_df = df[pg_mask]
        feats = [f for f in get_model_features(pos_group) if f in pg_df.columns]
        labelled = pg_df[pg_df["Market value"] > 0].copy()
        unlabelled = pg_df[pg_df["Market value"] == 0].copy()
        if len(labelled) < 20:
            continue
        X_lab = labelled[feats].values.astype(float)
        y_lab = np.log1p(labelled["Market value"].values)
        scaler = StandardScaler()
        X_lab_s = scaler.fit_transform(X_lab)
        oof_preds = np.full(len(labelled), np.nan)
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        for ti, vi in kf.split(X_lab_s):
            m = xgb.XGBRegressor(
                n_estimators=300, max_depth=4, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.7,
                min_child_weight=3, reg_alpha=0.5, reg_lambda=2.0,
                random_state=42, verbosity=0,
            )
            m.fit(X_lab_s[ti], y_lab[ti])
            oof_preds[vi] = m.predict(X_lab_s[vi])
        model_values.loc[labelled.index] = np.expm1(oof_preds).round(-2)
        if len(unlabelled) > 0:
            full_m = xgb.XGBRegressor(
                n_estimators=300, max_depth=4, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.7,
                min_child_weight=3, reg_alpha=0.5, reg_lambda=2.0,
                random_state=42, verbosity=0,
            )
            full_m.fit(X_lab_s, y_lab)
            X_unlab = scaler.transform(unlabelled[feats].values.astype(float))
            model_values.loc[unlabelled.index] = np.expm1(full_m.predict(X_unlab)).round(-2)
    return model_values


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def lamberts_tier(bi):
    if pd.isna(bi):
        return "NO LISTED VALUE"
    if bi >= 30: return "ELITE VALUE"
    if bi >= 20: return "HIGH VALUE"
    if bi >= 10: return "VALUE"
    if bi >= -10: return "FAIR PRICE"
    if bi >= -20: return "SLIGHT OVERVALUE"
    return "OVERVALUED"


def upgrade_flag(sqs_rank: float, hradec_avg: float, hradec_min: float) -> str:
    """Would this player be an upgrade on Hradec's current option?"""
    if sqs_rank >= hradec_avg + 10:
        return "CLEAR UPGRADE"
    if sqs_rank >= hradec_min:
        return "ROTATIONAL / COVER"
    return "DEPTH"


def run():
    print("=" * 70)
    print("  FC HRADEC KRÁLOVÉ — JAMESTOWN RECRUITMENT MODEL")
    print(f"  Season: {ACTIVE_SEASON} | Budget cap: €{BUDGET_CAP:,}")
    print("=" * 70)

    # 1. Load all data (use full dataset to train the MV model)
    print("\n[1] Loading data ...")
    raw = load_data()
    all_feats = list(set(BASE_FEATURES + GK_FEATURES))
    raw["pos_group"] = raw["Position"].apply(assign_pos_group)
    raw = clean_numeric(raw, all_feats)
    raw["Market value"] = pd.to_numeric(raw["Market value"], errors="coerce").fillna(0)

    # Full universe for MV model training (all seasons, enough data)
    full = raw[raw["Minutes played"] >= MIN_MINUTES].copy().reset_index(drop=True)
    print(f"    Full universe (all seasons, ≥{MIN_MINUTES} min): {len(full):,} players")

    # 2. Load Hradec squad
    print("\n[2] Loading FC Hradec squad baseline ...")
    squad = load_hradec_squad()
    baseline = squad_baseline(squad)
    print(f"    Squad size: {len(squad)} players")
    for pg, b in baseline.items():
        names = ", ".join(b["names"]) if b["names"] else "—"
        print(f"    {pg:4s}  starters: {names}  |  avg quality: {b['avg_pct']:.0f}th pctile")

    # 3. SQS on full universe
    print("\n[3] Computing Statistical Quality Scores ...")
    full["sqs"] = compute_sqs(full)
    full["sqs_rank"] = full.groupby("pos_group")["sqs"].rank(pct=True) * 100

    # 4. OOF market value model (trained on full universe)
    print("\n[4] Training XGBoost market-value model (OOF) ...")
    full["model_value"] = oof_predict_market_value(full)

    full["mv_rank"] = np.nan
    for pg in POSITION_GROUPS:
        mask = (full["pos_group"] == pg) & (full["Market value"] > 0)
        if mask.sum() > 0:
            full.loc[mask, "mv_rank"] = full.loc[mask, "Market value"].rank(pct=True) * 100

    full["bloom_index"] = full["sqs_rank"] - full["mv_rank"]
    full["value_tier"] = full["bloom_index"].apply(lamberts_tier)
    full["value_ratio"] = np.where(
        full["Market value"] > 0,
        full["model_value"] / full["Market value"].replace(0, np.nan),
        np.nan,
    )

    # 5. Apply recruitment filters
    print("\n[5] Applying recruitment filters ...")
    targets = full[
        (full["season"] == ACTIVE_SEASON) &
        (full["league"].isin(RECRUITMENT_LEAGUES)) &
        (full["Market value"] <= BUDGET_CAP) &
        (full["Age"] <= MAX_AGE) &
        (full["Minutes played"] >= MIN_MINUTES)
    ].copy()
    print(f"    Candidates after filters: {len(targets):,}")

    # 6. Upgrade flag vs Hradec starters
    targets["hradec_starter_avg"] = targets["pos_group"].map(
        {pg: b["avg_pct"] for pg, b in baseline.items()}
    )
    targets["hradec_starter_min"] = targets["pos_group"].map(
        {pg: b["min_pct"] for pg, b in baseline.items()}
    )
    targets["hradec_starters"] = targets["pos_group"].map(
        {pg: " / ".join(b["names"]) for pg, b in baseline.items()}
    )
    targets["upgrade_flag"] = targets.apply(
        lambda r: upgrade_flag(r["sqs_rank"], r["hradec_starter_avg"], r["hradec_starter_min"]),
        axis=1,
    )
    targets["vs_hradec_gap"] = (targets["sqs_rank"] - targets["hradec_starter_avg"]).round(1)

    # 7. Output
    out_cols = [
        "Player", "Team", "league", "Position", "pos_group", "Age",
        "Contract expires", "Foot",
        "Market value", "model_value", "value_ratio",
        "sqs_rank", "bloom_index", "value_tier",
        "upgrade_flag", "vs_hradec_gap", "hradec_starters",
        "Minutes played",
        "Goals per 90", "xG per 90", "Assists per 90", "xA per 90",
        "Progressive passes per 90", "Progressive runs per 90",
        "Touches in box per 90", "Defensive duels won, %",
        "Aerial duels won, %", "Dribbles per 90", "Successful dribbles, %",
        "Key passes per 90", "PAdj Interceptions",
        "Save rate, %", "Prevented goals per 90",
    ]
    out_cols = [c for c in out_cols if c in targets.columns]

    print("\n[6] Writing output ...")
    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        # Master shortlist: clear upgrades, sorted by Lamberts Index
        upgrades = targets[targets["upgrade_flag"] == "CLEAR UPGRADE"].sort_values(
            "bloom_index", ascending=False, na_position="last"
        )
        upgrades[out_cols].to_excel(writer, sheet_name="CLEAR UPGRADES", index=False)

        # All targets ranked
        all_t = targets[out_cols].sort_values(
            "bloom_index", ascending=False, na_position="last"
        )
        all_t.to_excel(writer, sheet_name="All Targets (ranked)", index=False)

        # Per position
        for pg in POSITION_GROUPS:
            sub = targets[targets["pos_group"] == pg][out_cols].sort_values(
                "bloom_index", ascending=False, na_position="last"
            )
            if len(sub) > 0:
                sub.to_excel(writer, sheet_name=pg, index=False)

        # Hradec squad overview
        squad_out = squad.copy()
        squad_out.to_excel(writer, sheet_name="Hradec Squad", index=False)

    print(f"    Saved → {OUTPUT}")

    # 8. Console summary
    print("\n" + "=" * 70)
    print("  CLEAR UPGRADES — top 5 per position")
    print("=" * 70)
    for pg in POSITION_GROUPS:
        sub = targets[
            (targets["pos_group"] == pg) &
            (targets["upgrade_flag"] == "CLEAR UPGRADE")
        ].sort_values("bloom_index", ascending=False, na_position="last").head(5)
        if len(sub) == 0:
            continue
        b = baseline[pg]
        print(f"\n  {pg} — current starters: {', '.join(b['names']) or '—'} "
              f"(avg {b['avg_pct']:.0f}th pctile)")
        print(f"  {'Player':<22} {'Team':<22} {'Age':>3}  "
              f"{'SQS':>5}  {'Gap':>5}  {'Mkt €':>8}  {'BI':>5}  Tier")
        print("  " + "-" * 85)
        for _, r in sub.iterrows():
            mv = f"{int(r['Market value']):,}" if r["Market value"] > 0 else "—"
            bi = f"{r['bloom_index']:+.1f}" if pd.notna(r["bloom_index"]) else "—"
            gap = f"{r['vs_hradec_gap']:+.1f}"
            print(
                f"  {str(r['Player']):<22} {str(r['Team']):<22} "
                f"{int(r['Age']):>3}  {r['sqs_rank']:>5.1f}  {gap:>5}  "
                f"{mv:>8}  {bi:>5}  {r['value_tier']}"
            )

    print(f"\n  Output: hradec_recruitment_2526.xlsx")


if __name__ == "__main__":
    run()
