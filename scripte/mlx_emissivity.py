#  cd /home/pi/growpro/scripts

# msg.payload = "python3 /home/pi/growpro/scripts/mlx_emissivity.py --set " + msg.payload;
# return msg;

# ✅ Emissivität nur auslesen:

# python3 mlx_emissivity.py --read

# ✅ Emissivität simulieren (kein Schreiben):

# python3 mlx_emissivity.py --set 0.98 --simulate

# ✅ Nur wenn du bereit bist, wirklich zu schreiben (nicht simulieren):

# python3 mlx_emissivity.py --set 0.95


# ⚠️ Emissivität setzen (EEPROM schreiben)


import time
from smbus2 import SMBus, i2c_msg
import argparse

I2C_ADDR = 0x5A
REG_EMISS = 0x24

def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
    return crc

def read_emissivity(bus_num=1):
    with SMBus(bus_num) as bus:
        # Schreibe Registeradresse
        write = i2c_msg.write(I2C_ADDR, [REG_EMISS])
        read = i2c_msg.read(I2C_ADDR, 3)  # Low, High, PEC
        bus.i2c_rdwr(write, read)
        data = list(read)
        low, high, pec = data[0], data[1], data[2]

        # Debug-Ausgabe
        print(f"[DEBUG] Gelesene Bytes: LOW=0x{low:02X}, HIGH=0x{high:02X}, PEC=0x{pec:02X}")

        raw = (high << 8) | low

        # PEC prüfen (Adresse+Write, Register, Adresse+Read, Low, High)
        pec_data = [(I2C_ADDR << 1), REG_EMISS, (I2C_ADDR << 1) | 1, low, high]
        calc_pec = crc8(pec_data)
        if pec != calc_pec:
            print(f"[WARNUNG] PEC Fehler! Gelesener PEC: 0x{pec:02X}, Berechneter PEC: 0x{calc_pec:02X}")

        return raw / 65535.0

def write_bytes_pec(bus, reg, data, simulate=True):
    low = data & 0xFF
    high = (data >> 8) & 0xFF

    # Buffer für PEC: Adresse+Write, Register, Low, High
    buffer = [I2C_ADDR << 1, reg, low, high]
    pec = crc8(buffer)

    if simulate:
        print(f"[SIMULATION] Schreiben an 0x{reg:02X} → LOW=0x{low:02X}, HIGH=0x{high:02X}, PEC=0x{pec:02X}")
        return
    msg = i2c_msg.write(I2C_ADDR, [reg, low, high, pec])
    bus.i2c_rdwr(msg)

def write_emissivity(emissivity, bus_num=1, simulate=True):
    assert 0.1 <= emissivity <= 1.0, "Emissivität muss zwischen 0.1 und 1.0 liegen"
    raw = int(emissivity * 65535) & 0xFFFF

    with SMBus(bus_num) as bus:
        print("[INFO] Schritt 1: Lösche aktuellen Emissivitätswert (setze auf 0)...")
        write_bytes_pec(bus, REG_EMISS, 0x0000, simulate)
        time.sleep(5)  # längere Wartezeit nach Löschen

        if not simulate:
            cleared = read_emissivity(bus_num)
            print(f"[INFO] Wert nach Löschen: {cleared:.4f}")

        print(f"[INFO] Schritt 2: Schreibe neuen Wert: {emissivity:.4f} → 0x{raw:04X}")
        write_bytes_pec(bus, REG_EMISS, raw, simulate)
        time.sleep(5)  # Wartezeit nach Schreiben

        if not simulate:
            new = read_emissivity(bus_num)
            print(f"[VERIFIKATION] Neuer Wert: {new:.4f} (0x{int(new * 65535):04X})")

def main():
    parser = argparse.ArgumentParser(description="Lese oder setze Emissivität am MLX90614.")
    parser.add_argument("--read", action="store_true", help="Nur aktuelle Emissivität auslesen")
    parser.add_argument("--set", type=float, help="Neuen Emissivitätswert setzen (z.B. 0.95)")
    parser.add_argument("--simulate", action="store_true", help="Nur simulieren, nicht schreiben")
    args = parser.parse_args()

    if args.read:
        val = read_emissivity()
        print(f"Aktuelle Emissivität: {val:.4f} (0x{int(val * 65535):04X})")
    elif args.set is not None:
        write_emissivity(args.set, simulate=args.simulate)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()





