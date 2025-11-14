#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Programación directa de ELF en RAM vía pyOCD (escritura por segmentos PT_LOAD).
Esta ruta es más robusta para reprogramar firmware que vive en RAM cuando
FileProgrammer falla por problemas con el core en ejecución.
Requisitos: pip install pyocd pyelftools
"""

import os
import time
import struct
from pyocd.core.helpers import ConnectHelper
from elftools.elf.elffile import ELFFile

class MCU_Programmer:
    def __init__(self, opts, elf_path, verify=True, retries=2):
        self.opts = opts
        self.elf_path = elf_path
        self.session = None
        self.core = None
        self.verify = verify
        self.retries = int(retries)

    def __enter__(self):
        self.session = ConnectHelper.session_with_chosen_probe(options=self.opts)
        if self.session is None:
            raise RuntimeError("[ERROR] No se detectó ningún debugger conectado.")
        self.session.open()
        print("[INFO] Sesión pyOCD abierta.")
        target = self.session.board.target
        self.core = getattr(target, "selected_core", target)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            try:
                self.session.close()
                print("[INFO] Sesión pyOCD cerrada.")
            except Exception as e:
                print(f"[WARN] Error al cerrar sesión: {e}")

    # ---------------------------------------------------------
    # Halt fuerte: intenta garantizar que el core y el bus estén libres
    # ---------------------------------------------------------
    def halt_fuerte(self):
        """Intenta detener el core de forma robusta para permitir escritura en RAM."""
        try:
            self.core.halt()
        except Exception:
            pass
        time.sleep(0.02)

        # Intentos adicionales: reinvocar halt y una pequeña espera
        try:
            self.core.halt()
        except Exception:
            pass
        time.sleep(0.02)

        # Lectura/Escritura corta a registros de depuración para forzar sincronización
        # (no todos los targets permiten escribir DHCSR directamente; si falla, lo ignoramos)
        try:
            # Dirección DHCSR (Cortex-M) 0xE000EDF0 - escribir tiene restricciones en hardware,
            # así que lo hacemos solo si write_memory no lanza excepción.
            # NOTA: algunos probes rechazan escribir ahí; por eso lo intentamos en try/except.
            DHCSR = 0xE000EDF0
            # Valor con C_DEBUGEN y C_HALT bits a 1 (0xA05F0003)
            self.core.write_memory(DHCSR, 0xA05F0003)
            time.sleep(0.01)
        except Exception:
            # no crítico, continuar
            pass

        # Un último halt y small delay
        try:
            self.core.halt()
        except Exception:
            pass
        time.sleep(0.02)

    # ---------------------------------------------------------
    # Escritura directa del ELF en RAM (segmentos PT_LOAD)
    # ---------------------------------------------------------
    def programar_elf_ram_direct(self):
        """
        Escribe directamente en memoria RAM los segmentos PT_LOAD del ELF.
        Verifica (si self.verify == True) leyendo y comparando.
        """
        if not os.path.isfile(self.elf_path):
            raise FileNotFoundError(f"[ERROR] ELF no existe: {self.elf_path}")

        # 1) Asegurarnos de que el core está detenido completamente
        print("[INFO] Aplicando halt fuerte antes de escribir RAM...")
        self.halt_fuerte()

        # 2) Parsear ELF y obtener segmentos PT_LOAD
        with open(self.elf_path, 'rb') as f:
            ef = ELFFile(f)
            load_segments = [seg for seg in ef.iter_segments() if seg['p_type'] == 'PT_LOAD']
            if not load_segments:
                raise RuntimeError("No se encontraron segmentos PT_LOAD en el ELF.")

            # 3) Intentar varias veces (retries) en caso de fallo transitorio
            last_exc = None
            for attempt in range(self.retries + 1):
                try:
                    for seg in load_segments:
                        paddr = seg['p_paddr']   # dirección física donde se desea cargar
                        data = seg.data()
                        size = len(data)
                        if size == 0:
                            continue

                        print(f"[INFO] Escribiendo segmento: {hex(paddr)} len={size}")
                        # Escribimos de 4 en 4 bytes para eficiencia
                        addr = paddr
                        i = 0
                        # Escribir palabras de 4 bytes cuando sea posible
                        while i + 4 <= size:
                            word = struct.unpack_from('<I', data, i)[0]
                            self.core.write_memory(addr, word)
                            addr += 4
                            i += 4

                        # Escribir los bytes restantes (1..3)
                        while i < size:
                            # leer un byte y escribirlo. write_memory admite escribir palabra;
                            # hacemos word con el byte en LSB y escribimos en la dirección con tamaño 8 bits
                            # No todos los backends aceptan ancho 8, así que hacemos read-modify-write de palabra.
                            byte = data[i]
                            # Leemos la palabra actual alineada a 4 para reemplazar el byte correspondiente
                            aligned_addr = addr & ~0x3
                            try:
                                cur_word = self.core.read_memory(aligned_addr)
                            except Exception:
                                # si no podemos leer, inicializamos a 0xFFFFFFFF como fallback
                                cur_word = 0xFFFFFFFF
                            # calcular desplazamiento dentro de la palabra
                            offset = addr & 0x3
                            # montar nueva palabra
                            mask = 0xFF << (offset * 8)
                            new_word = (cur_word & ~mask) | (byte << (offset * 8))
                            self.core.write_memory(aligned_addr, new_word)
                            addr += 1
                            i += 1

                    # 4) Verificación opcional
                    if self.verify:
                        print("[INFO] Verificando segmentos escritos...")
                        ok = True
                        for seg in load_segments:
                            paddr = seg['p_paddr']
                            data = seg.data()
                            size = len(data)
                            addr = paddr
                            i = 0
                            while i + 4 <= size:
                                expected_word = struct.unpack_from('<I', data, i)[0]
                                read_word = self.core.read_memory(addr)
                                if expected_word != read_word:
                                    print(f"[ERROR] Verificación falló en 0x{addr:08X}: esperado 0x{expected_word:08X} leido 0x{read_word:08X}")
                                    ok = False
                                    break
                                addr += 4
                                i += 4
                            if not ok:
                                break
                            # comparar restantes bytes
                            while i < size and ok:
                                aligned_addr = addr & ~0x3
                                read_word = self.core.read_memory(aligned_addr)
                                offset = addr & 0x3
                                read_byte = (read_word >> (offset * 8)) & 0xFF
                                expected_byte = data[i]
                                if read_byte != expected_byte:
                                    print(f"[ERROR] Verificación byte falló en 0x{addr:08X}: esperado 0x{expected_byte:02X} leido 0x{read_byte:02X}")
                                    ok = False
                                    break
                                addr += 1
                                i += 1
                        if not ok:
                            raise RuntimeError("Verificación de escritura falló (intentar de nuevo).")
                        else:
                            print("[INFO] Verificación OK.")
                    # si llegamos hasta aquí, todo bien
                    print("[INFO] Programación directa de ELF en RAM completada con éxito.")
                    return

                except Exception as e:
                    last_exc = e
                    print(f"[WARN] Intento {attempt+1} falló: {e}")
                    # intentar volver a haltear y reintentar
                    time.sleep(0.05)
                    try:
                        self.halt_fuerte()
                    except Exception:
                        pass

            # si terminan los intentos y sigue fallando:
            raise RuntimeError(f"[ERROR] No se pudo programar ELF en RAM tras {self.retries+1} intentos. Ultima excepción: {last_exc}")

    # ---------------------------------------------------------
    # API simple: mutualizar con tu flujo
    # ---------------------------------------------------------
    def programar_elf(self):
        """
        Compatibilidad: por defecto usamos escritura directa en RAM si el ELF parece tener
        vectores en 0x2000... (RAM). Si quisieras usar FileProgrammer para flash,
        podríamos detectarlo y usarlo.
        """
        # Detectar si ELF contiene .isr_vector en 0x2000... -> asumimos RAM
        with open(self.elf_path, 'rb') as f:
            ef = ELFFile(f)
            sec = ef.get_section_by_name('.isr_vector')
            if sec is not None:
                vaddr = sec['sh_addr']
                if 0x20000000 <= vaddr <= 0x2FFFFFFF:
                    # Es firmware RAM: usar escritura directa
                    self.programar_elf_ram_direct()
                    return

        # Si no es RAM (o no encontramos .isr_vector), fallback: usar FileProgrammer
        # (esto requiere pyOCD FileProgrammer, pero lo dejamos como fallback)
        try:
            from pyocd.flash.file_programmer import FileProgrammer
            print("[INFO] ELF no detectado como RAM. Intentando FileProgrammer (fallback).")
            # halt fuerte antes de flash por si acaso
            self.halt_fuerte()
            FileProgrammer(self.session).program(self.elf_path)
            print("[INFO] FileProgrammer completado.")
        except Exception as e:
            raise RuntimeError(f"[ERROR] FileProgrammer falló: {e}")

if __name__ == "__main__":
    opts = {
        "frequency": 1800000,
        "connect_mode": "under_reset",
        "halt_on_connect": True,
        "resume_on_disconnect": False,
        "reset_type": "hw",
        "enable_semihosting": False
    }
    elf_path = "/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"

    with MCU_Programmer(opts, elf_path) as mcu:
        # primera ejecución
        mcu.programar_elf()   # ahora usa el método directo en RAM
        pcs = mcu.core.read_core_register('pc')
        print(f'[HOLAA] {hex(pcs)}')
