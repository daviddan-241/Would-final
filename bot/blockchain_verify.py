import logging
import requests

log = logging.getLogger(__name__)

SOL_ADDRESS = "46ZKRuURaASKEcKBafnPZgMaTqBL8RK8TssZgZzFCBzn"
ETH_ADDRESS = "0x479F8bdD340bD7276D6c7c9B3fF86EF2315f857A"
BNB_HEX_ADDRESS = "0x479F8bdD340bD7276D6c7c9B3fF86EF2315f857A"

SOL_RPC = "https://api.mainnet-beta.solana.com"
ETH_RPCS = [
    "https://cloudflare-eth.com",
    "https://eth.llamarpc.com",
    "https://rpc.ankr.com/eth",
]
BSC_RPCS = [
    "https://bsc-dataseed.binance.org",
    "https://bsc-dataseed1.binance.org",
    "https://bsc-dataseed2.binance.org",
]


def verify_sol_tx(tx_hash: str, from_wallet: str) -> tuple[bool, str]:
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                tx_hash,
                {"encoding": "json", "maxSupportedTransactionVersion": 0}
            ]
        }
        resp = requests.post(SOL_RPC, json=payload, timeout=20)
        data = resp.json()
        result = data.get("result")
        if not result:
            return False, "Transaction not found on Solana. Double-check the hash."
        meta = result.get("meta", {}) or {}
        if meta.get("err") is not None:
            return False, "Transaction failed on-chain. Please send a new one."
        account_keys = (
            result.get("transaction", {})
            .get("message", {})
            .get("accountKeys", [])
        )
        if SOL_ADDRESS in account_keys:
            return True, "verified"
        return False, (
            f"Payment destination not found in this transaction.\n"
            f"Make sure you sent to: `{SOL_ADDRESS}`"
        )
    except Exception as e:
        log.warning(f"SOL verify error: {e}")
        return False, "Could not reach Solana network. Try again in a moment."


def verify_eth_tx(tx_hash: str, from_wallet: str) -> tuple[bool, str]:
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getTransactionByHash",
        "params": [tx_hash],
        "id": 1
    }
    for rpc in ETH_RPCS:
        try:
            resp = requests.post(rpc, json=payload, timeout=15)
            result = resp.json().get("result")
            if not result:
                continue
            to = (result.get("to") or "").lower()
            if to == ETH_ADDRESS.lower():
                block = result.get("blockNumber")
                if block is None:
                    return False, "Transaction is still pending. Wait for confirmation and try again."
                return True, "verified"
            return False, (
                f"Transaction sent to wrong address.\n"
                f"Required address: `{ETH_ADDRESS}`"
            )
        except Exception as e:
            log.warning(f"ETH verify error ({rpc}): {e}")
            continue
    return False, "Could not reach Ethereum network. Try again in a moment."


def verify_bnb_tx(tx_hash: str, from_wallet: str) -> tuple[bool, str]:
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getTransactionByHash",
        "params": [tx_hash],
        "id": 1
    }
    for rpc in BSC_RPCS:
        try:
            resp = requests.post(rpc, json=payload, timeout=15)
            result = resp.json().get("result")
            if not result:
                continue
            block = result.get("blockNumber")
            if block is None:
                return False, "Transaction is still pending on BSC. Wait for confirmation."
            return True, "verified"
        except Exception as e:
            log.warning(f"BNB verify error ({rpc}): {e}")
            continue
    return False, "Could not reach BNB Chain network. Try again in a moment."


def verify_transaction(chain: str, tx_hash: str, from_wallet: str) -> tuple[bool, str]:
    chain = chain.lower()
    if chain == "sol":
        return verify_sol_tx(tx_hash, from_wallet)
    elif chain == "eth":
        return verify_eth_tx(tx_hash, from_wallet)
    elif chain == "bnb":
        return verify_bnb_tx(tx_hash, from_wallet)
    return False, "Unknown chain."
