# Morpheus Inference for Cursor

<p align="center">
  <img src="assets/logo.png" alt="Morpheus Inference logo" width="128" height="128" />
</p>

Send chat and embedding requests to Morpheus, a decentralized AI inference network, through api.mor.org or your own Uplink.

- Plugin name: `morpheus-inference` (Cursor Plugin, manifest in `.cursor-plugin/plugin.json`)
- Repository: `absgrafx/morpheus-grok-mcp`
- Version: 0.2.1 (see [CHANGELOG.md](CHANGELOG.md))
- Author: ABSGrafx, devs@absgrafx.com
- License: MIT

## What it does

The plugin adds an MCP (Model Context Protocol) server, which gives your agent three tools, plus two skills.

| Tool | What it calls |
|------|---------------|
| `morpheus_chat` | `POST {base}/chat/completions` |
| `morpheus_embed` | `POST {base}/embeddings` |
| `morpheus_list_models` | `GET {base}/models` |

| Skill | Purpose |
|-------|---------|
| `use-morpheus-model` | Tells the agent to use Morpheus only when you ask for it or have said you want it, and how to handle fallbacks and alerts. |
| `morpheus-setup` | Walks through configuration and a first test. |

Using Morpheus is opt-in. The plugin does not replace your agent's own model.

## Get a key

You need one API key. Pick where it comes from:

- **api.mor.org:** sign in at [app.mor.org](https://app.mor.org) and create an API key. The plugin then uses `https://api.mor.org/api/v1`.
- **Your own Uplink:** if you run a [Morpheus Uplink](https://github.com/MorpheusAIs/Morpheus-Uplink), use a key from the Uplink web interface. The Uplink documentation ([API keys](https://github.com/MorpheusAIs/Morpheus-Uplink/blob/main/docs/03-gui.md#api-keys)) lists three kinds: Master (inference and admin), Prompt (inference only) and ephemeral (named keys for apps and agents). Use a Prompt key or an ephemeral key, not the Master key. The base URL (web address) is your Uplink host followed by `/v1`, for example `https://uplink.example.com/v1`.

Keep the key out of chat, prompts, and files in your repo.

## Install

### From the Cursor Marketplace

The listing is not live yet. Cursor's [plugin documentation](https://cursor.com/docs/plugins#installing-plugins) describes the install steps: open **Customize** in the sidebar, find the plugin, and select **Install**. Then set the values described in [Configuration](#configuration).

`mcp.json` starts the server with `uvx`, pinned to the `v0.2.1` tag of this repository:

```json
"command": "uvx",
"args": ["--from", "git+https://github.com/absgrafx/morpheus-grok-mcp@v0.2.1", "morpheus-mcp"]
```

You need [uv](https://docs.astral.sh/uv/) installed for `uvx`. See [Supply chain](#supply-chain) for what the pin covers.

### From a clone (local testing)

```bash
git clone https://github.com/absgrafx/morpheus-grok-mcp.git
cd morpheus-grok-mcp
uv sync --extra dev
uv run python scripts/validate_plugin.py
uv run pytest -q
uv run python scripts/smoke_mcp.py
```

The last command starts the MCP server from your clone and prints its tools:

```text
tools: morpheus_chat, morpheus_embed, morpheus_list_models
```

To load the plugin in Cursor from your machine, copy it into the local plugins folder:

```bash
mkdir -p ~/.cursor/plugins/local/morpheus-inference
cp -r .cursor-plugin assets mcp.json skills README.md LICENSE ~/.cursor/plugins/local/morpheus-inference/
```

Copy the files rather than linking them: Cursor's [local testing notes](https://cursor.com/docs/plugins#test-plugins-locally) say a symlink in this folder loads only if its target is inside the folder. Then restart Cursor (or run **Developer: Reload Window**) and check **Customize** for the MCP server and skills.

## Configuration

Three settings, plus an optional model list. Set them in the Cursor dashboard under **Plugins**, at install time or later with **Configure**. The plugin declares only the names; it never stores the values.

| Setting | Variable | Required | Value |
|---------|----------|----------|-------|
| API key | `MORPHEUS_API_KEY` | yes | Your key from app.mor.org or your Uplink |
| Mode | `MORPHEUS_MODE` | yes, default `api.mor.org` | `api.mor.org` or `uplink` |
| Base URL | `MORPHEUS_BASE_URL` | Uplink mode only | For example `https://uplink.example.com/v1` |
| Model hierarchy | `MORPHEUS_MODELS` | no | Chat models to try, comma-separated, most preferred first |

In `api.mor.org` mode the base URL is always `https://api.mor.org/api/v1`, and `MORPHEUS_BASE_URL` is ignored.

In `uplink` mode:

- The base URL must start with `https://`. Plain `http://` is accepted only for `localhost`, `127.0.0.1` and `::1`.
- A user name or password in the URL (`https://user:pass@host`) is rejected. Put the key in `MORPHEUS_API_KEY` instead.
- The plugin makes the URL end in `/v1`: it removes a pasted `/chat/completions`, `/embeddings` or `/models`, collapses `/v1/v1`, and adds `/v1` if it is missing. It logs a warning for each change. It never adds `/api`.

Model ids must match the endpoint's catalog exactly. Call `morpheus_list_models` to see them.

Per-agent keys and the old policy flags from 0.1.0 were removed. See [docs/DESIGN.md](docs/DESIGN.md#removed-in-020) for how to get the same results.

## Model hierarchy and fallback

For `morpheus_chat`, the plugin tries models in this order: the `model` argument (if the agent passed one), then each id in `MORPHEUS_MODELS`. `MORPHEUS_MODELS` applies to chat only, because embedding models are different: for `morpheus_embed`, the plugin tries the `model` argument, then each id in the optional `fallback_models` argument.

If the agent passes no `model` and `MORPHEUS_MODELS` is empty, nothing is sent to Morpheus. The tool returns `host_fallback` at once, with an alert saying no model was set.

- Each model is called once. There are no silent retries.
- Each call waits up to 60 seconds for a reply. The agent can set `timeout_seconds` on a call; values below 1 are raised to 1 and values above 300 are lowered to 300.
- An HTTP (web request) error, a timeout, a network error, or an empty response moves on to the next model, and each failure is reported.
- HTTP 401 or 403 means the key was rejected. Every model uses the same key, so the plugin stops there.
- When no Morpheus model is left, the tool returns `"status": "host_fallback"` with `"use_host_model": true` and this instruction to the agent: "Morpheus could not complete this request. Use your own model to handle it now. First show the user the text in user_alert, then continue with your own model."
- `morpheus_list_models` makes a single call. If it fails, it also returns `host_fallback`, with an alert, and tells the agent that Morpheus is not reachable right now.

Example: with `MORPHEUS_MODELS` set to `model-a,model-b`, suppose `model-a` returns HTTP 502. The plugin records an alert for `model-a`, calls `model-b`, and returns the answer from `model-b` together with that alert. If `model-b` also fails, a second alert is added and the tool returns `host_fallback`, so your agent's own model takes over.

## Testing

1. Get a key. Mint your own at [app.mor.org](https://app.mor.org), which includes $1 of free inference, or use an Uplink Prompt key (not the Master key).
2. Set `MORPHEUS_MODELS`. Without it, a chat call that names no model goes straight to `host_fallback`. `morpheus_embed` does not read `MORPHEUS_MODELS`, so it always needs an explicit `model` argument.
3. Use these test models:
   - Chat: `deepseek-v4-flash`, a warm hosted model. It is a reasoning model, so a reply can take up to about 60 seconds.
   - Embeddings: `BGE-EN-ICL` works through an Uplink. Hosted api.mor.org embedding models may be cold, so an embedding call there can fail until one is warm.

Use warm models for testing. Cheaper hosted models (for example `Aion 3.5 Mini`) may return HTTP 503 `model_unavailable` when they are not warm. Try another warm model or use an Uplink.

With `MORPHEUS_MODELS=deepseek-v4-flash`, try these prompts:

| Prompt | Expected result |
|--------|-----------------|
| "List the Morpheus models" | `morpheus_list_models` returns `"status": "ok"` and the model list. |
| "Use morpheus_chat: reply with the word pong" | `"status": "ok"`, `model_used` and `requested_model` are `deepseek-v4-flash`, and the content is `pong`. |
| "Embed 'hello world' with morpheus_embed using BGE-EN-ICL" | `"status": "ok"` and a vector with 4096 dimensions. Through an Uplink, `model_used` is `text-embedding-bge-en-icl`. |

Fallback checks:

- Through an Uplink, `MORPHEUS_MODELS=BGE-EN-ICL,deepseek-v4-flash`: chat returns an alert for `BGE-EN-ICL` (an embedding model can't be used for chat), then `pong` from `deepseek-v4-flash`. On api.mor.org the endpoint may instead choose a different model, which shows as an informational `model_substituted` note.
- `MORPHEUS_MODELS=BGE-EN-ICL,Aion 3.5 Mini`: chat returns an alert for `BGE-EN-ICL`. If `Aion 3.5 Mini` is not warm, a second alert follows, then `"status": "host_fallback"`, and your agent's own model answers. If it is warm, it answers with `"status": "ok"`.

## Alerts

Every failure produces an alert. Each alert has:

| Field | Meaning |
|-------|---------|
| `model` | The model that failed |
| `endpoint` | The full URL that was called |
| `http_status` | The HTTP status code, or `null` if there was no HTTP response |
| `error` | A short description: a parsed error message (the status code is in `http_status`), or for example `timed out after 60s` |
| `time` | Local time with UTC offset |
| `action` | What was done instead |

If the endpoint returns an HTTP error, the alert shows the status code and a short parsed error message (the error type up to 60 characters and the message up to 200 characters). The raw response body is never shown. If the body is not JSON or has no message, the alert says so instead. The configured key is always masked, and the request text is never included: a message that quotes the request is replaced by "(upstream message withheld: it quoted the request)".

The alert reaches you and the agent in three ways:

1. In the tool result: `alerts` (structured) and `user_alert` (one line per failure), with `agent_instructions` telling the agent to show `user_alert` to you.
2. As an MCP log message (warning level) to Cursor.
3. On the server's standard error output, at the moment the failure happens.

Example `user_alert`:

```text
Morpheus alert at 2026-10-14T16:43:57-04:00: model no-such-model-xyz on https://uplink.example.com/v1/chat/completions failed (HTTP 404; invalid_request_error: model "no-such-model-xyz" not found in catalog). Action: Tried the next Morpheus model, deepseek-v4-flash.
```

### Model substitution (informational)

An endpoint can choose a different model than the one requested. For example, api.mor.org corrects close names and serves names it doesn't know with its default model. This is expected behaviour, not a failure, so the plugin reports it as information. Every successful chat or embedding result has two fields:

- `model_used`: the model named in the response's `model` field. If the response has no `model` field, this is the requested model.
- `requested_model`: the model the plugin asked for.

The plugin treats two names as the same model if they differ only in letter case or in spaces, `-` or `_`; if the response adds a provider prefix (`org/name`) to a name asked for without one, or both use the same provider; or if the pair is in the plugin's alias list (an Uplink serves `BGE-EN-ICL` as `text-embedding-bge-en-icl`). Otherwise the result keeps `"status": "ok"` and adds an informational entry to `alerts` with `type` `model_substituted`, `severity` `info`, and the fields `requested`, `served`, `endpoint` and `time`. Its text is added to `user_alert`, and `agent_instructions` tells the agent to mention it to you, not to treat it as a failure. It goes to Cursor as an info-level MCP log message, and to standard error only with `--verbose`.

A model name from the endpoint is shown only if it uses letters, digits, single spaces and `. _ : / @ + -`, is at most 100 characters, and does not contain the key or repeat the request text. Otherwise every output (`model_used`, alerts, `user_alert`, MCP log messages and standard error) shows `(invalid model name)` instead. Requested names are checked the same way when they are shown. Example:

```text
Morpheus note at 2026-10-15T10:25:16-04:00: served by google-gemma-4-31b-it instead of nonexistent-model-xyz on https://api.mor.org/api/v1/chat/completions (the endpoint picked the model).
```

## Privacy

- Your messages and embedding inputs go to the endpoint you choose: api.mor.org, or your own Uplink. That endpoint passes them to a Morpheus compute provider to run the model. Check the terms of the endpoint you use for how it handles data.
- When the plugin hands back to your agent's own model, the request is handled by that model in the usual way. The plugin does not send it anywhere else.
- The plugin has no telemetry and stores nothing on disk.
- Logs go to standard error only. By default only warnings (alerts and URL fixes) are logged. Starting the server with `morpheus-mcp --verbose` adds one line per request: method, URL, model id and the last four characters of the key. Message text is never logged.
- Every log line, alert and error passes through redaction: the configured key is masked whatever its format, as are `sk-` keys, Bearer tokens and credentials in URLs.
- Masking matches the key's exact text. A key that is split, base64-encoded, or URL-encoded with reserved characters is not masked. A key shorter than 4 characters is not masked.
- The key is passed to the server as an environment variable by Cursor. It is not written to this repository, and CI uses no keys.

## Supply chain

- The install is pinned to the `v0.2.1` tag. A Git tag can be moved, so a commit-hash pin would be stronger. It can't be used here because the release commit only exists after the merge, so the tag is the pin for 0.2.1.
- `uvx --from git+...` does not read `uv.lock`, so `pyproject.toml` pins the two direct dependencies exactly (`mcp==1.30.0`, `httpx==0.28.1`). Their own dependencies are resolved at install time.
- The CI workflow pins its GitHub Actions to commit hashes and has read-only repository access.

## Support

Email devs@absgrafx.com or open an issue on this repository.

## Development

Continuous integration (CI) on GitHub Actions (Linux) runs `uv sync --extra dev --frozen`, `uv run python scripts/validate_plugin.py` and `uv run pytest -q` on every pull request and on pushes to `main`. The validator checks the manifest and `mcp.json` with `jsonschema`, checks that every `${VAR}` in `mcp.json` is declared, checks that the install is pinned to `v<version>`, and checks that the contact email matches the manifest everywhere. Tests use mocked HTTP and need no key.

To change the contact email, edit `author.email` in `.cursor-plugin/plugin.json` and replace the old address in `pyproject.toml`, this README and `docs/listing/cursor-directory.md`. The validator fails until they match.

## License

MIT. Copyright (c) 2026 ABSGrafx LLC. See [LICENSE](LICENSE).
