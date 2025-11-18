# importation of other util libaries
import sys

############################################################

# Importing the code as seperate clean files
import transaction
import wallet
import bootstrap
import miner
import wallet

############################################################

# Learned this in undergrad
if __name__ == "__main__":
    
    if len(sys.argv) < 2:
        
        # Intro heading
        print("-"*100)
        print("Building a Blockchain Ecosystem")
        print("-"*100)

        # Details
        print("\nThis program simulates the blockchain ecosystem with:")
        print("\t-> 1 Bootstrap Node")
        print("\t-> 3 Miners")
        print("\t-> 5 Wallets")

        # Set up explanation
        print("\nIn order to use this program:")
        print("\t-> python main.py bootstrap")
        print("\t-> python main.py miner <miner-name> <port-number>")
        print("\t-> python main.py wallet <owner-name>")

        # Give an example setup
        print()
        print("-"*100)
        print("Example set up (run in this order):")
        print("-"*100)
        print()
        print("1 - Terminal 1: python main.py bootstrap")
        print("2 - Terminal 2: python main.py miner Miner1 9001")
        print("3 - Terminal 3: python main.py miner Miner2 9002")
        print("4 - Terminal 4: python main.py miner Miner3 9003")
        print("5 - Terminal 5: python main.py wallet Dimi")
        print("6 - Terminal 6: python main.py wallet Mark")
        print("7 - Terminal 7: python main.py wallet Jack")
        print("8 - Terminal 8: python main.py wallet John")
        print("9 - Terminal 9: python main.py wallet Adam")
        
        print()
        print("-"*100)
        print()

        sys.exit(1)
    
    # Whether its a miner/wallet/bootstrap, this will be addressed in the first argument
    role = sys.argv[1].lower()
    
    # If you want the Bootstrap node
    if role == "bootstrap":
        print()
        print("-"*100)
        print("Starting the Bootstrap node!")
        print("-"*100)
        bootstrap = bootstrap.Bootstrap("127.0.0.1", 8333)
        bootstrap.run_bootstrap()
    
    # If you want the Miner
    elif role == "miner":
        if len(sys.argv) != 4:
            print("\nError: Miner requires both name and port")
            print("Input should be: python main.py miner <name> <port>")
            sys.exit(1)
        
        miner_name = sys.argv[2]
        miner_port = int(sys.argv[3])
        
        print()
        print("-"*100)
        print(f"Starting Miner: {miner_name}")
        print("-"*100)
        
        # I will just hard code in a difficulty of 2 and a minimum trans_per_block of 4
        miner = miner.Miner(miner_name, "127.0.0.1", miner_port, "127.0.0.1", 8333, 2, 4)
        miner.start_miner()
    
    # If you want the Wallet
    elif role == "wallet":
        if len(sys.argv) != 3:
            print("\nError: Wallet requires name")
            print("Input should be: python main.py wallet <name>")
            sys.exit(1)
        
        wallet_name = sys.argv[2]
        
        print()
        print("-"*100)
        print(f"Starting Wallet: {wallet_name}")
        print("-"*100)
        
        # Create the wallet
        wallet = wallet.Wallet(wallet_name)
        
        # Now for task 9, I will give an initial 100 Trump coins
        trump_coins = 100

        print(f"\n[Wallet {wallet_name}] Receiving {trump_coins} Trump coins from Genesis")

        genesis_tx = transaction.Transaction("Genesis", wallet_name, trump_coins, 0)
        wallet.add_transaction(genesis_tx)
        
        print(f"\n[Wallet {wallet_name}] You now start with {wallet.wallet_balance()} Trump coins")
        
        # Connect the Wallet to the Bootstrap and get random Miner
        print(f"\n[Wallet {wallet_name}] Connecting to Bootstrap node...")

        wallet.connect_to_bootstrap("127.0.0.1", 8333)
        
        if wallet.miner_socket is None:
            print(f"\n[Wallet {wallet_name}] Failed to connect to any miners")
            sys.exit(1)
        
        # Start the interactive wallet loop
        print(f"\n[Wallet {wallet_name}] Starting wallet interface...")
        print("-"*100)
        print()
        
        # This worked so I will leave it like this
        wallet.running = True
        wallet.wallet_loop()

    else:
        # Error handling
        print(f"\nUnknown role: {role}")
        print("The only valid roles: bootstrap, miner, wallet\n")
        sys.exit(1)