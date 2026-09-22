# morpheus-mcp

Grok / Cursor **Marketplace MCP** that routes OpenAI-compatible inference to Morpheus:

- **Public:** `https://api.mor.org/api/v1`
- **Custom:** your Uplink base `https://<host>/v1`

Maintainer (public): **NomadicRogue**. Design roles on the project: CoS / CTO / CISO / Builder (and peer lanes as needed).

Design source of truth (accepted, private eng): [`absgrafx/absgrafx-eng` → `morpheus-grok-marketplace-mcp-v0/`](https://github.com/absgrafx/absgrafx-eng/tree/main/morpheus-grok-marketplace-mcp-v0) (tip `d3ff734`).

Implementation status: **scaffold** — Builder work starts after operator authorize. Staff bridge remains internal until dogfood migration.

## Non-goals (v0)

- Not shipping the staff CLI
- Not embedding Uplink/Lumerin
- No secrets in this repo (plugin variables / secure install UI only)

## License

MIT — see `LICENSE`.
