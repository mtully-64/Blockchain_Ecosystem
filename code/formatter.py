def data_helper(sender: str, receiver: str, amount: str, time: float):
    """
    Helper function to produce data to be added to blocks.
    We used this in a worksheet so I will use it again.
    """
    data = f"{sender},{receiver},{amount},{str(time)}"
    return data

# These helper functions were outlined to send/receive a string across a socket
def send_line(sock, s):
    """
    Function to send a line over a socket
    It just makes sure there is only one newline and its then converted into a byte sequence
    """
    try:
        sock.sendall((s.rstrip("\n") + "\n").encode("utf-8"))
    except Exception:
        pass

def receive_line(sock):
    """Function is to understand/receive a line over a socket"""
    data = bytearray()
    try:
        while True:
            ch = sock.recv(1)
            if not ch:
                return ""
            data += ch
            if ch == b"\n":
                return data.decode("utf-8", errors="replace").rstrip("\n")
    except Exception:
        return ""