import asyncio
import json
import math
import os
from collections import deque
from security import security_middleware, validate_sensor_data
import aiohttp_session
import aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography.fernet import Fernet
from auth import auth_middleware, register_auth_routes
import joblib
from aiohttp import web
from aiohttp_session import get_session

# ================= MODEL =================

model = joblib.load("modelDecision.pkl")

# ================= CLIENTS =================

clients = set()

# ================= SENSOR BUFFERS =================

vibration_buffer = deque(maxlen=10)
current_buffer = deque(maxlen=10)


# ================= FEATURES =================

def calculate_features():

    if len(vibration_buffer) < 10:
        return None

    if len(current_buffer) < 10:
        return None

    vib = list(vibration_buffer)
    cur = list(current_buffer)

    # Vibration
    vib_mean = sum(vib) / len(vib)

    vib_rms = math.sqrt(
        sum(x * x for x in vib) / len(vib)
    )

    vib_std = math.sqrt(
        sum((x - vib_mean) ** 2 for x in vib) / len(vib)
    )

    # Current
    current_mean = sum(cur) / len(cur)

    current_rms = math.sqrt(
        sum(x * x for x in cur) / len(cur)
    )

    current_std = math.sqrt(
        sum((x - current_mean) ** 2 for x in cur) / len(cur)
    )

    return (
        vib_rms,
        vib_mean,
        vib_std,
        current_rms,
        current_mean,
        current_std
    )


# ================= ESP32 DATA =================

async def receive_esp32(request):

    try:

        data = await request.json()
        is_valid, message = validate_sensor_data(data)

        if not is_valid:
            return web.json_response(
        {"status": "error", "message": message},
        status=400
        )

        temperature = float(data["temperature"])
        current = float(data["current"])
        rpm = float(data["rpm"])
        vibration = float(data["vibration"])

        vibration_buffer.append(vibration)
        current_buffer.append(current)

        features = calculate_features()

        if features is None:

            prediction = "CALIBRATING"

        else:

            (
                vib_rms,
                vib_mean,
                vib_std,
                current_rms,
                current_mean,
                current_std
            ) = features

            model_input = [[
                vib_rms,
                vib_mean,
                vib_std,
                current_rms,
                current_mean,
                current_std,
                rpm,
                temperature
            ]]

            prediction = model.predict(model_input)[0]

        # Fan status is reported by the ESP32 hardware, not inferred here.
        fan_status = data.get("fan_status")
        if not isinstance(fan_status, bool):
            fan_status = None

        dashboard_data = {
            "temperature": round(temperature, 1),
            "current": round(current, 2),
            "rpm": round(rpm),
            "vibration": round(vibration, 2),
            "prediction": str(prediction),
            "fan_status": fan_status,
            "overheat_tripped": bool(data.get("overheat_tripped", False))
        }

        if features is not None:

            dashboard_data.update({
                "vib_rms": round(vib_rms, 3),
                "vib_mean": round(vib_mean, 3),
                "vib_std": round(vib_std, 3),
                "current_rms": round(current_rms, 3),
                "current_mean": round(current_mean, 3),
                "current_std": round(current_std, 3)
            })

        print(
            f"Temp: {temperature:.1f} | "
            f"Current: {current:.2f} | "
            f"RPM: {rpm:.0f} | "
            f"Vibration: {vibration:.2f} | "
            f"Fan: {'ON' if fan_status else 'OFF' if fan_status is False else 'UNKNOWN'} | "
            f"Prediction: {prediction}"
        )

        # Send to all dashboards
        if clients:

            message = json.dumps(dashboard_data)

            await asyncio.gather(
                *(client.send_str(message) for client in clients),
                return_exceptions=True
            )

        return web.json_response({
            "status": "ok",
            "prediction": str(prediction)
        })

    except Exception as e:

        print("ESP32 ERROR:", e)

        return web.json_response(
            {
                "status": "error",
                "message": str(e)
            },
            status=500
        )


# ================= WEBSOCKET =================

async def websocket_handler(request):

    ws = web.WebSocketResponse()

    await ws.prepare(request)

    clients.add(ws)

    print("Dashboard connected!")

    try:

        async for msg in ws:

            pass

    finally:

        clients.discard(ws)

        print("Dashboard disconnected!")

    return ws


# ================= HEALTH CHECK =================

async def health(request):

    return web.json_response({
        "status": "MotorGuard online"
    })


# ================= STATIC FILES =================

async def index(request):

    return web.FileResponse("web.html")



# ================= SECURITY DASHBOARD API =================

async def security_dashboard_api(request):
    session = await get_session(request)
    if session.get("role") != "admin":
        raise web.HTTPForbidden(text="Administrator access required")

    from security import API_KEY, HMAC_SECRET, REQUEST_LIMIT, MAX_TIME_DIFFERENCE, used_nonces
    from pathlib import Path

    log_path = Path("security.log")
    events = []
    if log_path.exists():
        try:
            events = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
        except OSError:
            events = ["Unable to read security log."]

    return web.json_response({
        "api_key_configured": bool(API_KEY),
        "hmac_configured": bool(HMAC_SECRET),
        "replay_protection": True,
        "timestamp_window_seconds": MAX_TIME_DIFFERENCE,
        "rate_limit_per_second": REQUEST_LIMIT,
        "recent_events": events
    })


# ================= MAIN =================


async def main():

    # ================= SESSION CONFIGURATION =================

    session_secret = os.getenv("SESSION_SECRET")

    if not session_secret:
        raise RuntimeError("SESSION_SECRET is missing")

    # ================= APPLICATION SETUP =================

    app = web.Application(
    middlewares=[
        security_middleware,

        aiohttp_session.session_middleware(
            EncryptedCookieStorage(
                Fernet(session_secret.encode()),
                secure=os.getenv(
                    "COOKIE_SECURE", "false"
                ).lower() == "true"
            )
        ),

        auth_middleware
    ]
)

    # ================= AUTHENTICATION ROUTES =================

    register_auth_routes(app)

    # ================= ESP32 SENSOR DATA =================

    app.router.add_post(
        "/data",
        receive_esp32
    )

    # ================= DASHBOARD WEBSOCKET =================

    app.router.add_get(
        "/ws",
        websocket_handler
    )

    # ================= HEALTH CHECK =================

    app.router.add_get(
        "/health",
        health
    )

    # Admin-only security dashboard data
    app.router.add_get(
        "/api/security",
        security_dashboard_api
    )

    # ================= DASHBOARD PAGE =================

    app.router.add_get(
        "/",
        index
    )

    # ================= STATIC FILES =================

    app.router.add_static(
    "/static/",
    "./static",
    show_index=False
)

    # ================= SERVER CONFIGURATION =================

    port = int(os.environ.get("PORT", 5001))

    print("================================")
    print("MotorGuard Cloud Server")
    print("================================")
    print(f"Listening on port: {port}")
    print("Login endpoint: /login")
    print("Dashboard endpoint: /")
    print("ESP32 endpoint: /data")
    print("WebSocket endpoint: /ws")
    print("Health endpoint: /health")
    print("================================")

    # ================= START SERVER =================

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()

    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
