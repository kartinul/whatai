# WhatAI

A WhatsApp AI bot powered by Google Gemini and Baileys (TypeScript). It features rate-limit handling, persistent chat history context, and a secure PC-automation CLI command handler for the owner.

## Setup

1. Install dependencies using Bun:
   ```bash
   bun install
   ```

2. Create a `.env` file in the root directory:
   ```ini
   ALLOWED_NUMBERS=1234567890,0987654321
   OWNER_NUMBERS=1234567890
   GEMINI_KEY_1=your_gemini_api_key_1
   GEMINI_KEY_2=your_gemini_api_key_2
   ```

## Usage

Run the bot:
```bash
bun start
```
*On the first run, it will generate a QR code in the terminal. Scan it with your WhatsApp mobile app to link the session.*

### Features
- **AI Chat:** Anyone in `ALLOWED_NUMBERS` can talk to the bot by starting their message with `kujju`.
- **Hermes Bridge:** Anyone in `ALLOWED_NUMBERS` can send `$kujju <prompt>` to query Hermes Agent via SSE stream. Responses are delivered with `>` prefix.
- **Owner Commands:** Anyone in `OWNER_NUMBERS` can run PC commands by sending `!kujju <command>` (e.g. `!kujju increase volume` or `!kujju open notepad`).
- **Dynamic Skills:** Easily add numbers to the allowlist via `python skills/add_number.py <number>`.

### Hermes Bridge Setup

Add to your `.env`:
```ini
HERMES_API_URL=https://your-hermes-instance.up.railway.app
HERMES_API_KEY=your-...rd
```

The bridge sends a prompt to Hermes's `/hapi/v1/chat/completions` endpoint using the OpenAI Chat Completions format with streaming enabled. It relays only the final `message` and `error` events back to WhatsApp. Auth is via `Authorization: Bearer` header using the **same password as the dashboard** (`DASHBOARD_PASSWORD`).
