import subprocess


def run_command(command: str) -> str:
    """Run a CLI command string and return stdout/stderr."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (result.stdout or result.stderr or "done").strip()
    except subprocess.TimeoutExpired:
        return "timed out"
    except Exception as e:
        return f"error: {e}"
