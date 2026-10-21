# PostgreSQL query performance lab

A runnable companion to Isaiah Aimiton's Medium draft. Requires Python 3.9+ and a running Docker Engine; no Python packages are required. The default image is `postgres:18` (downloaded by Docker if absent).

```sh
cd postgresql-query-lab
python3 run.py
```

The runner creates a uniquely named, disposable container with 2 CPUs and 1 GiB memory, no network and no exposed ports. It loads 10,000 accounts and 1,000,000 transactions, then removes its own container in a `finally` block. It does not connect to existing databases. Results are overwritten on each run. If the process is forcibly killed, remove only the `query-lab-…` container from that run.

The SQL files follow the article in order:

1. `01_setup.sql`: schema, synthetic data, basic timestamp index.
2. `02_computed.sql`: computed UTC-date predicate.
3. `03_range.sql`: half-open timestamp range.
4. `04_index.sql`: partial composite index; rerun 03 afterward.
5. `05_cursor.sql`: prepared cursor query. Execute in the same session with values from the last row of your previous page.
6. `06_maintenance.sql`: table statistics, update, vacuum and example settings. Run with autocommit; VACUUM cannot execute inside a transaction block.

For manual use, execute these only in a fresh disposable database. Setup intentionally fails if the schema already exists; it does not drop existing data.

## Evidence and checks

`results/summary.json` contains five measured execution times per stage, their median, root-plan buffer totals from the final repetition, and validation results. One unreported warm-up precedes each stage. JSON plans are retained for all 15 measured runs. `environment.json` records the server, actual image ID and key settings. These sequential, warmed local measurements are not cold-cache or production-load benchmarks. Image tags can change; use the recorded image ID on this machine for exact image reuse, or set `LAB_IMAGE` to an available version/digest.

The runner asserts identical ordered first-page records across all three stages, identical full results for all 30 date windows between the computed and range forms, genuine timestamp ties, and complete cursor traversal equal to the full ordered result. It also executes the prepared cursor query and maintenance SQL. No application latency or 500-million-row claim is made.

## Requested 500-million-row experiment

```sh
python3 run_scale.py --rows 500000000
```

This version loads and measures a 1-million-row pilot first. Its capacity gate checks both the filesystem containing the project and PostgreSQL's container filesystem, requiring twice the projected relation size plus a 15 GiB reserve. On Docker Desktop the virtual disk can advertise more space than the physical host can supply, so both checks matter. The project-path check assumes the project and Docker data share the host disk; if you move Docker storage elsewhere, update the host-path check to that backing filesystem before using it.

The recorded attempt stopped at the capacity gate: only 37 GiB was available on the host, versus an estimated 66 GiB for the relation alone and a 147 GiB planning allowance. The 500-million-row load and benchmark were NOT completed. A successful capacity check is a heuristic, not a guarantee. If it passes, loading proceeds in 1-million-row batches and checks the 15 GiB reserve before each batch. The container uses the same 2 CPU / 1 GiB limit as the pilot; this favors comparability over fast loading.

`results-scale/` contains the current article's fresh pilot measurements, exact row count, relation sizes, capacity decision, JSON plans and additional text EXPLAIN captures. The text captures are separate runs and their times differ from the five-run medians. `results/` preserves the earlier successful run; normal planner/statistics and timing differences are expected.

At 1 million rows the runner performs the complete correctness checks described above. At larger scales it compares first-page results and the first 10,000 cursor rows to the ordered result, and skips the exhaustive 30-day comparison. The larger load branch has not been executed on this machine because of the capacity gate. Runners remove their own containers on exit, including failures, so large loads do not persist for later manual exploration.

`evidence/` contains screenshots and the local HTML reports used to capture them. These are screenshots of saved database output presented in a report, not screenshots of a live SQL-client session. The article makes this distinction explicit.

## Repository layout

- `run.py`: complete one-million-row reproduction and correctness checks.
- `run_scale.py`: guarded larger-scale runner (500-million-row load not yet completed).
- `sql/`: ordered tutorial queries.
- `results/`: original recorded run.
- `results-scale/`: fresh pilot, text plans, and capacity evidence used in the article.
- `evidence/`: HTML presentations and screenshots of saved output.
- `docs/article.md`: current Medium draft with relative image links.
- `docs/assets/`: article images.
- `docs/publishing-notes.md`: publishing guidance.

## Commit and publish yourself

Git is initialized on `main`, with no commits or configured remote. Review the files before committing:

```sh
git status
git add .
git commit -m "Add reproducible PostgreSQL query performance lab"
```

Then create your personal GitHub repository, add its remote URL, and push. No license has been chosen; add your preferred license before inviting reuse.
