
import os
import json
import time
import uuid
import hmac
import hashlib
import urllib.request
import urllib.error

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MOTORGUARD_API_KEY")
HMAC_SECRET = os.getenv("MOTORGUARD_HMAC_SECRET")

if not API_KEY or not HMAC_SECRET:
    raise RuntimeError("API key or HMAC secret missing from .env")


# Sensor data
data = {
    "temperature": 35,
    "current": 2,
    "rpm": 1450,
    "vibration": 1.8
}

body = json.dumps(data).encode()

# Timestamp and unique request ID
timestamp = str(int(time.time()))
nonce = str(uuid.uuid4())

# Generate HMAC-SHA256 signature using separate secret
message = f"{timestamp}.{nonce}.".encode() + body

signature = hmac.new(
    HMAC_SECRET.encode(),
    message,
    hashlib.sha256
).hexdigest()

# Request headers
headers = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
    "X-Timestamp": timestamp,
    "X-Nonce": nonce,
    "X-Signature": signature
}


def send_request():
    request = urllib.request.Request(
        "http://localhost:5001/data",
        data=body,
        headers=headers,
        method="POST"
    )

    try:
        response = urllib.request.urlopen(request)
        print("HTTP:", response.status)
        print(response.read().decode())

    except urllib.error.HTTPError as error:
        print("HTTP:", error.code)
        print(error.read().decode())


print("\nMOTORGUARD ENDPOINT SECURITY TEST\n")

print("TEST 1: Original signed request")
send_request()

print("\nTEST 2: Replay the exact same request")
send_request()
