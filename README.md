# Morpheus Inference for Cursor

<p align="center">
  <img src="assets/logo.png" alt="Morpheus Inference logo" width="128" height="128" />
</p>

Run chat and embeddings on Morpheus decentralized inference (api.mor.org or your own Uplink).

- Plugin name: `morpheus-inference` (Cursor Plugin, manifest in `.cursor-plugin/plugin.json`)
- Repository: `absgrafx/morpheus-grok-mcp`
- Version: 0.2.0
- Author: ABSGrafx, devs@absgrafx.com
- License: MIT

## What it does

The plugin adds an MCP server with three tools and two skills.

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
- **Your own Uplink:** if you run a [Morpheus Uplink](https://github.com/MorpheusAIs/Morpheus-Uplink), use its Prompt key or create an ephemeral key in the Uplink GUI. Do not use the Uplink Master key here; it also has admin rights. The base URL is your Uplink host followed by `/v1`, for example `https://uplink.example.com/v1`.

Keep the key out of chat, prompts, and files in your repo.

## Install

### From the Cursor Marketplace

When the listing is live: open **Customize** in Cursor, search for "Morpheus Inference", select **Install**, then set the values described in [Configuration](#configuration).

`mcp.json` starts the server with `uvx`, pinned to the `v0.2.0` tag of this repository:

```json
"command": "uvx",
"args": ["--from", "git+https://github.com/absgrafx/morpheus-grok-mcp@v0.2.0", "morpheus-mcp"]
```

You need [uv](https://docs.astral.sh/uv/) installed for `uvx`.

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

To load the plugin in Cursor from your machine, copy it into the local plugins folder (Cursor skips symlinks that point outside this folder):

```bash
mkdir -p ~/.cursor/plugins/local/morpheus-inference
cp -r .cursor-plugin assets mcp.json skills README.md LICENSE ~/.cursor/plugins/local/morpheus-inference/
```

Then restart Cursor (or run **Developer: Reload Window**) and check **Customize** for the MCP server and skills.

## Configuration

Three settings, plus an optional model list. Set them in Cursor under **Plugins > Configure**. The plugin declares only the names; it never stores the values.

| Setting | Variable | Required | Value |
|---------|----------|----------|-------|
| API key | `MORPHEUS_API_KEY` | yes | Your key from app.mor.org or your Uplink |
| Mode | `MORPHEUS_MODE` | yes, default `api.mor.org` | `api.mor.org` or `uplink` |
| Base URL | `MORPHEUS_BASE_URL` | Uplink mode only | For example `https://uplink.example.com/v1` |
| Model hierarchy | `MORPHEUS_MODELS` | no | Comma-separated model ids, most preferred first |

In `api.mor.org` mode the base URL is always `https://api.mor.org/api/v1`, and `MORPHEUS_BASE_URL` is ignored.

In `uplink` mode the plugin makes the base URL end in `/v1`: it removes a pasted `/chat/completions`, `/embeddings` or `/models`, collapses `/v1/v1`, and adds `/v1` if it is missing. It logs a warning for each change. It never adds `/api`.

Model ids must match the endpoint's catalog exactly. Call `morpheus_list_models` to see them.

Per-agent keys and the old policy flags from 0.1.0 were removed. See [docs/DESIGN.md](docs/DESIGN.md#removed-in-020) for how to get the same results.

## Model hierarchy and fallback

For `morpheus_chat`, the plugin tries models in this order: the `model` the agent passed (if any), then each id in `MORPHEUS_MODELS`. For `morpheus_embed`, it tries `model`, then each of `fallback_models`.

- Each model is called once. There are no silent retries.
- An HTTP error, a timeout (60 seconds by default, or `timeout_seconds`), a network error, or an empty response moves on to the next model, and each failure is reported.
- HTTP 401 or 403 means the key was rejected. Every model uses the same key, so the plugin stops there.
- When no Morpheus model is left, the tool returns `"status": "host_fallback"` with `"use_host_model": true` and this instruction to the agent: "Morpheus could not complete this request. Use your own model to handle it now. First show the user the text in user_alert, then continue with your own model."

Example: with `MORPHEUS_MODELS` set to `model-a,model-b`, if `model-a` returns HTTP 502 the plugin calls `model-b` and returns its answer with an alert. If `model-b` also fails, control goes back to your agent's own model.

## Alerts

Every failure produces an alert. Each alert has:

| Field | Meaning |
|-------|---------|
| `model` | The model that failed |
| `endpoint` | The full URL that was called |
| `http_status` | The HTTP code, or `null` if there was no HTTP response |
| `error` | The error message (for example `HTTP 502: ...` or `timed out after 60s`) |
| `time` | Local time with UTC offset |
| `action` | What was done instead |

The alert reaches you and the agent in three ways:

1. In the tool result: `alerts` (structured) and `user_alert` (one line per failure), with `agent_instructions` telling the agent to show `user_alert` to you.
2. As an MCP log message (warning level) to Cursor.
3. On the server's stderr, at the moment the failure happens.

Example `user_alert`:

```text
Morpheus alert at 2026-10-14T16:43:57-04:00: model no-such-model-xyz on https://uplink.example.com/v1/chat/completions failed (HTTP 404; HTTP 404: {"error":{"message":"model \"no-such-model-xyz\" not found in catalog","type":"invalid_request_error"}}). Action: Tried the next Morpheus model, deepseek-v4-flash.
```

## Privacy

- Your messages and embedding inputs go to the endpoint you choose: api.mor.org, or your own Uplink. That endpoint passes them to a Morpheus compute provider to run the model. Check the terms of the endpoint you use for how it handles data.
- When the plugin hands back to your agent's own model, the request is handled by that model in the usual way. The plugin does not send it anywhere else.
- The plugin has no telemetry and stores nothing on disk.
- Logs (stderr only) contain the HTTP method, URL, model id, and the last four characters of the key. They never contain message text. Error text in alerts is cut to 300 characters, and anything that looks like an `sk-` key is masked.
- The key is passed to the server as an environment variable by Cursor. It is not written to this repository, and CI uses no keys.

## Support

Email devs@absgrafx.com or open an issue on this repository.

## Development

CI (GitHub Actions, Linux) runs `uv sync --extra dev --frozen`, `uv run python scripts/validate_plugin.py` and `uv run pytest -q` on every pull request and on pushes to `main`. The validator checks the manifest and `mcp.json` with `jsonschema`, checks that every `${VAR}` in `mcp.json` is declared, and checks that the install is pinned to `v<version>`. Tests use mocked HTTP and need no key.

## License

MIT. Copyright (c) 2026 ABSGrafx LLC. See [LICENSE](LICENSE).
