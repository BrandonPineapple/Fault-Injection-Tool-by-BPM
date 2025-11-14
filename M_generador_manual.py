
#!/usr/bin/env python3
# ============================================================
# generador_fallas_manual_v2_final.py
# Generador manual de fallas (independiente, consola)
# - breakpoint forzado en .text si existe (en FLASH o RAM según ELF)
# - validación y normalización de regiones
# - alineación automática a 4 bytes para RAM/REGISTROS
# - máscara autogenerada si el usuario deja el campo vacío
# - exporta CSV final
# ============================================================

import csv
import random
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from elftools.elf.elffile import ELFFile
from M_analisis_memorias_mejorado import metodo_pseudo_mems


class ManualFaultGenerator:
    def __init__(self, elf_path: Path, map_path: Path):
        self.elf_path = Path(elf_path)
        self.map_path = Path(map_path)

        # Obtener rangos con metodo_pseudo_mems (debe devolver RAM-PARCIAL y opcional FLASH-PARCIAL)
        mem = metodo_pseudo_mems(self.elf_path, self.map_path)

        try:
            self.ram_start = int(mem["RAM-PARCIAL"][0], 16)
            self.ram_end = int(mem["RAM-PARCIAL"][1], 16)
        except Exception as e:
            raise RuntimeError(f"No se pudo obtener rango RAM desde metodo_pseudo_mems: {e}")

        flash_info = mem.get("FLASH-PARCIAL", None)
        if flash_info and flash_info[0] not in (None, "None") and flash_info[1] not in (None, "None"):
            self.flash_start = int(flash_info[0], 16)
            self.flash_end = int(flash_info[1], 16)
            self.flash_present = True
        else:
            # Simular flash en RAM si no existe
            self.flash_start = self.ram_start
            self.flash_end = self.ram_end
            self.flash_present = False
            print("⚠️  No se detectaron secciones FLASH en el ELF; se simulará FLASH usando el rango RAM.")

        # Registros/periféricos (puedes ajustar si requieres otros rangos)
        self.reg_start, self.reg_end = (0x40000000, 0x400FFFFF)

        # Intentar localizar .text
        tr = self._get_text_range()
        if tr:
            self.text_start, self.text_end = tr
        else:
            self.text_start, self.text_end = (None, None)

        # Determinar región del breakpoint (.text dentro de flash o ram)
        self.bp_region = self._determine_bp_region()

        # Mostrar rangos detectados en hex
        print("\n=== RANGOS DETECTADOS ===")
        print(f"RAM       : {self._fmt(self.ram_start)} - {self._fmt(self.ram_end)}")
        print(f"FLASH     : {self._fmt(self.flash_start)} - {self._fmt(self.flash_end)} {'(real)' if self.flash_present else '(simulada en RAM)'}")
        print(f"REGISTROS : {self._fmt(self.reg_start)} - {self._fmt(self.reg_end)}")
        if self.text_start:
            print(f".text     : {self._fmt(self.text_start)} - {self._fmt(self.text_end)}")
            print(f"Breakpoint region (forzada) -> {self.bp_region} (.text)")
        else:
            print("⚠️  No se detectó sección .text en el ELF; el breakpoint podrá ubicarse en FLASH (si hay) o en RAM.")
        print("==========================\n")

    # -----------------------------
    # Helpers
    # -----------------------------
    def _fmt(self, val: int) -> str:
        return f"0x{val:08X}"

    def _get_text_range(self) -> Optional[Tuple[int, int]]:
        """Lee el ELF y devuelve (start,end) de la sección .text si existe."""
        try:
            with open(self.elf_path, 'rb') as f:
                elf = ELFFile(f)
                for sec in elf.iter_sections():
                    if sec.name == ".text":
                        start = sec["sh_addr"]
                        size = sec["sh_size"]
                        if start is not None and size:
                            return (int(start), int(start + size - 1))
        except Exception as e:
            print(f"⚠️  No se pudo leer ELF para obtener .text: {e}")
        return None

    def _determine_bp_region(self) -> Optional[str]:
        """Determina si .text está en FLASH o en RAM; devuelve 'FLASH' o 'RAM' o None."""
        if self.text_start is None:
            return None
        if self.flash_start <= self.text_start <= self.flash_end:
            return "FLASH"
        if self.ram_start <= self.text_start <= self.ram_end:
            return "RAM"
        return None

    def _normalize_region(self, region_raw: str) -> Optional[str]:
        """Normaliza entradas de región a 'RAM','FLASH','REGISTROS'."""
        if not region_raw:
            return None
        r = region_raw.strip().lower()
        mapping = {
            # RAM aliases
            "ram": "RAM", "memory": "RAM", "mem": "RAM",
            # FLASH aliases
            "flash": "FLASH", "rom": "FLASH", "text": "FLASH",
            # REGISTROS / PERIFERICOS aliases
            "registros": "REGISTROS", "registro": "REGISTROS", "reg": "REGISTROS",
            "periferico": "REGISTROS", "periférico": "REGISTROS", "perifericos": "REGISTROS",
            "periféricos": "REGISTROS"
        }
        return mapping.get(r, None)

    # -----------------------------
    # Validación y alineación
    # -----------------------------
    def validar_direccion(self, region: str, direccion_hex: str) -> Tuple[bool, str]:
        """
        Valida que la dirección pertenezca al rango de la región.
        Para RAM y REGISTROS fuerza alineación a 4 bytes (redondeando hacia abajo)
        y devuelve la dirección formateada en hex.
        """
        region_can = self._normalize_region(region)
        if region_can is None:
            return False, "Región desconocida. Opciones válidas: RAM, FLASH, REGISTROS."

        if not direccion_hex:
            return False, "Dirección vacía."

        try:
            if not direccion_hex.startswith(("0x", "0X")):
                direccion_hex = "0x" + direccion_hex
            val = int(direccion_hex, 16)
        except ValueError:
            return False, "Formato hexadecimal inválido."

        if region_can == "RAM":
            s, e = self.ram_start, self.ram_end
        elif region_can == "FLASH":
            s, e = self.flash_start, self.flash_end
        else:  # REGISTROS
            s, e = self.reg_start, self.reg_end

        if not (s <= val <= e):
            return False, f"Dirección fuera del rango válido {self._fmt(s)} - {self._fmt(e)}."

        # Alineación automática para RAM y REGISTROS: redondear hacia abajo al múltiplo de 4
        if region_can in ("RAM", "REGISTROS"):
            if val % 4 != 0:
                aligned = val & ~0x3
                print(f"⚠️  Dirección {self._fmt(val)} no alineada a 32 bits; ajustada a {self._fmt(aligned)}")
                val = aligned

        return True, self._fmt(val)

    def validar_direccion_bp(self, direccion_hex: str) -> Tuple[bool, str]:
        """
        Validación específica para breakpoints: si .text existe, la dirección debe estar
        dentro de .text; si no existe, se permite en FLASH (si está presente) o en RAM.
        No se aplica alineación automática para breakpoints (pueden ser direcciones de instrucción).
        """
        if self.text_start is None:
            preferred = "FLASH" if self.flash_present else "RAM"
            return self.validar_direccion(preferred, direccion_hex)

        try:
            if not direccion_hex.startswith(("0x", "0X")):
                direccion_hex = "0x" + direccion_hex
            val = int(direccion_hex, 16)
        except ValueError:
            return False, "Formato hexadecimal inválido."

        if not (self.text_start <= val <= self.text_end):
            return False, f"Breakpoint fuera de .text: rango válido {self._fmt(self.text_start)} - {self._fmt(self.text_end)}."
        return True, self._fmt(val)

    # -----------------------------
    # Máscara
    # -----------------------------
    def generar_mascara(self, bit: Optional[int] = None) -> Tuple[str, int]:
        """Genera máscara de 1 bit en formato 32-bit y devuelve (mask_hex, bit_pos)."""
        bit_pos = bit if bit is not None else random.randint(0, 31)
        return f"0x{1 << bit_pos:08X}", bit_pos

    # -----------------------------
    # Interacción en consola
    # -----------------------------
    def solicitar_direccion_bp(self, msg: str) -> str:
        """
        Pide dirección de breakpoint validando que esté en .text (si existe)
        o en la región preferida si no hay .text.
        """
        if self.text_start:
            prompt = f"{msg} (debe pertenecer a .text {self._fmt(self.text_start)} - {self._fmt(self.text_end)}): "
        else:
            pref = "FLASH" if self.flash_present else "RAM"
            prompt = f"{msg} (no hay .text; se permitirá en {pref}): "

        while True:
            val = input(prompt).strip()
            ok, res = self.validar_direccion_bp(val)
            if ok:
                return res
            print(f"❌ {res}")

    def solicitar_direccion(self, region: str, msg: str) -> str:
        """Pide una dirección para RAM/FLASH/REGISTROS con validación y alineación si aplica."""
        while True:
            val = input(msg).strip()
            ok, res = self.validar_direccion(region, val)
            if ok:
                return res
            print(f"❌ {res}")

    def solicitar_mascara_interactiva(self) -> str:
        val = input("Máscara (0x..., vacío = aleatoria): ").strip()
        if not val:
            mask, bit = self.generar_mascara()
            print(f"   → Generada automáticamente: {mask} (bit {bit})")
            return mask
        try:
            if not val.startswith(("0x", "0X")):
                val = "0x" + val
            m = int(val, 16)
            if m == 0 or (m & (m - 1)) != 0 or m > 0xFFFFFFFF:
                print("   ⚠️  Máscara inválida; se generará automáticamente.")
                mask, bit = self.generar_mascara()
                return mask
            return f"0x{m:08X}"
        except ValueError:
            mask, bit = self.generar_mascara()
            print(f"   ⚠️  Valor inválido. Generada automáticamente: {mask} (bit {bit})")
            return mask

    # -----------------------------
    # Generador manual (modo consola)
    # -----------------------------
    def generar_fallas_manuales(self) -> List[Dict]:
        lista: List[Dict] = []
        while True:
            try:
                n = int(input("Número de fallas a ingresar: ").strip())
                if n <= 0:
                    print("Ingrese un número entero positivo.")
                    continue
                break
            except ValueError:
                print("Número inválido. Intente de nuevo.")

        for i in range(1, n + 1):
            print(f"\n=== FALLA {i} ===")

            # Breakpoint: forzado a .text si existe
            if self.text_start:
                print(f"Nota: el breakpoint debe situarse en la sección .text ({self._fmt(self.text_start)} - {self._fmt(self.text_end)}).")
                dir_bp = self.solicitar_direccion_bp("Dirección breakpoint (ej. 0x08000190)")
                region_bp_final = self.bp_region or ("FLASH" if self.flash_present else "RAM")
            else:
                region_bp_raw = input("Región breakpoint (Flash/RAM/Registros) [Flash]: ").strip() or "Flash"
                region_bp = self._normalize_region(region_bp_raw) or "FLASH"
                if not self.flash_present and region_bp == "FLASH":
                    print("⚠️  No hay FLASH real; se usará RAM.")
                    region_bp = "RAM"
                dir_bp = self.solicitar_direccion(region_bp, f"Dirección breakpoint [{region_bp}]: ")
                region_bp_final = region_bp

            # Inyección: RAM o REGISTROS
            region_iny_raw = input("Región de inyección (RAM/Registros) [RAM]: ").strip() or "RAM"
            region_iny = self._normalize_region(region_iny_raw) or "RAM"
            dir_iny = self.solicitar_direccion(region_iny, f"Dirección de inyección [{region_iny}]: ")

            mascara = self.solicitar_mascara_interactiva()
            tipo_falla = input("Tipo de falla (bitflip/stuck-at-0/stuck-at-1) [bitflip]: ").strip().lower() or "bitflip"
            if tipo_falla not in ["bitflip", "stuck-at-0", "stuck-at-1"]:
                print("⚠️ Tipo inválido, se usará 'bitflip'.")
                tipo_falla = "bitflip"

            entry = {
                "FAULT_ID": i,
                "UBICACION": region_iny,
                "TIPO_FALLA": tipo_falla,
                "DIRECCION STOP": dir_bp,
                #"REGION_INYECCION": region_bp_final,
                "DIRECCION INYECCION": dir_iny,
                "MASCARA": mascara

            }
            lista.append(entry)

        return lista

    # -----------------------------
    # Guardar CSV
    # -----------------------------
    def guardar_csv(self, lista: List[Dict], out_path: Path):
        if not lista:
            print("No hay filas para guardar.")
            return
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(lista[0].keys()))
            writer.writeheader()
            for row in lista:
                writer.writerow(row)
        print(f"\n✅ Archivo CSV generado: {out_path}")


# ---------------------------
# Bloque principal (prueba)
# ---------------------------
if __name__ == "__main__":
    # Ajusta estas rutas a tu entorno
    ELF = Path(r"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf")
    MAP = Path(r"/Users/apple/Documents/PruebasST/LED/Debug/LED.map")
    OUT = Path("LISTA_FALLAS_MANUAL.csv")
    #"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"
    #"/Users/apple/Documents/PruebasST/LED/Debug/LED.map"

    gen = ManualFaultGenerator(ELF, MAP)
    fallas = gen.generar_fallas_manuales()
    gen.guardar_csv(fallas, OUT)
    print("\nHecho.")

# r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"
# r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.map"