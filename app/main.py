from fastapi import FastAPI
from pydantic import BaseModel
import requests
import os
import time
import base64

app = FastAPI()

serial_number = os.getenv('SERIAL_NUMBER', 'SIMULATOR0001')
part_number = os.getenv('PART_NUMBER', '1529455-01-D')
tasmota_ip = os.getenv('TASMOTA_IP', '172.16.90.72')
START_TIME = time.time()
session_start_energy_kwh = None
session_start_time = None

class Vitals(BaseModel):
    contactor_closed: bool
    vehicle_connected: bool
    session_s: int
    grid_v: float
    grid_hz: float
    vehicle_current_a: float
    currentA_a: float
    currentB_a: float
    currentC_a: float
    currentN_a: float
    voltageA_v: float
    voltageB_v: float
    voltageC_v: float
    relay_coil_v: float
    pcba_temp_c: float
    handle_temp_c: float
    mcu_temp_c: float
    uptime_s: int
    input_thermopile_uv: int
    prox_v: float
    pilot_high_v: float
    pilot_low_v: float
    session_energy_wh: float
    config_status: int
    evse_state: int
    current_alerts: list

class Version(BaseModel):
    firmware_version: str
    part_number: str
    serial_number: str

class Lifetime(BaseModel):
    contactor_cycles: int
    contactor_cycles_loaded: int
    alert_count: int
    thermal_foldbacks: int
    avg_startup_temp: float
    charge_starts: int
    energy_wh: float
    connector_cycles: int
    uptime_s: int
    charging_time_s: int

class WifiStatus(BaseModel):
    wifi_ssid: str
    wifi_signal_strength: int
    wifi_rssi: int
    wifi_snr: int
    wifi_connected: bool
    wifi_infra_ip: str
    internet: bool
    wifi_mac: str


def fetch_tasmota_status():
    """Single Status 0 call to Tasmota. Raises on failure."""
    response = requests.get(f"http://{tasmota_ip}/cm?cmnd=Status%200", timeout=2)
    response.raise_for_status()
    return response.json()

def get_tasmota_status():
    """Best-effort version for lifetime/wifi_status — returns {} on failure
    rather than raising, since those endpoints can degrade gracefully."""
    try:
        return fetch_tasmota_status()
    except Exception:
        return {}

@app.get("/api/1/vitals")
async def get_vitals():
    global session_start_energy_kwh, session_start_time
    try:
        data = fetch_tasmota_status()
    except requests.RequestException as e:
        return {"error": f"Error fetching data from Tasmota device: {e}"}
    energy = data.get("StatusSNS", {}).get("ENERGY", {})
    current = energy.get("Current", 0)
    charging = current > 4.5
    connected = str(data.get("Status", {}).get("Power")) == "1"
    mcu_temp = data.get("StatusSNS", {}).get("ESP32", {}).get("Temperature", 15.2)
    grid_voltage = energy.get("Voltage", 0) or 229.2
    voltage_a = energy.get("Voltage", 0) or 10
    current_a = current or 0.60

    total_kwh = energy.get("Total", 0)
    if connected and session_start_energy_kwh is None:
        # Session just started — record the baseline
        session_start_energy_kwh = total_kwh
        session_start_time = time.time()
    elif not connected:
        # Session ended (or never started) — clear the baseline
        session_start_energy_kwh = None
        session_start_time = None

    if session_start_energy_kwh is not None:
        session_energy_wh = round((total_kwh - session_start_energy_kwh) * 1000, 1)
        session_s = int(time.time() - session_start_time)
    else:
        session_energy_wh = 0.0
        session_s = 0
    
    if not connected:
        evse_state = 1
    elif connected and not charging:
        evse_state = 8 if session_energy_wh > 0 else 4
    else:
        evse_state = 11
        
    return Vitals(
        contactor_closed=charging,
        vehicle_connected=connected,
        session_s=session_s,
        grid_v=grid_voltage,
        grid_hz=49.828,
        vehicle_current_a=current,
        currentA_a=current_a,
        currentB_a=0.30,
        currentC_a=0.0,
        currentN_a=0.0,
        voltageA_v=voltage_a,
        voltageB_v=0.0,
        voltageC_v=0.0,
        relay_coil_v=11.9,
        pcba_temp_c=mcu_temp,
        handle_temp_c=1.8,
        mcu_temp_c=mcu_temp,
        uptime_s=26103,
        input_thermopile_uv=-176,
        prox_v=0.0,
        pilot_high_v=11.9,
        pilot_low_v=11.8,
        session_energy_wh=session_energy_wh,
        config_status=5,
        evse_state=evse_state,
        current_alerts=[]
    )

@app.get("/api/1/version")
async def version():
    return Version(
        firmware_version="24.44.3",
        part_number=part_number,
        serial_number=serial_number,
    )

@app.get("/api/1/lifetime")
async def lifetime():
    status = get_tasmota_status()
    energy_kwh = status.get("StatusSNS", {}).get("ENERGY", {}).get("Total", 0)
    return Lifetime(
        contactor_cycles=0,
        contactor_cycles_loaded=0,
        alert_count=0,
        thermal_foldbacks=0,
        avg_startup_temp=25.0,
        charge_starts=0,
        energy_wh=round(energy_kwh * 1000, 1),
        connector_cycles=0,
        uptime_s=int(time.time() - START_TIME),
        charging_time_s=0,
    )

@app.get("/api/1/wifi_status")
async def wifi_status():
    status = get_tasmota_status()
    wifi = status.get("StatusSTS", {}).get("Wifi", {})
    net = status.get("StatusNET", {})
    ssid = wifi.get("SSId", "")
    return WifiStatus(
        wifi_ssid=base64.b64encode(ssid.encode()).decode(),
        wifi_signal_strength=wifi.get("RSSI", 0),
        wifi_rssi=wifi.get("Signal", 0),
        wifi_snr=40,
        wifi_connected=bool(wifi.get("AP", 0)),
        wifi_infra_ip=net.get("IPAddress", "0.0.0.0"),
        internet=True,
        wifi_mac=net.get("Mac", "00:00:00:00:00:00"),
    )
