from web3 import Web3
import json
import sys

RPC = "https://api.avax-test.network/ext/bc/C/rpc"
PRIVATE_KEY = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
ACCOUNT = "0xB7131d4417d84025BAD139949D183398c2cf0916"

w3 = Web3(Web3.HTTPProvider(RPC))

if not w3.is_connected():
    print("❌ RPC not connected")
    sys.exit()

# --- LOAD COMPILATION ARTIFACT ---
with open("Source.json") as f:
    artifact = json.load(f)

abi = artifact["abi"]
bytecode = artifact["data"]["bytecode"]["object"]

Source = w3.eth.contract(abi=abi, bytecode=bytecode)

# --- FIXED: PASS ONE ARGUMENT TO CONSTRUCTOR ---
tx = Source.constructor(ACCOUNT).build_transaction({
    "from": ACCOUNT,
    "nonce": w3.eth.get_transaction_count(ACCOUNT),
    "gas": 3_000_000,
    "gasPrice": w3.eth.gas_price,
    "chainId": 43113    # AVAX Fuji
})

signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

print("⏳ Waiting for confirmation...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

print("✅ Contract deployed at:", receipt.contractAddress)