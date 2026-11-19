# Hub Rev D: bill of materials

Everything needed to build the Rev D hub (concept D, underglow) from nothing. Prices are rough
US estimates (late 2026), not checked against live listings; check before ordering.

## Electronics

| # | Part | Spec / what to search for | Qty | Approx. |
|---|---|---|---|---|
| 1 | Raspberry Pi 5 | 4 GB is plenty for Home Assistant (2 GB works) | 1 | $60 |
| 2 | Raspberry Pi 5 Active Cooler | official one; the case is designed around it | 1 | $5 |
| 3 | Raspberry Pi 27 W USB-C power supply | **official 27 W (5.1 V 5 A)**: the LEDs and ESP32 run off the Pi's 5 V, so a 3 A supply would brown out | 1 | $12 |
| 4 | microSD card, 64 GB high endurance | SanDisk High Endurance or Samsung PRO Endurance | 1 | $12 |
| 5 | Ethernet cable, 0.5–1 m | hub to router | 1 | $5 |
| 6 | Addressable RGBW LED strip | **SK6812 RGBW, 5 V, 144 LEDs/m, 12 mm wide, white PCB, IP30 (no silicone)**, white channel warm (~3000 K) or natural (~4000 K). Uses 32 LEDs (0.23 m); 1 m is the usual minimum | 1 m | $15–25 |
| 7 | ESP32-C3 SuperMini | 22.5 × 18 mm, USB-C; runs ESPHome and drives the strip. Usually sold in 2–3 packs | 1 (pack) | $8 |
| 8 | Level shifter, 74AHCT125 (DIP-14) | 3.3 V data to the 5 V strip (e.g. Adafruit #1787). One gate used | 1 | $2 |
| 9 | Electrolytic capacitor, 1000 µF, 10 V or more | across the strip's 5 V / GND, max 8 mm diameter | 1 | $1 |
| 10 | Resistor, 330 Ω, ¼ W | in the data line, at the strip end | 1 | $1 (kit) |
| 11 | Female pin header, 2.54 mm, 1 × 40 | cut a 1 × 2 piece; slips onto the Pi's pins 2 and 6, wires soldered to its tails (lower than a jumper housing) | 1 strip | $2 |
| 12 | Silicone hook-up wire, 26 AWG, 3 colours | strip corner jumpers and data | 1 set | $10 |
| 13 | Silicone hook-up wire, 22–24 AWG, red + black | 5 V / GND from the Pi to the ESP32 and strip | 1 set | (in 12 if a mixed kit) |
| 14 | Heat-shrink tubing assortment, 1.5–3 mm | covers every joint | 1 kit | $6 |

## Hardware

| # | Part | Spec | Qty | Approx. |
|---|---|---|---|---|
| 15 | Heat-set inserts M3 × 5.7 mm, OD 4.6 mm | Ruthex or CNC Kitchen "standard" M3; the holes are sized for these | 4 (kit) | $8 |
| 16 | M3 × 12 button-head hex screws (ISO 7380), black | plinth + floor into the shell | 4 | $6 (pack) |
| 17 | M2.5 × 6 socket or pan-head screws | Pi into the floor's standoffs | 4 | $6 (pack) |
| 18 | 3M Bumpon SJ5302 feet (7.9 × 2.2 mm) | sit in the foot recesses | 4 | $5 (pack) |

## Filament

| # | Part | Spec | Qty | Approx. |
|---|---|---|---|---|
| 19 | White PLA (Bambu PLA Basic or similar) | shell, about 50 g | 1 kg | $20 |
| 20 | Black PLA (Bambu PLA Basic or similar) | floor + plinth, about 42 g | 1 kg | $20 |

Parts total (without filament): about $160–180.

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
- Software is free: Raspberry Pi Imager (Home Assistant OS) and ESPHome (inside Home Assistant). Cap the
  LED power in ESPHome (about 1 A); full white on all 32 LEDs would draw about 2 A.
- Untested: whether the strip reads clean data without the level shifter. Fit it.
