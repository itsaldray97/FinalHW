from web3 import Web3
import json

RPC = "https://data-seed-prebsc-1-s1.binance.org:8545/"
CHAIN_ID = 97

PRIVATE_KEY = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
ACCOUNT = "0xB7131d4417d84025BAD139949D183398c2cf0916"

DESTINATION_ADDRESS = "0x6D5150421e565A6ACD3987D849cCc3C194caC91D"

UNDERLYING = [
    "0xc677c31AD31F73A5290f5ef067F8CEF8d301e45c",
    "0x0773b81e0524447784CcE1F3808fed6AaA156eC8"
]

w3 = Web3(Web3.HTTPProvider(RPC))
assert w3.is_connected(), "❌ BNB Testnet RPC failed!"

with open("Destination.json") as f:
    abi = json.load(f)["abi"]

destination = w3.eth.contract(address=DESTINATION_ADDRESS, abi=abi)

# -----------------------------------------
# ⭐ ROLE CHECK — IMPORTANT
# -----------------------------------------
default_admin = destination.functions.DEFAULT_ADMIN_ROLE().call()
creator = destination.functions.CREATOR_ROLE().call()
warden = destination.functions.WARDEN_ROLE().call()

print("Has ADMIN:", destination.functions.hasRole(default_admin, ACCOUNT).call())
print("Has CREATOR:", destination.functions.hasRole(creator, ACCOUNT).call())
print("Has WARDEN:", destination.functions.hasRole(warden, ACCOUNT).call())

for u in UNDERLYING:
    wrapped = destination.functions.wrapped_tokens(u).call()
    print("wrapped token for", u, "=", wrapped)

print(destination.functions.wrapped_tokens(UNDERLYING[0]).call())

# If any of these is False → STOP and tell me
# -----------------------------------------

def call_register(token, nonce):
    tx = destination.functions.registerToken(token).build_transaction({
        "from": ACCOUNT,
        "nonce": nonce,
        "gas": 500000,
        "gasPrice": w3.eth.gas_price,
        "chainId": CHAIN_ID
    })

    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print("Sent:", tx_hash.hex())

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Status:", receipt.status)
    print(receipt)

nonce = w3.eth.get_transaction_count(ACCOUNT)

call_register(UNDERLYING[0], nonce)
call_register(UNDERLYING[1], nonce + 1)

print("🎉 Tokens registered on BNB Testnet")
