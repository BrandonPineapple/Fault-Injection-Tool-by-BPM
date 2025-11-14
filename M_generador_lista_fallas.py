import csv
import random
from pathlib import Path
from M_analisis_memorias_mejorado import metodo_pseudo_mems

class RandomFaultGenerator:
    def __init__(self, flash_csv: Path, reg_csv: Path, elf_path: Path, map_path: Path):
        self.flash_csv = Path(flash_csv)
        self.reg_csv = Path(reg_csv)
        self.elf_path = Path(elf_path)
        self.map_path = Path(map_path)
        self.flash_addresses = []
        self.register_bits = []

        # Cargar automáticamente los rangos desde el ELF
        mem = metodo_pseudo_mems(self.elf_path, self.map_path)
        self.ram_start = int(mem["RAM-PARCIAL"][0], 16)
        self.ram_end   = int(mem["RAM-PARCIAL"][1], 16)
        self.flash_start = int(mem["FLASH-PARCIAL"][0], 16)
        self.flash_end   = int(mem["FLASH-PARCIAL"][1], 16)

    def load_flash_csv(self):
        with open(self.flash_csv, newline='') as f:
            reader = csv.DictReader(f)
            self.flash_addresses = [row['DIRECCION'] for row in reader]

    def load_reg_csv(self):
        with open(self.reg_csv, newline='') as f:
            reader = csv.DictReader(f)
            self.register_bits = list(reader)

    def _choose_fault_mode(self, fault_mode: str):
        """Selecciona aleatoriamente el modo si es 'Todos'"""
        modes = ["bitflip", "stuck-at-0", "stuck-at-1"]
        return random.choice(modes) if fault_mode.lower() == "todos" else fault_mode

    def generate_random_faults(self, n: int, fault_type: str, fault_mode: str):
        faults = []

        # Normalizar entrada
        tipos_validos = ["registro", "ram", "flash"]
        if fault_type.lower() not in tipos_validos:
            raise ValueError("Tipo de falla inválido: debe ser 'Registro', 'RAM', 'Flash' o 'Todos'")

        for i in range(n):
            # Selección del modo de falla
            mode = self._choose_fault_mode(fault_mode)

            # Selección del tipo de inyección
            if fault_type.lower() == "todos":
                fault_type_actual = random.choice(["registro", "flash", "ram"])
            else:
                fault_type_actual = fault_type.lower()

            if fault_type_actual == "registro":
                if not self.register_bits:
                    raise RuntimeError("CSV de registros no cargado")
                if not self.flash_addresses:
                    raise RuntimeError("CSV de flash no cargado")

                reg_bit = random.choice(self.register_bits)
                direccion_flash = random.choice(self.flash_addresses)

                fault = {
                    "FAULT_ID": i + 1,
                    "UBICACION": "Registro",
                    "TIPO_FALLA": mode,
                    "PERIFERICO": reg_bit.get("PERIFERICO", ""),
                    "REGISTRO": reg_bit.get("REGISTRO", ""),
                    "CAMPO": reg_bit.get("CAMPO", ""),
                    "BIT": reg_bit.get("BIT", ""),
                    "DIRECCION": reg_bit.get("DIRECCION", ""),
                    "MASCARA": reg_bit.get("MASCARA", ""),
                    "TIPO DE ACCESO": reg_bit.get("TIPO DE ACCESO", ""),
                    "DIRECCION FLASH": direccion_flash
                }

            elif fault_type_actual == "flash":
                if not self.flash_addresses:
                    raise RuntimeError("CSV de flash no cargado")
                addr = random.choice(self.flash_addresses)
                fault = {
                    "FAULT_ID": i + 1,
                    "UBICACION": "Flash",
                    "TIPO_FALLA": mode,
                    "DIRECCION FLASH": addr
                }

            elif fault_type_actual == "ram":
                inicio_alineado = (self.ram_start + 3) & ~3
                fin_alineado = self.ram_end & ~3
                direccion_valor = random.randint(inicio_alineado // 4, fin_alineado // 4) * 4
                direccion_ram = f"0x{direccion_valor:08X}"
                bit_pos = random.randint(0, 31)
                mascara = f"0x{1 << bit_pos:08X}"

                if not self.flash_addresses:
                    raise RuntimeError("CSV de flash no cargado")
                direccion_flash = random.choice(self.flash_addresses)

                fault = {
                    "FAULT_ID": i + 1,
                    "UBICACION": "RAM",
                    "TIPO_FALLA": mode,
                    "DIRECCION FLASH": direccion_flash,
                    "DIRECCION RAM": direccion_ram,
                    "MASCARA": mascara,
                    "BIT": bit_pos
                }

            faults.append(fault)
        return faults

    def save_to_csv(self, faults: list, out_path: Path):
        out_path = Path(out_path)
        with open(out_path, "w", newline="") as f:
            writer = None
            for row in faults:
                if row["UBICACION"] == "Registro":
                    fieldnames = ["FAULT_ID", "UBICACION", "TIPO_FALLA", "PERIFERICO", "REGISTRO", "CAMPO",
                                  "BIT", "DIRECCION FLASH", "DIRECCION", "MASCARA", "TIPO DE ACCESO"]

                elif row["UBICACION"] == "Flash":
                    fieldnames = ["FAULT_ID", "UBICACION", "TIPO_FALLA", "DIRECCION FLASH"]

                elif row["UBICACION"] == "RAM":
                    fieldnames = ["FAULT_ID", "UBICACION", "TIPO_FALLA", "DIRECCION FLASH", "DIRECCION RAM", "MASCARA", "BIT"]

                else:
                    continue

                if writer is None:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

                writer.writerow(row)

        print(f"Archivo CSV de fallas generado: {out_path}")


# ---------------------------
# Main para pruebas
# ---------------------------
if __name__ == "__main__":
    FLASH_CSV = Path("DIRECCIONES_EJECUTABLE.csv")
    REG_CSV = Path("LISTA_FALLAS_PERIFERICO.csv")
    ELF_FILE = Path(r"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf")


    MAP_FILE = Path("/Users/apple/Documents/PruebasST/LED/Debug/LED.map")
    OUT_CSV = Path("LISTA_INYECCION.csv")

    generator = RandomFaultGenerator(FLASH_CSV, REG_CSV, ELF_FILE, MAP_FILE)
    generator.load_flash_csv()
    generator.load_reg_csv()

    fault_type = input("Tipo de inyección (Registro/Flash/RAM:) ").strip()
    fault_mode = input("Modo de falla (Bitflip/Stuck-at-0/Stuck-at-1/Todos): ").strip()
    num_faults = int(input("Número de fallas a generar: "))

    faults = generator.generate_random_faults(num_faults, fault_type, fault_mode)
    generator.save_to_csv(faults, OUT_CSV)

