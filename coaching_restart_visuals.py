"""Coaching-detail set-piece visuals built on the shared restart model."""

from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from restart_visuals import (
    _end, _event_team, _figure, _is_goal, _metric, _pitch_axis, _save,
    _sequences, _xg,
)


WHITE = "#F4F7F9"
MUTED = "#9BB0BF"
CYAN = "#35D0D6"
PINK = "#FF4F8B"
AMBER = "#FFBD59"
GREEN = "#55D187"
RED = "#FF6474"
PANEL = "#112A3C"
GRID = "#315064"
NAVY = "#071522"


def _zone(location):
    if not location:
        return "UNKNOWN"
    x, y = location[:2]
    if x < 102:
        return "SHORT / EDGE"
    if x >= 114 and 30 <= y <= 50:
        return "SIX-YARD CENTRAL"
    if y < 30:
        return "NEAR CHANNEL"
    if y > 50:
        return "FAR CHANNEL"
    return "PENALTY SPOT"


def _corner_routines(path, seq, team):
    groups = defaultdict(list)
    rows = [r for r in seq if r["attacking"] and r["restart"] == "Corner"]
    for row in rows:
        p = row["start"].get("pass", {})
        length = float(p.get("length", 0) or 0)
        technique = p.get("technique", {}).get("name")
        key = ("SHORT" if length < 15 or p.get("height", {}).get("name") == "Ground Pass"
               else "INSWING" if technique == "Inswinging"
               else "OUTSWING" if technique == "Outswinging" else "STRAIGHT / OTHER")
        groups[key].append(row)
    fig = _figure("SET PIECES | CORNER ROUTINE TYPES",
                  f"{team}: corner selection and attacking return",
                  "Technique and pass-height tags | second phase = shot after the initial three actions")
    labels = ["INSWING", "OUTSWING", "SHORT", "STRAIGHT / OTHER"]
    ax = fig.add_axes([.07, .43, .52, .30], facecolor=NAVY)
    ax.barh(range(4), [len(groups[k]) for k in labels],
            color=[CYAN, AMBER, GREEN, "#A78BFA"])
    ax.set_yticks(range(4), labels); ax.invert_yaxis()
    ax.tick_params(colors=WHITE, length=0); ax.grid(axis="x", color=GRID, alpha=.35)
    [sp.set_visible(False) for sp in ax.spines.values()]
    for i, label in enumerate(labels):
        m = _metric(groups[label]); y = .68-i*.105
        second = sum(shot.get("index", 0) > r["start"].get("index", 0)+3
                     for r in groups[label] for shot in r["shots"])
        fig.text(.66, y, label, color=WHITE, fontsize=10, fontweight="bold")
        fig.text(.80, y, f"{100*m['shots']/max(m['n'],1):.1f} sh/100", color=AMBER, fontsize=10)
        fig.text(.90, y, f"{100*m['xg']/max(m['n'],1):.2f} xG/100", color=CYAN, fontsize=10)
        fig.text(.66, y-.035, f"{second} second-phase shots", color=MUTED, fontsize=8)
    takers = Counter(r["start"].get("player", {}).get("name", "Unknown") for r in rows)
    fig.text(.07, .29, "PRIMARY TAKERS", color=CYAN, fontsize=9, fontweight="bold")
    for i, (player, n) in enumerate(takers.most_common(6)):
        fig.text(.07+i*.145, .235, player[:18], color=WHITE, fontsize=8)
        fig.text(.07+i*.145, .195, str(n), color=AMBER, fontsize=13, fontweight="bold")
    _save(fig, path)


def _first_contacts(path, seq, team):
    fig = _figure("SET PIECES | FIRST CONTACTS & AERIAL THREATS",
                  f"{team}: who reaches corner deliveries first?",
                  "First meaningful event after delivery | aerial outcomes only where explicitly tagged")
    for side, (title, rows) in enumerate((
        ("ATTACKING", [r for r in seq if r["attacking"] and r["restart"] == "Corner"]),
        ("DEFENDING", [r for r in seq if not r["attacking"] and r["restart"] == "Corner"]))):
        x0 = .055+side*.47; contacts = Counter(); players = Counter(); headers = Counter()
        for row in rows:
            candidates = [e for e in row["events"]
                          if e.get("index", 0) > row["start"].get("index", 0)
                          and e.get("type", {}).get("name") in
                          {"Shot", "Clearance", "Duel", "Pass", "Ball Receipt*"}]
            if candidates:
                event = candidates[0]
                contacts[event.get("type", {}).get("name", "Other")] += 1
                players[event.get("player", {}).get("name", "Unknown")] += 1
            for shot in row["shots"]:
                if shot.get("shot", {}).get("body_part", {}).get("name") == "Head":
                    headers[shot.get("player", {}).get("name", "Unknown")] += 1
        fig.text(x0, .75, title, color=GREEN if side == 0 else RED, fontsize=12, fontweight="bold")
        labels = ["Shot", "Clearance", "Duel", "Pass", "Ball Receipt*"]
        ax = fig.add_axes([x0, .46, .39, .22], facecolor=NAVY)
        ax.bar(labels, [contacts[k] for k in labels],
               color=[AMBER, CYAN, RED, "#A78BFA", GREEN])
        ax.tick_params(colors=WHITE, labelsize=7, length=0)
        [sp.set_visible(False) for sp in ax.spines.values()]
        fig.text(x0, .39, "FIRST CONTACT", color=MUTED, fontsize=8, fontweight="bold")
        fig.text(x0+.27, .39, "HEADER THREATS", color=MUTED, fontsize=8, fontweight="bold")
        for i, (player, n) in enumerate(players.most_common(5)):
            fig.text(x0, .35-i*.045, player[:25], color=WHITE, fontsize=8)
            fig.text(x0+.23, .35-i*.045, str(n), color=CYAN, fontsize=8, fontweight="bold")
        for i, (player, n) in enumerate(headers.most_common(5)):
            fig.text(x0+.27, .35-i*.045, player[:22], color=WHITE, fontsize=8)
            fig.text(x0+.41, .35-i*.045, str(n), color=AMBER, fontsize=8, fontweight="bold")
    _save(fig, path)


def _target_zones(path, seq, team):
    rows = [r for r in seq if r["attacking"] and r["restart"] == "Corner"]
    zones = defaultdict(list)
    fig = _figure("SET PIECES | CORNER TARGET ZONES",
                  f"{team}: where deliveries are aimed and where shots follow",
                  "Delivery endpoints translated into coaching zones")
    ax, pitch = _pitch_axis(fig, (.055, .12, .58, .64), half=True)
    for row in rows:
        end = _end(row["start"])
        if end:
            zones[_zone(end)].append(row)
            pitch.scatter(end[0], end[1], ax=ax, s=28, color=WHITE, alpha=.34)
    for text, pos, color in (("NEAR", (111, 22), CYAN), ("PENALTY SPOT", (108, 40), AMBER),
                             ("FAR", (111, 58), PINK)):
        pitch.annotate(text, pos, ax=ax, color=color, fontsize=8, fontweight="bold")
    for i, label in enumerate(("SIX-YARD CENTRAL", "PENALTY SPOT", "NEAR CHANNEL",
                               "FAR CHANNEL", "SHORT / EDGE")):
        m = _metric(zones[label]); y = .68-i*.10
        fig.text(.68, y, label, color=WHITE, fontsize=9, fontweight="bold")
        fig.text(.84, y, str(m["n"]), color=AMBER, fontsize=10, fontweight="bold")
        fig.text(.89, y, f"{100*m['xg']/max(m['n'],1):.2f} xG/100", color=CYAN, fontsize=10)
        fig.text(.68, y-.034, f"{m['shots']} shots | {m['goals']} goals", color=MUTED, fontsize=8)
    _save(fig, path)


def _defensive_indicators(path, seq, team):
    rows = [r for r in seq if not r["attacking"] and r["restart"] == "Corner"]
    fig = _figure("SET PIECES | DEFENSIVE STRUCTURE INDICATORS",
                  f"{team}: defensive corner contacts and clearance footprint",
                  "Event-data indicators only - marking, blocks and screens require video confirmation")
    ax, pitch = _pitch_axis(fig, (.055, .12, .55, .64), half=True)
    contacts, clears, duels = [], [], []; leaders = Counter()
    for row in rows:
        for event in row["events"]:
            if _event_team(event) != team or not event.get("location"): continue
            typ = event.get("type", {}).get("name")
            flipped = [120-event["location"][0], 80-event["location"][1]]
            if typ in {"Clearance", "Duel", "Block", "Interception"}: contacts.append(flipped)
            if typ == "Clearance":
                clears.append(flipped); leaders[event.get("player", {}).get("name", "Unknown")] += 1
            elif typ == "Duel": duels.append(flipped)
    if contacts:
        bs = pitch.bin_statistic([p[0] for p in contacts], [p[1] for p in contacts],
                                 statistic="count", bins=(5, 6), normalize=True)
        pitch.heatmap(bs, ax=ax, cmap="YlGnBu", alpha=.75)
    if clears: pitch.scatter([p[0] for p in clears], [p[1] for p in clears], ax=ax, s=32, color=CYAN, marker="s", alpha=.5)
    if duels: pitch.scatter([p[0] for p in duels], [p[1] for p in duels], ax=ax, s=38, color=RED, marker="x", alpha=.65)
    fig.text(.65, .72, "INTERPRETATION", color=CYAN, fontsize=10, fontweight="bold")
    fig.text(.65, .66, "Central contact concentration is consistent with protected zones plus individual match-ups.",
             color=WHITE, fontsize=8.5, wrap=True)
    fig.text(.65, .56, "VIDEO CHECKLIST", color=AMBER, fontsize=9, fontweight="bold")
    for i, text in enumerate(("Zonal / man / hybrid assignments", "Goalkeeper screens and blocking",
                              "Players held for counters", "Changes after substitutions")):
        fig.text(.65, .515-i*.05, f"- {text}", color=MUTED, fontsize=8.5)
    fig.text(.65, .28, "CLEARANCE LEADERS", color=MUTED, fontsize=8, fontweight="bold")
    for i, (player, n) in enumerate(leaders.most_common(5)):
        fig.text(.65, .24-i*.04, player[:27], color=WHITE, fontsize=8)
        fig.text(.92, .24-i*.04, str(n), color=CYAN, fontsize=8, ha="right", fontweight="bold")
    _save(fig, path)


def _counter_exposure(path, seq, team):
    rows = [r for r in seq if r["attacking"] and r["restart"] in {"Corner", "Free Kick"}]
    fig = _figure("SET PIECES | REST DEFENCE & COUNTER EXPOSURE",
                  f"{team}: opponent exits after attacking restarts",
                  "Opponent actions retained inside the recorded restart possession")
    ax, pitch = _pitch_axis(fig); points = []; arrows = []; outlets = Counter()
    for row in rows:
        opponent_events = [e for e in row["events"] if _event_team(e) != team]
        if not opponent_events:
            continue
        first_index = opponent_events[0].get("index", 0)
        for event in [e for e in opponent_events if e.get("index", 0) <= first_index+10]:
            loc = event.get("location")
            if loc:
                points.append((120-loc[0], 80-loc[1]))
                outlets[event.get("player", {}).get("name", "Unknown")] += 1
            if event.get("type", {}).get("name") == "Pass" and loc and _end(event):
                end = _end(event); arrows.append((120-loc[0], 80-loc[1], 120-end[0], 80-end[1]))
    for a, b, c, d in arrows:
        pitch.arrows(a, b, c, d, ax=ax, color=RED, alpha=.22, width=.8, headwidth=3, headlength=3)
    if points: pitch.scatter([p[0] for p in points], [p[1] for p in points], ax=ax, s=25, color=AMBER, alpha=.4)
    fig.text(.77, .68, f"{len(points)}", color=RED, fontsize=28, fontweight="bold")
    fig.text(.84, .695, "OPPONENT ACTIONS", color=WHITE, fontsize=8, fontweight="bold")
    fig.text(.77, .56, f"{len(arrows)}", color=CYAN, fontsize=24, fontweight="bold")
    fig.text(.84, .58, "COUNTER PASSES", color=WHITE, fontsize=8, fontweight="bold")
    fig.text(.77, .45, "FIRST OUTLETS", color=MUTED, fontsize=8, fontweight="bold")
    for i, (player, n) in enumerate(outlets.most_common(6)):
        fig.text(.77, .41-i*.045, player[:23], color=WHITE, fontsize=8)
        fig.text(.94, .41-i*.045, str(n), color=AMBER, fontsize=8, ha="right", fontweight="bold")
    _save(fig, path)


def _throw_pressure(path, seq, team):
    rows = [r for r in seq if r["attacking"] and r["restart"] == "Throw-in"]
    thirds = {"DEFENSIVE": [], "MIDDLE": [], "FINAL": []}
    for row in rows:
        loc = row["start"].get("location")
        if loc: thirds["DEFENSIVE" if loc[0] < 40 else "MIDDLE" if loc[0] < 80 else "FINAL"].append(row)
    fig = _figure("RESTARTS | THROW-IN ROUTINES BY ZONE",
                  f"{team}: direction, pressure response and retention",
                  "Pressure is taken from the receiver's first recorded action")
    for i, (third, subset) in enumerate(thirds.items()):
        x0 = .07+i*.31; directions = Counter(); pressured = observed = retained = 0
        for row in subset:
            loc, end = row["start"].get("location"), _end(row["start"])
            if loc and end:
                gain = end[0]-loc[0]
                directions["FORWARD" if gain > 5 else "BACKWARD" if gain < -5 else "LATERAL"] += 1
            receiver = next((e for e in row["events"][1:] if _event_team(e) == team and e.get("player")), None)
            if receiver: observed += 1; pressured += bool(receiver.get("under_pressure"))
            retained += row["completed"] and not row["early_loss"]
        fig.text(x0, .73, third, color=CYAN, fontsize=12, fontweight="bold")
        labels = ["FORWARD", "LATERAL", "BACKWARD"]
        ax = fig.add_axes([x0, .43, .25, .22], facecolor=NAVY)
        ax.bar(labels, [directions[k] for k in labels], color=[GREEN, CYAN, RED])
        ax.tick_params(colors=WHITE, labelsize=7, length=0); [sp.set_visible(False) for sp in ax.spines.values()]
        vals = [("VOLUME", len(subset)), ("RECEIVER PRESSURED", f"{100*pressured/max(observed,1):.0f}%"),
                ("SECURE RETENTION", f"{100*retained/max(len(subset),1):.0f}%"),
                ("SHOTS / 100", f"{100*sum(len(r['shots']) for r in subset)/max(len(subset),1):.1f}")]
        for j, (label, value) in enumerate(vals):
            fig.text(x0, .35-j*.06, label, color=MUTED, fontsize=8)
            fig.text(x0+.22, .35-j*.06, str(value), color=AMBER, fontsize=9, ha="right", fontweight="bold")
    _save(fig, path)


def _direct_free_kicks(path, seq, team):
    fig = _figure("SET PIECES | DIRECT FREE KICKS",
                  f"{team}: direct-shot threat and goalkeeper outcomes",
                  "Wall and goalkeeper starting positions require video confirmation")
    ax, pitch = _pitch_axis(fig, (.055, .12, .58, .64), half=True)
    own, against = [], []
    for row in [r for r in seq if r["restart"] == "Free Kick"]:
        for shot in row["shots"]:
            if shot.get("shot", {}).get("type", {}).get("name") != "Free Kick" or not shot.get("location"): continue
            target = own if row["attacking"] else against; target.append(shot)
            x, y = shot["location"][:2]
            if not row["attacking"]: y = 80-y
            pitch.scatter(x, y, ax=ax, s=90+800*_xg(shot), color=CYAN if row["attacking"] else RED,
                          marker="*" if _is_goal(shot) else "o", edgecolors=WHITE, linewidth=.8)
    for i, (label, shots, color) in enumerate((("FOR", own, CYAN), ("AGAINST", against, RED))):
        x0 = .68+i*.14
        fig.text(x0, .70, label, color=color, fontsize=10, fontweight="bold")
        fig.text(x0, .62, str(len(shots)), color=WHITE, fontsize=27, fontweight="bold")
        fig.text(x0, .57, f"{sum(_xg(s) for s in shots):.2f} xG", color=AMBER, fontsize=10)
        fig.text(x0, .52, f"{sum(_is_goal(s) for s in shots)} goals", color=WHITE, fontsize=9)
    fig.text(.68, .39, "VIDEO CHECK", color=AMBER, fontsize=9, fontweight="bold")
    for i, text in enumerate(("Wall size and jump", "Keeper sightline", "Weak-side coverage", "Rebound roles")):
        fig.text(.68, .345-i*.05, f"- {text}", color=MUTED, fontsize=8.5)
    _save(fig, path)


def _goal_kick_press(path, seq, team):
    rows = [r for r in seq if not r["attacking"] and r["restart"] == "Goal Kick"]
    fig = _figure("RESTARTS | GOAL-KICK PRESS PLAN",
                  f"{team}: pressure and recovery response to opposition goal kicks",
                  "White destination | red pressure | green recovery")
    ax, pitch = _pitch_axis(fig); ends = []; pressures = []; recoveries = []
    for row in rows:
        if _end(row["start"]): ends.append((120-_end(row["start"])[0], 80-_end(row["start"])[1]))
        start_index = row["start"].get("index", 0)
        for event in [e for e in row["events"] if e.get("index", 0) <= start_index+15]:
            if _event_team(event) != team or not event.get("location"): continue
            loc = (120-event["location"][0], 80-event["location"][1])
            if event.get("type", {}).get("name") == "Pressure": pressures.append(loc)
            elif event.get("type", {}).get("name") in {"Ball Recovery", "Interception"}: recoveries.append(loc)
    if ends: pitch.scatter([p[0] for p in ends], [p[1] for p in ends], ax=ax, s=35, color=WHITE, alpha=.35)
    if pressures: pitch.scatter([p[0] for p in pressures], [p[1] for p in pressures], ax=ax, s=45, color=RED, marker="x", alpha=.7)
    if recoveries: pitch.scatter([p[0] for p in recoveries], [p[1] for p in recoveries], ax=ax, s=55, color=GREEN, marker="D", alpha=.8)
    fig.text(.77, .68, "PRESSING TRIGGERS", color=CYAN, fontsize=10, fontweight="bold")
    for i, text in enumerate(("Marked short receiver", "Receiver facing own goal",
                              "Lofted ball to touchline", "Loose second ball")):
        fig.text(.77, .62-i*.058, f"{i+1}. {text}", color=WHITE, fontsize=8.5)
    fig.text(.77, .33, f"{len(pressures)} pressures", color=RED, fontsize=11, fontweight="bold")
    fig.text(.77, .28, f"{len(recoveries)} recoveries", color=GREEN, fontsize=11, fontweight="bold")
    _save(fig, path)


def _kickoff_context(path, seq, team):
    rows = [r for r in seq if r["restart"] == "Kick Off"]
    groups = defaultdict(list)
    for row in rows:
        minute = row["start"].get("minute", 0)
        if minute <= 1:
            label = "MATCH OPENING"
        elif 45 <= minute <= 47:
            label = "SECOND-HALF OPENING"
        elif row["attacking"]:
            label = "AFTER CONCEDING"
        else:
            label = "AFTER SCORING"
        groups[label].append(row)
    fig = _figure("RESTARTS | KICK-OFF CONTEXT",
                  f"{team}: opening and restart-after-goal tendencies",
                  "Classification uses match time and the recorded kick-off sequence")
    for i, label in enumerate(("MATCH OPENING", "SECOND-HALF OPENING", "AFTER CONCEDING", "AFTER SCORING")):
        x0 = .055+i*.235; subset = groups[label]; m = _metric(subset); gains = []
        for row in subset:
            loc, end = row["start"].get("location"), _end(row["start"])
            if loc and end: gains.append(end[0]-loc[0])
        fig.text(x0, .70, label, color=CYAN, fontsize=10, fontweight="bold")
        fig.text(x0, .60, str(len(subset)), color=WHITE, fontsize=32, fontweight="bold")
        for j, (name, value) in enumerate((
            ("FIRST-PASS GAIN", f"{np.mean(gains) if gains else 0:+.1f}"),
            ("FINAL-THIRD ACCESS", f"{m['final']:.0f}%"), ("EARLY LOSS", f"{m['loss']:.0f}%"),
            ("SHOTS / 100", f"{100*m['shots']/max(m['n'],1):.1f}"))):
            fig.text(x0, .48-j*.075, name, color=MUTED, fontsize=8)
            fig.text(x0+.18, .48-j*.075, value, color=AMBER, fontsize=10, ha="right", fontweight="bold")
    _save(fig, path)


def _recent_trend(path, seq, team):
    dates = sorted({r["date"] for r in seq}); recent_dates = set(dates[-3:])
    labels = ["Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"]
    season_sh, recent_sh, season_xg, recent_xg = [], [], [], []
    for restart in labels:
        season = [r for r in seq if r["attacking"] and r["restart"] == restart]
        recent = [r for r in season if r["date"] in recent_dates]
        season_sh.append(100*sum(len(r["shots"]) for r in season)/max(len(season),1))
        recent_sh.append(100*sum(len(r["shots"]) for r in recent)/max(len(recent),1))
        season_xg.append(100*sum(r["xg"] for r in season)/max(len(season),1))
        recent_xg.append(100*sum(r["xg"] for r in recent)/max(len(recent),1))
    fig = _figure("SET PIECES | RECENT TREND VS SEASON",
                  f"{team}: are restart tendencies changing?",
                  "Last three completed matches compared with the full available season")
    for j, (title, a, b) in enumerate((("SHOTS PER 100", season_sh, recent_sh), ("xG PER 100", season_xg, recent_xg))):
        ax = fig.add_axes([.07+j*.47, .20, .40, .52], facecolor=NAVY); y = np.arange(5)
        ax.barh(y-.18, a, height=.34, color=GRID, label="Season")
        ax.barh(y+.18, b, height=.34, color=AMBER, label="Last 3")
        ax.set_yticks(y, labels); ax.invert_yaxis(); ax.tick_params(colors=WHITE, length=0)
        ax.grid(axis="x", color=GRID, alpha=.35); [sp.set_visible(False) for sp in ax.spines.values()]
        ax.set_title(title, color=WHITE, fontsize=10, fontweight="bold")
        ax.legend(frameon=False, labelcolor=WHITE, fontsize=8)
    _save(fig, path)


def _coaching_plan(path, seq, team):
    threats = Counter(); takers = Counter()
    for row in seq:
        if not row["attacking"] or row["restart"] not in {"Corner", "Free Kick"}: continue
        takers[row["start"].get("player", {}).get("name", "Unknown")] += 1
        for shot in row["shots"]:
            threats[shot.get("player", {}).get("name", "Unknown")] += 1+5*_xg(shot)
    fig = _figure("SET PIECES | COACHING PLAN",
                  f"FC Hradec Králové restart plan against {team}",
                  "Training-pitch actions derived from the season restart profile")
    columns = [
        ("THREE ATTACKING ROUTINES", ["1. Overload penalty spot; screen central clearer.",
         "2. Short corner, recycle, attack second phase.", "3. Far-post runner plus edge-box rebound cover."], GREEN),
        ("THREE DEFENSIVE RULES", ["1. Protect six-yard centre before tracking runners.",
         "2. Assign edge-box player for recycled deliveries.", "3. Keep a two-player counter outlet when possible."], RED)]
    for i, (title, items, color) in enumerate(columns):
        x0 = .06+i*.47; fig.text(x0, .73, title, color=color, fontsize=11, fontweight="bold")
        for j, item in enumerate(items):
            y = .65-j*.105
            fig.add_artist(plt.Rectangle((x0, y-.035), .40, .073, transform=fig.transFigure,
                                         facecolor=PANEL, edgecolor=GRID))
            fig.text(x0+.015, y, item, color=WHITE, fontsize=8.5, va="center")
    fig.text(.06, .33, "OPPOSITION THREATS TO ASSIGN", color=AMBER, fontsize=10, fontweight="bold")
    for i, (player, score) in enumerate(threats.most_common(5)):
        fig.text(.06+i*.175, .275, player[:21], color=WHITE, fontsize=8)
        fig.text(.06+i*.175, .235, f"threat {score:.1f}", color=CYAN, fontsize=8, fontweight="bold")
    fig.text(.06, .16, "PRIMARY TAKERS", color=MUTED, fontsize=8, fontweight="bold")
    fig.text(.18, .16, " | ".join(p for p, _ in takers.most_common(4)), color=WHITE, fontsize=8.5)
    fig.text(.06, .10, "SUBSTITUTION RULE", color=PINK, fontsize=9, fontweight="bold")
    fig.text(.18, .10, "Re-rank active aerial threats; transfer the strongest marker and reconfirm edge-box and outlet roles.",
             color=WHITE, fontsize=8.5)
    _save(fig, path)


def build_coaching_restart_assets(asset_dir, matches, events_by_id, team):
    asset_dir = Path(asset_dir); asset_dir.mkdir(parents=True, exist_ok=True)
    seq = _sequences(matches, events_by_id, team)
    specs = [
        ("restart_17_corner_routine_types.png", _corner_routines),
        ("restart_18_first_contacts.png", _first_contacts),
        ("restart_19_corner_target_zones.png", _target_zones),
        ("restart_20_defensive_structure.png", _defensive_indicators),
        ("restart_21_counter_exposure.png", _counter_exposure),
        ("restart_22_throw_pressure.png", _throw_pressure),
        ("restart_23_direct_free_kicks.png", _direct_free_kicks),
        ("restart_24_goal_kick_press.png", _goal_kick_press),
        ("restart_25_kickoff_context.png", _kickoff_context),
        ("restart_26_recent_trends.png", _recent_trend),
        ("restart_27_coaching_plan.png", _coaching_plan),
    ]
    paths = []
    for filename, function in specs:
        path = asset_dir / filename; function(path, seq, team); paths.append(path)
    return paths
