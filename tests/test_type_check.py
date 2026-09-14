import json
import subprocess
import sys
import pytest

# Helper to run pyright and capture results

def run_pyright():
    # run pyright and return parsed json
    cmd = ["pyright", ".", "--output", "json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        # pyright exit code 0 means success, >0 indicates errors
        result = e
    return result

@pytest.mark.skip(reason="Requires pyright to be installed in the environment")
def test_pyright_no_errors():
    result = run_pyright()
    # If pyright exits with non-zero, capture output
    if result.returncode != 0:
        # parse json output if available
        try:
            data = json.loads(result.stdout)
        except Exception:
            data = None
        # Build error message
        msg = f"Pyright reported errors (exit {result.returncode}). Output:\n{result.stdout}\n{result.stderr}"
        if data and "errors" in data:
            msg += f"\nParsed errors: {data['errors']}"
        raise AssertionError(msg)
    # No errors
    assert result.returncode == 0
