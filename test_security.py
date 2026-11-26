
import os
import json
import time
import uuid
import hmac
import hashlib

from dotenv import load_dotenv
from security import verify_request_signature

load_dotenv()

API_KEY = os.getenv("MOTORGUARD_API_KEY")

if not API_KEY:
    raise RuntimeError("API key missing from .env")


def create_signature(timestamp, nonce, body):
    message = f"{timestamp}.{nonce}.".encode() + body

    return hmac.new(
        API_KEY.encode(),
        message,
        hashlib.sha256
    ).hexdigest()


print("\nMOTORGUARD SECURITY TESTS\n")

# TEST 1: Valid request
timestamp = str(int(time.time()))
nonce = str(uuid.uuid4())

data = {
    "temperature": 55,
    "current": 4.5,
    "rpm": 1400,
    "vibration": 2.1
}

body = json.dumps(data).encode()
signature = create_signature(timestamp, nonce, body)

result = verify_request_signature(
    timestamp, nonce, signature, body
)

print("Test 1 - Valid request:", "PASS" if result else "FAIL")


# TEST 2: Replay same request
result = verify_request_signature(
    timestamp, nonce, signature, body
)

print("Test 2 - Replayed request:", "PASS" if not result else "FAIL")


# TEST 3: Modified sensor data
new_nonce = str(uuid.uuid4())
modified_body = json.dumps({
    "temperature": 25,
    "current": 4.5,
    "rpm": 1400,
    "vibration": 2.1
}).encode()

result = verify_request_signature(
    timestamp,
    new_nonce,
    signature,
    modified_body
)

print("Test 3 - Modified data:", "PASS" if not result else "FAIL")


# TEST 4: Expired timestamp
old_timestamp = str(int(time.time()) - 120)
old_nonce = str(uuid.uuid4())

old_signature = create_signature(
    old_timestamp, old_nonce, body
)

result = verify_request_signature(
    old_timestamp,
    old_nonce,
    old_signature,
    body
)

print("Test 4 - Expired request:", "PASS" if not result else "FAIL")
