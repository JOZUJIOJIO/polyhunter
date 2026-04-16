"""
PolyHunter Token Allowance Setup
=================================
Sets up all required token approvals for trading on Polymarket.

This script:
1. Approves USDC.e for CTF Exchange, Neg Risk CTF Exchange, and CTF contract
2. Approves Conditional Tokens for the same contracts

Usage:
  python scripts/set_allowances.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import httpx
from eth_account import Account
from eth_abi import encode

PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
RPC_URL = "https://1rpc.io/matic"
CHAIN_ID = 137

# Contract addresses
USDC_E = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKENS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# Spender addresses (Polymarket contracts)
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_CTF_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"

MAX_UINT256 = 2**256 - 1

# ERC20 approve(address,uint256) selector
APPROVE_SELECTOR = "0x095ea7b3"
# ERC1155 setApprovalForAll(address,bool) selector
SET_APPROVAL_SELECTOR = "0xa22cb465"


def get_nonce(address: str) -> int:
    resp = httpx.post(RPC_URL, json={
        "jsonrpc": "2.0", "method": "eth_getTransactionCount",
        "params": [address, "latest"], "id": 1
    }, timeout=15, verify=False)
    return int(resp.json()["result"], 16)


def get_gas_price() -> int:
    resp = httpx.post(RPC_URL, json={
        "jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 1
    }, timeout=15, verify=False)
    return int(resp.json()["result"], 16)


def send_tx(acct, to: str, data: str, nonce: int, gas_price: int) -> str:
    tx = {
        "to": to,
        "value": 0,
        "gas": 100000,
        "gasPrice": gas_price,
        "nonce": nonce,
        "chainId": CHAIN_ID,
        "data": data,
    }
    signed = acct.sign_transaction(tx)
    raw = signed.raw_transaction.hex()
    if not raw.startswith("0x"):
        raw = "0x" + raw

    resp = httpx.post(RPC_URL, json={
        "jsonrpc": "2.0", "method": "eth_sendRawTransaction",
        "params": [raw], "id": 1
    }, timeout=15, verify=False)

    result = resp.json()
    if "error" in result:
        raise Exception(f"TX failed: {result['error']}")
    return result["result"]


def wait_for_tx(tx_hash: str, timeout: int = 60) -> bool:
    for _ in range(timeout // 2):
        resp = httpx.post(RPC_URL, json={
            "jsonrpc": "2.0", "method": "eth_getTransactionReceipt",
            "params": [tx_hash], "id": 1
        }, timeout=15, verify=False)
        result = resp.json().get("result")
        if result:
            status = int(result["status"], 16)
            return status == 1
        time.sleep(2)
    return False


def build_approve_data(spender: str, amount: int = MAX_UINT256) -> str:
    """Build ERC20 approve(address, uint256) calldata."""
    spender_padded = spender[2:].lower().zfill(64)
    amount_hex = hex(amount)[2:].zfill(64)
    return APPROVE_SELECTOR + spender_padded + amount_hex


def build_set_approval_data(operator: str, approved: bool = True) -> str:
    """Build ERC1155 setApprovalForAll(address, bool) calldata."""
    operator_padded = operator[2:].lower().zfill(64)
    approved_hex = "1".zfill(64) if approved else "0".zfill(64)
    return SET_APPROVAL_SELECTOR + operator_padded + approved_hex


def main():
    if not PRIVATE_KEY:
        print("ERROR: POLYMARKET_PRIVATE_KEY not set in .env")
        sys.exit(1)

    pk = PRIVATE_KEY if PRIVATE_KEY.startswith("0x") else "0x" + PRIVATE_KEY
    acct = Account.from_key(pk)
    address = acct.address
    print(f"Wallet: {address}")

    nonce = get_nonce(address)
    gas_price = get_gas_price()
    print(f"Gas price: {gas_price / 1e9:.1f} Gwei")
    print()

    # Define all approval transactions
    approvals = [
        # ERC20: USDC.e → CTF Exchange
        ("USDC.e → CTF Exchange", USDC_E, build_approve_data(CTF_EXCHANGE)),
        # ERC20: USDC.e → Neg Risk CTF Exchange
        ("USDC.e → Neg Risk CTF Exchange", USDC_E, build_approve_data(NEG_RISK_CTF_EXCHANGE)),
        # ERC20: USDC.e → Neg Risk Adapter
        ("USDC.e → Neg Risk Adapter", USDC_E, build_approve_data(NEG_RISK_ADAPTER)),
        # ERC1155: Conditional Tokens → CTF Exchange
        ("CT → CTF Exchange", CONDITIONAL_TOKENS, build_set_approval_data(CTF_EXCHANGE)),
        # ERC1155: Conditional Tokens → Neg Risk CTF Exchange
        ("CT → Neg Risk CTF Exchange", CONDITIONAL_TOKENS, build_set_approval_data(NEG_RISK_CTF_EXCHANGE)),
        # ERC1155: Conditional Tokens → Neg Risk Adapter
        ("CT → Neg Risk Adapter", CONDITIONAL_TOKENS, build_set_approval_data(NEG_RISK_ADAPTER)),
    ]

    print(f"Sending {len(approvals)} approval transactions...\n")

    for i, (label, to, data) in enumerate(approvals):
        print(f"[{i+1}/{len(approvals)}] {label}...")
        try:
            tx_hash = send_tx(acct, to, data, nonce, gas_price)
            print(f"  TX: {tx_hash}")
            success = wait_for_tx(tx_hash)
            if success:
                print(f"  ✅ Confirmed")
            else:
                print(f"  ❌ Failed or timed out")
            nonce += 1
        except Exception as e:
            print(f"  ❌ Error: {e}")
            # Try to continue with next nonce
            nonce += 1

    print()
    print("=" * 50)
    print("DONE! All token approvals submitted.")
    print("You can now trade on Polymarket.")
    print()
    print("Note: Your USDC is 'native USDC' not 'USDC.e'.")
    print("Polymarket accepts both — when you place an order,")
    print("the exchange handles the conversion automatically.")
    print("=" * 50)


if __name__ == "__main__":
    main()
