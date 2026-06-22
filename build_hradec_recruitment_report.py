"""
FC Hradec Králové — Jamestown Recruitment Report
Clean, white-background PDF.

Pages:
  1  Cover + squad quality overview
  2  Value scatter (SQS vs market value, all positions)
  3-9 Per-position target tables (top 8 per role)
  10  Priority shortlist (top 15 clear upgrades)
"""

import os, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from io import BytesIO

warnings.filterwarnings("ignore")

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_FILE  = os.path.join(BASE_DIR, "hradec_recruitment_2526.xlsx")
SQUAD_FILE = os.path.join(BASE_DIR, "hradec_player_tracking.xlsx")
OUTPUT_PDF = os.path.join(BASE_DIR, "hradec_recruitment_report.pdf")

PW, PH = A4   # 595 x 842 pt (portrait)

# Palette — clean, minimal
BLACK   = "#111111"
GREY1   = "#444444"
GREY2   = "#888888"
GREY3   = "#CCCCCC"
GREY4   = "#F2F2F2"
WHITE   = "#FFFFFF"
BLUE    = "#1A56DB"
GREEN   = "#1E8449"
AMBER   = "#D4700A"
RED     = "#C0392B"
ACCENT  = "#1A56DB"   # main accent — blue

POSITION_ORDER  = ["GK", "CB", "FB", "DM", "CM", "W", "FW"]
POSITION_LABELS = {
    "GK": "Goalkeeper", "CB": "Centre-Back", "FB": "Full-Back",
    "DM": "Defensive Mid", "CM": "Central Mid", "W": "Winger", "FW": "Forward",
}
IMPECT_MAP = {
    "GOALKEEPER": "GK", "CENTRAL_DEFENDER": "CB",
    "RIGHT_CENTRAL_DEFENDER": "CB", "LEFT_CENTRAL_DEFENDER": "CB",
    "RIGHT_DEFENDER": "FB", "LEFT_DEFENDER": "FB",
    "RIGHT_WINGBACK_DEFENDER": "FB", "LEFT_WINGBACK_DEFENDER": "FB",
    "DEFENSE_MIDFIELD": "DM", "CENTRAL_MIDFIELD": "CM",
    "ATTACKING_MIDFIELD": "CM", "RIGHT_WINGER": "W",
    "LEFT_WINGER": "W", "CENTER_FORWARD": "FW", "SECOND_STRIKER": "FW",
}
STAT_COLS = {
    "GK": ["Save rate, %", "Prevented goals per 90", "Exits per 90", "Accurate passes, %"],
    "CB": ["Defensive duels won, %", "Aerial duels won, %", "PAdj Interceptions", "Progressive passes per 90"],
    "FB": ["Defensive duels won, %", "Crosses per 90", "Accurate crosses, %", "Progressive runs per 90"],
    "DM": ["PAdj Interceptions", "Defensive duels won, %", "Accurate passes, %", "Progressive passes per 90"],
    "CM": ["Key passes per 90", "Progressive passes per 90", "xA per 90", "Goals per 90"],
    "W":  ["Goals per 90", "Assists per 90", "Dribbles per 90", "Touches in box per 90"],
    "FW": ["Goals per 90", "xG per 90", "Shots on target, %", "Touches in box per 90"],
}
STAT_SHORT = {
    "Save rate, %": "Save %",
    "Prevented goals per 90": "Prev. Goals/90",
    "Exits per 90": "Exits/90",
    "Accurate passes, %": "Pass Acc %",
    "Defensive duels won, %": "Def Duel %",
    "Aerial duels won, %": "Aerial %",
    "PAdj Interceptions": "Interceptions",
    "Progressive passes per 90": "Prog Pass/90",
    "Crosses per 90": "Crosses/90",
    "Accurate crosses, %": "Cross Acc %",
    "Progressive runs per 90": "Prog Runs/90",
    "Key passes per 90": "Key Pass/90",
    "xA per 90": "xA/90",
    "Goals per 90": "Goals/90",
    "Assists per 90": "Assists/90",
    "Dribbles per 90": "Dribbles/90",
    "Touches in box per 90": "Box Touches/90",
    "xG per 90": "xG/90",
    "Shots on target, %": "SoT %",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fig_to_imageread(fig, dpi=180):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return ImageReader(buf)


def stamp_page(c, page_num, total):
    c.setFont("Helvetica", 7)
    c.setFillColorCMYK(0, 0, 0, 0.6)
    c.drawString(36, 18, "FC Hradec Králové  ·  Jamestown Recruitment Model  ·  2025–2026")
    c.drawRightString(PW - 36, 18, f"{page_num} / {total}")


def contract_label(val):
    """Return (text, colour) for contract expiry."""
    if not isinstance(val, str) or not val.strip():
        return "—", GREY2
    try:
        yr = int(str(val).strip()[:4])
        if yr <= 2026: return f"Jun {yr} ⚡", AMBER
        if yr == 2027: return f"Jun {yr}", GREY1
        return f"Jun {yr}", GREEN
    except Exception:
        return str(val)[:8], GREY2


def qual_color(pct):
    if pct >= 70: return GREEN
    if pct >= 40: return AMBER
    return RED


def bi_color(bi):
    if pd.isna(bi): return GREY2
    if bi >= 20: return GREEN
    if bi >= 10: return BLUE
    if bi >= -10: return GREY1
    return RED


# ---------------------------------------------------------------------------
# Page 1 — Cover
# ---------------------------------------------------------------------------

def page_cover(c, df, squad_df):
    fig, ax = plt.subplots(figsize=(PW / 72, PH / 72))
    fig.patch.set_facecolor(WHITE)
    ax.set_facecolor(WHITE)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    # Top accent bar
    ax.add_patch(Rectangle((0, 0.96), 1, 0.04, color=BLUE, transform=ax.transAxes, clip_on=False))

    # Title
    ax.text(0.06, 0.905, "FC HRADEC KRÁLOVÉ", fontsize=26, fontweight="bold",
            color=BLACK, transform=ax.transAxes, va="top")
    ax.text(0.06, 0.870, "Recruitment Intelligence Report  ·  Season 2025–2026",
            fontsize=11, color=GREY1, transform=ax.transAxes, va="top")
    ax.text(0.06, 0.847, "Jamestown methodology  ·  Budget ≤ €1,000,000  ·  Age ≤ 30",
            fontsize=9, color=GREY2, transform=ax.transAxes, va="top")

    # Thin divider
    ax.axhline(0.835, xmin=0.06, xmax=0.94, color=GREY3, linewidth=0.8)

    # Quick stats row
    squad_q = squad_df.copy()
    squad_q["pos_group"] = squad_q["position"].map(IMPECT_MAP).fillna("CM")
    squad_q["q"] = squad_q["IMPECT_SCORE_PACKING_pct"] * 100

    n_upgrades = int((df["upgrade_flag"] == "CLEAR UPGRADE").sum())
    n_elite    = int((df["bloom_index"] >= 30).sum())
    n_exp26    = int(df["Contract expires"].astype(str).str.startswith("2026").sum())

    stats = [
        ("551", "Candidates\nanalysed"),
        (str(n_upgrades), "Clear\nupgrades"),
        (str(n_elite), "Elite\nvalue targets"),
        (str(n_exp26), "Expiring\ncontracts 2026"),
    ]
    for j, (num, label) in enumerate(stats):
        x = 0.06 + j * 0.24
        ax.text(x, 0.800, num, fontsize=28, fontweight="bold", color=BLUE,
                transform=ax.transAxes, va="top")
        ax.text(x, 0.762, label, fontsize=8, color=GREY2,
                transform=ax.transAxes, va="top", linespacing=1.5)

    ax.axhline(0.740, xmin=0.06, xmax=0.94, color=GREY3, linewidth=0.8)

    # Squad quality section
    ax.text(0.06, 0.725, "CURRENT SQUAD — POSITION QUALITY",
            fontsize=9, fontweight="bold", color=BLACK, transform=ax.transAxes, va="top")
    ax.text(0.06, 0.706, "Based on Impect percentile scores vs Czech top-flight peers",
            fontsize=8, color=GREY2, transform=ax.transAxes, va="top")

    bar_x0 = 0.22; bar_xmax = 0.70; row_h = 0.052; y0 = 0.685
    for i, pg in enumerate(POSITION_ORDER):
        sub = squad_q[squad_q["pos_group"] == pg].nlargest(2, "playDuration")
        q = sub["q"].mean() if len(sub) > 0 else 0
        names = "  ·  ".join(sub["commonname"].tolist()) if len(sub) > 0 else "—"
        y = y0 - i * row_h

        ax.text(0.06, y, POSITION_LABELS[pg], fontsize=8.5, fontweight="bold",
                color=BLACK, transform=ax.transAxes, va="center")
        ax.text(bar_x0 - 0.01, y, names, fontsize=7.5, color=GREY2,
                transform=ax.transAxes, va="center", ha="right")

        # Bar background
        ax.add_patch(Rectangle((bar_x0, y - 0.012), bar_xmax, 0.024,
                               color=GREY4, transform=ax.transAxes))
        # Fill
        fill_w = bar_xmax * (q / 100)
        col = qual_color(q)
        ax.add_patch(Rectangle((bar_x0, y - 0.012), fill_w, 0.024,
                               color=col, alpha=0.85, transform=ax.transAxes))

        ax.text(bar_x0 + bar_xmax + 0.01, y, f"{q:.0f}th",
                fontsize=8, color=col, fontweight="bold",
                transform=ax.transAxes, va="center")

        status = "STRENGTH" if q >= 70 else "NEEDS COVER" if q >= 40 else "PRIORITY"
        ax.text(bar_x0 + bar_xmax + 0.065, y, status,
                fontsize=7.5, color=col, transform=ax.transAxes, va="center")

    ax.axhline(0.320, xmin=0.06, xmax=0.94, color=GREY3, linewidth=0.8)

    # Methodology note
    ax.text(0.06, 0.305,
            "METHODOLOGY",
            fontsize=8, fontweight="bold", color=BLACK, transform=ax.transAxes, va="top")
    method_text = (
        "Statistical Quality Score (SQS): position-weighted composite of per-90 Wyscout metrics, "
        "adjusted for league difficulty (CZ II ×0.82 · Slovakia ×0.78 · Slovakia II ×0.68).\n\n"
        "Bloom Index (BI): SQS percentile rank minus Market Value percentile rank within the same position pool. "
        "A positive BI indicates a player performing above what the market currently prices in — the core "
        "Jamestown value signal.\n\n"
        "Market value model: XGBoost with 5-fold out-of-fold predictions to avoid in-sample inflation. "
        "Recruitment universe: CZ II + Slovak leagues, 2025–2026 season only."
    )
    ax.text(0.06, 0.280, method_text, fontsize=7.8, color=GREY1,
            transform=ax.transAxes, va="top", linespacing=1.6, wrap=True,
            multialignment="left")

    img = fig_to_imageread(fig)
    plt.close(fig)
    c.drawImage(img, 0, 0, PW, PH)
    stamp_page(c, 1, 10)
    c.showPage()


# ---------------------------------------------------------------------------
# Page 2 — Value scatter (one panel per position)
# ---------------------------------------------------------------------------

def page_value_map(c, df):
    fig = plt.figure(figsize=(PH / 72, PW / 72))   # landscape
    fig.patch.set_facecolor(WHITE)

    fig.text(0.5, 0.96, "Value Map — SQS Rank vs Market Value",
             ha="center", fontsize=14, fontweight="bold", color=BLACK)
    fig.text(0.5, 0.925,
             "Each dot is a candidate player.  Gold ring = clear upgrade on current Hradec starter.  "
             "Bubble size = Bloom Index magnitude.",
             ha="center", fontsize=8, color=GREY2)

    axes = fig.subplots(2, 4, gridspec_kw=dict(
        hspace=0.55, wspace=0.35, left=0.06, right=0.97, top=0.88, bottom=0.10
    ))

    with_mv = df[df["Market value"] > 0].copy()

    for idx, pg in enumerate(POSITION_ORDER):
        row, col = divmod(idx, 4)
        ax = axes[row][col]
        ax.set_facecolor(GREY4)
        ax.spines[:].set_color(GREY3)
        ax.tick_params(colors=GREY2, labelsize=6.5)
        ax.xaxis.label.set_color(GREY2)
        ax.yaxis.label.set_color(GREY2)

        sub = with_mv[with_mv["pos_group"] == pg]
        if len(sub) == 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=GREY2, transform=ax.transAxes, fontsize=8)
            ax.set_title(POSITION_LABELS[pg], fontsize=9, fontweight="bold", color=BLACK, pad=6)
            continue

        bi_vals = sub["bloom_index"].fillna(0).clip(0, 80)
        sizes = bi_vals * 1.5 + 18

        # Colour by upgrade status
        colors = [GREEN if u == "CLEAR UPGRADE" else BLUE if u == "ROTATIONAL / COVER"
                  else GREY3 for u in sub["upgrade_flag"]]

        ax.scatter(sub["Market value"] / 1000, sub["sqs_rank"],
                   c=colors, s=sizes, alpha=0.7, edgecolors="white", linewidths=0.4, zorder=3)

        # Gold ring for clear upgrades
        upgrades = sub[sub["upgrade_flag"] == "CLEAR UPGRADE"]
        ax.scatter(upgrades["Market value"] / 1000, upgrades["sqs_rank"],
                   s=sizes[upgrades.index] + 60,
                   facecolors="none", edgecolors="#D4A017", linewidths=1.5, zorder=4)

        # Label top 3
        for _, r in sub.nlargest(3, "bloom_index").iterrows():
            name = str(r["Player"]).split()[-1]
            ax.annotate(name, (r["Market value"] / 1000, r["sqs_rank"]),
                        xytext=(3, 3), textcoords="offset points",
                        fontsize=5.5, color=BLACK)

        ax.set_xlabel("Market Value (€k)", fontsize=7)
        ax.set_ylabel("SQS Rank", fontsize=7)
        ax.set_ylim(0, 105)
        ax.axhline(50, color=GREY3, linewidth=0.7, linestyle="--")
        ax.set_title(POSITION_LABELS[pg], fontsize=9, fontweight="bold", color=BLACK, pad=6)
        ax.grid(True, color=WHITE, linewidth=0.8, alpha=0.9)

    # Hide last panel
    axes[1][3].set_visible(False)

    # Legend
    legend_els = [
        mpatches.Patch(color=GREEN, label="Clear upgrade"),
        mpatches.Patch(color=BLUE, label="Rotational / cover"),
        mpatches.Patch(color=GREY3, label="Depth"),
        mpatches.Patch(facecolor="none", edgecolor="#D4A017", label="Gold ring = upgrade"),
    ]
    fig.legend(handles=legend_els, loc="lower center", ncol=4, fontsize=7.5,
               facecolor=WHITE, edgecolor=GREY3, framealpha=1,
               bbox_to_anchor=(0.5, 0.01))

    img = fig_to_imageread(fig, dpi=180)
    plt.close(fig)
    c.setPageSize((PH, PW))   # landscape
    c.drawImage(img, 0, 0, PH, PW)
    c.setPageSize(A4)
    stamp_page(c, 2, 10)
    c.showPage()


# ---------------------------------------------------------------------------
# Pages 3–9 — Per-position tables
# ---------------------------------------------------------------------------

def page_position(c, df, squad_df, pg, page_num):
    squad_df = squad_df.copy()
    squad_df["pos_group"] = squad_df["position"].map(IMPECT_MAP).fillna("CM")
    squad_df["q"] = squad_df["IMPECT_SCORE_PACKING_pct"] * 100

    starters = squad_df[squad_df["pos_group"] == pg].nlargest(2, "playDuration")
    starter_names = "  /  ".join(starters["commonname"].tolist()) if len(starters) > 0 else "—"
    starter_q = starters["q"].mean() if len(starters) > 0 else 50.0

    targets = df[df["pos_group"] == pg].sort_values(
        "bloom_index", ascending=False, na_position="last"
    ).head(8).reset_index(drop=True)

    stats = [s for s in STAT_COLS.get(pg, []) if s in df.columns]

    fig, ax = plt.subplots(figsize=(PW / 72, PH / 72))
    fig.patch.set_facecolor(WHITE)
    ax.set_facecolor(WHITE); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    # Header bar
    ax.add_patch(Rectangle((0, 0.956), 1, 0.044, color=BLUE, transform=ax.transAxes, clip_on=False))
    ax.text(0.04, 0.978, POSITION_LABELS[pg].upper(), fontsize=13, fontweight="bold",
            color=WHITE, transform=ax.transAxes, va="center")
    ax.text(0.96, 0.978, "FC HRADEC KRÁLOVÉ  ·  2025–2026 RECRUITMENT",
            fontsize=8, color=WHITE, transform=ax.transAxes, va="center", ha="right")

    # Subheader
    ax.text(0.04, 0.934,
            f"Current starters: {starter_names}   ·   Impect quality: {starter_q:.0f}th percentile",
            fontsize=8.5, color=GREY1, transform=ax.transAxes, va="center")
    ax.axhline(0.922, xmin=0.04, xmax=0.96, color=GREY3, linewidth=0.6)

    if len(targets) == 0:
        ax.text(0.5, 0.5, "No candidates found for this position.",
                ha="center", va="center", fontsize=11, color=GREY2, transform=ax.transAxes)
        img = fig_to_imageread(fig)
        plt.close(fig)
        c.setPageSize(A4)
        c.drawImage(img, 0, 0, PW, PH)
        stamp_page(c, page_num, 10)
        c.showPage()
        return

    # Column header row
    col_xs = {
        "rank":     0.040,
        "player":   0.075,
        "team":     0.310,
        "age":      0.490,
        "contract": 0.530,
        "mv":       0.620,
        "sqs":      0.700,
        "bi":       0.755,
        "flag":     0.800,
    }
    hdr_y = 0.905
    hdrs = {"rank": "#", "player": "Player", "team": "Team / League",
            "age": "Age", "contract": "Contract", "mv": "Mkt Val",
            "sqs": "SQS", "bi": "BI", "flag": "Status"}
    for k, x in col_xs.items():
        ax.text(x, hdr_y, hdrs[k], fontsize=7.5, fontweight="bold",
                color=GREY2, transform=ax.transAxes, va="center")

    # Stat columns header (right block)
    stat_x0 = 0.04; stat_w = 0.20; stat_gap = 0.005
    stat_block_x = [(stat_x0 + i * (stat_w + stat_gap)) for i in range(len(stats))]

    row_h = 0.098; y0 = 0.872

    for i, (_, row) in enumerate(targets.iterrows()):
        y = y0 - i * row_h
        bg = GREY4 if i % 2 == 0 else WHITE
        ax.add_patch(Rectangle((0.03, y - 0.040), 0.94, row_h - 0.006,
                               color=bg, transform=ax.transAxes))

        # Left accent strip (upgrade colour)
        uf = str(row.get("upgrade_flag", ""))
        strip_col = GREEN if uf == "CLEAR UPGRADE" else BLUE if uf == "ROTATIONAL / COVER" else GREY3
        ax.add_patch(Rectangle((0.03, y - 0.040), 0.005, row_h - 0.006,
                               color=strip_col, transform=ax.transAxes))

        # Rank
        ax.text(col_xs["rank"], y, f"{i+1}", fontsize=9, fontweight="bold",
                color=GREY2, transform=ax.transAxes, va="center")

        # Player name
        ax.text(col_xs["player"], y + 0.014, str(row["Player"]),
                fontsize=9, fontweight="bold", color=BLACK, transform=ax.transAxes, va="center")
        ax.text(col_xs["player"], y - 0.016, f"{row['Position']}",
                fontsize=7, color=GREY2, transform=ax.transAxes, va="center")

        # Team
        ax.text(col_xs["team"], y + 0.014, str(row["Team"]),
                fontsize=8.5, color=BLACK, transform=ax.transAxes, va="center")
        ax.text(col_xs["team"], y - 0.016, str(row["league"]),
                fontsize=7, color=GREY2, transform=ax.transAxes, va="center")

        # Age
        age_col = GREEN if row["Age"] <= 23 else GREY1 if row["Age"] <= 27 else GREY2
        ax.text(col_xs["age"], y, str(int(row["Age"])),
                fontsize=9, color=age_col, fontweight="bold",
                transform=ax.transAxes, va="center")

        # Contract
        cflag, ccol = contract_label(row.get("Contract expires", ""))
        ax.text(col_xs["contract"], y, cflag, fontsize=7.5, color=ccol,
                transform=ax.transAxes, va="center")

        # Market value
        mv = f"€{int(row['Market value']):,}" if row.get("Market value", 0) > 0 else "—"
        ax.text(col_xs["mv"], y, mv, fontsize=8, color=BLACK,
                transform=ax.transAxes, va="center")

        # SQS
        sqs = row.get("sqs_rank", 0)
        sqs_col = GREEN if sqs >= 70 else AMBER if sqs >= 40 else RED
        ax.text(col_xs["sqs"], y, f"{sqs:.0f}",
                fontsize=9, fontweight="bold", color=sqs_col,
                transform=ax.transAxes, va="center")

        # Bloom Index
        bi = row.get("bloom_index", np.nan)
        bi_str = f"{bi:+.0f}" if pd.notna(bi) else "—"
        ax.text(col_xs["bi"], y, bi_str, fontsize=9, fontweight="bold",
                color=bi_color(bi), transform=ax.transAxes, va="center")

        # Upgrade flag (short)
        flag_short = {"CLEAR UPGRADE": "↑ Upgrade", "ROTATIONAL / COVER": "~ Cover",
                      "DEPTH": "Depth"}.get(uf, uf)
        ax.text(col_xs["flag"], y, flag_short, fontsize=7.5, color=strip_col,
                fontweight="bold", transform=ax.transAxes, va="center")

    # Stat mini bars section at bottom
    if len(stats) > 0 and len(targets) > 0:
        ax.axhline(0.088, xmin=0.04, xmax=0.96, color=GREY3, linewidth=0.6)
        ax.text(0.04, 0.078, "KEY METRICS — percentile fill within position pool",
                fontsize=7.5, fontweight="bold", color=GREY2, transform=ax.transAxes, va="center")

        bar_w = 0.88 / len(targets)
        bar_h_bar = 0.022
        bar_y_base = 0.040

        # Stat row labels
        stat_y_positions = [bar_y_base + s * (bar_h_bar + 0.005) for s in range(len(stats))]

        for si, sc in enumerate(stats):
            sy = stat_y_positions[si]
            short = STAT_SHORT.get(sc, sc[:16])
            ax.text(0.038, sy + bar_h_bar / 2, short, fontsize=6,
                    color=GREY2, transform=ax.transAxes, va="center", ha="left")

            col_vals = pd.to_numeric(df[df["pos_group"] == pg][sc], errors="coerce").dropna()

            for ti, (_, row) in enumerate(targets.iterrows()):
                bx = 0.155 + ti * bar_w
                val = float(row.get(sc, 0) or 0)
                pct = float((col_vals <= val).sum()) / max(len(col_vals), 1)
                bar_col = GREEN if pct >= 0.7 else AMBER if pct >= 0.4 else RED

                # Background
                ax.add_patch(Rectangle((bx, sy), bar_w - 0.004, bar_h_bar,
                                       color=GREY4, transform=ax.transAxes))
                # Fill
                ax.add_patch(Rectangle((bx, sy), (bar_w - 0.004) * pct, bar_h_bar,
                                       color=bar_col, alpha=0.75, transform=ax.transAxes))
                # Value label
                ax.text(bx + (bar_w - 0.004) / 2, sy + bar_h_bar / 2,
                        f"{val:.1f}", fontsize=5.5, color=BLACK,
                        transform=ax.transAxes, va="center", ha="center")

                if si == 0:
                    # Player name above first bar row
                    name_short = str(targets.iloc[ti]["Player"]).split()[-1][:10]
                    ax.text(bx + (bar_w - 0.004) / 2, sy + bar_h_bar + 0.012,
                            name_short, fontsize=5.5, color=GREY1,
                            transform=ax.transAxes, va="center", ha="center")

    img = fig_to_imageread(fig, dpi=180)
    plt.close(fig)
    c.setPageSize(A4)
    c.drawImage(img, 0, 0, PW, PH)
    stamp_page(c, page_num, 10)
    c.showPage()


# ---------------------------------------------------------------------------
# Page 10 — Priority shortlist
# ---------------------------------------------------------------------------

def page_shortlist(c, df, page_num):
    top = df[df["upgrade_flag"] == "CLEAR UPGRADE"].nlargest(15, "bloom_index").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(PW / 72, PH / 72))
    fig.patch.set_facecolor(WHITE)
    ax.set_facecolor(WHITE); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    # Header
    ax.add_patch(Rectangle((0, 0.956), 1, 0.044, color=BLUE, transform=ax.transAxes, clip_on=False))
    ax.text(0.04, 0.978, "PRIORITY SHORTLIST", fontsize=13, fontweight="bold",
            color=WHITE, transform=ax.transAxes, va="center")
    ax.text(0.96, 0.978, "TOP 15 CLEAR UPGRADES  ·  ALL POSITIONS",
            fontsize=8, color=WHITE, transform=ax.transAxes, va="center", ha="right")

    ax.text(0.04, 0.934,
            "Ranked by Bloom Index  ·  All are clear upgrades on current Hradec starters  ·  Budget ≤ €1M",
            fontsize=8.5, color=GREY1, transform=ax.transAxes, va="center")
    ax.axhline(0.922, xmin=0.04, xmax=0.96, color=GREY3, linewidth=0.6)

    # Column headers
    cols = {
        "#":         0.040,
        "Player":    0.075,
        "Pos":       0.300,
        "Team":      0.340,
        "Age":       0.530,
        "Contract":  0.570,
        "Mkt Val":   0.665,
        "SQS":       0.760,
        "BI":        0.820,
        "vs Hradec": 0.875,
    }
    hdr_y = 0.905
    for hdr, x in cols.items():
        ax.text(x, hdr_y, hdr, fontsize=7.5, fontweight="bold",
                color=GREY2, transform=ax.transAxes, va="center")
    ax.axhline(0.896, xmin=0.04, xmax=0.96, color=GREY3, linewidth=0.4)

    row_h = 0.054; y0 = 0.876

    for i, (_, row) in enumerate(top.iterrows()):
        y = y0 - i * row_h
        bg = GREY4 if i % 2 == 0 else WHITE
        ax.add_patch(Rectangle((0.03, y - 0.024), 0.94, row_h - 0.004,
                               color=bg, transform=ax.transAxes))

        bi = row.get("bloom_index", np.nan)
        strip_col = GREEN if pd.notna(bi) and bi >= 20 else BLUE

        ax.add_patch(Rectangle((0.03, y - 0.024), 0.004, row_h - 0.004,
                               color=strip_col, transform=ax.transAxes))

        mv = f"€{int(row['Market value']):,}" if row.get("Market value", 0) > 0 else "—"
        bi_str = f"{bi:+.0f}" if pd.notna(bi) else "—"
        cflag, ccol = contract_label(row.get("Contract expires", ""))
        gap = row.get("vs_hradec_gap", np.nan)
        gap_str = f"{gap:+.0f}" if pd.notna(gap) else "—"
        sqs = row.get("sqs_rank", 0)

        values = {
            "#":         (f"{i+1}", GREY2, False),
            "Player":    (str(row["Player"])[:28], BLACK, True),
            "Pos":       (str(row["pos_group"]), BLUE, False),
            "Team":      (str(row["Team"])[:22], GREY1, False),
            "Age":       (str(int(row["Age"])), GREEN if row["Age"] <= 23 else GREY1, False),
            "Contract":  (cflag, ccol, False),
            "Mkt Val":   (mv, BLACK, False),
            "SQS":       (f"{sqs:.0f}", GREEN if sqs >= 70 else AMBER if sqs >= 40 else RED, True),
            "BI":        (bi_str, strip_col, True),
            "vs Hradec": (gap_str, GREEN if pd.notna(gap) and gap > 0 else RED, True),
        }

        for hdr, x in cols.items():
            val, col, bold = values[hdr]
            ax.text(x, y, val, fontsize=8.5 if bold else 8,
                    color=col, fontweight="bold" if bold else "normal",
                    transform=ax.transAxes, va="center")

    # Footer note
    ax.axhline(0.055, xmin=0.04, xmax=0.96, color=GREY3, linewidth=0.6)
    ax.text(0.04, 0.040,
            "vs Hradec = SQS rank gap vs current starter average at that position.  "
            "⚡ = contract expiring 2026 (potential cut-price acquisition).",
            fontsize=7.5, color=GREY2, transform=ax.transAxes, va="center")

    img = fig_to_imageread(fig, dpi=180)
    plt.close(fig)
    c.setPageSize(A4)
    c.drawImage(img, 0, 0, PW, PH)
    stamp_page(c, page_num, 10)
    c.showPage()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    print("Building FC Hradec Králové recruitment report ...")

    df = pd.read_excel(DATA_FILE, sheet_name="All Targets (ranked)")
    squad_df = pd.read_excel(SQUAD_FILE)

    for col in ["Market value", "Age", "bloom_index", "sqs_rank", "Minutes played",
                "vs_hradec_gap"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    squad_df["playDuration"] = pd.to_numeric(
        squad_df["playDuration"], errors="coerce").fillna(0)
    squad_df["IMPECT_SCORE_PACKING_pct"] = pd.to_numeric(
        squad_df["IMPECT_SCORE_PACKING_pct"], errors="coerce").fillna(0)

    c = rl_canvas.Canvas(OUTPUT_PDF, pagesize=A4)
    c.setTitle("FC Hradec Králové — Recruitment Report 2025-26")

    print("  [1/4] Cover ...")
    page_cover(c, df, squad_df)

    print("  [2/4] Value map ...")
    page_value_map(c, df)

    print("  [3/4] Position pages ...")
    for i, pg in enumerate(POSITION_ORDER):
        print(f"         {pg} ...")
        page_position(c, df, squad_df, pg, page_num=3 + i)

    print("  [4/4] Shortlist ...")
    page_shortlist(c, df, page_num=10)

    c.save()
    print(f"\n  Done → {OUTPUT_PDF}")


if __name__ == "__main__":
    run()
