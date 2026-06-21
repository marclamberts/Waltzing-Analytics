#!/usr/bin/env python3
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".python_packages"))
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / "tmp" / "matplotlib"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from mplsoccer import Pitch, VerticalPitch
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from restart_visuals import build_restart_assets
from coaching_restart_visuals import build_coaching_restart_assets


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "HNL"
OUT_DIR = ROOT / "output" / "pdf"
ASSET_DIR = OUT_DIR / "varazdin_shooting_mplsoccer_assets"
TMP_DIR = ROOT / "tmp" / "pdfs"
PDF_PATH = OUT_DIR / "NK_Varazdin_opposition_report_shooting.pdf"

TEAM = "Varaždin"
TEAM_SHORT = "VARAŽDIN"
ANALYST_TEAM = "FC HRADEC KRÁLOVÉ"

NAVY = "#071522"
NAVY_2 = "#0D2232"
PANEL = "#112A3C"
WHITE = "#F4F7F9"
MUTED = "#9BB0BF"
CYAN = "#35D0D6"
PINK = "#FF4F8B"
AMBER = "#FFBD59"
GREEN = "#55D187"
RED = "#FF6474"
GRID = "#315064"

XT_GRID = [
    [0.0064, 0.0078, 0.0084, 0.0096, 0.0113, 0.0141, 0.0169, 0.0212, 0.0276, 0.0349, 0.0379, 0.0212],
    [0.0075, 0.0088, 0.0099, 0.0117, 0.0143, 0.0176, 0.0212, 0.0265, 0.0349, 0.0440, 0.0604, 0.1081],
    [0.0089, 0.0100, 0.0114, 0.0135, 0.0169, 0.0212, 0.0265, 0.0349, 0.0440, 0.0604, 0.1081, 0.2575],
    [0.0094, 0.0106, 0.0122, 0.0148, 0.0187, 0.0240, 0.0308, 0.0407, 0.0560, 0.0812, 0.1479, 0.2575],
    [0.0094, 0.0106, 0.0122, 0.0148, 0.0187, 0.0240, 0.0308, 0.0407, 0.0560, 0.0812, 0.1479, 0.2575],
    [0.0089, 0.0100, 0.0114, 0.0135, 0.0169, 0.0212, 0.0265, 0.0349, 0.0440, 0.0604, 0.1081, 0.2575],
    [0.0075, 0.0088, 0.0099, 0.0117, 0.0143, 0.0176, 0.0212, 0.0265, 0.0349, 0.0440, 0.0604, 0.1081],
    [0.0064, 0.0078, 0.0084, 0.0096, 0.0113, 0.0141, 0.0169, 0.0212, 0.0276, 0.0349, 0.0379, 0.0212],
]

W, H = 1600, 900
FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def load_data():
    matches = json.loads((DATA_DIR / "matches.json").read_text())
    match_by_id = {m["match_id"]: m for m in matches}
    events_by_id = {}
    for p in sorted(DATA_DIR.glob("*.json")):
        if p.name == "matches.json":
            continue
        try:
            match_id = int(p.stem.rsplit("_", 1)[-1])
        except ValueError:
            continue
        events_by_id[match_id] = json.loads(p.read_text())
    return matches, match_by_id, events_by_id


def team_name(m, side):
    return m[f"{side}_team"][f"{side}_team_name"]


def opponent(m, team=TEAM):
    return team_name(m, "away") if team_name(m, "home") == team else team_name(m, "home")


def result_string(m, team=TEAM):
    home = team_name(m, "home") == team
    gf = m["home_score"] if home else m["away_score"]
    ga = m["away_score"] if home else m["home_score"]
    return f"{gf}-{ga}"


def shot_rows(match_id, events, match):
    rows = []
    for e in events:
        if e.get("type", {}).get("name") != "Shot":
            continue
        s = e.get("shot", {})
        loc = e.get("location", [None, None])
        rows.append({
            "match_id": match_id,
            "date": match["match_date"],
            "team": e.get("team", {}).get("name"),
            "player": e.get("player", {}).get("name", "Unknown"),
            "minute": e.get("minute", 0),
            "second": e.get("second", 0),
            "xg": float(s.get("statsbomb_xg", 0) or 0),
            "outcome": s.get("outcome", {}).get("name", ""),
            "shot_type": s.get("type", {}).get("name", "Unknown"),
            "play_pattern": e.get("play_pattern", {}).get("name", "Unknown"),
            "x": loc[0] if len(loc) > 0 else None,
            "y": loc[1] if len(loc) > 1 else None,
        })
    return rows


def compile_stats(matches, events_by_id):
    all_shots = []
    valid_matches = [
        m for m in matches
        if m["match_id"] in events_by_id
        and m.get("home_score") is not None
        and m.get("away_score") is not None
    ]
    for m in valid_matches:
        all_shots.extend(shot_rows(m["match_id"], events_by_id[m["match_id"]], m))

    teams = sorted({team_name(m, "home") for m in valid_matches} | {team_name(m, "away") for m in valid_matches})
    stats = {t: {"games": 0, "points": 0, "gf": 0, "ga": 0, "shots": 0, "xg": 0, "shots_against": 0, "xga": 0} for t in teams}
    for m in valid_matches:
        h, a = team_name(m, "home"), team_name(m, "away")
        hs, aas = m["home_score"], m["away_score"]
        stats[h]["games"] += 1
        stats[a]["games"] += 1
        stats[h]["gf"] += hs
        stats[h]["ga"] += aas
        stats[a]["gf"] += aas
        stats[a]["ga"] += hs
        if hs > aas:
            stats[h]["points"] += 3
        elif hs < aas:
            stats[a]["points"] += 3
        else:
            stats[h]["points"] += 1
            stats[a]["points"] += 1
        match_shots = [s for s in all_shots if s["match_id"] == m["match_id"]]
        for s in match_shots:
            t = s["team"]
            o = a if t == h else h
            stats[t]["shots"] += 1
            stats[t]["xg"] += s["xg"]
            stats[o]["shots_against"] += 1
            stats[o]["xga"] += s["xg"]
    for t, d in stats.items():
        g = max(d["games"], 1)
        d.update({
            "ppg": d["points"] / g,
            "shots90": d["shots"] / g,
            "xg90": d["xg"] / g,
            "xga90": d["xga"] / g,
            "goals90": d["gf"] / g,
        })
    league_xg = sum(d["xg90"] for d in stats.values()) / len(stats)
    league_shots = sum(d["shots90"] for d in stats.values()) / len(stats)
    for d in stats.values():
        d["shooting_index"] = 100 * (0.7 * d["xg90"] / league_xg + 0.3 * d["shots90"] / league_shots)
    return valid_matches, all_shots, stats


def base_image():
    return Image.new("RGB", (W, H), NAVY)


def header(draw, kicker, title, subtitle=None):
    draw.text((80, 45), kicker.upper(), fill=CYAN, font=font(22, True))
    draw.text((80, 88), title, fill=WHITE, font=font(48, True))
    if subtitle:
        draw.text((82, 151), subtitle, fill=MUTED, font=font(22))
    draw.line((80, 198, W - 80, 198), fill=GRID, width=2)


def footer(draw, source="StatsBomb event data | 2025/26 1. HNL"):
    draw.line((80, H - 55, W - 80, H - 55), fill=GRID, width=2)
    draw.text((80, H - 42), source, fill=MUTED, font=font(16))
    draw.text((W - 80, H - 42), "FC HRADEC KRÁLOVÉ | OPPOSITION ANALYSIS", fill=MUTED, font=font(16), anchor="ra")


def rounded_panel(draw, box, fill=PANEL, outline=None, radius=20):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2 if outline else 1)


def draw_pitch(draw, box):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=12, fill="#0B4B49", outline=WHITE, width=3)
    # Attacking half only: x 60-120, y 0-80.
    penalty_x = x0 + (102 - 60) / 60 * (x1 - x0)
    six_x = x0 + (114 - 60) / 60 * (x1 - x0)
    draw.rectangle((penalty_x, y0 + (18 / 80) * (y1 - y0), x1, y0 + (62 / 80) * (y1 - y0)), outline=WHITE, width=3)
    draw.rectangle((six_x, y0 + (30 / 80) * (y1 - y0), x1, y0 + (50 / 80) * (y1 - y0)), outline=WHITE, width=3)
    goal_h = (8 / 80) * (y1 - y0)
    draw.rectangle((x1, (y0 + y1) / 2 - goal_h / 2, x1 + 12, (y0 + y1) / 2 + goal_h / 2), outline=WHITE, width=3)
    spot_x = x0 + (108 - 60) / 60 * (x1 - x0)
    draw.ellipse((spot_x - 4, (y0 + y1) / 2 - 4, spot_x + 4, (y0 + y1) / 2 + 4), fill=WHITE)
    return box


def pitch_xy(x, y, box):
    x0, y0, x1, y1 = box
    xx = x0 + ((max(60, min(120, x)) - 60) / 60) * (x1 - x0)
    yy = y0 + (max(0, min(80, y)) / 80) * (y1 - y0)
    return xx, yy


def save_shotmap(path, shots, title, subtitle):
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.055, 0.17, 0.70, 0.60])
    pitch = VerticalPitch(
        pitch_type="statsbomb", half=True, pitch_color="#0B4B49",
        line_color=WHITE, linewidth=1.5, goal_type="box", line_zorder=2
    )
    pitch.draw(ax=ax)
    for s in sorted(shots, key=lambda z: z["xg"]):
        if s["x"] is None:
            continue
        goal = s["outcome"] == "Goal"
        pitch.scatter(
            s["x"], s["y"], ax=ax,
            s=75 + 1250 * s["xg"],
            color=PINK if goal else CYAN,
            edgecolors=WHITE if goal else NAVY_2,
            linewidth=1.6, alpha=0.94, zorder=4
        )
    fig.text(0.05, 0.91, "SHOOTING | MPLSOCCER SHOT MAP", color=CYAN, fontsize=15, fontweight="bold")
    fig.text(0.05, 0.845, title, color=WHITE, fontsize=29, fontweight="bold")
    fig.text(0.05, 0.805, subtitle, color=MUTED, fontsize=14)
    fig.add_artist(Line2D([0.05, 0.95], [0.775, 0.775], transform=fig.transFigure, color=GRID, linewidth=1))
    goals = sum(s["outcome"] == "Goal" for s in shots)
    xg = sum(s["xg"] for s in shots)
    cards = [("SHOTS", len(shots), CYAN), ("xG", f"{xg:.2f}", AMBER), ("GOALS", goals, PINK), ("xG / SHOT", f"{xg/max(len(shots),1):.2f}", WHITE)]
    for i, (label, value, color) in enumerate(cards):
        card = fig.add_axes([0.79, 0.66 - i * 0.14, 0.16, 0.105])
        card.set_facecolor(PANEL)
        card.set_xticks([]); card.set_yticks([])
        for spine in card.spines.values():
            spine.set_visible(False)
        card.text(0.08, 0.72, label, transform=card.transAxes, color=MUTED, fontsize=11, fontweight="bold")
        card.text(0.92, 0.22, str(value), transform=card.transAxes, color=color, fontsize=24, fontweight="bold", ha="right")
    fig.text(0.795, 0.115, "●", color=CYAN, fontsize=19)
    fig.text(0.82, 0.12, "SHOT", color=MUTED, fontsize=11, fontweight="bold")
    fig.text(0.875, 0.115, "●", color=PINK, fontsize=19)
    fig.text(0.90, 0.12, "GOAL", color=MUTED, fontsize=11, fontweight="bold")
    fig.add_artist(Line2D([0.05, 0.95], [0.075, 0.075], transform=fig.transFigure, color=GRID, linewidth=1))
    fig.text(0.05, 0.04, "StatsBomb event data | 2025/26 1. HNL", color=MUTED, fontsize=10)
    fig.text(0.95, 0.04, "FC HRADEC KRÁLOVÉ | OPPOSITION ANALYSIS", color=MUTED, fontsize=10, ha="right")
    fig.savefig(path, facecolor=NAVY, dpi=100)
    plt.close(fig)


def save_flowmap(path, recent, all_shots):
    img = base_image()
    d = ImageDraw.Draw(img)
    header(d, "SHOOTING | RECENT FORM", "xG flow - last three matches", "Cumulative expected goals; goals marked by diamonds")
    colors = [CYAN, PINK, AMBER]
    chart = (120, 250, 1480, 730)
    x0, y0, x1, y1 = chart
    max_xg = 0
    series = []
    for m in recent:
        shots = [s for s in all_shots if s["match_id"] == m["match_id"] and s["team"] == TEAM]
        max_xg = max(max_xg, sum(s["xg"] for s in shots))
        series.append(shots)
    ymax = max(2.0, math.ceil(max_xg * 2) / 2)
    for minute in range(0, 91, 15):
        xx = x0 + minute / 90 * (x1 - x0)
        d.line((xx, y0, xx, y1), fill=GRID, width=1)
        d.text((xx, y1 + 15), str(minute), fill=MUTED, font=font(16), anchor="ma")
    for i in range(5):
        val = ymax * i / 4
        yy = y1 - i / 4 * (y1 - y0)
        d.line((x0, yy, x1, yy), fill=GRID, width=1)
        d.text((x0 - 18, yy), f"{val:.1f}", fill=MUTED, font=font(16), anchor="rm")
    for idx, (m, shots) in enumerate(zip(recent, series)):
        color = colors[idx]
        cum = 0
        pts = [(x0, y1)]
        for s in sorted(shots, key=lambda z: (z["minute"], z["second"])):
            xx = x0 + min(s["minute"], 90) / 90 * (x1 - x0)
            yy0 = y1 - cum / ymax * (y1 - y0)
            pts.append((xx, yy0))
            cum += s["xg"]
            yy = y1 - cum / ymax * (y1 - y0)
            pts.append((xx, yy))
            if s["outcome"] == "Goal":
                r = 9
                d.polygon([(xx, yy-r), (xx+r, yy), (xx, yy+r), (xx-r, yy)], fill=color, outline=WHITE)
        pts.append((x1, y1 - cum / ymax * (y1 - y0)))
        d.line(pts, fill=color, width=5, joint="curve")
        label = f"{m['match_date'][5:]}  {opponent(m)}  {result_string(m)}  |  {cum:.2f} xG"
        d.line((150 + idx * 470, 790, 195 + idx * 470, 790), fill=color, width=6)
        d.text((210 + idx * 470, 790), label, fill=WHITE, font=font(18, True), anchor="lm")
    footer(d)
    img.save(path, quality=95)


def save_match_flow(path, match, all_shots):
    opponent_name = opponent(match)
    match_shots = [s for s in all_shots if s["match_id"] == match["match_id"]]
    team_shots = [s for s in match_shots if s["team"] == TEAM]
    opp_shots = [s for s in match_shots if s["team"] == opponent_name]
    max_xg = max(sum(s["xg"] for s in team_shots), sum(s["xg"] for s in opp_shots), 1.0)
    ymax = math.ceil((max_xg + 0.2) * 2) / 2

    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.075, 0.20, 0.85, 0.55], facecolor=NAVY)
    for shots, color, label in [(team_shots, CYAN, TEAM), (opp_shots, PINK, opponent_name)]:
        shots = sorted(shots, key=lambda z: (z["minute"], z["second"]))
        minutes, values = [0], [0]
        cumulative = 0
        goal_points = []
        for s in shots:
            minute = min(s["minute"] + s["second"] / 60, 95)
            minutes.extend([minute, minute])
            values.extend([cumulative, cumulative + s["xg"]])
            cumulative += s["xg"]
            if s["outcome"] == "Goal":
                goal_points.append((minute, cumulative))
        minutes.append(95)
        values.append(cumulative)
        ax.plot(minutes, values, color=color, linewidth=3.2, label=f"{label}  {cumulative:.2f} xG")
        if goal_points:
            ax.scatter(
                [p[0] for p in goal_points], [p[1] for p in goal_points],
                marker="D", s=90, color=color, edgecolor=WHITE, linewidth=1.2, zorder=5
            )
    ax.set_xlim(0, 95); ax.set_ylim(0, ymax)
    ax.set_xticks(range(0, 91, 15))
    ax.tick_params(colors=MUTED, labelsize=11, length=0)
    ax.grid(color=GRID, linewidth=0.7, alpha=0.8)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xlabel("MATCH MINUTE", color=WHITE, fontsize=12, fontweight="bold", labelpad=14)
    ax.set_ylabel("CUMULATIVE xG", color=WHITE, fontsize=12, fontweight="bold", labelpad=14)
    legend = ax.legend(loc="upper left", frameon=False, ncol=2, fontsize=13)
    for text in legend.get_texts():
        text.set_color(WHITE)
    venue = "HOME" if team_name(match, "home") == TEAM else "AWAY"
    fig.text(0.05, 0.91, "SHOOTING | INDIVIDUAL MATCH xG FLOW", color=CYAN, fontsize=15, fontweight="bold")
    fig.text(0.05, 0.845, f"Varaždin {result_string(match)} {opponent_name}", color=WHITE, fontsize=29, fontweight="bold")
    fig.text(0.05, 0.805, f"{match['match_date']} | {venue} | goals marked by diamonds", color=MUTED, fontsize=14)
    fig.add_artist(Line2D([0.05, 0.95], [0.775, 0.775], transform=fig.transFigure, color=GRID, linewidth=1))
    fig.add_artist(Line2D([0.05, 0.95], [0.075, 0.075], transform=fig.transFigure, color=GRID, linewidth=1))
    fig.text(0.05, 0.04, "StatsBomb event data | 2025/26 1. HNL", color=MUTED, fontsize=10)
    fig.text(0.95, 0.04, "FC HRADEC KRÁLOVÉ | OPPOSITION ANALYSIS", color=MUTED, fontsize=10, ha="right")
    fig.savefig(path, facecolor=NAVY, dpi=100)
    plt.close(fig)


def team_passes(events):
    rows = []
    for e in events:
        if e.get("team", {}).get("name") != TEAM or e.get("type", {}).get("name") != "Pass":
            continue
        p = e.get("pass", {})
        loc = e.get("location", [None, None])
        end = p.get("end_location", [None, None])
        if len(loc) < 2 or len(end) < 2:
            continue
        rows.append({
            "player": e.get("player", {}).get("name", "Unknown"),
            "recipient": p.get("recipient", {}).get("name"),
            "x": loc[0], "y": loc[1], "end_x": end[0], "end_y": end[1],
            "minute": e.get("minute", 0),
            "complete": "outcome" not in p,
            "cross": bool(p.get("cross")),
            "play_pattern": e.get("play_pattern", {}).get("name", ""),
            "pass_type": p.get("type", {}).get("name", ""),
            "cluster_id": p.get("pass_cluster_id"),
            "cluster_label": p.get("pass_cluster_label", ""),
        })
        rows[-1]["xt"] = max(0, xt_at(end[0], end[1]) - xt_at(loc[0], loc[1])) if "outcome" not in p else 0
    return rows


def xt_at(x, y):
    col = min(11, max(0, int(x / 120 * 12)))
    row = min(7, max(0, int(y / 80 * 8)))
    return XT_GRID[row][col]


def plot_page_frame(fig, kicker, title, subtitle):
    fig.text(0.05, 0.91, kicker, color=CYAN, fontsize=15, fontweight="bold")
    fig.text(0.05, 0.845, title, color=WHITE, fontsize=29, fontweight="bold")
    fig.text(0.05, 0.805, subtitle, color=MUTED, fontsize=14)
    fig.add_artist(Line2D([0.05, 0.95], [0.775, 0.775], transform=fig.transFigure, color=GRID, linewidth=1))
    fig.add_artist(Line2D([0.05, 0.95], [0.075, 0.075], transform=fig.transFigure, color=GRID, linewidth=1))
    fig.text(0.05, 0.04, "StatsBomb event data | 2025/26 1. HNL", color=MUTED, fontsize=10)
    fig.text(0.95, 0.04, "FC HRADEC KRÁLOVÉ | OPPOSITION ANALYSIS", color=MUTED, fontsize=10, ha="right")


def match_subtitle(match, suffix):
    venue = "HOME" if team_name(match, "home") == TEAM else "AWAY"
    return f"{match['match_date']} | {venue} | {suffix}"


def save_pass_network(path, match, events):
    passes = team_passes(events)
    sub_minutes = [
        e.get("minute", 100) for e in events
        if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Substitution"
    ]
    cutoff = min(sub_minutes) if sub_minutes else 95
    completed = [p for p in passes if p["complete"] and p["recipient"] and p["minute"] <= cutoff]
    positions = defaultdict(list)
    for p in completed:
        positions[p["player"]].append((p["x"], p["y"]))
        positions[p["recipient"]].append((p["end_x"], p["end_y"]))
    avg = {
        player: (sum(x for x, _ in pts)/len(pts), sum(y for _, y in pts)/len(pts), len(pts))
        for player, pts in positions.items() if len(pts) >= 2
    }
    links = defaultdict(int)
    for p in completed:
        if p["player"] in avg and p["recipient"] in avg:
            links[tuple(sorted((p["player"], p["recipient"])))] += 1
    link_values = sorted(links.values(), reverse=True)
    threshold = max(2, link_values[min(13, len(link_values)-1)]) if link_values else 2

    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.08, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    for (a, b), count in links.items():
        if count < threshold:
            continue
        x1, y1, _ = avg[a]; x2, y2, _ = avg[b]
        pitch.lines(x1, y1, x2, y2, ax=ax, color=CYAN, lw=1.2 + count*0.65, alpha=min(0.9, 0.25+count/10), zorder=2)
    max_touches = max((v[2] for v in avg.values()), default=1)
    for player, (x, y, touches) in avg.items():
        size = 280 + 700 * touches / max_touches
        pitch.scatter(x, y, ax=ax, s=size, color=PINK, edgecolors=WHITE, linewidth=1.5, zorder=4)
        surname = player.split()[-1]
        ax.text(x, y, surname, color=WHITE, fontsize=8.5, fontweight="bold", ha="center", va="center", zorder=5)
    plot_page_frame(
        fig, "PASSING | INDIVIDUAL MATCH PASS NETWORK",
        f"Varaždin {result_string(match)} {opponent(match)}",
        match_subtitle(match, f"completed passes before first substitution ({cutoff}')")
    )
    fig.text(0.84, 0.66, f"{len(completed)}", color=CYAN, fontsize=30, fontweight="bold")
    fig.text(0.84, 0.625, "COMPLETED PASSES", color=MUTED, fontsize=11, fontweight="bold")
    fig.text(0.84, 0.52, f"{len(avg)}", color=PINK, fontsize=30, fontweight="bold")
    fig.text(0.84, 0.485, "NETWORK PLAYERS", color=MUTED, fontsize=11, fontweight="bold")
    fig.text(0.84, 0.38, f"≥ {threshold}", color=AMBER, fontsize=30, fontweight="bold")
    fig.text(0.84, 0.345, "PASSES PER LINK", color=MUTED, fontsize=11, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100)
    plt.close(fig)


def save_pass_clusters(path, match, events):
    passes = [p for p in team_passes(events) if p["complete"] and p["cluster_id"] is not None]
    grouped = defaultdict(list)
    for p in passes:
        grouped[p["cluster_id"]].append(p)
    clusters = sorted(grouped.items(), key=lambda z: len(z[1]), reverse=True)[:6]
    colors = [CYAN, PINK, AMBER, GREEN, RED, "#A78BFA"]

    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.72, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    for idx, (_, rows) in enumerate(clusters):
        color = colors[idx]
        for p in rows:
            pitch.lines(p["x"], p["y"], p["end_x"], p["end_y"], ax=ax, color=color, lw=1.1, alpha=0.14, zorder=2)
        sx = sum(p["x"] for p in rows)/len(rows); sy = sum(p["y"] for p in rows)/len(rows)
        ex = sum(p["end_x"] for p in rows)/len(rows); ey = sum(p["end_y"] for p in rows)/len(rows)
        pitch.arrows(sx, sy, ex, ey, ax=ax, color=color, width=3.2, headwidth=6, headlength=6, zorder=4)
        ax.text(sx, sy, str(idx+1), color=NAVY, fontsize=10, fontweight="bold", ha="center", va="center",
                bbox=dict(boxstyle="circle,pad=0.3", facecolor=color, edgecolor=WHITE), zorder=5)
    plot_page_frame(
        fig, "PASSING | INDIVIDUAL MATCH PASS CLUSTERS",
        f"Varaždin {result_string(match)} {opponent(match)}",
        match_subtitle(match, "top six StatsBomb pass clusters | completed passes")
    )
    fig.text(0.81, 0.70, "TOP PASS PATTERNS", color=WHITE, fontsize=15, fontweight="bold")
    for idx, (_, rows) in enumerate(clusters):
        label = rows[0]["cluster_label"].replace("Attacking third - ", "").replace("Defensive third - ", "").replace("Middle third - ", "")
        if len(label) > 31:
            label = label[:29] + "..."
        y = 0.63 - idx*0.085
        fig.text(0.81, y, f"{idx+1}", color=colors[idx], fontsize=17, fontweight="bold")
        fig.text(0.835, y+0.003, f"{len(rows)} passes", color=WHITE, fontsize=11, fontweight="bold")
        fig.text(0.835, y-0.025, label, color=MUTED, fontsize=9)
    fig.savefig(path, facecolor=NAVY, dpi=100)
    plt.close(fig)


def save_crosses(path, match, events):
    crosses = [
        p for p in team_passes(events)
        if p["cross"]
        and p["play_pattern"] not in {"From Corner", "From Free Kick"}
        and p["pass_type"] not in {"Corner", "Free Kick"}
    ]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    for p in crosses:
        color = GREEN if p["complete"] else PINK
        pitch.arrows(p["x"], p["y"], p["end_x"], p["end_y"], ax=ax, color=color, alpha=0.9,
                     width=2.1, headwidth=5, headlength=5, zorder=3)
        pitch.scatter(p["x"], p["y"], ax=ax, s=38, color=color, edgecolors=WHITE, linewidth=0.7, zorder=4)
    complete = sum(p["complete"] for p in crosses)
    left = sum(p["y"] < 40 for p in crosses)
    right = len(crosses) - left
    plot_page_frame(
        fig, "PASSING | OPEN-PLAY CROSSES",
        f"Varaždin {result_string(match)} {opponent(match)}",
        match_subtitle(match, "corners and free kicks excluded")
    )
    stats_cards = [
        ("CROSSES", len(crosses), CYAN),
        ("COMPLETED", complete, GREEN),
        ("SUCCESS", f"{complete/max(len(crosses),1)*100:.0f}%", AMBER),
        ("LEFT / RIGHT", f"{left} / {right}", WHITE),
    ]
    for i, (label, value, color) in enumerate(stats_cards):
        fig.text(0.84, 0.68-i*0.13, str(value), color=color, fontsize=28, fontweight="bold")
        fig.text(0.84, 0.645-i*0.13, label, color=MUTED, fontsize=10.5, fontweight="bold")
    fig.text(0.84, 0.14, "GREEN = COMPLETED", color=GREEN, fontsize=10, fontweight="bold")
    fig.text(0.84, 0.11, "PINK = INCOMPLETE", color=PINK, fontsize=10, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100)
    plt.close(fig)


def save_pass_selection(path, match, events, kind):
    passes = team_passes(events)
    if kind == "final_third":
        selected = [p for p in passes if p["complete"] and p["x"] < 80 <= p["end_x"]]
        kicker = "PASSING | FINAL-THIRD ENTRIES"
        suffix = "completed passes crossing the x=80 line"
        stat_label = "ENTRIES"
        color = CYAN
    elif kind == "penalty_area":
        selected = [
            p for p in passes if p["complete"]
            and p["end_x"] >= 102 and 18 <= p["end_y"] <= 62
            and not (p["x"] >= 102 and 18 <= p["y"] <= 62)
        ]
        kicker = "PASSING | PENALTY-AREA ENTRIES"
        suffix = "completed passes entering the penalty area"
        stat_label = "BOX ENTRIES"
        color = PINK
    else:
        def goal_dist(x, y):
            return math.hypot(120-x, 40-y)
        def is_progressive(p):
            if not p["complete"]:
                return False
            start, end = goal_dist(p["x"], p["y"]), goal_dist(p["end_x"], p["end_y"])
            reduction = start-end
            threshold = 30 if p["x"] < 60 and p["end_x"] < 60 else 15 if p["x"] < 60 <= p["end_x"] else 10
            return reduction >= threshold
        selected = [p for p in passes if is_progressive(p)]
        kicker = "PASSING | PROGRESSIVE PASSES"
        suffix = "goal-distance reduction: 30/15/10 StatsBomb pitch units by starting zone"
        stat_label = "PROGRESSIVE"
        color = AMBER

    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    for p in selected:
        pitch.arrows(p["x"], p["y"], p["end_x"], p["end_y"], ax=ax, color=color, alpha=0.78,
                     width=1.8, headwidth=4.5, headlength=4.5, zorder=3)
    if kind == "final_third":
        ax.axvline(80, color=WHITE, linestyle="--", linewidth=1.2, alpha=0.8)
    elif kind == "penalty_area":
        ax.fill_between([102, 120], 18, 62, color=PINK, alpha=0.08)
    plot_page_frame(
        fig, kicker, f"Varaždin {result_string(match)} {opponent(match)}",
        match_subtitle(match, suffix)
    )
    players = defaultdict(int)
    for p in selected:
        players[p["player"]] += 1
    leaders = sorted(players.items(), key=lambda z: z[1], reverse=True)[:4]
    fig.text(0.84, 0.68, str(len(selected)), color=color, fontsize=30, fontweight="bold")
    fig.text(0.84, 0.645, stat_label, color=MUTED, fontsize=11, fontweight="bold")
    fig.text(0.84, 0.54, "LEADING PLAYERS", color=WHITE, fontsize=13, fontweight="bold")
    for i, (player, count) in enumerate(leaders):
        fig.text(0.84, 0.49-i*0.065, f"{count}", color=color, fontsize=16, fontweight="bold")
        fig.text(0.875, 0.492-i*0.065, player, color=MUTED, fontsize=10)
    fig.savefig(path, facecolor=NAVY, dpi=100)
    plt.close(fig)


def save_passing_xt(path, match, events):
    passes = [p for p in team_passes(events) if p["complete"] and p["xt"] > 0]
    total_xt = sum(p["xt"] for p in passes)
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    max_xt = max((p["xt"] for p in passes), default=0.01)
    for p in sorted(passes, key=lambda z: z["xt"]):
        pitch.arrows(
            p["x"], p["y"], p["end_x"], p["end_y"], ax=ax,
            color=CYAN, alpha=0.18 + 0.75*p["xt"]/max_xt,
            width=0.8 + 3.2*p["xt"]/max_xt,
            headwidth=4, headlength=4, zorder=3
        )
    plot_page_frame(
        fig, "PASSING | EXPECTED THREAT (xT)",
        f"Varaždin {result_string(match)} {opponent(match)}",
        match_subtitle(match, "positive xT added by completed passes | 12x8 possession-value grid")
    )
    player_xt = defaultdict(float)
    for p in passes:
        player_xt[p["player"]] += p["xt"]
    leaders = sorted(player_xt.items(), key=lambda z: z[1], reverse=True)[:5]
    fig.text(0.84, 0.68, f"{total_xt:.2f}", color=CYAN, fontsize=30, fontweight="bold")
    fig.text(0.84, 0.645, "PASSING xT", color=MUTED, fontsize=11, fontweight="bold")
    fig.text(0.84, 0.54, "TOP xT PASSERS", color=WHITE, fontsize=13, fontweight="bold")
    for i, (player, value) in enumerate(leaders):
        fig.text(0.84, 0.49-i*0.062, f"{value:.2f}", color=CYAN, fontsize=15, fontweight="bold")
        fig.text(0.885, 0.492-i*0.062, player, color=MUTED, fontsize=9.5)
    fig.savefig(path, facecolor=NAVY, dpi=100)
    plt.close(fig)


def save_xg_channels(path, match, all_shots):
    shots = [s for s in all_shots if s["match_id"] == match["match_id"] and s["team"] == TEAM]
    labels = ["LEFT WIDE", "LEFT HALF-SPACE", "CENTRAL", "RIGHT HALF-SPACE", "RIGHT WIDE"]
    bounds = [(0, 16), (16, 32), (32, 48), (48, 64), (64, 80)]
    values, counts = [], []
    for low, high in bounds:
        channel = [s for s in shots if low <= s["y"] < high or (high == 80 and s["y"] == 80)]
        values.append(sum(s["xg"] for s in channel))
        counts.append(len(channel))
    colors = [CYAN, GREEN, AMBER, PINK, "#A78BFA"]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.15, 0.18, 0.58, 0.54], facecolor=NAVY)
    bars = ax.barh(range(5), values, color=colors, height=0.62)
    ax.set_yticks(range(5), labels=labels); ax.invert_yaxis()
    ax.tick_params(axis="y", colors=WHITE, labelsize=12, length=0)
    ax.tick_params(axis="x", colors=MUTED, labelsize=10, length=0)
    ax.grid(axis="x", color=GRID, alpha=0.7)
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.set_xlim(0, max(values + [0.1]) * 1.22)
    for i, (bar, value, count) in enumerate(zip(bars, values, counts)):
        ax.text(value + max(values+[0.1])*0.03, bar.get_y()+bar.get_height()/2, f"{value:.2f} xG | {count} shots",
                color=WHITE, fontsize=11, fontweight="bold", va="center")
    plot_page_frame(fig, "SHOOTING | xG BY ATTACKING CHANNEL", f"Varaždin {result_string(match)} {opponent(match)}",
                    match_subtitle(match, "five equal-width StatsBomb channels"))
    fig.text(0.83, 0.64, f"{sum(values):.2f}", color=CYAN, fontsize=30, fontweight="bold")
    fig.text(0.83, 0.605, "TOTAL xG", color=MUTED, fontsize=11, fontweight="bold")
    top = max(range(5), key=lambda i: values[i]) if values else 0
    fig.text(0.83, 0.49, labels[top], color=colors[top], fontsize=15, fontweight="bold")
    fig.text(0.83, 0.455, "TOP CHANNEL", color=MUTED, fontsize=11, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_zone_origin_passes(path, match, events, zone):
    passes = [p for p in team_passes(events) if p["complete"]]
    if zone == "half_spaces":
        selected = [p for p in passes if p["x"] >= 60 and (16 <= p["y"] < 32 or 48 <= p["y"] < 64)]
        kicker, subtitle, color = "PASSING | PASSES FROM HALF-SPACES", "origins in attacking-half left/right half-spaces", CYAN
        zones = [(60, 16, 60, 16), (60, 48, 60, 16)]
    else:
        selected = [p for p in passes if 80 <= p["x"] < 102 and 26.7 <= p["y"] <= 53.3]
        kicker, subtitle, color = "PASSING | PASSES FROM ZONE 14", "origins in central zone outside the penalty area", AMBER
        zones = [(80, 26.7, 22, 26.6)]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    for x, y, w, h in zones:
        ax.add_patch(plt.Rectangle((x, y), w, h, color=color, alpha=0.12, zorder=1))
    for p in selected:
        pitch.arrows(p["x"], p["y"], p["end_x"], p["end_y"], ax=ax, color=color, alpha=0.7,
                     width=1.6, headwidth=4, headlength=4, zorder=3)
    plot_page_frame(fig, kicker, f"Varaždin {result_string(match)} {opponent(match)}", match_subtitle(match, subtitle))
    fig.text(0.84, 0.68, str(len(selected)), color=color, fontsize=30, fontweight="bold")
    fig.text(0.84, 0.645, "COMPLETED PASSES", color=MUTED, fontsize=11, fontweight="bold")
    into_box = sum(p["end_x"] >= 102 and 18 <= p["end_y"] <= 62 for p in selected)
    fig.text(0.84, 0.53, str(into_box), color=PINK, fontsize=30, fontweight="bold")
    fig.text(0.84, 0.495, "INTO PENALTY AREA", color=MUTED, fontsize=11, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_pressing(path, match, events):
    pressures = [e for e in events if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Pressure" and e.get("location")]
    xs, ys = [e["location"][0] for e in pressures], [e["location"][1] for e in pressures]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    if pressures:
        bs = pitch.bin_statistic(xs, ys, statistic="count", bins=(6, 4), normalize=True)
        pitch.heatmap(bs, ax=ax, cmap="magma", alpha=0.72, zorder=1)
        pitch.scatter(xs, ys, ax=ax, s=12, color=WHITE, alpha=0.25, zorder=3)
    high = sum(x >= 80 for x in xs); counter = sum(bool(e.get("counterpress")) for e in pressures)
    plot_page_frame(fig, "OFF-BALL | PRESSING MAP", f"Varaždin {result_string(match)} {opponent(match)}",
                    match_subtitle(match, "pressure-event density | dots show individual pressures"))
    for i, (label, value, color) in enumerate([("PRESSURES", len(pressures), CYAN), ("HIGH PRESS", high, PINK), ("COUNTERPRESS", counter, AMBER)]):
        fig.text(0.84, 0.68-i*0.14, str(value), color=color, fontsize=30, fontweight="bold")
        fig.text(0.84, 0.645-i*0.14, label, color=MUTED, fontsize=11, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_progression(path, match, events):
    actions = []
    for e in events:
        if e.get("team", {}).get("name") != TEAM or not e.get("location"):
            continue
        typ = e.get("type", {}).get("name")
        if typ == "Pass" and "outcome" not in e.get("pass", {}):
            end = e.get("pass", {}).get("end_location")
        elif typ == "Carry":
            end = e.get("carry", {}).get("end_location")
        else:
            continue
        if not end or end[0] - e["location"][0] < 10:
            continue
        actions.append((typ, e["location"][0], e["location"][1], end[0], end[1]))
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    for typ, x, y, ex, ey in actions:
        color = CYAN if typ == "Pass" else AMBER
        pitch.arrows(x, y, ex, ey, ax=ax, color=color, alpha=0.48, width=1.3, headwidth=3.6, headlength=3.6)
    n_pass = sum(a[0] == "Pass" for a in actions); n_carry = len(actions)-n_pass
    plot_page_frame(fig, "ON-BALL | BALL PROGRESSION", f"Varaždin {result_string(match)} {opponent(match)}",
                    match_subtitle(match, "completed passes and carries gaining at least 10 pitch units"))
    fig.text(0.84, 0.68, str(n_pass), color=CYAN, fontsize=30, fontweight="bold"); fig.text(0.84, 0.645, "PROGRESSIVE PASSES", color=MUTED, fontsize=11, fontweight="bold")
    fig.text(0.84, 0.53, str(n_carry), color=AMBER, fontsize=30, fontweight="bold"); fig.text(0.84, 0.495, "PROGRESSIVE CARRIES", color=MUTED, fontsize=11, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_defensive(path, match, events):
    actions = []
    for e in events:
        if e.get("team", {}).get("name") != TEAM or not e.get("location"):
            continue
        typ = e.get("type", {}).get("name")
        if typ == "Duel" and e.get("duel", {}).get("type", {}).get("name") == "Tackle": label = "Tackle"
        elif typ in {"Interception", "Block", "Ball Recovery", "Clearance"}: label = typ
        else: continue
        actions.append((label, e["location"][0], e["location"][1]))
    styles = {"Tackle": (CYAN, "o"), "Interception": (PINK, "s"), "Block": (AMBER, "X"), "Ball Recovery": (GREEN, "^"), "Clearance": ("#A78BFA", "D")}
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    counts = defaultdict(int)
    for label, x, y in actions:
        color, marker = styles[label]; counts[label] += 1
        pitch.scatter(x, y, ax=ax, s=75, color=color, marker=marker, edgecolors=WHITE, linewidth=0.7, alpha=0.85)
    plot_page_frame(fig, "OFF-BALL | DEFENSIVE ACTIONS", f"Varaždin {result_string(match)} {opponent(match)}",
                    match_subtitle(match, "tackles, interceptions, blocks, recoveries and clearances"))
    for i, label in enumerate(styles):
        fig.text(0.84, 0.68-i*0.09, str(counts[label]), color=styles[label][0], fontsize=20, fontweight="bold")
        fig.text(0.88, 0.685-i*0.09, label.upper(), color=MUTED, fontsize=10, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def event_end(e):
    typ = e.get("type", {}).get("name")
    if typ == "Pass":
        return e.get("pass", {}).get("end_location")
    if typ == "Carry":
        return e.get("carry", {}).get("end_location")
    return None


def save_build_up(path, match, events):
    goal_kicks = [e for e in events if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Pass"
                  and e.get("pass", {}).get("type", {}).get("name") == "Goal Kick"]
    possessions = {e.get("possession") for e in goal_kicks}
    actions = [e for e in events if e.get("possession") in possessions and e.get("team", {}).get("name") == TEAM
               and e.get("type", {}).get("name") in {"Pass", "Carry"} and e.get("location") and event_end(e)]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    for e in actions:
        end = event_end(e); is_gk = e.get("pass", {}).get("type", {}).get("name") == "Goal Kick"
        color = PINK if is_gk else CYAN
        pitch.arrows(e["location"][0], e["location"][1], end[0], end[1], ax=ax, color=color,
                     alpha=0.35 if not is_gk else 0.95, width=1.4 if not is_gk else 2.8,
                     headwidth=4.5, headlength=4.5)
    short = sum(e.get("pass", {}).get("end_location", [120])[0] < 40 for e in goal_kicks)
    long = len(goal_kicks)-short
    plot_page_frame(fig, "ON-BALL | GOAL-KICK BUILD-UP", f"Varaždin {result_string(match)} {opponent(match)}",
                    match_subtitle(match, "pink = goal kick | cyan = subsequent actions in the same possession"))
    for i, (label, value, color) in enumerate([("GOAL KICKS", len(goal_kicks), PINK), ("SHORT", short, CYAN), ("LONG", long, AMBER)]):
        fig.text(0.84, 0.68-i*0.14, str(value), color=color, fontsize=30, fontweight="bold")
        fig.text(0.84, 0.645-i*0.14, label, color=MUTED, fontsize=11, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_transitions(path, match, events):
    team_possessions = defaultdict(list)
    for e in events:
        if e.get("possession_team", {}).get("name") == TEAM and e.get("possession") is not None:
            team_possessions[e["possession"]].append(e)
    recoveries = [
        (e.get("index", 0), e.get("minute", 0)*60+e.get("second", 0))
        for e in events if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Ball Recovery"
    ]
    counter_possessions = set()
    for possession, rows in team_possessions.items():
        first = min(rows, key=lambda e: e.get("index", 0))
        first_idx = first.get("index", 0); first_time = first.get("minute", 0)*60+first.get("second", 0)
        tagged_counter = any(e.get("play_pattern", {}).get("name") == "From Counter" for e in rows)
        recovery_triggered = any(0 <= first_time-t <= 15 and idx <= first_idx for idx, t in recoveries)
        if tagged_counter or recovery_triggered:
            counter_possessions.add(possession)
    actions = [e for e in events if e.get("possession") in counter_possessions and e.get("team", {}).get("name") == TEAM
               and e.get("type", {}).get("name") in {"Pass", "Carry"} and e.get("location") and event_end(e)]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    for e in actions:
        end = event_end(e); color = CYAN if e["type"]["name"] == "Pass" else AMBER
        pitch.arrows(e["location"][0], e["location"][1], end[0], end[1], ax=ax, color=color, alpha=0.68,
                     width=1.6, headwidth=4, headlength=4)
    shots = [e for e in events if e.get("possession") in counter_possessions and e.get("team", {}).get("name") == TEAM
             and e.get("type", {}).get("name") == "Shot"]
    xg = sum(e.get("shot", {}).get("statsbomb_xg", 0) or 0 for e in shots)
    plot_page_frame(fig, "ON-BALL | ATTACKING TRANSITIONS", f"Varaždin {result_string(match)} {opponent(match)}",
                    match_subtitle(match, "possessions tagged From Counter or started within 15 seconds of recovery"))
    for i, (label, value, color) in enumerate([("RECOVERY ATTACKS", len(counter_possessions), CYAN), ("SHOTS", len(shots), PINK), ("TRANSITION xG", f"{xg:.2f}", AMBER)]):
        fig.text(0.84, 0.68-i*0.14, str(value), color=color, fontsize=30, fontweight="bold")
        fig.text(0.84, 0.645-i*0.14, label, color=MUTED, fontsize=11, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_pressure_turnovers(path, match, events):
    losses = []
    for e in events:
        if e.get("team", {}).get("name") != TEAM or not e.get("location") or not e.get("under_pressure"):
            continue
        typ = e.get("type", {}).get("name")
        if typ in {"Dispossessed", "Miscontrol"}:
            losses.append((typ, e["location"][0], e["location"][1], e.get("player", {}).get("name", "Unknown")))
        elif typ == "Pass" and "outcome" in e.get("pass", {}):
            losses.append(("Incomplete pass", e["location"][0], e["location"][1], e.get("player", {}).get("name", "Unknown")))
    styles = {"Dispossessed": (PINK, "X"), "Miscontrol": (AMBER, "o"), "Incomplete pass": (CYAN, "s")}
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    counts, players = defaultdict(int), defaultdict(int)
    for typ, x, y, player in losses:
        color, marker = styles[typ]; counts[typ] += 1; players[player] += 1
        pitch.scatter(x, y, ax=ax, s=95, color=color, marker=marker, edgecolors=WHITE, linewidth=0.8, alpha=0.9)
    plot_page_frame(fig, "ON-BALL | TURNOVERS UNDER PRESSURE", f"Varaždin {result_string(match)} {opponent(match)}",
                    match_subtitle(match, "pressured dispossessions, miscontrols and incomplete passes"))
    fig.text(0.84, 0.69, str(len(losses)), color=PINK, fontsize=30, fontweight="bold")
    fig.text(0.84, 0.655, "PRESSURED LOSSES", color=MUTED, fontsize=11, fontweight="bold")
    for i, typ in enumerate(styles):
        fig.text(0.84, 0.55-i*0.07, str(counts[typ]), color=styles[typ][0], fontsize=17, fontweight="bold")
        fig.text(0.875, 0.553-i*0.07, typ.upper(), color=MUTED, fontsize=9.5)
    leaders = sorted(players.items(), key=lambda z: z[1], reverse=True)[:3]
    for i, (player, count) in enumerate(leaders):
        fig.text(0.84, 0.29-i*0.055, f"{count}  {player}", color=WHITE, fontsize=9.5)
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_chance_network(path, match, events):
    shots_by_id = {e.get("id"): e for e in events if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Shot"}
    links = []
    for e in events:
        if e.get("team", {}).get("name") != TEAM or e.get("type", {}).get("name") != "Pass":
            continue
        sid = e.get("pass", {}).get("assisted_shot_id")
        if not sid or sid not in shots_by_id or not e.get("location"):
            continue
        shot = shots_by_id[sid]
        links.append((e.get("player", {}).get("name", "Unknown"), shot.get("player", {}).get("name", "Unknown"),
                      e["location"], shot.get("location"), shot.get("shot", {}).get("statsbomb_xg", 0) or 0))
    agg = defaultdict(lambda: {"n": 0, "xg": 0, "origins": [], "shots": []})
    for passer, shooter, origin, sloc, xg in links:
        key = (passer, shooter); agg[key]["n"] += 1; agg[key]["xg"] += xg; agg[key]["origins"].append(origin); agg[key]["shots"].append(sloc)
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.74, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    for (passer, shooter), v in agg.items():
        ox = sum(p[0] for p in v["origins"])/v["n"]; oy = sum(p[1] for p in v["origins"])/v["n"]
        sx = sum(p[0] for p in v["shots"])/v["n"]; sy = sum(p[1] for p in v["shots"])/v["n"]
        pitch.arrows(ox, oy, sx, sy, ax=ax, color=CYAN, alpha=0.75, width=1.4+v["xg"]*4, headwidth=5, headlength=5)
        ax.text(ox, oy, passer.split()[-1], color=WHITE, fontsize=8, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=.25", facecolor=PINK, edgecolor=WHITE))
        ax.text(sx, sy, shooter.split()[-1], color=WHITE, fontsize=8, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=.25", facecolor=NAVY_2, edgecolor=CYAN))
    total_xga = sum(v["xg"] for v in agg.values())
    plot_page_frame(fig, "ON-BALL | CHANCE-CREATION NETWORK", f"Varaždin {result_string(match)} {opponent(match)}",
                    match_subtitle(match, "shot-assist origin linked to resulting shot location"))
    fig.text(0.84, 0.68, str(len(links)), color=CYAN, fontsize=30, fontweight="bold")
    fig.text(0.84, 0.645, "ASSISTED SHOTS", color=MUTED, fontsize=11, fontweight="bold")
    fig.text(0.84, 0.53, f"{total_xga:.2f}", color=PINK, fontsize=30, fontweight="bold")
    fig.text(0.84, 0.495, "xG ASSISTED", color=MUTED, fontsize=11, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_possession_funnel(path, match, events):
    poss = defaultdict(list)
    for e in events:
        if e.get("possession_team", {}).get("name") == TEAM and e.get("possession") is not None:
            poss[e["possession"]].append(e)
    total = len(poss)
    final_third = box = shot = goal = 0
    for rows in poss.values():
        reached_final = reached_box = has_shot = has_goal = False
        for e in rows:
            if e.get("team", {}).get("name") != TEAM: continue
            pts = [e.get("location"), event_end(e)]
            for loc in pts:
                if not loc: continue
                reached_final |= loc[0] >= 80
                reached_box |= loc[0] >= 102 and 18 <= loc[1] <= 62
            if e.get("type", {}).get("name") == "Shot":
                has_shot = True; has_goal |= e.get("shot", {}).get("outcome", {}).get("name") == "Goal"
        final_third += reached_final; box += reached_box; shot += has_shot; goal += has_goal
    stages = [("POSSESSIONS", total, CYAN), ("FINAL THIRD", final_third, GREEN), ("PENALTY AREA", box, AMBER), ("SHOT", shot, PINK), ("GOAL", goal, RED)]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.10, 0.19, 0.78, 0.50]); ax.set_facecolor(NAVY); ax.axis("off")
    maxw = 0.92
    for i, (label, value, color) in enumerate(stages):
        width = maxw * (value/max(total, 1))
        y = 0.88-i*0.19
        ax.add_patch(plt.Rectangle((0.5-width/2, y-0.06), width, 0.12, color=color, alpha=0.9))
        if width < 0.15:
            ax.text(0.5+width/2+0.025, y, f"{label}  {value}", color=WHITE, fontsize=13, fontweight="bold", ha="left", va="center")
        else:
            ax.text(0.5, y, f"{label}  {value}", color=NAVY if i < 3 else WHITE, fontsize=14, fontweight="bold", ha="center", va="center")
        if i > 0:
            ax.text(0.96, y, f"{value/max(stages[i-1][1],1)*100:.0f}% of previous", color=MUTED, fontsize=10, ha="right", va="center")
    plot_page_frame(fig, "ON-BALL | POSSESSION OUTCOME FUNNEL", f"Varaždin {result_string(match)} {opponent(match)}",
                    match_subtitle(match, "unique Varaždin possessions reaching each stage"))
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_combined_existing(path, title, subtitle, image_paths, matches):
    img = base_image()
    d = ImageDraw.Draw(img)
    header(d, "THREE-MATCH COMPARISON", title, subtitle)
    panel_w, panel_h = 460, 330
    for i, (source, match) in enumerate(zip(image_paths, matches)):
        x = 55 + i * 510
        y = 250
        rounded_panel(d, (x, y, x+panel_w, y+panel_h+75), fill=NAVY_2, outline=GRID)
        d.text((x+15, y+20), f"{match['match_date'][5:]} | {result_string(match)} vs {opponent(match)}",
               fill=WHITE, font=font(19, True))
        src = Image.open(source).convert("RGB")
        # Preserve the full analytical page so definitions, maps and key figures remain visible.
        src.thumbnail((panel_w-20, panel_h-15))
        px = x + (panel_w-src.width)//2
        py = y + 55
        img.paste(src, (px, py))
    d.text((80, 735), "Each panel retains its original metric definition and match-level key figures.", fill=MUTED, font=font(18))
    footer(d)
    img.save(path, quality=95)


def combined_pitch_figure(title, subtitle, kicker="THREE-MATCH AGGREGATE | ONE PITCH"):
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.06, 0.14, 0.72, 0.62])
    pitch = Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1.4, goal_type="box")
    pitch.draw(ax=ax)
    plot_page_frame(fig, kicker, title, subtitle)
    return fig, ax, pitch


def add_match_legend(fig, recent, colors):
    for i, (match, color) in enumerate(zip(recent, colors)):
        fig.text(0.82, 0.70-i*0.07, "━━", color=color, fontsize=17, fontweight="bold")
        fig.text(0.86, 0.705-i*0.07, f"{match['match_date'][5:]} | {result_string(match)} {opponent(match)}",
                 color=WHITE, fontsize=9.5)


def save_one_pitch_metric(path, mode, recent, events_by_id, all_shots):
    titles = {
        "pass_clusters": ("Pass clusters", "Top five StatsBomb clusters per match | color identifies match"),
        "open_play_crosses": ("Open-play crosses", "Corners and free kicks excluded | arrows show deliveries"),
        "final_third_entries": ("Final-third entries", "Completed passes crossing the x=80 line"),
        "penalty_area_entries": ("Penalty-area entries", "Completed passes entering the penalty area"),
        "progressive_passes": ("Progressive passes", "Goal-distance reduction thresholds by starting zone"),
        "passing_xt": ("Expected threat through passing", "Positive xT passes | line width reflects value"),
        "halfspace_passes": ("Passes from half-spaces", "Completed passes originating in attacking-half half-spaces"),
        "zone14_passes": ("Passes from Zone 14", "Completed passes originating in central Zone 14"),
        "pressing": ("Pressing locations", "Individual StatsBomb pressure events"),
        "progression": ("Ball progression", "Completed passes and carries gaining at least 10 pitch units"),
        "defensive_actions": ("Defensive actions", "Tackles, interceptions, blocks, recoveries and clearances"),
        "goal_kick_buildup": ("Goal-kick build-up", "Goal kicks and subsequent same-possession actions"),
        "attacking_transitions": ("Attacking transitions", "Recovery attacks: passes and carries within transition possessions"),
        "pressure_turnovers": ("Turnovers under pressure", "Pressured dispossessions, miscontrols and incomplete passes"),
        "chance_networks": ("Chance creation", "Shot-assist origins linked to resulting shot locations"),
    }
    title, subtitle = titles[mode]
    fig, ax, pitch = combined_pitch_figure(title, subtitle)
    colors = [CYAN, PINK, AMBER]
    total = 0
    for match, color in zip(recent, colors):
        events = events_by_id[match["match_id"]]
        passes = team_passes(events)
        arrows, points = [], []
        if mode == "pass_clusters":
            grouped = defaultdict(list)
            for p in passes:
                if p["complete"] and p["cluster_id"] is not None: grouped[p["cluster_id"]].append(p)
            for _, rows in sorted(grouped.items(), key=lambda z: len(z[1]), reverse=True)[:5]:
                arrows.append((sum(p["x"] for p in rows)/len(rows), sum(p["y"] for p in rows)/len(rows),
                               sum(p["end_x"] for p in rows)/len(rows), sum(p["end_y"] for p in rows)/len(rows), 3.0))
        elif mode == "open_play_crosses":
            arrows = [(p["x"], p["y"], p["end_x"], p["end_y"], 1.7) for p in passes if p["cross"]
                      and p["play_pattern"] not in {"From Corner", "From Free Kick"} and p["pass_type"] not in {"Corner", "Free Kick"}]
        elif mode == "final_third_entries":
            arrows = [(p["x"], p["y"], p["end_x"], p["end_y"], 1.5) for p in passes if p["complete"] and p["x"] < 80 <= p["end_x"]]
        elif mode == "penalty_area_entries":
            arrows = [(p["x"], p["y"], p["end_x"], p["end_y"], 1.7) for p in passes if p["complete"]
                      and p["end_x"] >= 102 and 18 <= p["end_y"] <= 62 and not (p["x"] >= 102 and 18 <= p["y"] <= 62)]
        elif mode == "progressive_passes":
            def gd(x, y): return math.hypot(120-x, 40-y)
            def prog(p):
                reduction = gd(p["x"], p["y"])-gd(p["end_x"], p["end_y"])
                threshold = 30 if p["x"] < 60 and p["end_x"] < 60 else 15 if p["x"] < 60 <= p["end_x"] else 10
                return p["complete"] and reduction >= threshold
            arrows = [(p["x"], p["y"], p["end_x"], p["end_y"], 1.4) for p in passes if prog(p)]
        elif mode == "passing_xt":
            arrows = [(p["x"], p["y"], p["end_x"], p["end_y"], 0.8+18*p["xt"]) for p in passes if p["complete"] and p["xt"] > .005]
        elif mode == "halfspace_passes":
            arrows = [(p["x"], p["y"], p["end_x"], p["end_y"], 1.3) for p in passes if p["complete"] and p["x"] >= 60
                      and (16 <= p["y"] < 32 or 48 <= p["y"] < 64)]
        elif mode == "zone14_passes":
            arrows = [(p["x"], p["y"], p["end_x"], p["end_y"], 1.6) for p in passes if p["complete"]
                      and 80 <= p["x"] < 102 and 26.7 <= p["y"] <= 53.3]
        elif mode == "pressing":
            points = [(e["location"][0], e["location"][1], 35, "o") for e in events
                      if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Pressure" and e.get("location")]
        elif mode == "progression":
            for e in events:
                if e.get("team", {}).get("name") != TEAM or not e.get("location"): continue
                end = event_end(e)
                if e.get("type", {}).get("name") in {"Pass", "Carry"} and end and end[0]-e["location"][0] >= 10:
                    if e["type"]["name"] != "Pass" or "outcome" not in e.get("pass", {}):
                        arrows.append((e["location"][0], e["location"][1], end[0], end[1], 1.2))
        elif mode == "defensive_actions":
            for e in events:
                if e.get("team", {}).get("name") != TEAM or not e.get("location"): continue
                typ = e.get("type", {}).get("name")
                if typ in {"Interception", "Block", "Ball Recovery", "Clearance"} or (typ == "Duel" and e.get("duel", {}).get("type", {}).get("name") == "Tackle"):
                    points.append((e["location"][0], e["location"][1], 48, "o"))
        elif mode == "goal_kick_buildup":
            gk = [e for e in events if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Pass"
                  and e.get("pass", {}).get("type", {}).get("name") == "Goal Kick"]
            poss = {e.get("possession") for e in gk}
            for e in events:
                end = event_end(e)
                if e.get("possession") in poss and e.get("team", {}).get("name") == TEAM and end and e.get("location"):
                    arrows.append((e["location"][0], e["location"][1], end[0], end[1], 2.2 if e in gk else 0.8))
        elif mode == "attacking_transitions":
            recoveries = [(e.get("index", 0), e.get("minute", 0)*60+e.get("second", 0)) for e in events
                          if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Ball Recovery"]
            poss_rows = defaultdict(list)
            for e in events:
                if e.get("possession_team", {}).get("name") == TEAM: poss_rows[e.get("possession")].append(e)
            poss = set()
            for pid, rows in poss_rows.items():
                first = min(rows, key=lambda e: e.get("index", 0)); ft = first.get("minute", 0)*60+first.get("second", 0)
                if any(e.get("play_pattern", {}).get("name") == "From Counter" for e in rows) or any(0 <= ft-t <= 15 and idx <= first.get("index", 0) for idx,t in recoveries):
                    poss.add(pid)
            for e in events:
                end = event_end(e)
                if e.get("possession") in poss and e.get("team", {}).get("name") == TEAM and end and e.get("location"):
                    arrows.append((e["location"][0], e["location"][1], end[0], end[1], 1.1))
        elif mode == "pressure_turnovers":
            for e in events:
                if e.get("team", {}).get("name") != TEAM or not e.get("location") or not e.get("under_pressure"): continue
                typ = e.get("type", {}).get("name")
                if typ in {"Dispossessed", "Miscontrol"} or (typ == "Pass" and "outcome" in e.get("pass", {})):
                    points.append((e["location"][0], e["location"][1], 60, "X"))
        elif mode == "chance_networks":
            shots = {e.get("id"): e for e in events if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Shot"}
            for e in events:
                sid = e.get("pass", {}).get("assisted_shot_id")
                if e.get("team", {}).get("name") == TEAM and sid in shots and e.get("location") and shots[sid].get("location"):
                    s = shots[sid]; arrows.append((e["location"][0], e["location"][1], s["location"][0], s["location"][1],
                                                    1.4+4*(s.get("shot", {}).get("statsbomb_xg", 0) or 0)))
        for x, y, ex, ey, lw in arrows:
            pitch.arrows(x, y, ex, ey, ax=ax, color=color, alpha=0.40, width=lw, headwidth=4, headlength=4)
        for x, y, size, marker in points:
            pitch.scatter(x, y, ax=ax, s=size, marker=marker, color=color, edgecolors=WHITE, linewidth=0.5, alpha=0.65)
        total += len(arrows)+len(points)
    add_match_legend(fig, recent, colors)
    fig.text(0.82, 0.42, f"{total}", color=WHITE, fontsize=28, fontweight="bold")
    fig.text(0.82, 0.385, "TOTAL ACTIONS SHOWN", color=MUTED, fontsize=10, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100)
    plt.close(fig)


def save_goalkeeper_distribution(path, recent, events_by_id):
    fig, ax, pitch = combined_pitch_figure("Goalkeeper distribution", "All three matches on one pitch | color identifies match")
    colors = [CYAN, PINK, AMBER]
    totals = []
    for match, color in zip(recent, colors):
        passes = [e for e in events_by_id[match["match_id"]] if e.get("team", {}).get("name") == TEAM
                  and e.get("type", {}).get("name") == "Pass"
                  and e.get("position", {}).get("name") == "Goalkeeper"
                  and e.get("location") and e.get("pass", {}).get("end_location")]
        complete = 0
        for e in passes:
            p = e["pass"]; success = "outcome" not in p; complete += success
            pitch.arrows(e["location"][0], e["location"][1], p["end_location"][0], p["end_location"][1],
                         ax=ax, color=color, width=1.5 if success else 0.9, headwidth=4, headlength=4,
                         alpha=0.65 if success else 0.22)
        totals.append((len(passes), complete))
    add_match_legend(fig, recent, colors)
    for i, (n, c) in enumerate(totals):
        fig.text(0.84, 0.47-i*.055, f"{n} passes | {c/max(n,1)*100:.0f}% complete", color=colors[i], fontsize=10, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_goalkeeper_actions(path, recent, events_by_id):
    fig, ax, pitch = combined_pitch_figure("Goalkeeper interventions", "All three matches on one pitch | marker identifies action")
    colors = [CYAN, PINK, AMBER]
    markers = {"Shot Saved": "o", "Goal Conceded": "X", "Punch": "^", "Collected": "s", "Keeper Sweeper": "D", "Shot Faced": "."}
    for match, color in zip(recent, colors):
        actions = [e for e in events_by_id[match["match_id"]] if e.get("team", {}).get("name") == TEAM
                   and e.get("type", {}).get("name") == "Goal Keeper" and e.get("location")]
        for e in actions:
            typ = e.get("goalkeeper", {}).get("type", {}).get("name", "Other")
            pitch.scatter(e["location"][0], e["location"][1], ax=ax, s=90, color=color, marker=markers.get(typ, "o"),
                          edgecolors=WHITE, linewidth=0.7, alpha=0.9)
    add_match_legend(fig, recent, colors)
    fig.text(0.82, 0.46, "○ save / faced", color=WHITE, fontsize=10)
    fig.text(0.82, 0.42, "× goal conceded", color=WHITE, fontsize=10)
    fig.text(0.82, 0.38, "◇ sweeper | △ punch | □ collected", color=WHITE, fontsize=10)
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_set_piece_comparison(path, recent, events_by_id, mode):
    config = {
        "attacking_corners": ("SET PIECES | ATTACKING CORNERS", "Varaždin corner deliveries and resulting shots", "From Corner", TEAM, False),
        "attacking_free_kicks": ("SET PIECES | ATTACKING FREE KICKS", "Varaždin free-kick deliveries and resulting shots", "From Free Kick", TEAM, False),
        "defending_corners": ("SET PIECES | DEFENDING CORNERS", "Opponent corner deliveries into Varaždin's defensive area", "From Corner", "OPP", True),
    }
    kicker, title, pattern, selected_team, flip = config[mode]
    fig, ax, pitch = combined_pitch_figure(title, "All three matches on one pitch | arrows = deliveries | circles = resulting shots")
    colors = [CYAN, PINK, AMBER]
    totals = []
    for match, color in zip(recent, colors):
        ev = events_by_id[match["match_id"]]
        rows = [e for e in ev if e.get("play_pattern", {}).get("name") == pattern
                and ((e.get("team", {}).get("name") == TEAM) if selected_team == TEAM else (e.get("team", {}).get("name") != TEAM))]
        required_type = "Corner" if pattern == "From Corner" else "Free Kick"
        deliveries = [
            e for e in rows
            if e.get("type", {}).get("name") == "Pass"
            and e.get("pass", {}).get("type", {}).get("name") == required_type
            and e.get("location") and e.get("pass", {}).get("end_location")
        ]
        shots = [e for e in rows if e.get("type", {}).get("name") == "Shot" and e.get("location")]
        for e in deliveries:
            x, y = e["location"][:2]; ex, ey = e["pass"]["end_location"][:2]
            if flip: x, y, ex, ey = 120-x, 80-y, 120-ex, 80-ey
            success = "outcome" not in e["pass"]
            pitch.arrows(x, y, ex, ey, ax=ax, color=color, alpha=0.72 if success else 0.35,
                         width=1.3, headwidth=3.8, headlength=3.8)
        xg = 0
        for e in shots:
            x, y = e["location"][:2]
            if flip: x, y = 120-x, 80-y
            val = e.get("shot", {}).get("statsbomb_xg", 0) or 0; xg += val
            pitch.scatter(x, y, ax=ax, s=70+700*val, color=color, edgecolors=WHITE, linewidth=1.2)
        totals.append((len(deliveries), len(shots), xg))
    add_match_legend(fig, recent, colors)
    for i, (deliveries, shots, xg) in enumerate(totals):
        fig.text(0.82, 0.47-i*.055, f"{deliveries} deliveries | {shots} shots | {xg:.2f} xG", color=colors[i], fontsize=10, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def season_team_metrics(matches, events_by_id):
    totals = defaultdict(lambda: defaultdict(float))
    games = defaultdict(int)
    for match in matches:
        events = events_by_id.get(match["match_id"], [])
        teams = {team_name(match, "home"), team_name(match, "away")}
        for team in teams:
            games[team] += 1
        for e in events:
            team = e.get("team", {}).get("name")
            if team not in teams:
                continue
            typ = e.get("type", {}).get("name")
            if typ == "Pass":
                totals[team]["passes"] += 1
                if "outcome" not in e.get("pass", {}):
                    totals[team]["completed"] += 1
                    loc, end = e.get("location"), e.get("pass", {}).get("end_location")
                    if loc and end:
                        if loc[0] < 80 <= end[0]: totals[team]["final_entries"] += 1
                        if end[0] >= 102 and 18 <= end[1] <= 62 and not (loc[0] >= 102 and 18 <= loc[1] <= 62):
                            totals[team]["box_entries"] += 1
                totals[team]["obv"] += e.get("obv_total_net") or 0
            elif typ == "Carry":
                totals[team]["obv"] += e.get("obv_total_net") or 0
            elif typ == "Pressure":
                totals[team]["pressures"] += 1
            elif typ == "Shot":
                totals[team]["shots"] += 1
                totals[team]["xg"] += e.get("shot", {}).get("statsbomb_xg", 0) or 0
    metrics = {}
    for team, vals in totals.items():
        g = max(games[team], 1)
        metrics[team] = {k: v/g for k, v in vals.items()}
        metrics[team]["pass_pct"] = vals["completed"]/max(vals["passes"], 1)*100
        metrics[team]["xg_per_shot"] = vals["xg"]/max(vals["shots"], 1)
    return metrics


def player_value_metrics(recent, events_by_id):
    data = defaultdict(lambda: defaultdict(float))
    for match in recent:
        for e in events_by_id[match["match_id"]]:
            if e.get("team", {}).get("name") != TEAM or not e.get("player"):
                continue
            player = e["player"]["name"]; typ = e.get("type", {}).get("name")
            data[player]["actions"] += 1
            data[player]["obv"] += e.get("obv_total_net") or 0
            if typ == "Pass":
                p = e.get("pass", {}); loc = e.get("location"); end = p.get("end_location")
                if "outcome" not in p and loc and end:
                    data[player]["xt"] += max(0, xt_at(end[0], end[1])-xt_at(loc[0], loc[1]))
                    if loc[0] < 80 <= end[0]: data[player]["final_entries"] += 1
                    if end[0] >= 102 and 18 <= end[1] <= 62 and not (loc[0] >= 102 and 18 <= loc[1] <= 62):
                        data[player]["box_entries"] += 1
                sid = p.get("assisted_shot_id")
                if sid:
                    shot = next((z for z in events_by_id[match["match_id"]] if z.get("id") == sid), None)
                    if shot: data[player]["xa"] += shot.get("shot", {}).get("statsbomb_xg", 0) or 0
            elif typ == "Carry":
                loc, end = e.get("location"), e.get("carry", {}).get("end_location")
                if loc and end and end[0]-loc[0] >= 10: data[player]["progressions"] += 1
            elif typ == "Shot":
                data[player]["xg"] += e.get("shot", {}).get("statsbomb_xg", 0) or 0
                if e.get("shot", {}).get("outcome", {}).get("name") == "Goal": data[player]["goals"] += 1
    return data


def save_league_zscores(path, metrics):
    labels = [("xg", "xG / match"), ("shots", "Shots / match"), ("xg_per_shot", "xG / shot"),
              ("pass_pct", "Pass completion"), ("final_entries", "Final-third entries"),
              ("box_entries", "Penalty-area entries"), ("pressures", "Pressures"), ("obv", "Passing + carrying OBV")]
    teams = list(metrics)
    zvals = []
    for key, label in labels:
        vals = [metrics[t].get(key, 0) for t in teams]
        mean = sum(vals)/len(vals); sd = math.sqrt(sum((v-mean)**2 for v in vals)/max(len(vals), 1)) or 1
        zvals.append((label, (metrics[TEAM].get(key, 0)-mean)/sd))
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.22, 0.18, 0.62, 0.58], facecolor=NAVY)
    colors = [CYAN if z >= 0 else PINK for _, z in zvals]
    ax.barh(range(len(zvals)), [z for _, z in zvals], color=colors, height=.58)
    ax.set_yticks(range(len(zvals)), [l for l, _ in zvals]); ax.invert_yaxis()
    ax.axvline(0, color=WHITE, lw=1); ax.grid(axis="x", color=GRID, alpha=.65)
    ax.tick_params(colors=WHITE, labelsize=12, length=0)
    for spine in ax.spines.values(): spine.set_visible(False)
    for i, (_, z) in enumerate(zvals):
        ax.text(z - .05 if z >= 0 else z + .05, i, f"{z:+.2f}", color=WHITE, fontsize=11, fontweight="bold",
                ha="right" if z >= 0 else "left", va="center")
    plot_page_frame(fig, "BENCHMARKING | LEAGUE Z-SCORES", "Varaždin attacking and possession profile",
                    "2025/26 1. HNL | positive = above league average")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_league_beeswarm(path, metrics):
    specs = [("xg", "xG / match"), ("xg_per_shot", "xG / shot"), ("box_entries", "Box entries"),
             ("final_entries", "Final-third entries"), ("pressures", "Pressures"), ("obv", "OBV")]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.12, 0.18, 0.76, 0.58], facecolor=NAVY)
    teams = list(metrics)
    for row, (key, label) in enumerate(specs):
        vals = [metrics[t].get(key, 0) for t in teams]
        lo, hi = min(vals), max(vals); span = hi-lo or 1
        normalized = [(v-lo)/span for v in vals]
        for t, x in zip(teams, normalized):
            ax.scatter(x, row, s=180 if t == TEAM else 60, color=PINK if t == TEAM else CYAN,
                       edgecolor=WHITE if t == TEAM else NAVY, linewidth=1, alpha=.95)
        rank = 1 + sum(metrics[t].get(key, 0) > metrics[TEAM].get(key, 0) for t in teams)
        ax.text(1.03, row, f"{rank}/{len(teams)}", color=PINK, fontsize=11, fontweight="bold", va="center")
    ax.set_yticks(range(len(specs)), [label for _, label in specs]); ax.invert_yaxis()
    ax.set_xlim(-.05, 1.13); ax.set_xticks([0, .5, 1], ["LOW", "LEAGUE RANGE", "HIGH"])
    ax.tick_params(colors=WHITE, labelsize=12, length=0); ax.grid(axis="x", color=GRID, alpha=.55)
    for spine in ax.spines.values(): spine.set_visible(False)
    plot_page_frame(fig, "BENCHMARKING | LEAGUE DISTRIBUTIONS", "Where Varaždin sit within the HNL",
                    "pink = Varaždin | cyan = other teams | right label = league rank")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_player_value_bars(path, player_data):
    rows = sorted(player_data.items(), key=lambda z: z[1]["obv"] + z[1]["xt"], reverse=True)[:12]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.25, 0.17, 0.62, 0.60], facecolor=NAVY)
    y = list(range(len(rows))); raw_obv = [v["obv"] for _, v in rows]; raw_xt = [v["xt"] for _, v in rows]
    max_obv, max_xt = max(raw_obv) or 1, max(raw_xt) or 1
    obv = [max(0, v)/max_obv*100 for v in raw_obv]; xt = [v/max_xt*100 for v in raw_xt]
    ax.barh([v-.18 for v in y], obv, color=CYAN, height=.32, label="OBV index")
    ax.barh([v+.18 for v in y], xt, color=AMBER, height=.32, label="Passing xT index")
    ax.set_yticks(y, [p for p, _ in rows]); ax.invert_yaxis(); ax.axvline(0, color=WHITE, lw=.8)
    ax.set_xlim(0, 105)
    ax.tick_params(colors=WHITE, labelsize=11, length=0); ax.grid(axis="x", color=GRID, alpha=.55)
    for spine in ax.spines.values(): spine.set_visible(False)
    leg = ax.legend(frameon=False, loc="lower right"); [t.set_color(WHITE) for t in leg.get_texts()]
    plot_page_frame(fig, "PLAYER VALUE | OBV + xT", "On-ball value contribution - last three matches",
                    "each metric indexed separately: top player = 100 | OBV supplied by StatsBomb")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_player_scatter(path, player_data):
    rows = [(p, v) for p, v in player_data.items() if v["actions"] >= 20]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.12, 0.18, 0.72, 0.58], facecolor=NAVY)
    for p, v in rows:
        size = 100 + 900*(v["xg"]+v["xa"])
        ax.scatter(v["xt"], v["obv"], s=size, color=CYAN, edgecolor=WHITE, linewidth=1, alpha=.86)
        ax.text(v["xt"]+.01, v["obv"], p.split()[-1], color=WHITE, fontsize=9)
    ax.axhline(0, color=GRID); ax.axvline(0, color=GRID); ax.grid(color=GRID, alpha=.45)
    ax.set_xlabel("PASSING xT", color=WHITE, fontsize=12, fontweight="bold")
    ax.set_ylabel("STATSBOMB OBV", color=WHITE, fontsize=12, fontweight="bold")
    ax.tick_params(colors=MUTED); [sp.set_visible(False) for sp in ax.spines.values()]
    plot_page_frame(fig, "PLAYER VALUE | CREATOR EFFICIENCY", "Passing xT vs StatsBomb OBV",
                    "bubble size = xG + xG assisted | last three matches")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_obv_beeswarm(path, recent, events_by_id):
    actions = defaultdict(list)
    for match in recent:
        for e in events_by_id[match["match_id"]]:
            if e.get("team", {}).get("name") == TEAM and e.get("player") and e.get("type", {}).get("name") in {"Pass", "Carry"}:
                if e.get("obv_total_net") is not None: actions[e["player"]["name"]].append(e["obv_total_net"])
    players = sorted(actions, key=lambda p: sum(actions[p]), reverse=True)[:10]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.20, 0.18, 0.68, 0.58], facecolor=NAVY)
    for row, player in enumerate(players):
        vals = actions[player]
        for i, value in enumerate(vals):
            jitter = ((i*37)%17-8)/50
            ax.scatter(value, row+jitter, s=30, color=GREEN if value >= 0 else PINK, alpha=.55)
        ax.scatter(sum(vals), row, s=110, color=AMBER, edgecolor=WHITE, linewidth=1.1, zorder=5)
    ax.set_yticks(range(len(players)), players); ax.invert_yaxis(); ax.axvline(0, color=WHITE, lw=1)
    ax.tick_params(colors=WHITE, labelsize=11, length=0); ax.grid(axis="x", color=GRID, alpha=.5)
    for spine in ax.spines.values(): spine.set_visible(False)
    plot_page_frame(fig, "PLAYER VALUE | ACTION DISTRIBUTION", "Pass and carry OBV beeswarm",
                    "green = positive action | pink = negative | gold = player's cumulative OBV")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_player_ratings(path, player_data):
    players = [p for p, v in player_data.items() if v["actions"] >= 20]
    keys = ["obv", "xt", "xg", "xa", "final_entries", "box_entries", "progressions"]
    z = defaultdict(dict)
    for key in keys:
        vals = [player_data[p][key] for p in players]; mean = sum(vals)/len(vals); sd = math.sqrt(sum((v-mean)**2 for v in vals)/len(vals)) or 1
        for p in players: z[p][key] = (player_data[p][key]-mean)/sd
    ratings = []
    for p in players:
        score = .25*z[p]["obv"]+.20*z[p]["xt"]+.20*(z[p]["xg"]+z[p]["xa"])/2+.20*(z[p]["final_entries"]+z[p]["box_entries"])/2+.15*z[p]["progressions"]
        ratings.append((p, max(0, min(100, 50+15*score))))
    ratings.sort(key=lambda x: x[1], reverse=True); ratings = ratings[:12]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.25, 0.17, 0.60, 0.60], facecolor=NAVY)
    ax.barh(range(len(ratings)), [v for _, v in ratings], color=[CYAN if v >= 50 else PINK for _, v in ratings], height=.6)
    ax.set_yticks(range(len(ratings)), [p for p, _ in ratings]); ax.invert_yaxis(); ax.set_xlim(0, 100)
    ax.axvline(50, color=WHITE, lw=1, linestyle="--"); ax.tick_params(colors=WHITE, labelsize=11, length=0)
    ax.grid(axis="x", color=GRID, alpha=.5); [sp.set_visible(False) for sp in ax.spines.values()]
    for i, (_, value) in enumerate(ratings): ax.text(value+1, i, f"{value:.0f}", color=WHITE, fontsize=11, fontweight="bold", va="center")
    plot_page_frame(fig, "PLAYER RATING | COMPOSITE INDEX", "Three-match on-ball contribution rating",
                    "OBV 25% | xT 20% | xG+xA 20% | entries 20% | progression 15% | team-relative")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def possession_style_metrics(events, team=TEAM):
    poss = defaultdict(list)
    for e in events:
        if e.get("possession_team", {}).get("name") == team and e.get("possession") is not None:
            poss[e["possession"]].append(e)
    rows = []
    for pid, actions in poss.items():
        team_actions = [e for e in actions if e.get("team", {}).get("name") == team]
        if not team_actions:
            continue
        times = [e.get("minute", 0)*60+e.get("second", 0) for e in actions]
        passes = sum(e.get("type", {}).get("name") == "Pass" for e in team_actions)
        starts = [e.get("location") for e in team_actions if e.get("location")]
        ends = [event_end(e) or e.get("location") for e in team_actions if event_end(e) or e.get("location")]
        start_x = starts[0][0] if starts else 0
        max_x = max((p[0] for p in ends if p), default=start_x)
        rows.append({"duration": max(times)-min(times) if times else 0, "passes": passes,
                     "start_x": start_x, "max_x": max_x, "gain": max_x-start_x})
    return rows


def save_style_radar(path, metrics):
    specs = [("xg", "xG"), ("shots", "SHOTS"), ("xg_per_shot", "SHOT QUALITY"), ("pass_pct", "PASS %"),
             ("final_entries", "FINAL 3RD"), ("box_entries", "BOX ENTRIES"), ("pressures", "PRESSING"), ("obv", "OBV")]
    teams = list(metrics)
    percentiles = []
    for key, label in specs:
        value = metrics[TEAM].get(key, 0)
        rank = sum(metrics[t].get(key, 0) <= value for t in teams) / len(teams) * 100
        percentiles.append(rank)
    values = percentiles + [percentiles[0]]
    angles = [2*math.pi*i/len(specs) for i in range(len(specs))] + [0]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.23, 0.13, 0.54, 0.66], polar=True, facecolor=NAVY)
    ax.plot(angles, values, color=CYAN, lw=3); ax.fill(angles, values, color=CYAN, alpha=.20)
    ax.set_ylim(0, 100); ax.set_yticks([25, 50, 75, 100], ["25", "50", "75", "100"], color=MUTED, fontsize=9)
    ax.set_xticks(angles[:-1], [label for _, label in specs], color=WHITE, fontsize=11, fontweight="bold")
    ax.grid(color=GRID, alpha=.7); ax.spines["polar"].set_color(GRID)
    for angle, value in zip(angles[:-1], percentiles):
        ax.scatter(angle, value, s=90, color=PINK, edgecolor=WHITE, zorder=4)
    plot_page_frame(fig, "BENCHMARKING | STYLE RADAR", "Varaždin league-percentile profile",
                    "2025/26 1. HNL | outer ring = league-leading")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_match_kpi_heatmap(path, recent, events_by_id, all_shots):
    metrics = []
    labels = ["xG", "Shots", "Pass %", "Final 3rd entries", "Box entries", "Pressures", "OBV"]
    for match in recent:
        events = events_by_id[match["match_id"]]; passes = team_passes(events)
        shots = [s for s in all_shots if s["match_id"] == match["match_id"] and s["team"] == TEAM]
        metrics.append([
            sum(s["xg"] for s in shots), len(shots),
            sum(p["complete"] for p in passes)/max(len(passes), 1)*100,
            sum(p["complete"] and p["x"] < 80 <= p["end_x"] for p in passes),
            sum(p["complete"] and p["end_x"] >= 102 and 18 <= p["end_y"] <= 62 and not (p["x"] >= 102 and 18 <= p["y"] <= 62) for p in passes),
            sum(e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Pressure" for e in events),
            sum((e.get("obv_total_net") or 0) for e in events if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") in {"Pass", "Carry"})
        ])
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.18, 0.22, 0.68, 0.50], facecolor=NAVY)
    for col in range(len(labels)):
        vals = [row[col] for row in metrics]; mean = sum(vals)/3; sd = math.sqrt(sum((v-mean)**2 for v in vals)/3) or 1
        for row in range(3):
            z = (metrics[row][col]-mean)/sd
            color = CYAN if z > .35 else PINK if z < -.35 else PANEL
            ax.add_patch(plt.Rectangle((col, row), 1, 1, color=color, alpha=.85))
            ax.text(col+.5, row+.42, f"{metrics[row][col]:.2f}" if col in {0, 6} else f"{metrics[row][col]:.0f}",
                    color=WHITE, fontsize=12, fontweight="bold", ha="center", va="center")
            ax.text(col+.5, row+.70, f"z {z:+.1f}", color=NAVY if color != PANEL else MUTED, fontsize=8, ha="center")
    ax.set_xlim(0, len(labels)); ax.set_ylim(3, 0)
    ax.set_xticks([i+.5 for i in range(len(labels))], labels); ax.xaxis.tick_top()
    ax.set_yticks([i+.5 for i in range(3)], [f"{m['match_date'][5:]} {opponent(m)}" for m in recent])
    ax.tick_params(colors=WHITE, labelsize=10, length=0); [sp.set_visible(False) for sp in ax.spines.values()]
    plot_page_frame(fig, "CONSISTENCY | MATCH KPI HEATMAP", "How the last three performances differed",
                    "cell z-scores are relative only to these three matches")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_possession_distribution(path, recent, events_by_id):
    colors = [CYAN, PINK, AMBER]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.12, 0.20, 0.76, 0.54], facecolor=NAVY)
    bins = list(range(0, 41, 4))
    for match, color in zip(recent, colors):
        rows = possession_style_metrics(events_by_id[match["match_id"]])
        vals = [min(r["duration"], 40) for r in rows]
        ax.hist(vals, bins=bins, histtype="step", linewidth=3, color=color, density=True,
                label=f"{match['match_date'][5:]} {opponent(match)}")
    ax.set_xlabel("POSSESSION DURATION (SECONDS, CAPPED AT 40)", color=WHITE, fontsize=12, fontweight="bold")
    ax.set_ylabel("DENSITY", color=WHITE, fontsize=12, fontweight="bold")
    ax.tick_params(colors=MUTED); ax.grid(color=GRID, alpha=.5); [sp.set_visible(False) for sp in ax.spines.values()]
    leg = ax.legend(frameon=False); [t.set_color(WHITE) for t in leg.get_texts()]
    plot_page_frame(fig, "POSSESSION STYLE | DURATION DISTRIBUTION", "How long Varaždin keep each possession",
                    "last three matches | longer right tail indicates more sustained attacks")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_pass_distribution(path, recent, events_by_id):
    colors = [CYAN, PINK, AMBER]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.12, 0.20, 0.76, 0.54], facecolor=NAVY)
    bins = list(range(0, 61, 5))
    for match, color in zip(recent, colors):
        vals = [e.get("pass", {}).get("length", 0) for e in events_by_id[match["match_id"]]
                if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Pass"]
        ax.hist(vals, bins=bins, histtype="step", linewidth=3, color=color, density=True,
                label=f"{match['match_date'][5:]} {opponent(match)}")
    ax.set_xlabel("PASS LENGTH (STATSBOMB PITCH UNITS)", color=WHITE, fontsize=12, fontweight="bold")
    ax.set_ylabel("DENSITY", color=WHITE, fontsize=12, fontweight="bold")
    ax.tick_params(colors=MUTED); ax.grid(color=GRID, alpha=.5); [sp.set_visible(False) for sp in ax.spines.values()]
    leg = ax.legend(frameon=False); [t.set_color(WHITE) for t in leg.get_texts()]
    plot_page_frame(fig, "PASSING STYLE | LENGTH DISTRIBUTION", "Short circulation versus direct passing",
                    "all Varaždin passes in the last three matches")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_pass_direction(path, recent, events_by_id):
    colors = [CYAN, PINK, AMBER]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.28, 0.15, 0.50, 0.64], polar=True, facecolor=NAVY)
    edges = [(-math.pi + i*math.pi/6) for i in range(13)]
    centers = [(edges[i]+edges[i+1])/2 for i in range(12)]
    for match, color in zip(recent, colors):
        angles = [e.get("pass", {}).get("angle", 0) for e in events_by_id[match["match_id"]]
                  if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Pass"]
        counts = [sum(edges[i] <= a < edges[i+1] for a in angles) for i in range(12)]
        total = max(sum(counts), 1); counts = [c/total*100 for c in counts]
        ax.plot(centers+[centers[0]], counts+[counts[0]], color=color, lw=2.5,
                label=f"{match['match_date'][5:]} {opponent(match)}")
    ax.set_theta_zero_location("E"); ax.set_theta_direction(-1); ax.set_xticks([])
    ax.tick_params(colors=MUTED); ax.grid(color=GRID, alpha=.6); ax.spines["polar"].set_color(GRID)
    leg = ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(1.45, 1.1)); [t.set_color(WHITE) for t in leg.get_texts()]
    plot_page_frame(fig, "PASSING STYLE | DIRECTION ROSE", "Directional tendencies of Varaždin passing",
                    "right = forward toward opponent goal | share of passes by angular sector")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_pressure_performance(path, recent, events_by_id):
    player = defaultdict(lambda: defaultdict(float))
    for match in recent:
        for e in events_by_id[match["match_id"]]:
            if e.get("team", {}).get("name") != TEAM or not e.get("player") or not e.get("under_pressure"): continue
            p = e["player"]["name"]; typ = e.get("type", {}).get("name")
            if typ == "Pass":
                player[p]["passes"] += 1; player[p]["complete"] += "outcome" not in e.get("pass", {})
            if typ in {"Dispossessed", "Miscontrol"} or (typ == "Pass" and "outcome" in e.get("pass", {})):
                player[p]["losses"] += 1
    rows = [(p, v) for p, v in player.items() if v["passes"] >= 5]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.12, 0.20, 0.72, 0.54], facecolor=NAVY)
    for p, v in rows:
        pct = v["complete"]/v["passes"]*100
        ax.scatter(v["passes"], pct, s=90+v["losses"]*55, color=CYAN, edgecolor=WHITE, linewidth=1)
        ax.text(v["passes"]+.3, pct, p.split()[-1], color=WHITE, fontsize=9)
    ax.set_xlabel("PASSES ATTEMPTED UNDER PRESSURE", color=WHITE, fontsize=12, fontweight="bold")
    ax.set_ylabel("COMPLETION UNDER PRESSURE (%)", color=WHITE, fontsize=12, fontweight="bold")
    ax.tick_params(colors=MUTED); ax.grid(color=GRID, alpha=.5); [sp.set_visible(False) for sp in ax.spines.values()]
    plot_page_frame(fig, "PLAYER RELIABILITY | UNDER PRESSURE", "Passing volume versus retention under pressure",
                    "bubble size = pressured turnovers | minimum five pressured passes")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_risk_value_scatter(path, player_data):
    rows = [(p, v) for p, v in player_data.items() if v["actions"] >= 20]
    max_obv = max((max(0, v["obv"]) for _, v in rows), default=1) or 1
    max_xt = max((v["xt"] for _, v in rows), default=1) or 1
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.12, 0.20, 0.72, 0.54], facecolor=NAVY)
    for p, v in rows:
        value = 50*(max(0, v["obv"])/max_obv + v["xt"]/max_xt)
        ax.scatter(v["actions"], value, s=100+v["final_entries"]*30, color=AMBER, edgecolor=WHITE, linewidth=1)
        ax.text(v["actions"]+2, value, p.split()[-1], color=WHITE, fontsize=9)
    ax.set_xlabel("ON-BALL ACTIONS", color=WHITE, fontsize=12, fontweight="bold")
    ax.set_ylabel("NORMALIZED VALUE INDEX (OBV 50% + xT 50%)", color=WHITE, fontsize=12, fontweight="bold")
    ax.tick_params(colors=MUTED); ax.grid(color=GRID, alpha=.5); [sp.set_visible(False) for sp in ax.spines.values()]
    plot_page_frame(fig, "PLAYER ROLE | VOLUME AND VALUE", "On-ball involvement versus value contribution",
                    "bubble size = final-third entries | OBV and xT normalized separately before combining")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_territory_summary(path, recent, events_by_id):
    labels, field_tilt, deep_completions, opp_half = [], [], [], []
    for match in recent:
        events = events_by_id[match["match_id"]]; opp = opponent(match)
        team_att = sum(e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") in {"Pass", "Carry", "Shot"} and e.get("location", [0])[0] >= 80 for e in events)
        opp_att = sum(e.get("team", {}).get("name") == opp and e.get("type", {}).get("name") in {"Pass", "Carry", "Shot"} and e.get("location", [0])[0] >= 80 for e in events)
        field_tilt.append(team_att/max(team_att+opp_att, 1)*100)
        deep_completions.append(sum(e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Pass"
                                    and "outcome" not in e.get("pass", {}) and e.get("pass", {}).get("end_location", [0])[0] >= 100 for e in events))
        team_actions = [e for e in events if e.get("team", {}).get("name") == TEAM and e.get("location")]
        opp_half.append(sum(e["location"][0] >= 60 for e in team_actions)/max(len(team_actions), 1)*100)
        labels.append(f"{match['match_date'][5:]}\n{opponent(match)}")
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.12, 0.22, 0.74, 0.50], facecolor=NAVY)
    x = range(3); width=.24
    ax.bar([i-width for i in x], field_tilt, width, color=CYAN, label="Field tilt %")
    ax.bar(x, opp_half, width, color=AMBER, label="Actions in opponent half %")
    ax.bar([i+width for i in x], deep_completions, width, color=PINK, label="Deep completions")
    ax.set_xticks(list(x), labels); ax.tick_params(colors=WHITE, labelsize=11, length=0)
    ax.grid(axis="y", color=GRID, alpha=.5); [sp.set_visible(False) for sp in ax.spines.values()]
    leg = ax.legend(frameon=False); [t.set_color(WHITE) for t in leg.get_texts()]
    plot_page_frame(fig, "TERRITORY | MATCH COMPARISON", "Field tilt, opponent-half presence and deep completions",
                    "field tilt uses attacking-third pass/carry/shot actions")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def varazdin_opponent_events(matches, events_by_id):
    rows = []
    for match in matches:
        if TEAM not in {team_name(match, "home"), team_name(match, "away")}:
            continue
        opp = opponent(match)
        rows.extend((match, e) for e in events_by_id.get(match["match_id"], []) if e.get("team", {}).get("name") == opp)
    return rows


def save_vulnerability_sources(path, matches, events_by_id):
    agg = defaultdict(lambda: [0, 0, 0])
    for match, e in varazdin_opponent_events(matches, events_by_id):
        if e.get("type", {}).get("name") != "Shot": continue
        pattern = e.get("play_pattern", {}).get("name", "Other")
        label = {"Regular Play": "OPEN PLAY", "From Corner": "CORNER", "From Free Kick": "FREE KICK",
                 "From Throw In": "THROW-IN", "From Counter": "COUNTER"}.get(pattern, "OTHER")
        agg[label][0] += e.get("shot", {}).get("statsbomb_xg", 0) or 0
        agg[label][1] += 1
        agg[label][2] += e.get("shot", {}).get("outcome", {}).get("name") == "Goal"
    order = sorted(agg, key=lambda k: agg[k][0], reverse=True)
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([0.20, 0.18, 0.64, 0.58], facecolor=NAVY)
    vals = [agg[k][0] for k in order]
    bars = ax.barh(range(len(order)), vals, color=[CYAN, PINK, AMBER, GREEN, RED, "#A78BFA"][:len(order)], height=.62)
    ax.set_yticks(range(len(order)), order); ax.invert_yaxis(); ax.tick_params(colors=WHITE, labelsize=12, length=0)
    ax.grid(axis="x", color=GRID, alpha=.55); [sp.set_visible(False) for sp in ax.spines.values()]
    for i, k in enumerate(order):
        ax.text(vals[i]+.25, i, f"{vals[i]:.2f} xGA | {agg[k][1]} shots | {agg[k][2]} goals",
                color=WHITE, fontsize=11, fontweight="bold", va="center")
    plot_page_frame(fig, "HOW TO HURT VARAŽDIN | CHANCE SOURCE", "Opposition xG by attacking source",
                    "2025/26 season | restarts are separated from open play")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_conceded_danger_map(path, matches, events_by_id):
    fig, ax, pitch = combined_pitch_figure("Where Varaždin concede chances", "Season opposition shots | marker size = xG | goals outlined", "HOW TO HURT VARAŽDIN | SEASON MAP")
    shots = []
    for match, e in varazdin_opponent_events(matches, events_by_id):
        if e.get("type", {}).get("name") == "Shot" and e.get("location"):
            shots.append(e)
    for e in sorted(shots, key=lambda z: z.get("shot", {}).get("statsbomb_xg", 0) or 0):
        xg = e.get("shot", {}).get("statsbomb_xg", 0) or 0
        goal = e.get("shot", {}).get("outcome", {}).get("name") == "Goal"
        pitch.scatter(e["location"][0], e["location"][1], ax=ax, s=35+900*xg,
                      color=PINK if goal else CYAN, edgecolors=WHITE if goal else NAVY,
                      linewidth=1.2, alpha=.66)
    ax.axhline(32, color=AMBER, ls="--", lw=1); ax.axhline(48, color=AMBER, ls="--", lw=1)
    central_xg = sum((e.get("shot", {}).get("statsbomb_xg", 0) or 0) for e in shots if 32 <= e["location"][1] < 48)
    total_xg = sum((e.get("shot", {}).get("statsbomb_xg", 0) or 0) for e in shots)
    fig.text(.82, .48, f"{central_xg:.1f}", color=AMBER, fontsize=30, fontweight="bold")
    fig.text(.82, .445, f"CENTRAL xGA ({central_xg/max(total_xg,1)*100:.0f}%)", color=MUTED, fontsize=10, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_opponent_box_entries(path, matches, events_by_id):
    fig, ax, pitch = combined_pitch_figure("How opponents enter Varaždin's penalty area", "Season completed passes entering the box", "HOW TO HURT VARAŽDIN | SEASON MAP")
    colors = {"LEFT": CYAN, "CENTRAL": AMBER, "RIGHT": PINK}
    counts = defaultdict(int)
    for match, e in varazdin_opponent_events(matches, events_by_id):
        if e.get("type", {}).get("name") != "Pass" or not e.get("location") or "outcome" in e.get("pass", {}): continue
        end = e.get("pass", {}).get("end_location")
        if not end or not (end[0] >= 102 and 18 <= end[1] <= 62) or (e["location"][0] >= 102 and 18 <= e["location"][1] <= 62): continue
        side = "LEFT" if e["location"][1] < 26.7 else "RIGHT" if e["location"][1] > 53.3 else "CENTRAL"
        counts[side] += 1
        pitch.arrows(e["location"][0], e["location"][1], end[0], end[1], ax=ax, color=colors[side],
                     alpha=.12, width=.8, headwidth=3, headlength=3)
    for i, side in enumerate(["LEFT", "CENTRAL", "RIGHT"]):
        fig.text(.82, .55-i*.08, f"{counts[side]}", color=colors[side], fontsize=24, fontweight="bold")
        fig.text(.87, .56-i*.08, f"{side} ORIGIN", color=MUTED, fontsize=10, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_set_piece_matrix(path, matches, events_by_id):
    types = ["From Corner", "From Free Kick", "From Throw In"]
    labels = ["CORNERS", "FREE KICKS", "THROW-INS"]
    values = []
    for pattern in types:
        shots = [e for _, e in varazdin_opponent_events(matches, events_by_id)
                 if e.get("type", {}).get("name") == "Shot" and e.get("play_pattern", {}).get("name") == pattern]
        values.append([len(shots), sum(e.get("shot", {}).get("statsbomb_xg", 0) or 0 for e in shots),
                       sum(e.get("shot", {}).get("outcome", {}).get("name") == "Goal" for e in shots)])
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([.18, .24, .68, .44], facecolor=NAVY); ax.axis("off")
    cols = ["SHOTS", "xGA", "GOALS", "xGA / SHOT"]
    for j, col in enumerate(cols): ax.text(.35+j*.16, 1.04, col, color=MUTED, fontsize=12, fontweight="bold", ha="center")
    for i, (label, row) in enumerate(zip(labels, values)):
        y = .78-i*.28; ax.text(.03, y, label, color=WHITE, fontsize=15, fontweight="bold")
        display = [row[0], f"{row[1]:.2f}", row[2], f"{row[1]/max(row[0],1):.2f}"]
        for j, value in enumerate(display):
            color = [CYAN, AMBER, PINK][i]
            ax.add_patch(plt.Rectangle((.27+j*.16, y-.08), .14, .16, color=color, alpha=.84))
            ax.text(.34+j*.16, y, str(value), color=NAVY, fontsize=16, fontweight="bold", ha="center", va="center")
    plot_page_frame(fig, "HOW TO HURT VARAŽDIN | SET-PIECE MATRIX", "Restart vulnerability",
                    "season shots, xGA and goals conceded by restart type")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_second_phase_map(path, matches, events_by_id):
    fig, ax, pitch = combined_pitch_figure("Second-phase locations after restarts", "First opponent on-ball action after an attacking corner/free-kick delivery", "HOW TO HURT VARAŽDIN | SEASON MAP")
    colors = {"From Corner": PINK, "From Free Kick": AMBER}
    counts = defaultdict(int)
    for match in matches:
        if TEAM not in {team_name(match, "home"), team_name(match, "away")}: continue
        ev = events_by_id.get(match["match_id"], []); opp = opponent(match)
        for i, e in enumerate(ev):
            pattern = e.get("play_pattern", {}).get("name")
            if e.get("team", {}).get("name") != opp or e.get("type", {}).get("name") != "Pass" or pattern not in colors: continue
            required = "Corner" if pattern == "From Corner" else "Free Kick"
            if e.get("pass", {}).get("type", {}).get("name") != required: continue
            end = e.get("pass", {}).get("end_location")
            if pattern == "From Free Kick" and (not end or end[0] < 80): continue
            for z in ev[i+1:i+9]:
                if z.get("possession") != e.get("possession"): break
                if z.get("team", {}).get("name") == opp and z.get("location") and z.get("type", {}).get("name") in {"Pass", "Carry", "Shot", "Ball Receipt*"}:
                    pitch.scatter(z["location"][0], z["location"][1], ax=ax, s=45, color=colors[pattern], alpha=.42)
                    counts[pattern] += 1; break
    fig.text(.82, .50, str(counts["From Corner"]), color=PINK, fontsize=27, fontweight="bold")
    fig.text(.82, .465, "CORNER SECOND PHASES", color=MUTED, fontsize=10, fontweight="bold")
    fig.text(.82, .38, str(counts["From Free Kick"]), color=AMBER, fontsize=27, fontweight="bold")
    fig.text(.82, .345, "FREE-KICK SECOND PHASES", color=MUTED, fontsize=10, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_opponent_key_passes(path, matches, events_by_id):
    fig, ax, pitch = combined_pitch_figure("Opposition key-pass origins", "Season shot assists linked to resulting shot locations", "HOW TO HURT VARAŽDIN | SEASON MAP")
    n = 0; xga = 0
    for match in matches:
        if TEAM not in {team_name(match, "home"), team_name(match, "away")}: continue
        ev = events_by_id.get(match["match_id"], []); opp = opponent(match)
        shots = {e.get("id"): e for e in ev if e.get("team", {}).get("name") == opp and e.get("type", {}).get("name") == "Shot"}
        for e in ev:
            sid = e.get("pass", {}).get("assisted_shot_id")
            if e.get("team", {}).get("name") != opp or sid not in shots or not e.get("location"): continue
            shot = shots[sid]; val = shot.get("shot", {}).get("statsbomb_xg", 0) or 0
            pitch.arrows(e["location"][0], e["location"][1], shot["location"][0], shot["location"][1],
                         ax=ax, color=CYAN, alpha=.18, width=.8+5*val, headwidth=3.5, headlength=3.5)
            n += 1; xga += val
    fig.text(.82, .50, str(n), color=CYAN, fontsize=28, fontweight="bold"); fig.text(.82, .465, "ASSISTED SHOTS", color=MUTED, fontsize=10, fontweight="bold")
    fig.text(.82, .38, f"{xga:.1f}", color=PINK, fontsize=28, fontweight="bold"); fig.text(.82, .345, "xG ASSISTED", color=MUTED, fontsize=10, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_line_breaks(path, matches, events_by_id):
    fig, ax, pitch = combined_pitch_figure("Passes received behind Varaždin's block", "Proxy line breaks: completed opponent passes crossing x=80 or ending behind x=100", "HOW TO HURT VARAŽDIN | SEASON MAP")
    counts = defaultdict(int)
    for match, e in varazdin_opponent_events(matches, events_by_id):
        if e.get("type", {}).get("name") != "Pass" or "outcome" in e.get("pass", {}) or not e.get("location"): continue
        end = e.get("pass", {}).get("end_location")
        if not end: continue
        if e["location"][0] < 80 <= end[0]:
            color = CYAN; counts["midfield"] += 1
        elif e["location"][0] < 100 <= end[0]:
            color = PINK; counts["defence"] += 1
        else: continue
        pitch.arrows(e["location"][0], e["location"][1], end[0], end[1], ax=ax, color=color, alpha=.14, width=.8, headwidth=3, headlength=3)
    fig.text(.82, .50, str(counts["midfield"]), color=CYAN, fontsize=28, fontweight="bold"); fig.text(.82, .465, "INTO FINAL THIRD", color=MUTED, fontsize=10, fontweight="bold")
    fig.text(.82, .38, str(counts["defence"]), color=PINK, fontsize=28, fontweight="bold"); fig.text(.82, .345, "BEHIND DEFENCE", color=MUTED, fontsize=10, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_far_post_entries(path, matches, events_by_id):
    fig, ax, pitch = combined_pitch_figure("Weak-side and far-post entries", "Completed opponent deliveries from one flank to the opposite half of the box", "HOW TO HURT VARAŽDIN | SEASON MAP")
    left_to_right = right_to_left = 0
    for match, e in varazdin_opponent_events(matches, events_by_id):
        if e.get("type", {}).get("name") != "Pass" or "outcome" in e.get("pass", {}) or not e.get("location"): continue
        end = e.get("pass", {}).get("end_location")
        if not end or not (end[0] >= 102 and 18 <= end[1] <= 62): continue
        if e["location"][1] < 24 and end[1] > 40:
            color = CYAN; left_to_right += 1
        elif e["location"][1] > 56 and end[1] < 40:
            color = PINK; right_to_left += 1
        else: continue
        pitch.arrows(e["location"][0], e["location"][1], end[0], end[1], ax=ax, color=color, alpha=.35, width=1.2, headwidth=4, headlength=4)
    fig.text(.82, .50, str(left_to_right), color=CYAN, fontsize=28, fontweight="bold"); fig.text(.82, .465, "LEFT TO FAR SIDE", color=MUTED, fontsize=10, fontweight="bold")
    fig.text(.82, .38, str(right_to_left), color=PINK, fontsize=28, fontweight="bold"); fig.text(.82, .345, "RIGHT TO FAR SIDE", color=MUTED, fontsize=10, fontweight="bold")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_press_targets(path, recent, events_by_id):
    player = defaultdict(lambda: [0, 0, 0])
    for match in recent:
        for e in events_by_id[match["match_id"]]:
            if e.get("team", {}).get("name") != TEAM or not e.get("player") or not e.get("under_pressure"): continue
            p = e["player"]["name"]; player[p][0] += 1
            typ = e.get("type", {}).get("name")
            loss = typ in {"Dispossessed", "Miscontrol"} or (typ == "Pass" and "outcome" in e.get("pass", {}))
            player[p][1] += loss; player[p][2] += e.get("obv_total_net") or 0
    rows = sorted(player.items(), key=lambda z: (z[1][1], -z[1][2]), reverse=True)[:12]
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax = fig.add_axes([.25, .17, .61, .60], facecolor=NAVY)
    vals = [v[1]/max(v[0],1)*100 for _,v in rows]
    ax.barh(range(len(rows)), vals, color=[PINK if v >= 25 else AMBER for v in vals], height=.6)
    ax.set_yticks(range(len(rows)), [p for p,_ in rows]); ax.invert_yaxis(); ax.set_xlabel("PRESSURED LOSS RATE (%)", color=WHITE, fontweight="bold")
    ax.tick_params(colors=WHITE, length=0); ax.grid(axis="x", color=GRID, alpha=.5); [sp.set_visible(False) for sp in ax.spines.values()]
    for i, (_, v) in enumerate(rows): ax.text(vals[i]+1, i, f"{v[1]}/{v[0]} losses", color=WHITE, fontsize=10, va="center")
    plot_page_frame(fig, "HOW TO HURT VARAŽDIN | PRESSING TARGETS", "Players most vulnerable under pressure",
                    "last three matches | pressured losses divided by pressured actions")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_match_plan(path):
    img = base_image(); d = ImageDraw.Draw(img)
    header(d, "HOW TO HURT VARAŽDIN", "FC Hradec Králové match plan", "Evidence-led attacking priorities")
    items = [
        ("01", "WIN RESTARTS", "Corners, free kicks and throw-ins are repeatable routes into Varaždin's defensive box."),
        ("02", "DELIVER WIDE, FINISH CENTRAL", "Use wide and half-space origins, then attack the central corridor and penalty spot."),
        ("03", "ATTACK SECOND PHASES", "Keep numbers outside the box for recycled balls after the first set-piece clearance."),
        ("04", "PRESS THE RECEIVER", "Target the highest pressured-loss players immediately as they receive facing their own goal."),
        ("05", "FAR-POST OCCUPATION", "Hold the weak-side runner and attack beyond the back line when play develops from one flank."),
        ("06", "PERSIST, DON'T FORCE COUNTERS", "Transitions are not their main weakness; sustained territory and repeated entries are stronger routes."),
    ]
    for i, (num, title, body) in enumerate(items):
        y = 245 + i*88
        rounded_panel(d, (80, y, 1520, y+68), fill=PANEL, outline=GRID, radius=14)
        d.text((105, y+34), num, fill=CYAN, font=font(22, True), anchor="lm")
        d.text((165, y+22), title, fill=WHITE, font=font(20, True), anchor="lm")
        d.text((500, y+35), body, fill=MUTED, font=font(17), anchor="lm")
    footer(d, "StatsBomb event data | 2025/26 1. HNL | opposition vulnerability synthesis")
    img.save(path, quality=95)


def save_formation_analysis(path, matches, events_by_id):
    formations = defaultdict(lambda: [0, 0])
    recent = sorted([m for m in matches if TEAM in {team_name(m, "home"), team_name(m, "away")}], key=lambda m: m["match_date"])[-5:]
    avg_positions = []
    for match in matches:
        if TEAM not in {team_name(match, "home"), team_name(match, "away")}: continue
        ev = events_by_id.get(match["match_id"], [])
        xi = next((e for e in ev if e.get("team", {}).get("name") == TEAM and e.get("type", {}).get("name") == "Starting XI"), None)
        formation = str(xi.get("tactics", {}).get("formation", "Unknown")) if xi else "Unknown"
        formations[formation][0] += 1; formations[formation][1] += 90
    for match in recent:
        positions = defaultdict(list)
        for e in events_by_id[match["match_id"]]:
            if (e.get("team", {}).get("name") == TEAM and e.get("player") and e.get("location")
                    and e.get("type", {}).get("name") in {"Pass", "Carry", "Ball Receipt*"}):
                positions[e["player"]["name"]].append(e["location"])
        avg_positions.append({p: (sum(v[0] for v in pts)/len(pts), sum(v[1] for v in pts)/len(pts)) for p, pts in positions.items() if len(pts) >= 5})
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax1 = fig.add_axes([.06, .52, .38, .25], facecolor=NAVY)
    order = sorted(formations, key=lambda k: formations[k][0], reverse=True)
    ax1.barh(range(len(order)), [formations[k][0] for k in order], color=AMBER)
    ax1.set_yticks(range(len(order)), order); ax1.invert_yaxis(); ax1.tick_params(colors=WHITE, length=0)
    [sp.set_visible(False) for sp in ax1.spines.values()]; ax1.grid(axis="x", color=GRID, alpha=.5); ax1.set_title("FORMATION FREQUENCY", color=WHITE, fontweight="bold")
    for i, (match, pos) in enumerate(zip(recent, avg_positions)):
        ax = fig.add_axes([.47+i*.105, .19, .095, .49])
        pitch = VerticalPitch(pitch_type="statsbomb", pitch_color=NAVY, line_color=GRID, linewidth=.8)
        pitch.draw(ax=ax)
        for x, y in pos.values(): pitch.scatter(x, y, ax=ax, s=45, color=AMBER, alpha=.9)
        ax.set_title(match["match_date"][5:], color=MUTED, fontsize=8)
    plot_page_frame(fig, "REFERENCE VISUAL | FORMATION & POSITIONAL ANALYSIS", "Varaždin shape and positional tendencies",
                    "season formation frequency | average on-ball locations in the last five matches")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_progressive_density(path, matches, events_by_id):
    origins, receptions = [], []
    for match in matches:
        if TEAM not in {team_name(match, "home"), team_name(match, "away")}: continue
        for p in team_passes(events_by_id.get(match["match_id"], [])):
            if not p["complete"]: continue
            start = math.hypot(120-p["x"], 40-p["y"]); end = math.hypot(120-p["end_x"], 40-p["end_y"])
            threshold = 30 if p["x"] < 60 and p["end_x"] < 60 else 15 if p["x"] < 60 <= p["end_x"] else 10
            if start-end >= threshold:
                origins.append((p["x"], p["y"])); receptions.append((p["end_x"], p["end_y"]))
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    for i, (title, points) in enumerate([("ORIGIN LOCATIONS", origins), ("RECEPTION LOCATIONS", receptions)]):
        ax = fig.add_axes([.09+i*.45, .17, .37, .58])
        pitch = VerticalPitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1)
        pitch.draw(ax=ax)
        if points:
            bs = pitch.bin_statistic([p[0] for p in points], [p[1] for p in points], statistic="count", bins=(6, 8), normalize=True)
            pitch.heatmap(bs, ax=ax, cmap="YlOrBr", alpha=.8)
        ax.set_title(title, color=WHITE, fontsize=13, fontweight="bold")
    plot_page_frame(fig, "REFERENCE VISUAL | PROGRESSIVE PASS DENSITY", "Where Varaždin progression starts and finishes",
                    "season progressive-pass origins and reception locations")
    fig.savefig(path, facecolor=NAVY, dpi=100); plt.close(fig)


def save_switches_analysis(path, matches, events_by_id):
    metrics = season_team_metrics(matches, events_by_id); team_counts = defaultdict(int); player = defaultdict(int); lines = []
    for match in matches:
        ev = events_by_id.get(match["match_id"], [])
        for e in ev:
            if e.get("type", {}).get("name") == "Pass" and e.get("pass", {}).get("switch"):
                t = e.get("team", {}).get("name"); team_counts[t] += 1
                if t == TEAM and e.get("location") and e.get("pass", {}).get("end_location"):
                    player[e.get("player", {}).get("name", "Unknown")] += 1
                    lines.append((e["location"], e["pass"]["end_location"]))
    games = defaultdict(int)
    for m in matches: games[team_name(m,"home")] += 1; games[team_name(m,"away")] += 1
    rates = sorted(((t, n/max(games[t],1)) for t,n in team_counts.items()), key=lambda z:z[1], reverse=True)
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=NAVY)
    ax1 = fig.add_axes([.07,.54,.84,.18], facecolor=NAVY)
    ax1.scatter(range(len(rates)), [v for _,v in rates], color=[AMBER if t==TEAM else MUTED for t,v in rates], s=[140 if t==TEAM else 35 for t,v in rates])
    ax1.axhline(next((v for t,v in rates if t==TEAM),0), color=AMBER, ls="--"); ax1.set_xticks([]); ax1.tick_params(colors=MUTED); [sp.set_visible(False) for sp in ax1.spines.values()]
    ax2 = fig.add_axes([.08,.13,.38,.34]); pitch=Pitch(pitch_type="statsbomb", pitch_color="#0B4B49", line_color=WHITE, linewidth=1); pitch.draw(ax=ax2)
    for a,b in lines: pitch.arrows(a[0],a[1],b[0],b[1],ax=ax2,color=AMBER,alpha=.25,width=.8,headwidth=3,headlength=3)
    ax3=fig.add_axes([.55,.13,.35,.34],facecolor=NAVY); top=sorted(player.items(),key=lambda z:z[1],reverse=True)[:10]
    ax3.barh(range(len(top)),[v for _,v in top],color=AMBER);ax3.set_yticks(range(len(top)),[p for p,_ in top]);ax3.invert_yaxis();ax3.tick_params(colors=WHITE,length=0);[sp.set_visible(False) for sp in ax3.spines.values()]
    plot_page_frame(fig,"REFERENCE VISUAL | SWITCHES OF PLAY","Switch frequency, spatial distribution and top contributors","season league ranking and Varaždin switch map")
    fig.savefig(path,facecolor=NAVY,dpi=100);plt.close(fig)


def save_cutback_zones(path, matches, events_by_id):
    pts=[]
    for m in matches:
        if TEAM not in {team_name(m,"home"),team_name(m,"away")}:continue
        for e in events_by_id.get(m["match_id"],[]):
            if e.get("team",{}).get("name")==TEAM and e.get("type",{}).get("name")=="Pass" and e.get("pass",{}).get("cut_back") and e.get("pass",{}).get("end_location"):
                pts.append(e["pass"]["end_location"])
    fig=plt.figure(figsize=(16,9),dpi=100,facecolor=NAVY);ax=fig.add_axes([.25,.15,.5,.62])
    pitch=VerticalPitch(pitch_type="statsbomb",half=True,pitch_color="#0B4B49",line_color=WHITE,linewidth=1.4);pitch.draw(ax=ax)
    if pts:
        bs=pitch.bin_statistic([p[0] for p in pts],[p[1] for p in pts],statistic="count",bins=(5,4),normalize=True);pitch.heatmap(bs,ax=ax,cmap="YlOrBr",alpha=.75)
        pitch.scatter([p[0] for p in pts],[p[1] for p in pts],ax=ax,s=40,color=WHITE,alpha=.55)
    plot_page_frame(fig,"REFERENCE VISUAL | CUTBACK RECEPTION ZONES","Where Varaždin cutbacks arrive","season successful and unsuccessful cutback end locations")
    fig.savefig(path,facecolor=NAVY,dpi=100);plt.close(fig)


def save_long_ball_targets(path, matches, events_by_id):
    player=defaultdict(int);pts=[]
    for m in matches:
        if TEAM not in {team_name(m,"home"),team_name(m,"away")}:continue
        for e in events_by_id.get(m["match_id"],[]):
            p=e.get("pass",{})
            if e.get("team",{}).get("name")==TEAM and e.get("type",{}).get("name")=="Pass" and p.get("length",0)>=30 and p.get("end_location"):
                name=p.get("recipient",{}).get("name")
                if not name: continue
                player[name]+=1;pts.append((p["end_location"],name))
    fig,ax,pitch=combined_pitch_figure("Long-ball targets","Season pass receptions from balls travelling at least 30 pitch units","REFERENCE VISUAL | TARGET ANALYSIS")
    top=dict(sorted(player.items(),key=lambda z:z[1],reverse=True)[:8]); colors={p:[CYAN,PINK,AMBER,GREEN,"#A78BFA",RED,WHITE,MUTED][i] for i,p in enumerate(top)}
    for loc,name in pts:pitch.scatter(loc[0],loc[1],ax=ax,s=50,color=colors.get(name,MUTED),alpha=.45,edgecolors=WHITE,linewidth=.3)
    for i,(p,n) in enumerate(top.items()):fig.text(.82,.65-i*.055,f"{n:>3}  {p}",color=colors[p],fontsize=9.5,fontweight="bold")
    fig.savefig(path,facecolor=NAVY,dpi=100);plt.close(fig)


def save_goal_kick_receivers(path, matches, events_by_id):
    short=defaultdict(int);long=defaultdict(int);pts=[]
    for m in matches:
        if TEAM not in {team_name(m,"home"),team_name(m,"away")}:continue
        for e in events_by_id.get(m["match_id"],[]):
            p=e.get("pass",{})
            if e.get("team",{}).get("name")==TEAM and e.get("type",{}).get("name")=="Pass" and p.get("type",{}).get("name")=="Goal Kick" and p.get("end_location"):
                name=p.get("recipient",{}).get("name")
                if not name: continue
                (short if p.get("length",0)<30 else long)[name]+=1;pts.append((p["end_location"],name))
    fig,ax,pitch=combined_pitch_figure("Goal-kick end locations and receivers","Season goal kicks | receiver colors and short/long rankings","REFERENCE VISUAL | GOAL-KICK RECEIVERS")
    names=sorted(set(short)|set(long),key=lambda p:short[p]+long[p],reverse=True)[:12];palette=[CYAN,PINK,AMBER,GREEN,"#A78BFA",RED,WHITE,MUTED,"#55AADD","#DD77AA","#99CC55","#CC9955"];colors=dict(zip(names,palette))
    for loc,name in pts:pitch.scatter(loc[0],loc[1],ax=ax,s=55,color=colors.get(name,MUTED),edgecolors=WHITE,linewidth=.4,alpha=.7)
    for i,p in enumerate(names[:6]):fig.text(.81,.68-i*.05,f"{p}: {short[p]} short | {long[p]} long",color=colors[p],fontsize=9)
    fig.savefig(path,facecolor=NAVY,dpi=100);plt.close(fig)


def save_zone_reception_rankings(path, matches, events_by_id):
    games=defaultdict(int);mid=defaultdict(int);final=defaultdict(int);vplayers=defaultdict(lambda:[0,0])
    for m in matches:
        h,a=team_name(m,"home"),team_name(m,"away");games[h]+=1;games[a]+=1
        for e in events_by_id.get(m["match_id"],[]):
            if e.get("type",{}).get("name")!="Pass" or "outcome" in e.get("pass",{}) or not e.get("pass",{}).get("end_location"):continue
            t=e.get("team",{}).get("name");x,y=e["pass"]["end_location"][:2]
            hs=16<=y<32 or 48<=y<64
            if hs and 40<=x<80:mid[t]+=1
            if hs and x>=80:final[t]+=1
            if t==TEAM and hs:
                rec=e.get("pass",{}).get("recipient",{}).get("name","Unknown")
                if 40<=x<80:vplayers[rec][0]+=1
                elif x>=80:vplayers[rec][1]+=1
    fig=plt.figure(figsize=(16,9),dpi=100,facecolor=NAVY)
    for j,(title,data,color) in enumerate([("MIDDLE-THIRD HALF-SPACE RECEPTIONS",mid,CYAN),("FINAL-THIRD HALF-SPACE RECEPTIONS",final,AMBER)]):
        ax=fig.add_axes([.08+j*.47,.22,.4,.5],facecolor=NAVY);rates=sorted(((t,n/max(games[t],1)) for t,n in data.items()),key=lambda z:z[1],reverse=True)
        ax.barh(range(len(rates)),[v for _,v in rates],color=[color if t==TEAM else PANEL for t,v in rates]);ax.set_yticks(range(len(rates)),[t for t,v in rates]);ax.invert_yaxis();ax.tick_params(colors=WHITE,labelsize=8,length=0);[sp.set_visible(False) for sp in ax.spines.values()];ax.set_title(title,color=WHITE,fontsize=11,fontweight="bold")
    plot_page_frame(fig,"REFERENCE VISUAL | HALF-SPACE RECEPTION RANKINGS","League context for middle- and final-third half-space access","receptions per match | Varaždin highlighted")
    fig.savefig(path,facecolor=NAVY,dpi=100);plt.close(fig)


def save_verticality(path, matches, events_by_id):
    games=defaultdict(int);gain=defaultdict(float);passes=defaultdict(int)
    for m in matches:
        games[team_name(m,"home")]+=1;games[team_name(m,"away")]+=1
        for e in events_by_id.get(m["match_id"],[]):
            if e.get("type",{}).get("name")=="Pass" and "outcome" not in e.get("pass",{}) and e.get("location") and e.get("pass",{}).get("end_location"):
                t=e.get("team",{}).get("name");gain[t]+=max(0,e["pass"]["end_location"][0]-e["location"][0]);passes[t]+=1
    rates=sorted(((t,gain[t]/max(passes[t],1)) for t in gain),key=lambda z:z[1],reverse=True)
    fig=plt.figure(figsize=(16,9),dpi=100,facecolor=NAVY);ax=fig.add_axes([.22,.16,.63,.62],facecolor=NAVY)
    ax.barh(range(len(rates)),[v for _,v in rates],color=[AMBER if t==TEAM else PANEL for t,v in rates]);ax.set_yticks(range(len(rates)),[t for t,v in rates]);ax.invert_yaxis();ax.tick_params(colors=WHITE,length=0);ax.grid(axis="x",color=GRID,alpha=.5);[sp.set_visible(False) for sp in ax.spines.values()]
    plot_page_frame(fig,"REFERENCE VISUAL | TEAM VERTICALITY","Average forward distance per completed pass","2025/26 HNL league ranking")
    fig.savefig(path,facecolor=NAVY,dpi=100);plt.close(fig)


def save_sequence_involvement(path, matches, events_by_id):
    zones=[[0,0,0] for _ in range(3)];players=defaultdict(lambda:[0,0,0])
    vm=[m for m in matches if TEAM in {team_name(m,"home"),team_name(m,"away")}]
    for m in vm:
        ev=events_by_id.get(m["match_id"],[]);shotposs={e.get("possession") for e in ev if e.get("team",{}).get("name")==TEAM and e.get("type",{}).get("name")=="Shot"}
        for e in ev:
            if e.get("possession") not in shotposs or e.get("team",{}).get("name")!=TEAM or not e.get("player") or not e.get("location"):continue
            z=0 if e["location"][0]<40 else 1 if e["location"][0]<80 else 2;players[e["player"]["name"]][z]+=1
    top=sorted(players.items(),key=lambda z:sum(z[1]),reverse=True)[:15]
    fig=plt.figure(figsize=(16,9),dpi=100,facecolor=NAVY);ax=fig.add_axes([.31,.16,.58,.62],facecolor=NAVY);y=range(len(top));left=[0]*len(top)
    for j,(label,color) in enumerate([("DEFENSIVE THIRD",GREEN),("MIDDLE THIRD",AMBER),("FINAL THIRD",PINK)]):
        vals=[v[j]/max(len(vm),1) for _,v in top];ax.barh(y,vals,left=left,color=color,label=label);left=[a+b for a,b in zip(left,vals)]
    ax.set_yticks(y,[p for p,v in top]);ax.invert_yaxis();ax.tick_params(colors=WHITE,length=0);[sp.set_visible(False) for sp in ax.spines.values()];leg=ax.legend(frameon=False);[t.set_color(WHITE) for t in leg.get_texts()]
    plot_page_frame(fig,"REFERENCE VISUAL | ATTACKING SEQUENCE INVOLVEMENT","Player actions in possessions ending with a shot","stacked by pitch third | per match")
    fig.savefig(path,facecolor=NAVY,dpi=100);plt.close(fig)


def save_finishing_scatter(path, matches, events_by_id):
    games=defaultdict(int);shots=defaultdict(int);xg=defaultdict(float);goals=defaultdict(int)
    for m in matches:
        games[team_name(m,"home")]+=1;games[team_name(m,"away")]+=1
        for e in events_by_id.get(m["match_id"],[]):
            if e.get("type",{}).get("name")=="Shot" and e.get("shot",{}).get("type",{}).get("name")!="Penalty":
                t=e.get("team",{}).get("name");shots[t]+=1;xg[t]+=e.get("shot",{}).get("statsbomb_xg",0) or 0;goals[t]+=e.get("shot",{}).get("outcome",{}).get("name")=="Goal"
    teams=list(shots);fig=plt.figure(figsize=(16,9),dpi=100,facecolor=NAVY);ax=fig.add_axes([.12,.18,.74,.58],facecolor=NAVY)
    for t in teams:
        xx=xg[t]/max(shots[t],1);yy=goals[t]/max(games[t],1)*100
        ax.scatter(xx,yy,s=170 if t==TEAM else 60,color=AMBER if t==TEAM else MUTED,edgecolor=WHITE if t==TEAM else NAVY)
        ax.text(xx+.002,yy,t,color=WHITE if t==TEAM else MUTED,fontsize=8)
    ax.set_xlabel("NON-PENALTY xG PER SHOT",color=WHITE,fontweight="bold");ax.set_ylabel("NON-PENALTY GOALS PER 100 MATCHES",color=WHITE,fontweight="bold");ax.tick_params(colors=MUTED);ax.grid(color=GRID,alpha=.5);[sp.set_visible(False) for sp in ax.spines.values()]
    plot_page_frame(fig,"REFERENCE VISUAL | FINISHING EFFICIENCY","Non-penalty conversion versus xG per shot","2025/26 HNL league comparison")
    fig.savefig(path,facecolor=NAVY,dpi=100);plt.close(fig)


def save_defensive_line_height(path, matches, events_by_id):
    games=defaultdict(int);xs=defaultdict(list)
    for m in matches:
        games[team_name(m,"home")]+=1;games[team_name(m,"away")]+=1
        for e in events_by_id.get(m["match_id"],[]):
            if e.get("type",{}).get("name") in {"Interception","Block","Clearance","Duel","Pressure"} and e.get("location"):
                xs[e.get("team",{}).get("name")].append(e["location"][0])
    vals=sorted(((t,sum(v)/len(v)) for t,v in xs.items() if v),key=lambda z:z[1],reverse=True)
    fig=plt.figure(figsize=(16,9),dpi=100,facecolor=NAVY);ax=fig.add_axes([.23,.15,.62,.64],facecolor=NAVY)
    ax.barh(range(len(vals)),[v for _,v in vals],color=[AMBER if t==TEAM else PANEL for t,v in vals]);ax.set_yticks(range(len(vals)),[t for t,v in vals]);ax.invert_yaxis();ax.tick_params(colors=WHITE,length=0);ax.grid(axis="x",color=GRID,alpha=.5);[sp.set_visible(False) for sp in ax.spines.values()]
    plot_page_frame(fig,"REFERENCE VISUAL | DEFENSIVE LINE HEIGHT","Average location of defensive actions","proxy for team compactness and defensive-line height")
    fig.savefig(path,facecolor=NAVY,dpi=100);plt.close(fig)


def save_line_breaking_players(path, matches, events_by_id):
    players=defaultdict(lambda:[0,0,0])
    for m in matches:
        if TEAM not in {team_name(m,"home"),team_name(m,"away")}:continue
        for e in events_by_id.get(m["match_id"],[]):
            if e.get("team",{}).get("name")!=TEAM or e.get("type",{}).get("name")!="Pass" or "outcome" in e.get("pass",{}) or not e.get("location") or not e.get("pass",{}).get("end_location"):continue
            x=e["location"][0];ex=e["pass"]["end_location"][0];p=e.get("player",{}).get("name","Unknown")
            if x<40<=ex:players[p][0]+=1
            if x<80<=ex:players[p][1]+=1
            if x<100<=ex:players[p][2]+=1
    top=sorted(players.items(),key=lambda z:sum(z[1]),reverse=True)[:15]
    fig=plt.figure(figsize=(16,9),dpi=100,facecolor=NAVY);ax=fig.add_axes([.29,.16,.60,.62],facecolor=NAVY);y=range(len(top));left=[0]*len(top)
    for j,(label,color) in enumerate([("FIRST LINE",GREEN),("MIDFIELD LINE",CYAN),("LAST LINE",AMBER)]):
        vals=[v[j] for _,v in top];ax.barh(y,vals,left=left,color=color,label=label);left=[a+b for a,b in zip(left,vals)]
    ax.set_yticks(y,[p for p,v in top]);ax.invert_yaxis();ax.tick_params(colors=WHITE,length=0);ax.grid(axis="x",color=GRID,alpha=.5);[sp.set_visible(False) for sp in ax.spines.values()];leg=ax.legend(frameon=False);[t.set_color(WHITE) for t in leg.get_texts()]
    plot_page_frame(fig,"REFERENCE VISUAL | LINE-BREAKING PROGRESSION","Progression by line broken","completed pass proxies crossing x=40, x=80 and x=100")
    fig.savefig(path,facecolor=NAVY,dpi=100);plt.close(fig)


def save_possession_field_tilt_scatter(path, matches, events_by_id):
    passes=defaultdict(int);completed=defaultdict(int);att=defaultdict(int);games=defaultdict(int)
    for m in matches:
        h,a=team_name(m,"home"),team_name(m,"away");games[h]+=1;games[a]+=1
        for e in events_by_id.get(m["match_id"],[]):
            t=e.get("team",{}).get("name")
            if e.get("type",{}).get("name")=="Pass":
                passes[t]+=1;completed[t]+=("outcome" not in e.get("pass",{}))
            if e.get("type",{}).get("name") in {"Pass","Carry","Shot"} and e.get("location") and e["location"][0]>=80:att[t]+=1
    teams=list(games);total_pass=sum(completed.values());total_att=sum(att.values())
    fig=plt.figure(figsize=(16,9),dpi=100,facecolor=NAVY);ax=fig.add_axes([.13,.18,.73,.58],facecolor=NAVY)
    for t in teams:
        x=completed[t]/max(total_pass,1)*100;y=att[t]/max(total_att,1)*100
        ax.scatter(x,y,s=180 if t==TEAM else 65,color=AMBER if t==TEAM else MUTED,edgecolor=WHITE if t==TEAM else NAVY)
        ax.text(x+.08,y,t,color=WHITE if t==TEAM else MUTED,fontsize=8)
    ax.set_xlabel("SHARE OF LEAGUE COMPLETED PASSES (%)",color=WHITE,fontweight="bold");ax.set_ylabel("SHARE OF LEAGUE FINAL-THIRD ACTIONS (%)",color=WHITE,fontweight="bold");ax.tick_params(colors=MUTED);ax.grid(color=GRID,alpha=.5);[sp.set_visible(False) for sp in ax.spines.values()]
    plot_page_frame(fig,"REFERENCE VISUAL | POSSESSION VS FIELD TILT","League possession and territorial dominance","completed-pass share versus final-third action share")
    fig.savefig(path,facecolor=NAVY,dpi=100);plt.close(fig)


def poisson(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def save_probability(path, xgf, xga):
    img = base_image()
    d = ImageDraw.Draw(img)
    header(d, "SHOOTING | SCORELINE MODEL", "xG scoreline probability matrix", f"Neutral opposition-only baseline: Varaždin λ={xgf:.2f}, opponent λ={xga:.2f}")
    left, top, cell = 360, 275, 92
    max_goals = 5
    probs = [[poisson(i, xgf) * poisson(j, xga) for j in range(max_goals + 1)] for i in range(max_goals + 1)]
    maxp = max(max(r) for r in probs)
    d.text((left + cell * 3, top - 105), "OPPONENT GOALS", fill=MUTED, font=font(20, True), anchor="ma")
    d.text((left - 140, top + cell * 3), "VARAŽDIN GOALS", fill=MUTED, font=font(20, True), anchor="mm")
    for j in range(max_goals + 1):
        d.text((left + j*cell + cell/2, top - 42), str(j), fill=WHITE, font=font(22, True), anchor="mm")
    for i in range(max_goals + 1):
        d.text((left - 42, top + i*cell + cell/2), str(i), fill=WHITE, font=font(22, True), anchor="mm")
        for j in range(max_goals + 1):
            p = probs[i][j]
            intensity = p / maxp
            rgb = tuple(int(int(NAVY_2[k:k+2], 16) * (1-intensity) + int(CYAN[k:k+2], 16) * intensity) for k in (1,3,5))
            d.rounded_rectangle((left+j*cell+4, top+i*cell+4, left+(j+1)*cell-4, top+(i+1)*cell-4), radius=12, fill=rgb)
            d.text((left+j*cell+cell/2, top+i*cell+cell/2), f"{p*100:.1f}%", fill=WHITE, font=font(19, True), anchor="mm")
    home_win = sum(probs[i][j] for i in range(6) for j in range(6) if i > j)
    draw = sum(probs[i][i] for i in range(6))
    away_win = sum(probs[i][j] for i in range(6) for j in range(6) if i < j)
    outcomes = [("VARAŽDIN WIN", home_win, CYAN), ("DRAW", draw, AMBER), ("OPPONENT WIN", away_win, PINK)]
    for idx, (label, val, color) in enumerate(outcomes):
        y = 310 + idx * 150
        rounded_panel(d, (1040, y, 1450, y + 112), outline=color)
        d.text((1070, y + 22), label, fill=MUTED, font=font(18, True))
        d.text((1415, y + 58), f"{val*100:.0f}%", fill=color, font=font(38, True), anchor="ra")
    d.text((1040, 760), "Tail outcomes above 5 goals are excluded from displayed totals.", fill=MUTED, font=font(15))
    footer(d)
    img.save(path, quality=95)


def save_scatter(path, stats):
    img = base_image()
    d = ImageDraw.Draw(img)
    header(d, "SHOOTING | LEAGUE CONTEXT", "Shots per 90 vs xG per 90", "2025/26 1. HNL - team attacking output")
    chart = (160, 255, 1450, 740)
    x0, y0, x1, y1 = chart
    xs = [v["shots90"] for v in stats.values()]
    ys = [v["xg90"] for v in stats.values()]
    xmin, xmax = min(xs)-0.7, max(xs)+0.7
    ymin, ymax = min(ys)-0.12, max(ys)+0.12
    avgx, avgy = sum(xs)/len(xs), sum(ys)/len(ys)
    def pos(x, y):
        return x0+(x-xmin)/(xmax-xmin)*(x1-x0), y1-(y-ymin)/(ymax-ymin)*(y1-y0)
    ax, ay = pos(avgx, avgy)
    d.line((ax, y0, ax, y1), fill=GRID, width=2)
    d.line((x0, ay, x1, ay), fill=GRID, width=2)
    d.text((ax+8, y0+10), "LEAGUE AVG SHOTS", fill=MUTED, font=font(14, True))
    d.text((x0+8, ay-24), "LEAGUE AVG xG", fill=MUTED, font=font(14, True))
    for t, v in stats.items():
        x, y = pos(v["shots90"], v["xg90"])
        focus = t == TEAM
        r = 18 if focus else 11
        d.ellipse((x-r, y-r, x+r, y+r), fill=PINK if focus else CYAN, outline=WHITE if focus else None, width=3)
        label = "VARAŽDIN" if focus else t.replace("HNK ", "").replace("Lokomotiva Zagreb", "Lokomotiva")
        d.text((x+16, y-12), label, fill=WHITE if focus else MUTED, font=font(16, focus))
    for i in range(5):
        val = xmin + (xmax-xmin)*i/4
        xx, _ = pos(val, ymin)
        d.text((xx, y1+16), f"{val:.1f}", fill=MUTED, font=font(15), anchor="ma")
        valy = ymin + (ymax-ymin)*i/4
        _, yy = pos(xmin, valy)
        d.text((x0-15, yy), f"{valy:.1f}", fill=MUTED, font=font(15), anchor="rm")
    d.text(((x0+x1)/2, y1+54), "SHOTS PER 90", fill=WHITE, font=font(18, True), anchor="ma")
    d.text((x0-95, (y0+y1)/2), "xG PER 90", fill=WHITE, font=font(18, True), anchor="mm")
    footer(d)
    img.save(path, quality=95)


def shot_category(s):
    if s["shot_type"] == "Penalty":
        return "Penalty"
    p = s["play_pattern"]
    if p == "From Corner":
        return "Corner"
    if p == "From Free Kick" or s["shot_type"] == "Free Kick":
        return "Free kick"
    if p in {"From Throw In", "From Keeper", "Other"}:
        return "Other restart"
    return "Open play"


def save_xg_type(path, season_shots):
    img = base_image()
    d = ImageDraw.Draw(img)
    header(d, "SHOOTING | CHANCE SOURCE", "xG by chance type", "Varaždin season totals; share of total expected goals")
    agg = defaultdict(lambda: [0, 0])
    for s in season_shots:
        cat = shot_category(s)
        agg[cat][0] += s["xg"]
        agg[cat][1] += 1
    order = sorted(agg, key=lambda k: agg[k][0], reverse=True)
    total = sum(v[0] for v in agg.values())
    maxv = max(v[0] for v in agg.values())
    colors = [CYAN, PINK, AMBER, GREEN, RED]
    for i, cat in enumerate(order):
        y = 270 + i * 105
        xg, shots = agg[cat]
        d.text((125, y+22), cat.upper(), fill=WHITE, font=font(21, True))
        d.rounded_rectangle((400, y, 1260, y+56), radius=16, fill=NAVY_2)
        width = 860*xg/maxv
        d.rounded_rectangle((400, y, 400+width, y+56), radius=16, fill=colors[i % len(colors)])
        d.text((1285, y+28), f"{xg:.2f} xG", fill=WHITE, font=font(22, True), anchor="lm")
        d.text((400, y+72), f"{shots} shots  |  {xg/max(shots,1):.2f} xG/shot  |  {xg/total*100:.0f}% share", fill=MUTED, font=font(16))
    rounded_panel(d, (1120, 720, 1480, 805), outline=CYAN)
    d.text((1150, 740), "TOTAL SEASON xG", fill=MUTED, font=font(16, True))
    d.text((1445, 770), f"{total:.2f}", fill=CYAN, font=font(30, True), anchor="ra")
    footer(d)
    img.save(path, quality=95)


def save_ppg_index(path, stats):
    img = base_image()
    d = ImageDraw.Draw(img)
    header(d, "SHOOTING | OUTPUT EFFICIENCY", "Points per game vs shooting index", "Shooting index = 70% xG/90 + 30% shots/90; league average = 100")
    chart = (160, 255, 1450, 740)
    x0, y0, x1, y1 = chart
    xs = [v["shooting_index"] for v in stats.values()]
    ys = [v["ppg"] for v in stats.values()]
    xmin, xmax = min(xs)-6, max(xs)+6
    ymin, ymax = max(0, min(ys)-0.15), max(ys)+0.15
    def pos(x, y):
        return x0+(x-xmin)/(xmax-xmin)*(x1-x0), y1-(y-ymin)/(ymax-ymin)*(y1-y0)
    ax, ay = pos(100, sum(ys)/len(ys))
    d.line((ax, y0, ax, y1), fill=GRID, width=2)
    d.line((x0, ay, x1, ay), fill=GRID, width=2)
    for t, v in stats.items():
        x, y = pos(v["shooting_index"], v["ppg"])
        focus = t == TEAM
        r = 18 if focus else 11
        d.ellipse((x-r, y-r, x+r, y+r), fill=PINK if focus else CYAN, outline=WHITE if focus else None, width=3)
        label = "VARAŽDIN" if focus else t.replace("HNK ", "").replace("Lokomotiva Zagreb", "Lokomotiva")
        d.text((x+16, y-12), label, fill=WHITE if focus else MUTED, font=font(16, focus))
    d.text((ax+8, y0+10), "LEAGUE AVG INDEX", fill=MUTED, font=font(14, True))
    d.text((x0+8, ay-24), "LEAGUE AVG PPG", fill=MUTED, font=font(14, True))
    d.text(((x0+x1)/2, y1+54), "SHOOTING INDEX", fill=WHITE, font=font(18, True), anchor="ma")
    d.text((35, (y0+y1)/2), "POINTS PER GAME", fill=WHITE, font=font(17, True), anchor="lm")
    footer(d)
    img.save(path, quality=95)


def create_assets(matches, all_shots, stats, events_by_id):
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    team_matches = sorted(
        [m for m in matches if TEAM in {team_name(m, "home"), team_name(m, "away")}],
        key=lambda m: m["match_date"]
    )
    recent = team_matches[-3:][::-1]
    season_shots = [s for s in all_shots if s["team"] == TEAM]
    save_shotmap(
        ASSET_DIR / "01_varazdin_season_shotmap.png",
        season_shots,
        "Varaždin season shot map",
        f"2025/26 1. HNL | {len(team_matches)} matches | attacking direction bottom to top"
    )
    recent_paths = []
    for i, m in enumerate(recent, 1):
        shots = [s for s in all_shots if s["match_id"] == m["match_id"] and s["team"] == TEAM]
        venue = "HOME" if team_name(m, "home") == TEAM else "AWAY"
        p = ASSET_DIR / f"0{i+1}_varazdin_last3_{m['match_date']}_{opponent(m).replace(' ', '_')}.png"
        save_shotmap(p, shots, f"Varaždin {result_string(m)} {opponent(m)}", f"{m['match_date']} | {venue} | matchweek {m['match_week']}")
        recent_paths.append(p)
    flow_paths = []
    for i, m in enumerate(recent, 1):
        p = ASSET_DIR / f"0{i+4}_varazdin_xg_flow_{m['match_date']}_{opponent(m).replace(' ', '_')}.png"
        save_match_flow(p, m, all_shots)
        flow_paths.append(p)
    network_paths, cluster_paths, cross_paths = [], [], []
    final_third_paths, box_entry_paths, progressive_paths, xt_paths = [], [], [], []
    channel_paths, halfspace_paths, zone14_paths = [], [], []
    pressing_paths, progression_paths, defensive_paths = [], [], []
    buildup_paths, transition_paths, pressure_loss_paths, chance_network_paths, funnel_paths = [], [], [], [], []
    for i, m in enumerate(recent, 1):
        safe_opp = opponent(m).replace(" ", "_")
        network = ASSET_DIR / f"{i+7:02d}_pass_network_{m['match_date']}_{safe_opp}.png"
        cluster = ASSET_DIR / f"{i+10:02d}_pass_clusters_{m['match_date']}_{safe_opp}.png"
        cross = ASSET_DIR / f"{i+13:02d}_open_play_crosses_{m['match_date']}_{safe_opp}.png"
        final_third = ASSET_DIR / f"{i+20:02d}_final_third_entries_{m['match_date']}_{safe_opp}.png"
        box_entry = ASSET_DIR / f"{i+23:02d}_penalty_area_entries_{m['match_date']}_{safe_opp}.png"
        progressive = ASSET_DIR / f"{i+26:02d}_progressive_passes_{m['match_date']}_{safe_opp}.png"
        xt = ASSET_DIR / f"{i+29:02d}_passing_xt_{m['match_date']}_{safe_opp}.png"
        channel = ASSET_DIR / f"{i+32:02d}_xg_channels_{m['match_date']}_{safe_opp}.png"
        halfspace = ASSET_DIR / f"{i+35:02d}_passes_halfspaces_{m['match_date']}_{safe_opp}.png"
        zone14 = ASSET_DIR / f"{i+38:02d}_passes_zone14_{m['match_date']}_{safe_opp}.png"
        pressing = ASSET_DIR / f"{i+41:02d}_pressing_{m['match_date']}_{safe_opp}.png"
        progression = ASSET_DIR / f"{i+44:02d}_progression_{m['match_date']}_{safe_opp}.png"
        defensive = ASSET_DIR / f"{i+47:02d}_defensive_{m['match_date']}_{safe_opp}.png"
        buildup = ASSET_DIR / f"{i+50:02d}_goal_kick_buildup_{m['match_date']}_{safe_opp}.png"
        transition = ASSET_DIR / f"{i+53:02d}_attacking_transitions_{m['match_date']}_{safe_opp}.png"
        pressure_loss = ASSET_DIR / f"{i+56:02d}_turnovers_under_pressure_{m['match_date']}_{safe_opp}.png"
        chance_network = ASSET_DIR / f"{i+59:02d}_chance_creation_network_{m['match_date']}_{safe_opp}.png"
        funnel = ASSET_DIR / f"{i+62:02d}_possession_funnel_{m['match_date']}_{safe_opp}.png"
        save_pass_network(network, m, events_by_id[m["match_id"]])
        save_pass_clusters(cluster, m, events_by_id[m["match_id"]])
        save_crosses(cross, m, events_by_id[m["match_id"]])
        save_pass_selection(final_third, m, events_by_id[m["match_id"]], "final_third")
        save_pass_selection(box_entry, m, events_by_id[m["match_id"]], "penalty_area")
        save_pass_selection(progressive, m, events_by_id[m["match_id"]], "progressive")
        save_passing_xt(xt, m, events_by_id[m["match_id"]])
        save_xg_channels(channel, m, all_shots)
        save_zone_origin_passes(halfspace, m, events_by_id[m["match_id"]], "half_spaces")
        save_zone_origin_passes(zone14, m, events_by_id[m["match_id"]], "zone14")
        save_pressing(pressing, m, events_by_id[m["match_id"]])
        save_progression(progression, m, events_by_id[m["match_id"]])
        save_defensive(defensive, m, events_by_id[m["match_id"]])
        save_build_up(buildup, m, events_by_id[m["match_id"]])
        save_transitions(transition, m, events_by_id[m["match_id"]])
        save_pressure_turnovers(pressure_loss, m, events_by_id[m["match_id"]])
        save_chance_network(chance_network, m, events_by_id[m["match_id"]])
        save_possession_funnel(funnel, m, events_by_id[m["match_id"]])
        network_paths.append(network)
        cluster_paths.append(cluster)
        cross_paths.append(cross)
        final_third_paths.append(final_third)
        box_entry_paths.append(box_entry)
        progressive_paths.append(progressive)
        xt_paths.append(xt)
        channel_paths.append(channel); halfspace_paths.append(halfspace); zone14_paths.append(zone14)
        pressing_paths.append(pressing); progression_paths.append(progression); defensive_paths.append(defensive)
        buildup_paths.append(buildup); transition_paths.append(transition); pressure_loss_paths.append(pressure_loss)
        chance_network_paths.append(chance_network); funnel_paths.append(funnel)
    combined_specs = [
        "pass_clusters", "open_play_crosses", "final_third_entries", "penalty_area_entries",
        "progressive_passes", "passing_xt", "halfspace_passes", "zone14_passes", "pressing",
        "progression", "defensive_actions", "goal_kick_buildup", "attacking_transitions",
        "pressure_turnovers", "chance_networks",
    ]
    combined_paths = []
    for idx, slug in enumerate(combined_specs, 1):
        combined = ASSET_DIR / f"combined_{idx:02d}_{slug}.png"
        save_one_pitch_metric(combined, slug, recent, events_by_id, all_shots)
        combined_paths.append(combined)
    gk_distribution = ASSET_DIR / "combined_goalkeeper_distribution.png"
    gk_actions = ASSET_DIR / "combined_goalkeeper_actions.png"
    save_goalkeeper_distribution(gk_distribution, recent, events_by_id)
    save_goalkeeper_actions(gk_actions, recent, events_by_id)
    restart_assets = (
        build_restart_assets(ASSET_DIR, matches, events_by_id, TEAM)
        + build_coaching_restart_assets(ASSET_DIR, matches, events_by_id, TEAM)
    )
    league_metrics = season_team_metrics(matches, events_by_id)
    player_metrics = player_value_metrics(recent, events_by_id)
    league_zscores = ASSET_DIR / "evaluation_league_zscores.png"
    league_beeswarm = ASSET_DIR / "evaluation_league_beeswarm.png"
    player_value = ASSET_DIR / "evaluation_player_obv_xt.png"
    player_scatter = ASSET_DIR / "evaluation_player_scatter.png"
    obv_beeswarm = ASSET_DIR / "evaluation_obv_beeswarm.png"
    player_ratings = ASSET_DIR / "evaluation_player_ratings.png"
    save_league_zscores(league_zscores, league_metrics)
    save_league_beeswarm(league_beeswarm, league_metrics)
    save_player_value_bars(player_value, player_metrics)
    save_player_scatter(player_scatter, player_metrics)
    save_obv_beeswarm(obv_beeswarm, recent, events_by_id)
    save_player_ratings(player_ratings, player_metrics)
    style_radar = ASSET_DIR / "evaluation_style_radar.png"
    match_heatmap = ASSET_DIR / "evaluation_match_heatmap.png"
    possession_distribution = ASSET_DIR / "evaluation_possession_distribution.png"
    pass_distribution = ASSET_DIR / "evaluation_pass_length_distribution.png"
    pass_direction = ASSET_DIR / "evaluation_pass_direction_rose.png"
    pressure_performance = ASSET_DIR / "evaluation_under_pressure.png"
    volume_value = ASSET_DIR / "evaluation_volume_value.png"
    territory = ASSET_DIR / "evaluation_territory.png"
    save_style_radar(style_radar, league_metrics)
    save_match_kpi_heatmap(match_heatmap, recent, events_by_id, all_shots)
    save_possession_distribution(possession_distribution, recent, events_by_id)
    save_pass_distribution(pass_distribution, recent, events_by_id)
    save_pass_direction(pass_direction, recent, events_by_id)
    save_pressure_performance(pressure_performance, recent, events_by_id)
    save_risk_value_scatter(volume_value, player_metrics)
    save_territory_summary(territory, recent, events_by_id)
    vulnerability_sources = ASSET_DIR / "vulnerability_01_chance_sources.png"
    vulnerability_danger = ASSET_DIR / "vulnerability_02_conceded_danger_map.png"
    vulnerability_entries = ASSET_DIR / "vulnerability_03_box_entries.png"
    vulnerability_setpieces = ASSET_DIR / "vulnerability_04_set_piece_matrix.png"
    vulnerability_seconds = ASSET_DIR / "vulnerability_05_second_phases.png"
    vulnerability_keypasses = ASSET_DIR / "vulnerability_06_key_passes.png"
    vulnerability_linebreaks = ASSET_DIR / "vulnerability_07_line_breaks.png"
    vulnerability_farpost = ASSET_DIR / "vulnerability_08_far_post.png"
    vulnerability_press = ASSET_DIR / "vulnerability_09_press_targets.png"
    vulnerability_plan = ASSET_DIR / "vulnerability_10_match_plan.png"
    save_vulnerability_sources(vulnerability_sources, matches, events_by_id)
    save_conceded_danger_map(vulnerability_danger, matches, events_by_id)
    save_opponent_box_entries(vulnerability_entries, matches, events_by_id)
    save_set_piece_matrix(vulnerability_setpieces, matches, events_by_id)
    save_second_phase_map(vulnerability_seconds, matches, events_by_id)
    save_opponent_key_passes(vulnerability_keypasses, matches, events_by_id)
    save_line_breaks(vulnerability_linebreaks, matches, events_by_id)
    save_far_post_entries(vulnerability_farpost, matches, events_by_id)
    save_press_targets(vulnerability_press, recent, events_by_id)
    save_match_plan(vulnerability_plan)
    reference_formation = ASSET_DIR / "reference_01_formation_analysis.png"
    reference_progressive_density = ASSET_DIR / "reference_02_progressive_density.png"
    reference_switches = ASSET_DIR / "reference_03_switches.png"
    reference_cutbacks = ASSET_DIR / "reference_04_cutback_zones.png"
    reference_long_balls = ASSET_DIR / "reference_05_long_ball_targets.png"
    reference_goal_kicks = ASSET_DIR / "reference_06_goal_kick_receivers.png"
    reference_halfspaces = ASSET_DIR / "reference_07_halfspace_rankings.png"
    reference_verticality = ASSET_DIR / "reference_08_verticality.png"
    reference_sequences = ASSET_DIR / "reference_09_sequence_involvement.png"
    reference_finishing = ASSET_DIR / "reference_10_finishing_scatter.png"
    reference_line_height = ASSET_DIR / "reference_11_defensive_line_height.png"
    reference_line_breaking = ASSET_DIR / "reference_12_line_breaking_players.png"
    reference_possession_tilt = ASSET_DIR / "reference_13_possession_field_tilt.png"
    save_formation_analysis(reference_formation, matches, events_by_id)
    save_progressive_density(reference_progressive_density, matches, events_by_id)
    save_switches_analysis(reference_switches, matches, events_by_id)
    save_cutback_zones(reference_cutbacks, matches, events_by_id)
    save_long_ball_targets(reference_long_balls, matches, events_by_id)
    save_goal_kick_receivers(reference_goal_kicks, matches, events_by_id)
    save_zone_reception_rankings(reference_halfspaces, matches, events_by_id)
    save_verticality(reference_verticality, matches, events_by_id)
    save_sequence_involvement(reference_sequences, matches, events_by_id)
    save_finishing_scatter(reference_finishing, matches, events_by_id)
    save_defensive_line_height(reference_line_height, matches, events_by_id)
    save_line_breaking_players(reference_line_breaking, matches, events_by_id)
    save_possession_field_tilt_scatter(reference_possession_tilt, matches, events_by_id)
    prob = ASSET_DIR / "17_varazdin_xg_scoreline_matrix.png"
    scatter = ASSET_DIR / "18_hnl_shots90_vs_xg90.png"
    types = ASSET_DIR / "19_varazdin_xg_by_type.png"
    ppg = ASSET_DIR / "20_hnl_ppg_vs_shooting_index.png"
    save_probability(prob, stats[TEAM]["xg90"], stats[TEAM]["xga90"])
    save_scatter(scatter, stats)
    save_xg_type(types, season_shots)
    save_ppg_index(ppg, stats)
    return {
        "season": ASSET_DIR / "01_varazdin_season_shotmap.png",
        "recent": recent_paths,
        "flows": flow_paths, "networks": network_paths, "clusters": cluster_paths,
        "crosses": cross_paths, "final_third": final_third_paths, "box_entries": box_entry_paths,
        "progressive": progressive_paths, "xt": xt_paths,
        "channels": channel_paths, "halfspaces": halfspace_paths, "zone14": zone14_paths,
        "pressing": pressing_paths, "progression": progression_paths, "defensive": defensive_paths,
        "buildup": buildup_paths, "transitions": transition_paths, "pressure_losses": pressure_loss_paths,
        "chance_networks": chance_network_paths, "funnels": funnel_paths,
        "combined_pitch": combined_paths,
        "goalkeeping": [gk_distribution, gk_actions],
        "set_pieces": restart_assets,
        "evaluation": [
            league_zscores, league_beeswarm, style_radar, match_heatmap,
            possession_distribution, pass_distribution, pass_direction, territory,
            player_value, player_scatter, obv_beeswarm, pressure_performance,
            volume_value, player_ratings
        ],
        "vulnerability": [
            vulnerability_sources, vulnerability_danger, vulnerability_entries,
            vulnerability_setpieces, vulnerability_seconds, vulnerability_keypasses,
            vulnerability_linebreaks, vulnerability_farpost, vulnerability_press,
            vulnerability_plan
        ],
        "reference_visuals": [
            reference_formation, reference_progressive_density, reference_switches,
            reference_cutbacks, reference_long_balls, reference_goal_kicks,
            reference_halfspaces, reference_verticality, reference_sequences,
            reference_finishing, reference_line_height, reference_line_breaking,
            reference_possession_tilt
        ],
        "prob": prob, "scatter": scatter, "types": types, "ppg": ppg,
        "recent_matches": recent, "season_shots": season_shots
    }


def pdf_cover(c, width, height, stats, recent):
    c.setFillColor(NAVY)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(CYAN)
    c.rect(0, 0, 18, height, fill=1, stroke=0)
    c.setFont("Arial-Bold", 16)
    c.drawString(52, height-58, "FC HRADEC KRÁLOVÉ | OPPOSITION ANALYSIS")
    c.setFillColor(WHITE)
    c.setFont("Arial-Bold", 50)
    c.drawString(52, height-145, "NK VARAŽDIN")
    c.setFillColor(MUTED)
    c.setFont("Arial", 23)
    c.drawString(55, height-182, "PRE-MATCH SCOUT REPORT")
    c.setFillColor(PINK)
    c.rect(55, height-235, 175, 7, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Arial-Bold", 28)
    c.drawString(55, height-300, "COMPLETE OPPOSITION REPORT")
    c.setFillColor(MUTED)
    c.setFont("Arial", 15)
    c.drawString(55, height-330, "On-ball | Off-ball | Goalkeeping | Set pieces | Match plan")
    boxes = [
        ("xG / 90", f"{stats[TEAM]['xg90']:.2f}"),
        ("SHOTS / 90", f"{stats[TEAM]['shots90']:.1f}"),
        ("GOALS / 90", f"{stats[TEAM]['goals90']:.2f}"),
        ("PPG", f"{stats[TEAM]['ppg']:.2f}"),
    ]
    for i, (label, value) in enumerate(boxes):
        x = 55 + i*185
        c.setFillColor(PANEL)
        c.roundRect(x, 92, 160, 92, 10, fill=1, stroke=0)
        c.setFillColor(MUTED)
        c.setFont("Arial-Bold", 10)
        c.drawString(x+16, 154, label)
        c.setFillColor(CYAN if i < 2 else WHITE)
        c.setFont("Arial-Bold", 25)
        c.drawString(x+16, 112, value)
    c.setFillColor(MUTED)
    c.setFont("Arial", 10)
    c.drawRightString(width-42, 32, "2025/26 1. HNL | StatsBomb event data")


def pdf_contents(c, width, height):
    c.setFillColor(NAVY)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.setFillColor(CYAN)
    c.setFont("Arial-Bold", 13)
    c.drawString(50, height-50, "REPORT STRUCTURE")
    c.setFillColor(WHITE)
    c.setFont("Arial-Bold", 34)
    c.drawString(50, height-92, "CONTENTS")
    sections = [
        ("01", "PROFILE & SHAPE", "03-09", CYAN),
        ("02", "SHOOTING", "10-24", CYAN),
        ("03", "BUILD-UP & PASSING", "25-36", CYAN),
        ("04", "PROGRESSION & CREATION", "37-53", CYAN),
        ("05", "OFF-BALL", "54-59", CYAN),
        ("06", "GOALKEEPING", "60-61", CYAN),
        ("07", "SET PIECES & RESTARTS", "62-88", CYAN),
        ("08", "PLAYER EVALUATION", "89-93", CYAN),
        ("09", "HOW TO HURT VARAŽDIN", "94-103", PINK),
    ]
    for i, (num, title, detail, color) in enumerate(sections):
        y = height-145-i*48
        c.setFillColor(PANEL)
        c.roundRect(50, y-34, width-100, 39, 7, fill=1, stroke=0)
        c.setFillColor(color)
        c.setFont("Arial-Bold", 11)
        c.drawString(70, y-15, num)
        c.setFillColor(WHITE)
        c.setFont("Arial-Bold", 14)
        c.drawString(115, y-15, title)
        c.setFillColor(MUTED)
        c.setFont("Arial-Bold", 11)
        c.drawRightString(width-70, y-15, detail)
    c.setFillColor(MUTED)
    c.setFont("Arial", 10)
    c.drawString(50, 34, "103-page pre-match report | season context plus recent-match detail")


def add_image_page(c, width, height, image_path, page_no):
    c.setFillColor(NAVY)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    c.drawImage(ImageReader(str(image_path)), 0, 0, width=width, height=height, preserveAspectRatio=True, anchor="c")
    c.setFillColor(MUTED)
    c.setFont("Arial", 8)
    c.drawRightString(width-17, 10, f"{page_no:02d}")


def create_pdf(assets, stats):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("Arial", FONT_REG))
    pdfmetrics.registerFont(TTFont("Arial-Bold", FONT_BOLD))
    page_size = landscape(A4)
    width, height = page_size
    c = canvas.Canvas(str(PDF_PATH), pagesize=page_size)
    c.setTitle("NK Varaždin Opposition Report - Shooting")
    pdf_cover(c, width, height, stats, assets["recent_matches"])
    c.showPage()
    pdf_contents(c, width, height)
    c.showPage()
    cp = assets["combined_pitch"]
    ev = assets["evaluation"]
    ref = assets["reference_visuals"]
    paths = [
        # 03-09 | Profile, shape and league context
        ref[0], ev[2], ev[0], ev[1], ref[12], ev[3], ev[7],

        # 10-24 | Shooting and chance output
        assets["season"], *assets["recent"], *assets["flows"],
        *assets["channels"], assets["types"], assets["scatter"],
        ref[9], assets["prob"], assets["ppg"],

        # 25-36 | Build-up and passing style
        *assets["networks"], cp[11], ref[5], ev[4], ev[5], ev[6],
        ref[7], ref[2], ref[4], cp[0],

        # 37-53 | Progression and chance creation
        ref[1], cp[4], ref[11], cp[9], cp[2], cp[3], cp[6], cp[7],
        ref[6], cp[5], cp[14], ref[3], cp[1], ref[8], *assets["funnels"],

        # 54-59 | Off-ball behaviour
        cp[8], cp[10], ref[10], cp[13], ev[11], cp[12],

        # 60-61 | Goalkeeping
        *assets["goalkeeping"],

        # 62-88 | Set pieces, restart families and coaching detail
        *assets["set_pieces"],

        # 89-93 | Player evaluation
        ev[8], ev[9], ev[10], ev[12], ev[13],

        # 94-103 | Vulnerabilities and match plan
        *assets["vulnerability"],
    ]
    for page_no, p in enumerate(paths, start=3):
        add_image_page(c, width, height, p, page_no)
        c.showPage()
    c.save()


def write_summary(matches, assets, stats):
    v = stats[TEAM]
    recent_lines = []
    for m in assets["recent_matches"]:
        shots = [s for s in assets["season_shots"] if s["match_id"] == m["match_id"]]
        recent_lines.append(f"- {m['match_date']} | {TEAM} {result_string(m)} {opponent(m)} | {len(shots)} shots | {sum(s['xg'] for s in shots):.2f} xG")
    text = f"""NK VARAŽDIN SHOOTING MODULE

Season: 2025/26 1. HNL
Matches: {v['games']}
Shots: {v['shots']} ({v['shots90']:.2f} per match)
xG: {v['xg']:.2f} ({v['xg90']:.2f} per match)
Goals: {v['gf']} ({v['goals90']:.2f} per match)
xGA: {v['xga']:.2f} ({v['xga90']:.2f} per match)
Points per game: {v['ppg']:.2f}
Shooting index: {v['shooting_index']:.1f} (league average 100)

Last three matches:
{chr(10).join(recent_lines)}

Method note:
The scoreline matrix uses independent Poisson distributions with Varaždin season xG-for and xG-against per match. It is an opposition-only neutral baseline, not a Hradec-specific forecast.
The shooting index is 70% league-normalized xG per match and 30% league-normalized shots per match.
"""
    (OUT_DIR / "NK_Varazdin_shooting_report_notes.txt").write_text(text)


def main():
    matches, _, events_by_id = load_data()
    valid_matches, all_shots, stats = compile_stats(matches, events_by_id)
    assets = create_assets(valid_matches, all_shots, stats, events_by_id)
    create_pdf(assets, stats)
    write_summary(valid_matches, assets, stats)
    print(PDF_PATH)
    print(f"pages=103 assets={len(list(ASSET_DIR.glob('*.png')))}")
    print(f"varazdin={stats[TEAM]}")


if __name__ == "__main__":
    main()
