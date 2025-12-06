from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware  # Necessary for POA chains
from datetime import datetime
import json
import pandas as pd


def connect_to(chain):
    if chain == 'source':  # The source contract chain is avax
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"  # AVAX C-chain testnet

    if chain == 'destination':  # The destination contract chain is bsc
        api_url = "https://data-seed-prebsc-1-s1.binance.org:8545/"  # BSC testnet

    if chain in ['source', 'destination']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        return w3

    # fall-through for invalid chain
    raise ValueError(f"Invalid chain: {chain}")


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

    # This is different from Bridge IV where chain was "avax" or "bsc"
    global df
    if chain not in ['source', 'destination']:
        print(f"This is an invalid chain!!!: {chain}")
        return 0

    w3 = connect_to(chain)
    contract_data = get_contract_info(chain, contract_info)
    contract_address = Web3.to_checksum_address(contract_data['address'])
    contract_abi = contract_data['abi']     # ABI is already a list, not a filename
    contract = w3.eth.contract(address=contract_address, abi=contract_abi)

    latest_block = w3.eth.block_number
    start_block = max(0, latest_block - 4)  # last 5 blocks

    events_list = []

    # Scan the last 5 blocks
    for block_num in range(start_block, latest_block + 1):
        block = w3.eth.get_block(block_num, full_transactions=True)

        for tx in block.transactions:
            receipt = w3.eth.get_transaction_receipt(tx.hash)

            # If chain is source, look for Deposit events
            if chain == 'source':
                deposit_events = contract.events.Deposit().process_receipt(receipt)
                for ev in deposit_events:
                    event_data = {
                        'event': 'Deposit',
                        'blockNumber': ev.blockNumber,
                        'transactionHash': ev.transactionHash.hex(),
                        'amount': ev.args['amount'],
                        'token': ev.args['token'],
                        'recipient': ev.args['recipient'],
                        'timestamp': datetime.fromtimestamp(block.timestamp),
                    }
                    events_list.append(event_data)

                    handle_deposits(ev, contract_info=contract_info)

            # If chain is destination, look for Unwrap events
            elif chain == 'destination':
                unwrap_events = contract.events.Unwrap().process_receipt(receipt)
                for ev in unwrap_events:
                    event_data = {
                        'event': 'Unwrap',
                        'blockNumber': ev.blockNumber,
                        'transactionHash': ev.transactionHash.hex(),
                        'amount': ev.args['amount'],
                        'token': ev.args['token'],
                        'recipient': ev.args['recipient'],
                        'timestamp': datetime.fromtimestamp(block.timestamp),
                    }
                    events_list.append(event_data)

                    handle_unwraps(ev, contract_info=contract_info)

    df = pd.DataFrame(events_list)
    return df


def handle_deposits(event, contract_info="contract_info.json"):
    """
        Handle Deposit events by calling the wrap function on the destination chain
    """
    w3_dest = connect_to('destination')
    contract_data_dest = get_contract_info('destination', contract_info)
    contract_address_dest = Web3.to_checksum_address(contract_data_dest['address'])
    contract_abi = contract_data_dest['abi']
    contract_dest = w3_dest.eth.contract(address=contract_address_dest, abi=contract_abi)

    private_key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
    account_address = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    nonce = w3_dest.eth.get_transaction_count(account_address)

    tx = contract_dest.functions.wrap(
        event.args['token'],
        event.args['recipient'],
        event.args['amount']
    ).build_transaction({
        'chainId': w3_dest.eth.chain_id,
        'gas': 2000000,
        'gasPrice': w3_dest.to_wei('5', 'gwei'),
        'nonce': nonce,
    })

    signed_tx = w3_dest.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3_dest.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Wrap transaction sent with hash: {tx_hash.hex()}")


def handle_unwraps(event, contract_info="contract_info.json"):
    """
        Handle Unwrap events by calling the withdraw function on the source chain
    """
    w3_source = connect_to('source')
    contract_data_source = get_contract_info('source', contract_info)
    contract_address_source = Web3.to_checksum_address(contract_data_source['address'])
    contract_abi = contract_data_source['abi']
    contract_source = w3_source.eth.contract(address=contract_address_source, abi=contract_abi)

    private_key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
    account_address = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    nonce = w3_source.eth.get_transaction_count(account_address)

    tx = contract_source.functions.withdraw(
        event.args['token'],
        event.args['recipient'],
        event.args['amount']
    ).build_transaction({
        'chainId': w3_source.eth.chain_id,
        'gas': 2000000,
        'gasPrice': w3_source.to_wei('5', 'gwei'),
        'nonce': nonce,
    })

    signed_tx = w3_source.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3_source.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Withdraw transaction sent with hash: {tx_hash.hex()}")