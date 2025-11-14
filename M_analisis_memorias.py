#------------------------MODULO ANÁLISIS DE MEMORIAS RAM Y FLASH------------------------------#

# Se importar librerías a emplear
import re
import subprocess
import sys
from elftools.elf.elffile import ELFFile

# Se define una función que va a permitir obtener las direcciones totales de las memorias
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

    # Se almacenan en diccionarios las direcciones
    return {
        "RAM-TOTAL": aleatorio_ram,
        "FLASH-TOTAL": aleatorio_flash
    }


# -------------------------
# Función para obtener rangos FLASH y RAM desde un ELF
# -------------------------
def metodo_pseudo_mems(elf_path, map_path):

    valores_totales = metodo_aleatorio_dir(map_path)
    ram_total = valores_totales["RAM-TOTAL"]
    flash_total = valores_totales["FLASH-TOTAL"]

    # Se definen variables donde se van a almacenar los datos de inicio y fin
    flash_start = flash_end = None
    ram_start = ram_end = None

    try:
        with open(elf_path, 'rb') as f:
            elf = ELFFile(f)

            for section in elf.iter_sections():
                addr = section['sh_addr']
                size = section['sh_size']

                if addr == 0 or size == 0:
                    continue

                # FLASH
                if int(flash_total[0], 16) <= addr < int(flash_total[1], 16):
                    flash_start = addr if flash_start is None else min(flash_start, addr)
                    flash_end = addr + size if flash_end is None else max(flash_end, addr + size)

                # RAM
                elif int(ram_total[0], 16) <= addr < int(ram_total[1], 16):
                    ram_start = addr if ram_start is None else min(ram_start, addr)
                    ram_end = addr + size if ram_end is None else max(ram_end, addr + size)

        return {
            "FLASH-PARCIAL": [hex(flash_start), hex(flash_end - 1)],
            "RAM-PARCIAL": [hex(ram_start), hex(ram_end - 1)]
        }

    except FileNotFoundError:
        print(f"Error: archivo ELF no encontrado en {elf_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error al procesar el ELF: {e}")
        sys.exit(1)


# ---------- BLOQUE MAIN ----------
if __name__ == "__main__":

    #archivo_map= r"D:\Descargas\LED.map"
    archivo_map = r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.map"
    #/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.map
    #"/Users/apple/Documents/PruebasST/LED/Debug/LED.map"
    memorias_totales = metodo_aleatorio_dir(archivo_map)

    # Guarda los valores en variables
    ram_total = memorias_totales["RAM-TOTAL"]
    flash_total = memorias_totales["FLASH-TOTAL"]

    print()
    print("=== Direcciones de memoria RAM y FLASH totales ===")
    print("RAM:", ram_total)
    print("FLASH:", flash_total)
    archivo_elf= r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"
        #r"D:\Descargas\LED.elf"
        #"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"
    memorias_paricales = metodo_pseudo_mems(archivo_elf, archivo_map)
    print()
    print("=== Direcciones de memoria RAM y FLASH parciales ===")
    print("RAM:", memorias_paricales["RAM-PARCIAL"])
    print("FLASH:", memorias_paricales["FLASH-PARCIAL"])
