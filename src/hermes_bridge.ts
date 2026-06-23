import type { WASocket } from "@whiskeysockets/baileys";
import { sendMsg } from "./utils";

const HERMES_URL = process.env.HERMES_API_URL || "http://localhost:8000";

interface HermesEvent {
  type: "thinking" | "tool_call" | "tool_result" | "message" | "done" | "error";
  content?: string;
  tool?: string;
  args?: string;
  output?: string;
}

export async function streamHermes(
  sock: WASocket,
  chatId: string,
  prompt: string,
): Promise<void> {
  const resp = await fetch(`${HERMES_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: [{ role: "user", content: prompt }],
      stream: true,
    }),
  });

  if (!resp.ok || !resp.body) {
    await sendMsg(sock, chatId, `[error] Hermes request failed: ${resp.status}`);
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const event: HermesEvent = JSON.parse(line.slice(6));
        await handleEvent(sock, chatId, event);
      } catch {
        // skip malformed JSON lines
      }
    }
  }
}

async function handleEvent(
  sock: WASocket,
  chatId: string,
  event: HermesEvent,
) {
  switch (event.type) {
    case "message":
      await sendMsg(sock, chatId, `> ${event.content || ""}`);
      break;
    case "error":
      await sendMsg(sock, chatId, `[!] ${event.content || "unknown"}`);
      break;
    default:
      break;
  }
}
