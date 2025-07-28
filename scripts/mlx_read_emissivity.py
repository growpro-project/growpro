#  cd /home/pi/growpro/scripts
# python3 mlx_read_emissivity.py


# ✅ Emissivität auslesen

# from smbus2 import SMBus

# I2C_ADDR = 0x5A
# REG_EMISS = 0x24

# def read_emissivity(bus_num=1):
#     with SMBus(bus_num) as bus:
#         low = bus.read_byte_data(I2C_ADDR, REG_EMISS)
#         high = bus.read_byte_data(I2C_ADDR, REG_EMISS + 1)
#         raw = (high << 8) | low
#         emissivity = raw / 65535.0
#         return emissivity

# emiss = read_emissivity()
# print(f"Aktuelle Emissivität: {emiss:.4f}")

# gerundet = round(emiss, 2)
# print(gerundet)

from smbus2 import SMBus, i2c_msg

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
        # Sende erst das Register, dann lese 3 Bytes (Low, High, PEC)
        write = i2c_msg.write(I2C_ADDR, [REG_EMISS])
        read = i2c_msg.read(I2C_ADDR, 3)
        bus.i2c_rdwr(write, read)
        
        data = list(read)
        low, high, pec = data[0], data[1], data[2]
        raw = (high << 8) | low
        
        # PEC überprüfen
        pec_data = [(I2C_ADDR << 1), REG_EMISS, (I2C_ADDR << 1) | 1, low, high]
        calc_pec = crc8(pec_data)
        
        if pec != calc_pec:
            print(f"[WARNUNG] PEC-Fehler! Gelesener PEC: 0x{pec:02X}, Berechneter PEC: 0x{calc_pec:02X}")
            return None
        
        emissivity = raw / 65535.0
        return emissivity

if __name__ == "__main__":
    emiss = read_emissivity()
    if emiss is not None:
        print(f"Aktuelle Emissivität: {emiss:.4f}")
    else:
        print("Fehler beim Auslesen der Emissivität.")
