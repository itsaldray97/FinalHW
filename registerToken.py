from web3 import Web3
import json

# -------------------------------
# CONFIG
# -------------------------------
RPC = "https://api.avax-test.network/ext/bc/C/rpc"   # Avalanche Fuji
CHAIN_ID = 43113

PRIVATE_KEY = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
ACCOUNT = Web3.to_checksum_address("0xB7131d4417d84025BAD139949D183398c2cf0916")

DESTINATION_ADDRESS = Web3.to_checksum_address("0x5304Df8C40d25fA52478d916199abfaBFC8E220b")

# The underlying token to wrap:
UNDERLYING_TOKEN = Web3.to_checksum_address("0x0773b81e0524447784CcE1F3808fed6AaA156eC8")
# Change this to call for the 2nd token

NAME = "WrappedTokenA"
SYMBOL = "wTKA"

# -------------------------------
# CONNECT
# -------------------------------
w3 = Web3(Web3.HTTPProvider(RPC))
assert w3.is_connected(), "❌ Failed to connect"
print("✅ Connected")

# -------------------------------
# LOAD ABI
# -------------------------------
with open("Destination.json", "r") as f:
    artifact = json.load(f)

abi = artifact["abi"]
destination = w3.eth.contract(address=DESTINATION_ADDRESS, abi=abi)

# -------------------------------
# BUILD TX
# -------------------------------
nonce = w3.eth.get_transaction_count(ACCOUNT)

tx = destination.functions.createToken(
    UNDERLYING_TOKEN,
    NAME,
    SYMBOL
).build_transaction({
    "from": ACCOUNT,
    "nonce": nonce,
    "gas": 3_000_000,
    "gasPrice": w3.eth.gas_price,
    "chainId": CHAIN_ID,
})

# -------------------------------
# SIGN & SEND
# -------------------------------
signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

print("⏳ Sending createToken() ...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

# -------------------------------
# RESULT
# -------------------------------
print("Tx:", tx_hash.hex())
print("Status:", receipt.status)

if receipt.status == 1:
    print("🎉 SUCCESS — wrapped token created!")
else:
    print("❌ FAILED — transaction reverted")

# Read back the wrapped address:
wrapped_addr = destination.functions.wrapped_tokens(UNDERLYING_TOKEN).call()
print("Wrapped token:", wrapped_addr)