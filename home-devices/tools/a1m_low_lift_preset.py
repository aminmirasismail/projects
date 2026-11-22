"""Install a Bambu Studio printer preset for the A1 Mini that parks low after a print.

Stock end G-code lifts the toolhead 100 mm above the print (up to Z 180) and parks it at the
purge spot (X-13). A later manual filament swap then purges from that height and the waste
scatters past the purge bin. This preset lifts 10 mm instead; the bed slides out for removal.

  python a1m_low_lift_preset.py            # writes the user preset; restart Bambu Studio
  python a1m_low_lift_preset.py --check F  # only write the patched end G-code to F (tests)
"""
import json, os, time, sys
SYS = r"C:\Program Files\Bambu Studio\resources\profiles\BBL\machine"
ROOT = os.path.join(os.environ["APPDATA"], "BambuStudio", "user")
UID = next(d for d in os.listdir(ROOT) if d.isdigit())   # the signed-in Bambu account
USER = os.path.join(ROOT, UID, "machine")
NAME = "Bambu Lab A1 mini 0.4 nozzle - Low lift"
g = json.load(open(os.path.join(SYS, "Bambu Lab A1 mini 0.4 nozzle template machine_end_gcode.json"), encoding="utf-8"))["machine_end_gcode"]
old = """{if (max_layer_z + 100.0) < 180}
    G1 Z{max_layer_z + 100.0} F600
    G1 Z{max_layer_z +98.0}
{else}"""
new = """; Low lift: park 10 mm above the print (stock lifts 100 mm), so a later
; filament swap purges low, into the bin. The bed slides out for part removal.
{if (max_layer_z + 10.0) < 180}
    G1 Z{max_layer_z + 10.0} F600
    G1 Z{max_layer_z + 8.0}
{else}"""
assert g.count(old) == 1, "end G-code changed upstream; not patching"
g = g.replace(old, new)
preset = {"from": "User", "inherits": "Bambu Lab A1 mini 0.4 nozzle", "name": NAME,
          "printer_settings_id": NAME, "is_custom_defined": "0", "version": "1.0.0.0",
          "machine_end_gcode": g}
if "--check" in sys.argv:          # write the merged preset for a CLI slice test
    json.dump(g, open(sys.argv[2], "w")); sys.exit()
os.makedirs(USER, exist_ok=True)
json.dump(preset, open(os.path.join(USER, NAME + ".json"), "w", encoding="utf-8"), indent=4)
open(os.path.join(USER, NAME + ".info"), "w").write(
    f"sync_info = \nuser_id = {UID}\nsetting_id = \nbase_id = GM020\nupdated_time = {int(time.time())}\n")
print("wrote", os.path.join(USER, NAME + ".json"))
