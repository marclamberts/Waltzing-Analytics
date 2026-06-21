#!/usr/bin/env python3
"""Create a one-page Tunisia-Japan post-match dashboard from Opta events."""

import csv
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / ".python_packages"))
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / "tmp" / "matplotlib"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from mplsoccer import Pitch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parent
SOURCE = Path("/Users/marclamberts/Event data/WC 2026/NEW/2026-06-20_Tunisia - Japan.json")
WC_ROOT = Path("/Users/marclamberts/Event data/WC 2026")
OUT_PNG = ROOT / "output" / "png" / "Tunisia_Japan_post_match_dashboard.png"
OUT_PDF = ROOT / "output" / "pdf" / "Tunisia_Japan_post_match_dashboard.pdf"

TUNISIA_ID = "ctp7ovvf34m7fzshua9ogbr6i"
JAPAN_ID = "6duaxcbrofil112qfq4v895go"
TEAMS = [(TUNISIA_ID, "Tunisia"), (JAPAN_ID, "Japan")]

NAVY = "#071522"
PANEL = "#112A3C"
GRID = "#315064"
WHITE = "#F4F7F9"
MUTED = "#9BB0BF"
CYAN = "#35D0D6"
PINK = "#FF4F8B"
AMBER = "#FFBD59"
GREEN = "#55D187"
RED = "#FF6474"


def qualifiers(event):
    return {q["qualifierId"]: q.get("value") for q in event.get("qualifier", [])}


def train_xg_model():
    """Ridge model fitted to the existing Opta WC shot outputs."""
    labelled = []
    qids = set()
    for csv_path in WC_ROOT.glob("reports/*/shots.csv"):
        raw_path = WC_ROOT / "DONE" / f"{csv_path.parent.name}.json"
        if not raw_path.exists():
            continue
        raw_shots = [
            e for e in json.loads(raw_path.read_text())["event"]
            if e.get("typeId") in {13, 14, 15, 16}
        ]
        used = set()
        for row in csv.DictReader(csv_path.open()):
            candidates = []
            for i, event in enumerate(raw_shots):
                if i in used:
                    continue
                if (
                    event.get("playerId") == row["player_id"]
                    and event.get("typeId") == int(row["type_id"])
                    and event.get("timeMin") == int(float(row["time_min"]))
                ):
                    distance = abs(float(event.get("x", 0))-float(row["x"]))
                    distance += abs(float(event.get("y", 0))-float(row["y"]))
                    candidates.append((distance, i, event))
            if not candidates:
                continue
            _, idx, event = min(candidates)
            used.add(idx)
            qids.update(qualifiers(event))
            labelled.append((event, float(row["xg"])))
    qids = sorted(qids)

    def features(event):
        x, y = float(event.get("x", 0)), float(event.get("y", 50))
        dx, dy = 100-x, abs(50-y)
        qs = qualifiers(event)
        return [
            1, x/100, y/100, dx/100, dy/50,
            math.hypot(dx, dy)/100,
            int(event.get("typeId") == 13),
            int(event.get("typeId") == 14),
            int(event.get("typeId") == 15),
            int(event.get("typeId") == 16),
            *[int(qid in qs) for qid in qids],
        ]

    x_matrix = np.array([features(event) for event, _ in labelled])
    target = np.array([
        math.log(min(.95, max(.005, value))/(1-min(.95, max(.005, value))))
        for _, value in labelled
    ])
    ridge = 1.0
    beta = np.linalg.solve(
        x_matrix.T @ x_matrix + ridge*np.eye(x_matrix.shape[1]),
        x_matrix.T @ target,
    )

    def predict(event):
        logit = np.array(features(event)) @ beta
        return float(np.clip(1/(1+np.exp(-logit)), .01, .90))

    return predict, len(labelled)


def team_stats(events, team_id, predict_xg):
    team_events = [event for event in events if event.get("contestantId") == team_id]
    shots = [event for event in team_events if event.get("typeId") in {13, 14, 15, 16}]
    for event in shots:
        event["_xg"] = predict_xg(event)
    passes = [event for event in team_events if event.get("typeId") == 1]
    return {
        "events": team_events,
        "shots_list": shots,
        "shots": len(shots),
        "on_target": sum(event.get("typeId") in {15, 16} for event in shots),
        "goals": sum(event.get("typeId") == 16 for event in shots),
        "xg": sum(event["_xg"] for event in shots),
        "big_chances": sum(214 in qualifiers(event) for event in shots),
        "passes": len(passes),
        "completed": sum(event.get("outcome") == 1 for event in passes),
    }


def draw_pitch_panel(fig, stats):
    ax = fig.add_axes([.045, .20, .47, .58])
    pitch = Pitch(
        pitch_type="opta", pitch_color="#0B4B49", line_color=WHITE,
        linewidth=1.2, goal_type="box",
    )
    pitch.draw(ax=ax)
    colors = {"Tunisia": PINK, "Japan": CYAN}
    for _, team in TEAMS:
        for shot in stats[team]["shots_list"]:
            x, y = float(shot["x"]), float(shot["y"])
            if team == "Tunisia":
                x, y = 100-x, 100-y
            goal = shot.get("typeId") == 16
            pitch.scatter(
                x, y, ax=ax, s=55+950*shot["_xg"],
                color=AMBER if goal else colors[team],
                marker="*" if goal else "o",
                edgecolors=WHITE, linewidth=1.1, alpha=.92,
            )
    ax.set_title("SHOT MAP | SIZE = ESTIMATED xG", color=MUTED, fontsize=9,
                 fontweight="bold", pad=8)
    fig.text(.055, .17, "Tunisia attacks left", color=PINK, fontsize=8.5, fontweight="bold")
    fig.text(.505, .17, "Japan attacks right", color=CYAN, fontsize=8.5,
             fontweight="bold", ha="right")


def draw_flow(fig, stats):
    ax = fig.add_axes([.555, .53, .40, .22], facecolor=NAVY)
    for team, color in (("Tunisia", PINK), ("Japan", CYAN)):
        shots = sorted(stats[team]["shots_list"], key=lambda event: (event.get("periodId", 1), event.get("timeMin", 0), event.get("timeSec", 0)))
        mins = [0]
        cumulative = [0]
        total = 0
        for shot in shots:
            minute = shot.get("timeMin", 0)
            total += shot["_xg"]
            mins.extend([minute, minute])
            cumulative.extend([cumulative[-1], total])
        mins.append(100)
        cumulative.append(total)
        ax.plot(mins, cumulative, color=color, linewidth=2.5, label=team)
        for shot in shots:
            if shot.get("typeId") == 16:
                minute = shot.get("timeMin", 0)
                before = sum(s["_xg"] for s in shots if s.get("timeMin", 0) <= minute)
                ax.scatter(minute, before, s=65, color=AMBER, marker="*", zorder=5)
    ax.set_xlim(0, 100)
    ymax = max(stats["Tunisia"]["xg"], stats["Japan"]["xg"], .5)*1.18
    ax.set_ylim(0, ymax)
    ax.set_xticks([0, 15, 30, 45, 60, 75, 90], ["0", "15", "30", "HT", "60", "75", "90"])
    ax.tick_params(colors=MUTED, labelsize=7, length=0)
    ax.grid(color=GRID, alpha=.35)
    [spine.set_visible(False) for spine in ax.spines.values()]
    ax.set_title("xG FLOW", color=WHITE, fontsize=10, fontweight="bold", loc="left")
    legend = ax.legend(frameon=False, loc="upper left", fontsize=7, ncol=2)
    for text in legend.get_texts():
        text.set_color(WHITE)


def draw_metrics(fig, stats):
    labels = ["SHOTS", "ON TARGET", "xG", "BIG CHANCES", "PASS COMPLETION"]
    left = stats["Tunisia"]
    right = stats["Japan"]
    left_values = [left["shots"], left["on_target"], f"{left['xg']:.2f}", left["big_chances"],
                   f"{100*left['completed']/max(left['passes'], 1):.0f}%"]
    right_values = [right["shots"], right["on_target"], f"{right['xg']:.2f}", right["big_chances"],
                    f"{100*right['completed']/max(right['passes'], 1):.0f}%"]
    for i, label in enumerate(labels):
        y = .445-i*.064
        fig.add_artist(plt.Rectangle((.555, y-.025), .40, .050,
                                     transform=fig.transFigure, color=PANEL))
        fig.text(.575, y, str(left_values[i]), color=PINK, fontsize=13,
                 fontweight="bold", va="center")
        fig.text(.755, y, label, color=MUTED, fontsize=7.5,
                 fontweight="bold", ha="center", va="center")
        fig.text(.935, y, str(right_values[i]), color=CYAN, fontsize=13,
                 fontweight="bold", ha="right", va="center")


def draw_takeaways(fig, stats):
    japan = stats["Japan"]
    scorers = Counter(
        shot.get("playerName", "Unknown")
        for shot in japan["shots_list"] if shot.get("typeId") == 16
    )
    scorer_text = " | ".join(
        f"{player} x{count}" if count > 1 else player
        for player, count in scorers.items()
    )
    items = [
        ("DECISIVE EDGE", f"4 goals from {japan['xg']:.2f} xG\noutperformed chance quality."),
        ("SHOT CONTROL", "Japan: 11 shots and 8 on target.\nTunisia produced only two attempts."),
        ("SCORERS", scorer_text.replace(" | J.", "\nJ.")),
    ]
    fig.text(.555, .095, "POST-MATCH READ", color=AMBER, fontsize=9, fontweight="bold")
    for i, (title, body) in enumerate(items):
        x = .555+i*.135
        fig.add_artist(plt.Rectangle((x, .022), .125, .064, transform=fig.transFigure,
                                     color=PANEL))
        fig.text(x+.008, .067, title, color=WHITE, fontsize=6.5, fontweight="bold")
        fig.text(x+.008, .049, body, color=MUTED, fontsize=5.7, va="top", linespacing=1.25)


def create_dashboard():
    payload = json.loads(SOURCE.read_text())
    events = payload["event"]
    predict_xg, training_shots = train_xg_model()
    stats = {
        name: team_stats(events, team_id, predict_xg)
        for team_id, name in TEAMS
    }

    fig = plt.figure(figsize=(16, 9), dpi=120, facecolor=NAVY)
    fig.text(.045, .945, "FIFA WORLD CUP 2026 | POST-MATCH ANALYSIS",
             color=CYAN, fontsize=11, fontweight="bold")
    fig.text(.045, .887, "TUNISIA", color=WHITE, fontsize=29, fontweight="bold")
    fig.text(.235, .887, "0", color=PINK, fontsize=34, fontweight="bold")
    fig.text(.285, .887, "-", color=MUTED, fontsize=28, fontweight="bold")
    fig.text(.335, .887, "4", color=CYAN, fontsize=34, fontweight="bold")
    fig.text(.395, .887, "JAPAN", color=WHITE, fontsize=29, fontweight="bold")
    fig.text(.045, .842, "20 JUNE 2026 | FULL TIME | JAPAN WIN",
             color=MUTED, fontsize=9, fontweight="bold")
    fig.add_artist(Line2D([.045, .955], [.812, .812], transform=fig.transFigure,
                          color=GRID, linewidth=1))

    draw_pitch_panel(fig, stats)
    draw_flow(fig, stats)
    draw_metrics(fig, stats)
    draw_takeaways(fig, stats)
    fig.text(.955, .012,
             f"Opta event data | xG model calibrated on {training_shots} WC 2026 shots | Marc Lamberts",
             color=MUTED, fontsize=5.6, ha="right")

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, facecolor=NAVY, dpi=120)
    plt.close(fig)

    width, height = 1152, 648
    pdf = canvas.Canvas(str(OUT_PDF), pagesize=(width, height))
    pdf.setTitle("Tunisia 0-4 Japan Post-Match Dashboard")
    pdf.drawImage(ImageReader(str(OUT_PNG)), 0, 0, width=width, height=height)
    pdf.showPage()
    pdf.save()
    return stats, training_shots


if __name__ == "__main__":
    match_stats, sample = create_dashboard()
    print(OUT_PNG)
    print(OUT_PDF)
    print(f"xg_training_sample={sample}")
    for team in ("Tunisia", "Japan"):
        row = match_stats[team]
        print(team, {key: row[key] for key in ("goals", "shots", "on_target", "xg", "big_chances", "passes", "completed")})
