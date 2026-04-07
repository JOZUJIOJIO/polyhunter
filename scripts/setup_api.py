"""
PolyHunter API Setup Script
===========================
This script helps you set up Polymarket API credentials.

Usage:
  1. Set POLYMARKET_PRIVATE_KEY in your .env file first
  2. Run: python scripts/setup_api.py
  3. The script will auto-generate API credentials and update your .env

Prerequisites:
  - A funded Polygon wallet (EOA) with USDC.e
  - Private key for that wallet
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv


def check_read_only():
    """Test connection with read-only client first."""
    from py_clob_client.client import ClobClient

    print("\n[1/4] Testing read-only connection to Polymarket...")
    client = ClobClient("https://clob.polymarket.com")

    try:
        resp = client.get_ok()
        print(f"  Connection: OK")
    except Exception as e:
        print(f"  Connection FAILED: {e}")
        print("  Check your network connection or VPN settings.")
        return False

    try:
        server_time = client.get_server_time()
        print(f"  Server time: {server_time}")
    except Exception as e:
        print(f"  Warning: Could not get server time: {e}")

    return True


def derive_api_credentials(private_key: str):
    """Derive or create API credentials from the private key."""
    from py_clob_client.client import ClobClient

    print("\n[2/4] Deriving API credentials from your private key...")

    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137,
        signature_type=0,  # EOA
    )

    try:
        creds = client.create_or_derive_api_creds()
        print(f"  API Key:       {creds.api_key}")
        print(f"  API Secret:    {creds.api_secret[:10]}...")
        print(f"  API Passphrase:{creds.api_passphrase[:10]}...")
        return creds
    except Exception as e:
        print(f"  FAILED to derive credentials: {e}")
        print("  Make sure your private key is correct and your wallet has some MATIC for gas.")
        return None


def get_wallet_address(private_key: str) -> str:
    """Derive the wallet address from a private key."""
    try:
        from eth_account import Account
        acct = Account.from_key(private_key)
        return acct.address
    except ImportError:
        print("  Warning: eth_account not installed, cannot derive address.")
        print("  Install it: pip install eth-account")
        return ""
    except Exception as e:
        print(f"  Error deriving address: {e}")
        return ""


def update_env_file(api_key: str, api_secret: str, api_passphrase: str, funder: str):
    """Update .env file with the new credentials."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

    print(f"\n[3/4] Updating {env_path}...")

    # Read existing .env
    env_lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            env_lines = f.readlines()

    # Update or add values
    updates = {
        "POLYMARKET_API_KEY": api_key,
        "POLYMARKET_API_SECRET": api_secret,
        "POLYMARKET_API_PASSPHRASE": api_passphrase,
        "POLYMARKET_FUNDER": funder,
    }

    updated_keys = set()
    new_lines = []
    for line in env_lines:
        stripped = line.strip()
        for key, value in updates.items():
            if stripped.startswith(f"{key}="):
                new_lines.append(f"{key}={value}\n")
                updated_keys.add(key)
                break
        else:
            new_lines.append(line)

    # Append any keys not found
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)

    print("  .env updated successfully!")


def verify_trading_client(private_key: str, api_key: str, api_secret: str, api_passphrase: str):
    """Verify the full authenticated client works."""
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds

    print("\n[4/4] Verifying authenticated client...")

    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137,
        signature_type=0,
        funder=get_wallet_address(private_key),
    )
    client.set_api_creds(ApiCreds(
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase,
    ))

    try:
        # Try to get open orders (should return empty list for new account)
        orders = client.get_orders()
        print(f"  Authenticated access: OK")
        print(f"  Open orders: {len(orders) if orders else 0}")
        return True
    except Exception as e:
        print(f"  Warning: Could not verify full access: {e}")
        print("  This may be normal if you haven't set token allowances yet.")
        return True  # Non-fatal


def check_allowances():
    """Print instructions for setting token allowances."""
    print("\n" + "=" * 60)
    print("TOKEN ALLOWANCES")
    print("=" * 60)
    print("""
Before you can trade, you need to approve token spending on Polygon.
This requires 6 approval transactions (small gas fee each).

You can do this by:
  1. Going to https://polymarket.com and connecting your MetaMask wallet
  2. Making a small manual trade - Polymarket will prompt you to approve

Or run the allowance script:
  python scripts/set_allowances.py  (coming soon)
""")


def main():
    load_dotenv()

    private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "").strip()

    if not private_key:
        print("ERROR: POLYMARKET_PRIVATE_KEY not set in .env")
        print()
        print("Steps:")
        print("  1. Copy .env.example to .env:")
        print("     cp .env.example .env")
        print("  2. Edit .env and set POLYMARKET_PRIVATE_KEY to your wallet's private key")
        print("  3. Run this script again")
        sys.exit(1)

    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    # Derive wallet address
    address = get_wallet_address(private_key)
    if address:
        print(f"Wallet address: {address}")

    # Step 1: Check read-only connection
    if not check_read_only():
        sys.exit(1)

    # Step 2: Derive API credentials
    creds = derive_api_credentials(private_key)
    if not creds:
        sys.exit(1)

    # Step 3: Update .env
    update_env_file(
        api_key=creds.api_key,
        api_secret=creds.api_secret,
        api_passphrase=creds.api_passphrase,
        funder=address,
    )

    # Step 4: Verify
    verify_trading_client(private_key, creds.api_key, creds.api_secret, creds.api_passphrase)

    # Print allowance info
    check_allowances()

    print("\n" + "=" * 60)
    print("SETUP COMPLETE!")
    print("=" * 60)
    print(f"""
Your .env file has been updated with:
  - POLYMARKET_API_KEY
  - POLYMARKET_API_SECRET
  - POLYMARKET_API_PASSPHRASE
  - POLYMARKET_FUNDER

Next steps:
  1. Set token allowances (see above)
  2. Start the backend:  uvicorn backend.main:app --reload --port 8000
  3. Start the frontend: cd frontend && npm run dev
  4. Open http://localhost:3000
""")


if __name__ == "__main__":
    main()
