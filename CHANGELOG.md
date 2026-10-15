# Changelog

## 0.2.1 (unreleased; tag `v0.2.1` is created after merge)

### Fixed
- `model_used` now reports the model named in the response's `model` field for chat and embeddings, falling back to the requested name only when the field is absent. Before, it always showed the requested name, even when the endpoint served another model (for example, api.mor.org served `nonexistent-model-xyz` with `google-gemma-4-31b-it`).

### Added
- `requested_model` on every successful chat and embedding result.
- An informational `model_substituted` entry (`requested`, `served`, `endpoint`, `time`, `severity: info`) when the endpoint chose a different model than the one requested. Names match if they differ only in letter case or separators, if the response adds a provider prefix to a name asked for without one or both use the same provider, or if the pair is in the alias list (`BGE-EN-ICL` and `text-embedding-bge-en-icl`). Its text ("served by <model> instead of <requested> (the endpoint picked the model)") is added to `user_alert`, the status stays `ok`, and the agent is told to mention it, not to treat it as a failure.

### Security
- Model names from the endpoint, and requested names when shown, are limited to letters, digits, single spaces and `. _ : / @ + -`, up to 100 characters. A name with anything else, a truncated name, or one that contains the key or repeats the request text is shown as `(invalid model name)` in every output.

### Changed
- README Testing: recommends warm models, notes that `BGE-EN-ICL` embeddings work through an Uplink and hosted embedding models may be cold, and replaces the fallback checks with `BGE-EN-ICL,deepseek-v4-flash` and `BGE-EN-ICL,Aion 3.5 Mini`.
- The install pin moves to `@v0.2.1`.

## 0.2.0 (2026-10-15)

### Changed
- The manifest moved to `.cursor-plugin/plugin.json` (Cursor Plugin format), so `logo` and `variables` are valid. The root `plugin.json` was removed.
- Configuration is now three settings: `MORPHEUS_API_KEY`, `MORPHEUS_MODE` (`api.mor.org` or `uplink`) and `MORPHEUS_BASE_URL`, plus the optional `MORPHEUS_MODELS`.
- The install is pinned to `git+https://github.com/absgrafx/morpheus-grok-mcp@v0.2.0`. The direct dependencies are pinned exactly (`mcp==1.30.0`, `httpx==0.28.1`).
- The `use-morpheus-model` skill is opt-in: Morpheus is used when the user asks for it or has enabled it.
- Logging defaults to warnings only. `--verbose` adds one line per request.
- The server reports its own version (0.2.0) at startup.
- The logo is a 256 x 256 PNG with transparent corners.

### Added
- A model hierarchy for chat, with automatic fallback to the next model on an error, timeout or empty response, and a final handoff to the host's own model (`status: host_fallback`).
- An alert for every failure, with model, endpoint, HTTP status code or error, time and action, in the tool result, as an MCP log message and on standard error.
- `fallback_models` for `morpheus_embed`, and `timeout_seconds` (limited to 1-300 seconds) for chat and embeddings.
- CI validation of the manifest and `mcp.json` with jsonschema.
- `scripts/smoke_mcp.py` (starts the server and lists its tools) and a cursor.directory listing draft in `docs/listing/`.

### Security
- Alerts, logs and errors never contain the raw upstream body, the request text or the configured key (any format).
- Base URLs with a user name or password are rejected. Only `https://` is accepted, with `http://` allowed for localhost, 127.0.0.1 and ::1 only.
- CI has read-only permissions and pins its actions to commit hashes.

### Removed
- Per-agent key slots, key-role variables, `MORPHEUS_MODEL_DEFAULT` and the policy flags. See `docs/DESIGN.md`.

## 0.1.0

- First version: stdio MCP server with `morpheus_chat`, `morpheus_list_models` and `morpheus_embed`.
