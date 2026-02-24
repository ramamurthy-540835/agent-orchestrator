#!/usr/bin/env python3
"""
Start all Databricks serving endpoints in your workspace.
Works with agents-db orchestration.
"""

import os
import asyncio
import json
from databricks_client import databricks_client


async def start_all_endpoints():
    """Start all stopped serving endpoints"""

    if not databricks_client or not databricks_client.config.is_configured():
        print("❌ Databricks not configured. Set DATABRICKS_HOST and DATABRICKS_TOKEN")
        return

    print("🚀 Starting all Databricks serving endpoints...")
    print(f"Workspace: {databricks_client.config.host}")
    print()

    # List all endpoints
    try:
        endpoints = await databricks_client.list_endpoints()
        print(f"Found {len(endpoints)} endpoints:\n")

        stopped = []
        running = []

        for endpoint in endpoints:
            name = endpoint.get("name", "Unknown")
            state = endpoint.get("state", "UNKNOWN")

            if state == "STOPPED":
                stopped.append(name)
                print(f"  ⏸️  STOPPED: {name}")
            else:
                running.append(name)
                print(f"  ✅ {state}: {name}")

        print(f"\nStatus: {len(running)} running, {len(stopped)} stopped")

        if not stopped:
            print("\n✅ All endpoints already running!")
            return

        # Start each stopped endpoint
        print(f"\n🔄 Starting {len(stopped)} endpoints...")

        for endpoint_name in stopped:
            try:
                response = await databricks_client.call_api(
                    "POST",
                    f"/serving-endpoints/{endpoint_name}/start",
                    {}
                )
                print(f"  ✓ {endpoint_name} - start command sent")
            except Exception as e:
                print(f"  ❌ {endpoint_name} - error: {str(e)}")

        print("\n⏳ Endpoints are starting (takes 2-5 minutes)...")
        print("Check Databricks workspace → Serving Endpoints for status")

    except Exception as e:
        print(f"❌ Error: {e}")


async def check_endpoint_status():
    """Check status of all endpoints"""

    if not databricks_client or not databricks_client.config.is_configured():
        print("❌ Databricks not configured")
        return

    try:
        endpoints = await databricks_client.list_endpoints()

        print("Endpoint Status:")
        print("-" * 50)

        for endpoint in endpoints:
            name = endpoint.get("name", "Unknown")
            state = endpoint.get("state", "UNKNOWN")

            if state == "READY":
                status = "✅"
            elif state == "STOPPED":
                status = "⏸️"
            elif state == "PENDING":
                status = "⏳"
            else:
                status = "❓"

            print(f"{status} {name:40} {state}")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        asyncio.run(check_endpoint_status())
    else:
        asyncio.run(start_all_endpoints())
