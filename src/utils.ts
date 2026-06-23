import type { WASocket, AnyMessageContent } from "@whiskeysockets/baileys";

// ------------------------------------------------------------------
// In-memory chat history store
// Keyed by chat_id string, stores last N (sender, text) tuples
// ------------------------------------------------------------------

const HISTORY_LIMIT = 10;
const historyStore = new Map<string, { sender: string; text: string }[]>();

export function recordMessage(
  chatId: string,
  sender: string,
  text: string,
): void {
  if (!historyStore.has(chatId)) {
    historyStore.set(chatId, []);
  }
  const history = historyStore.get(chatId)!;
  history.push({ sender, text });
  if (history.length > HISTORY_LIMIT) {
    history.shift(); // Remove oldest
  }
}

export function getChatHistory(
  chatId: string,
  n: number = 10,
): { sender: string; text: string }[] {
  const history = historyStore.get(chatId) || [];
  return history.slice(-n);
}

// ------------------------------------------------------------------
// Messaging
// ------------------------------------------------------------------

export async function sendMsg(
  client: WASocket,
  chatId: string,
  msg: string,
): Promise<void> {
  while (msg.toLowerCase().startsWith("kujju")) {
    msg = msg.slice(5);
  }
  await client.sendMessage(chatId, { text: `💦 ${msg.trim()}` });
}
