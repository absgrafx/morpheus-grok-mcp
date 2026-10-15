---
name: morpheus-setup
description: >-
  Help the user configure the Morpheus Inference plugin: API key, mode
  (api.mor.org or Uplink), base URL and model hierarchy, then check it works.
  Use when the user asks to set up or troubleshoot Morpheus.
---

# Morpheus setup

The plugin has three settings and one optional list. The user sets them in Cursor under **Plugins > Morpheus Inference > Configure**. Never ask the user to paste a key into chat.

| Setting | Variable | Notes |
|---------|----------|-------|
| API key | `MORPHEUS_API_KEY` | A key from app.mor.org, or a Prompt or ephemeral key from the user's own Uplink (not the Master key). |
| Mode | `MORPHEUS_MODE` | `api.mor.org` (default) or `uplink`. |
| Base URL | `MORPHEUS_BASE_URL` | Uplink mode only, for example `https://uplink.example.com/v1`. Must be `https://` (`http://` only for localhost, 127.0.0.1 or ::1) with no user name or password in it. Ignored in api.mor.org mode, which always uses `https://api.mor.org/api/v1`. |
| Model hierarchy (optional) | `MORPHEUS_MODELS` | Chat models to try, comma-separated, most preferred first. |

## Check it works

1. Call `morpheus_list_models`. Expect `status: "ok"` and a list of model ids. If you get an alert, show it to the user: an HTTP 401 or 403 means the key was rejected; a 404 usually means the base URL is wrong.
2. If the hierarchy is empty, suggest the user pick ids from that list and set **Model hierarchy**.
3. Call `morpheus_chat` with a short message, for example `[{"role": "user", "content": "Reply with one word: pong"}]`, and show the user the result.

## Uplink base URL

Use the base that ends in `/v1`. The plugin removes a pasted `/chat/completions` and adds a missing `/v1`, and says so in its log. It never adds `/api` for an Uplink.
