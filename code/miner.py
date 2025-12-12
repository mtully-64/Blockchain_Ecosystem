import threading
import queue
import formatter
import transaction
import time
import socket
import block

class Miner:
    """
    Creation of a Miner where they can register to the bootstrap node (directory service of the network),
    Connects to other peers within the network (Peer2Peer),
    Allows a wallet to connect with itself and submit transactions,
    The miner will broadcast all of these transactions to the network
    """
    def __init__(self, name: str, host: str = "127.0.0.1", port: int = 9101, bootstrap_host: str = "127.0.0.1", bootstrap_port: int = 8333, difficulty: int = 3, trans_per_block: int = 4):
        self.name = name

        # Storing the host and port of the miner
        self.host = host
        self.port = port

        # Storing the bootstrap node's info
        self.bootstrap_host = bootstrap_host
        self.bootstrap_port = bootstrap_port

        # Define and manage peers (other miners on the network)
        self._peers_lock = threading.Lock()
        self._peers = {} # miner name -> socket

        # Define and manage the miner's mempool
        self._mempool_lock = threading.Lock()
        self._mempool = queue.PriorityQueue() # Priority queue as taught

        # Ensure that 2 transactions with the same fee won't crash the PriorityQueue
        self._mempool_seq = 0
        self._seq_lock = threading.Lock()

        # I ended up doing this over being scared about duplicate transactions and error handling
        self._transaction_ids = set()

        # I have to make a lock to the blockchain, since my own miner has multiple threads wanting to read/write
        self._blockchain_lock = threading.Lock()
        self._blockchain = [] # I realised that a list works, of blocks that are then 'linked' to one another

        # I need to dictate the number of transactions per block
        self.min_trans = trans_per_block
        # Also set the miner's difficulty in which he inputs into his block
        self.difficulty = difficulty

        # Set up the listening socket for the miner
        self.listener = None
        # Through trial and error, I realise you need a registration socket (bootstrap node's socket)
        self.bootstrap_socket = None
        # I need a variable again to flag whether this is running or not
        self.running = False

    def peer_names(self):
        """Returns the list of peers on the network (by miner name)"""
        with self._peers_lock:
            return list(self._peers.keys())

    def add_peer(self, name, sock):
        """Update the socket of a known miner or else add the miner"""
        with self._peers_lock:
            old = self._peers.get(name)
            self._peers[name] = sock
            if old and old is not sock:
                try: old.close()
                except: pass

    def get_sockets(self):
        """Return the list of all sockets known to be owned by fellow peers/miners"""
        with self._peers_lock:
            return list(self._peers.items())
        
    def remove_peer(self, name):
        """Remove a peer from the network miner information"""
        with self._peers_lock:
            # If the name doesnt exist in the peers dict, then return None instead of a KeyError
            s = self._peers.pop(name, None)
            if s:
                try: s.close()
                except: pass

    def broadcast_peers(self, line):
        """Function will send a lines into the network for each socket's info"""
        for _, s in self.get_sockets():
            formatter.send_line(s, line)

    def peer_reader(self, peer_name, sock):
        """Function to listen to messages from peers"""
        print(f"\n[Miner {self.name}] Peer connected: {peer_name}")
        try:
            while True:
                line = formatter.receive_line(sock)
                if not line:
                    break
                parts = line.split(" ", 1)
                if len(parts) >= 2:
                    cmd = parts[0].upper()
                    payload = parts[1]
                    
                    if cmd == "TX":
                        self.process_transaction_message(payload, from_peer=True)
                    elif cmd == "BLOCK":
                        print(f"[Miner {self.name}] Received block from {peer_name}")
        finally:
            print(f"\n[Miner {self.name}] Peer disconnect: {peer_name}")
            self.remove_peer(peer_name)

    def process_local_message(self, text, client_socket):
        """Function to handle the processing of text, that the Miner uses to broadcast a new peer into the network (P2P network)"""
        print(f"[Miner {self.name}] from client: {text}")
        formatter.send_line(client_socket, f"[you@{self.name}] {text}")
        self.broadcast_peers(f"MSG {self.name} {text}")

    def process_transaction_message(self, message, from_peer=False):
        """Handles whether a transaction is from a wallet or a peer"""
        try:
            if message.startswith("Transaction:"):
                transaction_data = message.replace("Transaction:", "")
                # Machine readable
                transaction_data = transaction_data.strip().split(",") 

                if len(transaction_data) >= 5:
                    sender = transaction_data[0].strip()
                    receiver = transaction_data[1].strip()
                    amount = float(transaction_data[2].strip())
                    fee = float(transaction_data[3].strip())
                    transaction_id = transaction_data[4].strip()

                    with self._mempool_lock:
                        # Check duplicate transaction
                        if transaction_id in self._transaction_ids:
                            return True
                        
                        # Else will now make the transaction
                        tx = transaction.Transaction(sender, receiver, amount, fee)

                        # This is the sequence thing if there is two transaction fees with the same value
                        with self._seq_lock:
                            seq = self._mempool_seq
                            self._mempool_seq += 1

                        self._mempool.put((-float(fee), seq, tx))  # As requested, done highest fee as highest priority
                        self._transaction_ids.add(transaction_id)

                        print(f"\n[Miner {self.name}] Transaction was added to the mempool:")
                        print(f"\tID: {transaction_id}")
                        print(f"\tSender: {sender}")
                        print(f"\tReceiver: {receiver}")
                        print(f"\tAmount: {amount}")
                        print(f"\tFee: {fee}")

                        # If it came from a wallet and not a peer then I have to broadcast it to the network
                        if not from_peer:
                            self.broadcast_peers(f"TX {message}") # Its not the most efficient way I wrote the strings
                        return True
            return False
        
        except Exception as e:
            print(f"[Miner {self.name}] Error: {e}")
            return False

    def send_blockchain_data(self, conn, start_index):
        """
        Send blockchain blocks to wallet starting from start_index
        This connection will close after sending data, so thats its constantly refreshing new info
        """
        try:
            with self._blockchain_lock:
                # Get blocks from start_index onwards
                if start_index < 0:
                    start_index = 0
                
                blocks_to_send = self._blockchain[start_index:] if start_index < len(self._blockchain) else []
            
            if not blocks_to_send:
                # No new blocks, just send END
                formatter.send_line(conn, "END_BLOCKS")
                return
            
            # Send each block
            for i, blk in enumerate(blocks_to_send, start=start_index):
                formatter.send_line(conn, f"BLOCK {i} {len(blk.data)}")
                
                # Send each transaction in the block
                for tx in blk.data:
                    tx_str = f"TX: {tx.sender},{tx.receiver},{tx.amount},{tx.fee},{tx.transaction_id}"
                    formatter.send_line(conn, tx_str)
            
            # Signal end of blocks
            formatter.send_line(conn, "END_BLOCKS")
            
        except Exception as e:
            print(f"[Miner {self.name}] Error sending blockchain: {e}")
            try:
                formatter.send_line(conn, "END_BLOCKS")
            except:
                pass

    def handle_client(self, connection, address, first_line=None):
        """Function to handle when a wallet connects to a miner"""
        try:
            if first_line:
                # Check if this is a blockchain query
                if first_line.startswith("GET_BLOCKS"):
                    parts = first_line.split()
                    start_index = int(parts[1]) if len(parts) > 1 else 0
                    # Send blockchain data and close that connection
                    self.send_blockchain_data(connection, start_index)
                    return
                
                # Otherwise process as transaction
                if self.process_transaction_message(first_line):
                    formatter.send_line(connection, "OK")

            # Keep connection open for persistent transaction sending
            while True:
                line = formatter.receive_line(connection)
                if not line or line.strip().lower() == "exit":
                    break
                
                # Now handle GET_BLOCKS in the loop
                if line.startswith("GET_BLOCKS"):
                    parts = line.split()
                    start_index = int(parts[1]) if len(parts) > 1 else 0
                    self.send_blockchain_data(connection, start_index)
                    continue
                
                if self.process_transaction_message(line):
                    formatter.send_line(connection, "OK")
        finally:
            try:
                connection.close()
            except:
                pass
            

    def classify_and_handle(self, conn, addr):
        """Function to handle a new connection - whether they are a peer or other"""
        # This is the first line received from the new connection
        first_line = formatter.receive_line(conn)
        
        # Close connection if nothing
        if not first_line:
            try: conn.close()
            except: pass
            return
        
        parts = first_line.split()

        if len(parts) == 2 and parts[0].upper() == "PEER":
            pname = parts[1]
            # Add the peer to list of known peers/miners (self._miners)
            self.add_peer(pname, conn)
            self.peer_reader(pname, conn)
        else:
            self.handle_client(conn, addr, first_line=first_line)

    def connect_to_peer(self, peer_host, peer_port, peer_name):
        """Function used to connect Miner to peer"""
        # If the name is my name (the miner) or the name is already a connected peer, then we don't need to connect
        if peer_name == self.name or peer_name in self.peer_names():
            return
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.connect((peer_host, peer_port))
            formatter.send_line(s, f"PEER {self.name}")
            self.add_peer(peer_name, s)
            threading.Thread(target=self.peer_reader, args=(peer_name, s), daemon=True).start()
        except Exception:
            pass

    def start_peer_acceptance_loop(self):
        """This triggers the Miner to start listening for other Miners on the network (peers)"""
        try:
            # When the Miner is running
            while self.running:
                try:
                    # Get the connection and address to the Bootstrap node
                    connection, address = self.listener.accept()
                    threading.Thread(target=self.classify_and_handle, args=(connection, address), daemon=True).start()
                except OSError:
                    # Close the socket
                    break
                except Exception:
                    # Ignore errors
                    if not self.running:
                        break
        except Exception:
            pass

    def start_mining_loop(self):
        """This triggers the Miner to start mining"""
        print(f"\n[Miner {self.name}] Starting to mine")

        try:
            # I need to check the mempool periodically, so I will do it every 2 seconds
            while self.running:
                # Check every 2s
                time.sleep(2)

                selected_transactions = []

                # This is my way that I got the transactions out of the priority queue
                with self._mempool_lock:
                    if self._mempool.qsize() >= self.min_trans:
                        for i in range(self.min_trans):
                            try:
                                priority, seq, tx = self._mempool.get_nowait()
                                selected_transactions.append(tx)
                                self._mempool.task_done()
                                # This is where I want to check for duplicates from before
                                self._transaction_ids.discard(tx.transaction_id) # I could have done .remove() but .discard() gives no error
                            except queue.Empty:
                                break

                        # If there wasn't enough transactions for the block
                        if len(selected_transactions) < self.min_trans:
                            for tx in selected_transactions:
                                with self._seq_lock:
                                    seq = self._mempool_seq
                                    self._mempool_seq += 1
                                self._mempool.put((-tx.fee, seq, tx))
                                self._transaction_ids.add(tx.transaction_id)
                            selected_transactions = []

                if len(selected_transactions) == self.min_trans:
                    print(f"\n[Miner {self.name}] Mining block with {len(selected_transactions)} transactions")

                    # Get the previous blocks hash
                    with self._blockchain_lock:
                        if self._blockchain:
                            previous_hash = self._blockchain[-1].hash
                        else:
                            previous_hash = "0" * 64 

                    try:
                        new_block = block.Block(selected_transactions, previous_hash, self.difficulty)

                        # Now just add the block to the chain
                        with self._blockchain_lock:
                            self._blockchain.append(new_block)

                        print(f"\n[Miner {self.name}] Block mined! Hash: {new_block.hash}")
                        print(f"[Miner {self.name}] Blockchain length: {len(self._blockchain)}")

                        # Tell the network via broadcast of block
                        self.broadcast_peers(f"BLOCK {new_block.hash}")

                    except Exception as e:
                        print(f"[Miner {self.name}] Error creating block: {e}")
                        
                        for tx in selected_transactions:
                            with self._seq_lock:
                                seq = self._mempool_seq
                                self._mempool_seq += 1
                            with self._mempool_lock:
                                self._mempool.put((-tx.fee, seq, tx))
                                self._transaction_ids.add(tx.transaction_id)
        except Exception:
            pass
                
    def peer_connector(self):
        """This triggers the Miner to request the Miner list from the Bootstrap node and connects to each peer (other Miners)"""
        try:
            while self.running:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.connect((self.bootstrap_host, self.bootstrap_port))
                        formatter.send_line(s, "LIST")
                        entries = []
                        while True:
                            line = formatter.receive_line(s)
                            if not line or line == "END":
                                break
                            parts = line.split()
                            if len(parts) == 3:
                                name, host, port = parts[0], parts[1], int(parts[2])
                                entries.append((name, host, port))
                    for name, host, port in entries:
                        self.connect_to_peer(host, port, name)
                except Exception:
                    if not self.running:
                        break
                time.sleep(1.5)
        except Exception:
            pass
    
    def start_miner(self):
        """This function starts the miner - accepting connections from network peers and mining"""
        # First I see Dimi makes a socket for the miner, in which is a 'listener' socket
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((self.host, self.port))
        self.listener.listen()

        print(f"\n[Miner {self.name}] Serving on {self.host}:{self.port}")

        # Then register the newly made miner
        self.bootstrap_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.bootstrap_socket.connect((self.bootstrap_host, self.bootstrap_port))
            formatter.send_line(self.bootstrap_socket, f"REGISTER {self.name} {self.host} {self.port}")
            if formatter.receive_line(self.bootstrap_socket) != "OK":
                print(f"\n[Miner {self.name}] Bootstrap node registration failed")
                self.bootstrap_socket.close()
                self.bootstrap_socket = None
            else:
                print(f"\n[Miner {self.name}] Registered with Bootstrap node")
        except Exception as e:
            print(f"\n[Miner {self.name}] Could not register with Bootstrap node: {e}")
            self.bootstrap_socket = None

        # Now the Miner is connected up and running
        self.running = True

        # Now we create a threads to handle each of the Miner's tasks
        #   1 - Periodically get all miners on network and connect to them
        threading.Thread(target=self.peer_connector, daemon=True).start()
        #   2 - Start accepting incoming peer connections
        threading.Thread(target=self.start_peer_acceptance_loop, daemon=True).start()
        #   3 - Start mining
        threading.Thread(target=self.start_mining_loop, daemon=True).start()

        # Periodically check the miner is still running
        try:
            while self.running == True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print(f"\n[Miner {self.name}] Miner is stopping")
        finally:
            self.running = False

            if self.listener:
                try: self.listener.close()
                except: pass

            if self.bootstrap_socket:
                try: self.bootstrap_socket.close()
                except: pass

            with self._peers_lock:
                for peer_socket in self._peers.values():
                    try:
                        peer_socket.close()
                    except:
                        pass
                self._peers.clear()