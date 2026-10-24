# ============================================================
# Adds (or removes) the DayBill connector in the Claude desktop
# app's config file: claude_desktop_config.json → "mcpServers".
# A timestamped backup of the old file is kept next to it.
#
#   python register_claude.py            -> add / update
#   python register_claude.py --remove   -> remove
# ============================================================
import os
import sys
import json
import glob
import shutil
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "daybill_mcp.py")
NAME = "daybill"


def config_paths():
    """Every place the Claude desktop app may keep its config on Windows
    (normal installer and Microsoft Store build), plus macOS for dev."""
    paths = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(os.path.join(appdata, "Claude", "claude_desktop_config.json"))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        for pkg in glob.glob(os.path.join(local, "Packages", "Claude_*")):
            paths.append(os.path.join(pkg, "LocalCache", "Roaming", "Claude",
                                      "claude_desktop_config.json"))
    if sys.platform == "darwin":
        paths.append(os.path.expanduser(
            "~/Library/Application Support/Claude/claude_desktop_config.json"))
    # keep only locations whose Claude folder exists (app installed / run once)
    found = [p for p in paths if os.path.isdir(os.path.dirname(p))]
    return found or paths[:1]


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8-sig") as f:
        txt = f.read().strip()
    return json.loads(txt) if txt else {}


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(path, path + f".backup_{stamp}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    remove = "--remove" in sys.argv
    python = sys.executable
    if python.lower().endswith("pythonw.exe"):
        python = python[:-5] + ".exe"          # stdio needs console python
    entry = {"command": python, "args": [SERVER],
             "env": {"PYTHONIOENCODING": "utf-8"}}
    for path in config_paths():
        try:
            data = load(path)
        except Exception as e:
            print(f"  ! Could not read {path}: {e}")
            print("    Fix or delete that file, then run this again.")
            continue
        servers = data.setdefault("mcpServers", {})
        if remove:
            if servers.pop(NAME, None) is not None:
                save(path, data)
                print(f"  - Removed DayBill from {path}")
            else:
                print(f"  (DayBill was not in {path})")
        else:
            servers[NAME] = entry
            save(path, data)
            print(f"  + Registered DayBill in {path}")
    if not remove:
        print("\n  Python : " + python)
        print("  Server : " + SERVER)


if __name__ == "__main__":
    main()
