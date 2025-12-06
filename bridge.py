from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import json
import pandas as pd


# ------------------------------------------------------------
# CONNECT TO CHAINS
# ------------------------------------------------------------

# Connect to source or destination chain,
# im sure these links is the one i used to deploy, recheck later!!!!!!
def connect_to(chain):
    if chain == 'source':
        api_url = "https://api.avax-test.network/ext/bc/C/rpc"
    elif chain == 'destination':
        api_url = "https://bsc-testnet.publicnode.com"
    else:
        raise ValueError(f"Invalid chain")

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
    """
    Scan recent blocks for bridge events and handle them.
    :param chain: chain as w3 object, an api url string, either 'source' or 'destination'
    :param contract_info: as defined in json files
    :return: 0 if invalid chain, else DataFrame of events

    Will be fed to other handlers based on event type.
    1. On source chain, Deposit events → call wrap() on destination.
    2. On destination chain, Unwrap events → call withdraw() on source.
    3. Withdrawal and Wrap events are logged but require no action.
    4. Returns a DataFrame of all detected events.

    Tbh idk if this is the best way to do it but it works during tests :)
    """
    if chain not in ['source', 'destination']:
        return 0

    w3 = connect_to(chain)


    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to {chain} chain")

    # Get contract info, address and ABI, create contract object
    cdata = get_contract_info(chain, contract_info)
    contract_address = Web3.to_checksum_address(cdata['address'])
    contract = w3.eth.contract(address=contract_address, abi=cdata['abi']) # create contract object

    latest_block = w3.eth.block_number
    # Scan last N blocks for events, N = 20 for now
    from_block = max(latest_block - 20, 0) # Scan last 20 blocks, guide says 5 is enuf but i kept getting misses,
    to_block = latest_block

    events_list = []

    # Event signature topics, must add "0x" prefix somehow idk why w3.keccak docs not clear on this
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
    # SOURCE CHAIN, SOURCE OF DEPOSIT EVENTS, HANDLE THEM
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
            # In case of error (e.g. too many logs), return empty list,
            # might check ABI later....
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
            # call handle deposits to wrap on destination, see below
            handle_deposits(deposits, contract_info)

        try:
            # if there are withdrawal events, log them too,
            logs2 = w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": contract_address,
                "topics": [WITHDRAWAL_TOPIC]
            })
        except:
            # In case of error, return empty list
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
            #if there are withdrawal events, no action needed, just log, see below
            handle_withdrawals(withdrawals)

    # ------------------------------------------------------------
    # DESTINATION CHAIN, SOURCE OF UNWRAP EVENTS, HANDLE THEM
    # ------------------------------------------------------------
    else:
        #this block is for DESTINATIOn chain, so shd handle unwrap events to call withdraw on source

        try:

            logs = w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": contract_address,
                "topics": [UNWRAP_TOPIC]
            })
        except:
            logs = []

        # process unwrap events, log them, and call handle_unwraps to withdraw on source
        unwraps = []
        for log in logs:
            ev = contract.events.Unwrap().process_log(log)
            unwraps.append(ev)
            events_list.append({
                "event": "Unwrap",
                "block": ev.blockNumber,
                "underlying_token": ev.args["underlying_token"], # double check these arg names match the event ABI
                "wrapped_token": ev.args["wrapped_token"],
                "sender": ev.args["frm"],
                "to": ev.args["to"],
                "amount": ev.args["amount"],
                "tx": ev.transactionHash.hex(),
            })

        if unwraps:
            # call handle unwraps to withdraw on source, see below
            handle_unwraps(unwraps, contract_info)

        try:
            logs2 = w3.eth.get_logs({
                "fromBlock": from_block,
                "toBlock": to_block,
                "address": contract_address,
                "topics": [WRAP_TOPIC] # log wrap events too, check again emit events in contract.....
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
            # if there are wrap events, no action needed, just log, see below
            handle_wraps(wraps)

    return pd.DataFrame(events_list) # Return all detected events as a DataFrame,


# ------------------------------------------------------------
# HANDLE DEPOSITS --> CALL wrap() ON DESTINATION
# ------------------------------------------------------------
def handle_deposits(events, contract_info="contract_info.json"):
    """
    Handle Deposit events by calling wrap() on destination chain.
    1. Sort events by block number and log index to maintain order.
    2. For each event, extract token, recipient, and amount.
    3. Build and send wrap() transaction on destination chain.
    4. Print transaction hash for each wrap.
    5. Increment nonce for each transaction.
    6. Uses a predefined private key and sender address.
    :param events: event object
    :param contract_info:  as defined by json files
    :return:
    """
    w3 = connect_to("destination")
    cdata = get_contract_info("destination", contract_info)
    dest = w3.eth.contract(address=Web3.to_checksum_address(cdata["address"]), abi=cdata["abi"])

    key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16" # predefined private key, after this assignment ill delete my account...
    sender = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    nonce = w3.eth.get_transaction_count(sender) # get current nonce for sender, will increment for each tx

    for ev in sorted(events, key=lambda e: (e.blockNumber, e.logIndex)): #need to sort to maintain order, so that the nonce increments correctly
        token = ev.args["token"]
        recipient = ev.args["recipient"]
        amount = ev.args["amount"]

        tx = dest.functions.wrap(token, recipient, amount).build_transaction({
            "chainId": w3.eth.chain_id,
            "gas": 300000, # set gas limit
            "gasPrice": w3.to_wei("5", "gwei"),
            "nonce": nonce
        }) # build the wrap transaction, sign the nonce and gas params

        signed = w3.eth.account.sign_transaction(tx, key) # sign the transaction with the private key
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction) # send the signed transaction
        # print("Wrap:", tx_hash.hex()) # print the transaction hash
        nonce += 1 # increment nonce for next transaction


# ------------------------------------------------------------
# HANDLE UNWRAPS --> CALL withdraw() ON SOURCE
# ------------------------------------------------------------
def handle_unwraps(events, contract_info="contract_info.json"):
    """
    Handle Unwrap events by calling withdraw() on source chain.
    1. Sort events by block number and log index to maintain order.
    2. For each event, extract underlying_token, recipient, and amount.
    3. Build and send withdraw() transaction on source chain.
    4. Print transaction hash for each withdraw.
    5. Increment nonce for each transaction.
    6. Uses a predefined private key and sender address.

    :param events: events object
    :param contract_info: as defined by json files
    :return:
    """
    w3 = connect_to("source")

    cdata = get_contract_info("source", contract_info)
    src = w3.eth.contract(
        address=Web3.to_checksum_address(cdata["address"]),
        abi=cdata["abi"]
    )

    #again these key will be deleted after this assignment
    key = "0x6608bee2f462fa92b53bf52acb0ebfab6e8597ac618059d028f07b4f08023c16"
    sender = "0xB7131d4417d84025BAD139949D183398c2cf0916"

    nonce = w3.eth.get_transaction_count(sender)

    for ev in sorted(events, key=lambda e: (e.blockNumber, e.logIndex)): # sort to maintain order

        # MUST MATCH THE DESTINATION UNWRAP EVENT ABI, OTHERWISE THIS WILL FAIL
        # check again lol... why i kept failing brother.....
        underlying_token = ev.args["underlying_token"]
        recipient = ev.args["to"]
        amount = ev.args["amount"]

        # Build withdraw transaction, make sure params match the withdraw() function ABI
        # double check again lol...

        #boilerplate stuff, same as above but different signaturesss...
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

        # Sign and send transaction, print tx hash

        signed = w3.eth.account.sign_transaction(tx, key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        # print("Withdraw:", tx_hash.hex())

        nonce += 1


# ------------------------------------------------------------
# HANDLE WITHDRAWAL EVENTS --> NO ACTION NEEDED
# ------------------------------------------------------------
def handle_withdrawals(events):
    """FORMALITY CODE, NO ACTION NEEDED"""
    if not events:
        raise Exception("No events")
    return 0


# ------------------------------------------------------------
# HANDLE WRAP EVENTS --> NO ACTION NEEDED
# ------------------------------------------------------------
def handle_wraps(events):
    """FORMALITY CODE, NO ACTION NEEDED"""
    if not events:
        raise Exception("No events")
    return 0
