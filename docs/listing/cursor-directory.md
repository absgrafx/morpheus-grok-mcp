# cursor.directory listing (draft, not submitted)

Submit page: https://cursor.directory/plugins/new ("Auto-detect from a GitHub repo or create one manually").
The form's field list is not visible without signing in, so the fields below cover the usual set.
Submit only after the v0.2.2 pull request is merged and the `v0.2.2` tag exists.

## Fields

| Field | Value |
|-------|-------|
| Name | Morpheus Inference |
| Slug / plugin id | `morpheus-inference` |
| GitHub repository | https://github.com/absgrafx/morpheus-grok-mcp |
| Homepage | https://github.com/absgrafx/morpheus-grok-mcp#readme |
| Version | 0.2.2 |
| Author | ABSGrafx |
| Contact | devs@absgrafx.com |
| License | MIT |
| Logo | `assets/logo.png` (256 x 256 PNG, transparent rounded corners) |
| Category | MCP server / AI models (confirm on the form) |
| Tags | morpheus, mcp, inference, openai-compatible, decentralized, uplink |

## Short description

Chat and tool calling on Morpheus decentralized inference, via api.mor.org or your own Uplink. Embeddings optional. https://github.com/absgrafx/morpheus-grok-mcp#readme

## Long description

Morpheus Inference adds an MCP (Model Context Protocol) server to Cursor. `morpheus_chat` runs chat
with tool calling (OpenAI-format `tools` and `tool_calls`) on api.mor.org or your own Uplink;
embeddings are optional. Opt-in: your agent's own model stays as it is. Set a key, a mode and a
model list. On a failure the next model is tried, then your agent's model, with an alert each time.
The key is always masked, and there is no telemetry. Docs: https://github.com/absgrafx/morpheus-grok-mcp#readme

## Setup

1. Get a key: create one at https://app.mor.org, or use a Prompt or ephemeral key from your own
   Uplink's web interface (not the Master key).
2. Install the plugin and set `MORPHEUS_API_KEY`, `MORPHEUS_MODE` and, for Uplink,
   `MORPHEUS_BASE_URL`. Optionally set `MORPHEUS_MODELS` (chat models, most preferred first), for example `model-a,model-b`.
3. Ask the agent to run `morpheus_list_models` to check the connection.
4. Full setup, testing and troubleshooting: https://github.com/absgrafx/morpheus-grok-mcp#readme

Requires [uv](https://docs.astral.sh/uv/) (the server runs with `uvx`, pinned to tag `v0.2.2`).

## MCP config (as shipped in mcp.json)

```json
{
  "mcpServers": {
    "morpheus-inference": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/absgrafx/morpheus-grok-mcp@v0.2.2", "morpheus-mcp"],
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
