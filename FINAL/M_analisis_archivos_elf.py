#------------------------ MODULO ANALISIS DE ARCHIVOS ELF -------------------------------#

import subprocess
import re
from pathlib import Path
import csv
import sys

# --------------------------------------------------------------------
# Clase que se encarga de analizar archivos ELF
# --------------------------------------------------------------------
class ElfAnalyzer:
    def __init__(self, elf_path: str):
        elf_path = str(elf_path).replace("\\", "/")
        self.elf_path = Path(elf_path)  # Convierte la ruta en objeto Path
        if not self.elf_path.exists():
            raise FileExistsError(f'Archivo ELF no encontrado: {elf_path}')
        self.exec_addresses = []  # Lista donde se guardarán las direcciones ejecutables

    # ----------------------------------------------------------------
    # Obtiene todas las direcciones de la sección ejecutable (.text)
    # ----------------------------------------------------------------
    def list_exec_addresses(self, section: str = '.text'):
        objdump_cmd = None

        # Detecta el sistema operativo
        if sys.platform.startswith("win"):
            # Rutas posibles donde puede estar instalado el toolchain en Windows
            possible_paths = [
                r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.3 rel1\bin\arm-none-eabi-objdump.exe",
                r"C:\Program Files\Arm GNU Toolchain arm-none-eabi\14.3 rel1\bin\arm-none-eabi-objdump.exe",
            ]
            for path in possible_paths:
                if Path(path).exists():
                    objdump_cmd = path
                    break
            if objdump_cmd is None:
                objdump_cmd = "arm-none-eabi-objdump.exe"  # Fallback si está en el PATH
        else:
            # En macOS o Linux normalmente basta con el nombre del comando
            objdump_cmd = "arm-none-eabi-objdump"

        # Muestra qué comando se está utilizando (útil para depuración)
        print(f"[INFO] Usando objdump: {objdump_cmd}")

        # Construye el comando completo
        cmd = [objdump_cmd, "-d", "-j", section, str(self.elf_path)]

        # Ejecuta el comando y captura la salida
        try:
            out = subprocess.check_output(cmd, text=True, errors="ignore")
        except FileNotFoundError:
            raise FileNotFoundError(
                f"No se encontró '{objdump_cmd}'. Verifica que Arm GNU Toolchain esté instalado "
                f"y agregado al PATH del sistema."
            )

        # Procesa la salida para extraer las direcciones ejecutables
        addrs = []
        for line in out.splitlines():
            m = re.match(r"^\s*([0-9a-fA-F]+):\s", line)
            if not m:
                continue
            addr_hex = m.group(1)
            if ".word" in line:
                continue
            if re.search(r"\t[A-Za-z]", line) is None:
                continue
            addrs.append(f"0x{addr_hex.lower()}")

        # Elimina duplicados manteniendo el orden
        seen = set()
        self.exec_addresses = [a for a in addrs if not (a in seen or seen.add(a))]

        print(f"[INFO] Total de direcciones encontradas: {len(self.exec_addresses)}")
        return self.exec_addresses

    # ----------------------------------------------------------------
    # Genera un archivo CSV con las direcciones encontradas
    # ----------------------------------------------------------------
    def generate_csv(self, out_dir: Path = None, filename: str = None):
        if not self.exec_addresses:
            raise RuntimeError("Primero ejecuta list_exec_addresses() antes de generar el CSV.")
        if out_dir is None:
            out_dir = Path(__file__).resolve().parent
        else:
            out_dir = Path(out_dir)
        if filename is None:
            filename = f'DIRECCIONES_EJECUTABLE.csv'

        csv_path = out_dir / filename
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'DIRECCION'])
            for i, addr in enumerate(self.exec_addresses, 1):
                writer.writerow([i, addr])
        print(f"[INFO] Archivo CSV generado: {csv_path}")

# --------------------------------------------------------------------
# Main para pruebas
# --------------------------------------------------------------------
if __name__ == '__main__':
    # Ruta segura (usa r"" para evitar errores de escape)
    ELF_PATH = "/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"

    #"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"
    #"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"

    # Crear analizador y ejecutar los métodos principales
    analizador = ElfAnalyzer(ELF_PATH)
    analizador.list_exec_addresses()
    analizador.generate_csv()
