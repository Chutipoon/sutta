# Working on Sutta

Work from this repository directory. Read README.md and docs/VALIDATION.md before changes.

- Canonical Pali string values, Unicode, whitespace, source order, IDs and revision must be preserved.
- Join human translations only by exact segment IDs. Never invent source IDs or references with an LLM.
- Keep source ingestion, embedding, search, translation adapters and API responsibilities separate.
- Run `uv run sutta verify` and `git diff --check`. Use `uv run --no-sync` only when the environment already matches uv.lock and another process holds the Windows executable.
- Do not weaken relevance tests or mark gold cases human_verified without actual independent review.
- Report prototype search/translation as experimental until acceptance gates pass; passing mocks is not linguistic validation.
- Never enable paid fallback, create paid infrastructure, or log/commit credentials. Azure retries must reserve persistent budget before each request.
- Do not modify the upstream checkout. Use the pinned source and model revisions.
- Default service binds to 127.0.0.1. Public deployment requires a separate design for authentication and resource limits.
- Do not rebuild the full corpus index until the pilot comparison is reviewed and a model is selected from evidence.
