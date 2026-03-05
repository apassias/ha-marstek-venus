# Marstek Venus (Local UDP) — Home Assistant integration (HACS)

Local (no-cloud) integration for **Marstek VenusE / VenusC** batteries using the **local UDP JSON-RPC API** (default port `30000`).

## What this integration does

- **Wizard setup**: finds devices automatically (broadcast scan), with fallback subnet scan
- **Multi-battery**: manage multiple Venus devices in one integration entry
- **Stable polling**: `DataUpdateCoordinator` (default 60s; configurable)
- **Energy dashboard ready**: grid import/export energy sensors in **kWh**
- Battery status (SOC, temperature, charge/discharge flags)
- Meter powers (phase A/B/C + total)
- Wi‑Fi diagnostics (SSID, RSSI, IP, MAC)
- Mode control (Auto / AI / Manual / Passive)
- Services to set Passive power or Manual time slots

## Install (HACS custom repository)

1. Home Assistant → **HACS** → **Integrations**
2. Top-right **⋮** → **Custom repositories**
3. Add this repository URL, type **Integration**
4. Install **Marstek Venus (Local UDP)**
5. Restart Home Assistant

## Setup

Home Assistant → **Settings** → **Devices & Services** → **Add integration** → **Marstek Venus (Local UDP)**

The wizard offers:
- **Broadcast scan** (fast) — recommended
- **Subnet scan** (fallback) — use when broadcast is blocked (e.g. `192.168.11.0/24`)

Select one or multiple devices and finish.

### Add / remove devices later
Settings → Devices & Services → Marstek Venus (Local UDP) → **Configure** (Options)

## Energy Dashboard (Grid)

Settings → Dashboards → Energy → Electricity grid:

- **Grid consumption**: `… Grid Import Energy (kWh)`
- **Return to grid**: `… Grid Export Energy (kWh)`

### Energy units / scaling
On VenusE 3.0, `EM.GetStatus` energy counters (`input_energy`, `output_energy`) behave like **0.1 Wh units**.
This integration converts to **kWh** with:

`kWh = counter / (energy_units_per_wh * 1000)`

Default `energy_units_per_wh = 10.0` (i.e. 10 units = 1 Wh).
You can change this in Options if your firmware differs.

## Troubleshooting

- If discovery finds nothing:
  - try **Subnet scan**
  - ensure the battery and Home Assistant are on the same LAN/VLAN and UDP is allowed
  - verify the UDP port (default `30000`)

- If you see timeouts:
  - increase the polling interval (Options → Poll interval)

## Local API reference
This integration is based on Marstek’s “Device Open API” (UDP JSON-RPC).
