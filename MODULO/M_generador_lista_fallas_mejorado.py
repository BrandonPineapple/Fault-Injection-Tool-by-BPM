#!/usr/bin/env python3
import csv
import random
from pathlib import Path
from typing import Optional, Tuple
from elftools.elf.elffile import ELFFile
from M_analisis_memorias_mejorado import metodo_pseudo_mems

class RandomFaultGenerator:
    def __init__(self, flash_csv: Path, reg_csv: Path, elf_path: Path, map_path: Path):
        self.flash_csv = Path(flash_csv)
        self.reg_csv = Path(reg_csv)
        self.elf_path = Path(elf_path)
        self.map_path = Path(map_path)

        self.flash_addresses = []   # direcciones tomadas desde CSV (si aplica)
        self.register_bits = []     # registros/periféricos desde CSV (si aplica)

        # Rango RAM / FLASH (metodo_pseudo_mems debe devolver RAM-PARCIAL y opcional FLASH-PARCIAL)
        mem = metodo_pseudo_mems(self.elf_path, self.map_path)

        # RAM (debe existir)
        try:
            self.ram_start = int(mem["RAM-PARCIAL"][0], 16)
            self.ram_end   = int(mem["RAM-PARCIAL"][1], 16)
        except Exception as e:
            raise RuntimeError(f"No se pudo obtener rango RAM desde metodo_pseudo_mems: {e}")

        # FLASH puede no existir (firmware cargado en RAM)
        flash_info = mem.get("FLASH-PARCIAL", None)
        if flash_info and flash_info[0] not in (None, "None") and flash_info[1] not in (None, "None"):
            # FLASH real detectada
            self.flash_start = int(flash_info[0], 16)
            self.flash_end   = int(flash_info[1], 16)
            self.flash_present = True
            print(f"FLASH detectada: {hex(self.flash_start)} - {hex(self.flash_end)}")
        else:
            # No hay FLASH: redirigir (simular) FLASH hacia RAM
            self.flash_start = self.ram_start
            self.flash_end   = self.ram_end
            self.flash_present = False
            print("⚠️  No se detectaron secciones FLASH en el ELF. Se simulará FLASH usando el rango RAM.")
            print(f"FLASH simulada (RAM): {hex(self.flash_start)} - {hex(self.flash_end)}")

        # Intentar obtener rango .text real desde el ELF (para DIRECCION STOP)
        text_range = self._get_text_range()
        if text_range:
            self.text_start, self.text_end = text_range
            print(f".text detectada: {hex(self.text_start)} - {hex(self.text_end)}")
        else:
            # Si no hay .text (muy raro), usar inicio RAM como referencia
            self.text_start = None
            self.text_end = None
            print("⚠️  No se detectó sección .text en el ELF; se usará todo el rango FLASH/RAM para inyecciones 'flash'.")

    # -----------------------
    # Helpers
    # -----------------------
    def _get_text_range(self) -> Optional[Tuple[int,int]]:
        """Lee el ELF y devuelve (start,end) de la sección .text si existe."""
        try:
            with open(self.elf_path, 'rb') as f:
                elf = ELFFile(f)
                for sec in elf.iter_sections():
                    if sec.name == '.text':
                        start = sec['sh_addr']
                        size = sec['sh_size']
                        if start and size:
                            return (int(start), int(start + size - 1))
        except Exception as e:
            print(f"⚠️  No se pudo leer ELF para obtener .text: {e}")
        return None

    def addr_to_section(self, addr: int) -> str:
        """Devuelve el nombre de la sección ELF que contiene addr o 'UNKNOWN'."""
        try:
            with open(self.elf_path, 'rb') as f:
                elf = ELFFile(f)
                for sec in elf.iter_sections():
                    start = sec['sh_addr']
                    size = sec['sh_size']
                    if start and size:
                        s = int(start)
                        e = int(start + size - 1)
                        if s <= addr <= e:
                            return sec.name
        except Exception:
            pass
        return "UNKNOWN"

    # -----------------------
    # CSV loaders
    # -----------------------
    def load_flash_csv(self):
        """Carga direcciones de FLASH desde CSV (campo 'DIRECCION')."""
        if not self.flash_csv.exists():
            print(f"⚠️  CSV de FLASH no encontrado: {self.flash_csv} (continuando sin direcciones FLASH).")
            self.flash_addresses = []
            return
        with open(self.flash_csv, newline='') as f:
            reader = csv.DictReader(f)
            self.flash_addresses = [row['DIRECCION'] for row in reader if row.get('DIRECCION')]
        print(f"➡️  Direcciones FLASH cargadas: {len(self.flash_addresses)}")

    def load_reg_csv(self):
        """Carga registro/periféricos desde CSV (mantiene todas las columnas)."""
        if not self.reg_csv.exists():
            print(f"⚠️  CSV de registros no encontrado: {self.reg_csv} (continuando sin registros).")
            self.register_bits = []
            return
        with open(self.reg_csv, newline='') as f:
            reader = csv.DictReader(f)
            self.register_bits = list(reader)
        print(f"➡️  Registros/periféricos cargados: {len(self.register_bits)}")

    # -----------------------
    # Modo de falla
    # -----------------------
    def _choose_fault_mode(self, fault_mode: str) -> str:
        modes = ["bitflip", "stuck-at-0", "stuck-at-1"]
        return random.choice(modes) if fault_mode.lower() == "todos" else fault_mode

    # -----------------------
    # Generador de fallas
    # -----------------------
    def generate_random_faults(self, n: int, fault_type: str, fault_mode: str):
        """
        Genera n fallas. Para UBICACION == 'FLASH' (aunque FLASH esté en RAM),
        escoge DIRECCION STOP aleatoria dentro de .text (si existe),
        y DIRECCION INYECCION aleatoria dentro del rango FLASH (o RAM si simulado).
        """
        faults = []
        tipos_validos = ["registro", "ram", "flash", "todos"]
        if fault_type.lower() not in tipos_validos:
            raise ValueError("Tipo de falla inválido: debe ser 'Registro', 'RAM', 'flash' o 'Todos'")

        for i in range(n):
            mode = self._choose_fault_mode(fault_mode)

            # decidir el tipo real a generar
            if fault_type.lower() == "todos":
                choices = ["registro", "ram"]
                # permitimos 'flash' siempre: si no hay flash real, será simulado con RAM
                choices.append("flash")
                fault_type_actual = random.choice(choices)
            else:
                fault_type_actual = fault_type.lower()

            # ---------- REGISTRO ----------
            if fault_type_actual == "registro":
                if not self.register_bits:
                    raise RuntimeError("CSV de registros no cargado o vacío.")
                reg_bit = random.choice(self.register_bits)
                direccion_flash = random.choice(self.flash_addresses) if (self.flash_addresses) else "N/A"
                fault = {
                    "FAULT_ID": i + 1,
                    "UBICACION": "Registro",
                    "TIPO_FALLA": mode,
                    "PERIFERICO": reg_bit.get("PERIFERICO", ""),
                    "REGISTRO": reg_bit.get("REGISTRO", ""),
                    "CAMPO": reg_bit.get("CAMPO", ""),
                    "BIT": reg_bit.get("BIT", ""),
                    "DIRECCION INYECCION": reg_bit.get("DIRECCION", ""),
                    "MASCARA": reg_bit.get("MASCARA", ""),
                    "TIPO DE ACCESO": reg_bit.get("TIPO DE ACCESO", ""),
                    "DIRECCION STOP": direccion_flash
                }

            # ---------- FLASH (o FLASH simulada sobre RAM) ----------
            elif fault_type_actual == "flash":
                bit_pos = random.randint(0, 31)
                mascara = f"0x{1 << bit_pos:08X}"

                # DIRECCION STOP: elegir del CSV (segunda columna)
                if self.flash_addresses:
                    pick = random.choice(self.flash_addresses)
                    try:
                        direccion_stop_val = int(pick, 16)
                    except ValueError:
                        direccion_stop_val = self.flash_start  # fallback seguro
                else:
                    # fallback si no hay CSV
                    if self.text_start is not None and self.text_end is not None:
                        direccion_stop_val = random.randint(self.text_start, self.text_end)
                    else:
                        direccion_stop_val = random.randint(self.flash_start, self.flash_end)

                # Alinear STOP (2 bytes por instrucción Thumb)
                direccion_stop_val &= ~1
                direccion_stop = f"0x{direccion_stop_val:08X}"

                # DIRECCION INYECCION (sigue igual)
                # Alinear a palabra (4 bytes) para accesos de 32 bits
                inicio_alineado = (self.flash_start + 3) & ~3
                fin_alineado = self.flash_end & ~3
                direccion_inyeccion_val = random.randint(inicio_alineado // 4, fin_alineado // 4) * 4
                direccion_inyeccion = f"0x{direccion_inyeccion_val:08X}"

                fault = {
                    "FAULT_ID": i + 1,
                    "UBICACION": "FLASH",
                    "TIPO_FALLA": mode,
                    "DIRECCION STOP": direccion_stop,
                    "DIRECCION INYECCION": direccion_inyeccion,
                    "MASCARA": mascara,
                    "BIT": bit_pos
                }

            # ---------- RAM ----------
            elif fault_type_actual == "ram":
                inicio_alineado = (self.ram_start + 3) & ~3
                fin_alineado = self.ram_end & ~3
                if inicio_alineado > fin_alineado:
                    raise RuntimeError("Rango RAM inválido/alineado incorrecto.")
                direccion_valor = random.randint(inicio_alineado // 4, fin_alineado // 4) * 4
                direccion_ram = f"0x{direccion_valor:08X}"
                bit_pos = random.randint(0, 31)
                mascara = f"0x{1 << bit_pos:08X}"

                direccion_flash = random.choice(self.flash_addresses) if (self.flash_addresses) else "N/A"

                fault = {
                    "FAULT_ID": i + 1,
                    "UBICACION": "RAM",
                    "TIPO_FALLA": mode,
                    "DIRECCION STOP": direccion_flash,
                    "DIRECCION INYECCION": direccion_ram,
                    "MASCARA": mascara,
                    "BIT": bit_pos
                }

            else:
                # no debería ocurrir
                continue

            faults.append(fault)

        return faults

    # -----------------------
    # Guardar CSV
    # -----------------------
    def save_to_csv(self, faults: list, out_path: Path):
        out_path = Path(out_path)
        # Para que el CSV tenga las columnas correctas por tipo, escribimos por filas agrupando
        with open(out_path, "w", newline="") as f:
            writer = None
            for row in faults:
                ubicacion = row.get("UBICACION", "")
                if ubicacion == "Registro":
                    fieldnames = ["FAULT_ID", "UBICACION", "TIPO_FALLA", "PERIFERICO", "REGISTRO", "CAMPO",
                                  "BIT", "DIRECCION STOP", "DIRECCION INYECCION", "MASCARA", "TIPO DE ACCESO"]
                elif ubicacion == "FLASH":
                    # formato solicitado con STOP + INYECCION
                    fieldnames = ["FAULT_ID", "UBICACION", "TIPO_FALLA",
                                  "DIRECCION STOP", "DIRECCION INYECCION", "MASCARA", "BIT"]
                elif ubicacion == "RAM":
                    fieldnames = ["FAULT_ID", "UBICACION", "TIPO_FALLA",
                                  "DIRECCION STOP", "DIRECCION INYECCION", "MASCARA", "BIT"]
                else:
                    # fila desconocida: omitimos
                    continue

                if writer is None:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

                # asegurar que no falten claves
                safe_row = {k: row.get(k, "") for k in fieldnames}
                writer.writerow(safe_row)

        print(f"✅ Archivo CSV de fallas generado: {out_path}")

# ---------------------------
# Bloque main (prueba)
# ---------------------------
if __name__ == "__main__":
    FLASH_CSV = Path("DIRECCIONES_EJECUTABLE.csv")           # CSV con campo DIRECCION (opcional)
    REG_CSV = Path("LISTA_FALLAS_PERIFERICO.csv")           # CSV con campos PERIFERICO, REGISTRO, BIT, etc.
    ELF_FILE = Path(r"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf")
    MAP_FILE = Path(r"/Users/apple/Documents/PruebasST/LED/Debug/LED.map")
    OUT_CSV = Path("LISTA_INYECCION.csv")
    #"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"
    #"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.map"
    #"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"
    #"/Users/apple/Documents/PruebasST/LED/Debug/LED.map"


    gen = RandomFaultGenerator(FLASH_CSV, REG_CSV, ELF_FILE, MAP_FILE)
    gen.load_flash_csv()
    gen.load_reg_csv()

    fault_type = input("Tipo de inyección (Registro/Flash/RAM/Todos): ").strip()
    fault_mode = input("Modo de falla (Bitflip/Stuck-at-0/Stuck-at-1/Todos): ").strip()
    num_faults = int(input("Número de fallas a generar: "))

    faults = gen.generate_random_faults(num_faults, fault_type, fault_mode)
    gen.save_to_csv(faults, OUT_CSV)
    print("Hecho.")
