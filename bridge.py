from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from datetime import datetime
import json
import pandas as pd


# ------------------------------------------------------------
# CONNECT TO CHAINS
# ------------------------------------------------------------
def connect_to(chain):
    if chain == 'source':
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"
    elif chain == 'destination':
        api_url = "https://bsc-testnet.publicnode.com"
    else:
        raise ValueError(f"Invalid chain: {chain}")

    w3 = Web3(Web3.HTTPProvider(api_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    with open(contract_info, "r") as f:
        return json.load(f)[chain]


# ------------------------------------------------------------
# MAIN EVENT SCANNER
# ------------------------------------------------------------
def scan_blocks(chain, contract_info="contract_info.json"):
    if chain not in ['source', 'destination']:
        return 0

    w3 = connect_to(chain)
    cdata = get_contract_info(chain, contract_info)
    contract_address = Web3.to_checksum_address(cdata['address'])
    contract = w3.eth.contract(address=contract_address, abi=cdata['abi'])

    latest_block = w3.eth.block_number
    from_block = max(latest_block - 20, 0)
    to_block = latest_block

    events_list = []

    # Event signature topics
    DEPOSIT_TOPIC = "0x" + w3.keccak(
        text="Deposit(address,address,uint256)"
    ).hex()

    UNWRAP_TOPIC = "0x" + w3.keccak(
        text="Unwrap(address,address,address,address,uint256)"
    ).hex()

    WITHDRAWAL_TOPIC = "0x" + w3.keccak(
        text="Withdrawal(address,address,uint256)"
    ).hex()

    WRAP_TOPIC = "0x" + w3.keccak(
        text="Wrap(address,address,uint256)"
    ).hex()

    # ------------------------------------------------------------
    # SOURCE CHAIN
    # ------------------------------------------------------------
    if chain == "source":

        try:
            logs = w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": contract_address,
                "topics": [DEPOSIT_TOPIC]
            })
        except:
            logs = []

        deposits = []
        for log in logs:
            ev = contract.events.Deposit().process_log(log)
            deposits.append(ev)
            events_list.append({
                "event": "Deposit",
                "block": ev.blockNumber,
                "token": ev.args["token"],
                "recipient": ev.args["recipient"],
                "amount": ev.args["amount"],
                "tx": ev.transactionHash.hex(),
            })

        if deposits:
            handle_deposits(deposits, contract_info)

        try:
            logs2 = w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": contract_address,
                "topics": [WITHDRAWAL_TOPIC]
            })
        except:
            logs2 = []

        withdrawals = []
        for log in logs2:
            ev = contract.events.Withdrawal().process_log(log)
            withdrawals.append(ev)
            events_list.append({
                "event": "Withdrawal",
                "block": ev.blockNumber,
                "token": ev.args["token"],
                "recipient": ev.args["recipient"],
                "amount": ev.args["amount"],
                "tx": ev.transactionHash.hex(),
            })

        if withdrawals:
            handle_withdrawals(withdrawals)

    # ------------------------------------------------------------
    # DESTINATION CHAIN
    # ------------------------------------------------------------
    else:

        try:
            logs = w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": contract_address,
                "topics": [UNWRAP_TOPIC]
            })
        except:
            logs = []

        unwraps = []
        for log in logs:
            ev = contract.events.Unwrap().process_log(log)
            unwraps.append(ev)
            events_list.append({
                "event": "Unwrap",
                "block": ev.blockNumber,
                "underlying_token": ev.args["underlying_token"],
                "wrapped_token": ev.args["wrapped_token"],
                "sender": ev.args["frm"],
                "to": ev.args["to"],
                "amount": ev.args["amount"],
                "tx": ev.transactionHash.hex(),
            })

        if unwraps:
            handle_unwraps(unwraps, contract_info)

        try:
            logs2 = w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": contract_address,
                "topics": [WRAP_TOPIC]
            })
        except:
            logs2 = []

        wraps = []
        for log in logs2:
            ev = contract.events.Wrap().process_log(log)
            wraps.append(ev)
            events_list.append({
                "event": "Wrap",
                "block": ev.blockNumber,
                "underlying_token": ev.args["underlying_token"],
                "wrapped_token": ev.args["wrapped_token"],
                "to": ev.args["to"],
                "amount": ev.args["amount"],
                "tx": ev.transactionHash.hex(),
            })

        if wraps:
            handle_wraps(wraps)

    return pd.DataFrame(events_list)


# ------------------------------------------------------------
# HANDLE DEPOSITS → CALL wrap() ON DESTINATION
# ------------------------------------------------------------
def handle_deposits(events, contract_info="contract_info.json"):
    w3 = connect_to("destination")
    cdata = get_contract_info("destination", contract_info)
    dest = w3.eth.contract(address=Web3.to_checksum_address(cdata["address"]), abi=cdata["abi"])

    key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
    sender = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    nonce = w3.eth.get_transaction_count(sender)

    for ev in sorted(events, key=lambda e: (e.blockNumber, e.logIndex)):
        token = ev.args["token"]
        recipient = ev.args["recipient"]
        amount = ev.args["amount"]

        tx = dest.functions.wrap(token, recipient, amount).build_transaction({
            "chainId": w3.eth.chain_id,
            "gas": 300000,
            "gasPrice": w3.to_wei("5", "gwei"),
            "nonce": nonce
        })

        signed = w3.eth.account.sign_transaction(tx, key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print("Wrap:", tx_hash.hex())
        nonce += 1


# ------------------------------------------------------------
# HANDLE UNWRAPS → CALL withdraw() ON SOURCE
# ------------------------------------------------------------
def handle_unwraps(events, contract_info="contract_info.json"):
    w3 = connect_to("source")

    cdata = get_contract_info("source", contract_info)
    src = w3.eth.contract(
        address=Web3.to_checksum_address(cdata["address"]),
        abi=cdata["abi"]
    )

    key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
    sender = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    nonce = w3.eth.get_transaction_count(sender)

    for ev in sorted(events, key=lambda e: (e.blockNumber, e.logIndex)):

        # MUST MATCH THE DESTINATION UNWRAP EVENT ABI
        underlying_token = ev.args["underlying_token"]
        recipient = ev.args["to"]
        amount = ev.args["amount"]

        tx = src.functions.withdraw(
            underlying_token,
            recipient,
            amount
        ).build_transaction({
            "chainId": w3.eth.chain_id,
            "gas": 300000,
            "gasPrice": w3.to_wei("5", "gwei"),
            "nonce": nonce,
        })

        signed = w3.eth.account.sign_transaction(tx, key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print("Withdraw:", tx_hash.hex())

        nonce += 1


# ------------------------------------------------------------
# HANDLE WITHDRAWAL EVENTS → NO ACTION NEEDED
# ------------------------------------------------------------
def handle_withdrawals(events):
    print(f"Detected {len(events)} Withdrawal events (no action required).")


# ------------------------------------------------------------
# HANDLE WRAP EVENTS → NO ACTION NEEDED
# ------------------------------------------------------------
def handle_wraps(events):
    print(f"Detected {len(events)} Wrap events (no action required).")
