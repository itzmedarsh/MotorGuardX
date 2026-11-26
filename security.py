
import os
import math
import time
import hmac
import hashlib
import threading

from collections import defaultdict, deque
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MOTORGUARD_API_KEY")
HMAC_SECRET = os.getenv("MOTORGUARD_HMAC_SECRET")

# ================= RATE LIMITING =================

REQUEST_LIMIT = 5
TIME_WINDOW = 1

request_history = defaultdict(deque)


def check_rate_limit(client_ip):
    now = time.monotonic()
    requests = request_history[client_ip]

    while requests and now - requests[0] >= TIME_WINDOW:
        requests.popleft()

    if len(requests) >= REQUEST_LIMIT:
        return False

    requests.append(now)
    return True


# ================= REPLAY PROTECTION =================

MAX_TIME_DIFFERENCE = 60
MAX_NONCES = 10000

used_nonces = {}
nonce_lock = threading.Lock()


def verify_request_signature(timestamp, nonce, signature, body):

    if not timestamp or not nonce or not signature:
        return False

    if len(nonce) > 128 or len(signature) != 64:
        return False

    try:
        request_time = int(timestamp)
    except (TypeError, ValueError):
        return False

    current_time = int(time.time())

    if abs(current_time - request_time) > MAX_TIME_DIFFERENCE:
        return False

    message = f"{timestamp}.{nonce}.".encode() + body

    if not HMAC_SECRET:
        return False

    expected_signature = hmac.new(
        HMAC_SECRET.encode(),
        message,
        hashlib.sha256
    )   .hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        return False

    with nonce_lock:

        expired = [
            key for key, expiry in used_nonces.items()
            if expiry < current_time
        ]

        for key in expired:
            del used_nonces[key]

        if nonce in used_nonces:
            return False

        if len(used_nonces) >= MAX_NONCES:
            return False

        used_nonces[nonce] = request_time + MAX_TIME_DIFFERENCE

    return True


# ================= SENSOR VALIDATION =================

def validate_sensor_data(data):

    if not isinstance(data, dict):
        return False, "Invalid JSON object"

    required_fields = [
        "temperature",
        "current",
        "rpm",
        "vibration"
    ]

    for field in required_fields:

        if field not in data:
            return False, f"Missing field: {field}"

        try:
            value = float(data[field])
        except (TypeError, ValueError):
            return False, f"Invalid value: {field}"

        if not math.isfinite(value):
            return False, f"Non-finite value: {field}"

    temperature = float(data["temperature"])
    current = float(data["current"])
    rpm = float(data["rpm"])
    vibration = float(data["vibration"])

    if not -20 <= temperature <= 150:
        return False, "Temperature outside allowed range"

    if not 0 <= current <= 100:
        return False, "Current outside allowed range"

    if not 0 <= rpm <= 10000:
        return False, "RPM outside allowed range"

    if not 0 <= vibration <= 100:
        return False, "Vibration outside allowed range"

    if "fan_status" in data and not isinstance(data["fan_status"], bool):
        return False, "Invalid value: fan_status must be boolean"

    if "overheat_tripped" in data and not isinstance(data["overheat_tripped"], bool):
        return False, "Invalid value: overheat_tripped must be boolean"

    return True, "Valid"


# ================= SECURITY MIDDLEWARE =================

@web.middleware
async def security_middleware(request, handler):

    if request.path == "/health":
        return await handler(request)

    if request.path == "/data":

        if not API_KEY:
            return web.json_response(
                {"error": "Server security configuration error"},
                status=503
            )

        supplied_key = request.headers.get("X-API-Key", "")

        if not hmac.compare_digest(supplied_key, API_KEY):
            return web.json_response(
                {"error": "Unauthorized"},
                status=401
            )

        client_ip = request.remote or "unknown"

        if not check_rate_limit(client_ip):
            return web.json_response(
                {"error": "Too many requests"},
                status=429
            )

        body = await request.read()

        valid_signature = verify_request_signature(
            request.headers.get("X-Timestamp"),
            request.headers.get("X-Nonce"),
            request.headers.get("X-Signature"),
            body
        )

        if not valid_signature:
            return web.json_response(
                {"error": "Invalid signature or replayed request"},
                status=401
            )

        request["raw_body"] = body

    return await handler(request)
