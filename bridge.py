from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from datetime import datetime
import json
import pandas as pd


def connect_to(chain):
    if chain == 'source':
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"
    elif chain == 'destination':
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"
    else:
        raise ValueError(f"Invalid chain: {chain}")

    w3 = Web3(Web3.HTTPProvider(api_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    with open(contract_info, "r") as f:
        return json.load(f)[chain]


# ---------- MAIN EVENT SCANNER ----------
def scan_blocks(chain, contract_info="contract_info.json"):
    if chain not in ['source', 'destination']:
        return 0

    w3 = connect_to(chain)
    cdata = get_contract_info(chain, contract_info)
    contract_address = Web3.to_checksum_address(cdata['address'])
    contract_abi = cdata['abi']
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)

    latest = w3.eth.block_number
    from_block = max(latest - 5, 0)
    to_block = latest

    events_list = []
    block_ts = {}

    def ts(blocknum):
        if blocknum not in block_ts:
            block_ts[blocknum] = w3.eth.get_block(blocknum).timestamp
        return datetime.fromtimestamp(block_ts[blocknum])

    DEPOSIT_TOPIC = "0x" + w3.keccak(
        text="Deposit(address,address,uint256)"
    ).hex()

    UNWRAP_TOPIC = "0x" + w3.keccak(
        text="Unwrap(address,address,uint256)"
    ).hex()

    # ============================================================
    #                SOURCE CHAIN – detect DEPOSITS
    # ============================================================
    if chain == 'source':
        logs = w3.eth.get_logs({
            "fromBlock": from_block,
            "toBlock": to_block,
            "address": contract_address,
            "topics": [DEPOSIT_TOPIC, None, None]
        })

        deposit_events = []

        for log in logs:
            ev = contract.events.Deposit().process_log(log)
            deposit_events.append(ev)

        if deposit_events:
            handle_deposits(deposit_events, contract_info)

    # ============================================================
    #                DESTINATION CHAIN – detect UNWRAPS
    # ============================================================
    else:
        try:
            logs = w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": contract_address,
                "topics": [
                    UNWRAP_TOPIC,
                    None,
                    None
                ]
            })
        except Exception as e:
            print("No unwrap events or RPC limit reached:", e)
            return pd.DataFrame([])

        unwrap_events = []

        for log in logs:
            ev = contract.events.Unwrap().process_log(log)
            unwrap_events.append(ev)

            # append inside the loop
            events_list.append({
                "event": "Unwrap",
                "blockNumber": ev.blockNumber,
                "transactionHash": ev.transactionHash.hex(),
                "amount": ev.args["amount"],
                "underlying_token": ev.args["underlying_token"],
                "to": ev.args["to"],
            })

        if unwrap_events:
            handle_unwraps(unwrap_events, contract_info)

    return pd.DataFrame(events_list)


# --------------------------------------------------------------
#                  HANDLE DEPOSITS → WRAP()
# --------------------------------------------------------------
def handle_deposits(events, contract_info="contract_info.json"):
    w3_dest = connect_to("destination")
    cdata = get_contract_info("destination", contract_info)
    dest_contract = w3_dest.eth.contract(
        address=Web3.to_checksum_address(cdata["address"]),
        abi=cdata["abi"]
    )

    private_key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
    sender = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    nonce = w3_dest.eth.get_transaction_count(sender)

    for ev in sorted(events, key=lambda e: (e.blockNumber, e.logIndex)):
        args = ev["args"]

        token = args["token"]
        recipient = args["recipient"]
        amount = args["amount"]

        tx = dest_contract.functions.wrap(token, recipient, amount).build_transaction({
            "chainId": w3_dest.eth.chain_id,
            "gas": 300000,
            "gasPrice": w3_dest.to_wei("5", "gwei"),
            "nonce": nonce
        })

        signed_tx = w3_dest.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3_dest.eth.send_raw_transaction(signed_tx.raw_transaction)
        print("Wrap transaction:", tx_hash.hex())
        nonce += 1


# --------------------------------------------------------------
#                HANDLE UNWRAPS → WITHDRAW()
# --------------------------------------------------------------
def handle_unwraps(events, contract_info="contract_info.json"):
    w3_src = connect_to("source")
    cdata = get_contract_info("source", contract_info)
    src_contract = w3_src.eth.contract(
        address=Web3.to_checksum_address(cdata["address"]),
        abi=cdata["abi"]
    )

    private_key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
    account = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    nonce = w3_src.eth.get_transaction_count(account)

    for ev in sorted(events, key=lambda e: (e.blockNumber, e.logIndex)):
        args = ev["args"]
        underlying = args["underlying_token"]
        recipient = args["to"]
        amount = args["amount"]

        tx = src_contract.functions.withdraw(underlying, recipient, amount).build_transaction({
            "chainId": w3_src.eth.chain_id,
            "gas": 300000,
            "gasPrice": w3_src.to_wei("5", "gwei"),
            "nonce": nonce
        })

        signed = w3_src.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3_src.eth.send_raw_transaction(signed.raw_transaction)
        print("Withdraw transaction:", tx_hash.hex())
        nonce += 1
