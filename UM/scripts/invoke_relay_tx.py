import os
import sys
import base64
import pickle
from dotenv import load_dotenv
from algosdk import account, mnemonic
from algosdk.v2client import algod
from algosdk.future.transaction import *
from pyteal import compileTeal, Mode

load_dotenv("./.env")
p = os.environ.get("PROJECT_PATH")
sys.path.insert(0,p)

from assets.relay_lsig import *

m = os.environ.get("MNEMONIC") # This is YOUR address. Make sure it is funded with atleast 4Algo.
sk = mnemonic.to_private_key(m)
pk = account.address_from_private_key(sk)

# Node address and token.
algod_address = "http://localhost:4001" 
algod_token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

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
    # print("Account 3 address: {}".format(accounts[3]['pk']))

    return accounts

# Funding the Test adresses
def fund_accounts(algod_client, private_key, accounts, amount):
    params = algod_client.suggested_params()
    sender = account.address_from_private_key(private_key)

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

# create delegation
def create_lsig(algod_client, private_key, app_index):
    with open("./artifacts/relay_auth.lsig", "wb") as f:
        compiled = compileTeal(relay_auth(), Mode.Signature, version=6)
        response = algod_client.compile(compiled)

        # Create logic sig
        programstr = response['result']
        t = programstr.encode("ascii")
        program = base64.decodebytes(t)

        arg1 = (app_index).to_bytes(8, 'big')
        lsig = LogicSigAccount(program, args=[arg1])
        lsig.sign(private_key)

        pickle.dump(lsig, f, pickle.HIGHEST_PROTOCOL)

def call_app(client, lsig, index):
    # declare sender
    sender = lsig.address()
    print("Call from account:", sender)

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn = ApplicationNoOpTxn(sender=sender, sp=params, index=index)

    # sign transaction
    lstx = LogicSigTransaction(txn, lsig)

    drr = create_dryrun(client, [lstx])
    filename = "dryrun.msgp"
    with open(filename, "wb") as f:
        f.write(base64.b64decode(encoding.msgpack_encode(drr)))

    # send transaction
    tx_id = client.send_transaction(lstx)

    # await confirmation
    wait_for_confirmation(client, tx_id)

def main():
    # Initialize an algod client
    algod_client = algod.AlgodClient(algod_token=algod_token, algod_address=algod_address)
    app_id = 387
    accounts = generate_accounts(2)
    accounts_ = generate_accounts(2)
    fund_accounts(algod_client, sk, accounts, 1000000)
    create_lsig(algod_client, accounts[1]['sk'], app_id)

    with open('./artifacts/relay_auth.lsig', 'rb') as f:
        lsig = pickle.load(f)
        call_app(algod_client, lsig, app_id)

if __name__ == "__main__":
    main()
