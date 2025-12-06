from web3 import Web3
import json
import sys

# ---------------------------
# BNB TESTNET RPC
# ---------------------------
RPC = "https://bsc-testnet.publicnode.com"
CHAIN_ID = 97  # BSC Testnet Chain ID

PRIVATE_KEY = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
ACCOUNT = "0xB7131d4417d84025BAD139949D183398c2cf0916"

w3 = Web3(Web3.HTTPProvider(RPC))
assert w3.is_connected(), "❌ BNB Testnet RPC failed!"

print("✅ Connected to BNB Testnet")

# ---------------------------
# Load Destination ABI/Bytecode
# ---------------------------
with open("Destination.json") as f:
    artifact = json.load(f)

abi = artifact["abi"]
bytecode = artifact["data"]["bytecode"]["object"]

Destination = w3.eth.contract(abi=abi, bytecode=bytecode)

# ---------------------------
# Deploy with admin address
# ---------------------------
tx = Destination.constructor(ACCOUNT).build_transaction({
    "from": ACCOUNT,
    "nonce": w3.eth.get_transaction_count(ACCOUNT),
    "gas": 4_000_000,
    "gasPrice": w3.eth.gas_price,
    "chainId": CHAIN_ID
})

signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

print("⏳ Deploying Destination on BNB Testnet...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

DEST_ADDRESS = receipt.contractAddress
print("🎉 Destination deployed at:", DEST_ADDRESS)
