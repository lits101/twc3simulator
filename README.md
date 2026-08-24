# twc3simulator (Tesla Wall Connector 3 Simulator)

Fakes the API responses of a real Tesla Wall Connector 3, using live current, energy, and network data pulled from a Tasmota smart plug wired into the circuit. It doesn't control anything — it's a read-only stand-in that lets software expecting a "real" TWC3 (like evcc or Home Assistant) work with a Tesla Universal Mobile Connector (or any other dumb charger) instead.

<img width="836" height="584" alt="UMC" src="https://github.com/user-attachments/assets/33b68e9f-87c4-4ebe-9231-d9f81c4afd02" />

## Credit

This is a fork of [laenglea/twc3simulator](https://github.com/laenglea/twc3simulator) — all credit for the original idea and implementation goes to [@laenglea](https://github.com/laenglea), who built this after finding evcc had no way to control charging through a Universal Mobile Connector. 

## What this fork adds

I basically just wanted my UMC to display in Home Assistant. This fork extends langlea's original idea to work with Home Assistant's Tesla Wall Connector integration, which polls a few endpoints beyond what evcc needs. 

- **`/api/1/version`** — static device identity (firmware/part/serial number). HA's config flow reads these during setup and fails if the endpoint is missing.
- **`/api/1/lifetime`** — cumulative energy, sourced from the Tasmota device's own running total (`Status 0` → `StatusSNS.ENERGY.Total`), converted from kWh to Wh.
- **`/api/1/wifi_status`** — Wi-Fi connection details, sourced from the Tasmota device's own network status (`Status 0` → `StatusSTS.Wifi` and `StatusNET`) rather than static placeholders — since the Tasmota is the thing actually connected to your network, its real signal strength, IP, and MAC are more honest than making something up.

All three reuse a single `Status 0` call to the Tasmota device rather than hitting it separately per endpoint.

## Requirements

- A Tasmota outlet or smart relay, connected to your dumb charger of choice. I use a Sonoff POWR320D (20 amp) relay, flashed with Tasmota.

* To extract a temperature value for pcba_temp_c, your Tasmota device will require an on-board temperature sensor. In my case, the POWR320D has this, which can be enabled by running: `curl "http://tasmota_ip/cm?cmnd=SetOption146%201"`. Your mileage may vary. 

## Installation

This fork isn't published as a prebuilt image — build it from source.

Clone it to the machine you want to run it on:

    git clone https://github.com/lits101/twc3simulator.git

Then build and run via docker compose:

    services:
      twc3sim:
        container_name: twc3sim
        build: ./twc3simulator
        environment:
          - "TASMOTA_IP=10.10.10.10"
        ports:
          - "80:80"
        restart: unless-stopped

where `TASMOTA_IP` is the IP of the Tasmota device the current/energy/wifi information should come from.

Or build directly from GitHub without a local clone:

    services:
      twc3sim:
        container_name: twc3sim
        build: https://github.com/lits101/twc3simulator.git#main
        environment:
          - "TASMOTA_IP=10.10.10.10"
        ports:
          - "80:80"
        restart: unless-stopped

You can also include environment variables for the serial number and part number of your UMC, and these will be passed through to Home Assistant if specified. 

```
environment:
  - SERIAL_NUMBER=<your UMC2's actual serial number>
  - PART_NUMBER=<your UMC2's actual part number>
```

## Validate

if it's running properly you should get something back when looking at each of:

    http://<ip>/api/1/vitals
    http://<ip>/api/1/lifetime
    http://<ip>/api/1/version
    http://<ip>/api/1/wifi_status
