# LinkedCode tests

Run commands from the project root. `tests/pytest.ini` sets the Python import path. Use explicit `tests/` paths, or `python -m pytest tests`, so the test configuration is selected.

Example targeted run (no live AI calls):

```powershell
.\venv\Scripts\python.exe -X utf8 -m pytest tests/test_generation_input_contract.py tests/test_constraint_notation.py -q
```

Some files are manual integration scripts. Run them as modules so `backend` imports resolve:

```powershell
.\venv\Scripts\python.exe -X utf8 -m tests.test_generator
```

Live checks such as `tests/test_llm.py` call Groq; generation/workflow scripts can consume quota and modify local practice data. Run live checks deliberately. A directory-wide pytest run includes the live Groq check. Collecting tests with `--collect-only` does not invoke that test function.


Helper scripts (`check_user.py`, `check_password.py`, `migrate_database.py`, `upgrade_existing_user.py`, `run_oracle_generation.py`) also live here. Run them deliberately as modules, e.g. `python -m tests.check_user`; some read or modify the real local database, and the oracle-generation script makes live Groq calls. JSON debug snapshots live in `tests/artifacts/`. Execution configuration examples are in `tests/.env.execution.example`; the real private `.env` stays at the project root.
