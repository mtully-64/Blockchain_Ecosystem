import time
import hashlib
from utils import hash_function

# Now I make the class to create objects of "blocks" for the blockchain
class Block:
    def __init__(self, tx_list: list, previous_hash, difficulty=1):
        self.timestamp = time.time()
        self.data = tx_list # this is either a list of transactions
        self.previous_hash = previous_hash

        # Setting up for mining
        self.difficulty = difficulty
        self.nonce = 0

        # This is the block's merkle tree, it returns the root of the tree
        self.merkle_tree = self.create_merkle_tree()

        # Creating the block's hash
        self.hash = self.calculate_hash()

        # Function to mine the block
        self.mine(difficulty)

    def data_to_str(self):
        """
        Since the data is a list and not strings, I need to be able to handle this
        """
        if not self.data:
            return "No transactions at all"
        
        transactions_string = []
        for tx in self.data:
            tx_string = f"{tx.transaction_id},{tx.sender},{tx.receiver},{tx.amount},{tx.timestamp}" 
            transactions_string.append(tx_string)

        # Didn't know what to do with it, so done this in terms of a String
        return "||".join(transactions_string)
    
    def calculate_hash(self):
        if isinstance(self.data, list): # It should always be a list, but I am leaving this in here cause of Genesis block modification if needed
            data_str = self.merkle_tree

        to_hash = str(self.timestamp) + data_str + self.previous_hash + str(self.nonce) + str(self.difficulty) 

        return hashlib.sha256(to_hash.encode()).hexdigest() # this is returned in a string hexadecimal format - not 0101010111 but instead 2cf24dba5fb0a30e2
    
    def create_merkle_tree(self):
        """
        I will use 'self.data' which is a list of transactions
        
        Each Transaction has a transaction ID, this is the SHA-256 of the transaction information (self.transaction_id = sha256(self.data)), where self.data is defined from the "data_helper()" function
        """
        
        # if no transactions then return error handling
        if not self.data:
            return "No transactions at all"
        
        # if the data is a transaction list (this is extra but i just decided to add it as a back up)
        if isinstance(self.data, list):
            if len(self.data) < 1: # this used to be set to 8 from worksheet four (this is why this code is here)
                return "You require at least one transaction in the list!"
            
            # make the leaves
            leaves = []
            for tx in self.data:
                leaves.append(tx.transaction_id)

            # make the layers
            layers = [leaves]
            while len(layers[-1]) > 1:
                cur = layers[-1]
                nxt = []
                for i in range(0, len(cur), 2):
                    left = cur[i]
                    right = cur[i + 1] if i + 1 < len(cur) else cur[i] # duplicate last if its an odd one
                    nxt.append(hash_function.sha256(left + right))
                layers.append(nxt)

            # assign the root node from the layers matrix
            root = layers[-1][0]

            # do the print demo for each block
            print(f"\nCreating merkle tree...")
            print("\nLeaves (hashes):")
            for i, h in enumerate(leaves):
                print(f"    Leaf {i}: {h}")

            print("\nMerkle root:", root)

            print("\nTree (from root to leaves):")
            for depth, layer in enumerate(reversed(layers), start=0):
                level = len(layers) - 1 - depth
                print(f"    Layer {level} ({len(layer)} node(s)):")
                for node in layer:
                    print(" ", node)

            # set the root, layers and leaves to the block as an extra
            self.merkle_tree_root = root
            self.merkle_tree_layers = layers
            self.merkle_tree_leaves = leaves
            
            # return the root of the merkle tree I guess
            return self.merkle_tree_root
        
        # if this is a string (like expected for the genesis block), then just set None as there is no merkle tree
        # this should never be implemented but left just incase of a later change 
        elif isinstance(self.data, str):
            return None
        
    def mine(self, difficulty):
        """ 
        Method starts with a nonce = 0, keeps incrementing the nonce and hashing the block until hash is good
        Difficulty is the number of how many zeros
        """
        target = 1 << (256 - difficulty)
        start_time = time.time()

        while True:
            self.hash = self.calculate_hash() # I realised I have to recalulate the full block hash everytime
            if int(self.hash, 16) < target: # I use 16 and not "big" here, because I want to use .hexdigest instead of .digest for the SHA-256 function (Dimi used the .digest aka bytes and not hex)
                end_time = time.time()
                self.mining_time = end_time - start_time
                self.mining_attempts = self.nonce + 1 # realised to add one cause we start with a zero
                return
            self.nonce += 1
        

    def __str__(self):
        return f"This is the block, {self.hash}, with a timestamp of {self.timestamp}."