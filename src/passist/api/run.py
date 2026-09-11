"""
CLI forwarder for passist framework.
First attempts to call the warm server, falls back to in-process execution.
"""

import json
import sys
import os
import signal
import socket
from typing import Dict, Any, Optional
import httpx

# Add current directory to Python path so we can import passist modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .cli import run_tool
from .registry import TOOLS_BY_NAME

# Lockfile location - resolved relative to this file's location
LOCKFILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "..", "..", "..", ".passist-server", "server.json"
)
LOCKFILE_PATH = os.path.abspath(LOCKFILE_PATH)

def read_lockfile() -> Optional[Dict[str, Any]]:
    """Read the server lockfile to get connection details"""
    try:
        with open(LOCKFILE_PATH, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def call_warm_server(tool_name: str, args: Dict[str, Any], confirm: bool = False) -> Dict[str, Any]:
    """
    Call the warm server at 127.0.0.1:<port> with given tool and arguments.
    
    Returns:
        Result from server or fallback indicator
    """
    lockfile_data = read_lockfile()
    if not lockfile_data:
        # No server running, fall through to in-process
        return {"ok": False, "fallback": True}
    
    host = lockfile_data.get("host", "127.0.0.1")
    port = lockfile_data.get("port")
    token = lockfile_data.get("token")
    
    if not port or not token:
        # Invalid lockfile data
        return {"ok": False, "fallback": True}
    
    # Use HTTPX client to make the call
    try:
        # Use a new httpx client for this single call with no connection pooling
        client = httpx.Client(timeout=30.0)
        
        response = client.post(
            f"http://{host}:{port}/call",
            json={"tool": tool_name, "args": args, "confirm": confirm},
            headers={"Authorization": f"Bearer {token}"}
        )
        client.close()
        
        if response.status_code == 200:
            result = response.json()
            # If server indicates it can't handle this tool, fallback
            if not result.get("ok", True) and result.get("fallback", False):
                return {"ok": False, "fallback": True}
            return result
        else:
            # Server not responding or error occurred
            return {"ok": False, "fallback": True}
            
    except (ConnectionError, socket.error, httpx.RequestError):
        # Connection failed - server is down
        return {"ok": False, "fallback": True}

def main():
    """Main entry point for CLI forwarder"""
    if len(sys.argv) < 2:
        print("Usage: python -m passist.api.run <tool_name>", file=sys.stderr)
        print("Usage: python -m passist.api.run --list", file=sys.stderr)
        sys.exit(1)
    
    # Handle --list
    if sys.argv[1] == "--list":
        # List available tools from registry
        tool_list = []
        for tool_name, tool_spec in TOOLS_BY_NAME.items():
            tool_list.append({
                "name": tool_name,
                "description": tool_spec.description,
                "side_effect": tool_spec.side_effect
            })
        
        print(json.dumps(tool_list))
        sys.exit(0)
    
    # Regular tool execution
    tool_name = sys.argv[1]
    confirm = "--confirm" in sys.argv or "-c" in sys.argv
    
    # Read input from stdin (JSON) - buffer it for possible fallback
    try:
        stdin_input = sys.stdin.read()
        if not stdin_input.strip():
            args = {}
        else:
            args = json.loads(stdin_input)
        
        # Try warm server first
        result = call_warm_server(tool_name, args, confirm)
        
        if result.get("ok", True):
            # Success from warm server
            print(json.dumps(result["result"]))
            sys.exit(0)
        elif result.get("fallback", False):
            # Server doesn't know this tool or is down - fallback to in-process
            try:
                fallback_result = run_tool(tool_name, args, confirm)
                if fallback_result.get("ok"):
                    print(json.dumps(fallback_result["result"]))
                    sys.exit(0)
                else:
                    print(json.dumps({"error": fallback_result.get("error", "Unknown error")}), file=sys.stderr)
                    sys.exit(1)
            except Exception as e:
                print(json.dumps({"error": str(e)}), file=sys.stderr)
                sys.exit(1)
        else:
            # Error from server with explicit message
            print(json.dumps({"error": result.get("error", "Unknown error")}), file=sys.stderr) 
            sys.exit(1)
            
    except Exception as e:
        # Log errors to stderr and exit with error code
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()