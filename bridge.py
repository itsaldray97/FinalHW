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
    try:
        with open(contract_info, 'r') as f:
            contracts = json.load(f)
    except Exception as e:
        print(f"Failed to read contract info\n{e}")
        return 0
    return contracts[chain]


def scan_blocks(chain, contract_info="contract_info.json"):
    if chain not in ['source', 'destination']:
        print(f"This is an invalid chain!!!: {chain}")
        return 0

    w3 = connect_to(chain)
    contract_data = get_contract_info(chain, contract_info)
    contract_address = Web3.to_checksum_address(contract_data['address'])
    contract_abi = contract_data['abi']
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)


    latest_block = w3.eth.block_number
    from_block = max(latest_block - 10, 0)
    to_block = latest_block

    events_list = []


    block_timestamps = {}

    def get_event_timestamp(block_num):
        if block_num not in block_timestamps:

            block_timestamps[block_num] = w3.eth.get_block(block_num).timestamp
        return datetime.fromtimestamp(block_timestamps[block_num])

    deposit_topic = "0x" + w3.keccak(text="Deposit(address,address,uint256)").hex()
    unwrap_topic = "0x" + w3.keccak(text="Unwrap(address,address,uint256)").hex()

    if chain == "source":
        logs = w3.eth.get_logs({
            "fromBlock": from_block,
            "toBlock": to_block,
            "address": contract_address,
            "topics": [unwrap_topic]
        })

        deposit_events = []

        for log in logs:
            event = contract.events.Deposit().process_log(log)
            deposit_events.append(event)

            events_list.append({
                "event": "Deposit",
                "blockNumber": event.blockNumber,
                "transactionHash": event.transactionHash.hex(),
                "amount": event.args["amount"],
                "token": event.args["token"],
                "recepient": event.args["recipient"],
                "timestamp": get_event_timestamp(event.blockNumber)  # Used optimized function
            })

        if deposit_events:
            handle_deposits(deposit_events, contract_info)

    elif chain == "destination":
        logs = w3.eth.get_logs({
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "address": contract_address,
            "topics": [unwrap_topic]
        })

        unwrap_events = []

        for log in logs:
            event = contract.events.Unwrap().process_log(log)
            unwrap_events.append(event)

            events_list.append({
                "event": "Unwrap",
                "blockNumber": event.blockNumber,
                "transactionHash": event.transactionHash.hex(),
                "amount": event.args["amount"],
                "underlying_token": event.args["underlying_token"],
                "to": event.args["to"],
                "timestamp": get_event_timestamp(event.blockNumber)  # Used optimized function
            })

        if unwrap_events:
            handle_unwraps(unwrap_events, contract_info)

    df = pd.DataFrame(events_list)
    return df


def handle_deposits(events, contract_info="contract_info.json"):
    w3_dest = connect_to('destination')
    contract_data_dest = get_contract_info('destination', contract_info)
    contract_address_dest = Web3.to_checksum_address(contract_data_dest['address'])
    contract_abi_dest = contract_data_dest['abi']
    contract_dest = w3_dest.eth.contract(address=contract_address_dest, abi=contract_abi_dest)

    private_key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
    account_address = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    nonce = w3_dest.eth.get_transaction_count(account_address)

    # IMPORTANT: process events in deterministic order
    for ev in sorted(events, key=lambda e: e.blockNumber):
        args = ev['args']

        # Adjust these names to **match your event ABI**
        underlying_token = args['underlying_token']
        recipient = args['to']
        amount = args['amount']

        tx = contract_dest.functions.wrap(
            underlying_token,
            recipient,
            amount
        ).build_transaction({
            'chainId': w3_dest.eth.chain_id,
            'gas': 2000000,
            'gasPrice': w3_dest.to_wei('5', 'gwei'),
            'nonce': nonce,
        })

        signed_tx = w3_dest.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = w3_dest.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Wrap transaction sent with hash: {tx_hash.hex()}")

        nonce += 1



def handle_unwraps(events, contract_info="contract_info.json"):
    w3_source = connect_to('source')
    contract_data_source = get_contract_info('source', contract_info)
    contract_address_source = Web3.to_checksum_address(contract_data_source['address'])
    contract_abi_source = contract_data_source['abi']
    contract_source = w3_source.eth.contract(address=contract_address_source, abi=contract_abi_source)

    private_key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
    account_address = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    nonce = w3_source.eth.get_transaction_count(account_address)

    for ev in events:
        args = ev['args']
        underlying_token = args['underlying_token']
        recipient = args['to']
        amount = args['amount']

        tx = contract_source.functions.withdraw(
            underlying_token,
            recipient,
            amount
        ).build_transaction({
            'chainId': w3_source.eth.chain_id,
            'gas': 2000000,
            'gasPrice': w3_source.to_wei('5', 'gwei'),
            'nonce': nonce,
        })

        signed_tx = w3_source.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = w3_source.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Withdraw transaction sent with hash: {tx_hash.hex()}")

        nonce += 1