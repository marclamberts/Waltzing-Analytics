#!/usr/bin/env python3
"""Opponent-adjusted shot-suppression model for Opta-style event data.

The model estimates team attacking and defending effects with a
ridge-regularised Poisson regression:

    count ~ home advantage + attacking team + defending team + duration

It fits three related targets:
  1. non-penalty shots (the headline suppression rating);
  2. completed-pass entries into the final third (territory prevention);
  3. non-penalty shots conditional on final-third entries (post-entry control).

Only NumPy and Matplotlib are required. Both are already available in this
workspace's local ``.python_packages`` directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
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


SHOT_TYPES = {13, 14, 15, 16}  # missed, post, saved, goal
PASS_TYPE = 1
PENALTY_QUALIFIER = 9
OWN_GOAL_QUALIFIER = 28
END_X_QUALIFIER = 140
END_Y_QUALIFIER = 141
FINAL_THIRD_X = 66.6667
BOX_X = 83.0
BOX_Y_MIN = 21.1
BOX_Y_MAX = 78.9


@dataclass
class Match:
    match_id: str
    date: str
    home: str
    away: str
    minutes: float
    home_counts: dict[str, int]
    away_counts: dict[str, int]


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
        contestant_id: names
        for contestant_id, names in candidates.items()
        if len(names) != 1
    }
    if unresolved:
        raise ValueError(f"Could not resolve contestant IDs: {unresolved}")
    return {contestant_id: next(iter(names)) for contestant_id, names in candidates.items()}


def blank_counts() -> dict[str, int]:
    return {
        "shots": 0,
        "penalties": 0,
        "shots_on_target": 0,
        "box_shots": 0,
        "final_third_entries": 0,
        "box_entries": 0,
        "completed_passes": 0,
    }


def count_team_events(events: list[dict], contestant_id: str) -> dict[str, int]:
    counts = blank_counts()
    for event in events:
        if event.get("contestantId") != contestant_id:
            continue
        event_type = int(event.get("typeId", -1))
        qualifiers = qualifier_map(event)

        if event_type in SHOT_TYPES:
            if OWN_GOAL_QUALIFIER in qualifiers:
                continue
            if PENALTY_QUALIFIER in qualifiers:
                counts["penalties"] += 1
                continue
            counts["shots"] += 1
            counts["shots_on_target"] += int(event_type in {15, 16})
            counts["box_shots"] += int(float(event.get("x", 0) or 0) >= BOX_X)

        if event_type != PASS_TYPE or int(event.get("outcome", 0)) != 1:
            continue
        counts["completed_passes"] += 1
        if END_X_QUALIFIER not in qualifiers or END_Y_QUALIFIER not in qualifiers:
            continue
        try:
            start_x = float(event.get("x", 0) or 0)
            end_x = float(qualifiers[END_X_QUALIFIER])
            end_y = float(qualifiers[END_Y_QUALIFIER])
        except (TypeError, ValueError):
            continue
        counts["final_third_entries"] += int(
            start_x < FINAL_THIRD_X <= end_x
        )
        counts["box_entries"] += int(
            start_x < BOX_X <= end_x and BOX_Y_MIN <= end_y <= BOX_Y_MAX
        )
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
                home_counts=count_team_events(events, team_to_contestant[home]),
                away_counts=count_team_events(events, team_to_contestant[away]),
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
                    **counts,
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


def centered_effects(fit: PoissonFit, teams: list[str], block: str) -> tuple[np.ndarray, np.ndarray]:
    start = 2 if block == "attack" else 2 + len(teams)
    indexes = np.arange(start, start + len(teams))
    effects = fit.beta[indexes].copy()
    effects -= np.mean(effects)
    standard_errors = np.sqrt(np.maximum(np.diag(fit.covariance)[indexes], 0))
    return effects, standard_errors


def aggregate_team_rows(rows: list[dict], teams: list[str]) -> dict[str, dict[str, float]]:
    result = {
        team: defaultdict(float, {"matches": 0.0, "minutes": 0.0})
        for team in teams
    }
    for row in rows:
        attack = row["attack"]
        defence = row["defence"]
        result[attack]["matches"] += 1
        result[attack]["minutes"] += row["minutes"]
        for metric in (
            "shots",
            "penalties",
            "shots_on_target",
            "box_shots",
            "final_third_entries",
            "box_entries",
        ):
            result[attack][metric + "_for"] += row[metric]
            result[defence][metric + "_against"] += row[metric]
    return result


def add_model_metrics(
    output: dict[str, dict[str, float]],
    rows: list[dict],
    teams: list[str],
    fit: PoissonFit,
    x: np.ndarray,
    offset: np.ndarray,
    prefix: str,
) -> None:
    defence_effects, defence_se = centered_effects(fit, teams, "defence")
    team_index = {team: i for i, team in enumerate(teams)}
    neutral_coefficients = fit.beta.copy()
    defence_start = 2 + len(teams)
    neutral_coefficients[defence_start:defence_start + len(teams)] = np.mean(
        fit.beta[defence_start:defence_start + len(teams)]
    )
    neutral_predictions = np.exp(
        np.clip(x @ neutral_coefficients + offset, -20, 20)
    )

    for team in teams:
        idx = team_index[team]
        effect = float(defence_effects[idx])
        se = float(defence_se[idx])
        mask = np.array([row["defence"] == team for row in rows])
        baseline = float(np.sum(neutral_predictions[mask]))
        modelled = float(np.sum(fit.fitted[mask]))
        observed = float(np.sum([row["shots"] for row in rows if row["defence"] == team]))
        if prefix != "shot":
            observed = float(
                np.sum([
                    row["final_third_entries"]
                    for row in rows if row["defence"] == team
                ])
            )
        output[team][f"{prefix}_defence_effect"] = effect
        output[team][f"{prefix}_suppression_pct"] = 100.0 * (1.0 - math.exp(effect))
        output[team][f"{prefix}_suppression_index"] = 100.0 * math.exp(-effect)
        output[team][f"{prefix}_suppression_pct_low"] = (
            100.0 * (1.0 - math.exp(effect + 1.96 * se))
        )
        output[team][f"{prefix}_suppression_pct_high"] = (
            100.0 * (1.0 - math.exp(effect - 1.96 * se))
        )
        output[team][f"{prefix}_schedule_baseline"] = baseline
        output[team][f"{prefix}_modelled_count"] = modelled
        output[team][f"{prefix}_modelled_prevented"] = baseline - modelled
        output[team][f"{prefix}_observed_below_baseline"] = baseline - observed


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def create_leaderboard(path: Path, table: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered = sorted(table, key=lambda row: row["shot_suppression_pct"])
    teams = [row["team"] for row in ordered]
    values = np.array([row["shot_suppression_pct"] for row in ordered])
    low = np.array([row["shot_suppression_pct_low"] for row in ordered])
    high = np.array([row["shot_suppression_pct_high"] for row in ordered])
    colors = ["#35D0D6" if value >= 0 else "#FF6474" for value in values]

    fig, ax = plt.subplots(figsize=(12, 7), facecolor="#071522")
    ax.set_facecolor("#071522")
    y = np.arange(len(teams))
    ax.barh(y, values, color=colors, alpha=0.92)
    ax.errorbar(
        values, y, xerr=np.vstack((values - low, high - values)),
        fmt="none", ecolor="#DDE7EC", elinewidth=1.2, capsize=3, alpha=0.75
    )
    ax.axvline(0, color="#9BB0BF", linewidth=1)
    ax.set_yticks(y, teams, color="#F4F7F9", fontsize=10)
    ax.tick_params(axis="x", colors="#9BB0BF")
    ax.set_xlabel("Opponent-adjusted non-penalty shot suppression (%)", color="#9BB0BF")
    ax.set_title(
        "Croatia 2025/26 | Shot suppression",
        color="#F4F7F9", fontsize=18, fontweight="bold", loc="left", pad=18
    )
    ax.text(
        0, 1.01,
        "Positive = fewer shots allowed than expected | bars show approximate 95% intervals",
        transform=ax.transAxes, color="#9BB0BF", fontsize=10, va="bottom"
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

    shot_fit, shot_x, shot_offset, shot_cv = fit_target(rows, teams, "shots")
    territory_fit, territory_x, territory_offset, territory_cv = fit_target(
        rows, teams, "final_third_entries"
    )
    entry_fit, entry_x, entry_offset, entry_cv = fit_target(
        rows, teams, "shots", exposure="final_third_entries"
    )

    team_data = aggregate_team_rows(rows, teams)
    add_model_metrics(
        team_data, rows, teams, shot_fit, shot_x, shot_offset, "shot"
    )
    add_model_metrics(
        team_data, rows, teams, territory_fit, territory_x, territory_offset, "territory"
    )
    entry_effects, entry_se = centered_effects(entry_fit, teams, "defence")
    for idx, team in enumerate(teams):
        effect = float(entry_effects[idx])
        team_data[team]["post_entry_defence_effect"] = effect
        team_data[team]["post_entry_suppression_pct"] = 100.0 * (
            1.0 - math.exp(effect)
        )
        team_data[team]["post_entry_suppression_index"] = 100.0 * math.exp(-effect)
        team_data[team]["post_entry_suppression_pct_low"] = 100.0 * (
            1.0 - math.exp(effect + 1.96 * float(entry_se[idx]))
        )
        team_data[team]["post_entry_suppression_pct_high"] = 100.0 * (
            1.0 - math.exp(effect - 1.96 * float(entry_se[idx]))
        )

    table: list[dict] = []
    for team in teams:
        stats = team_data[team]
        nineties = max(stats["minutes"] / 90.0, 1e-9)
        table.append(
            round_record(
                {
                    "rank": 0,
                    "team": team,
                    "matches": int(stats["matches"]),
                    "minutes": stats["minutes"],
                    "shots_against_per90": stats["shots_against"] / nineties,
                    "shots_on_target_against_per90": (
                        stats["shots_on_target_against"] / nineties
                    ),
                    "box_shots_against_per90": stats["box_shots_against"] / nineties,
                    "final_third_entries_against_per90": (
                        stats["final_third_entries_against"] / nineties
                    ),
                    "box_entries_against_per90": stats["box_entries_against"] / nineties,
                    "shot_suppression_pct": stats["shot_suppression_pct"],
                    "shot_suppression_pct_low": stats["shot_suppression_pct_low"],
                    "shot_suppression_pct_high": stats["shot_suppression_pct_high"],
                    "shot_suppression_index": stats["shot_suppression_index"],
                    "modelled_shots_prevented": stats["shot_modelled_prevented"],
                    "observed_shots_below_schedule_baseline": (
                        stats["shot_observed_below_baseline"]
                    ),
                    "territory_suppression_pct": stats["territory_suppression_pct"],
                    "territory_suppression_index": stats["territory_suppression_index"],
                    "post_entry_suppression_pct": stats["post_entry_suppression_pct"],
                    "post_entry_suppression_pct_low": (
                        stats["post_entry_suppression_pct_low"]
                    ),
                    "post_entry_suppression_pct_high": (
                        stats["post_entry_suppression_pct_high"]
                    ),
                    "post_entry_suppression_index": (
                        stats["post_entry_suppression_index"]
                    ),
                }
            )
        )

    table.sort(key=lambda row: row["shot_suppression_index"], reverse=True)
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
                    "non_penalty_shots": row["shots"],
                    "penalties": row["penalties"],
                    "shots_on_target": row["shots_on_target"],
                    "box_shots": row["box_shots"],
                    "final_third_entries": row["final_third_entries"],
                    "box_entries": row["box_entries"],
                }
            )
        )

    diagnostics = {
        "data_directory": str(data_dir.resolve()),
        "matches": len(matches),
        "team_match_rows": len(rows),
        "teams": teams,
        "definitions": {
            "headline": "Non-penalty shots, excluding own goals",
            "territory": "Completed passes crossing into the attacking final third",
            "box_entries": "Completed passes crossing into the penalty area",
            "higher_is_better": True,
            "index_baseline": 100,
        },
        "models": {
            "shots": {
                "ridge": shot_fit.ridge,
                "converged": shot_fit.converged,
                "iterations": shot_fit.iterations,
                "poisson_deviance_per_row": (
                    poisson_deviance(
                        np.array([row["shots"] for row in rows]), shot_fit.fitted
                    ) / len(rows)
                ),
                "cv": shot_cv,
            },
            "territory": {
                "ridge": territory_fit.ridge,
                "converged": territory_fit.converged,
                "iterations": territory_fit.iterations,
                "cv": territory_cv,
            },
            "post_entry": {
                "ridge": entry_fit.ridge,
                "converged": entry_fit.converged,
                "iterations": entry_fit.iterations,
                "cv": entry_cv,
            },
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "team_shot_suppression.csv", table)
    write_csv(output_dir / "match_team_features.csv", match_rows)
    (output_dir / "model_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    create_leaderboard(output_dir / "shot_suppression_leaderboard.png", table)

    print(f"Processed {len(matches)} matches and {len(teams)} teams")
    print(f"Selected shot-model ridge: {shot_fit.ridge:g}")
    print(f"Output: {output_dir.resolve()}")
    print()
    print("Rank  Team                                      Suppression   Index")
    for row in table:
        print(
            f"{row['rank']:>4}  {row['team'][:40]:<40}"
            f" {row['shot_suppression_pct']:>9.2f}%"
            f" {row['shot_suppression_index']:>7.1f}"
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
        default=ROOT / "output" / "shot_suppression",
        help="Directory for model tables, diagnostics, and chart",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    run(arguments.data_dir, arguments.output_dir)
