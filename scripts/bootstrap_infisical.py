"""Bootstrap Infisical admin account, organization, and Universal Auth machine identity."""

import os
import sys
import httpx


def bootstrap_infisical(
    base_url: str = "http://localhost:8083",
    admin_email: str = "admin@central-intelligence.local",
    admin_password: str = "SuperSecurePass123!@#",
    org_name: str = "Central Intelligence Org",
    vault_project_name: str = "central-intelligence-vault",
) -> dict:
    client = httpx.Client(base_url=base_url.rstrip("/"), timeout=15.0)

    # 1. Check if already bootstrapped
    cfg_resp = client.get("/api/v1/admin/config")
    if cfg_resp.status_code == 200 and cfg_resp.json().get("config", {}).get("initialized"):
        print("Infisical instance is already bootstrapped.")
        return {}

    # 2. Bootstrap instance
    print(f"Bootstrapping Infisical admin at {base_url}...")
    b_resp = client.post(
        "/api/v1/admin/bootstrap",
        json={"email": admin_email, "password": admin_password, "organization": org_name},
    )
    if b_resp.status_code != 200:
        print(f"Bootstrap failed HTTP {b_resp.status_code}: {b_resp.text}")
        return {}

    b_data = b_resp.json()
    identity_token = b_data.get("identity", {}).get("credentials", {}).get("token")
    identity_id = b_data.get("identity", {}).get("id")
    print(f"Bootstrapped admin user and instance identity: {identity_id}")

    # 3. Attach Universal Auth
    auth_headers = {"Authorization": f"Bearer {identity_token}"}
    ua_resp = client.post(
        f"/api/v1/auth/universal-auth/identities/{identity_id}",
        json={
            "clientSecretTrustedIps": [{"ipAddress": "0.0.0.0/0"}, {"ipAddress": "::/0"}],
            "accessTokenTrustedIps": [{"ipAddress": "0.0.0.0/0"}, {"ipAddress": "::/0"}],
        },
        headers=auth_headers,
    )
    if ua_resp.status_code != 200:
        print(f"Universal auth attach failed: {ua_resp.text}")
        return {}

    client_id = ua_resp.json().get("identityUniversalAuth", {}).get("clientId")

    # 4. Create client secret
    cs_resp = client.post(
        f"/api/v1/auth/universal-auth/identities/{identity_id}/client-secrets",
        json={"description": "central-intelligence-agent", "numUsesLimit": 0, "ttl": 0},
        headers=auth_headers,
    )
    if cs_resp.status_code != 200:
        print(f"Client secret creation failed: {cs_resp.text}")
        return {}

    client_secret = cs_resp.json().get("clientSecret")

    # 5. Create project / vault workspace
    proj_resp = client.post(
        "/api/v2/workspace",
        json={"projectName": vault_project_name},
        headers=auth_headers,
    )
    proj_id = proj_resp.json().get("project", {}).get("id") if proj_resp.status_code == 200 else vault_project_name

    print("Infisical bootstrap complete:")
    print(f"  INFISICAL_CLIENT_ID={client_id}")
    print(f"  INFISICAL_CLIENT_SECRET={client_secret}")
    print(f"  INFISICAL_PROJECT_ID={proj_id}")

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "project_id": proj_id,
    }


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("INFISICAL_LIVE_URL", "http://localhost:8083")
    bootstrap_infisical(base_url=url)
