from web3 import Web3
import json

# -------------------------------
# CONFIGURATION
# -------------------------------
RPC = "https://api.avax-test.network/ext/bc/C/rpc"   # Avalanche Fuji
CHAIN_ID = 43113                                      # Chain ID for Fuji


PRIVATE_KEY = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
ACCOUNT = Web3.to_checksum_address("0xB7131d4417d84025BAD139949D183398c2cf0916")

# -------------------------------
# CONNECT TO RPC
# -------------------------------
w3 = Web3(Web3.HTTPProvider(RPC))
assert w3.is_connected(), "❌ RPC connection failed"
print("✅ Connected to RPC")

# -------------------------------
# LOAD REMIX JSON ARTIFACT
# -------------------------------
with open("Destination.json", "r") as f:
    artifact = json.load(f)

abi = artifact["abi"]
bytecode = artifact["data"]["bytecode"]["object"]   # Remix already places bytecode at root

Destination = w3.eth.contract(abi=abi, bytecode=bytecode)

# -------------------------------
# BUILD DEPLOY TRANSACTION
# -------------------------------
nonce = w3.eth.get_transaction_count(ACCOUNT)

tx = Destination.constructor(ACCOUNT).build_transaction({
    "from": ACCOUNT,
    "nonce": nonce,
    "gas": 5_000_000,
    "gasPrice": w3.eth.gas_price,
    "chainId": CHAIN_ID
})

# -------------------------------
# SIGN + SEND
# -------------------------------
signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

print("⏳ Deploying Destination...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

# -------------------------------
# RESULTS
# -------------------------------
print("\n==============================")
if receipt.status == 1:
    print("🎉 SUCCESS: Contract deployed!")
else:
    print("❌ Deployment FAILED")

print("Contract Address:", receipt.contractAddress)
print("Tx Hash:", tx_hash.hex())
print("==============================\n")