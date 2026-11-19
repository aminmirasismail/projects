# Hub v5: bill of materials

Everything needed to build the v5 hub (concept D, underglow) from nothing. The Pi 5 price was
checked against live listings on 2026-11-19; the rest are rough US estimates (memory-chip
shortages have pushed up Pi and SD card prices this year), so check before ordering.

## Electronics

| # | Part | Spec / what to search for | Qty | Approx. |
|---|---|---|---|---|
| 1 | Raspberry Pi 5, **4 GB** (SC1111), board only | Headroom for later devices (camera doorbell, local voice, add-ons); RAM can't be upgraded. Buy from an official reseller: CanaKit had it in stock at list price on 2026-11-19 (Adafruit $130, PiShop out). 2 GB ($77.50) is Home Assistant's minimum and would do for sensor-type devices only; 1 GB is below it. Avoid marketplace listings above list price | 1 | $110 |
| 2 | Raspberry Pi 5 Active Cooler | official one; the case is designed around it | 1 | $5 |
| 3 | Raspberry Pi 27 W USB-C power supply | **official 27 W (5.1 V 5 A)**: the LEDs and ESP32 run off the Pi's 5 V, so a 3 A supply would brown out | 1 | $12 |
| 4 | microSD card, 64 GB high endurance | SanDisk High Endurance or Samsung PRO Endurance | 1 | $12 |
| 5 | Ethernet cable, 0.5–1 m | hub to router | 1 | $5 |
| 6 | Addressable RGBW LED strip | **SK6812 RGBW, 5 V, 144 LEDs/m, 12 mm wide, white PCB, IP30 (no silicone)**, white channel warm (~3000 K) or natural (~4000 K). Uses 34 LEDs in 4 runs of 7 + 10 + 7 + 10 (0.24 m); 1 m is the usual minimum | 1 m | $15–25 |
| 7 | ESP32-C3 SuperMini | 22.5 × 18 mm, USB-C; runs ESPHome and drives the strip. Usually sold in 2–3 packs | 1 (pack) | $8 |
| 8 | Level shifter, **74AHCT1G125** (single gate, SOT-23-5) | 3.3 V data to the 5 V strip. Wired in line in the data wire under heat-shrink: pin 1 (/OE) to GND, pin 2 input from the ESP32, pin 4 output, pin 5 to 5 V, pin 3 GND | 2 (spare) | $2 |
| 8a | SOT-23 to DIP adapter boards | so the tiny chip can be soldered by hand | 1 pack | $5 |
| 8b | Ceramic capacitor, 0.1 µF | decoupling across the level shifter's 5 V / GND | 1 | $1 (kit) |
| 9 | Electrolytic capacitor, **470 µF, 10 V, 6.3 × 11 mm** | across the strip's 5 V / GND; sits in the saddle beside the ESP32 | 1 | $1 |
| 10 | Resistor, 330 Ω, ¼ W | in the data line, at the strip end | 1 | $1 (kit) |
| 11 | Female pin header, 2.54 mm, 1 × 40 | cut a 1 × 2 piece; plugs onto the Pi's **pins 4 (5 V) and 6 (GND)**, which sit next to each other; wires soldered to its tails | 1 strip | $2 |
| 12 | Silicone hook-up wire, 28 AWG, 3 colours | strip corner jumpers and data (28 AWG so three fit each 4.1 mm corner bay) | 1 set | $10 |
| 13 | Silicone hook-up wire, 22–24 AWG, red + black | 5 V / GND from the Pi to the ESP32 and strip | 1 set | (in 12 if a mixed kit) |
| 14 | Heat-shrink tubing assortment, 1.5–3 mm | covers every joint | 1 kit | $6 |

## Hardware

| # | Part | Spec | Qty | Approx. |
|---|---|---|---|---|
| 15 | Heat-set inserts M3 × 5.7 mm, OD 4.6 mm | Ruthex or CNC Kitchen "standard" M3; the holes are sized for these | 4 (kit) | $8 |
| 16 | **M3 × 10** button-head hex screws (ISO 7380), black | plinth, frame and floor into the shell; heads sit flush in the plinth, under the diffuser | 4 | $6 (pack) |
| 17 | M2.5 × 6 socket or pan-head screws | Pi into the floor's standoffs | 4 | $6 (pack) |
| 18 | 3M Bumpon SJ5302 feet (7.9 × 2.2 mm) | sit in the recesses in the 4 pads; raise the hub 0.4 mm | 4 | $5 (pack) |
| 18a | Black hot-glue sticks (or black silicone) | seals the wire hole round the strip wires (light trap) | a few | $5 |

## Filament

| # | Part | Spec | Qty | Approx. |
|---|---|---|---|---|
| 19 | White PLA (Bambu PLA Matte, the spool synced to your printer) | shell about 55 g + diffuser about 3 g | 1 kg | $20 |
| 20 | Black PLA (any; load and sync it in Bambu Studio before slicing) | plinth + frame about 22 g, floor about 17 g | 1 kg | $20 |

Parts total (without filament): about $210–230.

## Tools (skip whatever you already have)

| Tool | Why | Approx. |
|---|---|---|
| Temperature-controlled soldering iron (e.g. Pinecil V2 + a 65 W USB-C PD charger) | strip corner jumpers, ESP32, level shifter, header | $26 + $20 |
| Heat-set insert tip set for that iron (M3) | presses the inserts straight and to depth | $10–15 |
| Solder 0.6–0.8 mm rosin core + flux pen + brass tip cleaner | small pads on the strip and the ESP32 | $15 |
| Wire strippers (20–30 AWG) + flush cutters | wires, cutting the strip at its cut marks | $15 |
| Tweezers + helping hands | holding wires on the strip pads | $10 |
| Small heat gun (or a lighter, carefully) | heat-shrink | $15 |
| 2 mm hex driver (or key) | M3 button heads; M2.5 socket heads take 2 mm too (pan heads: #1 Phillips) | $5 |
| Multimeter | continuity and polarity check before power-on | $20 |
| Mini hot-glue gun | holds the ESP32 in its slot and tidies wires | $10 |
| microSD card reader | flashing Home Assistant OS (if your PC has no slot) | $8 |
| USB-C data cable | flashing ESPHome onto the ESP32 from your PC | $5 |
| Digital calipers | checking prints and fits (also for the skin coupons) | $20 |
| Hobby knife / deburring tool | cleaning print edges | $8 |

## Notes

- The plinth and floor come off together with the ESP32 and the strip still wired, so no connector is
  needed between them.
- Software is free: Raspberry Pi Imager (Home Assistant OS) and ESPHome (inside Home Assistant).
  34 LEDs at full RGBW would draw about 2.5 A (white channel alone about 0.7 A), hence the cap below.
- Fit the level shifter: the strip may misread 3.3 V data at 5 V.
- **Power cap: about 0.5 A.** ESPHome has no current setting, so set `max_brightness` and
  `color_correct` on the light (e.g. white channel alone at full, about 0.7 A, scaled to 70 %).
  Before calling it done, run the light at the cap for an hour and check the strip and the
  plinth don't get hot (PLA softens around 57 °C; print the plinth in PETG if it does).
- **Strip:** peel the adhesive backing or keep it; the lips leave room for the tape. Bow the strip
  slightly across its width to snap it past the lips. Cut only at the cut marks.
- **Diffuser:** goes in last, pushed up into the channel until it meets the stops; crush ribs hold
  it. Pop it out with a fingernail at a corner to reach the four screws.
- **Don't plug USB into the ESP32 while the Pi is powered**: both would feed its 5 V pin.
- **USB-C plug:** the Pi's socket sits 10.8 mm in from the outside face; the plug's overmould must
  be smaller than the 14 × 8 mm slot. The official 27 W supply's plug should fit; check yours.
- **ESP32 slot:** grips only the board's two bottom corners (1.5 mm deep). Measure your board's
  antenna-end edge first; tidy it with a dab of hot glue on the corners, not on the antenna.
