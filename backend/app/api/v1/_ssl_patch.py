# SSL patch module - must be imported BEFORE uvicorn or any ssl-dependent module
import sys
import os

# Store the python directory to find _ssl
python_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Try to find _ssl in various locations
ssl_locations = [
    os.path.join(python_dir, "DLLs", "_ssl.pyd"),
    os.path.join(python_dir, "_ssl.pyd"),
    os.path.join(os.environ.get("PYTHONHOME", ""), "DLLs", "_ssl.pyd") if os.environ.get("PYTHONHOME") else None,
]

ssl_found = False
for ssl_path in ssl_locations:
    if ssl_path and os.path.exists(ssl_path):
        print(f"Found _ssl at: {ssl_path}")
        # Add the directory to sys.path so _ssl gets loaded first
        ssl_dir = os.path.dirname(ssl_path)
        if ssl_dir not in sys.path:
            sys.path.insert(0, ssl_dir)
        ssl_found = True
        break

if not ssl_found:
    print("_ssl.pyd not found in standard locations")
    # Provide a minimal stub that uvicorn/config.py can at least import
    import types
    _ssl_stub = types.ModuleType('_ssl_stub')
    _ssl_stub.OPENSSL_VERSION_NUMBER = 0x00000000L
    _ssl_stub.OPENSSL_VERSION_INFO = (0, 0, 0)
    _ssl_stub.OPENSSL_VERSION = 'Unknown'
    
    # Basic SSL constants
    _ssl_stub.SSL_ERROR = 0
    _ssl_stub.SSL_ERROR_ZERO_RETURN = 0
    _ssl_stub.SSL_ERROR_WANT_READ = 1
    _ssl_stub.SSL_ERROR_WANT_WRITE = 2
    _ssl_stub.SSL_ERROR_WANT_X509_LOOKUP = 3
    _ssl_stub.SSL_ERROR_SYSCALL = 3
    _ssl_stub.SSL_ERROR_SSL = 10
    _ssl_stub.SSL_ERROR_EOF = 6
    _ssl_stub.SSL_ERROR_WANT_CONNECT = 4
    _ssl_stub.SSL_ERROR_INVALID_ERROR_CODE = -1
    
    # SSL protocol constants
    _ssl_stub.PROTOCOL_SSLv23 = 'PROTOCOL_SSLv23'
    _ssl_stub.PROTOCOL_TLS = 'PROTOCOL_TLS'
    _ssl_stub.PROTOCOL_TLS_CLIENT = 'PROTOCOL_TLS_CLIENT'
    _ssl_stub.PROTOCOL_TLS_SERVER = 'PROTOCOL_TLS_SERVER'
    
    # SSL verify modes
    _ssl_stub.CERT_REQUIRED = 'CERT_REQUIRED'
    _ssl_stub.CERT_OPTIONAL = 'CERT_OPTIONAL'
    _ssl_stub.CERT_NONE = 'CERT_NONE'
    
    # Minimal SSLContext
    _ssl_stub.SSLContext = type('SSLContext', (), {})()
    
    # HAS_* flags
    _ssl_stub.HAS_SNI = False
    _ssl_stub.HAS_ECDH = False
    _ssl_stub.HAS_NPN = False
    _ssl_stub.HAS_ALPN = False
    _ssl_stub.HAS_SSLv2 = False
    _ssl_stub.HAS_SSLv3 = False
    _ssl_stub.HAS_TLSv1 = False
    _ssl_stub.HAS_TLSv1_1 = False
    _ssl_stub.HAS_TLSv1_2 = False
    _ssl_stub.HAS_TLSv1_3 = False
    
    # Assign to sys.modules
    sys.modules['_ssl'] = _ssl_stub
    # Also replace ssl module
    sys.modules['ssl'] = types.ModuleType('ssl_patched')
    sys.modules['ssl']._ssl = _ssl_stub
    sys.modules['ssl'].SSLContext = _ssl_stub.SSLContext
    sys.modules['ssl']. PURPOSE = 'SERVER_AUTH'
    sys.modules['ssl'].CERT_REQUIRED = 'CERT_REQUIRED'
    sys.modules['ssl'].CERT_OPTIONAL = 'CERT_OPTIONAL'
    sys.modules['ssl'].CERT_NONE = 'CERT_NONE'