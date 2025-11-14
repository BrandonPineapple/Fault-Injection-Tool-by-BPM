#------------------------ MODULO ANALISIS DE ARCHIVOS ELF -------------------------------#

import subprocess
import re
from pathlib import Path
import csv
import sys

# Intento opcional de usar pyelftools para leer .isr_vector (no obligatorio)
try:
    from elftools.elf.elffile import ELFFile
    HAS_ELFTOOLS = True
except Exception:
    HAS_ELFTOOLS = False

# --------------------------------------------------------------------
# Clase que se encarga de analizar archivos ELF
# --------------------------------------------------------------------
class ElfAnalyzer:
    def __init__(self, elf_path: str):
        self.elf_path = Path(elf_path)
        if not self.elf_path.exists():
            raise FileExistsError(f'Archivo ELF no encontrado: {elf_path}')
        self.exec_addresses = []

    # ----------------------------------------------------------------
    # (opcional) intenta leer .isr_vector del ELF y devolver la dirección del ResetHandler (int)
    # ----------------------------------------------------------------
    def _detect_reset_from_isr_vector(self):
        if not HAS_ELFTOOLS:
            print("[WARN] pyelftools no disponible -> no se podrá detectar ResetHandler desde ELF")
            return None
        try:
            with open(self.elf_path, 'rb') as f:
                ef = ELFFile(f)
                sec = ef.get_section_by_name('.isr_vector')
                if sec is None:
                    print("[WARN] ELF no contiene sección .isr_vector")
                    return None
                data = sec.data()
                if len(data) < 8:
                    print("[WARN] .isr_vector demasiado corto para leer SP/Reset")
                    return None
                reset_handler = int.from_bytes(data[4:8], byteorder='little')
                vb = sec['sh_addr']
                print(f"[INFO] .isr_vector.sh_addr detectado en ELF: 0x{vb:08X}")
                print(f"[INFO] ResetHandler detectado en .isr_vector (valor): 0x{reset_handler:08X}")
                return reset_handler
        except Exception as e:
            print(f"[WARN] Error leyendo ELF (.isr_vector): {e}")
            return None

    # ----------------------------------------------------------------
    # NUEVO: obtiene direcciones de funciones (símbolos tipo T/t)
    # ----------------------------------------------------------------
    def _get_function_symbols(self):
        """Devuelve lista de direcciones (int) de símbolos de código (T/t)"""
        try:
            nm_cmd = "arm-none-eabi-nm"
            out = subprocess.check_output([nm_cmd, "-n", str(self.elf_path)],
                                          text=True, errors="ignore")
        except Exception as e:
            print(f"[WARN] No se pudo ejecutar nm: {e}")
            return []

        symbols = []
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 3:
                addr_str, sym_type, name = parts[0], parts[1], parts[2]
                if sym_type.lower() == 't':  # símbolo de código (.text)
                    try:
                        addr_int = int(addr_str, 16)
                        symbols.append(addr_int)
                    except ValueError:
                        continue
        print(f"[INFO] {len(symbols)} símbolos de función detectados (T/t).")
        return symbols

    # ----------------------------------------------------------------
    # Obtiene todas las direcciones de la sección ejecutable (.text)
    # ----------------------------------------------------------------
    def list_exec_addresses(self, section: str = '.text'):
        objdump_cmd = None

        # Detectar toolchain
        if sys.platform.startswith("win"):
            possible_paths = [
                r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.3 rel1\bin\arm-none-eabi-objdump.exe",
                r"C:\Program Files\Arm GNU Toolchain arm-none-eabi\14.3 rel1\bin\arm-none-eabi-objdump.exe",
            ]
            for path in possible_paths:
                if Path(path).exists():
                    objdump_cmd = path
                    break
            if objdump_cmd is None:
                objdump_cmd = "arm-none-eabi-objdump.exe"
        else:
            objdump_cmd = "arm-none-eabi-objdump"

        print(f"[INFO] Usando objdump: {objdump_cmd}")
        cmd = [objdump_cmd, "-d", "-j", section, str(self.elf_path)]

        try:
            out = subprocess.check_output(cmd, text=True, errors="ignore")
        except FileNotFoundError:
            raise FileNotFoundError(
                f"No se encontró '{objdump_cmd}'. Verifica que Arm GNU Toolchain esté instalado "
                f"y agregado al PATH del sistema."
            )

        # Extraer direcciones ejecutables
        addrs = []
        instr_re = re.compile(r"^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F]{2,})\s+\b([a-zA-Z_.]+)\b")
        for line in out.splitlines():
            if ".word" in line:
                continue
            m = instr_re.match(line)
            if not m:
                continue
            addr_hex = m.group(1)
            mnemonic = m.group(3)
            if mnemonic is None:
                continue
            addrs.append(f"0x{addr_hex.lower()}")

        seen = set()
        all_exec = [a for a in addrs if not (a in seen or seen.add(a))]

        # Detectar ResetHandler en RAM
        try:
            reset_handler = None
            if HAS_ELFTOOLS:
                with open(self.elf_path, 'rb') as f:
                    ef = ELFFile(f)
                    sec = ef.get_section_by_name('.isr_vector')
                    if sec is not None:
                        try:
                            vec_base = sec['sh_addr']
                        except Exception:
                            vec_base = sec.header.get('sh_addr', None)
                        if vec_base is not None and (0x20000000 <= int(vec_base) <= 0x2007FFFF):
                            data = sec.data()
                            if len(data) >= 8:
                                reset_handler = int.from_bytes(data[4:8], byteorder='little')
                                print(f"[INFO] .isr_vector en RAM (0x{vec_base:08X}) -> ResetHandler=0x{reset_handler:08X}")
                            else:
                                print("[WARN] .isr_vector presente pero demasiado corta para leer ResetHandler")
                        else:
                            if vec_base is not None:
                                print(f"[INFO] .isr_vector en ELF en 0x{vec_base:08X} -> asumimos ejecución desde FLASH, no filtramos.")
                            else:
                                print("[INFO] No se detectó sh_addr de .isr_vector -> no filtramos por ResetHandler")
                    else:
                        print("[INFO] No se encontró .isr_vector en ELF -> no filtramos por ResetHandler")
            else:
                print("[INFO] pyelftools ausente: no se intentará filtrar por ResetHandler (se mantiene lógica original).")
        except Exception as e:
            print(f"[WARN] Error detectando/reset_handler: {e}")
            reset_handler = None

        # 🔹 Nueva lógica con símbolos de funciones
        func_symbol_addrs = set(self._get_function_symbols())

        if reset_handler is not None:
            filtered = []
            discarded_count = 0
            for a in all_exec:
                try:
                    ai = int(a, 16)
                except Exception:
                    ai = 0
                # ✅ Mantener instrucciones si:
                # - están después del ResetHandler
                # - o pertenecen a una función válida detectada por nm
                if ai >= reset_handler or ai in func_symbol_addrs:
                    filtered.append(a)
                else:
                    discarded_count += 1
            print(f"[INFO] Filtrado aplicado (modo RAM + símbolos): {len(all_exec)} -> {len(filtered)} (descartadas {discarded_count})")
            self.exec_addresses = filtered
        else:
            self.exec_addresses = all_exec
            print(f"[INFO] Total de direcciones encontradas: {len(self.exec_addresses)} (sin filtrar)")

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
    ELF_PATH = r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"
    analizador = ElfAnalyzer(ELF_PATH)
    analizador.list_exec_addresses()
    analizador.generate_csv()
