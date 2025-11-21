from fastmcp import FastMCP
import os
import shlex

mcp = FastMCP("demo-mcp-server")

@mcp.tool
def ping(message: str = "pong") -> str:
    """A dummy tool that echos a message back."""
    return f"[MCP] {message}"

@mcp.tool
def find_best_teacher(subject:str) -> str:
    """Return the name of the best teacher for a given subject."""
    return f"The best teacher for {subject} is Robert duuh."

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b

@mcp.tool
def execute_command(command: str) -> str:
    """Execute a very restricted read-only command limited to the workspace.

    Allowed commands (examples):
      - cat <path>    (Linux) or type <path> (Windows)  -> read a file
      - ls [path]     (Linux) or dir [path] (Windows)   -> list directory
      - head <path> [n]
      - tail <path> [n]

    All paths are resolved inside the repository workspace root. Any attempt to
    access files outside the workspace or run non-whitelisted commands is denied.
    Output is truncated and lines containing likely secrets are redacted.
    """

    # Workspace root = two levels up from this file (project root)
    WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    MAX_OUTPUT_CHARS = 10000
    REDACT_PATTERNS = [
        "password", "passwd", "secret", "api_key", "apikey", "token",
        "private_key", "private", "ssh", "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----", "credential"
    ]

    def within_root(path: str) -> bool:
        try:
            path = os.path.abspath(path)
            return os.path.commonpath([path, WORKSPACE_ROOT]) == WORKSPACE_ROOT
        except Exception:
            return False

    def resolve_path(p: str) -> str:
        if os.path.isabs(p):
            candidate = os.path.abspath(p)
        else:
            candidate = os.path.abspath(os.path.join(WORKSPACE_ROOT, p))
        return candidate

    def redact_lines(text: str) -> str:
        out_lines = []
        for line in text.splitlines():
            low = line.lower()
            if any(pat in low for pat in REDACT_PATTERNS):
                out_lines.append("[REDACTED]")
            else:
                out_lines.append(line)
        return "\n".join(out_lines)

    def truncate(text: str) -> str:
        if len(text) > MAX_OUTPUT_CHARS:
            return text[:MAX_OUTPUT_CHARS] + "\n...[output truncated]"
        return text

    # Basic parsing - do not use a shell; only tokenized commands
    try:
        tokens = shlex.split(command, posix=(os.name != "nt"))
    except ValueError:
        return "Error: could not parse command."

    if not tokens:
        return "Error: empty command."

    cmd = tokens[0].lower()

    # Map Windows 'type' to 'cat' behaviour, 'dir' to 'ls'
    if cmd == "type":
        cmd = "cat"
    if cmd == "dir":
        cmd = "ls"

    try:
        if cmd == "ls":
            # ls [path]
            target = tokens[1] if len(tokens) > 1 else WORKSPACE_ROOT
            path = resolve_path(target)
            if not within_root(path):
                return "Error: access denied."
            if not os.path.isdir(path):
                return "Error: not a directory."
            entries = sorted(os.listdir(path))
            return "\n".join(entries) or "[empty]"

        elif cmd == "cat":
            # cat <path>
            if len(tokens) != 2:
                return "Usage: cat <path>"
            path = resolve_path(tokens[1])
            if not within_root(path):
                return "Error: access denied."
            if not os.path.isfile(path):
                return "Error: not a file."
            with open(path, "r", errors="ignore") as f:
                content = f.read()
            content = redact_lines(content)
            return truncate(content)

        elif cmd in ("head", "tail"):
            # head <path> [n]
            if len(tokens) < 2:
                return f"Usage: {cmd} <path> [lines]"
            path = resolve_path(tokens[1])
            if not within_root(path):
                return "Error: access denied."
            if not os.path.isfile(path):
                return "Error: not a file."
            try:
                n = int(tokens[2]) if len(tokens) > 2 else 10
            except ValueError:
                return "Error: lines must be an integer."
            with open(path, "r", errors="ignore") as f:
                lines = f.readlines()
            if cmd == "head":
                selected = lines[:n]
            else:
                selected = lines[-n:]
            content = "".join(selected)
            content = redact_lines(content)
            return truncate(content)

        else:
            return ("Error: only read-only operations inside the workspace are allowed. "
                    "Allowed commands: cat/type, ls/dir, head, tail.")
    except Exception:
        return "Error: could not perform the requested operation."

if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8001)
