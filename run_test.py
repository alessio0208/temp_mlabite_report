import sys
import requests
import pandas as pd
import json
from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Resolve and validate environment paths
def get_env_path(var_name):
    value = os.getenv(var_name)
    if value is None:
        raise EnvironmentError(f"{var_name} is not set in the .env file.")
    return Path(value)

def get_env_url(var_name):
    value = os.getenv(var_name)
    if value is None:
        raise EnvironmentError(f"{var_name} is not set in the .env file.")
    return value

# Correct handling: URL is a string, others are Path objects
MLABITE_URL = get_env_url("MLABITE_URL")
TEMPLATES_PATH = get_env_path("TEMPLATES_PATH")
CONFIG_PATH = get_env_path("CONFIG_PATH")
TESTS_PATH = get_env_path("TESTS_PATH")
REMOTE_SAVE_PATH = get_env_path("REMOTE_SAVE_PATH")

def ensure_extension(filename: str, ext: str) -> str:
    """Ensure the filename has the specified extension."""
    if '.' not in Path(filename).name:
        return f"{filename}{ext}"
    return filename

def load_config_data(config_path, cases_path):
    """Loads configuration data and cases from files, including filenames."""
    with open(config_path, 'r') as file:
        config = json.load(file)

    df = pd.read_csv(cases_path, sep='\t')
    return {
        'config': config,
        'prompts': df.to_json(),
        'config_filename': config_path.name,
        'prompts_filename': cases_path.name
    }


def _print_http_error(resp: requests.Response) -> None:
    """Pretty-print details from a failed HTTP response."""
    print("---- RESPONSE META ----")
    print("URL:    ", resp.url)
    print("Status: ", resp.status_code, resp.reason)
    print("OK?:    ", resp.ok)

    print("\n---- RESPONSE HEADERS ----")
    for k, v in resp.headers.items():
        print(f"{k}: {v}")

    body_text = resp.text or ""
    print("\n---- RAW BODY (text) ----")
    print(body_text)

    print("\n---- JSON (if any) ----")
    try:
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except Exception:
        print("<no valid JSON body>")

def run_bias_tests(base_url, data, test_name, *, raise_on_error=False, timeout=120):
    """
    Posts data to the bias test API and retrieves reports.
    On HTTP error, prints full diagnostics. If raise_on_error=False (default), returns
    a dict with 'error' and 'response' fields instead of raising.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = REMOTE_SAVE_PATH / test_name / timestamp
    data = dict(data)  # shallow copy so we don't mutate caller's dict
    data['save_path'] = str(save_path)

    try:
        # Using json= sets Content-Type: application/json and handles dumps
        resp = requests.post(f"{base_url}/run_bias_tests", json=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        # Print everything the server sent back (400, 422, 500, etc.)
        _print_http_error(resp)
        if raise_on_error:
            raise
        # Return a structured error object so caller can inspect programmatically
        err_payload = {
            "error": str(e),
            "status_code": resp.status_code,
            "reason": resp.reason,
            "url": resp.url,
            "text": resp.text,
        }
        try:
            err_payload["json"] = resp.json()
        except Exception:
            err_payload["json"] = None
        return err_payload
    except requests.RequestException as e:
        # Network problems, timeouts, DNS, connection refused, etc.
        print("---- REQUEST EXCEPTION ----")
        print(repr(e))
        if raise_on_error:
            raise
        return {"error": str(e), "status_code": None, "reason": None, "url": f"{base_url}/run_bias_tests", "json": None, "text": None}
    
def load_test_file(test_name: str) -> dict:
    """Loads the test file from TESTS_PATH, ensures .json extension."""
    test_filename = ensure_extension(test_name, ".json")
    test_path = TESTS_PATH / test_filename
    with open(test_path, "r") as f:
        return json.load(f)

def resolve_test_paths(test_data: dict) -> tuple[Path, Path]:
    """Resolve config and template paths with default extensions."""
    config_name = ensure_extension(test_data.get("config_file", ""), ".json")
    template_name = ensure_extension(test_data.get("template", ""), ".csv")
    return CONFIG_PATH / config_name, TEMPLATES_PATH / template_name

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_test.py <test_filename>")
        sys.exit(1)

    test_name = sys.argv[1]
    test_data = load_test_file(test_name)
    config_path, template_path = resolve_test_paths(test_data)
    data = load_config_data(config_path, template_path)
    result = run_bias_tests(MLABITE_URL, data, test_name)
    print("Test result:", result)

if __name__ == '__main__':
    main()
