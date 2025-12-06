from web3 import Web3
import json

RPC = "https://data-seed-prebsc-1-s1.binance.org:8545/"
PRIVATE_KEY = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
ACCOUNT = "0xB7131d4417d84025BAD139949D183398c2cf0916"

DEST = "0x8e1073a0D4FA7049D0bCf73Eb88f33ad11b0D798"   # your deployed contract

TOKENS = [
    "0xc677c31AD31F73A5290f5ef067F8CEF8d301e45c",
    "0x0773b81e0524447784CcE1F3808fed6AaA156eC8"
]

w3 = Web3(Web3.HTTPProvider(RPC))

with open("Destination.json") as f:
    artifact = json.load(f)

abi = artifact["abi"]
dest = w3.eth.contract(address=DEST, abi=abi)

nonce = w3.eth.get_transaction_count(ACCOUNT)

for token in TOKENS:
    tx = dest.functions.registerToken(token).build_transaction({
        "from": ACCOUNT,
        "nonce": nonce,
        "gasPrice": w3.eth.gas_price,
        "gas": 3000000,
        "chainId": 97   # BSC testnet
    })

    signed = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    print("RegisterToken sent:", tx_hash.hex())
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print("Status:", receipt.status)
    nonce += 1