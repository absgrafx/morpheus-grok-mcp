---
name: morpheus-setup
description: >-
  Install and configure the Morpheus Inference Marketplace MCP — endpoint
  public vs custom Uplink, key shared vs per_bot, smoke list_models then chat.
  Secrets only via Plugins → Configure / vault inject; never chat.
---

# Morpheus setup

Configure the **morpheus-inference** Marketplace MCP so Grok Bot can call Morpheus MoE.

Operator / maintainer handle in public docs: **NomadicRogue**. Crew roles that may assist installs: CoS (vault inject), Builder, Verification.

## 1. Endpoint mode

| Mode | Env | Base |
|------|-----|------|
| **public** (default) | `MORPHEUS_ENDPOINT_MODE=public` | Forced to `https://api.mor.org/api/v1` |
| **custom** | `MORPHEUS_ENDPOINT_MODE=custom` + `MORPHEUS_BASE_URL` | Your Uplink `https://<host>/v1` |

Custom bases are **auto-normalized** to end in `/v1` (warn on stderr, not hard-fail). Do **not** paste `/chat/completions` into the base. Private Uplink uses **`/v1`** (no `/api`). Public APIGW uses **`/api/v1`**.

## 2. Key mode

| Mode | Env | Behavior |
|------|-----|----------|
| **shared** (default) | `MORPHEUS_KEY_MODE=shared` + `MORPHEUS_API_KEY` | One Bearer key for all calls |
| **per_bot** | `MORPHEUS_KEY_MODE=per_bot` | Resolve key for `MORPHEUS_AGENT_SLOT` / `MORPHEUS_AGENT` |

Per-bot resolution order:

1. Discrete slot secret `MORPHEUS_API_KEY_<SLOT>` (SLOT upper role keys: `COS`, `CTO`, `CISO`, `BUILDER`, `VERIFICATION`, `COMMS`, `CFO`)
2. JSON map escape `MORPHEUS_API_KEYS_JSON` (`{"cos":"sk-…", …}` — arbitrary slot keys allowed)

**Hard-fail** if per_bot and the slot key is missing — no silent fallback to shared.

**Never** use a master / usage-only key for chat, embeddings, or list_models. If slot is `master` or `MORPHEUS_UPLINK_KEY_ROLE=master_usage_only`, the connector refuses.

## 3. Secrets UX

- Set secrets only via **Plugins → Configure**, InstallPlugin secure fields, or vault inject (CoS lane).
- **Never** paste `sk-…` into chat, README, memories, or commit them.
- `mcp.json` uses `${MORPHEUS_*}` placeholders only.

## 4. Default model + policy toggles

- `MORPHEUS_MODEL_DEFAULT` — exact id from `GET /models` (not a display name).
- `MORPHEUS_POLICY_MOE_DEFAULT` — prefer `morpheus_chat` for analysis (`true` default).
- `MORPHEUS_POLICY_CURSOR_EXCEPTION` — native/Cursor only when operator names an exception.
- `MORPHEUS_POLICY_FALLBACK_ON_DOWN` — if Morpheus is down, native fallback allowed **and** must surface `Morpheus didn’t work: <reason>`.

## 5. Smoke test

1. Call **`morpheus_list_models`** — expect a catalog (or a clear auth error).
2. Call **`morpheus_chat`** with a one-word ping and an exact model id.
3. On failure, do not invent bases; re-check public vs `/api/v1` vs custom `/v1`.

## 6. Local run (dev)

```bash
uv sync
uv run morpheus-mcp
# or: python -m morpheus_mcp
```

Marketplace install prefers `uvx --from git+https://github.com/absgrafx/morpheus-grok-mcp.git morpheus-mcp` per `mcp.json`.

