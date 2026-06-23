import sys
import os
import subprocess
import time

PID_FILE = os.path.join(os.path.dirname(__file__), "kujju-wa.pid")
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
LOG_FILE = os.path.join(PROJECT_ROOT, "bot.log")


def get_pid():
    if os.path.exists(PID_FILE):
        with open(PID_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return None
    return None


def start():
    pid = get_pid()
    if pid is not None:
        try:
            output = subprocess.check_output(
                f'tasklist /FI "PID eq {pid}" /NH', shell=True
            ).decode()
            if str(pid) in output:
                print(f"Bot is already running (PID: {pid})")
                return
        except Exception:
            pass

    print("Starting kujju-wa bot in background...")
    CREATE_NO_WINDOW = 0x08000000
    CREATE_NEW_PROCESS_GROUP = 0x00000200

    # Command to start the bot
    cmd = "bun start"

    log = open(LOG_FILE, "a")
    process = subprocess.Popen(
        cmd,
        shell=True,
        cwd=PROJECT_ROOT,
        creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )

    with open(PID_FILE, "w") as f:
        f.write(str(process.pid))
    print(f"Bot started successfully (PID: {process.pid})")
    print(f"Logs are being written to {LOG_FILE}")


def stop():
    pid = get_pid()
    if pid is None:
        print("Bot is not running.")
        return

    print(f"Stopping bot (PID: {pid})...")
    try:
        # /T kills the tree, /F forces
        subprocess.run(
            f"taskkill /PID {pid} /T /F",
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("Bot stopped successfully.")
    except subprocess.CalledProcessError:
        print("Failed to stop bot or it was already stopped.")

    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)


def restart():
    stop()
    time.sleep(2)
    start()


def enable():
    startup_path = os.path.join(
        os.getenv("APPDATA"), r"Microsoft\Windows\Start Menu\Programs\Startup"
    )
    bat_file = os.path.join(startup_path, "kujju-wa-startup.bat")

    cli_bat_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "kujju-wa.bat"
    )

    with open(bat_file, "w") as f:
        f.write("@echo off\n")
        f.write(f'call "{cli_bat_path}" start\n')

    print(f"Enabled at startup (Created {bat_file})")


def disable():
    startup_path = os.path.join(
        os.getenv("APPDATA"), r"Microsoft\Windows\Start Menu\Programs\Startup"
    )
    bat_file = os.path.join(startup_path, "kujju-wa-startup.bat")

    if os.path.exists(bat_file):
        os.remove(bat_file)
        print("Disabled startup.")
    else:
        print("Startup was not enabled.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: kujju-wa <start|stop|restart|enable|disable>")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "restart":
        restart()
    elif cmd == "enable":
        enable()
    elif cmd == "disable":
        disable()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: kujju-wa <start|stop|restart|enable|disable>")
        sys.exit(1)
