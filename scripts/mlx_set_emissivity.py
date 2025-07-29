#  cd /home/pi/growpro/scripts
# python3 mlx_set_emissivity.py

###################################################################################################################


# ⚠️ Set Emissivity
# python3 mlx_set_emissivity.py 0.95

# msg.payload = "/usr/bin/python3 /home/pi/set_emissivity.py " + msg.payload;
# return msg;


import time
from smbus2 import SMBus, i2c_msg

I2C_ADDR = 0x5A
REG_EMISS = 0x24

# Dynamische CRC8-Berechnung (Polynomial 0x07 für SMBus PEC)
def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc

def read_emissivity(bus_num=1):
    with SMBus(bus_num) as bus:
        low = bus.read_byte_data(I2C_ADDR, REG_EMISS)
        high = bus.read_byte_data(I2C_ADDR, REG_EMISS + 1)
        raw = (high << 8) | low
        emissivity = raw / 65535.0
        return emissivity

def write_bytes_pec(bus, reg, data):
    low = data & 0xFF
    high = (data >> 8) & 0xFF
    buffer = [I2C_ADDR << 1, reg, low, high]
    pec = crc8(buffer)
    msg = i2c_msg.write(I2C_ADDR, [reg, low, high, pec])
    bus.i2c_rdwr(msg)

def write_emissivity(emissivity, bus_num=1):
    assert 0.1 <= emissivity <= 1.0, "Emissivität muss zwischen 0.1 und 1.0 liegen"
    raw = int(emissivity * 65535) & 0xFFFF

    with SMBus(bus_num) as bus:
        print("Setze Emissivität auf 0 (Löschen)...")
        write_bytes_pec(bus, REG_EMISS, 0x0000)
        time.sleep(0.05)

        print(f"Schreibe neue Emissivität: {emissivity:.4f} → 0x{raw:04X}")
        write_bytes_pec(bus, REG_EMISS, raw)
        time.sleep(0.05)

        new = read_emissivity(bus_num)
        print(f"Verifiziert: {new:.4f} (0x{int(new * 65535):04X})")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Setze Emissivität für MLX90614-Sensor.")
    parser.add_argument("emissivity", type=float, help="Wert zwischen 0.1 und 1.0 (z.B. 0.95)")
    args = parser.parse_args()

    write_emissivity(args.emissivity)



