# TrialGuard AI Deployment Notes

## Supported deployment shape

The current portfolio release is designed for **one API instance** with a persistent volume. SQLite stores the study registry, review state, and audit trail; source CSV snapshots are stored under the same persistent data root.

This is intentionally simple and appropriate for a portfolio/demo deployment. Horizontal scaling to multiple API replicas would require a shared transactional database (for example PostgreSQL) plus shared/object storage for study source files.

## Docker Compose

Start Ollama on the host first and make sure the configured model is present:

```bash
ollama list
ollama pull llama3.2:3b
```

Then:

```bash
cp .env.example .env
docker compose up --build
```

Services:

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Dashboard: http://localhost:8501
- Liveness: http://localhost:8000/health
- Readiness: http://localhost:8000/ready

Docker Compose persists application data in the named `trialguard-data` volume.

## Remote container deployment

The API and dashboard can run from the same image with different commands. Required environment variables are documented in `.env.example`.

For a remote deployment:

1. Attach persistent storage and set `TRIALGUARD_DATA_DIR` to that mounted path.
2. Point `TRIALGUARD_OLLAMA_BASE_URL` at a reachable Ollama-compatible service if AI Investigation is enabled.
3. Expose the API and dashboard through HTTPS/reverse proxy infrastructure.
4. Keep one API replica while SQLite is used.
5. Treat the application as synthetic/demo software unless real clinical-data security, authentication, authorization, validation, retention, and regulatory controls have been implemented.

## Health semantics

`GET /health` is liveness only.

`GET /ready` verifies the persistent data directory is writable and SQLite can answer a query. Ollama is reported as an agent dependency but does **not** block core readiness because deterministic QC and human review remain useful when the model service is offline.

## CI

GitHub Actions runs:

- source compilation
- the full pytest suite
- a Docker image build

No live Ollama model is required for CI because agent routing/tool tests do not make live model calls.
