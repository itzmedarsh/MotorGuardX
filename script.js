const temperatureElement = document.getElementById("temperature");
const currentElement = document.getElementById("current");
const rpmElement = document.getElementById("rpm");
const vibrationElement = document.getElementById("vibration");

const connectionDot = document.getElementById("connection-dot");
const connectionText = document.getElementById("connection-text");

const predictionElement = document.getElementById("prediction");
const confidenceElement = document.getElementById("confidence");
const updatedElement = document.getElementById("updated");

const statusCard = document.getElementById("statusCard");
const motorStatus = document.getElementById("motorStatus");
const statusDescription = document.getElementById("statusDescription");
const statusIcon = document.getElementById("statusIcon");

const vibrationGaugeValue =
    document.getElementById("vibrationGaugeValue");

const currentGaugeValue =
    document.getElementById("currentGaugeValue");

const vibrationNeedle =
    document.getElementById("vibrationNeedle");

const currentNeedle =
    document.getElementById("currentNeedle");

let lastDataReceived = 0;
let previousFault = "NORMAL";


function saveFault(fault, vibration, current, temperature, rpm) {

    const history = JSON.parse(
        localStorage.getItem("motorFaultHistory") || "[]"
    );

    const now = new Date();

    const time =
        now.toLocaleDateString() +
        " " +
        now.toLocaleTimeString();

    history.push({
        time: time,
        fault: fault,
        vibration: Number(vibration).toFixed(2),
        current: Number(current).toFixed(2),
        temperature: Number(temperature).toFixed(1),
        rpm: rpm
    });

    // Keep latest 100 events
    if (history.length > 100) {
        history.shift();
    }

    localStorage.setItem(
        "motorFaultHistory",
        JSON.stringify(history)
    );
}


/* =================================
   UPDATE GAUGE
================================= */

function updateGauge(value, needle, valueElement) {

    const limitedValue = Math.max(
        0,
        Math.min(2, Number(value) || 0)
    );

    // 0.0 = LEFT
    // 1.0 = TOP
    // 2.0 = RIGHT

    const angle =
        -180 + (limitedValue / 2) * 180;

    needle.style.transform =
        `rotate(${angle}deg)`;

    valueElement.textContent =
        limitedValue.toFixed(2);
}


/* =================================
   UPDATE MOTOR STATUS
================================= */

function updateMotorStatus(
    prediction,
    vibration,
    current,
    temperature,
    rpm
) {

    const fault = prediction;

    motorStatus.textContent = fault;
    predictionElement.textContent = fault;

    // Normal
    if (fault === "NORMAL") {

        statusCard.className =
            "status-card normal";

        statusIcon.textContent = "✓";

        statusDescription.textContent =
            "Motor operating within normal parameters";
    }

    // Fault
    else {

        statusCard.className =
            "status-card danger";

        statusIcon.textContent = "!";

        statusDescription.textContent =
            "AI detected: " + fault;

        // Save to fault history
        if (fault !== previousFault) {

            saveFault(
                fault,
                vibration,
                current,
                temperature,
                rpm
            );
        }
    }

    previousFault = fault;
}


/* =================================
   WEBSOCKET
================================= */

// Automatically uses:
// Local HTTP  -> ws://
// Render HTTPS -> wss://

const socketProtocol =
    window.location.protocol === "https:"
        ? "wss"
        : "ws";

const socket =
    new WebSocket(
        `${socketProtocol}://${window.location.host}/ws`
    );


socket.onopen = () => {

    console.log("✅ Connected to MotorGuard server");

    if (connectionDot) {
        connectionDot.style.background = "";
    }

    if (connectionText) {
        connectionText.textContent =
            "SYSTEM ONLINE";
    }
};


socket.onmessage = (event) => {

    try {

        const data = JSON.parse(event.data);

        lastDataReceived = Date.now();

        /* =================================
           CONNECTION
        ================================= */

        if (connectionDot) {
            connectionDot.style.background = "";
        }

        if (connectionText) {
            connectionText.textContent =
                "SYSTEM ONLINE";
        }


        /* =================================
           CONVERT VALUES TO NUMBERS
        ================================= */

        const temperature =
            Number(data.temperature);

        const current =
            Number(data.current);

        const rpm =
            Number(data.rpm);

        const vibration =
            Number(data.vibration);

        updateFanFromHardware(data.fan_status, temperature, data.overheat_tripped);


        /* =================================
           SENSOR VALUES
        ================================= */

        if (temperatureElement) {

            temperatureElement.textContent =
                temperature.toFixed(1);
        }


        if (currentElement) {

            currentElement.textContent =
                current.toFixed(2);
        }


        if (rpmElement) {

            rpmElement.textContent =
                rpm;
        }


        if (vibrationElement) {

            vibrationElement.textContent =
                vibration.toFixed(2);
        }


        /* =================================
           GAUGES
        ================================= */

        updateGauge(
            vibration,
            vibrationNeedle,
            vibrationGaugeValue
        );

        updateGauge(
            current,
            currentNeedle,
            currentGaugeValue
        );


        /* =================================
           MOTOR STATUS
        ================================= */

        updateMotorStatus(
            data.prediction,
            data.vibration,
            data.current,
            data.temperature,
            data.rpm
        );


        /* =================================
           AI PREDICTION
        ================================= */

        if (
            predictionElement &&
            data.prediction
        ) {

            predictionElement.textContent =
                data.prediction;
        }


        /* =================================
           LAST UPDATED
        ================================= */

        if (updatedElement) {

            updatedElement.textContent =
                "Just now";
        }

    } catch (error) {

        console.error(
            "❌ Invalid WebSocket data:",
            error
        );
    }
};


/* =================================
   CONNECTION TIMEOUT
================================= */

setInterval(() => {

    if (
        Date.now() - lastDataReceived > 3000
    ) {

        if (connectionDot) {

            connectionDot.style.background =
                "#777";
        }

        if (connectionText) {

            connectionText.textContent =
                "SYSTEM OFFLINE";
        }

        if (temperatureElement) {
            temperatureElement.textContent = "0.0";
        }

        if (currentElement) {
            currentElement.textContent = "0.00";
        }

        if (rpmElement) {
            rpmElement.textContent = "0";
        }

        if (vibrationElement) {
            vibrationElement.textContent = "0.00";
        }

        updateGauge(
            0,
            vibrationNeedle,
            vibrationGaugeValue
        );

        updateGauge(
            0,
            currentNeedle,
            currentGaugeValue
        );

        if (motorStatus) {
            motorStatus.textContent =
                "OFFLINE";
        }

        if (statusDescription) {
            statusDescription.textContent =
                "System is disconnected";
        }

        if (statusIcon) {
            statusIcon.textContent = "✕";
        }
    }

}, 1000);


/* =================================
   ERROR
================================= */

socket.onerror = () => {

    console.log("❌ WebSocket error");

    if (connectionDot) {

        connectionDot.style.background =
            "#777";
    }

    if (connectionText) {

        connectionText.textContent =
            "SYSTEM OFFLINE";
        markFanOffline();
    }
};


/* =================================
   CLOSED
================================= */

socket.onclose = () => {

    console.log("❌ WebSocket disconnected");

    if (connectionDot) {

        connectionDot.style.background =
            "#777";
    }

    if (connectionText) {

        connectionText.textContent =
            "SYSTEM OFFLINE";
        markFanOffline();
    }
};

/* =================================
   COOLING FAN UI — HARDWARE STATUS
   The ESP32 controls the physical fan locally.
   The dashboard only displays the reported state.
================================= */
const fanPanel = document.getElementById("fanPanel");
const fanStateElement = document.getElementById("fanState");
const fanReasonElement = document.getElementById("fanReason");
const fanTemperatureElement = document.getElementById("fanTemperature");
const fanModeBadge = document.getElementById("fanModeBadge");
const fanNote = document.getElementById("fanNote");

function updateFanFromHardware(status, temperature, overheatTripped) {
    if (!fanPanel) return;
    if (Number.isFinite(temperature)) {
        fanTemperatureElement.textContent = temperature.toFixed(1);
    }
    fanModeBadge.textContent = "ESP32 AUTO CONTROL";
    fanPanel.classList.remove("is-on", "is-warning");

    if (typeof status !== "boolean") {
        fanStateElement.textContent = "STATUS UNKNOWN";
        fanReasonElement.textContent = "ESP32 firmware update required";
        fanNote.textContent = "No physical fan status received. Temperature alone is not treated as proof that the fan is running.";
        return;
    }

    if (status) {
        fanPanel.classList.add("is-on");
        fanStateElement.textContent = "FAN RUNNING";
        fanReasonElement.textContent = overheatTripped
            ? "Overheat protection active — motor stopped, fan retained ON"
            : "ESP32 reports physical fan output ON";
    } else {
        fanStateElement.textContent = "FAN STOPPED";
        fanReasonElement.textContent = "ESP32 reports physical fan output OFF";
        if (Number.isFinite(temperature) && temperature >= 50) {
            fanPanel.classList.add("is-warning");
            fanReasonElement.textContent = "High temperature but fan reports OFF — inspect hardware";
        }
    }
    fanNote.textContent = "Automatic control is handled locally by ESP32 GPIO 26. Dashboard is read-only.";
}

function markFanOffline() {
    if (!fanPanel) return;
    fanStateElement.textContent = "NO LIVE DATA";
    fanReasonElement.textContent = "Waiting for ESP32 sensor transmission";
    fanModeBadge.textContent = "ESP32 STATUS";
    fanPanel.classList.remove("is-on", "is-warning");
}
markFanOffline();

/* =================================
   SECURITY & AUTHORIZATION PANEL
   Backend endpoint is admin-only.
================================= */
const securityNav = document.getElementById("securityNav");
const adminNav = document.getElementById("adminNav");
const securityPanel = document.getElementById("security");
const securityMessage = document.getElementById("securityMessage");
const securityEvents = document.getElementById("securityEvents");

async function loadSecurityDashboard() {
    try {
        const response = await fetch("/api/security", {
            method: "GET",
            credentials: "same-origin",
            headers: { "Accept": "application/json" }
        });

        if (response.status === 403) {
            if (securityNav) securityNav.hidden = true;
            if (securityPanel) securityPanel.hidden = true;
            if (securityMessage) securityMessage.textContent = "Security dashboard is restricted to administrators.";
            return;
        }
        if (response.status === 401) {
            window.location.href = "/login";
            return;
        }
        if (!response.ok) throw new Error(`Security API returned ${response.status}`);

        const data = await response.json();
        if (securityNav) securityNav.hidden = false;
        if (adminNav) adminNav.hidden = false;
        if (securityPanel) securityPanel.hidden = false;

        const setStatus = (id, ok, yes, no) => {
            const el = document.getElementById(id);
            if (el) {
                el.textContent = ok ? yes : no;
                el.style.color = ok ? "#62d889" : "#ed7777";
            }
        };
        setStatus("apiKeyStatus", data.api_key_configured, "CONFIGURED", "MISSING");
        setStatus("hmacStatus", data.hmac_configured, "CONFIGURED", "MISSING");
        setStatus("replayStatus", data.replay_protection, "ACTIVE", "INACTIVE");

        const rate = document.getElementById("rateLimitStatus");
        if (rate) rate.textContent = `${data.rate_limit_per_second} req/sec`;

        const overall = document.getElementById("securityOverall");
        if (overall) {
            const healthy = data.api_key_configured && data.hmac_configured && data.replay_protection;
            overall.textContent = healthy ? "PROTECTION CONFIGURED" : "CONFIGURATION WARNING";
            overall.style.color = healthy ? "#62d889" : "#edb45a";
        }

        if (securityMessage) {
            securityMessage.textContent = `Replay timestamp window: ${data.timestamp_window_seconds} seconds. Security configuration is read-only from this dashboard.`;
        }
        if (securityEvents) {
            securityEvents.textContent = Array.isArray(data.recent_events) && data.recent_events.length
                ? data.recent_events.join("\\n")
                : "No security events have been logged yet.";
        }
    } catch (error) {
        console.error("Unable to load security dashboard:", error);
        if (securityMessage) securityMessage.textContent = "Unable to retrieve security information. Check the server and try again.";
        if (securityEvents) securityEvents.textContent = String(error.message || error);
    }
}

const refreshSecurityButton = document.getElementById("refreshSecurity");
if (refreshSecurityButton) refreshSecurityButton.addEventListener("click", loadSecurityDashboard);
loadSecurityDashboard();
