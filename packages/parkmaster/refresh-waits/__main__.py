#!/usr/bin/env python3
"""
Entry point for DigitalOcean Functions.
This file exposes the main handler `main(event, context)` that
DO Functions expect, forwarding to your logic in main.py.
"""
from main import update_park_waits_http
from datetime import datetime

def main(event, context=None):
    """
    HTTP handler entry point for DO Functions.
    `event` contains parsed HTTP params (query, body, etc.).
    `context` is unused but included per DO spec.
    """
    result = update_park_waits_http(event)
   
    # Ensure HTTP-compatible return shape
    return {
        "statusCode": 200 if result.get("success", True) else 500,
        "body": result,
        "headers": {
            "Content-Type": "application/json"
        }
    }

if __name__ == "__main__":
    # Local test example
    test_event = {"query": {"all": "true"}}
    result = main(test_event)
    print(f"[{datetime.utcnow().isoformat()}] Function result:", result)