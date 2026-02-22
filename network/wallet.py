from core import transaction
from utils import formatter
import random
import time
import socket
import threading

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
        
        # Track which blocks we've already processed
        self.last_processed_block_index = -1

    def add_transaction(self, transaction: transaction.Transaction):
        """Function that adds transactions where owner is receiver"""
        if transaction.receiver == self.owner:
            # Check for duplicates
            if not any(tx.transaction_id == transaction.transaction_id for tx in self.tx_received):
                self.tx_received.append(transaction)
                print(f"\n[Wallet {self.owner}] UTXO received {transaction.amount} coins from {transaction.sender}!")

    def wallet_balance(self):
        """Function to get the total of the received amount"""
        balance = 0
        for tx in self.tx_received:
            balance += float(tx.amount)
        return balance
    
    def see_all_transactions(self):
        """
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
    
    def get_available_miners(self, bootstrap_host: str = "127.0.0.1", bootstrap_port: int = 8333):
        """
        In the case of miner crash and loss of connection, I need to look for a list of all available miners from the bootstrap node
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as wallet_socket:
                wallet_socket.connect((bootstrap_host, bootstrap_port))
                formatter.send_line(wallet_socket, "LIST")
                miners = []
                while True:
                    line = formatter.receive_line(wallet_socket)
                    if not line:
                        break
                    if line == "END":
                        break
                    parts = line.split()
                    if len(parts) == 3:
                        miner, host, port_str = parts
                        try:
                            miners.append((miner, host, int(port_str)))
                        except:
                            pass
                return miners
        except Exception as e:
            print(f"[Wallet {self.owner}] Error querying bootstrap node: {e}")
            return []    
    
    def reconnect_to_miner(self, bootstrap_host: str ="127.0.0.1", bootstrap_port: int = 8333, exclude_current: bool = True):
        """Reconnect to a different miner in the event that the current one crashes/fails"""
        # Close the existing connection
        if self.miner_socket:
            try:
                self.miner_socket.close()
            except:
                pass
            self.miner_socket = None

        current_miner_name = self.connected_miner["miner"] if self.connected_miner else None

        # Get the list of the available miners
        miners = self.get_available_miners(bootstrap_host, bootstrap_port)
        
        if not miners:
            print(f"\n[Wallet {self.owner}] ERROR - No miners available for reconnection")
            self.connected_miner = None
            return False
        
        # Filter out that failed miner if its shown in the list
        if exclude_current and current_miner_name:
            miners = [(m, h, p) for m, h, p in miners if m != current_miner_name]
        
        if not miners:
            print(f"\n[Wallet {self.owner}] ERROR - No alternative miners available")
            self.connected_miner = None
            return False
        
        # Try to connect to each miner until one succeeds
        for miner, host, port in miners:
            try:
                print(f"\n[Wallet {self.owner}] Attempting to connect to {miner}...")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, port))
                self.miner_socket = sock
                self.connected_miner = {"miner": miner, "host": host, "port": port}
                print(f"[Wallet {self.owner}] Successfully reconnected to {miner} @ {host}:{port}")
                return True
            except Exception as e:
                print(f"[Wallet {self.owner}] Failed to connect to {miner}: {e}")
                try:
                    sock.close()
                except:
                    pass
                continue
        
        print(f"\n[Wallet {self.owner}] ERROR - Could not reconnect to any miner")
        self.connected_miner = None
        return False

    def query_blockchain_updates(self):
        """
        Queries the miner for blockchain updates using a temp connection, thats refreshed
        """
        if not self.connected_miner:
            return
        
        # I will give the wallet 3 chances to reconnect - due to error handling
        max_retries = 3
        retry_count = 0
        
        # Open a temporary connection
        while retry_count < max_retries:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as query_socket:
                    # Connect to our miner
                    query_socket.connect((self.connected_miner['host'], self.connected_miner['port']))
                
                    # Send blockchain query
                    formatter.send_line(query_socket, f"GET_BLOCKS {self.last_processed_block_index + 1}")
                
                    # Read blocks until END_BLOCKS
                    while True:
                        line = formatter.receive_line(query_socket)
                        if not line or line == "END_BLOCKS":
                            break
                    
                        # Now I have to parse the incoming message
                        if line.startswith("BLOCK"):
                            parts = line.split()
                            if len(parts) >= 3:
                                block_index = int(parts[1])
                                num_txs = int(parts[2])
                                
                                # Read each transaction in this block
                                for _ in range(num_txs):
                                    tx_line = formatter.receive_line(query_socket)
                                    if tx_line.startswith("TX:"):
                                        tx_data = tx_line[3:].strip().split(",")
                                        if len(tx_data) >= 5:
                                            sender = tx_data[0].strip()
                                            receiver = tx_data[1].strip()
                                            amount = float(tx_data[2].strip())
                                            fee = float(tx_data[3].strip())
                                            tx_id = tx_data[4].strip()
                                            
                                            # If this transaction is for this wallet then add it
                                            if receiver == self.owner:
                                                tx = transaction.Transaction(sender, receiver, amount, fee)
                                                self.add_transaction(tx)
                                
                                self.last_processed_block_index = block_index

                    # If we connect again then break this retry loop  
                    break

            except Exception as e:
                retry_count += 1
                print(f"[Wallet {self.owner}] Error querying blockchain ({retry_count}/{max_retries}): {e}")
                
                if retry_count >= max_retries:
                    print(f"[Wallet {self.owner}] Miner connection lost, attempting to reconnect...")
                    if self.reconnect_to_miner():
                        retry_count = 0  # I fucked up and forgot to reset this
                    else:
                        print(f"[Wallet {self.owner}] Could not reconnect to any miner")
                        break
                else:
                    time.sleep(1)
    
    def blockchain_monitor(self):
        """
        A background thread that periodically queries for new blocks
        """
        time.sleep(10)
        while self.running:
            self.query_blockchain_updates()
            time.sleep(10)

    def send_transaction_with_retry(self, transaction_message, max_retries=3):
        """Send the transaction where it retries and reconnects on failure"""
        retry_count = 0
        
        while retry_count < max_retries:
            if not self.miner_socket or not self.connected_miner:
                print(f"[Wallet {self.owner}] Not connected to a miner, attempting to reconnect...")
                if not self.reconnect_to_miner():
                    return False
            
            try:
                # Attempt to send transaction
                formatter.send_line(self.miner_socket, transaction_message)
                print(f"\n[Wallet {self.owner}] Sent transaction to miner {self.connected_miner['miner']}")
                return True
                
            except Exception as e:
                retry_count += 1
                print(f"[Wallet {self.owner}] Error sending the transaction ({retry_count}/{max_retries}): {e}")
                
                # Connection failed, try to reconnect
                print(f"[Wallet {self.owner}] Miner connection lost, attempting to reconnect...")
                if self.reconnect_to_miner():
                    # Successfully reconnected, continue retry loop
                    continue
                else:
                    print(f"[Wallet {self.owner}] Could not reconnect to any miner")
                    return False
        
        print(f"[Wallet {self.owner}] Failed to send transaction after {max_retries} attempts")
        return False

    def wallet_loop(self):
        """
        I need a running loop for each wallet
        Each loop will be in a thread, I presume the loop is constantly running for each wallet
        """
        print(f"[Wallet {self.owner}] Threaded loop starting")
        
        # Start the blockchain monitoring thread
        threading.Thread(target=self.blockchain_monitor, daemon=True).start()

        # When the loop starts
        while self.running:
            # Show them all transactions
            self.see_all_transactions()
            # Then let them decide
            reply = input(f"\n[Wallet {self.owner}] Would you like to send a transaction to another owner [yes/no/exit]?\n")
            reply = reply.strip().lower()

            # To send to an owner
            if reply == "yes":
                # collate information on transaction - receivee, amount and fee
                try:
                    input_receiver = str(input(f"\n[Wallet {self.owner}] Who are you going to send it to?\n")).strip()
                    input_amount = float(input(f"\n[Wallet {self.owner}] What amount are you going to send?\n").strip())
                    input_fee = float(input(f"\n[Wallet {self.owner}] What fee amount are you willing to spend?\n").strip())

                    # Negative error handling
                    if input_amount < 0 or input_fee < 0:
                        raise ValueError(f"Wallet [{self.owner}] Amount and fee must be a non-negative number")
                    
                except ValueError:
                    print(f"[Wallet {self.owner}] ERROR - Enter in valid numbers for amount and fee")
                    continue
                except Exception as e:
                    print(f"[Wallet {self.owner}] ERROR - {e}")
                    continue

                # select the transactions to make up cost
                selected_transactions = self.select_sufficient_transactions(input_amount, input_fee)

                # If there is selected UTXOs amounting to the min_trans number
                if selected_transactions != None:
                    # Make the new transaction
                    new_transaction = transaction.Transaction(self.owner, input_receiver, input_amount, input_fee)
                    # Print the information about the creation of the transaction
                    print(f"\n[Wallet {self.owner}] Transaction {new_transaction.transaction_id} created!!!")
                    print(f"\tSender: {new_transaction.sender}")
                    print(f"\tReceiver: {new_transaction.receiver}")
                    print(f"\tAmount: {new_transaction.amount}")
                    print(f"\tFee: {new_transaction.fee}")

                    # Calculate the total UTXO balance and find the change owed after deducting this from the newly created tx
                    total_input = sum(float(tx.amount) for tx in selected_transactions)
                    change = total_input - input_amount - input_fee
                    
                    # Everytime I made a Transaction I never got change back from the used UTXOs
                    if change > 0:
                        # Make a UTXO for the balanced money to go back to me
                        change_tx = transaction.Transaction(self.owner, self.owner, change, 0)
                        self.add_transaction(change_tx)
                        print(f"\n[Wallet {self.owner}] Change of {change} coins returned back")

                    transaction_message = f"Transaction: {new_transaction.sender}, {new_transaction.receiver}, {new_transaction.amount}, {new_transaction.fee}, {new_transaction.transaction_id}"

                    if not self.send_transaction_with_retry(transaction_message):
                        # Transaction failed after all my retry attempts, so just revert UTXOs
                        print(f"[Wallet {self.owner}] Transaction failed - reverting UTXOs")
                        for tx in selected_transactions:
                            self.tx_received.append(tx)
                        if change > 0:
                            # Undo the change transaction we added
                            self.tx_received = [tx for tx in self.tx_received if tx.transaction_id != change_tx.transaction_id]

            # Terminate the wallet
            elif reply == "exit":
                self.running = False
                print(f"\n[Wallet {self.owner}] Exiting from wallet")
                break

            # Do not send transaction at this time
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