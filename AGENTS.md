# Repository Guidelines

## Project Structure & Module Organization
FastAPI code lives in `backend/app` (api/services/models/repositories/schemas) with prompts, migrations, and storage assets beside it. Vue 3 + TypeScript files sit in `frontend/src` (`components`, `views`, `stores`, `api`) and publish static assets from `frontend/public`. Docs live in `docs/`, while helper scripts such as `diagnose_3agent.py`, `full_diagnostic.py`, and deployment tooling live in the repo root or `scripts/`. Tests split between `backend/tests` (unit plus `integration/`) and quick smoke utilities in `tests/`.

## Build, Test, and Development Commands
- `cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt` bootstraps dependencies.
- `cd backend && cp env.example .env && python run_migration.py && python reload_prompts.py` prepares the database and prompt templates.
- `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` runs the API, `python -m app.background_processor` enables async analysis, and `cd frontend && npm install && npm run dev` (or `npm run build`) serves the UI.
- Regression staples: `cd backend && pytest tests/test_async_analysis.py -v`, `pytest tests/integration/test_enhanced_mode_integration.py -v`, and `pytest ../tests/test_enhanced_mode.py -q`.

## Coding Style & Naming Conventions
Backend modules target Python 3.11+, four-space indentation, typed signatures, docstrings, and shared loggers (see `backend/app/services/auto_generator_service.py`); keep `snake_case` functions, `PascalCase` models, and enums such as `BugFixMode`. Vue/TypeScript code keeps PascalCase filenames, camelCase composables, script-setup with explicit interfaces, and Prettier enforcement via `npm run format`, while JSON keys mirror the matching Pydantic schema.

## Testing Guidelines
Place new unit tests near their modules inside `backend/tests`, escalate to `backend/tests/integration` whenever the DB, background processor, or AI router is touched, and keep CLI smoke checks under `tests/`. Prefer pytest fixtures, assert on structured payloads (with helpers like `remove_think_tags`), and rerun at least one integration test—capturing the command output in the PR—whenever orchestration or planning code shifts.

## Commit & Pull Request Guidelines
Use Conventional Commit subjects (`fix: …`, `feat: …`, `chore: …`) and keep them under ~72 characters. Summarize the scenario, note which modules or views changed, attach logs for the commands above, and include screenshots for UI updates; keep deployment-tool edits (`SERVER_DEPLOY.sh`, `server_deployment_guide.sh`) separate from feature code whenever possible.

## Configuration & Security Tips
Copy `backend/env.example` to `.env`, keep the filled file untracked, and rotate AI keys when logs are shared. Long-running agents must target the intended SQLite/LibSQL file in `backend/storage/`, and deployment scripts should read credentials from the environment instead of embedding them in `SERVER_DEPLOY.sh`.
