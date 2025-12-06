from web3 import Web3
import json
import sys

RPC = "https://api.avax-test.network/ext/bc/C/rpc"
PRIVATE_KEY = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
ACCOUNT = "0xB7131d4417d84025BAD139949D183398c2cf0916"

UNDERLYING1 = "0xc677c31AD31F73A5290f5ef067F8CEF8d301e45c"
UNDERLYING2 = "0x0773b81e0524447784CcE1F3808fed6AaA156eC8"

w3 = Web3(Web3.HTTPProvider(RPC))

if not w3.is_connected():
    print("❌ RPC not connected")
    sys.exit()

# --- LOAD ARTIFACT ---
with open("Destination.json") as f:
    artifact = json.load(f)

abi = artifact["abi"]
bytecode = artifact["data"]["bytecode"]["object"]

Destination = w3.eth.contract(abi=abi, bytecode=bytecode)

# --- DEPLOY CONTRACT ---
tx = Destination.constructor(ACCOUNT).build_transaction({
    "from": ACCOUNT,
    "nonce": w3.eth.get_transaction_count(ACCOUNT),
    "gas": 4_000_000,
    "gasPrice": w3.eth.gas_price,
    "chainId": 43113   # AVAX Fuji
})

signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

print("⏳ Deploying Destination...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
dest_address = receipt.contractAddress
print("✅ DESTINATION DEPLOYED AT:", dest_address)

# Create contract instance for interaction
destination = w3.eth.contract(address=dest_address, abi=abi)

# ----- REGISTER TOKENS -----
def register_token(token_address, nonce):
    tx = destination.functions.registerToken(
        Web3.to_checksum_address(token_address)
    ).build_transaction({
        "from": ACCOUNT,
        "nonce": nonce,
        "gas": 500000,
        "gasPrice": w3.eth.gas_price,
        "chainId": 43113
    })

    signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"📨 registerToken({token_address}) sent:", tx_hash.hex())

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print("   ↳ status:", receipt.status)

# Call registerToken twice
nonce = w3.eth.get_transaction_count(ACCOUNT)

register_token(UNDERLYING1, nonce)
register_token(UNDERLYING2, nonce + 1)

print("🎉 All tokens registered successfully!")