import transaction
import formatter
import random
import time
import socket

class Wallet:
    def __init__(self, owner: str):
        self.owner = owner
        # List of transactions with the owner as the destination
        self.tx_received = []

        # This is for that loop of a wallet
        self.running = False # Variable to control whether the wallet/loop is active

        # My socket to the miner kept closing, so if I add this the miner connection stayed up
        self.miner_socket = None
        self.connected_miner = None

    def add_transaction(self, transaction: transaction.Transaction):
        """Function that adds transactions where owner is receiver"""
        if transaction.receiver == self.owner:
            self.tx_received.append(transaction)

    def wallet_balance(self):
        """Function to get the total of the received amount"""
        balance = 0
        for tx in self.tx_received:
            balance += float(tx.amount)
        return balance
    
    def see_all_transactions(self):
        """
        Implementing (i) of Task 3
        Show all transactions where the owner is the receiver
        """
        if not self.tx_received:
            print(f"\n[Wallet {self.owner}] You have no received transactions!!!")
        else:
            print(f"\n[Wallet {self.owner}] Number of unspent tx: {len(self.tx_received)}")
            print(f"[Wallet {self.owner}] List of UTXOs:")
            for tx in self.tx_received:
                print(f"\tID: {tx.transaction_id}, Sender: {tx.sender}, Amount: {tx.amount}")
            print(f"Total balance of transactions: {self.wallet_balance()}")

    def select_sufficient_transactions(self, amount: float | int, fee: float | int):
        """
        Still continuing (i) of Task 3
        This is where they have accepted to send a transaction to another owner and must select transactions
        """
        amount = float(amount)
        fee = float(fee)
        cost = amount + fee

        # I am asked to select transactions that cover the cost of the transaction (the wallet does this automatically)
        cost_covering_tx = []
        funds = 0

        # Getting self.tx_received, however I cannot do this without it being sorted largest to smalled amount
        available_tx = sorted(self.tx_received, key=lambda x: float(x.amount), reverse=True)
        
        # Starting from the biggest, and moving sequentially until the smallest
        # Select pre-existing tx until we cover the cost of the transaction we want to send
        for tx in available_tx:
            if funds >= cost:
                break
            cost_covering_tx.append(tx)
            funds += float(tx.amount)

        # Error handle if it doesnt have enough funds
        if funds < cost:
            print(f"[Wallet {self.owner}] ERROR - Insufficient funds!!!")
            print(f"\tRequired: {cost}")
            print(f"\tAvailable: {self.wallet_balance()}")
            return None
        
        # Now I have to remove these transactions from the wallet
        for tx in cost_covering_tx:
            self.tx_received.remove(tx)

        print(f"[Wallet {self.owner}] {len(cost_covering_tx)} transaction(s) selected, adding up to {funds}")

        return cost_covering_tx
    
    def wallet_loop(self):
        """
        In order to do task 3, I need a loop running
        Each loop will be in a thread, I presume the loop is constantly running for each wallet
        """
        print(f"[Wallet {self.owner}] Threaded loop starting")

        # When the loop starts
        while self.running:
            # Show them all transactions
            self.see_all_transactions()
            # Then let them decide
            reply = input(f"\n[Wallet {self.owner}] Would you like to send a transaction to another owner [yes/no/exit]?\n")
            reply = reply.strip().lower()

            # Part (i) - to send to an owner
            if reply == "yes":
                # collate information on transaction - receivee, amount and fee
                try:
                    input_receiver = str(input(f"\n[Wallet {self.owner}] Who are you going to send it to?\n")).strip()
                    input_amount = float(input(f"\n[Wallet {self.owner}] What amount are you going to send?\n").strip())
                    input_fee = float(input(f"\n[Wallet {self.owner}] What fee amount are you willing to spend?\n").strip()) 
                except ValueError:
                    print(f"[Wallet {self.owner}] ERROR - Enter in valid numbers for amount and fee")
                    continue
                except Exception as e:
                    print(f"[Wallet {self.owner}] ERROR - {e}")
                    continue

                # select the transactions to make up cost
                selected_transactions = self.select_sufficient_transactions(input_amount, input_fee)

                if selected_transactions != None:
                    new_transaction = transaction.Transaction(self.owner, input_receiver, input_amount, input_fee)
                    print(f"\n[Wallet {self.owner}] Transaction {new_transaction.transaction_id} created!!!")
                    print(f"\tSender: {new_transaction.sender}")
                    print(f"\tReceiver: {new_transaction.receiver}")
                    print(f"\tAmount: {new_transaction.amount}")
                    print(f"\tFee: {new_transaction.fee}")

                    total_input = sum(float(tx.amount) for tx in selected_transactions)
                    change = total_input - input_amount - input_fee
                    
                    if change > 0:
                        change_tx = transaction.Transaction(self.owner, self.owner, change, fee=0)
                        self.add_transaction(change_tx)
                        print(f"\n[Wallet {self.owner}] Change of {change} coins returned back")

                    # Now you send the transaction from the wallet to the miner you randomly connected to
                    if self.miner_socket:
                        try:
                            transaction_message = f"Transaction: {new_transaction.sender}, {new_transaction.receiver}, {new_transaction.amount}, {new_transaction.fee}, {new_transaction.transaction_id}"

                            # Using the function send the string converted to the miner socket address
                            formatter.send_line(self.miner_socket, transaction_message)

                            print(f"\n[Wallet {self.owner}] Sent transaction to miner {self.connected_miner['miner']}")
                        except Exception as e:
                            print(f"[Wallet {self.owner} Error in sending transaction - {e}]")
                    else:
                        print(f"[Wallet {self.owner}] Not connected to a miner")

            # Part (ii) - terminate the wallet
            elif reply == "exit":
                self.running = False
                print(f"\n[Wallet {self.owner}] Exiting from wallet")
                break

            # Part (iii) - do not send transaction at this time
            elif reply == "no":
                print(f"\n[Wallet {self.owner}] You have decided not to send a transaction")
            
            else:
                print(f"\n[Wallet {self.owner}] Not a valid input. Enter yes/no/exit")

            # Sleep kept happening for "exit" so i had to do this
            if self.running and reply != "exit":
                # Sleep for a random period of time from 5 to 60 seconds
                sleep_duration = random.randint(5, 60)
                print(f"\n[Wallet {self.owner}] Going to sleep for {sleep_duration} seconds...")
                time.sleep(sleep_duration)

        # When the loop ends
        print(f"[Wallet {self.owner}] Wallet has been terminated")

    def connect_to_bootstrap(self, bootstrap_host: str= "127.0.0.1", bootstrap_port: int = 8333):
        """Function to allow the wallet to connect to the bootstrap node"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as wallet_socket:
            # Make the wallet's socket and connect it to the bootstrap node (directory service)
            wallet_socket.connect((bootstrap_host, bootstrap_port))

            # Request details of miners in the network
            formatter.send_line(wallet_socket, "LIST")
            miners = []
            while True:
                line = formatter.receive_line(wallet_socket)
                if not line:
                    print(f"\n[Wallet {self.owner}] Bootstrap node closed")
                    return
                if line == "END":
                    break
                parts = line.split()
                if len(parts) == 3:
                    miner, host, port_str = parts
                    try:
                        miners.append((miner, host, int(port_str)))
                    except:
                        pass

        # If there was no miner info returned from the bootstrap node
        if not miners:
            print(f"\n[Wallet {self.owner}] No miners available")
            return
        
        # If there was miner info given from bootstrap node
        # Print out each miner's information
        print(f"\n[Wallet {self.owner}] Available miners:")
        for i, (miner, host, port) in enumerate(miners, 1):
            print(f"\t{i}) {miner} @ {host}:{port}")
        
        # Now we randomly pick a miner to connect to
        print(f"\n[Wallet {self.owner}] You will randomly connect to a miner")
        selected_miner = random.choice(miners)
        miner, host, port = selected_miner

        # Now connect to selected miner - I done it this way cause "with" kept closing the connection
        try:
            self.miner_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.miner_socket.connect((host, port))
            self.connected_miner = {"miner": miner, "host": host, "port": port}

            print(f"[Wallet {self.owner}] Connected to {miner} @ {host}:{port}")
        
        except Exception as e:
            print(f"[Wallet {self.owner}] Failed to connect to miner: {e}")
            self.miner_socket = None
            self.connected_miner = None