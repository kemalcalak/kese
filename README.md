# kese

A personal-finance API: bank statements are imported, transactions are
categorised, budgets are watched, a month is reported. FastAPI over
PostgreSQL, async throughout.

> **Built with [kortex](https://github.com/kemalcalak/kortex)** (a private
> repository for now). The code in this repository was written by kortex's
> Code Engineer, the coding agent in the multi-agent assistant I build,
> running on `gpt-5.6-luna`, one stage at a time. I wrote the requests and
> approved its edits and commands as it worked. Each stage's acceptance tests
> (`tests/acceptance/`) were written before the stage began, and the agent
> was not allowed to change them; a stage counted as done only when they,
> `ruff` and `mypy` were green. Dependencies were added by hand, because
> kortex does not install packages yet.

## What it does

- **Accounts and transactions**: money as `Decimal` in `NUMERIC` columns,
  cursor pagination, filters by text, date range and category.
- **Categories and rules**: case-insensitive matching, the lower priority
  wins, an explicit category beats the rules, and older transactions can be
  re-categorised.
- **Statement import**: CSV or XLSX upload, queued, imported by a worker that
  takes jobs from a Postgres queue (`FOR UPDATE SKIP LOCKED`). The same file
  twice imports nothing twice.
- **Exchange rates** from the Turkish central bank (TCMB), cached per
  requested day, falling back to the last published bulletin.
- **Budgets** per category and month, with a `budget.exceeded` event stream
  (Server-Sent Events, resumable with `Last-Event-ID`).
- **Reports**: a monthly summary with a category ranking, a trend with a
  running total, and streaming CSV and XLSX exports.
- **Hardening**: JWT access and refresh tokens, login rate limiting, a request
  id on every response, one error envelope, and one JSON access-log line per
  request.

Every account, category, rule, budget and report belongs to one user; another
user's data answers `404`.

## Run it

PostgreSQL, the schema and the tests:

```bash
docker compose up -d postgres
uv sync
uv run alembic upgrade head
uv run pytest -q
```

The API in a container, with its documentation at
`http://127.0.0.1:8000/docs`:

```bash
docker compose up -d --build api
```

## Settings

All from the environment, prefixed `KESE_`:

| Variable | Default | |
|---|---|---|
| `KESE_ENV` | `local` | anything else is treated as production |
| `KESE_DATABASE_URL` | `postgresql+asyncpg://kese:kese@127.0.0.1:5433/kese` | the compose database |
| `KESE_JWT_SECRET` | random per process in `local` | required outside `local`, at least 32 characters, or the app refuses to start |
| `KESE_LOGIN_RATE_LIMIT` | `10/minute` | per client and account |
| `KESE_EVENTS_IDLE_SECONDS` | `25` | how long the event stream waits before it closes |

## Known gaps

- The import worker is a function, `kese.worker.run_once()`, not yet a
  long-running process of its own.
- The login rate limit is held in memory, so it counts per process.
- The exchange-rate client has only ever been tested against recorded
  responses, never against the bank's live endpoint.
