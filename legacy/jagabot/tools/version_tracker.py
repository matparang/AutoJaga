import os
WORKSPACE = "/root/.jagabot/workspace"
VERSION_FILE = f"{WORKSPACE}/VERSION.md"

def get_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r') as f:
            return f.read()
    return "Version file not found"
