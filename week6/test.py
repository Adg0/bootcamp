from helper import *
from algosdk.future import transaction
from algosdk import account, mnemonic
from algosdk.v2client import algod, indexer
from dotenv import load_dotenv
import os
import unittest

# Security(protecting private key)
load_dotenv("../.env")

algod_address = "https://testnet-api.algonode.cloud" #"http://localhost:4001" # 
algod_token = "" # "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
indexer_address = "https://testnet-idx.algonode.cloud" #"http://localhost:8980"

# user declared account mnemonics
funding_mnemonic = os.environ.get("MNEMONIC") # This is YOUR address. Make sure it is funded with atleast 4Algo.

unittest.TestLoader.sortTestMethodsUsing = None

class TestContract(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        cls.algod_client = algod.AlgodClient(algod_token, algod_address)
        cls.algod_indexer = indexer.IndexerClient("", indexer_address)
        cls.funding_sk  = mnemonic.to_private_key(funding_mnemonic)
        cls.accounts = generate_accounts(3)
        cls.app_index = 0
        cls.asset_id = 0
    
    #Methods for test cases must start with test
    def test_1_fund(self):
        amt = 1000000
        fund_accounts(TestContract.algod_client, TestContract.funding_sk, TestContract.accounts, amt)    

        print("Funded {amt} to new accounts for the purpose of deploying contract".format(amt = amt))
        
        response = TestContract.algod_indexer.account_info(address=TestContract.accounts[1]['pk'])
        balance = response['account']['amount']
        self.assertGreaterEqual(balance, amt)

    def test_2_create_asa(self):
        TestContract.asset_id = create_asa(TestContract.algod_client, TestContract.accounts[1]['sk'], 1000000, "ENB", TestContract.accounts[2]['pk'])
        response_created = TestContract.algod_indexer.search_assets(creator=TestContract.accounts[1]['pk'],asset_id=TestContract.asset_id)
        self.assertNotEqual(response_created['assets'], [], "Creator account is not creator of ASA or ASA not created at all.")
        self.assertEqual(response_created['assets'][0]['params']['unit-name'], 'ENB', "ASA unit name is wrong.")

    def test_3_optin_asa(self):
        optin_asa(TestContract.algod_client, TestContract.accounts[2]['sk'], TestContract.asset_id)
        optin_asa(TestContract.algod_client, TestContract.accounts[3]['sk'], TestContract.asset_id)

    def test_4_transfer_asa(self):
        amt_2 = 2000
        amt_3 = 1001
        transfer_asa(TestContract.algod_client, TestContract.accounts[1]['sk'], TestContract.accounts[2]['pk'], amt_2, TestContract.asset_id)
        transfer_asa(TestContract.algod_client, TestContract.accounts[1]['sk'], TestContract.accounts[3]['pk'], amt_3, TestContract.asset_id)
        balances = TestContract.algod_indexer.asset_balances(TestContract.asset_id)
        for b in balances["balances"]:
            if b['address'] == TestContract.accounts[2]['pk']:
                self.assertGreaterEqual(b['amount'], amt_2, "Send failed account has wrong ASA balance")
            if b['address'] == TestContract.accounts[3]['pk']:
                self.assertGreaterEqual(b['amount'], amt_3, "Send failed account has wrong ASA balance")

    #Methods for test cases must start with test
    def test_5_deploy_app(self):      
        # declare application state storage (immutable)
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
        approval_program_compiled = compile_program(TestContract.algod_client, approval_program_teal)

        # get PyTeal clear state program
        clear_state_program_ast = clear_state_program()
        # compile program to TEAL assembly
        clear_state_program_teal = compileTeal(
            clear_state_program_ast, mode=Mode.Application, version=6
        )
        # compile program to binary
        clear_state_program_compiled = compile_program( TestContract.algod_client, clear_state_program_teal)

        # configure registration and voting period
        status = TestContract.algod_client.status()
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
            intToBytes(TestContract.asset_id),
        ]
            
        # create new application
        TestContract.app_index = create_app(
            TestContract.algod_client,
            TestContract.accounts[1]['sk'],
            approval_program_compiled,
            clear_state_program_compiled,
            global_schema,
            local_schema,
            app_args,
        )

        print("Deployed new app with APP ID: "+str(TestContract.app_index))

        global_state = read_global_state(TestContract.algod_client, TestContract.accounts[1]['pk'], TestContract.app_index)
        self.assertEqual(encoding.encode_address(base64.b64decode(global_state['Creator'])), TestContract.accounts[1]['pk'], "Wrong creator in global storage")
        self.assertEqual(global_state['RegBegin'], regBegin, "Registration start is incorrect.")
        self.assertEqual(global_state['RegEnd'], regEnd, "Registration end is incorrect.")
        self.assertEqual(global_state['VoteBegin'], voteBegin, "Vote start is incorrect.")
        self.assertEqual(global_state['VoteEnd'], voteEnd, "Vote end is incorrect.")
        self.assertEqual(global_state['AssetID'], TestContract.asset_id, "ENB stored is incorrect.")

    def test_6_optin_app(self):
        global_state = read_global_state(TestContract.algod_client, TestContract.accounts[1]['pk'], TestContract.app_index)
        # Wait for registration round to begin
        wait_for_round(TestContract.algod_client, global_state['RegBegin'])

        opt_in_app(TestContract.algod_client, TestContract.accounts[2]['sk'], TestContract.app_index)
        opt_in_app(TestContract.algod_client, TestContract.accounts[3]['sk'], TestContract.app_index)
        local_state_2 = TestContract.algod_indexer.lookup_account_application_local_state(application_id=TestContract.app_index,address=TestContract.accounts[2]['pk'])
        local_state_3 = TestContract.algod_indexer.lookup_account_application_local_state(application_id=TestContract.app_index,address=TestContract.accounts[3]['pk'])
        self.assertIsNotNone(local_state_2['apps-local-states'][0],"Account is opting in, local state should exist")
        self.assertIsNotNone(local_state_3['apps-local-states'][0],"Account is opting in, local state should exist")

    def test_7_vote(self):
        global_state = read_global_state(TestContract.algod_client, TestContract.accounts[1]['pk'], TestContract.app_index)

        # Wait for voting round to begin
        wait_for_round(TestContract.algod_client, global_state['VoteBegin'])

        call_app(TestContract.algod_client, TestContract.accounts[2]['sk'], TestContract.app_index, [b"vote", b"yes"], [TestContract.accounts[2]['pk']], [TestContract.asset_id])
        call_app(TestContract.algod_client, TestContract.accounts[3]['sk'], TestContract.app_index, [b"vote", b"no"], [TestContract.accounts[3]['pk']], [TestContract.asset_id])
        balances = TestContract.algod_indexer.asset_balances(TestContract.asset_id)
        local_state_2 = read_local_state(TestContract.algod_client,TestContract.accounts[2]['pk'],TestContract.app_index)
        local_state_3 = read_local_state(TestContract.algod_client,TestContract.accounts[3]['pk'],TestContract.app_index)
        self.assertEqual(local_state_2['voted'], "yes")
        self.assertEqual(local_state_3['voted'], "no")
        for b in balances["balances"]:
            if b['address'] == TestContract.accounts[2]['pk']:
                self.assertEqual(local_state_2['ENB'], b['amount'])
            if b['address'] == TestContract.accounts[3]['pk']:
                self.assertEqual(local_state_3['ENB'], b['amount'])
        
        global_state = read_global_state(TestContract.algod_client, TestContract.accounts[1]['pk'], TestContract.app_index)
        print(global_state)
        self.assertEqual(global_state["yes"], local_state_2['ENB'])
        self.assertEqual(global_state["no"], local_state_3['ENB'])

    def test_8_win(self):
        global_state = read_global_state(TestContract.algod_client, TestContract.accounts[1]['pk'], TestContract.app_index)
        # Wait for voting round to end
        wait_for_round(TestContract.algod_client, global_state['VoteEnd'])

        global_state = read_global_state(TestContract.algod_client, TestContract.accounts[1]['pk'], TestContract.app_index)
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
        
        self.assertGreater(global_state[max_votes_choice], global_state['no'])
        #self.assertGreater(global_state[max_votes_choice], global_state['abstain'])
    
    def test_9_0_clear_app(self):
        #global_state_before = read_global_state(TestContract.algod_client, TestContract.accounts[1]['pk'], TestContract.app_index)
        clear_app(TestContract.algod_client, TestContract.accounts[2]['sk'], TestContract.app_index)
        clear_app(TestContract.algod_client, TestContract.accounts[3]['sk'], TestContract.app_index)
        local_state_2 = TestContract.algod_indexer.lookup_account_application_local_state(application_id=TestContract.app_index,address=TestContract.accounts[2]['pk'])
        local_state_3 = TestContract.algod_indexer.lookup_account_application_local_state(application_id=TestContract.app_index,address=TestContract.accounts[3]['pk'])
        self.assertEqual(local_state_2['apps-local-states'], [])
        self.assertEqual(local_state_3['apps-local-states'], [])

        global_state_after = read_global_state(TestContract.algod_client, TestContract.accounts[1]['pk'], TestContract.app_index)
        print(global_state_after)
        # self.assertLess(global_state_after['yes'], global_state_before['yes'])
        # self.assertLess(global_state_after['no'], global_state_before['no'])

    def test_9_1_delete_app(self):
        delete_app(TestContract.algod_client, TestContract.accounts[1]['sk'], TestContract.app_index)
        response = TestContract.algod_indexer.applications(application_id=TestContract.app_index,include_all=True)
        self.assertTrue(response['application']['deleted'])

    def test_9_2_close_asa(self):
        close_asa(TestContract.algod_client, TestContract.accounts[1]['pk'], TestContract.accounts[2]['sk'], TestContract.asset_id)
        close_asa(TestContract.algod_client, TestContract.accounts[1]['pk'], TestContract.accounts[3]['sk'], TestContract.asset_id)
        balances = TestContract.algod_indexer.asset_balances(TestContract.asset_id)
        for b in balances["balances"]:
            if b['address'] == TestContract.accounts[2]['pk']:
                self.assertEqual(b['amount'], 0, "ASA balance still exists")
            if b['address'] == TestContract.accounts[3]['pk']:
                self.assertEqual(b['amount'], 0, "ASA balance still exists")
    
    def test_9_3_delete_asa(self):
        delete_asa(TestContract.algod_client, TestContract.accounts[1]['sk'], TestContract.asset_id)

    def test_9_4_return_fund(self):
        addr = account.address_from_private_key(TestContract.funding_sk)
        return_fund(TestContract.algod_client, addr, TestContract.accounts)
        response = TestContract.algod_indexer.account_info(address=addr)
        balance = response['account']['amount']
        self.assertGreater(balance, 1000000)

def tearDownClass(self) -> None:
    return super().tearDown()

if __name__ == '__main__':
    unittest.main()
