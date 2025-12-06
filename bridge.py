from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware  # Necessary for POA chains
from datetime import datetime
import json
import pandas as pd


def connect_to(chain):
    """
    Connect to the correct RPC endpoint for the given chain.
    'source'  -> Avalanche Fuji (AVAX testnet)
    'destination' -> BSC testnet
    """
    if chain == 'source':  # The source contract chain is avax
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"  # AVAX C-chain testnet

    elif chain == 'destination':  # The destination contract chain is bsc
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"  # BSC testnet

    else:
        raise ValueError(f"Invalid chain: {chain}")

    w3 = Web3(Web3.HTTPProvider(api_url))
    # inject the poa compatibility middleware to the innermost layer
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    """
        Load the contract_info file into a dictionary
        This function is used by the autograder and will likely be useful to you
    """
    try:
        with open(contract_info, 'r') as f:
            contracts = json.load(f)
    except Exception as e:
        print(f"Failed to read contract info\nPlease contact your instructor\n{e}")
        return 0
    return contracts[chain]


def scan_blocks(chain, contract_info="contract_info.json"):
    """
        chain - (string) should be either "source" or "destination"
        Scan the last 5 blocks of the source and destination chains
        Look for 'Deposit' events on the source chain and 'Unwrap' events on the destination chain
        When Deposit events are found on the source chain, call the 'wrap' function the destination chain
        When Unwrap events are found on the destination chain, call the 'withdraw' function on the source chain
    """

    if chain not in ['source', 'destination']:
        print(f"This is an invalid chain!!!: {chain}")
        return 0

    w3 = connect_to(chain)
    contract_data = get_contract_info(chain, contract_info)
    contract_address = Web3.to_checksum_address(contract_data['address'])
    contract_abi = contract_data['abi']  # already a list in contract_info.json
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)

    latest_block = w3.eth.block_number
    from_block = max(latest_block - 4, 0)
    to_block = latest_block

    events_list = []

    from_block = latest_block - 4
    to_block = latest_block

    deposit_topic = "0x" + w3.keccak(text="Deposit(address,address,uint256)").hex()
    unwrap_topic = "0x" + w3.keccak(text="Unwrap(address,address,uint256)").hex()

    if chain == "source":

        logs = w3.eth.get_logs({
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "address": contract_address,
            "topics": [deposit_topic]
        })

        deposit_events = []

        for log in logs:
            event = contract.events.Deposit().process_log(log)
            deposit_events.append(event)  # Store the processed event structure for handling

            # Append log details to events_list for the DataFrame
            events_list.append({
                "event": "Deposit",
                "blockNumber": event.blockNumber,
                "transactionHash": event.transactionHash.hex(),
                "amount": event.args["amount"],
                "token": event.args["token"],
                "recepient": event.args["recipient"],
                "timestamp": datetime.fromtimestamp(w3.eth.get_block(event.blockNumber).timestamp)
            })

        if deposit_events:
            handle_deposits(deposit_events, contract_info)

    elif chain == "destination":
        # Get Unwrap logs
        logs = w3.eth.get_logs({
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "address": contract_address,
            "topics": [unwrap_topic]
        })

        unwrap_events = []  # Store processed events to pass to handler

        for log in logs:
            event = contract.events.Unwrap().process_log(log)
            unwrap_events.append(event)

            # Append log details to events_list for the DataFrame
            events_list.append({
                "event": "Unwrap",
                "blockNumber": event.blockNumber,
                "transactionHash": event.transactionHash.hex(),
                "amount": event.args["amount"],
                "token": event.args["token"],
                "recepient": event.args["recipient"],
                "amount": event.args["amount"],
                "underlying_token": event.args["underlying_token"],
                "recipient": event.args["to"],  # Using 'to' for recipient
                "timestamp": datetime.fromtimestamp(w3.eth.get_block(event.blockNumber).timestamp)
            })
        if unwrap_events:
            handle_unwraps(unwrap_events, contract_info)

    df = pd.DataFrame(events_list)
    return df


def handle_deposits(events, contract_info="contract_info.json"):
    """
        Handle Deposit events by calling the wrap function on the destination chain.

        events: iterable of Deposit event logs (from contract.events.Deposit().get_logs)
    """
    w3_dest = connect_to('destination')
    contract_data_dest = get_contract_info('destination', contract_info)
    contract_address_dest = Web3.to_checksum_address(contract_data_dest['address'])
    contract_abi_dest = contract_data_dest['abi']
    contract_dest = w3_dest.eth.contract(address=contract_address_dest, abi=contract_abi_dest)

    # These are provided in the assignment starter code
    private_key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
    account_address = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    # IMPORTANT: manage nonce manually so multiple events don't reuse the same nonce
    nonce = w3_dest.eth.get_transaction_count(account_address)

    for ev in events:
        args = ev['args']
        tx = contract_dest.functions.wrap(
            args['token'],        # underlying ERC20 on source
            args['recipient'],    # destination recipient
            args['amount']        # amount
        ).build_transaction({
            'chainId': w3_dest.eth.chain_id,
            'gas': 2000000,
            'gasPrice': w3_dest.to_wei('5', 'gwei'),
            'nonce': nonce,
        })

        signed_tx = w3_dest.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = w3_dest.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Wrap transaction sent with hash: {tx_hash.hex()}")

        nonce += 1  # use a new nonce for the next event


def handle_unwraps(events, contract_info="contract_info.json"):
    """
        Handle Unwrap events by calling the withdraw function on the source chain.

        events: iterable of Unwrap event logs (from contract.events.Unwrap().get_logs)
    """
    w3_source = connect_to('source')
    contract_data_source = get_contract_info('source', contract_info)
    contract_address_source = Web3.to_checksum_address(contract_data_source['address'])
    contract_abi_source = contract_data_source['abi']
    contract_source = w3_source.eth.contract(address=contract_address_source, abi=contract_abi_source)

    private_key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
    account_address = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    # Again, manage nonce manually for multiple Unwrap events
    nonce = w3_source.eth.get_transaction_count(account_address)

    for ev in events:
        args = ev['args']
        # NOTE: field names come from Destination.json:
        # Unwrap(underlying_token, wrapped_token, to, amount)
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