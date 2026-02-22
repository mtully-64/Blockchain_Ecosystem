import threading
from utils import formatter
import socket

class Bootstrap:
    """
    Creating a bootstrapping node
    A bootstrapping node is a node that provides the initial configuration info to new nodes to join the network
    The new nodes that use it to connect to the network are the "Miners"
    Multiple miners can connect to it in parallel to this node
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 8333):
        self.host = host
        self.port = port

        self._registry_lock = threading.Lock()
        self._registry = []

    def bootstrap_handler(self, conn, addr):
        with conn:
            # Line is the string received at the bootstrap node's socket
            # It will be a command to either register a new miner or list current miner info
            line = formatter.receive_line(conn) # command will either be REGISTER or LIST
            if not line:
                return
            parts = line.strip().split()
            command = parts[0].upper()

            # If it is a miner wanting to register
            if command == "REGISTER" and len(parts) == 4:
                # Set the registration information of a miner into variables
                name, host, port_str = parts[1], parts[2], parts[3]
                
                # Attempt to associate their port to the network
                try:
                    port = int(port_str)
                except ValueError:
                    formatter.send_line(conn, "ERR invalid port")
                    return
                with self._registry_lock:
                    # This is the new miner's details
                    entry = {"miner": name, "host": host, "port": port}
                    # If the miner and his details do not already exist in the registry, then append them
                    self._registry[:] = [e for e in self._registry if not (e["miner"] == name and e["host"] == host and e["port"] == port)]
                    self._registry.append(entry)

                # Inform the miner that all is OK
                formatter.send_line(conn, "OK")
                formatter.receive_line(conn)

                with self._registry_lock:
                    self._registry[:] = [e for e in self._registry if not (e["miner"] == name and e["host"] == host and e["port"] == port)]
            
            # Else if the miner wants to get the list of all other miner's information
            elif command == "LIST":
                with self._registry_lock:
                    entries = list(self._registry)
                for e in entries:
                    formatter.send_line(conn, f'{e["miner"]} {e["host"]} {e["port"]}')
                formatter.send_line(conn, "END")
            else:
                formatter.send_line(conn, "ERR unknown command")

    def run_bootstrap(self):
        """Start running the bootstrap node server"""
        # Set the socket to TCP and IPv4, alongside other socket options
        bootstrap_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        bootstrap_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind the socket to the host and port
        bootstrap_socket.bind((self.host, self.port))

        # Start listening to connections
        bootstrap_socket.listen()

        print(f"\n[Bootstrap Node] Listening on {self.host}:{self.port}")

        try:
            while True:
                # Now we start accepting incoming connections
                conn, addr = bootstrap_socket.accept()

                # Thread each one
                threading.Thread(target=self.bootstrap_handler, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[Bootstrap Node] Shutting down")
        finally:
            bootstrap_socket.close()