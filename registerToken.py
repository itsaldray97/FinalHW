from web3 import Web3
import json

RPC = "https://bsc-testnet.publicnode.com"   # <-- FIXED
CHAIN_ID = 97

PRIVATE_KEY = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
ACCOUNT = "0xB7131d4417d84025BAD139949D183398c2cf0916"
DESTINATION = "0x7036B63c5368b8619De306B55Ddf952AAbE33eb2"  # your deployed destination

TOKENS = [
    "0xc677c31AD31F73A5290f5ef067F8CEF8d301e45c",
    "0x0773b81e0524447784CcE1F3808fed6AaA156eC8"
]

w3 = Web3(Web3.HTTPProvider(RPC))
assert w3.is_connected()

with open("Destination.json") as f:
    abi = json.load(f)["abi"]

c = w3.eth.contract(address=DESTINATION, abi=abi)

nonce = w3.eth.get_transaction_count(ACCOUNT)

for token in TOKENS:
    print("Creating wrapper for:", token)

    tx = c.functions.createToken(token, "WrappedToken", "wT").build_transaction({
        "from": ACCOUNT,
        "nonce": nonce,
        "gas": 900000,
        "gasPrice": w3.eth.gas_price,
        "chainId": CHAIN_ID,
    })

    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print("Tx:", tx_hash.hex())

    r = w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Status:", r.status)

    wrapped = c.functions.wrapped_tokens(token).call()
    print("Wrapped token:", wrapped)

    nonce += 1