"""
FC Hradec Králové — Jamestown Recruitment Workbook
Produces a clean, filterable Excel file with conditional formatting.

Sheets:
  0. README         — methodology and column guide
  1. Priority List  — top 30 clear upgrades, all positions
  2. All Targets    — full 551-player list, filterable
  3-9. GK/CB/FB/DM/CM/W/FW — per-position tabs
  10. Squad         — current Hradec squad quality
"""

import os, warnings
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.formatting.rule import (
    ColorScaleRule, CellIsRule, FormulaRule, DataBarRule
)
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.filters import AutoFilter

warnings.filterwarnings("ignore")

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_FILE  = os.path.join(BASE_DIR, "hradec_recruitment_2526.xlsx")
SQUAD_FILE = os.path.join(BASE_DIR, "hradec_player_tracking.xlsx")
OUT_FILE   = os.path.join(BASE_DIR, "hradec_recruitment_model.xlsx")

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

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
BLUE_DARK   = "1A56DB"
BLUE_LIGHT  = "D6E4FF"
GREEN_DARK  = "1E8449"
GREEN_LIGHT = "D5F5E3"
AMBER_DARK  = "D4700A"
AMBER_LIGHT = "FDEBD0"
RED_DARK    = "C0392B"
RED_LIGHT   = "FADBD8"
GREY_HEADER = "F2F2F2"
WHITE       = "FFFFFF"
BLACK       = "111111"

def fill(hex_col):
    return PatternFill("solid", fgColor=hex_col)

def font(bold=False, color=BLACK, size=10, italic=False):
    return Font(bold=bold, color=color, size=size, italic=italic,
                name="Calibri")

def align(h="left", v="center", wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

def thin_border():
    s = Side(style="thin", color="CCCCCC")
    return Border(bottom=s)

def header_style(ws, row, bg=BLUE_DARK, fg=WHITE, size=10):
    for cell in ws[row]:
        if cell.value is not None:
            cell.fill    = fill(bg)
            cell.font    = font(bold=True, color=fg, size=size)
            cell.alignment = align("center")
            cell.border  = thin_border()

def set_col_widths(ws, widths: dict):
    """widths = {col_letter: width}"""
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

def add_autofilter(ws, header_row=1):
    ws.auto_filter.ref = ws.dimensions

def freeze(ws, cell="B2"):
    ws.freeze_panes = cell

# ---------------------------------------------------------------------------
# Column definitions for main data tables
# ---------------------------------------------------------------------------
MAIN_COLS = [
    ("Player",           "Player",             22),
    ("Team",             "Team",               20),
    ("league",           "League",             14),
    ("pos_group",        "Pos",                 6),
    ("Position",         "Wyscout Pos",        12),
    ("Age",              "Age",                 6),
    ("Contract expires", "Contract",           11),
    ("Market value",     "Mkt Val (€)",        12),
    ("model_value",      "Model Val (€)",      13),
    ("sqs_rank",         "SQS Rank",           10),
    ("bloom_index",      "Bloom Index",        12),
    ("upgrade_flag",     "Status",             16),
    ("vs_hradec_gap",    "vs Hradec",          11),
    ("Minutes played",   "Minutes",            10),
    ("Goals per 90",         "Goals/90",        9),
    ("xG per 90",            "xG/90",           8),
    ("Assists per 90",       "Assists/90",      9),
    ("xA per 90",            "xA/90",           8),
    ("Progressive passes per 90", "Prog Pass/90", 12),
    ("Progressive runs per 90",   "Prog Run/90",  11),
    ("Touches in box per 90",     "Box Touch/90", 12),
    ("Dribbles per 90",           "Dribbles/90",  11),
    ("Successful dribbles, %",    "Drib Succ %",  11),
    ("Defensive duels won, %",    "Def Duel %",   10),
    ("Aerial duels won, %",       "Aerial %",      9),
    ("PAdj Interceptions",        "Interceptions", 13),
    ("Key passes per 90",         "Key Pass/90",   11),
    ("Save rate, %",              "Save %",         8),
    ("Prevented goals per 90",    "Prev Goals/90", 13),
]

# Columns that get conditional formatting
CF_COLS = {
    "SQS Rank":     ("databar", 0, 100),
    "Bloom Index":  ("3color",  -50, 0, 50),
    "vs Hradec":    ("3color",  -30, 0, 30),
    "Age":          ("reverse3color", 18, 25, 30),
    "Mkt Val (€)":  ("databar", 0, 1000000),
}

# Status colours
STATUS_FILLS = {
    "CLEAR UPGRADE":      (GREEN_LIGHT, GREEN_DARK),
    "ROTATIONAL / COVER": (AMBER_LIGHT, AMBER_DARK),
    "DEPTH":              (GREY_HEADER, "666666"),
}


def build_df(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Select and rename columns for output."""
    src_cols = [c[0] for c in MAIN_COLS]
    hdr_cols = [c[1] for c in MAIN_COLS]
    existing = [c for c in src_cols if c in df_raw.columns]
    out = df_raw[existing].copy()
    rename = {c[0]: c[1] for c in MAIN_COLS if c[0] in out.columns}
    out = out.rename(columns=rename)
    # Ensure all header cols present
    for h in hdr_cols:
        if h not in out.columns:
            out[h] = ""
    return out[hdr_cols]


def write_data_sheet(ws, df: pd.DataFrame, title: str, subtitle: str = ""):
    """Write a formatted data table to a worksheet."""
    # Title row
    ws.append([title])
    ws.merge_cells(start_row=1, start_column=1,
                   end_row=1, end_column=len(df.columns))
    tc = ws["A1"]
    tc.fill  = fill(BLUE_DARK)
    tc.font  = font(bold=True, color=WHITE, size=13)
    tc.alignment = align("left", "center")
    ws.row_dimensions[1].height = 24

    if subtitle:
        ws.append([subtitle])
        ws.merge_cells(start_row=2, start_column=1,
                       end_row=2, end_column=len(df.columns))
        sc = ws["A2"]
        sc.fill = fill(BLUE_LIGHT)
        sc.font = font(color=BLUE_DARK, size=9)
        sc.alignment = align("left", "center")
        ws.row_dimensions[2].height = 16
        header_row = 3
    else:
        header_row = 2

    # Header
    ws.append(list(df.columns))
    header_style(ws, header_row)
    ws.row_dimensions[header_row].height = 18

    # Data rows
    for r_idx, row in enumerate(df.itertuples(index=False), start=header_row + 1):
        ws.append(list(row))
        ws.row_dimensions[r_idx].height = 16

        # Alternate row fill
        bg = "FAFAFA" if r_idx % 2 == 0 else WHITE
        for cell in ws[r_idx]:
            cell.fill = fill(bg)
            cell.font = font(size=9)
            cell.alignment = align("left", "center")
            cell.border = thin_border()

        # Status column colour
        status_col_idx = list(df.columns).index("Status") + 1 if "Status" in df.columns else None
        if status_col_idx:
            status_val = ws.cell(r_idx, status_col_idx).value
            if status_val in STATUS_FILLS:
                bg_s, fg_s = STATUS_FILLS[status_val]
                c = ws.cell(r_idx, status_col_idx)
                c.fill = fill(bg_s)
                c.font = font(bold=True, color=fg_s, size=9)
                c.alignment = align("center", "center")

        # SQS Rank inline colour
        sqs_col_idx = list(df.columns).index("SQS Rank") + 1 if "SQS Rank" in df.columns else None
        if sqs_col_idx:
            sqs_val = ws.cell(r_idx, sqs_col_idx).value
            try:
                sqs_val = float(sqs_val)
                if sqs_val >= 70:
                    ws.cell(r_idx, sqs_col_idx).font = font(bold=True, color=GREEN_DARK, size=10)
                elif sqs_val >= 40:
                    ws.cell(r_idx, sqs_col_idx).font = font(bold=True, color=AMBER_DARK, size=10)
                else:
                    ws.cell(r_idx, sqs_col_idx).font = font(bold=True, color=RED_DARK, size=10)
            except (ValueError, TypeError):
                pass

        # Bloom Index inline colour
        bi_col_idx = list(df.columns).index("Bloom Index") + 1 if "Bloom Index" in df.columns else None
        if bi_col_idx:
            bi_val = ws.cell(r_idx, bi_col_idx).value
            try:
                bi_val = float(bi_val)
                col = GREEN_DARK if bi_val >= 20 else BLUE_DARK if bi_val >= 10 else (
                    RED_DARK if bi_val < -10 else "555555")
                ws.cell(r_idx, bi_col_idx).font = font(bold=True, color=col, size=10)
            except (ValueError, TypeError):
                pass

    # Column widths
    width_map = {c[1]: c[2] for c in MAIN_COLS}
    for col_idx, col_name in enumerate(df.columns, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width_map.get(col_name, 12)

    # Autofilter on header row
    ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(df.columns))}{header_row}"
    ws.freeze_panes = f"A{header_row + 1}"

    # Conditional formatting: data bars for Bloom Index
    if "Bloom Index" in df.columns:
        bi_col_letter = get_column_letter(list(df.columns).index("Bloom Index") + 1)
        data_start = header_row + 1
        data_end   = header_row + len(df)
        bi_range   = f"{bi_col_letter}{data_start}:{bi_col_letter}{data_end}"
        ws.conditional_formatting.add(
            bi_range,
            ColorScaleRule(
                start_type="num", start_value=-50, start_color="C0392B",
                mid_type="num",   mid_value=0,     mid_color="FFFFFF",
                end_type="num",   end_value=50,     end_color="1E8449",
            )
        )

    return header_row


# ---------------------------------------------------------------------------
# README sheet
# ---------------------------------------------------------------------------
def build_readme(ws):
    ws.title = "README"
    ws.sheet_view.showGridLines = False

    def write(row, col, text, bold=False, size=10, color=BLACK,
              bg=None, merge_to=None, wrap=False, italic=False):
        c = ws.cell(row=row, column=col, value=text)
        c.font = font(bold=bold, size=size, color=color, italic=italic)
        c.alignment = align("left", "top", wrap=wrap)
        if bg:
            c.fill = fill(bg)
        if merge_to:
            ws.merge_cells(start_row=row, start_column=col,
                           end_row=row, end_column=merge_to)
        return c

    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 72

    # Title
    write(1, 1, "FC HRADEC KRÁLOVÉ — RECRUITMENT MODEL  2025–2026",
          bold=True, size=16, color=WHITE, bg=BLUE_DARK, merge_to=20)
    ws.row_dimensions[1].height = 32
    write(2, 1, "Jamestown Analytics methodology  ·  CZ II + Slovak leagues  ·  Budget ≤ €1,000,000  ·  Age ≤ 30",
          size=9, color=BLUE_DARK, bg=BLUE_LIGHT, merge_to=20)
    ws.row_dimensions[2].height = 16

    sections = [
        (4, "WORKBOOK STRUCTURE", None, True, 12, WHITE, BLUE_DARK),
        (5, "Sheet", "Contents", True, 9, WHITE, "444444"),
        (6,  "Priority List",  "Top 30 clear upgrades across all positions, ranked by Bloom Index. Start here.", False, 9, BLACK, None),
        (7,  "All Targets",    "All 551 candidates with filters. Use the dropdown on any column to filter by position, league, status etc.", False, 9, BLACK, None),
        (8,  "GK / CB / FB…",  "One tab per position. Pre-filtered to that role, sorted by Bloom Index.", False, 9, BLACK, None),
        (9,  "Squad",          "Current FC Hradec Králové squad with Impect quality scores and position gaps.", False, 9, BLACK, None),
        (10, "README",         "This sheet.", False, 9, BLACK, None),

        (12, "COLUMN GUIDE", None, True, 12, WHITE, BLUE_DARK),
        (13, "Column", "What it means", True, 9, WHITE, "444444"),
        (14, "SQS Rank",       "Statistical Quality Score rank (0–100 percentile). Built from position-weighted per-90 Wyscout metrics, adjusted for league difficulty. Higher = better. Green ≥70, Amber ≥40, Red <40.", False, 9, BLACK, None),
        (15, "Bloom Index",    "SQS rank minus Market Value rank within the same position pool. POSITIVE = player performing above what the market prices in (undervalued). Negative = overvalued. The core Jamestown signal.", False, 9, BLACK, None),
        (16, "vs Hradec",      "SQS rank gap vs current Hradec starters at that position. +30 means 30 percentile points better than who you're currently playing.", False, 9, BLACK, None),
        (17, "Status",         "CLEAR UPGRADE = SQS rank >10pts above Hradec starter average. ROTATIONAL / COVER = better than weakest option. DEPTH = below current starters.", False, 9, BLACK, None),
        (18, "Model Val",      "What the XGBoost model estimates the player should be worth based on stats alone (5-fold out-of-fold prediction — not in-sample). Compare to Mkt Val to find mispricing.", False, 9, BLACK, None),
        (19, "Contract",       "Contract expiry from Wyscout. Players expiring Jun 2026 (✦) can often be acquired cheaply or pre-contracted. Treat as a floor — negotiate from there.", False, 9, BLACK, None),
        (20, "Age",            "Green ≤23 (development asset), standard 24–27, grey 28+ (short resale window).", False, 9, BLACK, None),

        (22, "METHODOLOGY", None, True, 12, WHITE, BLUE_DARK),
        (23, "Step 1",  "Load all Market I files (CZ II, Slovakia, Slovakia II — 2025-26 season). Apply: ≥900 minutes, age ≤30, market value ≤€1M.", False, 9, BLACK, None),
        (24, "Step 2",  "Compute SQS per position using weighted per-90 metrics. League multiplier applied (CZ II ×0.82 · Slovakia ×0.78 · Slovakia II ×0.68) so a stat in CZ II counts more than the same stat in Slovakia II.", False, 9, BLACK, None),
        (25, "Step 3",  "Train XGBoost to predict log(market value) from stats. Use 5-fold out-of-fold predictions to avoid in-sample inflation. OOF R² is low (0.07–0.18) — expected, because market value in lower leagues is reputation-driven not stats-driven. That gap is the opportunity.", False, 9, BLACK, None),
        (26, "Step 4",  "Bloom Index = SQS percentile rank − Market Value percentile rank. Rank both within the same position group so GKs compare only to other GKs.", False, 9, BLACK, None),
        (27, "Step 5",  "Compare each candidate's SQS rank to the current Hradec starters at that position (from hradec_player_tracking.xlsx, Impect scores). CLEAR UPGRADE if SQS rank > starter average + 10 points.", False, 9, BLACK, None),

        (29, "HOW TO USE", None, True, 12, WHITE, BLUE_DARK),
        (30, "Quick start",    "Go to Priority List → sort by Bloom Index (descending) → filter Status = CLEAR UPGRADE → filter Age ≤ 26 for younger targets. These are your highest-value targets.", False, 9, BLACK, None),
        (31, "Filter by pos",  "Go to any position tab (e.g. CB) → already filtered. Sort by SQS Rank to see top performers regardless of market value.", False, 9, BLACK, None),
        (32, "Expiring deals", "In All Targets → filter Contract = 'Jun 2026 ✦' → these players can often be signed on a pre-contract or at a significant discount.", False, 9, BLACK, None),
        (33, "Colour coding",  "Status cells: Green = clear upgrade · Amber = rotational/cover · Grey = depth.\nSQS Rank: Green ≥70 · Amber ≥40 · Red <40.\nBloom Index: Green/white/red scale (green = undervalued).", False, 9, BLACK, None),
    ]

    for item in sections:
        row, col_b, col_c, bold, size, color, bg = item
        ws.row_dimensions[row].height = 15 if size <= 9 else 22

        if col_c is None:
            # Section header — spans both cols
            c = write(row, 2, col_b, bold=bold, size=size, color=color,
                      bg=bg or WHITE, merge_to=20)
        else:
            write(row, 2, col_b, bold=bold, size=size, color=color,
                  bg=bg or (GREY_HEADER if bold else WHITE))
            write(row, 3, col_c, bold=False, size=size, color=color,
                  bg=WHITE, wrap=True)
            ws.row_dimensions[row].height = 28 if size <= 9 and len(str(col_c)) > 80 else 15

    ws.sheet_view.showGridLines = False


# ---------------------------------------------------------------------------
# Squad sheet
# ---------------------------------------------------------------------------
def build_squad_sheet(ws, squad_df):
    ws.title = "Squad"
    ws.sheet_view.showGridLines = False

    squad_df = squad_df.copy()
    squad_df["pos_group"] = squad_df["position"].map(IMPECT_MAP).fillna("CM")
    squad_df["Quality (Impect %)"] = (squad_df["IMPECT_SCORE_PACKING_pct"] * 100).round(1)

    out_cols = {
        "commonname":        "Player",
        "position":          "Impect Position",
        "pos_group":         "Pos Group",
        "age":               "Age",
        "playDuration":      "Minutes",
        "Quality (Impect %)":"Quality (Impect %)",
        "IMPECT_SCORE_PACKING_pct":   "Overall Pctile",
        "OFFENSIVE_IMPECT_SCORE_PACKING_pct": "Offensive Pctile",
        "DEFENSIVE_IMPECT_SCORE_PACKING_pct": "Defensive Pctile",
        "PROGRESSION_SCORE_PACKING_pct":      "Progression Pctile",
    }
    existing = {k: v for k, v in out_cols.items() if k in squad_df.columns}
    df = squad_df[list(existing.keys())].rename(columns=existing).copy()
    for col in df.select_dtypes(include="float").columns:
        df[col] = df[col].round(3)
    df = df.sort_values("Minutes", ascending=False)

    # Title
    ws.append(["FC Hradec Králové — Current Squad Quality"])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(df.columns))
    ws["A1"].fill = fill(BLUE_DARK)
    ws["A1"].font = font(bold=True, color=WHITE, size=13)
    ws["A1"].alignment = align("left", "center")
    ws.row_dimensions[1].height = 24

    ws.append(["Scores from Impect API  ·  Czech top-flight league percentile ranks  ·  Higher = better"])
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(df.columns))
    ws["A2"].fill = fill(BLUE_LIGHT)
    ws["A2"].font = font(color=BLUE_DARK, size=9)
    ws["A2"].alignment = align("left", "center")
    ws.row_dimensions[2].height = 15

    ws.append(list(df.columns))
    header_style(ws, 3)
    ws.row_dimensions[3].height = 18

    widths = {"A": 22, "B": 25, "C": 10, "D": 6, "E": 10, "F": 18,
              "G": 15, "H": 17, "I": 17, "J": 18}

    for r_idx, row in enumerate(df.itertuples(index=False), start=4):
        ws.append(list(row))
        ws.row_dimensions[r_idx].height = 15
        bg = "FAFAFA" if r_idx % 2 == 0 else WHITE
        for cell in ws[r_idx]:
            cell.fill = fill(bg)
            cell.font = font(size=9)
            cell.alignment = align("left", "center")
            cell.border = thin_border()

        # Colour quality column
        q_col = list(df.columns).index("Quality (Impect %)") + 1
        q_val = ws.cell(r_idx, q_col).value
        try:
            q_val = float(q_val)
            col = GREEN_DARK if q_val >= 70 else AMBER_DARK if q_val >= 40 else RED_DARK
            ws.cell(r_idx, q_col).font = font(bold=True, color=col, size=10)
        except (ValueError, TypeError):
            pass

    for col_letter, w in widths.items():
        ws.column_dimensions[col_letter].width = w

    ws.auto_filter.ref = f"A3:{get_column_letter(len(df.columns))}3"
    ws.freeze_panes = "A4"

    # Conditional formatting on percentile columns
    pct_cols = ["Overall Pctile", "Offensive Pctile", "Defensive Pctile", "Progression Pctile"]
    for col_name in pct_cols:
        if col_name in df.columns:
            col_letter = get_column_letter(list(df.columns).index(col_name) + 1)
            ws.conditional_formatting.add(
                f"{col_letter}4:{col_letter}{3 + len(df)}",
                ColorScaleRule(
                    start_type="num", start_value=0,   start_color="C0392B",
                    mid_type="num",   mid_value=0.5,   mid_color="FFFFFF",
                    end_type="num",   end_value=1.0,   end_color="1E8449",
                )
            )

    ws.sheet_view.showGridLines = False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run():
    print("Building FC Hradec Králové recruitment workbook ...")

    df_raw   = pd.read_excel(DATA_FILE, sheet_name="All Targets (ranked)")
    squad_df = pd.read_excel(SQUAD_FILE)

    for col in ["Market value", "Age", "bloom_index", "sqs_rank",
                "Minutes played", "vs_hradec_gap", "model_value"]:
        if col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce")

    squad_df["playDuration"] = pd.to_numeric(squad_df["playDuration"], errors="coerce").fillna(0)
    squad_df["IMPECT_SCORE_PACKING_pct"] = pd.to_numeric(
        squad_df["IMPECT_SCORE_PACKING_pct"], errors="coerce").fillna(0)

    wb = Workbook()

    # ---- README ----
    print("  README ...")
    ws_readme = wb.active
    build_readme(ws_readme)

    # ---- Priority List ----
    print("  Priority list ...")
    ws_pri = wb.create_sheet("Priority List")
    ws_pri.sheet_view.showGridLines = False
    priority = df_raw[df_raw["upgrade_flag"] == "CLEAR UPGRADE"].nlargest(30, "bloom_index")
    df_pri = build_df(priority)
    # Round floats
    for col in df_pri.select_dtypes(include="float").columns:
        df_pri[col] = df_pri[col].round(2)
    write_data_sheet(ws_pri, df_pri,
                     "PRIORITY LIST — Top 30 Clear Upgrades",
                     "Ranked by Bloom Index  ·  All are clear upgrades on current Hradec starters  ·  Budget ≤ €1M")

    # ---- All Targets ----
    print("  All targets ...")
    ws_all = wb.create_sheet("All Targets")
    ws_all.sheet_view.showGridLines = False
    all_t = df_raw.sort_values("bloom_index", ascending=False, na_position="last")
    df_all = build_df(all_t)
    for col in df_all.select_dtypes(include="float").columns:
        df_all[col] = df_all[col].round(2)
    write_data_sheet(ws_all, df_all,
                     "ALL TARGETS — 551 Candidates",
                     "Use column filters to narrow by position, league, age, status · CZ II + Slovak leagues · 2025–2026")

    # ---- Per-position sheets ----
    for pg in POSITION_ORDER:
        print(f"  {pg} ...")
        ws_pg = wb.create_sheet(pg)
        ws_pg.sheet_view.showGridLines = False
        sub = df_raw[df_raw["pos_group"] == pg].sort_values(
            "bloom_index", ascending=False, na_position="last")
        df_pg = build_df(sub)
        for col in df_pg.select_dtypes(include="float").columns:
            df_pg[col] = df_pg[col].round(2)
        write_data_sheet(ws_pg, df_pg,
                         f"{POSITION_LABELS[pg].upper()} TARGETS",
                         f"Sorted by Bloom Index  ·  All {pg} candidates in recruitment universe")

    # ---- Squad ----
    print("  Squad ...")
    ws_squad = wb.create_sheet("Squad")
    build_squad_sheet(ws_squad, squad_df)

    # Tab colours
    tab_colors = {
        "README":       "1A56DB",
        "Priority List":"1E8449",
        "All Targets":  "444444",
        "GK": "2980B9", "CB": "2980B9", "FB": "2980B9",
        "DM": "2980B9", "CM": "2980B9", "W":  "2980B9", "FW": "2980B9",
        "Squad": "D4700A",
    }
    for sheet_name, color in tab_colors.items():
        if sheet_name in wb.sheetnames:
            wb[sheet_name].sheet_properties.tabColor = color

    wb.save(OUT_FILE)
    print(f"\n  Done → {OUT_FILE}")
    print(f"  Sheets: README · Priority List · All Targets · "
          + " · ".join(POSITION_ORDER) + " · Squad")


if __name__ == "__main__":
    run()
