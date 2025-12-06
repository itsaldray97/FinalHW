from web3 import Web3
import json

# -------------------------------------
# CONFIG
# -------------------------------------
RPC = "https://bsc-testnet.publicnode.com"    # Reliable BSC testnet RPC
CHAIN_ID = 97

PRIVATE_KEY = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
ACCOUNT = "0xB7131d4417d84025BAD139949D183398c2cf0916"

# -------------------------------------
# CONNECT
# -------------------------------------
w3 = Web3(Web3.HTTPProvider(RPC))
assert w3.is_connected(), "❌ Failed to connect to BNB Testnet"
print("✅ Connected to BNB Testnet")

# -------------------------------------
# LOAD CONTRACT ARTIFACT
# -------------------------------------
with open("Destination.json") as f:
    artifact = json.load(f)

abi = artifact["abi"]
bytecode = artifact["data"]["bytecode"]["object"]

Destination = w3.eth.contract(abi=abi, bytecode=bytecode)

# -------------------------------------
# DEPLOY CONTRACT (PASS ADMIN ADDRESS!)
# -------------------------------------
nonce = w3.eth.get_transaction_count(ACCOUNT)

tx = Destination.constructor(ACCOUNT).build_transaction({
    "from": ACCOUNT,
    "nonce": nonce,
    "gas": 4_000_000,
    "gasPrice": w3.eth.gas_price,
    "chainId": CHAIN_ID
})

signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

print("⏳ Deploying Destination...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

# -------------------------------------
# OUTPUT
# -------------------------------------
if receipt.status == 1:
    print("🎉 Deployment SUCCESS")
else:
    print("❌ Deployment FAILED")

print("Contract Address:", receipt.contractAddress)
print("Tx Hash:", tx_hash.hex())
