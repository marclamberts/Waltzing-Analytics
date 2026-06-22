"""
Jamestown Analytics-Style Player Valuation Model
Emulates Tony Bloom's value-finding approach:

  Core principle: find players whose STATISTICAL OUTPUT (per 90) significantly
  exceeds what their MARKET VALUE implies — i.e., find underpriced talent.

  Method:
  1. Build a position-specific Statistical Quality Score (SQS) from weighted
     per-90 metrics — this is the "true performance" signal.
  2. Train a regularised XGBoost on log(market_value) using out-of-fold
     predictions so model_value is a genuine OOF estimate, not in-sample.
  3. "Bloom Index" = SQS_percentile_rank − MV_percentile_rank (within position).
     Positive = player is performing above what the market prices in.
  4. Surface players with highest Bloom Index, sufficient minutes, young enough
     to be targets.
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

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Market I")
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Position groupings
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

# Weighted feature sets per position (weight = relative importance)
# Higher weight = more Jamestown-relevant for that role
POSITION_WEIGHTS = {
    "GK": {
        "Save rate, %": 3.0,
        "Prevented goals per 90": 3.0,
        "xG against per 90": -2.0,   # lower is better, negated below
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

# Features fed to the XGBoost market-value model
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
# Data loading & prep
# ---------------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    dfs = []
    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith(".xlsx"):
            continue
        stem = fname.replace(".xlsx", "")
        parts = stem.rsplit(" ", 1)
        df = pd.read_excel(os.path.join(DATA_DIR, fname))
        df["league"] = parts[0] if len(parts) == 2 else stem
        df["season"] = parts[1] if len(parts) == 2 else "unknown"
        df["source_file"] = fname
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def assign_position_group(pos_str) -> str:
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


def clean_numeric(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def get_model_features(pos_group: str) -> list:
    return GK_FEATURES if pos_group == "GK" else BASE_FEATURES


# ---------------------------------------------------------------------------
# Statistical Quality Score (SQS)
# ---------------------------------------------------------------------------

def compute_sqs(df: pd.DataFrame) -> pd.Series:
    """
    Compute a Statistical Quality Score for each player based on their
    position-specific weights. Returns a normalised 0-100 score.
    """
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
            if w < 0:
                # Invert: lower raw value = better, so we negate before weighting
                vals = -vals * abs(w)
            else:
                vals = vals * w
            raw += vals
        # Percentile rank within this position group → 0-100
        pct = raw.rank(pct=True) * 100
        scores.loc[mask] = pct

    return scores


# ---------------------------------------------------------------------------
# XGBoost out-of-fold market-value prediction
# ---------------------------------------------------------------------------

def oof_predict_market_value(df: pd.DataFrame) -> pd.Series:
    """
    For players WITH market values, produce out-of-fold XGBoost predictions
    (so we avoid train-on-same-data inflation).
    For players WITHOUT market values, predict using full model.
    Returns model_value (in €) for all players.
    """
    model_values = pd.Series(np.nan, index=df.index)

    for pos_group in POSITION_GROUPS:
        pg_mask = df["pos_group"] == pos_group
        pg_df = df[pg_mask].copy()
        feats = [f for f in get_model_features(pos_group) if f in pg_df.columns]

        # Split into labelled (has MV) and unlabelled
        labelled = pg_df[pg_df["Market value"] > 0].copy()
        unlabelled = pg_df[pg_df["Market value"] == 0].copy()

        if len(labelled) < 20:
            # Not enough to train; fall back to SQS as proxy
            continue

        X_lab = labelled[feats].values.astype(float)
        y_lab = np.log1p(labelled["Market value"].values)

        scaler = StandardScaler()
        X_lab_s = scaler.fit_transform(X_lab)

        # OOF predictions for labelled players
        oof_preds = np.full(len(labelled), np.nan)
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        for train_idx, val_idx in kf.split(X_lab_s):
            m = xgb.XGBRegressor(
                n_estimators=300, max_depth=4, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.7,
                min_child_weight=3, reg_alpha=0.5, reg_lambda=2.0,
                random_state=42, verbosity=0,
            )
            m.fit(X_lab_s[train_idx], y_lab[train_idx])
            oof_preds[val_idx] = m.predict(X_lab_s[val_idx])

        model_values.loc[labelled.index] = np.expm1(oof_preds).round(-2)

        # Full model for unlabelled players
        if len(unlabelled) > 0:
            full_model = xgb.XGBRegressor(
                n_estimators=300, max_depth=4, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.7,
                min_child_weight=3, reg_alpha=0.5, reg_lambda=2.0,
                random_state=42, verbosity=0,
            )
            full_model.fit(X_lab_s, y_lab)
            X_unlab = scaler.transform(unlabelled[feats].values.astype(float))
            preds_unlab = full_model.predict(X_unlab)
            model_values.loc[unlabelled.index] = np.expm1(preds_unlab).round(-2)

        # OOF R² for diagnostics
        valid_oof = ~np.isnan(oof_preds)
        r2 = r2_score(y_lab[valid_oof], oof_preds[valid_oof]) if valid_oof.sum() > 5 else np.nan
        print(
            f"    {pos_group:4s} — labelled={len(labelled):4d}  "
            f"unlabelled={len(unlabelled):4d}  OOF R²={r2:.3f}"
        )

    return model_values


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def bloom_index_tier(bi: float) -> str:
    """Value tier based on Bloom Index (SQS rank − MV rank, both 0-100)."""
    if bi >= 30:
        return "ELITE VALUE"
    if bi >= 20:
        return "HIGH VALUE"
    if bi >= 10:
        return "VALUE"
    if bi >= -10:
        return "FAIR PRICE"
    if bi >= -20:
        return "SLIGHT OVERVALUE"
    return "OVERVALUED"


def run():
    print("=" * 70)
    print("  JAMESTOWN ANALYTICS — PLAYER VALUATION MODEL")
    print("  Market I: Czech & Slovak Leagues | All Seasons")
    print("=" * 70)

    # 1. Load
    print("\n[1] Loading data ...")
    raw = load_data()
    print(f"    {len(raw):,} records from {raw['source_file'].nunique()} files")

    raw["pos_group"] = raw["Position"].apply(assign_position_group)
    all_feats = list(set(BASE_FEATURES + GK_FEATURES))
    raw = clean_numeric(raw, all_feats)

    MIN_MINUTES = 450
    df = raw[raw["Minutes played"] >= MIN_MINUTES].copy().reset_index(drop=True)
    print(f"    {len(df):,} players after ≥{MIN_MINUTES} min filter")
    print(f"    {(df['Market value'] > 0).sum():,} with listed market value")

    # 2. Statistical Quality Score
    print("\n[2] Computing Statistical Quality Scores ...")
    df["sqs"] = compute_sqs(df)
    # SQS percentile rank within position group
    df["sqs_rank"] = df.groupby("pos_group")["sqs"].rank(pct=True) * 100

    # 3. Market value percentile rank (within position, for those with listed MV)
    df["mv_rank"] = np.nan
    for pg in POSITION_GROUPS:
        mask = (df["pos_group"] == pg) & (df["Market value"] > 0)
        if mask.sum() > 0:
            df.loc[mask, "mv_rank"] = (
                df.loc[mask, "Market value"].rank(pct=True) * 100
            )

    # 4. OOF XGBoost model value
    print("\n[3] Training XGBoost (out-of-fold) ...")
    df["model_value"] = oof_predict_market_value(df)

    # 5. Bloom Index = SQS rank − MV rank (positive = undervalued)
    df["bloom_index"] = df["sqs_rank"] - df["mv_rank"]
    df["value_tier"] = df["bloom_index"].apply(
        lambda x: bloom_index_tier(x) if pd.notna(x) else "NO LISTED VALUE"
    )

    # Model value / market value ratio (for those with MV)
    df["value_ratio"] = np.where(
        df["Market value"] > 0,
        df["model_value"] / df["Market value"].replace(0, np.nan),
        np.nan,
    )

    # 6. Export
    print("\n[4] Writing output ...")
    out_cols = [
        "Player", "Team", "Position", "pos_group", "Age", "league", "season",
        "Minutes played", "Contract expires",
        "Market value", "model_value", "value_ratio",
        "sqs", "sqs_rank", "mv_rank", "bloom_index", "value_tier",
        "Goals per 90", "xG per 90", "Assists per 90", "xA per 90",
        "Progressive passes per 90", "Progressive runs per 90",
        "Touches in box per 90", "Defensive duels won, %",
        "Aerial duels won, %", "Dribbles per 90", "Successful dribbles, %",
        "Key passes per 90", "PAdj Interceptions", "Save rate, %",
    ]
    out_cols = [c for c in out_cols if c in df.columns]
    output = df[out_cols].copy()

    out_path = os.path.join(OUTPUT_DIR, "jamestown_valuations.xlsx")
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        # All players sorted by Bloom Index
        output.sort_values("bloom_index", ascending=False, na_position="last").to_excel(
            writer, sheet_name="All Players (Bloom)", index=False
        )

        # VALUE PICKS: high bloom index, enough minutes, reasonable age
        picks = output[
            (output["bloom_index"] >= 20) &
            (output["Minutes played"] >= 900) &
            (output["Age"] <= 28) &
            (output["Market value"] > 0)
        ].sort_values("bloom_index", ascending=False)
        picks.to_excel(writer, sheet_name="VALUE PICKS", index=False)

        # Broad value targets (no age/MV restriction, for unlisted players too)
        broad = output[
            (output["sqs_rank"] >= 65) &
            (output["Minutes played"] >= 900) &
            (output["Age"] <= 27)
        ].sort_values("sqs_rank", ascending=False)
        broad.to_excel(writer, sheet_name="TALENT POOL (no MV needed)", index=False)

        # Per-position sheets
        for pg in POSITION_GROUPS:
            sub = output[output["pos_group"] == pg].sort_values(
                "bloom_index", ascending=False, na_position="last"
            )
            if len(sub) > 0:
                sub.to_excel(writer, sheet_name=pg, index=False)

        # Overvalued
        overval = output[
            (output["bloom_index"] <= -25) &
            (output["Market value"] >= 200_000)
        ].sort_values("bloom_index")
        if len(overval) > 0:
            overval.to_excel(writer, sheet_name="OVERVALUED", index=False)

    print(f"    Saved → {out_path}")

    # 7. Console summary
    print("\n" + "=" * 70)
    print("  TOP VALUE PICKS (Bloom Index ≥ 20, age ≤ 28, ≥900 min, has MV)")
    print("=" * 70)
    top = output[
        (output["bloom_index"] >= 20) &
        (output["Minutes played"] >= 900) &
        (output["Age"] <= 28) &
        (output["Market value"] > 0)
    ].sort_values("bloom_index", ascending=False).head(30)

    if len(top) == 0:
        print("  No players met all filters.")
        # Diagnostic: what's the bloom index distribution?
        with_mv = output[output["Market value"] > 0]
        print(f"  Bloom index stats (players with MV, n={len(with_mv)}):")
        print(f"    mean={with_mv['bloom_index'].mean():.1f}  "
              f"std={with_mv['bloom_index'].std():.1f}  "
              f"max={with_mv['bloom_index'].max():.1f}  "
              f"min={with_mv['bloom_index'].min():.1f}")
        print(f"  ≥20: {(with_mv['bloom_index'] >= 20).sum()}")
        print(f"  ≥20 + age≤28: {((with_mv['bloom_index'] >= 20) & (with_mv['Age'] <= 28)).sum()}")
        print(f"  ≥20 + age≤28 + mins≥900: {((with_mv['bloom_index'] >= 20) & (with_mv['Age'] <= 28) & (with_mv['Minutes played'] >= 900)).sum()}")
    else:
        print(
            f"  {'Player':<22} {'Team':<20} {'Lg':<12} {'Pos':<5} "
            f"{'Age':>3}  {'Mkt €':>8}  {'SQS':>5}  {'BI':>5}  Tier"
        )
        print("  " + "-" * 100)
        for _, r in top.iterrows():
            mv = f"{int(r['Market value']):,}"
            bi = f"{r['bloom_index']:+.1f}" if pd.notna(r["bloom_index"]) else "—"
            sqs = f"{r['sqs_rank']:.0f}"
            print(
                f"  {str(r['Player']):<22} {str(r['Team']):<20} "
                f"{str(r['league']):<12} {str(r['pos_group']):<5} "
                f"{int(r['Age']):>3}  {mv:>8}  {sqs:>5}  {bi:>5}  {r['value_tier']}"
            )

    print("\n" + "=" * 70)
    print("  TALENT POOL — top performers regardless of listed MV (age ≤ 27)")
    print("=" * 70)
    talent = output[
        (output["sqs_rank"] >= 75) &
        (output["Minutes played"] >= 900) &
        (output["Age"] <= 27)
    ].sort_values("sqs_rank", ascending=False).head(20)

    if len(talent) > 0:
        print(
            f"  {'Player':<22} {'Team':<20} {'Lg':<12} {'Pos':<5} "
            f"{'Age':>3}  {'SQS rank':>8}  {'Mkt €':>8}"
        )
        print("  " + "-" * 90)
        for _, r in talent.iterrows():
            mv = f"{int(r['Market value']):,}" if r["Market value"] > 0 else "—"
            print(
                f"  {str(r['Player']):<22} {str(r['Team']):<20} "
                f"{str(r['league']):<12} {str(r['pos_group']):<5} "
                f"{int(r['Age']):>3}  {r['sqs_rank']:>8.1f}  {mv:>8}"
            )

    print(f"\n  Output: jamestown_valuations.xlsx")
    print(f"  Sheets: All Players (Bloom) | VALUE PICKS | TALENT POOL | GK/CB/FB/DM/CM/W/FW | OVERVALUED")


if __name__ == "__main__":
    run()
