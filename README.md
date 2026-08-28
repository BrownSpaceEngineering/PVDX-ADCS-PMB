# PVDX-ADCS-PMB
Combined ADCS actuation and Perovskite Measurement Board. Drives magnetorquers for attitude control and performs IV-sweep measurement of the perovskite solar cell payload.

## Status
- Design phase: Ready for review
- Current rev: rev-1.0
- Contributors: Nick Cavallo, Kelly Lin, Brandon Montoya

## System overview
This board serves two subsystems on one physical PCB:

- **ADCS (Attitude Determination and Control System)**: drives the magnetorquers used for attitude control, via H-bridge drivers.
- **PMB (Perovskite Measurement Board)**: performs IV-sweep characterization of the perovskite payload cells (pixels PX01–PX16 across devices DV01–DV04), amplifying photodiode signal and switching between measurement channels.

**Board sheets:**
- **Connectors** — Pin assignments for all board connectors: magnetorquers (MTQ), perovskite devices (PVK), and photodiodes (PD).
- **Magnetorquers** — Magnetorquer drive circuitry, built around DRV8837C H-bridge drivers.
- **Perovskites** — Perovskite cell IV-sweep measurement path, using INA226 current-sense for the current side of the sweep. Cell parameters this circuit is designed against: Isc = 5 mA, Voc = 1.1 V, sweep range 0–1.2 V, RSH1 = 10 Ω.
- **Photodiodes** — Photodiode signal amplification via TLV9001 op-amp, with ADG734BRUZ analog mux for channel switching between pixels.

### Repo layout
```
PVDX-ADCS-PMB/
├── PVDX-ADCS-PMB.kicad_pro / .kicad_sch / .kicad_pcb / .step
├── fp-lib-table, sym-lib-table, design-block-lib-table
├── schematics/          # sub-sheets
│   ├── connectors.kicad_sch
│   ├── magnetorquers.kicad_sch
│   ├── perovskites.kicad_sch
│   └── photodiodes.kicad_sch
├── libs/
│   ├── footprints.pretty/
│   ├── symbols/
│   ├── 3dmodels/
│   └── Library.kicad_blocks/
│       └── MTQ_Driver.kicad_block/   # deprecated
└── manufacturing/       # not yet created — pre-fab
```

## Key design notes
- **Sweep range narrowed to 0–1.2V (from originally spec'd -0.2–1.2V)**: simplifies the voltage control chain to single-supply operation — no negative rail needed for the DAC/opamp reference path.
- **Pixel selection via MCP23017 + ADG734 switches**: MCU sets one of 16 MCP23017 GPIO pins high over I2C to route that pixel's positive terminal to the measurement subcircuit. All other pixels are simultaneously routed through resistors to ground via the same ADG734 switches, so idle pixels have a defined thermal/electrical path (cooling) rather than floating while unmeasured.
- **Voltage control decouples DAC range from cell range**: DAC output spans 0–3.3V; a voltage divider steps this down to the cell's 0–1.2V operating range, and the TLV9001 opamp sources/sinks whatever current the pixel needs to actually hold that divided setpoint. This avoids needing a dedicated low-voltage DAC — tradeoff is the opamp must supply the full sweep current (up to 5mA design max) at low output impedance.
- **Current/voltage reading via INA226 shunt, not a dedicated current-sense element**: current is inferred from shunt voltage across a 10Ω shunt resistor, consistent with the confirmed RSH1 = 10Ω cell parameter. Design current range: 5mA max, 2–3mA expected typical.
- **Fixed I2C addresses**: MCP23017 at `0b0100000`, INA226 at `0b1000000` (address-pin strapped) — confirm no collisions with other devices sharing this board's I2C bus before finalizing layout.
- **4-layer stackup**: F.Cu (digital), In1.Cu (GND plane), In2.Cu (+3V3 plane), B.Cu (analog) — keeps the INA226 shunt-reading path referenced to the internal GND plane rather than sharing a layer with ADG734 switching noise.
- **Manual routing over autorouting**: FreeRouting v2.3.0 proved unreliable for this board's density/isolation requirements; routing is done by hand.
- **KiCad 10 Design Blocks unreliable for layout replication**: `MTQ_Driver` Design Block is reused at the schematic level only; PCB-side placement is manual (Swap command), not trusted to Design Block replication.
## Manufacturing history
No revisions manufactured yet — board is in layout.

## Open items
- _SPICE the PD amplifier circuit to verify gain_
- Design review for layout
- Generate Gerbers
- Send out for fab
