"""Shared set-piece and restart visual module for opposition reports."""

from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from mplsoccer import Pitch


RESTARTS = [
    ("Corner", "From Corner"),
    ("Free Kick", "From Free Kick"),
    ("Throw-in", "From Throw In"),
    ("Goal Kick", "From Goal Kick"),
    ("Kick Off", "From Kick Off"),
]


def _team_name(match, side):
    return match[f"{side}_team"][f"{side}_team_name"]


def _event_team(event):
    return event.get("team", {}).get("name")


def _pass_type(event):
    return event.get("pass", {}).get("type", {}).get("name")


def _xg(event):
    return float(event.get("shot", {}).get("statsbomb_xg", 0) or 0)


def _is_goal(event):
    return event.get("shot", {}).get("outcome", {}).get("name") == "Goal"


def _end(event):
    return event.get("pass", {}).get("end_location")


def _draw_frame(fig, kicker, title, subtitle):
    fig.text(0.055, 0.935, kicker, color="#35D0D6", fontsize=12, fontweight="bold")
    fig.text(0.055, 0.885, title, color="#F4F7F9", fontsize=25, fontweight="bold")
    fig.text(0.055, 0.847, subtitle, color="#9BB0BF", fontsize=10.5)
    fig.add_artist(Line2D([0.055, 0.945], [0.815, 0.815], transform=fig.transFigure,
                          color="#315064", linewidth=1))
    fig.text(0.945, 0.035, "StatsBomb event data | team attacks left to right",
             color="#9BB0BF", fontsize=7.5, ha="right")


def _figure(kicker, title, subtitle):
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor="#071522")
    _draw_frame(fig, kicker, title, subtitle)
    return fig


def _pitch_axis(fig, rect=(0.055, 0.105, 0.67, 0.66), half=False):
    ax = fig.add_axes(rect)
    pitch = Pitch(
        pitch_type="statsbomb",
        half=half,
        pitch_color="#0B4B49",
        line_color="#F4F7F9",
        linewidth=1.25,
        goal_type="box",
    )
    pitch.draw(ax=ax)
    return ax, pitch


def _save(fig, path):
    fig.savefig(path, facecolor="#071522", dpi=100)
    plt.close(fig)


def _valid_team_matches(matches, events_by_id, team):
    return [
        m for m in matches
        if m["match_id"] in events_by_id
        and team in {_team_name(m, "home"), _team_name(m, "away")}
        and m.get("home_score") is not None
        and m.get("away_score") is not None
    ]


def _sequences(matches, events_by_id, team):
    rows = []
    for match in _valid_team_matches(matches, events_by_id, team):
        grouped = defaultdict(list)
        for event in events_by_id[match["match_id"]]:
            grouped[event.get("possession")].append(event)
        for possession, events in grouped.items():
            events.sort(key=lambda e: e.get("index", 0))
            starters = [
                e for e in events
                if e.get("type", {}).get("name") == "Pass"
                and _pass_type(e) in {r[0] for r in RESTARTS}
            ]
            for start in starters:
                restart = _pass_type(start)
                pattern = dict(RESTARTS)[restart]
                owner = _event_team(start)
                sequence = [
                    e for e in events
                    if e.get("index", 0) >= start.get("index", 0)
                    and (
                        e.get("play_pattern", {}).get("name") == pattern
                        or e.get("index", 0) == start.get("index", 0)
                    )
                ]
                if not sequence:
                    sequence = [start]
                own_events = [e for e in sequence if _event_team(e) == owner]
                shots = [e for e in own_events if e.get("type", {}).get("name") == "Shot"]
                completed = "outcome" not in start.get("pass", {})
                box_entry = any(
                    e.get("type", {}).get("name") in {"Pass", "Carry"}
                    and (
                        (_end(e) and _end(e)[0] >= 102 and 18 <= _end(e)[1] <= 62)
                        or (
                            e.get("type", {}).get("name") == "Carry"
                            and e.get("carry", {}).get("end_location")
                            and e["carry"]["end_location"][0] >= 102
                            and 18 <= e["carry"]["end_location"][1] <= 62
                        )
                    )
                    for e in own_events
                )
                final_third = any(
                    (
                        _end(e)
                        if e.get("type", {}).get("name") == "Pass"
                        else e.get("carry", {}).get("end_location")
                    )
                    and (
                        _end(e)
                        if e.get("type", {}).get("name") == "Pass"
                        else e.get("carry", {}).get("end_location")
                    )[0] >= 80
                    for e in own_events
                    if e.get("type", {}).get("name") in {"Pass", "Carry"}
                )
                losses = [
                    e for e in sequence[:8]
                    if _event_team(e) == owner
                    and (
                        e.get("type", {}).get("name") in {"Dispossessed", "Miscontrol"}
                        or (
                            e.get("type", {}).get("name") == "Pass"
                            and "outcome" in e.get("pass", {})
                        )
                    )
                ]
                first_receiver = start.get("pass", {}).get("recipient", {}).get("name")
                rows.append({
                    "match_id": match["match_id"],
                    "date": match.get("match_date", ""),
                    "restart": restart,
                    "owner": owner,
                    "attacking": owner == team,
                    "start": start,
                    "events": sequence,
                    "shots": shots,
                    "xg": sum(_xg(e) for e in shots),
                    "goals": sum(_is_goal(e) for e in shots),
                    "completed": completed,
                    "box_entry": box_entry,
                    "final_third": final_third,
                    "early_loss": bool(losses),
                    "receiver": first_receiver,
                })
            direct_free_kicks = [
                e for e in events
                if e.get("type", {}).get("name") == "Shot"
                and e.get("shot", {}).get("type", {}).get("name") == "Free Kick"
                and not any(
                    s.get("index", 0) < e.get("index", 0)
                    and _pass_type(s) == "Free Kick"
                    for s in starters
                )
            ]
            for shot in direct_free_kicks:
                owner = _event_team(shot)
                rows.append({
                    "match_id": match["match_id"],
                    "date": match.get("match_date", ""),
                    "restart": "Free Kick",
                    "owner": owner,
                    "attacking": owner == team,
                    "start": shot,
                    "events": [shot],
                    "shots": [shot],
                    "xg": _xg(shot),
                    "goals": int(_is_goal(shot)),
                    "completed": False,
                    "box_entry": False,
                    "final_third": bool(shot.get("location") and shot["location"][0] >= 80),
                    "early_loss": False,
                    "receiver": None,
                })
    return rows


def _metric(rows):
    n = len(rows)
    shots = sum(len(r["shots"]) for r in rows)
    return {
        "n": n,
        "shots": shots,
        "xg": sum(r["xg"] for r in rows),
        "goals": sum(r["goals"] for r in rows),
        "complete": 100 * sum(r["completed"] for r in rows) / max(n, 1),
        "final": 100 * sum(r["final_third"] for r in rows) / max(n, 1),
        "box": 100 * sum(r["box_entry"] for r in rows) / max(n, 1),
        "loss": 100 * sum(r["early_loss"] for r in rows) / max(n, 1),
    }


def _overview(path, sequences, team, games):
    fig = _figure(
        "SET PIECES & RESTARTS | SEASON OVERVIEW",
        f"{team} restart performance: for and against",
        "Volume and possession outcomes for every restart family | rates are per 100 restarts",
    )
    headers = ["RESTART", "N", "PER 90", "SHOTS", "SH/100", "xG", "xG/100"]
    offsets = [0, .145, .19, .255, .31, .36, .405]
    for side, attacking in enumerate((True, False)):
        x0 = 0.055 + side * 0.465
        fig.text(x0, 0.765, "ATTACKING" if attacking else "DEFENDING",
                 color="#55D187" if attacking else "#FF6474", fontsize=13, fontweight="bold")
        for j, header in enumerate(headers):
            fig.text(x0 + offsets[j], 0.72,
                     header, color="#9BB0BF", fontsize=8, fontweight="bold")
        for i, (restart, _) in enumerate(RESTARTS):
            rows = [r for r in sequences if r["attacking"] == attacking and r["restart"] == restart]
            m = _metric(rows)
            y = 0.665 - i * 0.092
            fig.add_artist(plt.Rectangle((x0, y - .026), .41, .062, transform=fig.transFigure,
                                         facecolor="#112A3C", edgecolor="none"))
            vals = [
                restart, f"{m['n']}", f"{m['n']/max(games,1):.1f}", f"{m['shots']}",
                f"{100*m['shots']/max(m['n'],1):.1f}", f"{m['xg']:.2f}",
                f"{100*m['xg']/max(m['n'],1):.2f}",
            ]
            for j, value in enumerate(vals):
                fig.text(x0 + offsets[j], y,
                         value, color="#F4F7F9" if j else "#FFBD59",
                         fontsize=9.5, fontweight="bold" if j in {0, 6} else "normal")
    fig.text(.055, .13, "READING THE TABLE", color="#35D0D6", fontsize=10, fontweight="bold")
    fig.text(.055, .095,
             "Attacking rows measure chances created by the team. Defending rows measure chances created by opponents.",
             color="#9BB0BF", fontsize=9)
    _save(fig, path)


def _delivery_map(path, sequences, team, restart, attacking=True):
    side = "ATTACKING" if attacking else "DEFENDING"
    rows = [r for r in sequences if r["attacking"] == attacking and r["restart"] == restart]
    fig = _figure(
        f"SET PIECES | {side} {restart.upper()}S",
        f"{team}: {restart.lower()} delivery and shot map",
        "Arrows show the restart delivery | circles show resulting shots | defending events are flipped",
    )
    ax, pitch = _pitch_axis(fig)
    shots = []
    for row in rows:
        event = row["start"]
        loc, end = event.get("location"), _end(event)
        if loc and end:
            x, y, ex, ey = loc[0], loc[1], end[0], end[1]
            if not attacking:
                x, y, ex, ey = 120-x, 80-y, 120-ex, 80-ey
            color = "#55D187" if row["completed"] else "#FF6474"
            pitch.arrows(x, y, ex, ey, ax=ax, color=color, alpha=.30,
                         width=1.0, headwidth=3.5, headlength=3.5)
        for shot in row["shots"]:
            if not shot.get("location"):
                continue
            x, y = shot["location"][:2]
            if not attacking:
                x, y = 120-x, 80-y
            val = _xg(shot)
            goal = _is_goal(shot)
            pitch.scatter(x, y, ax=ax, s=65 + 850*val, color="#FFBD59" if goal else "#F4F7F9",
                          edgecolors="#071522", linewidth=1, alpha=.92, marker="*" if goal else "o")
            shots.append(shot)
    m = _metric(rows)
    fig.text(.77, .69, f"{m['n']}", color="#F4F7F9", fontsize=30, fontweight="bold")
    fig.text(.77, .65, "RESTARTS", color="#9BB0BF", fontsize=9, fontweight="bold")
    fig.text(.77, .56, f"{m['shots']}  |  {m['xg']:.2f}", color="#FFBD59", fontsize=19, fontweight="bold")
    fig.text(.77, .525, "SHOTS  |  xG", color="#9BB0BF", fontsize=9, fontweight="bold")
    fig.text(.77, .435, f"{m['goals']}  |  {m['complete']:.0f}%", color="#35D0D6", fontsize=19, fontweight="bold")
    fig.text(.77, .40, "GOALS  |  INITIAL COMPLETION", color="#9BB0BF", fontsize=9, fontweight="bold")
    fig.text(.77, .29, "Delivery", color="#F4F7F9", fontsize=9)
    fig.text(.84, .29, "complete", color="#55D187", fontsize=9, fontweight="bold")
    fig.text(.77, .25, "Delivery", color="#F4F7F9", fontsize=9)
    fig.text(.84, .25, "unsuccessful", color="#FF6474", fontsize=9, fontweight="bold")
    _save(fig, path)


def _corner_profile(path, sequences, team, attacking=True):
    rows = [r for r in sequences if r["attacking"] == attacking and r["restart"] == "Corner"]
    side = "ATTACKING" if attacking else "DEFENDING"
    fig = _figure(
        f"SET PIECES | {side} CORNER PROFILE",
        f"{team}: delivery zones, takers and outcomes",
        "End-zone density, side split and leading corner takers | defensive view shows opposition takers",
    )
    ax, pitch = _pitch_axis(fig, (0.055, .12, .47, .64), half=True)
    ends = []
    takers = Counter()
    side_count = Counter()
    for row in rows:
        event = row["start"]
        end = _end(event)
        if end:
            x, y = end[:2]
            ends.append((x, y))
        takers[event.get("player", {}).get("name", "Unknown")] += 1
        loc = event.get("location", [0, 40])
        side_count["LEFT"] += loc[1] < 40
        side_count["RIGHT"] += loc[1] >= 40
    if ends:
        bs = pitch.bin_statistic([p[0] for p in ends], [p[1] for p in ends],
                                 statistic="count", bins=(5, 6), normalize=True)
        pitch.heatmap(bs, ax=ax, cmap="YlOrBr", alpha=.80)
        pitch.scatter([p[0] for p in ends], [p[1] for p in ends], ax=ax,
                      s=22, color="#F4F7F9", alpha=.35)
    bar = fig.add_axes([.61, .47, .33, .27], facecolor="#071522")
    top = takers.most_common(7)
    bar.barh(range(len(top)), [v for _, v in top], color="#FFBD59")
    bar.set_yticks(range(len(top)), [p for p, _ in top])
    bar.invert_yaxis()
    bar.tick_params(colors="#F4F7F9", labelsize=8, length=0)
    [sp.set_visible(False) for sp in bar.spines.values()]
    bar.set_title("LEADING TAKERS", color="#F4F7F9", fontsize=10, fontweight="bold")
    m = _metric(rows)
    metrics = [
        ("LEFT / RIGHT", f"{side_count['LEFT']} / {side_count['RIGHT']}"),
        ("SHOT RATE", f"{100*m['shots']/max(m['n'],1):.1f} per 100"),
        ("xG RATE", f"{100*m['xg']/max(m['n'],1):.2f} per 100"),
        ("BOX ENTRY", f"{m['box']:.0f}%"),
    ]
    for i, (label, value) in enumerate(metrics):
        y = .37 - i*.07
        fig.text(.61, y, label, color="#9BB0BF", fontsize=8.5, fontweight="bold")
        fig.text(.82, y, value, color="#35D0D6", fontsize=11, fontweight="bold")
    _save(fig, path)


def _free_kick_profile(path, sequences, team, attacking=True):
    rows = [r for r in sequences if r["attacking"] == attacking and r["restart"] == "Free Kick"]
    side = "ATTACKING" if attacking else "DEFENDING"
    fig = _figure(
        f"SET PIECES | {side} FREE KICKS",
        f"{team}: free-kick origin, delivery and shot threat",
        "Lines show deliveries | stars are direct free-kick shots | defending events are flipped",
    )
    ax, pitch = _pitch_axis(fig)
    direct, delivered, takers = [], [], Counter()
    for row in rows:
        event = row["start"]
        takers[event.get("player", {}).get("name", "Unknown")] += 1
        loc, end = event.get("location"), _end(event)
        if loc and end:
            x, y, ex, ey = *loc[:2], *end[:2]
            if not attacking:
                x, y, ex, ey = 120-x, 80-y, 120-ex, 80-ey
            delivered.append((x, y, ex, ey))
            pitch.arrows(x, y, ex, ey, ax=ax, color="#35D0D6", alpha=.24,
                         width=.9, headwidth=3, headlength=3)
        for shot in row["shots"]:
            if not shot.get("location"):
                continue
            x, y = shot["location"][:2]
            if not attacking:
                x, y = 120-x, 80-y
            is_direct = shot.get("shot", {}).get("type", {}).get("name") == "Free Kick"
            direct.append(is_direct)
            pitch.scatter(x, y, ax=ax, s=80+700*_xg(shot), marker="*" if is_direct else "o",
                          color="#FFBD59" if is_direct else "#F4F7F9",
                          edgecolors="#071522", linewidth=1)
    m = _metric(rows)
    fig.text(.77, .67, f"{m['n']} free kicks", color="#F4F7F9", fontsize=20, fontweight="bold")
    fig.text(.77, .60, f"{sum(direct)} direct shots", color="#FFBD59", fontsize=13, fontweight="bold")
    fig.text(.77, .55, f"{m['shots']-sum(direct)} sequence shots", color="#35D0D6", fontsize=13, fontweight="bold")
    fig.text(.77, .48, f"{m['xg']:.2f} xG  |  {m['goals']} goals", color="#F4F7F9", fontsize=13)
    fig.text(.77, .38, "TOP TAKERS", color="#9BB0BF", fontsize=9, fontweight="bold")
    for i, (player, n) in enumerate(takers.most_common(6)):
        fig.text(.77, .34-i*.042, player, color="#F4F7F9", fontsize=8.5)
        fig.text(.94, .34-i*.042, str(n), color="#FFBD59", fontsize=8.5, ha="right", fontweight="bold")
    _save(fig, path)


def _throw_map(path, sequences, team, attacking=True):
    rows = [r for r in sequences if r["attacking"] == attacking and r["restart"] == "Throw-in"]
    side = "ATTACKING" if attacking else "DEFENDING"
    fig = _figure(
        f"RESTARTS | {side} THROW-INS",
        f"{team}: throw-in locations and direction",
        "Green = forward | cyan = lateral | red = backward | defending events are flipped",
    )
    ax, pitch = _pitch_axis(fig)
    directions, thirds = Counter(), Counter()
    for row in rows:
        event = row["start"]
        loc, end = event.get("location"), _end(event)
        if not loc or not end:
            continue
        x, y, ex, ey = *loc[:2], *end[:2]
        if not attacking:
            x, y, ex, ey = 120-x, 80-y, 120-ex, 80-ey
        gain = ex-x
        direction = "FORWARD" if gain > 5 else "BACKWARD" if gain < -5 else "LATERAL"
        directions[direction] += 1
        thirds["DEFENSIVE"] += x < 40
        thirds["MIDDLE"] += 40 <= x < 80
        thirds["FINAL"] += x >= 80
        color = {"FORWARD": "#55D187", "LATERAL": "#35D0D6", "BACKWARD": "#FF6474"}[direction]
        pitch.arrows(x, y, ex, ey, ax=ax, color=color, alpha=.20,
                     width=.8, headwidth=3, headlength=3)
    m = _metric(rows)
    for i, key in enumerate(("FORWARD", "LATERAL", "BACKWARD")):
        fig.text(.77, .68-i*.07, f"{directions[key]:>3}", color={"FORWARD": "#55D187", "LATERAL": "#35D0D6", "BACKWARD": "#FF6474"}[key],
                 fontsize=22, fontweight="bold")
        fig.text(.82, .685-i*.07, key, color="#F4F7F9", fontsize=9, fontweight="bold")
    fig.text(.77, .43, "LOCATION SPLIT", color="#9BB0BF", fontsize=9, fontweight="bold")
    for i, key in enumerate(("DEFENSIVE", "MIDDLE", "FINAL")):
        fig.text(.77, .385-i*.045, key, color="#F4F7F9", fontsize=8.5)
        fig.text(.94, .385-i*.045, str(thirds[key]), color="#FFBD59", fontsize=9, ha="right", fontweight="bold")
    fig.text(.77, .20, f"{m['shots']} shots | {m['xg']:.2f} xG | {m['box']:.0f}% box entry",
             color="#35D0D6", fontsize=10, fontweight="bold")
    _save(fig, path)


def _throw_outcomes(path, sequences, team):
    fig = _figure(
        "RESTARTS | THROW-IN OUTCOMES",
        f"{team}: retention, progression and threat from throw-ins",
        "Attack versus defence by pitch third | early loss covers the first eight recorded sequence actions",
    )
    labels = ["Initial completion", "Final-third access", "Box entry", "Early loss", "Shots / 100", "xG / 100"]
    for side, attacking in enumerate((True, False)):
        x = .08 + side*.46
        rows = [r for r in sequences if r["attacking"] == attacking and r["restart"] == "Throw-in"]
        m = _metric(rows)
        vals = [m["complete"], m["final"], m["box"], m["loss"],
                100*m["shots"]/max(m["n"],1), 100*m["xg"]/max(m["n"],1)]
        ax = fig.add_axes([x, .17, .37, .57], facecolor="#071522")
        colors = ["#55D187", "#35D0D6", "#FFBD59", "#FF6474", "#A78BFA", "#F4F7F9"]
        ax.barh(range(len(labels)), vals, color=colors)
        ax.set_yticks(range(len(labels)), labels)
        ax.invert_yaxis()
        ax.tick_params(colors="#F4F7F9", labelsize=9, length=0)
        ax.grid(axis="x", color="#315064", alpha=.35)
        [sp.set_visible(False) for sp in ax.spines.values()]
        ax.set_title("OWN THROW-INS" if attacking else "OPPONENT THROW-INS",
                     color="#55D187" if attacking else "#FF6474", fontsize=12, fontweight="bold")
        for i, val in enumerate(vals):
            ax.text(val + max(vals+[1])*.02, i, f"{val:.1f}", color="#F4F7F9", va="center", fontsize=8)
    _save(fig, path)


def _goal_kick_map(path, sequences, team, attacking=True):
    rows = [r for r in sequences if r["attacking"] == attacking and r["restart"] == "Goal Kick"]
    side = "BUILD-UP" if attacking else "OPPONENT GOAL KICKS"
    fig = _figure(
        f"RESTARTS | {side}",
        f"{team}: goal-kick destinations and receivers",
        "Color identifies leading receiver | size increases with pass length | defending events are flipped",
    )
    ax, pitch = _pitch_axis(fig)
    receivers = Counter(r["receiver"] or "Unknown" for r in rows)
    names = [p for p, _ in receivers.most_common(10)]
    palette = ["#35D0D6", "#FF4F8B", "#FFBD59", "#55D187", "#A78BFA",
               "#FF6474", "#F4F7F9", "#55AADD", "#DD77AA", "#99CC55"]
    colors = dict(zip(names, palette))
    lengths = []
    for row in rows:
        event = row["start"]
        end = _end(event)
        if not end:
            continue
        x, y = end[:2]
        if not attacking:
            x, y = 120-x, 80-y
        length = float(event.get("pass", {}).get("length", 0) or 0)
        lengths.append(length)
        pitch.scatter(x, y, ax=ax, s=30+1.8*length, color=colors.get(row["receiver"] or "Unknown", "#9BB0BF"),
                      edgecolors="#F4F7F9", linewidth=.4, alpha=.75)
    for i, player in enumerate(names[:8]):
        fig.text(.77, .70-i*.052, f"{receivers[player]:>3}  {player}", color=colors[player],
                 fontsize=8.7, fontweight="bold")
    m = _metric(rows)
    fig.text(.77, .24, f"{np.mean(lengths) if lengths else 0:.1f}", color="#FFBD59", fontsize=24, fontweight="bold")
    fig.text(.84, .252, "AVG LENGTH", color="#9BB0BF", fontsize=8, fontweight="bold")
    fig.text(.77, .18, f"{m['complete']:.0f}% complete  |  {m['loss']:.0f}% early loss",
             color="#35D0D6", fontsize=9.5, fontweight="bold")
    _save(fig, path)


def _goal_kick_outcomes(path, sequences, team):
    fig = _figure(
        "RESTARTS | GOAL-KICK OUTCOMES",
        f"{team}: build-up choice, security and progression",
        "Short <30 pitch units | medium 30-50 | long >50 | attack and opponent goal kicks compared",
    )
    categories = ["SHORT", "MEDIUM", "LONG"]
    for side, attacking in enumerate((True, False)):
        x0 = .075 + side*.46
        rows = [r for r in sequences if r["attacking"] == attacking and r["restart"] == "Goal Kick"]
        by_length = defaultdict(list)
        for row in rows:
            length = float(row["start"].get("pass", {}).get("length", 0) or 0)
            by_length["SHORT" if length < 30 else "MEDIUM" if length <= 50 else "LONG"].append(row)
        fig.text(x0, .755, "OWN GOAL KICKS" if attacking else "OPPONENT GOAL KICKS",
                 color="#55D187" if attacking else "#FF6474", fontsize=12, fontweight="bold")
        ax = fig.add_axes([x0, .44, .37, .25], facecolor="#071522")
        counts = [len(by_length[k]) for k in categories]
        ax.bar(categories, counts, color=["#35D0D6", "#FFBD59", "#FF4F8B"])
        ax.tick_params(colors="#F4F7F9", length=0)
        [sp.set_visible(False) for sp in ax.spines.values()]
        ax.set_title("DISTRIBUTION CHOICE", color="#9BB0BF", fontsize=9, fontweight="bold")
        for i, key in enumerate(categories):
            m = _metric(by_length[key])
            y = .35-i*.075
            fig.text(x0, y, key, color=["#35D0D6", "#FFBD59", "#FF4F8B"][i], fontsize=9, fontweight="bold")
            fig.text(x0+.10, y, f"{m['complete']:.0f}% comp", color="#F4F7F9", fontsize=8.5)
            fig.text(x0+.21, y, f"{m['final']:.0f}% final 3rd", color="#F4F7F9", fontsize=8.5)
            fig.text(x0+.33, y, f"{m['loss']:.0f}% loss", color="#FF6474", fontsize=8.5)
    _save(fig, path)


def _kickoff_map(path, sequences, team):
    fig = _figure(
        "RESTARTS | KICK-OFF PATTERNS",
        f"{team}: first actions and territory from kick-offs",
        "Own kick-offs in cyan | opponent kick-offs in pink | first four passes in each restart sequence",
    )
    ax, pitch = _pitch_axis(fig)
    totals = Counter()
    for row in [r for r in sequences if r["restart"] == "Kick Off"]:
        color = "#35D0D6" if row["attacking"] else "#FF4F8B"
        passes = [e for e in row["events"] if e.get("type", {}).get("name") == "Pass"][:4]
        for event in passes:
            loc, end = event.get("location"), _end(event)
            if not loc or not end:
                continue
            x, y, ex, ey = *loc[:2], *end[:2]
            if not row["attacking"]:
                x, y, ex, ey = 120-x, 80-y, 120-ex, 80-ey
            pitch.arrows(x, y, ex, ey, ax=ax, color=color, alpha=.22,
                         width=.9, headwidth=3, headlength=3)
        totals["OWN" if row["attacking"] else "OPP"] += 1
    fig.text(.77, .66, f"{totals['OWN']}", color="#35D0D6", fontsize=28, fontweight="bold")
    fig.text(.84, .675, "OWN KICK-OFFS", color="#F4F7F9", fontsize=9, fontweight="bold")
    fig.text(.77, .55, f"{totals['OPP']}", color="#FF4F8B", fontsize=28, fontweight="bold")
    fig.text(.84, .565, "OPPONENT KICK-OFFS", color="#F4F7F9", fontsize=9, fontweight="bold")
    _save(fig, path)


def _kickoff_outcomes(path, sequences, team):
    fig = _figure(
        "RESTARTS | KICK-OFF OUTCOMES",
        f"{team}: security and attacking return after kick-offs",
        "Sequence outcomes compare own and opponent restarts using the recorded kick-off possession",
    )
    labels = ["Completion", "Final-third access", "Box entry", "Early loss", "Shots / 100", "xG / 100"]
    own = _metric([r for r in sequences if r["restart"] == "Kick Off" and r["attacking"]])
    opp = _metric([r for r in sequences if r["restart"] == "Kick Off" and not r["attacking"]])
    own_vals = [own["complete"], own["final"], own["box"], own["loss"],
                100*own["shots"]/max(own["n"],1), 100*own["xg"]/max(own["n"],1)]
    opp_vals = [opp["complete"], opp["final"], opp["box"], opp["loss"],
                100*opp["shots"]/max(opp["n"],1), 100*opp["xg"]/max(opp["n"],1)]
    ax = fig.add_axes([.18, .18, .68, .55], facecolor="#071522")
    y = np.arange(len(labels))
    ax.barh(y-.18, own_vals, height=.34, color="#35D0D6", label="Own kick-offs")
    ax.barh(y+.18, opp_vals, height=.34, color="#FF4F8B", label="Opponent kick-offs")
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.tick_params(colors="#F4F7F9", length=0)
    ax.grid(axis="x", color="#315064", alpha=.35)
    [sp.set_visible(False) for sp in ax.spines.values()]
    ax.legend(frameon=False, labelcolor="#F4F7F9", loc="lower right")
    _save(fig, path)


def _roles(path, sequences, team):
    fig = _figure(
        "SET PIECES & RESTARTS | PLAYER ROLES",
        f"{team}: takers, receivers and first contacts",
        "Season role map across corners, free kicks, throw-ins, goal kicks and kick-offs",
    )
    columns = [
        ("CORNERS", "Corner"), ("FREE KICKS", "Free Kick"), ("THROW-INS", "Throw-in"),
        ("GOAL-KICK RECEIVERS", "Goal Kick"), ("KICK-OFF RECEIVERS", "Kick Off"),
    ]
    own = [r for r in sequences if r["attacking"]]
    for j, (title, restart) in enumerate(columns):
        x = .055 + j*.185
        rows = [r for r in own if r["restart"] == restart]
        counts = Counter()
        for row in rows:
            if restart in {"Goal Kick", "Kick Off"}:
                name = row["receiver"] or "Unknown"
            else:
                name = row["start"].get("player", {}).get("name", "Unknown")
            counts[name] += 1
        fig.text(x, .75, title, color="#35D0D6", fontsize=9, fontweight="bold")
        for i, (player, n) in enumerate(counts.most_common(9)):
            y = .69-i*.057
            fig.add_artist(plt.Rectangle((x, y-.017), .165, .039, transform=fig.transFigure,
                                         facecolor="#112A3C", edgecolor="none"))
            fig.text(x+.006, y, player[:22], color="#F4F7F9", fontsize=7.5)
            fig.text(x+.157, y, str(n), color="#FFBD59", fontsize=8, ha="right", fontweight="bold")
    _save(fig, path)


def build_restart_assets(asset_dir, matches, events_by_id, team):
    """Create the ordered full restart section and return image paths."""
    asset_dir = Path(asset_dir)
    asset_dir.mkdir(parents=True, exist_ok=True)
    sequences = _sequences(matches, events_by_id, team)
    games = len(_valid_team_matches(matches, events_by_id, team))
    specs = [
        ("restart_01_overview.png", _overview, (sequences, team, games)),
        ("restart_02_attacking_corners.png", _delivery_map, (sequences, team, "Corner", True)),
        ("restart_03_attacking_corner_profile.png", _corner_profile, (sequences, team, True)),
        ("restart_04_defending_corners.png", _delivery_map, (sequences, team, "Corner", False)),
        ("restart_05_defending_corner_profile.png", _corner_profile, (sequences, team, False)),
        ("restart_06_attacking_free_kicks.png", _free_kick_profile, (sequences, team, True)),
        ("restart_07_defending_free_kicks.png", _free_kick_profile, (sequences, team, False)),
        ("restart_08_attacking_throw_ins.png", _throw_map, (sequences, team, True)),
        ("restart_09_defending_throw_ins.png", _throw_map, (sequences, team, False)),
        ("restart_10_throw_in_outcomes.png", _throw_outcomes, (sequences, team)),
        ("restart_11_goal_kick_build_up.png", _goal_kick_map, (sequences, team, True)),
        ("restart_12_opponent_goal_kicks.png", _goal_kick_map, (sequences, team, False)),
        ("restart_13_goal_kick_outcomes.png", _goal_kick_outcomes, (sequences, team)),
        ("restart_14_kick_off_patterns.png", _kickoff_map, (sequences, team)),
        ("restart_15_kick_off_outcomes.png", _kickoff_outcomes, (sequences, team)),
        ("restart_16_player_roles.png", _roles, (sequences, team)),
    ]
    paths = []
    for filename, function, args in specs:
        path = asset_dir / filename
        function(path, *args)
        paths.append(path)
    return paths
