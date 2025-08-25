import requests
import base64
import json
import os
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urljoin

# Load environment variables from .env file
load_dotenv()

# Read environment variables
MLABITE_URL = os.getenv("MLABITE_URL")
REMOTE_RESULTS_PATH = os.getenv("REMOTE_RESULTS_PATH")
REMOTE_SAVE_PATH = os.getenv("REMOTE_SAVE_PATH")

if not MLABITE_URL:
    raise EnvironmentError("MLABITE_URL is not set in the .env file.")
if not REMOTE_RESULTS_PATH:
    raise EnvironmentError("RESULTS_PATH is not set in the .env file.")

RESULTS_DIR = Path(REMOTE_RESULTS_PATH)

def is_directory(node: dict) -> bool:
    return isinstance(node, dict) and 'content' not in node

def is_file(node: dict) -> bool:
    return isinstance(node, dict) and 'content' in node

def write_file(path: Path, content_b64: str) -> None:
    """Writes a base64-decoded file to disk."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(content_b64))
        print(f"[file] {path}")
    except Exception as exc:
        print(f"[err ] couldn’t write {path}: {exc}")

def create_entry(name: str, node: dict, dest_root: Path, depth: int) -> None:
    """Handles a single entry (file or folder)."""
    safe_name = Path(name).name
    path = dest_root / safe_name

    if is_directory(node):
        path.mkdir(parents=True, exist_ok=True)
        print(f"[dir ] {path}")
        create_entries(node, path, depth + 1)

    elif is_file(node):
        if depth == 0:
            print(f"[skip] {safe_name} (root-level file)")
        else:
            write_file(path, node["content"])

    else:
        print(f"[warn] unexpected entry for {safe_name}: {type(node).__name__}")

def create_entries(tree: dict, dest_root: Path, depth: int = 0) -> None:
    """Recursively creates files and folders from the JSON tree."""
    for name, node in tree.items():
        create_entry(name, node, dest_root, depth)

def save_fetched_results(json_response, output_root: Path):
    """Writes the reconstructed file structure."""
    file_tree = json_response if isinstance(json_response, dict) else json.loads(json_response)
    output_root.mkdir(parents=True, exist_ok=True)
    create_entries(file_tree, output_root)

def fetch_results():
    """
    Calls the /fetch_results endpoint via POST, with optional input_path.
    Saves results to RESULTS_DIR.
    """
    fetch_url = urljoin(MLABITE_URL, "fetch_results")

    response = requests.post(fetch_url, json={"s3_path": REMOTE_SAVE_PATH})
    response.raise_for_status()

    save_fetched_results(response.json(), RESULTS_DIR)
    return response

if __name__ == "__main__":
    fetch_results()
