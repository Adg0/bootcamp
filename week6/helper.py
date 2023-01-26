import os
import json
import base64
from dotenv import load_dotenv
from algosdk import account, mnemonic
from algosdk.v2client import algod
from algosdk.future import transaction
from algosdk.future.transaction import *
from pyteal import compileTeal, Mode
from contract import approval_program, clear_state_program

# Security(protecting private key)
load_dotenv("../.env")

# Funding Account
m = os.environ.get("MNEMONIC") # This is YOUR address. Make sure it is funded with atleast 4Algo.
sk = mnemonic.to_private_key(m)
pk = account.address_from_private_key(sk)

# Node address and token.
algod_address = "https://testnet-api.algonode.cloud" #"http://localhost:4001" 
algod_token = "" #"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

# Generating testing accounts
def generate_accounts(number_of_accounts):
    mn = []
    for i in range(number_of_accounts):
        acct = account.generate_account()
        mn.append(mnemonic.from_private_key(acct[0]))

    accounts = {}
    counter = 1
    for m in mn:
        accounts[counter] = {}
        accounts[counter]['sk'] = mnemonic.to_private_key(m)
        accounts[counter]['pk'] = account.address_from_private_key(accounts[counter]['sk'])
        counter += 1

    print("Account 1 address: {}".format(accounts[1]['pk']))
    print("Account 2 address: {}".format(accounts[2]['pk']))
    print("Account 3 address: {}".format(accounts[3]['pk']))

    return accounts

# Funding the Test adresses
def fund_accounts(algod_client, private_key, accounts, amount):
    params = algod_client.suggested_params()
    sender = account.address_from_private_key(private_key)
    note = "Funding test accounts".encode()

    # create transactions
    txns = []
    stxn = []
    for i in accounts:
        txns.append(PaymentTxn(sender, params, accounts[i]['pk'], amount))

    # compute group id and put it into each transaction
    group_id = calculate_group_id(txns)

    for i in accounts:
        txns[i-1].group = group_id
        # sign transactions
        stxn.append(txns[i-1].sign(private_key))

    # send transactions
    txid = algod_client.send_transactions(stxn)

    # wait for confirmation	
    wait_for_confirmation(algod_client, txid)

    for i in accounts:
        # get balance
        account_info = algod_client.account_info(accounts[i]['pk'])
        print("{}: {} microAlgos".format(accounts[i]['pk'], account_info.get('amount')))

#   Utility function used to print created asset for account and assetid
def print_created_asset(algodclient, account, assetid):    
    account_info = algodclient.account_info(account)
    idx = 0;
    for my_account_info in account_info['created-assets']:
        scrutinized_asset = account_info['created-assets'][idx]
        idx = idx + 1       
        if (scrutinized_asset['index'] == assetid):
            print("Asset ID: {}".format(scrutinized_asset['index']))
            print(json.dumps(my_account_info['params'], indent=4))
            break

#   Utility function used to print asset holding for account and assetid
def print_asset_holding(algodclient, account, assetid):
    account_info = algodclient.account_info(account)
    idx = 0
    for my_account_info in account_info['assets']:
        scrutinized_asset = account_info['assets'][idx]
        idx = idx + 1        
        if (scrutinized_asset['asset-id'] == assetid):
            print("Asset ID: {}".format(scrutinized_asset['asset-id']))
            print(json.dumps(scrutinized_asset, indent=4))
            break

# CREATE ASSET
def create_asa(algod_client, private_key, total, name, other):
    params = algod_client.suggested_params()
    sender = account.address_from_private_key(private_key)

    # Asset Creation transaction
    txn = AssetConfigTxn(
        sender=sender,
        sp=params,
        total=total,
        default_frozen=False,
        unit_name=name,
        asset_name="ENB",
        manager=sender,
        reserve=sender,
        freeze=other,
        clawback=other,
        url="https://bootcamp.assignment.com", 
        decimals=0,
    )
    # Sign with secret key of creator
    stxn = txn.sign(private_key)

    # Send the transaction to the network.
    txid = algod_client.send_transactions([stxn])
    # Wait for the transaction to be confirmed
    wait_for_confirmation(algod_client, txid)

    # Get the new asset's information from the creator account
    ptx = algod_client.pending_transaction_info(txid)
    asset_id = ptx["asset-index"]
    print_created_asset(algod_client, sender, asset_id)

    return asset_id

# OPT-IN
def optin_asa(algod_client, private_key, asset_id):
    params = algod_client.suggested_params()
    addr = account.address_from_private_key(private_key)
    account_info = algod_client.account_info(addr)
    holding = None
    idx = 0
    for my_account_info in account_info['assets']:
        scrutinized_asset = account_info['assets'][idx]
        idx = idx + 1    
        if (scrutinized_asset['asset-id'] == asset_id):
            holding = True
            break

    if not holding:
        # Use the AssetTransferTxn class to transfer assets and opt-in
        txn = AssetTransferTxn(
            sender=addr,
            sp=params,
            receiver=addr,
            amt=0,
            index=asset_id)
        stxn = txn.sign(private_key)
        # Send the transaction to the network.
        txid = algod_client.send_transactions([stxn])
        # Wait for the transaction to be confirmed
        wait_for_confirmation(algod_client, txid)

# TRANSFER ASSET
def transfer_asa(algod_client, private_key, receiver, amount, asset_id):
    params = algod_client.suggested_params()
    sender = account.address_from_private_key(private_key)
    txn = AssetTransferTxn(
        sender=sender,
        sp=params,
        receiver=receiver,
        amt=amount,
        index=asset_id,
    )
    stxn = txn.sign(private_key)
    # Send the transaction to the network.
    txid = algod_client.send_transactions([stxn])
    # Wait for the transaction to be confirmed
    wait_for_confirmation(algod_client, txid) 
    print_asset_holding(algod_client, receiver, asset_id)

# Delete ASA
def delete_asa(algod_client, private_key, asset_id):
    params = algod_client.suggested_params()
    sender = account.address_from_private_key(private_key)
    print("Deleting ASA: ", asset_id)

    # Asset destroy transaction
    txn = AssetConfigTxn(
        sender=sender,
        sp=params,
        index=asset_id,
        strict_empty_address_check=False,
    )

    # Sign with secret key of creator
    stxn = txn.sign(private_key)
    # Send the transaction to the network.
    txid = algod_client.send_transactions([stxn])
    # Wait for the transaction to be confirmed
    wait_for_confirmation(algod_client, txid) 

# Close remaining asa
def close_asa(algod_client, to, private_key, asset_id):
    params = algod_client.suggested_params()
    sender = account.address_from_private_key(private_key)
    print("{} Opting Out from ASA: {}".format(sender, asset_id))

    # Close account with a close_assets_to to the creator account, to clear it from its accountholdings
    txn = AssetTransferTxn(
        sender=sender,
        sp=params,
        receiver=to,
        amt=0,
        index=asset_id,
        close_assets_to=to,
        )
    stxn = txn.sign(private_key)
    # Send the transaction to the network.
    txid = algod_client.send_transactions([stxn])
    # Wait for the transaction to be confirmed
    wait_for_confirmation(algod_client, txid)

# Return remaining funds
def return_fund(algod_client, to, accounts):
    params = algod_client.suggested_params()
    note = "Closing test account".encode()
    for i in accounts:
        # get balance
        account_info = algod_client.account_info(accounts[i]['pk'])
        print("{}: returning {} microAlgos".format(accounts[i]['pk'], account_info.get('amount')))

        unsigned_txn = PaymentTxn(accounts[i]['pk'], params, to, 0, to, note)

        # sign transaction
        signed_txn = unsigned_txn.sign(accounts[i]['sk'])
        txid = algod_client.send_transactions([signed_txn])

        # wait for confirmation	
        wait_for_confirmation(algod_client, txid)

# helper function to compile program source
def compile_program(client, source_code):
    compile_response = client.compile(source_code)
    return base64.b64decode(compile_response["result"])

def wait_for_round(client, round):
    last_round = client.status().get("last-round")
    print(f"Waiting for round {round}")
    while last_round < round:
        last_round += 1
        client.status_after_block(last_round)
        print(f"Round {last_round}")


# create new application
def create_app(
    client,
    private_key,
    approval_program,
    clear_program,
    global_schema,
    local_schema,
    app_args,
):
    # define sender as creator
    sender = account.address_from_private_key(private_key)

    # declare on_complete as NoOp
    on_complete = OnComplete.NoOpOC.real

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = ApplicationCreateTxn(
        sender,
        params,
        on_complete,
        approval_program,
        clear_program,
        global_schema,
        local_schema,
        app_args,
    )

    # sign transaction
    signed_txn = txn.sign(private_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id)

    # display results
    transaction_response = client.pending_transaction_info(tx_id)
    app_id = transaction_response["application-index"]
    print("Created new app-id:", app_id)

    return app_id


# opt-in to application
def opt_in_app(client, private_key, index):
    # declare sender
    sender = account.address_from_private_key(private_key)
    print("OptIn from account: ", sender)

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = ApplicationOptInTxn(sender, params, index)

    # sign transaction
    signed_txn = txn.sign(private_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id)

    # display results
    transaction_response = client.pending_transaction_info(tx_id)
    print("OptIn to app-id:", transaction_response["txn"]["txn"]["apid"])


# call application
def call_app(client, private_key, index, app_args, accounts, foreign_assets):
    # declare sender
    sender = account.address_from_private_key(private_key)
    print("Call from account:", sender)

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = ApplicationNoOpTxn(sender=sender, sp=params, index=index, app_args=app_args, accounts=accounts, foreign_assets=foreign_assets)

    # sign transaction
    signed_txn = txn.sign(private_key)
    drr = create_dryrun(client, [signed_txn])
    filename = "dryrun.msgp"
    with open(filename, "wb") as f:
        f.write(base64.b64decode(encoding.msgpack_encode(drr)))
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id)


def format_state(state):
    formatted = {}
    for item in state:
        key = item["key"]
        value = item["value"]
        formatted_key = base64.b64decode(key).decode("utf-8")
        if value["type"] == 1:
            # byte string
            if formatted_key == "voted":
                formatted_value = base64.b64decode(value["bytes"]).decode("utf-8")
            else:
                formatted_value = value["bytes"]
            formatted[formatted_key] = formatted_value
        else:
            # integer
            formatted[formatted_key] = value["uint"]
    return formatted


# read user local state
def read_local_state(client, addr, app_id):
    results = client.account_info(addr)
    for local_state in results["apps-local-state"]:
        if local_state["id"] == app_id:
            if "key-value" not in local_state:
                return {}
            return format_state(local_state["key-value"])
    return {}


# read app global state
def read_global_state(client, addr, app_id):
    results = client.account_info(addr)
    apps_created = results["created-apps"]
    for app in apps_created:
        if app["id"] == app_id:
            return format_state(app["params"]["global-state"])
    return {}


# delete application
def delete_app(client, private_key, index):
    # declare sender
    sender = account.address_from_private_key(private_key)

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = ApplicationDeleteTxn(sender, params, index)

    # sign transaction
    signed_txn = txn.sign(private_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id)

    # display results
    transaction_response = client.pending_transaction_info(tx_id)
    print("Deleted app-id:", transaction_response["txn"]["txn"]["apid"])


# close out from application
def close_out_app(client, private_key, index):
    # declare sender
    sender = account.address_from_private_key(private_key)

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = ApplicationCloseOutTxn(sender, params, index)

    # sign transaction
    signed_txn = txn.sign(private_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id)

    # display results
    transaction_response = client.pending_transaction_info(tx_id)
    print("Closed out from app-id: ", transaction_response["txn"]["txn"]["apid"])


# clear application
def clear_app(client, private_key, index):
    # declare sender
    sender = account.address_from_private_key(private_key)

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = ApplicationClearStateTxn(sender, params, index)

    # sign transaction
    signed_txn = txn.sign(private_key)
    tx_id = signed_txn.transaction.get_txid()

    # send transaction
    client.send_transactions([signed_txn])

    # await confirmation
    wait_for_confirmation(client, tx_id)

    # display results
    transaction_response = client.pending_transaction_info(tx_id)
    print("Cleared app-id:", transaction_response["txn"]["txn"]["apid"])


# convert 64 bit integer i to byte string
def intToBytes(i):
    return i.to_bytes(8, "big")

# Assignment execution
def main():
    # Initialize an algod client
    algod_client = algod.AlgodClient(algod_token=algod_token, algod_address=algod_address)

    # Create testing accounts
    print("Generating Test Accounts:")
    accounts = generate_accounts(3)

    # Fund testing accounts with 1-Algo each
    print("\nFunding Test Accounts:")
    fund_accounts(algod_client, sk, accounts, 1000000)

    # Create ENB
    print("\nCreating ENB ASA")
    asset_id = create_asa(algod_client, accounts[1]['sk'], 1000000, "ENB", accounts[2]['pk'])

    # Optin to ENB
    print("\nAccounts Optin To ENB:")
    optin_asa(algod_client, accounts[2]['sk'], asset_id)
    optin_asa(algod_client, accounts[3]['sk'], asset_id)

    # Transfer ENB
    print("\nTransfer ENB to Accounts")
    transfer_asa(algod_client, accounts[1]['sk'], accounts[2]['pk'], 2000, asset_id)
    transfer_asa(algod_client, accounts[1]['sk'], accounts[3]['pk'], 1001, asset_id)

    # Create App
    print("\nCreating Voting App")
    local_ints = 1 # to register balance when vote submitted
    local_bytes = 1
    global_ints = 8 # 5 for setup and 3 for choice
    global_bytes = 1
    global_schema = StateSchema(global_ints, global_bytes)
    local_schema = StateSchema(local_ints, local_bytes)

    # get PyTeal approval program
    approval_program_ast = approval_program()
    # compile program to TEAL assembly
    approval_program_teal = compileTeal(
        approval_program_ast, mode=Mode.Application, version=6
    )
    # compile program to binary
    approval_program_compiled = compile_program(algod_client, approval_program_teal)

    # get PyTeal clear state program
    clear_state_program_ast = clear_state_program()
    # compile program to TEAL assembly
    clear_state_program_teal = compileTeal(
        clear_state_program_ast, mode=Mode.Application, version=6
    )
    # compile program to binary
    clear_state_program_compiled = compile_program(
        algod_client, clear_state_program_teal
    )

    # configure registration and voting period
    status = algod_client.status()
    regBegin = status["last-round"] + 10
    regEnd = regBegin + 10
    voteBegin = regEnd + 1
    voteEnd = voteBegin + 10

    print(f"Registration rounds: {regBegin} to {regEnd}")
    print(f"Vote rounds: {voteBegin} to {voteEnd}")

    # create list of bytes for app args
    app_args = [
        intToBytes(regBegin),
        intToBytes(regEnd),
        intToBytes(voteBegin),
        intToBytes(voteEnd),
        intToBytes(asset_id),
    ]

    # create new application
    app_id = create_app(
        algod_client,
        accounts[1]['sk'],
        approval_program_compiled,
        clear_state_program_compiled,
        global_schema,
        local_schema,
        app_args,
    )

    # read global state of application
    print("Global state:", read_global_state(algod_client, accounts[1]['pk'], app_id))

    # wait for registration period to start
    wait_for_round(algod_client, regBegin)

    # opt-in to application
    print("\nAccounts optin to Voting App")
    opt_in_app(algod_client, accounts[2]['sk'], app_id)
    opt_in_app(algod_client, accounts[3]['sk'], app_id)

    wait_for_round(algod_client, voteBegin)

    # call application without arguments
    print("\nAccounts Vote")
    call_app(algod_client, accounts[2]['sk'], app_id, [b"vote", b"yes"], [accounts[2]['pk']], [asset_id])
    call_app(algod_client, accounts[3]['sk'], app_id, [b"vote", b"no"], [accounts[3]['pk']], [asset_id])

    # read local state of application from user account
    print("Local state:", read_local_state(algod_client, accounts[2]['pk'], app_id))
    print("Local state:", read_local_state(algod_client, accounts[3]['pk'], app_id))

    # wait for registration period to start
    wait_for_round(algod_client, voteEnd)

    # read global state of application
    print("\nVote Ended")
    global_state = read_global_state(algod_client, accounts[1]['pk'], app_id)
    print("Global state:", global_state)

    max_votes = 0
    max_votes_choice = None
    for key, value in global_state.items():
        if key not in (
            "RegBegin",
            "RegEnd",
            "VoteBegin",
            "VoteEnd",
            "Creator",
            "AssetID",
        ) and isinstance(value, int):
            if value > max_votes:
                max_votes = value
                max_votes_choice = key

    print("The winner is:", max_votes_choice)

    print("\nCleaning Test Environment")
    # delete application
    delete_app(algod_client, accounts[1]['sk'], app_id)

    # clear application from user account
    clear_app(algod_client, accounts[2]['sk'], app_id)
    clear_app(algod_client, accounts[3]['sk'], app_id)

    # clear ENB holdings
    close_asa(algod_client, accounts[1]['pk'], accounts[2]['sk'], asset_id)
    close_asa(algod_client, accounts[1]['pk'], accounts[3]['sk'], asset_id)

    # delete ENB
    delete_asa(algod_client, accounts[1]['sk'], asset_id)

    # return remaining funds
    return_fund(algod_client, pk, accounts)

    print("****FINISHED****")

if __name__ == "__main__":
    main()
