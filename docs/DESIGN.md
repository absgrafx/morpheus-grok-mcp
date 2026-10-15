# Design notes (v0.2.1)

## Shape

- A Cursor Plugin (`.cursor-plugin/plugin.json`) with one stdio MCP server (`mcp.json`) and two skills.
- The MCP server is a thin OpenAI-compatible client for Morpheus: `POST /chat/completions`, `POST /embeddings`, `GET /models`.
- Two endpoints: the public Morpheus API at `https://api.mor.org/api/v1`, or the user's own Uplink at `https://<host>/v1`.

## Why the Cursor Plugin format

Cursor loads two manifest formats ([reference](https://cursor.com/docs/reference/plugins)):

- A root `plugin.json` (Agent Plugins standard). Its schema
  (`https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`) has `additionalProperties: false`
  and no `logo` or `variables` field. Those could only go under `extensions`, where the standard
  gives them no meaning, so Cursor would not show a configure form or fill `${VAR}` placeholders.
- `.cursor-plugin/plugin.json` (Cursor Plugin). It supports `logo` and `variables`, and Cursor
  substitutes declared variables into `${VAR}` placeholders in `mcp.json`.

This plugin needs user-set values (key, mode, base URL) passed to the MCP server, so it uses
`.cursor-plugin/plugin.json` only. There is no root `plugin.json`, so there is one manifest.
`mcp.json` still validates against the Agent Plugins 1.0.0 MCP schema.

## Settings

| Variable | Required | Meaning |
|----------|----------|---------|
| `MORPHEUS_API_KEY` | yes | Inference key |
| `MORPHEUS_MODE` | yes (default `api.mor.org`) | `api.mor.org` or `uplink` |
| `MORPHEUS_BASE_URL` | Uplink mode only | Uplink base ending in `/v1`; https only (http for localhost, 127.0.0.1, ::1); no user name or password |
| `MORPHEUS_MODELS` | no | Chat model hierarchy, comma-separated, most preferred first |

A value Cursor leaves as a literal `${VAR}` placeholder is treated as unset.

### Removed in 0.2.0

v0.1.0 had per-agent key slots (`MORPHEUS_KEY_MODE`, `MORPHEUS_API_KEY_<SLOT>`,
`MORPHEUS_API_KEYS_JSON`, `MORPHEUS_AGENT_SLOT`, `MORPHEUS_AGENT`), key-role guards
(`MORPHEUS_UPLINK_KEY_ROLE`, `MORPHEUS_KEY_ROLE`), `MORPHEUS_MODEL_DEFAULT`, and three policy
flags (`MORPHEUS_POLICY_*`). They are gone. The server no longer reads them.

- **Separate keys per agent or per project:** give each install or environment its own
  `MORPHEUS_API_KEY`. If you run your own Uplink, issue one inference key per agent there; Uplink
  tracks usage per key.
- **On an Uplink, use a Prompt key or an ephemeral key, not the Master key.** The Master key also has admin rights.
- **Default model:** put it first in `MORPHEUS_MODELS`.
- **Policy flags:** replaced by the opt-in rule in `skills/use-morpheus-model`: the agent uses
  Morpheus when the user asks for it or has said they want it, and otherwise works as usual.

## Fallback and alerts

See the README sections "Model hierarchy and fallback" and "Alerts". In short: each model is
called once, in order; any error, timeout or empty response moves to the next model and records an
alert; with no model passed and an empty hierarchy nothing is called and the result is host_fallback at once; a 401/403 stops at once, since every model uses the same key; when nothing is left, the
result has `status: "host_fallback"` and tells the agent to use its own model. The handoff text is
fixed by the server and never includes model output. Alerts carry a parsed, length-capped error
message, never the raw response body; the configured key and the request text are always removed.

Since 0.2.1, `model_used` is the model named in the response and `requested_model` is the model asked for. If they differ by more than an alias, the endpoint chose a different model: the result stays `ok` and adds an informational `model_substituted` entry (`severity: info`) to `alerts` and `user_alert`.
