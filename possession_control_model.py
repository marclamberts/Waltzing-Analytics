#!/usr/bin/env python3
"""Opponent-adjusted possession control value model for Opta-style event data.

The model estimates team attacking and defending effects with a
ridge-regularised Poisson regression:

    count ~ home advantage + attacking team + defending team + duration

It focuses on ball retention and territorial progression — not on shot output.
Three related targets are fitted:

  1. possession count — how many distinct in-possession sequences a team creates
     (proxy for press resistance, ball recovery, and retention);
  2. final-third possession entries — possessions that advance into the attacking
     final third (territorial control);
  3. final-third rate — entry count conditioned on possession count as an exposure
     (quality per sequence: passing precision and pattern-of-play value).

For each target the model reports the **attacking** team effect: how much better or
worse a team controls the ball than expected once opponent quality is accounted for.

Only NumPy and Matplotlib are required.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
BUNDLED_PYTHON = Path(
    "/Users/marclamberts/.cache/codex-runtimes/"
    "codex-primary-runtime/dependencies/python/bin/python3"
)
if sys.version_info < (3, 12) and BUNDLED_PYTHON.exists():
    os.execv(
        str(BUNDLED_PYTHON),
        [str(BUNDLED_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]],
    )
sys.path.insert(0, str(ROOT / ".python_packages"))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "tmp" / "matplotlib"))

import numpy as np


PASS_TYPE = 1
CARRY_TYPE = 43
FINAL_THIRD_X = 66.6667
BOX_X = 83.0
BOX_Y_MIN = 21.1
BOX_Y_MAX = 78.9
END_X_QUALIFIER = 140
END_Y_QUALIFIER = 141


@dataclass
class PossessionCounts:
    possession_count: int = 0
    ft_possessions: int = 0
    box_possessions: int = 0
    total_passes: int = 0
    completed_passes: int = 0


@dataclass
class Match:
    match_id: str
    date: str
    home: str
    away: str
    minutes: float
    home_counts: PossessionCounts
    away_counts: PossessionCounts


@dataclass
class PoissonFit:
    beta: np.ndarray
    covariance: np.ndarray
    fitted: np.ndarray
    ridge: float
    converged: bool
    iterations: int


def parse_filename(path: Path) -> tuple[str, str, str]:
    stem = path.stem
    if "_" not in stem or " - " not in stem:
        raise ValueError(f"Expected YYYY-MM-DD_Home - Away.json, got {path.name}")
    date, matchup = stem.split("_", 1)
    home, away = matchup.split(" - ", 1)
    return date, home, away


def qualifier_map(event: dict) -> dict[int, str | None]:
    return {
        int(q["qualifierId"]): q.get("value")
        for q in event.get("qualifier", [])
        if "qualifierId" in q
    }


def map_contestants(files: Iterable[Path]) -> dict[str, str]:
    candidates: dict[str, set[str]] = {}
    appearances: defaultdict[str, int] = defaultdict(int)
    for path in files:
        _, home, away = parse_filename(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        contestant_ids = {
            event.get("contestantId")
            for event in data.get("event", [])
            if event.get("contestantId")
        }
        for contestant_id in contestant_ids:
            appearances[contestant_id] += 1
            pair = {home, away}
            candidates[contestant_id] = (
                pair if contestant_id not in candidates
                else candidates[contestant_id] & pair
            )

    unresolved = {
        cid: names
        for cid, names in candidates.items()
        if len(names) != 1
    }
    if unresolved:
        raise ValueError(f"Could not resolve contestant IDs: {unresolved}")
    return {cid: next(iter(names)) for cid, names in candidates.items()}


def _end_x(event: dict, qualifiers: dict) -> float | None:
    """Return the x-coordinate where the event ended, if available."""
    if END_X_QUALIFIER in qualifiers:
        try:
            return float(qualifiers[END_X_QUALIFIER])
        except (TypeError, ValueError):
            pass
    return None


def _end_y(event: dict, qualifiers: dict) -> float | None:
    if END_Y_QUALIFIER in qualifiers:
        try:
            return float(qualifiers[END_Y_QUALIFIER])
        except (TypeError, ValueError):
            pass
    return None


def count_possession_events(events: list[dict], contestant_id: str) -> PossessionCounts:
    """Group events by possession ID and derive possession-level statistics."""
    # Collect events per possession where this contestant is the possession team.
    # Opta data uses contestantId on each event; we identify the possession team
    # as the contestant whose players generate the majority of actions in the sequence.
    # A simpler heuristic: a possession belongs to the contestant if the first
    # ball-advancing event (pass or carry) in the sequence is from that contestant.

    possession_events: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        pid = event.get("possessionId") or event.get("possession")
        if pid is None:
            continue
        possession_events[pid].append(event)

    counts = PossessionCounts()

    for pid, pev in possession_events.items():
        # Determine possession owner: contestant whose events dominate the sequence.
        contestant_event_count: dict[str, int] = defaultdict(int)
        for e in pev:
            cid = e.get("contestantId")
            if cid:
                contestant_event_count[cid] += 1
        if not contestant_event_count:
            continue
        owner = max(contestant_event_count, key=lambda c: contestant_event_count[c])
        if owner != contestant_id:
            continue

        # Measure maximum x-coordinate reached by the ball during this possession.
        max_x = 0.0
        for e in pev:
            if e.get("contestantId") != contestant_id:
                continue
            try:
                start_x = float(e.get("x", 0) or 0)
            except (TypeError, ValueError):
                start_x = 0.0
            max_x = max(max_x, start_x)
            qualifiers = qualifier_map(e)
            ex = _end_x(e, qualifiers)
            if ex is not None:
                ey = _end_y(e, qualifiers)
                max_x = max(max_x, ex)
                # Box possession: endpoint inside box from outside
                if ex >= BOX_X and ey is not None and BOX_Y_MIN <= ey <= BOX_Y_MAX:
                    pass  # tracked below after full loop

            etype = int(e.get("typeId", -1))
            if etype == PASS_TYPE:
                counts.total_passes += 1
                if int(e.get("outcome", 0)) == 1:
                    counts.completed_passes += 1

        counts.possession_count += 1
        if max_x >= FINAL_THIRD_X:
            counts.ft_possessions += 1
            if max_x >= BOX_X:
                counts.box_possessions += 1

    return counts


def load_matches(data_dir: Path) -> tuple[list[Match], dict[str, str]]:
    files = sorted(data_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON files found in {data_dir}")
    contestant_to_team = map_contestants(files)
    team_to_contestant = {team: cid for cid, team in contestant_to_team.items()}
    matches: list[Match] = []

    for path in files:
        date, home, away = parse_filename(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if home not in team_to_contestant or away not in team_to_contestant:
            raise ValueError(f"Missing contestant mapping for {path.name}")
        details = data.get("matchDetails", {})
        minutes = (
            float(details.get("matchLengthMin", 90) or 90)
            + float(details.get("matchLengthSec", 0) or 0) / 60.0
        )
        events = data.get("event", [])
        matches.append(
            Match(
                match_id=path.stem,
                date=date,
                home=home,
                away=away,
                minutes=max(minutes, 1.0),
                home_counts=count_possession_events(events, team_to_contestant[home]),
                away_counts=count_possession_events(events, team_to_contestant[away]),
            )
        )
    return matches, contestant_to_team


def build_rows(matches: list[Match], teams: list[str]) -> list[dict]:
    rows: list[dict] = []
    for match_number, match in enumerate(matches):
        for is_home, attack, defence, counts in (
            (1, match.home, match.away, match.home_counts),
            (0, match.away, match.home, match.away_counts),
        ):
            rows.append(
                {
                    "match_number": match_number,
                    "match_id": match.match_id,
                    "date": match.date,
                    "attack": attack,
                    "defence": defence,
                    "home": is_home,
                    "minutes": match.minutes,
                    "possession_count": counts.possession_count,
                    "ft_possessions": counts.ft_possessions,
                    "box_possessions": counts.box_possessions,
                    "total_passes": counts.total_passes,
                    "completed_passes": counts.completed_passes,
                }
            )
    return rows


def design_matrix(rows: list[dict], teams: list[str]) -> np.ndarray:
    team_index = {team: i for i, team in enumerate(teams)}
    matrix = np.zeros((len(rows), 2 + 2 * len(teams)), dtype=float)
    matrix[:, 0] = 1.0
    matrix[:, 1] = [row["home"] for row in rows]
    for r, row in enumerate(rows):
        matrix[r, 2 + team_index[row["attack"]]] = 1.0
        matrix[r, 2 + len(teams) + team_index[row["defence"]]] = 1.0
    return matrix


def fit_poisson_ridge(
    x: np.ndarray,
    y: np.ndarray,
    offset: np.ndarray,
    ridge: float,
    max_iter: int = 100,
    tolerance: float = 1e-9,
) -> PoissonFit:
    p = x.shape[1]
    penalty = np.eye(p) * ridge
    penalty[0, 0] = 0.0
    penalty[1, 1] = 0.0
    beta = np.zeros(p)
    beta[0] = math.log(max(float(np.mean(y)), 0.1)) - float(np.mean(offset))
    converged = False

    for iteration in range(1, max_iter + 1):
        eta = np.clip(x @ beta + offset, -20, 20)
        mu = np.exp(eta)
        z = eta - offset + (y - mu) / np.maximum(mu, 1e-10)
        weighted_x = x * np.sqrt(mu)[:, None]
        lhs = weighted_x.T @ weighted_x + penalty
        rhs = x.T @ (mu * z)
        new_beta = np.linalg.solve(lhs, rhs)
        if np.max(np.abs(new_beta - beta)) < tolerance:
            beta = new_beta
            converged = True
            break
        beta = new_beta

    eta = np.clip(x @ beta + offset, -20, 20)
    fitted = np.exp(eta)
    weighted_x = x * np.sqrt(fitted)[:, None]
    covariance = np.linalg.pinv(weighted_x.T @ weighted_x + penalty)
    return PoissonFit(beta, covariance, fitted, ridge, converged, iteration)


def poisson_deviance(y: np.ndarray, mu: np.ndarray) -> float:
    mu = np.maximum(mu, 1e-12)
    terms = np.where(y > 0, y * np.log(y / mu) - (y - mu), mu)
    return float(2 * np.sum(terms))


def select_ridge(
    x: np.ndarray,
    y: np.ndarray,
    offset: np.ndarray,
    match_numbers: np.ndarray,
) -> tuple[float, list[dict]]:
    candidates = (
        0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0,
        64.0, 128.0, 256.0, 512.0, 1024.0,
    )
    folds = match_numbers % 5
    diagnostics: list[dict] = []
    for ridge in candidates:
        fold_deviance = 0.0
        observations = 0
        for fold in range(5):
            train = folds != fold
            test = folds == fold
            fit = fit_poisson_ridge(x[train], y[train], offset[train], ridge)
            predicted = np.exp(np.clip(x[test] @ fit.beta + offset[test], -20, 20))
            fold_deviance += poisson_deviance(y[test], predicted)
            observations += int(np.sum(test))
        diagnostics.append(
            {
                "ridge": ridge,
                "cv_deviance_per_row": fold_deviance / observations,
            }
        )
    best = min(diagnostics, key=lambda row: row["cv_deviance_per_row"])
    return float(best["ridge"]), diagnostics


def fit_target(
    rows: list[dict],
    teams: list[str],
    target: str,
    exposure: str | None = None,
) -> tuple[PoissonFit, np.ndarray, np.ndarray, list[dict]]:
    x = design_matrix(rows, teams)
    y = np.array([row[target] for row in rows], dtype=float)
    duration_offset = np.log(
        np.array([row["minutes"] / 90.0 for row in rows], dtype=float)
    )
    if exposure:
        exposure_values = np.array(
            [max(float(row[exposure]), 0.5) for row in rows], dtype=float
        )
        exposure_scale = float(np.mean(exposure_values))
        offset = duration_offset + np.log(exposure_values / exposure_scale)
    else:
        offset = duration_offset
    match_numbers = np.array([row["match_number"] for row in rows])
    ridge, cv = select_ridge(x, y, offset, match_numbers)
    fit = fit_poisson_ridge(x, y, offset, ridge)
    return fit, x, offset, cv


def centered_attack_effects(
    fit: PoissonFit, teams: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    """Return mean-centred attack effects and their standard errors."""
    indexes = np.arange(2, 2 + len(teams))
    effects = fit.beta[indexes].copy()
    effects -= np.mean(effects)
    standard_errors = np.sqrt(np.maximum(np.diag(fit.covariance)[indexes], 0))
    return effects, standard_errors


def aggregate_team_rows(rows: list[dict], teams: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {
        team: defaultdict(float, {"matches": 0.0, "minutes": 0.0})
        for team in teams
    }
    for row in rows:
        attack = row["attack"]
        defence = row["defence"]
        result[attack]["matches"] += 1
        result[attack]["minutes"] += row["minutes"]
        for metric in (
            "possession_count",
            "ft_possessions",
            "box_possessions",
            "total_passes",
            "completed_passes",
        ):
            result[attack][metric + "_for"] += row[metric]
            result[defence][metric + "_against"] += row[metric]
    return result


def add_possession_metrics(
    output: dict[str, dict],
    rows: list[dict],
    teams: list[str],
    fit: PoissonFit,
    prefix: str,
) -> None:
    """Attach opponent-adjusted attacking possession metrics."""
    effects, se = centered_attack_effects(fit, teams)
    team_index = {team: i for i, team in enumerate(teams)}

    # Compute neutral predictions: zero out defence effects so we see the
    # attacking team effect in isolation.
    neutral_coefficients = fit.beta.copy()
    defence_start = 2 + len(teams)
    neutral_coefficients[defence_start:defence_start + len(teams)] = np.mean(
        fit.beta[defence_start:defence_start + len(teams)]
    )

    x = design_matrix(rows, teams)
    duration_offset = np.log(
        np.array([row["minutes"] / 90.0 for row in rows], dtype=float)
    )
    neutral_predictions = np.exp(np.clip(x @ neutral_coefficients + duration_offset, -20, 20))

    for team in teams:
        idx = team_index[team]
        effect = float(effects[idx])
        sterr = float(se[idx])
        mask = np.array([row["attack"] == team for row in rows])
        baseline = float(np.sum(neutral_predictions[mask]))
        modelled = float(np.sum(fit.fitted[mask]))
        output[team][f"{prefix}_attack_effect"] = effect
        output[team][f"{prefix}_control_pct"] = 100.0 * (math.exp(effect) - 1.0)
        output[team][f"{prefix}_control_index"] = 100.0 * math.exp(effect)
        output[team][f"{prefix}_control_pct_low"] = (
            100.0 * (math.exp(effect - 1.96 * sterr) - 1.0)
        )
        output[team][f"{prefix}_control_pct_high"] = (
            100.0 * (math.exp(effect + 1.96 * sterr) - 1.0)
        )
        output[team][f"{prefix}_schedule_baseline"] = baseline
        output[team][f"{prefix}_modelled_count"] = modelled
        output[team][f"{prefix}_modelled_above_baseline"] = modelled - baseline


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def create_leaderboard(path: Path, table: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered = sorted(table, key=lambda row: row["territory_control_pct"])
    teams = [row["team"] for row in ordered]
    values = np.array([row["territory_control_pct"] for row in ordered])
    low = np.array([row["territory_control_pct_low"] for row in ordered])
    high = np.array([row["territory_control_pct_high"] for row in ordered])
    colors = ["#35D0D6" if v >= 0 else "#FF6474" for v in values]

    fig, ax = plt.subplots(figsize=(12, 7), facecolor="#071522")
    ax.set_facecolor("#071522")
    y = np.arange(len(teams))
    ax.barh(y, values, color=colors, alpha=0.92)
    ax.errorbar(
        values, y, xerr=np.vstack((values - low, high - values)),
        fmt="none", ecolor="#DDE7EC", elinewidth=1.2, capsize=3, alpha=0.75,
    )
    ax.axvline(0, color="#9BB0BF", linewidth=1)
    ax.set_yticks(y, teams, color="#F4F7F9", fontsize=10)
    ax.tick_params(axis="x", colors="#9BB0BF")
    ax.set_xlabel(
        "Opponent-adjusted final-third possession entries vs expected (%)",
        color="#9BB0BF",
    )
    ax.set_title(
        "Possession control | Territory index",
        color="#F4F7F9", fontsize=18, fontweight="bold", loc="left", pad=18,
    )
    ax.text(
        0, 1.01,
        "Positive = more final-third possessions than schedule predicted | bars show approximate 95% intervals",
        transform=ax.transAxes, color="#9BB0BF", fontsize=10, va="bottom",
    )
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="x", color="#315064", alpha=0.35)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def round_record(record: dict) -> dict:
    rounded = {}
    for key, value in record.items():
        if isinstance(value, float):
            rounded[key] = round(value, 4)
        else:
            rounded[key] = value
    return rounded


def run(data_dir: Path, output_dir: Path) -> None:
    matches, contestant_map = load_matches(data_dir)
    teams = sorted(set(contestant_map.values()))
    rows = build_rows(matches, teams)

    # Model 1: possession volume — how many sequences does a team generate?
    volume_fit, volume_x, volume_offset, volume_cv = fit_target(
        rows, teams, "possession_count"
    )
    # Model 2: territory control — possessions reaching the attacking final third
    territory_fit, territory_x, territory_offset, territory_cv = fit_target(
        rows, teams, "ft_possessions"
    )
    # Model 3: possession quality — final-third rate conditional on possession count
    quality_fit, quality_x, quality_offset, quality_cv = fit_target(
        rows, teams, "ft_possessions", exposure="possession_count"
    )

    team_data = aggregate_team_rows(rows, teams)
    add_possession_metrics(team_data, rows, teams, volume_fit, "volume")
    add_possession_metrics(team_data, rows, teams, territory_fit, "territory")

    # Quality model: attach effects directly (same helper, but neutral_predictions
    # use the exposure-adjusted offset already baked into fit.fitted)
    quality_effects, quality_se = centered_attack_effects(quality_fit, teams)
    team_index = {team: i for i, team in enumerate(teams)}
    for team in teams:
        idx = team_index[team]
        effect = float(quality_effects[idx])
        sterr = float(quality_se[idx])
        team_data[team]["quality_attack_effect"] = effect
        team_data[team]["quality_control_pct"] = 100.0 * (math.exp(effect) - 1.0)
        team_data[team]["quality_control_index"] = 100.0 * math.exp(effect)
        team_data[team]["quality_control_pct_low"] = (
            100.0 * (math.exp(effect - 1.96 * sterr) - 1.0)
        )
        team_data[team]["quality_control_pct_high"] = (
            100.0 * (math.exp(effect + 1.96 * sterr) - 1.0)
        )

    # Composite possession control index: mean of three z-scores (on log scale)
    all_volume = np.array([team_data[t]["volume_attack_effect"] for t in teams])
    all_territory = np.array([team_data[t]["territory_attack_effect"] for t in teams])
    all_quality = np.array([team_data[t]["quality_attack_effect"] for t in teams])
    for team in teams:
        composite = float(np.mean([
            team_data[team]["volume_attack_effect"],
            team_data[team]["territory_attack_effect"],
            team_data[team]["quality_attack_effect"],
        ]))
        team_data[team]["possession_control_composite"] = composite
        team_data[team]["possession_control_index"] = 100.0 * math.exp(composite)

    table: list[dict] = []
    for team in teams:
        stats = team_data[team]
        nineties = max(stats["minutes"] / 90.0, 1e-9)
        pass_pct = (
            100.0 * stats["completed_passes_for"] / stats["total_passes_for"]
            if stats["total_passes_for"] > 0 else 0.0
        )
        table.append(
            round_record(
                {
                    "rank": 0,
                    "team": team,
                    "matches": int(stats["matches"]),
                    "minutes": stats["minutes"],
                    "possessions_per90": stats["possession_count_for"] / nineties,
                    "ft_possessions_per90": stats["ft_possessions_for"] / nineties,
                    "box_possessions_per90": stats["box_possessions_for"] / nineties,
                    "pass_completion_pct": pass_pct,
                    "ft_possession_rate": (
                        100.0 * stats["ft_possessions_for"] / stats["possession_count_for"]
                        if stats["possession_count_for"] > 0 else 0.0
                    ),
                    # Opponent-adjusted volume
                    "volume_control_pct": stats["volume_control_pct"],
                    "volume_control_pct_low": stats["volume_control_pct_low"],
                    "volume_control_pct_high": stats["volume_control_pct_high"],
                    "volume_control_index": stats["volume_control_index"],
                    # Opponent-adjusted territory
                    "territory_control_pct": stats["territory_control_pct"],
                    "territory_control_pct_low": stats["territory_control_pct_low"],
                    "territory_control_pct_high": stats["territory_control_pct_high"],
                    "territory_control_index": stats["territory_control_index"],
                    # Opponent-adjusted possession quality per sequence
                    "quality_control_pct": stats["quality_control_pct"],
                    "quality_control_pct_low": stats["quality_control_pct_low"],
                    "quality_control_pct_high": stats["quality_control_pct_high"],
                    "quality_control_index": stats["quality_control_index"],
                    # Composite index
                    "possession_control_index": stats["possession_control_index"],
                }
            )
        )

    table.sort(key=lambda row: row["possession_control_index"], reverse=True)
    for rank, row in enumerate(table, start=1):
        row["rank"] = rank

    match_rows = []
    for row in rows:
        match_rows.append(
            round_record(
                {
                    "match_id": row["match_id"],
                    "date": row["date"],
                    "team": row["attack"],
                    "opponent": row["defence"],
                    "home": row["home"],
                    "minutes": row["minutes"],
                    "possession_count": row["possession_count"],
                    "ft_possessions": row["ft_possessions"],
                    "box_possessions": row["box_possessions"],
                    "total_passes": row["total_passes"],
                    "completed_passes": row["completed_passes"],
                }
            )
        )

    diagnostics = {
        "data_directory": str(data_dir.resolve()),
        "matches": len(matches),
        "team_match_rows": len(rows),
        "teams": teams,
        "definitions": {
            "possession_count": (
                "Distinct possession sequences owned by the team "
                "(majority of events in the sequence belong to the team's contestantId)"
            ),
            "ft_possessions": (
                "Possessions in which the ball advanced to x >= 66.67 "
                "(the attacking final third)"
            ),
            "box_possessions": (
                "Possessions in which the ball reached the penalty area "
                "(x >= 83.0, y between 21.1 and 78.9)"
            ),
            "volume_control_pct": (
                "% more/fewer possession sequences than expected given opponents faced"
            ),
            "territory_control_pct": (
                "% more/fewer final-third possessions than expected given opponents faced"
            ),
            "quality_control_pct": (
                "% higher/lower final-third entry rate per possession than expected "
                "(conditioned on possession volume)"
            ),
            "possession_control_index": (
                "Composite index: 100 = average; >100 = above-average possession control. "
                "Geometric mean of volume, territory, and quality opponent-adjusted multipliers."
            ),
            "higher_is_better": True,
            "index_baseline": 100,
        },
        "models": {
            "volume": {
                "target": "possession_count",
                "ridge": volume_fit.ridge,
                "converged": volume_fit.converged,
                "iterations": volume_fit.iterations,
                "cv": volume_cv,
            },
            "territory": {
                "target": "ft_possessions",
                "ridge": territory_fit.ridge,
                "converged": territory_fit.converged,
                "iterations": territory_fit.iterations,
                "cv": territory_cv,
            },
            "quality": {
                "target": "ft_possessions | possession_count as exposure",
                "ridge": quality_fit.ridge,
                "converged": quality_fit.converged,
                "iterations": quality_fit.iterations,
                "cv": quality_cv,
            },
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "team_possession_control.csv", table)
    write_csv(output_dir / "match_team_possession_features.csv", match_rows)
    (output_dir / "possession_model_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    create_leaderboard(output_dir / "possession_control_leaderboard.png", table)

    print(f"Processed {len(matches)} matches and {len(teams)} teams")
    print(f"Selected volume-model ridge: {volume_fit.ridge:g}")
    print(f"Selected territory-model ridge: {territory_fit.ridge:g}")
    print(f"Selected quality-model ridge: {quality_fit.ridge:g}")
    print(f"Output: {output_dir.resolve()}")
    print()
    print(f"{'Rank':>4}  {'Team':<40}  {'Vol%':>7}  {'Terr%':>7}  {'Qual%':>7}  {'Index':>7}")
    for row in table:
        print(
            f"{row['rank']:>4}  {row['team'][:40]:<40}"
            f" {row['volume_control_pct']:>7.2f}%"
            f" {row['territory_control_pct']:>7.2f}%"
            f" {row['quality_control_pct']:>7.2f}%"
            f" {row['possession_control_index']:>7.1f}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("/Users/marclamberts/Event data/Croatia"),
        help="Directory containing Opta-style match JSON files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "output" / "possession_control",
        help="Directory for model tables, diagnostics, and chart",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    run(arguments.data_dir, arguments.output_dir)
