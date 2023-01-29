import base64
import pickle
from dotenv import load_dotenv
from hashlib import sha256
from algosdk import account, mnemonic, logic
from algosdk.v2client import algod
from algosdk.future.transaction import *
from utils import *

# depositing function
def make_deposit(client, private_key, index, app_args, boxes, amount):
    # declare sender
    sender = account.address_from_private_key(private_key)
    app_addr = logic.get_application_address(index)
    print("Deposit from account:", sender)

    # get node suggested parameters
    params = client.suggested_params()

    # create unsigned transaction
    txn_0 = PaymentTxn(sender=sender, sp=params, receiver=app_addr, amt=amount)
    txn = ApplicationNoOpTxn(sender=sender, sp=params, index=index, app_args=app_args, boxes=boxes)
    group_id = calculate_group_id([txn_0,txn])
    txn_0.group = group_id
    txn.group = group_id

    # sign transaction
    stxn = []
    stxn.append(txn_0.sign(private_key))
    stxn.append(txn.sign(private_key))

    drr = create_dryrun(client, stxn)
    filename = "dryrun.msgp"
    with open(filename, "wb") as f:
        f.write(base64.b64decode(encoding.msgpack_encode(drr)))

    # send transaction
    tx_id = client.send_transactions(stxn)

    # await confirmation
    wait_for_confirmation(client, tx_id)

def main():
    # Initialize an algod client
    algod_client = algod.AlgodClient(algod_token=algod_token, algod_address=algod_address)
    app_id = 395
    amount = 5000000
    nullifier = "20304050"
    secret = "passKey"
    s_n = secret + nullifier
    h = sha256(s_n.encode('utf-8')).hexdigest()
    print(s_n)
    print(h)
    make_deposit(algod_client, sk, app_id, [b"deposit",h.encode('utf-8')], [[app_id,"5algo"]], amount)
    print("Made a deposit")

if __name__ == "__main__":
    main()
