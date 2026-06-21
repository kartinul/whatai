from collections import defaultdict, deque
from neonize.client import NewClient
from neonize.proto.Neonize_pb2 import JID

_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=10))


def record_message(chat_id: str, sender: str, text: str) -> None:
    _history[chat_id].append((sender, text))


def get_chat_history(chat_id: str, n: int = 5) -> list[tuple[str, str]]:
    return list(_history[chat_id])[-n:]


def send_msg(client: NewClient, chat_id: JID, msg: str) -> None:
    while msg.startswith("kujju"):
        msg = msg[5:]
    client.send_message(chat_id, "💦 " + msg.strip())
