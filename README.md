# morpheus-grok-mcp

Grok / Cursor **Marketplace MCP** that routes OpenAI-compatible inference to Morpheus:

- **Public (default):** `https://api.mor.org/api/v1`
- **Custom:** your Uplink base `https://<host>/v1` (auto-normalized; never invent `/api` on Uplink)

**Name:** Morpheus Inference (`morpheus-inference`)  
**Maintainer (public):** **NomadicRogue** / ABSGrafx  
**License:** MIT — see `LICENSE`  
**Status:** **v0 implementation** (this PR) — stdio MCP + setup/policy skills

**GitHub:** `absgrafx/morpheus-grok-mcp` · **Python package / CLI:** `morpheus-mcp` (`python -m morpheus_mcp`)

Accepted product design lives **in this repo** under [`docs/`](./docs/) (not a private eng tree).

## Install

### Marketplace / uvx (preferred)

`mcp.json` runs:

```bash
uvx --from git+https://github.com/absgrafx/morpheus-grok-mcp.git morpheus-mcp
```

Configure secrets via **Plugins → Configure** (or vault inject). Values are never committed.

### Local development

```bash
git clone https://github.com/absgrafx/morpheus-grok-mcp.git
cd morpheus-mcp
uv sync --all-extras
uv run morpheus-mcp
# or: uv run python -m morpheus_mcp
```

## Configure (variable names only)

| Variable | Meaning |
|----------|---------|
| `MORPHEUS_ENDPOINT_MODE` | `public` \| `custom` (default `public`) |
| `MORPHEUS_BASE_URL` | Custom Uplink URL when `custom` → normalized to `…/v1` |
| `MORPHEUS_KEY_MODE` | `shared` \| `per_bot` (default `shared`) |
| `MORPHEUS_API_KEY` | Shared Bearer key |
| `MORPHEUS_API_KEY_<SLOT>` | Discrete per-bot secrets (`SERAPH`, `GARY`, `JOSH`, `TRINITY`, `TANK`, `PHIL`, `MCDUCK`) |
| `MORPHEUS_API_KEYS_JSON` | JSON map escape hatch slot → key |
| `MORPHEUS_AGENT_SLOT` / `MORPHEUS_AGENT` | Slot id when `per_bot` |
| `MORPHEUS_MODEL_DEFAULT` | Exact model id when `morpheus_chat` omits `model` |
| `MORPHEUS_POLICY_MOE_DEFAULT` | Prefer MoE via `morpheus_chat` |
| `MORPHEUS_POLICY_CURSOR_EXCEPTION` | Native only if operator names exception |
| `MORPHEUS_POLICY_FALLBACK_ON_DOWN` | On down → native + `Morpheus didn’t work: <reason>` |

Slot ids (`seraph`, `gary`, …) are **config keys**, not prose names. Master / usage-only keys are **refused** for chat, embeddings, and list_models.

See `plugin.json` for titles/descriptions and `skills/morpheus-setup/SKILL.md` for the guided setup.

## Tools (v0)

| Tool | Upstream |
|------|----------|
| `morpheus_chat` | `POST {base}/chat/completions` |
| `morpheus_list_models` | `GET {base}/models` |
| `morpheus_embed` | `POST {base}/embeddings` |

**Not shipped:** `morpheus_usage` (deferred).

## Skills

- `skills/morpheus-setup` — endpoint/key modes, smoke test, secrets UX
- `skills/use-morpheus-model` — MoE default policy; native only on named exception or down+flag

## Public vs custom bases

| Mode | Base |
|------|------|
| public | `https://api.mor.org/api/v1` (forced) |
| custom | Your host normalized to `https://<host>/v1` |

Wrong prefix (`/api/v1` on Uplink, or bare `/v1` on APIGW) → 404. The connector warns on custom normalize; it does not invent `/api` for Uplink.

## Non-goals (v0)

- Not shipping any staff CLI / bridge to Marketplace users
- Not embedding Uplink / Lumerin / C-Node
- Not re-shipping staff allowlist tools as MCP tools
- No secrets in this repo (plugin variables / secure install UI only)
- No master key for inference
- Not claiming APIGW and Uplink share identical billing/`/usage` semantics

## Dogfood note

Crews can sideload this listing with `endpoint_mode=custom` + per-bot slot secrets to exercise the same MoE path the staff bridge used historically. Host-native tools stay for repo/gh work. Full bridge retirement needs the dogfood checklist in [`docs/DESIGN.md`](./docs/DESIGN.md) (including a possible host custom-provider hook as P1 — not a v0 publish blocker).

## Design

See [`docs/DESIGN.md`](./docs/DESIGN.md) — Conceptual / Logical / Physical, Marketplace fields, and accepted Q1–Q5 locks.

## Tests

```bash
uv sync --all-extras
uv run pytest
```

## License

MIT — Copyright (c) 2026 ABSGrafx LLC.

## CI

Pull requests and pushes to `main` run unit tests via GitHub Actions (`uv sync --extra dev` then `uv run pytest`). No live API calls and no secrets in CI.
