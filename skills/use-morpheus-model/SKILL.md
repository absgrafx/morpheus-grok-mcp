---
name: use-morpheus-model
description: >-
  Default brain = Morpheus MoE via morpheus_chat with exact model ids.
  Native/Cursor only on named exception or Morpheus down + flag.
  Never put keys in prompts.
---

# Use Morpheus model

## DEFAULT

Morpheus MoE is the **default** analysis path. Call Marketplace MCP tool **`morpheus_chat`** with **exact model ids** from `morpheus_list_models` / `MORPHEUS_MODEL_DEFAULT`.

Standing rule: **NEVER** put API keys, seeds, mnemonics, or wallet secrets in any prompt on any model.

Policy env (set at install; skill obeys them):

- `MORPHEUS_POLICY_MOE_DEFAULT=true` → prefer `morpheus_chat`
- `MORPHEUS_POLICY_CURSOR_EXCEPTION=false` unless the operator (**NomadicRogue**) or CoS **explicitly names** a native/Cursor exception for that task
- `MORPHEUS_POLICY_FALLBACK_ON_DOWN=true` → if Morpheus returns 404/502/auth fail/empty content, native fallback is allowed **and** you MUST report: `Morpheus didn’t work: <reason>`

## Native / Cursor — FORBIDDEN unless

**(A)** Operator or CoS **explicitly names** a Cursor/native exception for that task, or  
**(B)** Morpheus is down (404/502/auth/empty) — then fallback is allowed **and** you must flag `Morpheus didn’t work: <reason>`.

NEVER self-serve native because work is “thin/small”. NEVER skip MoE by default.

## Models

Use **exact catalog ids** only (from `GET /models`). Never display-name SKUs. Pass `model=` on `morpheus_chat` or rely on `MORPHEUS_MODEL_DEFAULT`.

## Tools

- `morpheus_chat` — primary MoE path (`messages`, `model`, optional `temperature` / `max_tokens` / `tools` / `tool_choice`)
- `morpheus_list_models` — picker / smoke
- `morpheus_embed` — embeddings when needed

Staff allowlist CLI tools are **not** part of this Marketplace MCP; use the host’s native tools for repo/gh work.

## Keys

Resolved by the connector from plugin variables (`shared` or `per_bot` slot ids). Agents must **not** paste keys into tool arguments or prompts.

