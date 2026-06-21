# Shot suppression model

This pipeline estimates how effectively each Croatian league team prevents
opponent shots after adjusting for opponent attacking strength, venue, and
match duration.

## Run

```bash
python3 shot_suppression_model.py
```

The defaults read `/Users/marclamberts/Event data/Croatia` and write to
`output/shot_suppression`. Custom paths are supported:

```bash
python3 shot_suppression_model.py \
  --data-dir "/path/to/events" \
  --output-dir "/path/to/output"
```

## Model

The headline model is a ridge-regularised Poisson attack/defence model:

```text
non-penalty shots =
  home advantage + attacking-team strength + defending-team effect + duration
```

Five-fold grouped cross-validation selects the regularisation strength. The
defending-team effect becomes:

- `shot_suppression_pct`: estimated percentage reduction in opponent shots;
- `shot_suppression_index`: 100 is league average and higher is better;
- `modelled_shots_prevented`: expected shots prevented across the schedule;
- approximate 95% intervals, useful as uncertainty guides rather than strict
  causal confidence intervals.

Two companion models explain *how* teams suppress:

- `territory_suppression_pct`: opponent completed-pass entries into the final
  third prevented, adjusted for schedule;
- `post_entry_suppression_pct`: shots prevented after opponents have entered
  the final third.

Penalties and own goals are excluded from the headline shot count because they
do not represent normal shot creation. The event feed has no supplied xG, so
this model measures shot volume suppression rather than chance-quality
suppression.

## Outputs

- `team_shot_suppression.csv` — ranked team leaderboard and component metrics;
- `match_team_features.csv` — auditable match-level input table;
- `model_diagnostics.json` — definitions, selected penalties, and CV results;
- `shot_suppression_leaderboard.png` — presentation-ready leaderboard.
