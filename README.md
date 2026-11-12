# LinkedCode

Personalized DSA practice with FastAPI, LangGraph, Groq and SQLite. LinkedCode analyzes recent accepted LeetCode submissions, recommends an unsolved problem, and generates an original challenge with execution-based validation.

## Run locally (Windows PowerShell)

From the project root, with the existing virtual environment and private `.env` configured:

```powershell
.\venv\Scripts\python.exe -X utf8 -m uvicorn backend.main:app --reload
```

Open the dashboard at **http://127.0.0.1:8000/app/**. API documentation is at **http://127.0.0.1:8000/docs**. UTF-8 mode prevents Windows console errors when generated text contains mathematical symbols.

Alternatively, serve the frontend separately:

```powershell
.\venv\Scripts\python.exe -m http.server 5500 --directory frontend
```

Open http://localhost:5500 with the API running on port 8000. CORS supports localhost and 127.0.0.1 on ports 5500 and 5173. The same-origin `/app/` dashboard does not require a separate frontend server.

## Practice workflow

1. Create an account or sign in. JWTs stay in browser session storage; signing out removes them. Tokens expire after 30 minutes.
2. Link a LeetCode username, then refresh analysis. Analytics describe the recent accepted-submission sample, not the user's entire LeetCode history.
3. LinkedCode automatically chooses the practice level and topic focus from the last 20 accepted submissions. There are no manual generation preferences.
4. Generate challenges. Keep the page open while the AI pipeline runs. Rate-limit retries wait within the current phase. A draft that still fails both audits gets one fresh problem attempt; failed drafts are never saved. No automatic frontend retry starts an additional generation request.
5. Read saved original challenges, examples and constraints. Solutions and practice cases are available in expandable sections.
6. Update LeetCode practice to attempted, skipped or completed. Completion records a solved problem atomically and is idempotent. Completed recommendations cannot be reopened. Previously recommended, skipped and solved problems are excluded from later candidate pools.
7. Search saved questions by title/topic and filter by difficulty or recommendation status.

## API

All practice endpoints require `Authorization: Bearer <token>`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Obtain JWT |
| GET | `/auth/me` | Current account |
| PATCH | `/auth/profile` | Link/update LeetCode username |
| GET | `/leetcode/analyze` | Recent accepted-submission analytics |
| GET | `/leetcode/recent` | Recent accepted submissions |
| POST | `/recommendations/generate` | Run both agents; automatically based on recent history; no request body |
| GET | `/recommendations/history` | User's recommendation history |
| PATCH | `/recommendations/{slug}/status` | Update `{status}` |
| GET | `/practice/progress` | User-scoped practice counts |
| GET | `/generated-questions` | Saved original challenges |
| GET | `/generated-questions/{id}` | One owned challenge; other users receive 404 |
| GET | `/health` | Health check (public) |

The workflow analyzes the profile, filters candidates, runs the recommendation and generation branches, then saves both results in one SQLite transaction. Generation includes solution auditing/correction, an oracle, 10 regular and 15 verification cases, output comparison, quality evaluation, stress testing and final solution validation. Structural oracle similarity is a heuristic and does not prove independent algorithms.

Data lives in `backend/data/linkedcode.db`. Keep `.env`, API keys, JWT secrets and local databases private. Required environment variable names are `GROQ_API_KEY` and `JWT_SECRET_KEY`; no secrets belong in frontend code.

## Targeted verification

```powershell
.\venv\Scripts\python.exe -X utf8 -m pytest test_practice_api.py test_auth.py test_candidate_service.py test_lifecycle.py test_main.py test_graph.py -q
node --check frontend/script.js
```

API tests use isolated databases and mocked external services. Live Groq runs consume API quota and should be run deliberately.

## Current limitations

Local development integration is implemented. Generated Python runs in subprocesses, not a hardened sandbox; execution isolation remains necessary before exposing generation to untrusted/public users. History currently loads all owned rows, and generation runs within a single HTTP request; pagination and durable background jobs remain future reliability work. There is no deployment setup in this project.

## Python editor and execution

Open an original challenge from the practice trail. The question dialog includes a Python editor with four-space Tab indentation, Ctrl+Enter to run examples, and per-user/per-question drafts in browser session storage.

- **Run examples** judges the program against the question's examples. It does not create a submission or mark the question solved.
- **Custom input** runs stdin and displays stdout/errors; it does not judge correctness.
- **Submit all tests** judges the saved regular and verification cases. Submission verdicts and source code are stored in the local database. Accepted submissions contribute to the unique original-challenges-solved counter. Provider failures are not recorded as wrong answers.

Programs must read stdin and print stdout; Python standard-library solutions are supported. Output comparison ignores whitespace differences and compares remaining tokens exactly. There is no floating-point tolerance or custom checker. Verification inputs/outputs are omitted from execution results, but this is a practice product with revealable reference solutions, not an examination system.

The backend sends source code and inputs to the configured Judge0 service; browser JWTs and project environment variables are not forwarded. The default development endpoint is `https://ce.judge0.com`, with Python language ID `100`, verified during integration. Availability and quotas belong to that provider. To use another Judge0 instance, copy the relevant settings from `.env.execution.example` into the private `.env` and restart the backend. API keys remain backend-only. For token-authenticated instances use `JUDGE0_AUTH_TOKEN`; for a RapidAPI instance set its URL and `JUDGE0_RAPIDAPI_KEY`. Confirm the Python language ID on your chosen instance.

Each case requests 3 CPU seconds, an 8-second wall limit, 128 MB memory, a 64 KB output/file limit, and disabled network access. The adapter polls asynchronous submissions and bounds overall request time to 90 seconds. There is a five-second per-account cooldown and one active execution request per account, maintained in process memory for local single-worker use. No user solution falls back to the application's subprocess validator.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/generated-questions/{id}/execute` | `{code, mode: "examples" / "custom" / "submit", stdin?}` |
| GET | `/generated-questions/{id}/submissions` | Latest 20 owned submission summaries |

Both endpoints authenticate the user and require ownership of a validated original question. Test inputs and expected outputs are loaded from the server; requests cannot override cases, runtimes, limits or provider URLs. LeetCode recommendations still open on LeetCode, since the app does not own their judge test suites.

Execution tests: `python -m pytest test_python_runner.py test_python_execution_api.py -q`. These mock Judge0 and use isolated databases. The original AI-generation validation still uses the existing subprocess executor; hardening that separate path remains pending.

Provider API reference: https://ce.judge0.com/docs

### Performance judging

Full Submit now has two stages. First, the regular correctness and verification cases are judged. If these pass, the judge runs up to three hidden maximum-size patterns (reverse sorted, duplicate-heavy and random) from the problem's stress specification. Reference outputs are calculated on the same Judge0 runtime and 3-second CPU/128 MB limits, then cached in `question_performance_suites`. The cache is invalidated when the reference implementation, specification, runtime, provider or suite version changes.

If the reference cannot finish within the same budget, or its expected output exceeds the supported capture size, submission returns a problem-review/service error instead of blaming the learner. Cases use the declared `n_max`; this implementation supports specifications up to 200,000 elements. Problems without a supported stress specification remain available for example/custom runs, but are not accepted by the full performance judge.

An accepted full submission requires all correctness and performance cases to pass. Performance failures appear as hidden **Performance** results. Small-case-only historical Accepted submissions stay in history as **Correctness only**, and no longer grant full solved credit until resubmitted against the performance suite. This does not prove asymptotic complexity or reject every algorithm labelled brute force: algorithms that finish correctly within the real constraints should pass.

### Groq request budgets

Groq calls now reserve output tokens by phase instead of giving every request a large completion allowance. Recommendations reserve up to 1,200 tokens, audits 1,800, oracle/test-case phases 2,500, and core/correction/refinement phases 3,500. A conservative local input-size estimate reduces that reservation further when needed. All recent-question identities and topic information are kept, while duplicate topic metadata and diagnostic reports are omitted from prompts.

`GROQ_TPM_LIMIT` optionally sets the request-budget limit (default 8,000, matching the observed account limit). The local estimate is not an exact model tokenizer. If Groq reports a 413 with its actual `Limit` and `Requested` counts, the client can reduce the output reservation and retry the same complete prompt once. If it still cannot fit, generation returns a clear 503 budget error instead of repeatedly sending an oversized request. Source code, constraints and testcase inputs are never truncated to force a fit. Ordinary 429 quota exhaustion is separate and can still require waiting for other requests' token usage to expire.

### Solution correction patches

Audit correction responses now contain only the two implementations and their three complexity fields. The backend applies those five fields onto a deep copy of the original problem. Model-returned descriptions, examples, constraints and stress specifications are ignored rather than copied or rewritten. Corrected code still passes structural validation and another correctness audit against the original statement. This also avoids spending completion tokens reproducing immutable problem text.

### Supported generated-problem input contracts

The current stress infrastructure supports `N + N independent bounded integers`, optionally with an independently bounded scalar `K`. Tree/Graph topics may still be personalized, but their structures must be implicit (for example, complete-tree node weights or a Cartesian tree derived from any integer array). Supplied parent arrays, edge lists and index-dependent bounds such as `P[i] < i` require specialized valid-structure generators and are not supported by the current array generator. Such drafts are rejected early with representation guidance for the generation retry; missing array bounds are not fabricated to make a tree draft pass.
