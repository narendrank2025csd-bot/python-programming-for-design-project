# Startup Tycoon — Entrepreneur Life Simulator

This project is hosted in the `python-programming-for-design-project` repository.

A runnable Flask + SQLite browser game prototype. Players solve startup missions, earn XP and virtual coins, unlock levels, and purchase avatar accessories, equipment, a sports car, and a startup office.

## Features
- Create an account and log in with password hashing
- Persistent player profile, XP, levels, coins, submissions, inventory, and wallet ledger
- Six business challenge missions
- Offline rubric-based evaluation with feedback
- One reward per mission per player (database uniqueness constraint)
- Shop with eight purchasable items
- Responsive dark neon interface
- No paid API key required
- Hybrid Mode at `/game`: user-created recurring or one-time missions, server-calculated rewards, character progression, category skill paths, achievements, streaks, startup stages, office purchases, virtual employees, boss battles, reward history, and wallet activity
- Quest Village at `/village`: an original responsive isometric-inspired map with interactive buildings, pan/zoom controls, persistent quests, building unlocks/upgrades, and a live quest tracker
- Machine Learning Research Lab at `/ml-lab`: workbook-driven exploration, real scikit-learn regression/classification/clustering, evaluation, private saved models, predictions, experiment history, and one-time research quests
- Additive SQLite game tables; existing accounts, submissions, inventory, and wallet transactions are retained

## Windows / VS Code setup

Open the folder in VS Code. Open **Terminal → New Terminal**, then run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, use Command Prompt terminal instead:

```bat
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Hybrid Mode

After signing in, open **Hybrid Mode** from the navigation (or visit `/game`). Mission rewards are configured in `MISSION_REWARDS` in `app.py`: Easy (20 XP / 10 coins), Medium (50 / 25), Hard (100 / 50), and Epic (200 / 100). The server chooses rewards from the saved difficulty; values in a browser request are ignored.

Player XP continues to use the existing progression rule of 300 lifetime XP per character level. Startup XP is tracked separately and advances the startup through levels and stages. Daily missions can be completed once per UTC day; one-time missions can only be rewarded once. Skills, achievements, streaks, upgrades, employee hires, and boss progress are persisted in SQLite.

Mission deletion is a reversible-style archive: it hides the mission from the active board while preserving its completion and reward history. A recurring mission keeps its daily/one-time recurrence setting after it has been rewarded.

After signing in, open **Quest Village** from the navigation or visit `/village`. Click a building to see its purpose, quests, level, and actions. Accept a village quest, complete the real-world task, and submit action, outcome, and next-step notes. The server validates the required detail and awards the existing XP/coin rewards exactly once into the existing player record and wallet ledger. Completion notes are self-reported; the app validates their written structure, not external real-world activity. Village quest and building progression use additive `player_village_quests` and `village_buildings` tables.

## Machine Learning Research Lab

Install dependencies from the existing virtual environment with `python -m pip install -r requirements.txt`, then sign in and open **Research Lab** from the navigation or visit `/ml-lab`. The application reads `data/Startup_Tycoon_Combined_ML_Dataset_Pack.xlsx` directly with pandas/openpyxl. Its catalogue, row counts, columns, types, and summaries are calculated from the workbook on disk. The three included training sheets are `Synthetic_Sales_Demo` (1,200 rows), `Synthetic_India_Prices` (2,190 rows), and `Synthetic_Ecommerce_Survey` (500 rows); those counts describe the supplied workbook version, not hard-coded training results. `READ_ME_FIRST` is documentation and `Source_Catalog` contains references only—the external datasets listed there are not imported.

All three training sheets are synthetic and illustrative. The generated commodity prices are not actual Indian market prices; the survey-like records are not responses from real people. Good test metrics on this generated data do not establish real-world predictive performance. The India-prices model uses a chronological split when a date feature is selected. Regression/classification use train-only fitted preprocessing pipelines, a reproducible seed, and held-out metrics; K-Means displays cluster sizes and its silhouette score when valid.

Successful experiments save a server-generated model pipeline under `instance/ml_models/`; SQLite stores the owner, dataset hash/origin, task, selected columns, configuration, metrics, model version, deployment status, experiment status, and artifact ID in `ml_experiments`. Experiments begin as not deployed; predictions run locally through the saved pipeline. Model comparison, prediction, and history access are restricted to the signed-in model owner. Model artifacts are never accepted from user uploads. ML Lab progression uses additive `ml_quest_claims`, `ml_dataset_explorations`, `ml_predictions`, and `ml_model_comparisons` tables and grants configured XP/coins once per research quest through the existing wallet ledger.

The project database was backed up before adding the ML tables (`startup_tycoon.db.before_ml_lab_20261026_013310.bak`). The app continues to use `CREATE TABLE IF NOT EXISTS` for additive schema setup; it does not drop or recreate existing tables. Keep a separate backup before future schema changes. For rollback, stop the app, preserve the current database under a different name, and restore the appropriate pre-migration backup as `startup_tycoon.db`; restoring a snapshot discards data written after it was taken.

Run the Hybrid Mode and legacy-route regression tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Important
- The built-in evaluator is an offline keyword rubric, not a real AI model. It is deliberately transparent and needs no API key. You can later replace `score_answer()` in `app.py` with an LLM API integration.
- This is a learning prototype. Before public deployment, set a strong `SECRET_KEY`, disable Flask debug mode, add CSRF protection and rate limiting, configure HTTPS, and review authentication/security.
- The SQLite database (`startup_tycoon.db`) is created automatically next to `app.py`.
- Never put API keys or secrets in frontend JavaScript or commit them to a public repository.
