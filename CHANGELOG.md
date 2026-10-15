# Changelog

## 0.2.0 (unreleased; tag `v0.2.0` is created after merge)

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
