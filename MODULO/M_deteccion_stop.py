import subprocess
import re
import platform
import os

def get_tool(exe_name):
    if platform.system() == "Windows":
        base = r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.3 rel1\bin"
        return os.path.join(base, exe_name + ".exe")
    else:
        return exe_name


def obtener_rango_main(elf_path):
    cmd_nm = [get_tool("arm-none-eabi-nm"), "-S", "--size-sort", elf_path]
    result = subprocess.run(cmd_nm, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Error ejecutando nm: {result.stderr}")

    for linea in result.stdout.splitlines():
        if " main" in linea:
            partes = linea.split()
            addr = int(partes[0], 16)
            size = int(partes[1], 16)
            return addr, addr + size
    return None, None


def detectar_while_infinito(elf_path):
    addr_inicio, addr_fin = obtener_rango_main(elf_path)
    if addr_inicio is None:
        raise RuntimeError("No se encontró la función main.")

    cmd_objdump = [get_tool("arm-none-eabi-objdump"), "-d", elf_path]
    result = subprocess.run(cmd_objdump, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Error ejecutando objdump: {result.stderr}")

    patron = re.compile(r"^\s*([0-9a-f]+):\s+[0-9a-f]+\s+b\.n?\s+([0-9a-f]+)", re.IGNORECASE)
    candidatos = []

    for linea in result.stdout.splitlines():
        match = patron.match(linea)
        if match:
            addr_salto = int(match.group(1), 16)
            target = int(match.group(2), 16)

            if addr_inicio <= addr_salto <= addr_fin and addr_inicio <= target <= addr_fin:
                if target < addr_salto:
                    candidatos.append((addr_salto, target))

    if not candidatos:
        return None

    return max(candidatos, key=lambda x: x[0])


if __name__ == "__main__":
    elf_file = r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"
    # "/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"
    # "/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"

    print(f"[INFO] Analizando: {elf_file}")

    resultado = detectar_while_infinito(elf_file)

    if resultado:
        addr_salto, target = resultado
        print(f"[OK] while(1) detectado en main: salto en 0x{addr_salto:08x} → 0x{target:08x}")
    else:
        print("[ERROR] No se encontró while(1) dentro de main.")
