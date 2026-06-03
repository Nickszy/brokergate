import time
import subprocess
import httpx


def main():
    print("=== Testing OpenBroker API via User HTTP Requests ===")

    # 1. Start the uvicorn server as a subprocess (let output print directly to console)
    server_process = subprocess.Popen(
        ["uv", "run", "uvicorn", "openbroker.main:app", "--port", "8085", "--host", "127.0.0.1"]
    )

    # Wait for the server to spin up
    print("Starting OpenBroker API server...")
    time.sleep(3)

    client = httpx.Client(base_url="http://127.0.0.1:8085", timeout=30.0)

    try:
        # Check health endpoint
        print("Checking /health...")
        health_resp = client.get("/health")
        print(f"Health response ({health_resp.status_code}): {health_resp.json()}")

        # Test Account Summary Endpoint
        print("\nRequesting Account Summary GET /v1/accounts/20240513191053644/summary...")
        summary_resp = client.get("/v1/accounts/20240513191053644/summary")
        print(f"Status Code: {summary_resp.status_code}")
        print(f"JSON Response:\n{summary_resp.text}")

        # Test Account Positions Endpoint
        print("\nRequesting Account Positions GET /v1/accounts/20240513191053644/positions...")
        pos_resp = client.get("/v1/accounts/20240513191053644/positions")
        print(f"Status Code: {pos_resp.status_code}")
        print(f"JSON Response:\n{pos_resp.text}")

    except Exception as e:
        print(f"Error during API requests: {e}")
    finally:
        print("\nStopping OpenBroker API server...")
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")


if __name__ == "__main__":
    main()
