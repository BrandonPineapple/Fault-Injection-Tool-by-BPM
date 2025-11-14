#------------------------MODULO ANÁLISIS DE MEMORIAS RAM Y FLASH------------------------------#

import re
import sys
from elftools.elf.elffile import ELFFile

# -------------------------
# FUNCIÓN 1: OBTENER RANGOS TOTALES DE RAM Y FLASH DESDE .MAP
# -------------------------
def metodo_aleatorio_dir(map_path):
    """
    Devuelve los rangos de RAM y FLASH de un archivo .map
    """
    aleatorio_ram = []
    aleatorio_flash = []

    with open(map_path, 'r') as archivo_map:
        lineas = archivo_map.readlines()

    for linea in lineas:
        # Detecta RAM
        if re.match(r"^\s*RAM\b", linea):
            hex_values = re.findall(r'0x[0-9A-Fa-f]+', linea)
            if len(hex_values) >= 2:
                inicio = int(hex_values[0], 16)
                tam = int(hex_values[1], 16)
                fin = inicio + tam - 1
                aleatorio_ram = [hex(inicio), hex(fin)]

        # Detecta FLASH
        if re.match(r"^\s*FLASH\b", linea):
            hex_values = re.findall(r'0x[0-9A-Fa-f]+', linea)
            if len(hex_values) >= 2:
                inicio = int(hex_values[0], 16)
                tam = int(hex_values[1], 16)
                fin = inicio + tam - 1
                aleatorio_flash = [hex(inicio), hex(fin)]

    return {
        "RAM-TOTAL": aleatorio_ram,
        "FLASH-TOTAL": aleatorio_flash
    }


# -------------------------
# FUNCIÓN 2: OBTENER RANGOS PARCIALES DE RAM Y FLASH DESDE UN ELF
# -------------------------
def metodo_pseudo_mems(elf_path, map_path):
    """
    Analiza las secciones del ELF y obtiene los rangos parciales reales
    en RAM y/o FLASH, sin importar en cuál está el código.
    """

    valores_totales = metodo_aleatorio_dir(map_path)
    ram_total = valores_totales["RAM-TOTAL"]
    flash_total = valores_totales["FLASH-TOTAL"]

    flash_start = flash_end = None
    ram_start = ram_end = None

    try:
        with open(elf_path, 'rb') as f:
            elf = ELFFile(f)

            print("\n📄 Secciones detectadas en ELF:")
            for section in elf.iter_sections():
                addr = section['sh_addr']
                size = section['sh_size']

                if addr == 0 or size == 0:
                    continue

                print(f"  {section.name:<12} addr={hex(addr)} size={hex(size)}")

                # FLASH
                if flash_total and int(flash_total[0], 16) <= addr < int(flash_total[1], 16):
                    flash_start = addr if flash_start is None else min(flash_start, addr)
                    flash_end = addr + size if flash_end is None else max(flash_end, addr + size)

                # RAM
                if ram_total and int(ram_total[0], 16) <= addr < int(ram_total[1], 16):
                    ram_start = addr if ram_start is None else min(ram_start, addr)
                    ram_end = addr + size if ram_end is None else max(ram_end, addr + size)

        rangos = {}

        if flash_start is not None:
            rangos["FLASH-PARCIAL"] = [hex(flash_start), hex(flash_end - 1)]
        if ram_start is not None:
            rangos["RAM-PARCIAL"] = [hex(ram_start), hex(ram_end - 1)]

        if not rangos:
            print("❌ No se detectaron secciones dentro de los rangos definidos de RAM ni FLASH.")

        return rangos

    except FileNotFoundError:
        print(f"❌ Error: archivo ELF no encontrado en {elf_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error al procesar el ELF: {e}")
        sys.exit(1)


# -------------------------
# BLOQUE PRINCIPAL
# -------------------------
if __name__ == "__main__":

    archivo_map = "/Users/apple/Documents/PruebasST/LED/Debug/LED.map"
        #r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.map"
    archivo_elf = "/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"
        #r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"
    #"/Users/apple/Documents/PruebasST/LED/Debug/LED.map"
    #"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"

    memorias_totales = metodo_aleatorio_dir(archivo_map)
    print("\n=== Direcciones de memoria RAM y FLASH totales ===")
    print("RAM:", memorias_totales["RAM-TOTAL"])
    print("FLASH:", memorias_totales["FLASH-TOTAL"])

    memorias_parciales = metodo_pseudo_mems(archivo_elf, archivo_map)

    print("\n=== Direcciones de memoria RAM y FLASH parciales detectadas ===")
    for key, value in memorias_parciales.items():
        print(f"{key}: {value}")
    print("RAM:", memorias_parciales["RAM-PARCIAL"])
