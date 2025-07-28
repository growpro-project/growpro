# read ports:
# python3 pcf8574_control.py

# set port:
# python3 pcf8574_control.py set 0 1 # port 0 ON

import sys
from pcf8574 import PCF8574

# Initialisiere PCF8574 an I2C-Bus 1 mit Adresse 0x20
i2c_port_num = 1
pcf_address = 0x20
pcf = PCF8574(i2c_port_num, pcf_address)


def get_logical_port_state():
    """
    Gibt Port-Zustände in logischer Reihenfolge P0 bis P7 zurück.
    Da die Treiber-Port-Indizes intern umgekehrt sind (pcf.port[0] = P7),
    holen wir explizit in umgekehrter Reihenfolge.
    """
    return [pcf.port[i] for i in reversed(range(8))]


def set_logical_port_state(state_list):
    """
    Setzt Port-Zustände in logischer Reihenfolge P0 bis P7.
    Dreht die Liste um, bevor sie an den Treiber übergeben wird.
    """
    if len(state_list) != 8:
        raise ValueError("Exactly 8 values required")
    full_state = [state_list[7 - i] for i in range(8)]  # Drehen: P0 → port[7], ...
    pcf.port = full_state


# Hauptlogik
args = sys.argv[1:]

if not args:
    # Keine Argumente → Status aller Ports anzeigen
    #print(get_logical_port_state())
    states = get_logical_port_state()
    print([f"Port {i} = {'OFF' if s else 'ON'}" for i, s in enumerate(states)])


elif args[0] == "get":
    try:
        index = int(args[1])
        if not (0 <= index <= 7):
            raise ValueError
        print(get_logical_port_state()[index])
    except:
        print("Usage: get <0–7>")

elif args[0] == "set":
    try:
        index = int(args[1])
        # Wert invertieren: Eingabe 1 = ON → intern False; 0 = OFF → intern True
        input_val = args[2].lower()
        if input_val in ["1", "true", "on"]:
            value = False  # Relais EIN → LOW → False intern
        elif input_val in ["0", "false", "off"]:
            value = True   # Relais AUS → HIGH → True intern
        else:
            raise ValueError("Invalid value")
        if not (0 <= index <= 7):
            raise ValueError("Invalid port")
        state = get_logical_port_state()
        state[index] = value
        set_logical_port_state(state)
        print(f"Set P{index} to {'ON' if not value else 'OFF'}")
    except Exception as e:
        print("Usage: set <0–7> <0|1|on|off>")


elif args[0] == "setall":
    try:
        values = [x.lower() in ["1", "true", "on"] for x in args[1:]]
        if len(values) != 8:
            raise ValueError
        set_logical_port_state(values)
        print("Set all P0–P7:", values)
    except:
        print("Usage: setall <8x 0|1|on|off>")

elif args[0] == "bitmask":
    try:
        mask = int(args[1])
        if not (0 <= mask <= 255):
            raise ValueError
        # Maske wird Bitweise auf P0–P7 gemappt (LSB = P0)
        values = [(mask >> i) & 1 for i in range(8)]
        set_logical_port_state([bool(v) for v in values])
        print(f"Set via bitmask {mask:08b} → {get_logical_port_state()}")
    except:
        print("Usage: bitmask <0–255>")

else:
    print("Unknown command. Usage:")
    print("  (no args)             → show all ports P0–P7")
    print("  get <0–7>             → get P0–P7 state")
    print("  set <0–7> <0|1|on|off>→ set port")
    print("  setall <8 values>     → set all ports P0–P7")
    print("  bitmask <0–255>       → set ports from bitmask")
