"""
FC Hradec Králové — Jamestown Recruitment Report
Clean white-background PDF, 10 pages.
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
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from io import BytesIO

warnings.filterwarnings("ignore")

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_FILE  = os.path.join(BASE_DIR, "hradec_recruitment_2526.xlsx")
SQUAD_FILE = os.path.join(BASE_DIR, "hradec_player_tracking.xlsx")
OUTPUT_PDF = os.path.join(BASE_DIR, "hradec_recruitment_report.pdf")

PW, PH = A4   # 595 x 842 pt

# Palette
BLACK  = "#111111"
GREY1  = "#444444"
GREY2  = "#888888"
GREY3  = "#CCCCCC"
GREY4  = "#F4F4F4"
WHITE  = "#FFFFFF"
BLUE   = "#1A56DB"
GREEN  = "#1E8449"
AMBER  = "#D4700A"
RED    = "#C0392B"

POSITION_ORDER  = ["GK", "CB", "FB", "DM", "CM", "W", "FW"]
POSITION_LABELS = {
    "GK": "Goalkeeper",  "CB": "Centre-Back",  "FB": "Full-Back",
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
    "Prevented goals per 90": "Prev Goals/90",
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

TOTAL_PAGES = 10


def fig_bytes(fig, dpi=150):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return ImageReader(buf)


def stamp(c, n):
    c.setFont("Helvetica", 7)
    c.setFillGray(0.5)
    c.drawString(36, 18, "FC Hradec Králové  ·  Jamestown Recruitment Model  ·  2025–2026")
    c.drawRightString(PW - 36, 18, f"{n} / {TOTAL_PAGES}")


def qual_col(q):
    return GREEN if q >= 70 else AMBER if q >= 40 else RED


def bi_col(bi):
    if pd.isna(bi): return GREY2
    if bi >= 20: return GREEN
    if bi >= 10: return BLUE
    if bi >= -10: return GREY1
    return RED


def contract_fmt(val):
    if not isinstance(val, str) or not val.strip():
        return "—", GREY2
    try:
        yr = int(str(val).strip()[:4])
        if yr <= 2026: return f"Jun {yr} ✦", AMBER
        if yr == 2027: return f"Jun {yr}", GREY1
        return f"Jun {yr}", GREEN
    except Exception:
        return str(val)[:9], GREY2


def upgrade_fmt(uf):
    if uf == "CLEAR UPGRADE":     return "↑ Upgrade", GREEN
    if uf == "ROTATIONAL / COVER": return "~ Cover",   BLUE
    return "Depth", GREY2


# ---------------------------------------------------------------------------
# Page 1 — Cover
# ---------------------------------------------------------------------------
def page_cover(c, df, squad_df):
    fig = plt.figure(figsize=(PW / 72, PH / 72))
    fig.patch.set_facecolor(WHITE)

    # Use a tight gridspec: header area + squad bars area + method area
    gs = fig.add_gridspec(3, 1, height_ratios=[2.2, 3.5, 2.8],
                          top=0.97, bottom=0.04, left=0.0, right=1.0, hspace=0)

    # --- Top panel: title + stats ---
    ax_top = fig.add_subplot(gs[0])
    ax_top.set_facecolor(WHITE); ax_top.axis("off")
    ax_top.set_xlim(0, 1); ax_top.set_ylim(0, 1)

    # Blue accent bar
    ax_top.add_patch(Rectangle((0, 0.88), 1, 0.12, color=BLUE,
                               transform=ax_top.transAxes, clip_on=False))
    ax_top.text(0.05, 0.94, "FC HRADEC KRÁLOVÉ — RECRUITMENT REPORT  2025–2026",
                fontsize=13, fontweight="bold", color=WHITE,
                transform=ax_top.transAxes, va="center")

    ax_top.text(0.05, 0.77, "Jamestown methodology  ·  Budget ≤ €1,000,000  ·  Age ≤ 30  ·  "
                "CZ II + Slovak leagues", fontsize=8.5, color=GREY1,
                transform=ax_top.transAxes, va="center")

    n_upgrades = int((df["upgrade_flag"] == "CLEAR UPGRADE").sum())
    n_elite    = int((df["bloom_index"] >= 30).sum())
    n_exp26    = int(df["Contract expires"].astype(str).str.startswith("2026").sum())
    stats = [("551", "Candidates analysed"), (str(n_upgrades), "Clear upgrades"),
             (str(n_elite), "Elite value targets"), (str(n_exp26), "Expiring 2026")]
    for j, (num, lbl) in enumerate(stats):
        x = 0.05 + j * 0.24
        ax_top.text(x, 0.50, num, fontsize=26, fontweight="bold", color=BLUE,
                    transform=ax_top.transAxes, va="center")
        ax_top.text(x, 0.28, lbl, fontsize=8, color=GREY2,
                    transform=ax_top.transAxes, va="center")

    ax_top.axhline(0.10, xmin=0.04, xmax=0.96, color=GREY3, linewidth=0.8)
    ax_top.text(0.05, 0.04, "CURRENT SQUAD — POSITION QUALITY",
                fontsize=9, fontweight="bold", color=BLACK,
                transform=ax_top.transAxes, va="center")

    # --- Middle panel: squad quality bars ---
    ax_bars = fig.add_subplot(gs[1])
    ax_bars.set_facecolor(WHITE)
    ax_bars.set_xlim(0, 100)
    ax_bars.set_ylim(-0.5, len(POSITION_ORDER) - 0.5)
    ax_bars.axis("off")

    squad_df = squad_df.copy()
    squad_df["pos_group"] = squad_df["position"].map(IMPECT_MAP).fillna("CM")
    squad_df["q"] = squad_df["IMPECT_SCORE_PACKING_pct"] * 100

    for i, pg in enumerate(POSITION_ORDER):
        sub = squad_df[squad_df["pos_group"] == pg].nlargest(2, "playDuration")
        q = sub["q"].mean() if len(sub) > 0 else 0
        names = "  /  ".join(sub["commonname"].tolist()) if len(sub) > 0 else "—"
        col = qual_col(q)
        y = len(POSITION_ORDER) - 1 - i

        # Position label (left)
        ax_bars.text(0, y, POSITION_LABELS[pg], fontsize=8.5, fontweight="bold",
                     color=BLACK, va="center", ha="left")

        # Bar background
        ax_bars.barh(y, 70, left=18, height=0.55, color=GREY4)
        # Bar fill
        ax_bars.barh(y, 70 * q / 100, left=18, height=0.55, color=col, alpha=0.85)

        # Starter names inside/beside bar
        ax_bars.text(19, y, names, fontsize=7, color=GREY1, va="center", ha="left",
                     clip_on=True)

        # Percentile label (right of bar)
        ax_bars.text(90, y, f"{q:.0f}th", fontsize=8.5, fontweight="bold",
                     color=col, va="center", ha="left")
        status = "STRENGTH" if q >= 70 else "NEEDS COVER" if q >= 40 else "PRIORITY"
        ax_bars.text(97, y, status, fontsize=7.5, color=col, va="center", ha="left")

    # Thin separator
    ax_bars.axhline(-0.5, color=GREY3, linewidth=0.8)

    # --- Bottom panel: methodology ---
    ax_meth = fig.add_subplot(gs[2])
    ax_meth.set_facecolor(WHITE); ax_meth.axis("off")
    ax_meth.set_xlim(0, 1); ax_meth.set_ylim(0, 1)

    ax_meth.text(0.05, 0.92, "METHODOLOGY", fontsize=9, fontweight="bold",
                 color=BLACK, transform=ax_meth.transAxes, va="top")
    method = (
        "Statistical Quality Score (SQS): position-weighted composite of per-90 Wyscout metrics, "
        "adjusted for league difficulty (CZ II ×0.82 · Slovakia ×0.78 · Slovakia II ×0.68).\n\n"
        "Bloom Index (BI): SQS percentile rank minus Market Value percentile rank within the "
        "same position pool. Positive = player performing above what the market prices in.\n\n"
        "Recruitment universe: CZ II + Slovak leagues, 2025–2026 only. Budget ≤ €1M, age ≤ 30, "
        "minimum 900 minutes played."
    )
    ax_meth.text(0.05, 0.80, method, fontsize=8, color=GREY1,
                 transform=ax_meth.transAxes, va="top", linespacing=1.7,
                 multialignment="left", wrap=True)

    img = fig_bytes(fig, dpi=160)
    plt.close(fig)
    c.setPageSize(A4)
    c.drawImage(img, 0, 0, PW, PH)
    stamp(c, 1)
    c.showPage()


# ---------------------------------------------------------------------------
# Page 2 — Value map (landscape)
# ---------------------------------------------------------------------------
def page_value_map(c, df):
    LW, LH = landscape(A4)  # 842 x 595

    fig = plt.figure(figsize=(LW / 72, LH / 72))
    fig.patch.set_facecolor(WHITE)

    fig.text(0.5, 0.96, "Value Map — SQS Rank vs Market Value",
             ha="center", fontsize=13, fontweight="bold", color=BLACK)
    fig.text(0.5, 0.925,
             "Each dot = one candidate.  Gold ring = clear upgrade on current Hradec starter.  "
             "Dot size = Bloom Index magnitude.",
             ha="center", fontsize=8, color=GREY2)

    # 2 rows × 4 cols, hide last cell
    axes = fig.subplots(2, 4, gridspec_kw=dict(
        hspace=0.50, wspace=0.30,
        left=0.06, right=0.97, top=0.88, bottom=0.10,
    ))

    with_mv = df[df["Market value"] > 0].copy()

    for idx, pg in enumerate(POSITION_ORDER):
        row, col = divmod(idx, 4)
        ax = axes[row][col]
        ax.set_facecolor(GREY4)
        for sp in ax.spines.values():
            sp.set_color(GREY3); sp.set_linewidth(0.6)
        ax.tick_params(colors=GREY2, labelsize=6)

        sub = with_mv[with_mv["pos_group"] == pg]

        if len(sub) == 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color=GREY2, transform=ax.transAxes, fontsize=8)
            ax.set_title(POSITION_LABELS[pg], fontsize=8, fontweight="bold",
                         color=BLACK, pad=5)
            continue

        bi_clipped = sub["bloom_index"].fillna(0).clip(0, 80)
        sizes  = bi_clipped * 1.5 + 18
        colors = [GREEN if u == "CLEAR UPGRADE"
                  else BLUE if u == "ROTATIONAL / COVER"
                  else GREY3
                  for u in sub["upgrade_flag"]]

        ax.scatter(sub["Market value"] / 1000, sub["sqs_rank"],
                   c=colors, s=sizes, alpha=0.75,
                   edgecolors="white", linewidths=0.4, zorder=3)

        upgrades = sub[sub["upgrade_flag"] == "CLEAR UPGRADE"]
        if len(upgrades):
            ax.scatter(upgrades["Market value"] / 1000, upgrades["sqs_rank"],
                       s=sizes[upgrades.index] + 55,
                       facecolors="none", edgecolors="#D4A017",
                       linewidths=1.4, zorder=4)

        for _, r in sub.nlargest(3, "bloom_index").iterrows():
            name = str(r["Player"]).split()[-1]
            ax.annotate(name, (r["Market value"] / 1000, r["sqs_rank"]),
                        xytext=(3, 3), textcoords="offset points",
                        fontsize=5, color=BLACK)

        ax.set_xlabel("Market Value (€k)", fontsize=6.5, color=GREY2)
        ax.set_ylabel("SQS Rank",          fontsize=6.5, color=GREY2)
        ax.set_ylim(0, 105)
        ax.axhline(50, color=GREY3, linewidth=0.6, linestyle="--")
        ax.grid(True, color=WHITE, linewidth=0.8)
        ax.set_title(POSITION_LABELS[pg], fontsize=8, fontweight="bold",
                     color=BLACK, pad=5)

    # Hide unused cell (row=1, col=3)
    axes[1][3].set_visible(False)

    leg = [
        mpatches.Patch(color=GREEN,  label="Clear upgrade"),
        mpatches.Patch(color=BLUE,   label="Rotational / cover"),
        mpatches.Patch(color=GREY3,  label="Depth"),
        mpatches.Patch(facecolor="none", edgecolor="#D4A017", label="Gold ring = upgrade"),
    ]
    fig.legend(handles=leg, loc="lower center", ncol=4, fontsize=7.5,
               facecolor=WHITE, edgecolor=GREY3, framealpha=1,
               bbox_to_anchor=(0.5, 0.01))

    img = fig_bytes(fig, dpi=160)
    plt.close(fig)
    c.setPageSize(landscape(A4))
    c.drawImage(img, 0, 0, LW, LH)
    # Footer in landscape
    c.setFont("Helvetica", 7); c.setFillGray(0.5)
    c.drawString(36, 18, "FC Hradec Králové  ·  Jamestown Recruitment Model  ·  2025–2026")
    c.drawRightString(LW - 36, 18, f"2 / {TOTAL_PAGES}")
    c.showPage()


# ---------------------------------------------------------------------------
# Pages 3–9 — Per-position
# ---------------------------------------------------------------------------
def page_position(c, df, squad_df, pg, page_num):
    squad_df = squad_df.copy()
    squad_df["pos_group"] = squad_df["position"].map(IMPECT_MAP).fillna("CM")
    squad_df["q"] = squad_df["IMPECT_SCORE_PACKING_pct"] * 100

    starters = squad_df[squad_df["pos_group"] == pg].nlargest(2, "playDuration")
    starter_names = "  /  ".join(starters["commonname"].tolist()) if len(starters) > 0 else "—"
    starter_q     = starters["q"].mean() if len(starters) > 0 else 50.0

    targets = df[df["pos_group"] == pg].sort_values(
        "bloom_index", ascending=False, na_position="last"
    ).head(8).reset_index(drop=True)

    stats = [s for s in STAT_COLS.get(pg, []) if s in df.columns]

    # Figure split: main table (top ~75%) + stats table (bottom ~20%)
    fig = plt.figure(figsize=(PW / 72, PH / 72))
    fig.patch.set_facecolor(WHITE)

    gs = fig.add_gridspec(2, 1, height_ratios=[5.5, 1.6],
                          top=0.96, bottom=0.04, left=0.0, right=1.0, hspace=0.0)
    ax  = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    for a in (ax, ax2):
        a.set_facecolor(WHITE); a.axis("off")
        a.set_xlim(0, 1); a.set_ylim(0, 1)

    # ---- Header ----
    ax.add_patch(Rectangle((0, 0.955), 1, 0.045, color=BLUE,
                            transform=ax.transAxes, clip_on=False))
    ax.text(0.04, 0.978, POSITION_LABELS[pg].upper(),
            fontsize=12, fontweight="bold", color=WHITE, transform=ax.transAxes, va="center")
    ax.text(0.96, 0.978, "FC HRADEC KRÁLOVÉ  ·  2025–2026",
            fontsize=8, color=WHITE, transform=ax.transAxes, va="center", ha="right")

    ax.text(0.04, 0.935,
            f"Current starters: {starter_names}   ·   Impect quality: {starter_q:.0f}th percentile",
            fontsize=8.5, color=GREY1, transform=ax.transAxes, va="center")

    # Column header row
    # Columns and their x positions (in axes fraction)
    COL = {
        "#":        0.03,
        "Player":   0.08,
        "Team":     0.34,
        "Age":      0.53,
        "Contract": 0.58,
        "Mkt Val":  0.67,
        "SQS":      0.77,
        "BI":       0.83,
        "Status":   0.89,
    }
    HDR_Y = 0.910
    for hdr, x in COL.items():
        ax.text(x, HDR_Y, hdr, fontsize=7.5, fontweight="bold",
                color=GREY2, transform=ax.transAxes, va="center")

    ax.axhline(0.900, xmin=0.03, xmax=0.97, color=GREY3, linewidth=0.5)

    if len(targets) == 0:
        ax.text(0.5, 0.5, "No candidates found.", ha="center", va="center",
                fontsize=10, color=GREY2, transform=ax.transAxes)
    else:
        row_h = 0.108
        y0    = 0.865

        for i, (_, row) in enumerate(targets.iterrows()):
            y   = y0 - i * row_h
            bg  = GREY4 if i % 2 == 0 else WHITE
            ax.add_patch(Rectangle((0.03, y - row_h * 0.46), 0.94, row_h * 0.92,
                                   color=bg, transform=ax.transAxes))

            uf = str(row.get("upgrade_flag", ""))
            strip_col = GREEN if uf == "CLEAR UPGRADE" else BLUE if uf == "ROTATIONAL / COVER" else GREY3
            ax.add_patch(Rectangle((0.03, y - row_h * 0.46), 0.005, row_h * 0.92,
                                   color=strip_col, transform=ax.transAxes))

            # Rank
            ax.text(COL["#"], y, f"{i+1}", fontsize=9, fontweight="bold",
                    color=GREY2, transform=ax.transAxes, va="center")

            # Player name + position code (2 lines)
            ax.text(COL["Player"], y + 0.022, str(row["Player"]),
                    fontsize=9, fontweight="bold", color=BLACK,
                    transform=ax.transAxes, va="center")
            ax.text(COL["Player"], y - 0.022, str(row.get("Position", "")),
                    fontsize=6.5, color=GREY2, transform=ax.transAxes, va="center")

            # Team + league (2 lines)
            ax.text(COL["Team"], y + 0.022, str(row["Team"]),
                    fontsize=8.5, color=BLACK, transform=ax.transAxes, va="center")
            ax.text(COL["Team"], y - 0.022, str(row["league"]),
                    fontsize=6.5, color=GREY2, transform=ax.transAxes, va="center")

            # Age
            age = int(row["Age"])
            age_col = GREEN if age <= 23 else GREY1 if age <= 27 else GREY2
            ax.text(COL["Age"], y, str(age), fontsize=9, color=age_col,
                    fontweight="bold", transform=ax.transAxes, va="center")

            # Contract
            cflag, ccol = contract_fmt(row.get("Contract expires", ""))
            ax.text(COL["Contract"], y, cflag, fontsize=7.5, color=ccol,
                    transform=ax.transAxes, va="center")

            # Market value
            mv = f"€{int(row['Market value']):,}" if row.get("Market value", 0) > 0 else "—"
            ax.text(COL["Mkt Val"], y, mv, fontsize=8, color=BLACK,
                    transform=ax.transAxes, va="center")

            # SQS
            sqs = float(row.get("sqs_rank", 0))
            sqs_col = GREEN if sqs >= 70 else AMBER if sqs >= 40 else RED
            ax.text(COL["SQS"], y, f"{sqs:.0f}", fontsize=9.5, fontweight="bold",
                    color=sqs_col, transform=ax.transAxes, va="center")

            # BI
            bi = row.get("bloom_index", np.nan)
            bi_str = f"{bi:+.0f}" if pd.notna(bi) else "—"
            ax.text(COL["BI"], y, bi_str, fontsize=9.5, fontweight="bold",
                    color=bi_col(bi), transform=ax.transAxes, va="center")

            # Status
            flag_txt, flag_col = upgrade_fmt(uf)
            ax.text(COL["Status"], y, flag_txt, fontsize=7.5, color=flag_col,
                    fontweight="bold", transform=ax.transAxes, va="center")

    # ---- Stats table (bottom panel) — coloured cell grid ----
    ax2.add_patch(Rectangle((0, 0), 1, 1, color=GREY4, transform=ax2.transAxes))

    if len(targets) > 0 and len(stats) > 0:
        n_players = len(targets)
        n_stats   = len(stats)

        label_w = 0.16   # left column for stat name
        data_w  = 1.0 - label_w - 0.03
        col_w   = data_w / n_players
        cell_h  = 0.82 / (n_stats + 1)  # +1 for header row

        header_y = 1.0 - cell_h * 0.5

        # Header: "KEY METRICS" label + player surnames
        ax2.text(0.02, header_y, "KEY METRICS",
                 fontsize=6.5, fontweight="bold", color=GREY2,
                 transform=ax2.transAxes, va="center")
        for ti, (_, row) in enumerate(targets.iterrows()):
            cx = label_w + ti * col_w + col_w / 2
            name_short = str(row["Player"]).split()[-1][:9]
            ax2.text(cx, header_y, name_short, fontsize=6, color=BLACK,
                     transform=ax2.transAxes, va="center", ha="center", fontweight="bold")

        # Separator line below header
        sep_y = 1.0 - cell_h
        ax2.axhline(sep_y, color=GREY3, linewidth=0.5)

        # Stat rows
        col_vals_cache = {}
        for sc in stats:
            col_vals_cache[sc] = pd.to_numeric(
                df[df["pos_group"] == pg][sc], errors="coerce").dropna()

        for si, sc in enumerate(stats):
            row_y_centre = sep_y - cell_h * (si + 0.5)
            short = STAT_SHORT.get(sc, sc[:16])

            # Stat label
            ax2.text(label_w - 0.01, row_y_centre, short, fontsize=6.5, color=GREY1,
                     transform=ax2.transAxes, va="center", ha="right")

            col_vals = col_vals_cache[sc]

            for ti, (_, row) in enumerate(targets.iterrows()):
                cx  = label_w + ti * col_w
                val = float(row.get(sc, 0) or 0)
                pct = float((col_vals <= val).sum()) / max(len(col_vals), 1)

                cell_col = GREEN if pct >= 0.7 else AMBER if pct >= 0.4 else RED
                pad = 0.003
                ax2.add_patch(Rectangle(
                    (cx + pad, row_y_centre - cell_h * 0.45),
                    col_w - pad * 2, cell_h * 0.85,
                    color=cell_col, alpha=0.18, transform=ax2.transAxes
                ))
                ax2.text(cx + col_w / 2, row_y_centre, f"{val:.1f}",
                         fontsize=6.5, color=BLACK,
                         transform=ax2.transAxes, va="center", ha="center")

    img = fig_bytes(fig, dpi=160)
    plt.close(fig)
    c.setPageSize(A4)
    c.drawImage(img, 0, 0, PW, PH)
    stamp(c, page_num)
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
    ax.add_patch(Rectangle((0, 0.956), 1, 0.044, color=BLUE,
                            transform=ax.transAxes, clip_on=False))
    ax.text(0.04, 0.978, "PRIORITY SHORTLIST",
            fontsize=12, fontweight="bold", color=WHITE, transform=ax.transAxes, va="center")
    ax.text(0.96, 0.978, "TOP 15 CLEAR UPGRADES  ·  ALL POSITIONS",
            fontsize=8, color=WHITE, transform=ax.transAxes, va="center", ha="right")

    ax.text(0.04, 0.934,
            "Ranked by Bloom Index  ·  All are clear upgrades on current starters  ·  Budget ≤ €1M",
            fontsize=8.5, color=GREY1, transform=ax.transAxes, va="center")
    ax.axhline(0.922, xmin=0.04, xmax=0.96, color=GREY3, linewidth=0.5)

    COLS = {
        "#":         0.04,
        "Player":    0.08,
        "Pos":       0.31,
        "Team":      0.36,
        "Age":       0.56,
        "Contract":  0.61,
        "Mkt Val":   0.70,
        "SQS":       0.79,
        "BI":        0.85,
        "vs Hradec": 0.91,
    }
    HDR_Y = 0.905
    for hdr, x in COLS.items():
        ax.text(x, HDR_Y, hdr, fontsize=7.5, fontweight="bold",
                color=GREY2, transform=ax.transAxes, va="center")
    ax.axhline(0.896, xmin=0.04, xmax=0.96, color=GREY3, linewidth=0.4)

    row_h = 0.054; y0 = 0.876

    for i, (_, row) in enumerate(top.iterrows()):
        y  = y0 - i * row_h
        bg = GREY4 if i % 2 == 0 else WHITE
        ax.add_patch(Rectangle((0.03, y - 0.023), 0.94, row_h - 0.005,
                               color=bg, transform=ax.transAxes))

        bi      = row.get("bloom_index", np.nan)
        sqs     = float(row.get("sqs_rank", 0))
        gap     = row.get("vs_hradec_gap", np.nan)
        mv      = f"€{int(row['Market value']):,}" if row.get("Market value", 0) > 0 else "—"
        bi_str  = f"{bi:+.0f}" if pd.notna(bi) else "—"
        gap_str = f"{gap:+.0f}" if pd.notna(gap) and gap != 0 else "—"
        cflag, ccol = contract_fmt(row.get("Contract expires", ""))
        strip_col   = GREEN if pd.notna(bi) and bi >= 20 else BLUE

        ax.add_patch(Rectangle((0.03, y - 0.023), 0.004, row_h - 0.005,
                               color=strip_col, transform=ax.transAxes))

        values = {
            "#":         (f"{i+1}",                  GREY2,     False),
            "Player":    (str(row["Player"])[:26],    BLACK,     True),
            "Pos":       (str(row["pos_group"]),      BLUE,      True),
            "Team":      (str(row["Team"])[:20],      GREY1,     False),
            "Age":       (str(int(row["Age"])),       GREEN if row["Age"] <= 23 else GREY1, False),
            "Contract":  (cflag,                      ccol,      False),
            "Mkt Val":   (mv,                         BLACK,     False),
            "SQS":       (f"{sqs:.0f}",               GREEN if sqs >= 70 else AMBER, True),
            "BI":        (bi_str,                     strip_col, True),
            "vs Hradec": (gap_str,                    GREEN if pd.notna(gap) and gap > 0 else RED, True),
        }
        for hdr, x in COLS.items():
            val, col, bold = values[hdr]
            ax.text(x, y, val, fontsize=8.5 if bold else 8,
                    color=col, fontweight="bold" if bold else "normal",
                    transform=ax.transAxes, va="center")

    ax.axhline(0.054, xmin=0.04, xmax=0.96, color=GREY3, linewidth=0.5)
    ax.text(0.04, 0.038,
            "vs Hradec = SQS rank gap vs current starter average at that position  ·  "
            "✦ = contract expiring 2026 (potential cut-price acquisition)",
            fontsize=7.5, color=GREY2, transform=ax.transAxes, va="center")

    img = fig_bytes(fig, dpi=160)
    plt.close(fig)
    c.setPageSize(A4)
    c.drawImage(img, 0, 0, PW, PH)
    stamp(c, page_num)
    c.showPage()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run():
    print("Building FC Hradec Králové recruitment report ...")

    df       = pd.read_excel(DATA_FILE, sheet_name="All Targets (ranked)")
    squad_df = pd.read_excel(SQUAD_FILE)

    for col in ["Market value", "Age", "bloom_index", "sqs_rank",
                "Minutes played", "vs_hradec_gap"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    squad_df["playDuration"] = pd.to_numeric(
        squad_df["playDuration"], errors="coerce").fillna(0)
    squad_df["IMPECT_SCORE_PACKING_pct"] = pd.to_numeric(
        squad_df["IMPECT_SCORE_PACKING_pct"], errors="coerce").fillna(0)

    c = rl_canvas.Canvas(OUTPUT_PDF, pagesize=A4)
    c.setTitle("FC Hradec Králové — Recruitment Report 2025-26")

    print("  [1] Cover ...")
    page_cover(c, df, squad_df)

    print("  [2] Value map ...")
    page_value_map(c, df)

    print("  [3–9] Position pages ...")
    for i, pg in enumerate(POSITION_ORDER):
        print(f"        {pg} ...")
        page_position(c, df, squad_df, pg, page_num=3 + i)

    print("  [10] Shortlist ...")
    page_shortlist(c, df, page_num=10)

    c.save()
    print(f"\n  Done → {OUTPUT_PDF}")


if __name__ == "__main__":
    run()
