from web3 import Web3
import json

RPC = "https://bsc-testnet-rpc.publicnode.com"   # BNB testnet RPC
PRIVATE_KEY = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
ACCOUNT = "0xB7131d4417d84025BAD139949D183398c2cf0916"

DESTINATION = "0xAB25d175fC33Ae9c0189736e189f98e798E578b2"

# Load ABI
with open("Destination.json") as f:
    artifact = json.load(f)

abi = artifact["abi"]

w3 = Web3(Web3.HTTPProvider(RPC))
c = w3.eth.contract(address=DESTINATION, abi=abi)

creator_role = c.functions.CREATOR_ROLE().call()

tx = c.functions.grantRole(creator_role, ACCOUNT).build_transaction({
    "from": ACCOUNT,
    "nonce": w3.eth.get_transaction_count(ACCOUNT),
    "gas": 300000,
    "gasPrice": w3.eth.gas_price,
})

signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

print("TX:", tx_hash.hex())
print("Waiting...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
print("Status =", receipt.status)