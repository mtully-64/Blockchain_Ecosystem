import time
import formatter
import hash_function

class Transaction:
    def __init__(self, sender: str, receiver: str, amount: int | str, fee: int | float = 0):
        self.sender = sender
        self.receiver = receiver
        self.amount = str(amount)
        self.timestamp = time.time()
        self.fee = float(fee)

        # This is the data for the transaction used from a tutorial worksheet
        self.data = formatter.data_helper(self.sender, self.receiver, self.amount, self.timestamp)

        # Each transaction must have an ID
        self.transaction_id = hash_function.sha256(self.data)

    # Making the print/string format of the classes object
    def __str__(self):
        return f"Transaction ID of '{self.transaction_id}'. {self.sender} to {self.receiver}, for the amount of {self.amount} with {self.fee} fee."