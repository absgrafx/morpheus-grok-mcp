---
name: use-morpheus-model
description: >-
  Run a chat or embedding request on Morpheus decentralized inference with the
  morpheus_chat and morpheus_embed tools. Use only when the user asks for
  Morpheus or has said they want Morpheus used. Handles fallback and alerts.
---

# Use a Morpheus model

## When to use

Use these tools only when one of these is true:

- The user asks to use Morpheus for a request (for example "ask Morpheus", "run this on Morpheus").
- The user has said they want Morpheus used for this kind of work in this project or session.

Otherwise, keep working the way you normally do. This skill does not replace your own model, and nothing here asks you to avoid it.

## How to call

- `morpheus_chat`: pass `messages` in the OpenAI chat format. `model` is optional: if you leave it out, the models the user set in **Model hierarchy** are tried in order. If you pass no `model` and the hierarchy is empty, nothing is sent to Morpheus and the result is `host_fallback` with an alert; tell the user to set **Model hierarchy** or name a model.
- `morpheus_embed`: pass `input` and `model`, plus `fallback_models` if you want other embedding models tried.
- `morpheus_list_models`: shows the model ids on the endpoint and the configured hierarchy. Use exact ids from this list. If it fails, it also returns `host_fallback` with an alert.

Never put API keys, passwords or wallet secrets in messages or tool arguments.

## Reading the result

Every result is JSON with a `status`.

- `"ok"`: use `content` (or `tool_calls`). If the result also has `user_alert`, an earlier model failed and the next one answered. Show the `user_alert` text to the user along with the answer.
- `"host_fallback"`: no Morpheus model could answer. Show the `user_alert` text to the user, then handle the request with your own model.

Each alert gives the model, the endpoint, the HTTP code or error message, the time, and what was done instead. Do not hide or reword alerts, and do not call Morpheus again for the same request unless the user asks.
