import hashlib

# Now I have to make the function to handle hashing at SHA256
# This will be in 'hexdigest' not 'digest', so I can read it as a human
def sha256(data):
    """Simple SHA256 function"""
    return hashlib.sha256(data.encode('UTF-8')).hexdigest()