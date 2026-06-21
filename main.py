import logging
import os
import threading
from dotenv import load_dotenv
from neonize.client import NewClient
from neonize.events import MessageEv
from neonize.proto.Neonize_pb2 import JID

from utils import send_msg, record_message, get_chat_history
from ai_helpers import call_llm
from executor import run_command
from prompt import user_prompt, owner_prompt, SYSTEM_PROMPT, OWNER_SYSTEM_PROMPT

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------

load_dotenv()
ALLOWED_NUMBERS: set[str] = set(os.getenv("ALLOWED_NUMBERS", "").split(","))
OWNER_NUMBERS: set[str] = set(os.getenv("OWNER_NUMBERS", "").split(","))

logging.basicConfig(level=logging.INFO)
client = NewClient("wa_session.sqlite3")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def extract_text(message: MessageEv) -> str:
    if message.Message.conversation:
        return message.Message.conversation
    if message.Message.HasField("extendedTextMessage"):
        return message.Message.extendedTextMessage.text or ""
    return ""


def handle_owner_command(client: NewClient, chat_id: JID, cmd: str) -> None:
    import json, re
    try:
        raw = call_llm(OWNER_SYSTEM_PROMPT, owner_prompt(cmd))
        # Strip markdown fences if AI wrapped it
        raw = re.sub(r"^```(?:json)?\n?", "", raw.strip(), flags=re.MULTILINE)
        raw = re.sub(r"\n?```$", "", raw.strip())
        data = json.loads(raw)
        command = data["command"]
        response = data.get("response", "done")
        run_command(command)
        send_msg(client, chat_id, response)
        print(f"[owner] {cmd!r} => ran: {command!r}")
    except Exception as e:
        send_msg(client, chat_id, f"failed: {e}")
        print(f"[owner] error: {e}")


def handle_kujju(client: NewClient, chat_id: JID, chat_id_str: str, msg: str, username: str) -> None:
    history = get_chat_history(chat_id_str)
    try:
        ai_reply = call_llm(SYSTEM_PROMPT, user_prompt(msg, username, history))
        send_msg(client, chat_id, ai_reply)
        print(f"--> Replied to {chat_id}: {ai_reply[:60]}")
    except Exception as e:
        print(f"[error] AI reply failed: {e}")


# ------------------------------------------------------------------
# Event handler
# ------------------------------------------------------------------

@client.event(MessageEv)
def on_message(client: NewClient, message: MessageEv):
    src = message.Info.MessageSource

    # Sender.Server == "lid" means WhatsApp is using its new local ID scheme.
    # Resolve it to the actual phone number JID.
    if src.Sender.Server == "lid":
        resolved = client.get_pn_from_lid(src.Sender)
        phone = resolved.User if resolved else src.Sender.User
    elif src.Chat.Server == "g.us":
        phone = src.Sender.User          # group DM: sender is Sender
    else:
        phone = src.Chat.User            # 1-1 chat: the other person IS the chat JID


    if phone not in ALLOWED_NUMBERS:
        return

    print(f"resolved phone={phone!r}")

    text = extract_text(message)
    if not text:
        return

    chat_id = message.Info.MessageSource.Chat
    chat_id_str = str(chat_id)
    username = message.Info.Pushname or phone

    record_message(chat_id_str, username, text)

    # Owner command: !kujju <action>
    if phone in OWNER_NUMBERS and text.strip().lower().startswith("!kujju"):
        cmd = text.strip()[6:].strip()
        print(cmd)
        threading.Thread(
            target=handle_owner_command, args=(client, chat_id, cmd), daemon=True
        ).start()
        return

    # Bot trigger: kujju ...
    if text.strip().lower().startswith("kujju"):
        threading.Thread(
            target=handle_kujju, args=(client, chat_id, chat_id_str, text.strip(), username), daemon=True
        ).start()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("Starting WhatsApp Bridge... Please wait.")
    client.connect()
