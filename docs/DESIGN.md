# DESIGN — Morpheus Marketplace MCP (+ setup skill)

| Field | Value |
|-------|--------|
| **Status** | **ACCEPTED** (v0 locks Q1–Q5) |
| **Layer** | Conceptual → Logical → Physical |
| **Shape lock** | Marketplace MCP + thin setup/skill — **not** staff CLI to end users |
| **Secrets** | None in this pack / repo |

**North star:** Multi-agent crews can retire a box-local staff bridge and run the same Morpheus MoE path through a public Marketplace connector + installable policy skill.

---

## Recommendation (one paragraph)

Ship an **OSS Agent Plugin**: thin MCP that routes OpenAI-compatible `chat/completions` (plus `models`, optional `embeddings`) to either preset **`https://api.mor.org/api/v1`** or BYO **`https://<host>/v1`**, with setup fields for endpoint mode, key mode (`shared` \| `per_bot` with named slot ids / JSON map), model default, and policy toggles; plus packaged **setup** and **use-morpheus-model** skills. Do **not** re-ship staff allowlist tools — those stay host-native. Do **not** embed Uplink binary. Do **not** ship `morpheus_usage` in v0.

---

## Conceptual

### Product identity

| Is | Is not |
|----|--------|
| Marketplace MCP *transport adapter* to Morpheus inference | Staff CLI shipped to customers |
| Connector + setup skill for policy (“when Morpheus vs native”) | Full agent framework / second CoS |
| Supports public APIGW **or** private Uplink | True-embed of Uplink/C-Node |
| Default one shared key; dogfood-grade per-bot keys | Seven personas required for single-user installs |
| OSS listing, secrets only via plugin variables / secure UI | Keys in `mcp.json` / README / memories |

### Actors

- **End user (single):** install once → public api.mor.org + one key → MoE via skill.
- **Crew dogfood (multi-bot):** same listing; `key_mode=per_bot` with vault-injected slot secrets; `endpoint_mode=custom` pointing at private Uplink `…/v1`.
- **CoS:** vault inject / rotate keys; does not paste keys into chat or listing config.
- **Operator (NomadicRogue):** accept C/L/P + open questions before Builder ships.

### Why MCP

Multi-agent dogfood needs **per-bot key isolation**, an installable **policy skill**, and a **Marketplace discovery** path. A bare OpenAI base URL setting does not give first-class per-bot key map, listing, or retire-the-bridge story.

---

## Logical

### Install UX

1. Marketplace search “Morpheus” → setup fields + which are secret → Install with values.
2. Setup skill walks: endpoint public vs custom; key shared vs per_bot; default model id; policy toggles.
3. Smoke: `morpheus_list_models` then `morpheus_chat` with a one-word ping.
4. Auth: Bearer API key via plugin secret variable — no OAuth card required for v0.

### Config schema (names only — values never in listing files)

| Field | Type | Default | Semantics |
|-------|------|---------|-----------|
| `MORPHEUS_ENDPOINT_MODE` | `public` \| `custom` | `public` | Selects base resolution |
| `MORPHEUS_BASE_URL` | string URL | _(empty)_ | Required if `custom`. Auto-normalize to `…/v1` + **warn** (not hard-fail). Ignored if `public`. |
| `MORPHEUS_KEY_MODE` | `shared` \| `per_bot` | `shared` | Shared = one secret; per_bot = discrete slots or JSON map |
| `MORPHEUS_API_KEY` | secret | — | Shared key |
| `MORPHEUS_API_KEY_<SLOT>` | secret | — | Discrete per-bot secrets (preferred) |
| `MORPHEUS_API_KEYS_JSON` | secret JSON map | — | Escape hatch mapping slot id → key |
| `MORPHEUS_AGENT_SLOT` / `MORPHEUS_AGENT` | string | runtime | Which map/slot key when `per_bot` |
| `MORPHEUS_MODEL_DEFAULT` | string | installer-chosen | Exact catalog id from `/models` |
| `MORPHEUS_POLICY_MOE_DEFAULT` | bool | `true` | Prefer `morpheus_chat` |
| `MORPHEUS_POLICY_CURSOR_EXCEPTION` | bool | `false` | Named exception only |
| `MORPHEUS_POLICY_FALLBACK_ON_DOWN` | bool | `true` | On down → native + flag `Morpheus didn’t work: <reason>` |

Slot ids (technical config keys only, role-aligned): `cos`, `cto`, `ciso`, `builder`, `operations`, `comms`, `cfo`. Discrete env vars use the upper form (`MORPHEUS_API_KEY_COS`, …). JSON-map escape accepts arbitrary keys.

**Base resolution (one function):**

```
if endpoint_mode == public:
  base = "https://api.mor.org/api/v1"
else:
  base = normalize_uplink_base(base_url)  # ensure exactly …/v1, no trailing resource path
# requests: POST {base}/chat/completions — never double /v1 or invent /api on Uplink
```

### MCP tool surface (v0)

| Tool | Maps to | Notes |
|------|---------|-------|
| `morpheus_chat` | `POST {base}/chat/completions` | Primary. Pass-through: `messages`, `model`, `temperature`, `max_tokens`, optional `tools`/`tool_choice`. |
| `morpheus_list_models` | `GET {base}/models` | Install smoke + model picker |
| `morpheus_embed` | `POST {base}/embeddings` | Shipped in v0 |
| ~~`morpheus_usage`~~ | — | **Deferred** in v0 (not shipped) |

**Not in MCP:** staff allowlist / admin / wallet / Probe; master-key usage polling as a product feature.

### Multi-agent → keys

| Mode | Behavior |
|------|----------|
| `shared` | All calls use `MORPHEUS_API_KEY`. Fine for single-user installs. |
| `per_bot` | Discrete `MORPHEUS_API_KEY_<SLOT>` then JSON map. **Hard-fail** if missing — no silent shared fallback. |

Never use master / usage-only key for `morpheus_chat` / embed / list_models.

### Secrets UX

- `plugin.json` `variables`: names + titles/descriptions only; mark API key fields secret.
- `mcp.json`: `${MORPHEUS_*}` placeholders only.
- Installer: secure UI / CoS vault inject — **never chat**.
- Connector logs: endpoint_mode, HTTP status, model id, redacted key id — never raw `sk-`.

### Policy skill

- DEFAULT = Morpheus via `morpheus_chat` with exact model ids.
- Native/Cursor only if (A) named exception, or (B) Morpheus down → flag `Morpheus didn’t work: <reason>`.
- NEVER keys/seeds in prompts.

### Non-goals

1. Shipping staff CLI / bridge to Marketplace users.
2. True-embed Uplink binary or C-Node in the plugin.
3. Requiring seven personas for single-user installs.
4. Re-shipping staff allowlist as MCP tools in v0.
5. Using master key for inference.
6. Claiming APIGW and Uplink share identical billing/`/usage` semantics.

---

## Physical

### Repo layout

```
morpheus-grok-mcp/            # public OSS — https://github.com/absgrafx/morpheus-grok-mcp
  plugin.json
  mcp.json
  skills/
    morpheus-setup/SKILL.md
    use-morpheus-model/SKILL.md
  docs/                       # this design (accepted v0)
  README.md
  LICENSE                     # MIT — ABSGrafx LLC
  src/morpheus_mcp/           # thin Python MCP server (official mcp SDK)
```

Submit: https://cursor.com/marketplace/publish — open source + manual review.

### MCP server shape

- **v0:** local stdio MCP (`uvx` / `python -m morpheus_mcp`) holding secrets in process env from plugin variables.
- Remote HTTPS MCP hosted by Morpheus — defer.

### Exact bases

| Mode | Constant |
|------|----------|
| public | `https://api.mor.org/api/v1` |
| custom | user `MORPHEUS_BASE_URL` normalized to `https://<host>/v1` |

---

## Locks (Q1–Q5) — ACCEPTED

| # | Lock |
|---|------|
| Q1 | Named slot ids + JSON-map escape; prefer one install + map when host allows; else install-per-bot. |
| Q2 | Custom `base_url` → auto-normalize to `…/v1` + warn (**not** hard-fail). |
| Q3 | Defer `morpheus_usage` in v0. |
| Q4 | Marketplace default `endpoint_mode=public`; dogfood uses `custom`. |
| Q5 | v0 = skill + `morpheus_chat` tool; host custom-provider hook is **P1 dogfood gap** before deleting any staff bridge — **not** a v0 publish blocker. |

Bases: public `https://api.mor.org/api/v1` · private Uplink `https://<host>/v1`.

---

## Dogfood gaps (before deleting any staff bridge)

1. Plugin installable with **custom** Uplink base + path normalization proven.
2. Named slot ids (+ JSON-map escape) for crew bots without master key; CoS vault → plugin secrets.
3. Policy skill installed and obeyed.
4. Representative MoE workflows via **skill + `morpheus_chat`** without staff CLI (host tools stay native).
5. Ops floor: request logging sufficient (usage tool deferred); rollback if Morpheus down.
6. **P1 (pre-full-delete):** host-level custom-provider hook if skill+tool proves insufficient — not a v0 Marketplace publish blocker.

---

## Risks

1. **`/api/v1` vs `/v1`** — wrong prefix → 404. Installer must explain.
2. **Master key** — connector must refuse for inference.
3. **Account-wide plugins** — per-bot map/slots required for multi-agent dogfood.
4. **Catalog drift** — exact model ids differ; always `/models`.
