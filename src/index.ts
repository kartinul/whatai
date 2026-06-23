import {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
} from "@whiskeysockets/baileys";
import * as qrcode from "qrcode-terminal";
import * as dotenv from "dotenv";
import pino from "pino";
import { recordMessage, getChatHistory, sendMsg } from "./utils";
import { runCommand } from "./executor";
import {
  userPrompt,
  ownerPrompt,
  SYSTEM_PROMPT,
  OWNER_SYSTEM_PROMPT,
} from "./prompt";
import { callGroqLlm } from "./groq_helpers";
import { callLlm } from "./ai_helpers";

dotenv.config();

const ALLOWED_NUMBERS = new Set(
  (process.env.ALLOWED_NUMBERS || "").split(",").map((n) => n.trim()),
);
const OWNER_NUMBERS = new Set(
  (process.env.OWNER_NUMBERS || "").split(",").map((n) => n.trim()),
);

async function connectToWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState("auth_info_baileys");

  const sock = makeWASocket({
    auth: state,
    logger: pino({ level: "silent" }) as any,
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      qrcode.generate(qr, { small: true });
    }

    if (connection === "close") {
      const shouldReconnect =
        (lastDisconnect?.error as any)?.output?.statusCode !==
        DisconnectReason.loggedOut;
      console.log(
        "connection closed due to ",
        lastDisconnect?.error,
        ", reconnecting ",
        shouldReconnect,
      );
      if (shouldReconnect) {
        connectToWhatsApp();
      }
    } else if (connection === "open") {
      console.log("Opened connection");
    }
  });

  sock.ev.on("messages.upsert", async (m) => {
    if (m.type !== "notify") return;
    const msg = m.messages[0];

    const chatId = msg?.key?.remoteJid;
    let senderJid =
      msg?.key?.remoteJidAlt ||
      msg?.key?.participantAlt ||
      msg?.participant ||
      msg?.key?.participant ||
      msg?.key?.remoteJid;

    // If it's a fromMe message, the sender is always the owner/bot
    if (msg?.key?.fromMe) {
      senderJid = sock.user?.id || senderJid;
    }

    const phoneNo = senderJid
      ? senderJid.split("@")[0].split(":")[0]
      : "unknown";

    const text =
      msg?.message?.conversation ||
      msg?.message?.extendedTextMessage?.text ||
      "";

    if (!msg || !msg.message) return;
    if (!chatId || !senderJid) return;

    // If you sent it from your own phone (fromMe), you bypass the ALLOWED_NUMBERS list automatically.
    console.log(phoneNo);
    const isAllowed = msg.key.fromMe || ALLOWED_NUMBERS.has(phoneNo);
    if (!isAllowed) {
      return;
    }

    if (!text) return;

    console.log(
      `[debug] Received msg from ${phoneNo}: "${text}" (chatId: ${chatId}, fromMe: ${msg?.key?.fromMe})`,
    );

    const username = msg.pushName || phoneNo;

    const lowerText = text.trim().toLowerCase();

    // --- Owner command ---
    const isOwner = msg.key.fromMe || OWNER_NUMBERS.has(phoneNo);
    if (isOwner && lowerText.startsWith("!kujju")) {
      const cmd = text.trim().substring(6).trim();
      try {
        const raw = await callLlm(
          OWNER_SYSTEM_PROMPT,
          ownerPrompt(cmd, phoneNo),
        );
        // Clean AI response markdown fences
        const cleaned = raw
          .replace(/^```(?:json)?\n?/gm, "")
          .replace(/\n?```$/gm, "")
          .trim();
        const data = JSON.parse(cleaned);
        const command = data.command;
        const response = data.response || "done";

        await runCommand(command);
        await sendMsg(sock, chatId, response);
        console.log(`[owner] '${cmd}' => ran: '${command}'`);
      } catch (err: any) {
        await sendMsg(sock, chatId, `failed: ${err.message}`);
        console.log(`[owner] error: ${err.message}`);
      }
      return;
    }

    // --- Regular Kujju bot ---
    if (lowerText.startsWith("kujju")) {
      const history = getChatHistory(chatId);
      try {
        const aiReply = await callGroqLlm(
          SYSTEM_PROMPT,
          userPrompt(text.trim(), username, history),
        );
        await sendMsg(sock, chatId, aiReply);
        console.log(
          `--> Replied to ${chatId}: ${aiReply.substring(0, 60).replace(/\n/g, " ")}`,
        );
      } catch (err: any) {
        console.log(`[error] AI reply failed: ${err.message}`);
      }
    }
    // Record history
    recordMessage(chatId, username, text);
  });
}

connectToWhatsApp();
