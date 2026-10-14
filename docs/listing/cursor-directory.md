# cursor.directory listing (draft, not submitted)

Submit page: https://cursor.directory/plugins/new ("Auto-detect from a GitHub repo or create one manually").
The form's field list is not visible without signing in, so the fields below cover the usual set.
Submit only after the v0.2.0 pull request is merged and the `v0.2.0` tag exists.

## Fields

| Field | Value |
|-------|-------|
| Name | Morpheus Inference |
| Slug / plugin id | `morpheus-inference` |
| GitHub repository | https://github.com/absgrafx/morpheus-grok-mcp |
| Homepage | https://github.com/absgrafx/morpheus-grok-mcp#readme |
| Version | 0.2.0 |
| Author | ABSGrafx |
| Contact | devs@absgrafx.com |
| License | MIT |
| Logo | `assets/logo.png` (256 x 256 PNG, transparent rounded corners) |
| Category | MCP server / AI models |
| Tags | morpheus, mcp, inference, openai-compatible, decentralized, uplink |

## Short description

Run chat and embeddings on Morpheus decentralized inference (api.mor.org or your own Uplink).

## Long description

Morpheus Inference adds three MCP tools to Cursor: `morpheus_chat`, `morpheus_embed` and
`morpheus_list_models`. They call the OpenAI-compatible API of Morpheus, either the public
endpoint at api.mor.org or an Uplink you run yourself.

- Opt-in: the agent uses Morpheus when you ask for it or have said you want it. Your agent's own
  model stays as it is.
- Three settings: an API key, a mode (`api.mor.org` or `uplink`) and, for Uplink, a base URL.
- Model hierarchy: list the models you prefer, in order. On an error or timeout the next model is
  tried. If none works, the tool tells your agent to use its own model.
- Alerts: every failure is reported to you and the agent with the model, endpoint, HTTP code or
  message, time, and what was done instead. Nothing is retried silently.
- No telemetry. The key is set in Cursor's plugin configuration and never stored in the repo.

## Setup

1. Get a key: create one at https://app.mor.org, or use a Prompt or ephemeral key from your own
   Uplink.
2. Install the plugin and set `MORPHEUS_API_KEY`, `MORPHEUS_MODE` and, for Uplink,
   `MORPHEUS_BASE_URL`. Optionally set `MORPHEUS_MODELS`, for example `model-a,model-b`.
3. Ask the agent to run `morpheus_list_models` to check the connection.

Requires [uv](https://docs.astral.sh/uv/) (the server runs with `uvx`, pinned to tag `v0.2.0`).

## MCP config (as shipped in mcp.json)

```json
{
  "mcpServers": {
    "morpheus-inference": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/absgrafx/morpheus-grok-mcp@v0.2.0", "morpheus-mcp"],
      "env": {
        "MORPHEUS_API_KEY": "${MORPHEUS_API_KEY}",
        "MORPHEUS_MODE": "${MORPHEUS_MODE}",
        "MORPHEUS_BASE_URL": "${MORPHEUS_BASE_URL}",
        "MORPHEUS_MODELS": "${MORPHEUS_MODELS}"
      }
    }
  }
}
```

## Links

- Repository: https://github.com/absgrafx/morpheus-grok-mcp
- README: https://github.com/absgrafx/morpheus-grok-mcp#readme
- Issues: https://github.com/absgrafx/morpheus-grok-mcp/issues
- Morpheus API keys: https://app.mor.org
- Morpheus Uplink: https://github.com/MorpheusAIs/Morpheus-Uplink
