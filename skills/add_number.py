"""
skills/add_number.py  --  Add a phone number to ALLOWED_NUMBERS in .env
Usage: python skills/add_number.py <phone_number>
"""
import sys
import os
import re

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def add_number(phone: str) -> None:
    # Remove + and any whitespace
    phone = phone.replace("+", "").replace(" ", "").strip()

    with open(ENV_PATH, "r") as f:
        content = f.read()

    match = re.search(r"^(ALLOWED_NUMBERS=)(.*)$", content, re.MULTILINE)
    if match:
        existing = [n.strip() for n in match.group(2).split(",") if n.strip()]
        if phone in existing:
            print(f"{phone} already in ALLOWED_NUMBERS")
            return
        existing.append(phone)
        new_line = f"ALLOWED_NUMBERS={','.join(existing)}"
        content = content[:match.start()] + new_line + content[match.end():]
    else:
        content += f"\nALLOWED_NUMBERS={phone}"

    with open(ENV_PATH, "w") as f:
        f.write(content)

    print(f"Added {phone} to ALLOWED_NUMBERS")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python skills/add_number.py <phone_number>")
        sys.exit(1)
    add_number(sys.argv[1])
