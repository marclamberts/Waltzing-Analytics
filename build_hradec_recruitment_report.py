"""
FC Hradec Králové — Jamestown Recruitment Report
Generates a multi-page PDF with:
  Page 1  : Cover + Squad Quality Overview (heatmap)
  Page 2  : Value Map (SQS vs Market Value scatter, all positions)
  Pages 3-9: Per-position pages — top targets with comparison bars + contract flags
"""

import os
import warnings
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.colors import LinearSegmentedColormap
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from io import BytesIO
import matplotlib.patheffects as pe

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_FILE  = os.path.join(BASE_DIR, "hradec_recruitment_2526.xlsx")
OUTPUT_PDF = os.path.join(BASE_DIR, "hradec_recruitment_report.pdf")

PW, PH = A4  # 595 x 842 pt

# Colour palette
C_DARK   = "#0D1117"
C_NAVY   = "#1B2A4A"
C_BLUE   = "#1E88E5"
C_CYAN   = "#00BCD4"
C_GREEN  = "#43A047"
C_AMBER  = "#FB8C00"
C_RED    = "#E53935"
C_GOLD   = "#FFD600"
C_LIGHT  = "#E8EDF4"
C_MID    = "#8A9BBE"
C_WHITE  = "#FFFFFF"

TIER_COLORS = {
    "ELITE VALUE":      C_GREEN,
    "HIGH VALUE":       C_CYAN,
    "VALUE":            C_BLUE,
    "FAIR PRICE":       C_MID,
    "SLIGHT OVERVALUE": C_AMBER,
    "OVERVALUED":       C_RED,
    "NO LISTED VALUE":  "#6E6E6E",
}

POSITION_ORDER = ["GK", "CB", "FB", "DM", "CM", "W", "FW"]
POSITION_LABELS = {
    "GK": "Goalkeeper",
    "CB": "Centre-Back",
    "FB": "Full-Back",
    "DM": "Defensive Mid",
    "CM": "Central Mid",
    "W":  "Winger",
    "FW": "Forward",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fig_to_bytes(fig, dpi=150):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return buf


def draw_image(c, buf, x, y, w, h):
    img = ImageReader(buf)
    c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=True, mask="auto")


def set_dark_bg(fig, axes=None):
    fig.patch.set_facecolor(C_DARK)
    if axes:
        for ax in (axes if hasattr(axes, "__iter__") else [axes]):
            ax.set_facecolor(C_NAVY)
            ax.tick_params(colors=C_LIGHT)
            ax.xaxis.label.set_color(C_LIGHT)
            ax.yaxis.label.set_color(C_LIGHT)
            ax.title.set_color(C_WHITE)
            for spine in ax.spines.values():
                spine.set_edgecolor(C_MID)


def contract_flag(val):
    if not isinstance(val, str) or val.strip() == "":
        return "Unknown", C_MID
    try:
        yr = int(str(val).strip()[:4])
        if yr <= 2026:
            return f"Exp {yr} ⚡", C_GOLD
        if yr == 2027:
            return f"Exp {yr}", C_AMBER
        return f"Exp {yr}", C_GREEN
    except Exception:
        return str(val)[:9], C_MID


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def build_cover(c: rl_canvas.Canvas, df: pd.DataFrame):
    """Page 1: dark cover with title and quick squad summary."""
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    set_dark_bg(fig, ax)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    # Background gradient strip
    grad = np.linspace(0, 1, 256).reshape(1, -1)
    ax.imshow(grad, extent=[0, 1, 0.78, 1], aspect="auto",
              cmap=LinearSegmentedColormap.from_list("g", [C_NAVY, C_DARK]),
              zorder=0)

    # Title block
    ax.text(0.5, 0.93, "FC HRADEC KRÁLOVÉ", ha="center", va="center",
            fontsize=28, fontweight="bold", color=C_WHITE, transform=ax.transAxes)
    ax.text(0.5, 0.875, "RECRUITMENT INTELLIGENCE REPORT", ha="center", va="center",
            fontsize=14, color=C_CYAN, fontweight="bold", transform=ax.transAxes)
    ax.text(0.5, 0.835, "Season 2025–2026  |  Jamestown Methodology  |  Budget ≤ €1,000,000",
            ha="center", va="center", fontsize=9, color=C_MID, transform=ax.transAxes)

    # Divider
    ax.axhline(0.82, color=C_BLUE, linewidth=2, xmin=0.05, xmax=0.95)

    # Squad gap summary — avg SQS rank per position as coloured bar
    squad_df = pd.read_excel(os.path.join(BASE_DIR, "hradec_player_tracking.xlsx"))
    IMPECT_MAP = {
        "GOALKEEPER":"GK","CENTRAL_DEFENDER":"CB","RIGHT_CENTRAL_DEFENDER":"CB",
        "LEFT_CENTRAL_DEFENDER":"CB","RIGHT_DEFENDER":"FB","LEFT_DEFENDER":"FB",
        "RIGHT_WINGBACK_DEFENDER":"FB","LEFT_WINGBACK_DEFENDER":"FB",
        "DEFENSE_MIDFIELD":"DM","CENTRAL_MIDFIELD":"CM","ATTACKING_MIDFIELD":"CM",
        "RIGHT_WINGER":"W","LEFT_WINGER":"W","CENTER_FORWARD":"FW","SECOND_STRIKER":"FW",
    }
    squad_df["pos_group"] = squad_df["position"].map(IMPECT_MAP).fillna("CM")
    squad_df["q"] = squad_df["IMPECT_SCORE_PACKING_pct"] * 100

    # Per-position starters quality from "All Targets" to get Hradec baseline
    all_t = df  # full targets df passed in
    pos_baselines = {}
    for pg in POSITION_ORDER:
        sub = squad_df[squad_df["pos_group"] == pg].nlargest(2, "playDuration")
        pos_baselines[pg] = sub["q"].mean() if len(sub) > 0 else 50.0

    ax.text(0.5, 0.79, "CURRENT SQUAD QUALITY BY POSITION", ha="center",
            fontsize=10, color=C_GOLD, fontweight="bold", transform=ax.transAxes)

    bar_y0 = 0.60; bar_h = 0.025; gap = 0.008
    for i, pg in enumerate(POSITION_ORDER):
        q = pos_baselines[pg]
        y = bar_y0 - i * (bar_h + gap)
        color = C_GREEN if q >= 70 else C_AMBER if q >= 40 else C_RED
        # Background bar
        ax.barh(y, 1.0, height=bar_h, left=0, color="#1E2A3A", align="center",
                transform=ax.transAxes)
        # Fill bar
        ax.barh(y, q / 100, height=bar_h, left=0, color=color, alpha=0.85,
                align="center", transform=ax.transAxes)
        # Labels
        ax.text(0.02, y, POSITION_LABELS[pg], ha="left", va="center",
                fontsize=8.5, color=C_LIGHT, fontweight="bold", transform=ax.transAxes)
        ax.text(q / 100 + 0.01, y, f"{q:.0f}th pctile", ha="left", va="center",
                fontsize=8, color=C_WHITE, transform=ax.transAxes)
        status = "STRENGTH" if q >= 70 else "NEEDS COVER" if q >= 40 else "PRIORITY NEED"
        s_color = C_GREEN if q >= 70 else C_AMBER if q >= 40 else C_RED
        ax.text(0.97, y, status, ha="right", va="center",
                fontsize=7.5, color=s_color, fontweight="bold", transform=ax.transAxes)

    # Stats footer
    n_upgrades = len(df[df["upgrade_flag"] == "CLEAR UPGRADE"])
    n_elite    = len(df[df["value_tier"] == "ELITE VALUE"])
    n_u28      = len(df[(df["Age"] <= 25)])

    stats = [
        ("551", "Candidates Analysed"),
        (str(n_upgrades), "Clear Upgrades Found"),
        (str(n_elite), "Elite Value Targets"),
        (str(n_u28), "Age ≤ 25 Available"),
    ]
    ax.axhline(0.34, color=C_BLUE, linewidth=1, xmin=0.05, xmax=0.95, alpha=0.5)
    for j, (num, label) in enumerate(stats):
        x = 0.125 + j * 0.25
        ax.text(x, 0.30, num, ha="center", va="center",
                fontsize=24, fontweight="bold", color=C_CYAN, transform=ax.transAxes)
        ax.text(x, 0.265, label, ha="center", va="center",
                fontsize=7.5, color=C_MID, transform=ax.transAxes)

    ax.text(0.5, 0.04,
            "Model: XGBoost OOF market value | SQS: position-weighted per-90 metrics\n"
            "League adjustment applied: CZ II ×0.82 | Slovakia ×0.78 | Slovakia II ×0.68",
            ha="center", va="center", fontsize=7, color=C_MID, transform=ax.transAxes,
            linespacing=1.6)

    buf = fig_to_bytes(fig)
    plt.close(fig)
    c.setPageSize((PW, PH))
    draw_image(c, buf, 0, 0, PW, PH)
    c.showPage()


def build_value_map(c: rl_canvas.Canvas, df: pd.DataFrame):
    """Page 2: SQS rank vs Market Value scatter — one panel per position."""
    fig = plt.figure(figsize=(11.69, 8.27))  # landscape
    fig.patch.set_facecolor(C_DARK)

    rows, cols = 2, 4
    gs = gridspec.GridSpec(rows, cols, figure=fig, hspace=0.45, wspace=0.35,
                           left=0.06, right=0.97, top=0.88, bottom=0.10)

    fig.text(0.5, 0.96, "VALUE MAP — SQS Rank vs Market Value", ha="center",
             fontsize=14, fontweight="bold", color=C_WHITE)
    fig.text(0.5, 0.925, "Bubble = Bloom Index size  |  Colour = Value Tier  |  Circle = Clear Upgrade for Hradec",
             ha="center", fontsize=8, color=C_MID)

    # Legend
    legend_els = [mpatches.Patch(color=v, label=k) for k, v in TIER_COLORS.items()
                  if k != "NO LISTED VALUE"]
    fig.legend(handles=legend_els, loc="lower center", ncol=len(legend_els),
               fontsize=7, facecolor=C_NAVY, edgecolor=C_MID,
               labelcolor=C_LIGHT, framealpha=0.9,
               bbox_to_anchor=(0.5, 0.01))

    with_mv = df[df["Market value"] > 0].copy()

    for idx, pg in enumerate(POSITION_ORDER):
        row, col = divmod(idx, cols)
        ax = fig.add_subplot(gs[row, col])
        ax.set_facecolor(C_NAVY)
        for spine in ax.spines.values():
            spine.set_edgecolor(C_MID)
        ax.tick_params(colors=C_MID, labelsize=6)

        sub = with_mv[with_mv["pos_group"] == pg]
        if len(sub) == 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=C_MID, transform=ax.transAxes)
            ax.set_title(POSITION_LABELS[pg], color=C_WHITE, fontsize=8, fontweight="bold")
            continue

        colors = sub["value_tier"].map(TIER_COLORS).fillna(C_MID)
        sizes  = (sub["bloom_index"].clip(0, 80) * 1.2 + 20).fillna(20)

        ax.scatter(sub["Market value"] / 1000, sub["sqs_rank"],
                   c=colors, s=sizes, alpha=0.75, edgecolors="none", zorder=3)

        # Highlight clear upgrades with ring
        upgrades = sub[sub["upgrade_flag"] == "CLEAR UPGRADE"]
        ax.scatter(upgrades["Market value"] / 1000, upgrades["sqs_rank"],
                   s=sizes[upgrades.index] + 60,
                   facecolors="none", edgecolors=C_GOLD, linewidths=1.2,
                   zorder=4)

        # Label top 3 by bloom index
        top3 = sub.nlargest(3, "bloom_index")
        for _, r in top3.iterrows():
            name = str(r["Player"]).split()[-1]  # surname only
            ax.annotate(name, (r["Market value"] / 1000, r["sqs_rank"]),
                        xytext=(4, 3), textcoords="offset points",
                        fontsize=5.5, color=C_WHITE,
                        path_effects=[pe.withStroke(linewidth=1.5, foreground=C_DARK)])

        ax.set_xlabel("Market Value (€k)", color=C_MID, fontsize=6)
        ax.set_ylabel("SQS Rank", color=C_MID, fontsize=6)
        ax.set_title(POSITION_LABELS[pg], color=C_WHITE, fontsize=8, fontweight="bold")
        ax.set_ylim(0, 105)
        ax.axhline(50, color=C_MID, linewidth=0.5, linestyle="--", alpha=0.4)
        ax.grid(True, color=C_MID, alpha=0.1, linewidth=0.5)

    # Hide last empty panel
    if len(POSITION_ORDER) < rows * cols:
        fig.add_subplot(gs[1, 3]).set_visible(False)

    buf = fig_to_bytes(fig, dpi=180)
    plt.close(fig)
    c.setPageSize((PH, PW))  # landscape
    draw_image(c, buf, 0, 0, PH, PW)
    c.showPage()


def build_position_page(c: rl_canvas.Canvas, df: pd.DataFrame,
                        pg: str, squad_df: pd.DataFrame):
    """One page per position: top 8 targets with stat bars and contract badges."""
    IMPECT_MAP = {
        "GOALKEEPER":"GK","CENTRAL_DEFENDER":"CB","RIGHT_CENTRAL_DEFENDER":"CB",
        "LEFT_CENTRAL_DEFENDER":"CB","RIGHT_DEFENDER":"FB","LEFT_DEFENDER":"FB",
        "RIGHT_WINGBACK_DEFENDER":"FB","LEFT_WINGBACK_DEFENDER":"FB",
        "DEFENSE_MIDFIELD":"DM","CENTRAL_MIDFIELD":"CM","ATTACKING_MIDFIELD":"CM",
        "RIGHT_WINGER":"W","LEFT_WINGER":"W","CENTER_FORWARD":"FW","SECOND_STRIKER":"FW",
    }
    squad_df = squad_df.copy()
    squad_df["pos_group"] = squad_df["position"].map(IMPECT_MAP).fillna("CM")

    sub = df[df["pos_group"] == pg].sort_values(
        "bloom_index", ascending=False, na_position="last"
    ).head(8).reset_index(drop=True)

    if len(sub) == 0:
        return

    # Hradec starter info
    starters = squad_df[squad_df["pos_group"] == pg].nlargest(2, "playDuration")
    starter_names = " / ".join(starters["commonname"].tolist()) if len(starters) > 0 else "—"
    starter_q = starters["IMPECT_SCORE_PACKING_pct"].mean() * 100 if len(starters) > 0 else 50.0

    # Key stat columns per position
    STAT_COLS = {
        "GK": ["Save rate, %", "Prevented goals per 90", "Exits per 90", "Accurate passes, %"],
        "CB": ["Defensive duels won, %", "Aerial duels won, %", "PAdj Interceptions", "Progressive passes per 90"],
        "FB": ["Defensive duels won, %", "Crosses per 90", "Accurate crosses, %", "Progressive runs per 90"],
        "DM": ["PAdj Interceptions", "Defensive duels won, %", "Progressive passes per 90", "Accurate passes, %"],
        "CM": ["Key passes per 90", "Progressive passes per 90", "xA per 90", "Goals per 90"],
        "W":  ["Goals per 90", "Assists per 90", "Dribbles per 90", "Touches in box per 90"],
        "FW": ["Goals per 90", "xG per 90", "Shots on target, %", "Touches in box per 90"],
    }
    stat_cols = [s for s in STAT_COLS.get(pg, []) if s in sub.columns]

    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor(C_DARK)

    # Header
    fig.text(0.5, 0.975, f"{POSITION_LABELS[pg].upper()} TARGETS", ha="center",
             fontsize=16, fontweight="bold", color=C_WHITE)
    fig.text(0.5, 0.955,
             f"Current starters: {starter_names}  (Impect quality: {starter_q:.0f}th pctile)  |  Budget ≤ €1M  |  Age ≤ 30",
             ha="center", fontsize=8, color=C_MID)

    # Horizontal rule
    fig.add_artist(plt.Line2D([0.04, 0.96], [0.945, 0.945],
                              transform=fig.transFigure, color=C_BLUE, linewidth=1.5))

    n_cards = len(sub)
    card_h  = 0.10
    card_gap = 0.007
    start_y  = 0.925

    for i, (_, row) in enumerate(sub.iterrows()):
        y_top = start_y - i * (card_h + card_gap)
        y_bot = y_top - card_h

        # Card background
        card_ax = fig.add_axes([0.03, y_bot, 0.94, card_h])
        card_ax.set_facecolor(C_NAVY)
        card_ax.set_xlim(0, 1); card_ax.set_ylim(0, 1); card_ax.axis("off")
        for spine in card_ax.spines.values():
            spine.set_visible(False)

        # Left colour stripe (tier colour)
        tier_col = TIER_COLORS.get(str(row.get("value_tier", "")), C_MID)
        card_ax.add_patch(Rectangle((0, 0), 0.008, 1, color=tier_col, transform=card_ax.transAxes))

        # Rank badge
        card_ax.text(0.022, 0.5, f"#{i+1}", ha="left", va="center",
                     fontsize=11, fontweight="bold", color=tier_col)

        # Player name
        card_ax.text(0.065, 0.72, str(row["Player"]), ha="left", va="center",
                     fontsize=10, fontweight="bold", color=C_WHITE)
        # Team + league
        card_ax.text(0.065, 0.35, f"{row['Team']}  ·  {row['league']}",
                     ha="left", va="center", fontsize=7.5, color=C_MID)

        # Age pill
        age_col = C_GREEN if row["Age"] <= 23 else C_AMBER if row["Age"] <= 27 else C_RED
        card_ax.add_patch(FancyBboxPatch((0.29, 0.25), 0.055, 0.50,
                          boxstyle="round,pad=0.02", color=age_col, alpha=0.25))
        card_ax.text(0.318, 0.5, f"Age {int(row['Age'])}", ha="center", va="center",
                     fontsize=7.5, color=age_col, fontweight="bold")

        # Contract flag
        cflag, ccol = contract_flag(row.get("Contract expires", ""))
        card_ax.add_patch(FancyBboxPatch((0.355, 0.25), 0.075, 0.50,
                          boxstyle="round,pad=0.02", color=ccol, alpha=0.25))
        card_ax.text(0.393, 0.5, cflag, ha="center", va="center",
                     fontsize=7, color=ccol, fontweight="bold")

        # Market value
        mv = f"€{int(row['Market value']):,}" if row.get("Market value", 0) > 0 else "No MV"
        card_ax.text(0.445, 0.5, mv, ha="left", va="center",
                     fontsize=8, color=C_LIGHT, fontweight="bold")

        # Bloom index badge
        bi = row.get("bloom_index", np.nan)
        bi_str = f"BI {bi:+.0f}" if pd.notna(bi) else "BI —"
        bi_col = tier_col
        card_ax.add_patch(FancyBboxPatch((0.535, 0.22), 0.07, 0.56,
                          boxstyle="round,pad=0.02", color=bi_col, alpha=0.2))
        card_ax.text(0.57, 0.5, bi_str, ha="center", va="center",
                     fontsize=8, color=bi_col, fontweight="bold")

        # Upgrade flag
        uf = str(row.get("upgrade_flag", ""))
        uf_col = C_GREEN if uf == "CLEAR UPGRADE" else C_AMBER if uf == "ROTATIONAL / COVER" else C_MID
        card_ax.text(0.615, 0.5, uf, ha="left", va="center",
                     fontsize=7, color=uf_col, fontweight="bold")

        # Stat mini-bars (right side)
        bar_x0 = 0.76; bar_w_max = 0.22; bar_h_each = 0.18; bar_gap = 0.04
        for j, sc in enumerate(stat_cols[:4]):
            bx = bar_x0
            by = 0.85 - j * (bar_h_each + bar_gap)
            val = float(row.get(sc, 0) or 0)
            # Normalise within position group
            col_vals = pd.to_numeric(df[df["pos_group"] == pg][sc], errors="coerce").dropna()
            pct = float(col_vals[col_vals <= val].count()) / max(len(col_vals), 1)
            bar_color = C_GREEN if pct >= 0.7 else C_AMBER if pct >= 0.4 else C_RED
            # Background
            card_ax.add_patch(Rectangle((bx, by - bar_h_each / 2), bar_w_max, bar_h_each,
                              color="#0D1117", alpha=0.6))
            # Fill
            card_ax.add_patch(Rectangle((bx, by - bar_h_each / 2), bar_w_max * pct, bar_h_each,
                              color=bar_color, alpha=0.8))
            # Label
            short = sc.replace(" per 90", "/90").replace("Accurate ", "Acc ").replace(", %", "%")[:18]
            card_ax.text(bx - 0.005, by, short, ha="right", va="center",
                         fontsize=5.5, color=C_MID)
            card_ax.text(bx + bar_w_max + 0.005, by, f"{val:.1f}",
                         ha="left", va="center", fontsize=5.5, color=C_LIGHT)

        # SQS rank arc (small semicircle gauge)
        sqs = row.get("sqs_rank", 50)
        gauge_ax = fig.add_axes([0.715, y_bot + 0.005, 0.038, card_h - 0.01])
        gauge_ax.set_facecolor("none")
        gauge_ax.set_xlim(-1.3, 1.3); gauge_ax.set_ylim(-0.2, 1.3)
        gauge_ax.axis("off")
        theta = np.linspace(np.pi, 0, 100)
        gauge_ax.plot(np.cos(theta), np.sin(theta), color=C_MID, lw=2.5, alpha=0.3)
        fill_theta = np.linspace(np.pi, np.pi - (sqs / 100) * np.pi, 100)
        fill_col = C_GREEN if sqs >= 70 else C_AMBER if sqs >= 40 else C_RED
        gauge_ax.plot(np.cos(fill_theta), np.sin(fill_theta), color=fill_col, lw=2.5)
        gauge_ax.text(0, 0.15, f"{sqs:.0f}", ha="center", va="center",
                      fontsize=7.5, fontweight="bold", color=fill_col)
        gauge_ax.text(0, -0.1, "SQS", ha="center", va="center",
                      fontsize=5, color=C_MID)

    # Footer
    fig.text(0.5, 0.012,
             "SQS = Statistical Quality Score (position-weighted per-90 metrics, league-adjusted)  "
             "·  BI = Bloom Index (SQS rank − Market Value rank)  ·  Bar = pctile within position pool",
             ha="center", fontsize=6, color=C_MID)

    buf = fig_to_bytes(fig, dpi=160)
    plt.close(fig)
    c.setPageSize((PW, PH))
    draw_image(c, buf, 0, 0, PW, PH)
    c.showPage()


def build_shortlist_summary(c: rl_canvas.Canvas, df: pd.DataFrame):
    """Final page: top 15 overall targets in one ranked table."""
    top = df[df["upgrade_flag"] == "CLEAR UPGRADE"].nlargest(15, "bloom_index").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    set_dark_bg(fig, ax)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    fig.text(0.5, 0.972, "PRIORITY SHORTLIST — TOP 15 CLEAR UPGRADES", ha="center",
             fontsize=14, fontweight="bold", color=C_WHITE)
    fig.text(0.5, 0.950, "Ranked by Bloom Index  ·  All positions  ·  Budget ≤ €1M",
             ha="center", fontsize=8.5, color=C_MID)
    fig.add_artist(plt.Line2D([0.04, 0.96], [0.940, 0.940],
                              transform=fig.transFigure, color=C_GOLD, linewidth=1.5))

    # Column headers
    headers = ["#", "Player", "Pos", "Team", "Age", "Mkt €", "Contract", "SQS", "BI", "Tier"]
    xs      = [0.03, 0.07, 0.25, 0.31, 0.52, 0.58, 0.67, 0.78, 0.85, 0.91]
    header_y = 0.920
    for hdr, x in zip(headers, xs):
        ax.text(x, header_y, hdr, ha="left", va="center",
                fontsize=7.5, color=C_GOLD, fontweight="bold", transform=ax.transAxes)

    row_h = 0.054
    for i, (_, row) in enumerate(top.iterrows()):
        y = 0.895 - i * row_h
        bg_col = "#1B2A4A" if i % 2 == 0 else "#151E2E"
        ax.add_patch(Rectangle((0.02, y - 0.025), 0.96, row_h - 0.003,
                               color=bg_col, transform=ax.transAxes, zorder=0))

        tier_col = TIER_COLORS.get(str(row.get("value_tier", "")), C_MID)
        ax.add_patch(Rectangle((0.02, y - 0.025), 0.006, row_h - 0.003,
                               color=tier_col, transform=ax.transAxes, zorder=1))

        mv = f"€{int(row['Market value']):,}" if row.get("Market value", 0) > 0 else "—"
        bi = f"{row['bloom_index']:+.0f}" if pd.notna(row.get("bloom_index")) else "—"
        cflag, ccol = contract_flag(row.get("Contract expires", ""))

        vals = [
            f"#{i+1}", str(row["Player"])[:22], str(row["pos_group"]),
            str(row["Team"])[:18], str(int(row["Age"])), mv, cflag,
            f"{row['sqs_rank']:.0f}", bi, str(row.get("value_tier", ""))[:12],
        ]
        colors_row = [
            C_MID, C_WHITE, C_CYAN, C_LIGHT, C_LIGHT, C_AMBER, ccol,
            C_GREEN if row["sqs_rank"] >= 70 else C_AMBER,
            tier_col, tier_col,
        ]
        for val, x, col in zip(vals, xs, colors_row):
            ax.text(x, y, val, ha="left", va="center",
                    fontsize=7.5, color=col, transform=ax.transAxes, fontweight=(
                        "bold" if val.startswith("#") or col == C_WHITE else "normal"
                    ))

    fig.text(0.5, 0.018,
             "⚡ Contract expiring 2026 = potential free/low-cost acquisition",
             ha="center", fontsize=7.5, color=C_GOLD)

    buf = fig_to_bytes(fig, dpi=160)
    plt.close(fig)
    c.setPageSize((PW, PH))
    draw_image(c, buf, 0, 0, PW, PH)
    c.showPage()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    print("Building FC Hradec Králové recruitment report ...")

    df = pd.read_excel(DATA_FILE, sheet_name="All Targets (ranked)")
    squad_df = pd.read_excel(os.path.join(BASE_DIR, "hradec_player_tracking.xlsx"))

    # Ensure numeric
    for col in ["Market value", "Age", "bloom_index", "sqs_rank", "Minutes played"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    c = rl_canvas.Canvas(OUTPUT_PDF, pagesize=A4)

    print("  [1/4] Cover page ...")
    build_cover(c, df)

    print("  [2/4] Value map ...")
    build_value_map(c, df)

    print("  [3/4] Position pages ...")
    for pg in POSITION_ORDER:
        print(f"         {pg} ...")
        build_position_page(c, df, pg, squad_df)

    print("  [4/4] Priority shortlist ...")
    build_shortlist_summary(c, df)

    c.save()
    print(f"\n  Done → {OUTPUT_PDF}")


if __name__ == "__main__":
    run()
