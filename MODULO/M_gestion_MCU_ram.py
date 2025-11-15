#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M_gestion_mcu_auto.py

Módulo para gestionar sesión pyOCD y arrancar automáticamente desde la dirección
de la tabla de vectores indicada en cualquier ELF (.isr_vector.sh_addr).

Requisitos:
    pip install pyocd pyelftools

Uso:
    python M_gestion_mcu_auto.py
(ajusta elf_path en el bloque __main__ o cambia por argumentos)
"""
import os
import time
from pyocd.core.helpers import ConnectHelper
from pyocd.flash.file_programmer import FileProgrammer
from elftools.elf.elffile import ELFFile

# Dirección del VTOR (SCB->VTOR) en Cortex-M
VTOR_ADDR = 0xE000ED08

class MCU_RAM:
    def __init__(self, opts, elf_path):
        """
        opts: diccionario con las opciones de pyOCD (frecuencia, reset, etc.)
        elf_path: ruta del archivo ELF que se desea programar
        """
        self.opts = opts
        self.elf_path = elf_path
        self.session = None
        self.core = None
        self.target = None
        self.programmer = None

    def __enter__(self):
        """
        Abre sesión con pyOCD y prepara objetos (no programa automáticamente).
        """
        self.session = ConnectHelper.session_with_chosen_probe(options=self.opts)
        if self.session is None:
            raise RuntimeError("[ERROR] No se detectó ningún probe compatible. ¿Está conectado?")
        self.session.open()
        print("[INFO] Sesión pyOCD abierta correctamente.")

        self.target = self.session.board.target
        self.core = getattr(self.target, "selected_core", self.target)
        self.programmer = FileProgrammer(self.session)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Cierra la sesión de forma segura.
        """
        if self.session:
            try:
                self.session.close()
                print("[INFO] Sesión pyOCD cerrada.")
            except Exception as e:
                print(f"[WARN] Error cerrando sesión: {e}")
            finally:
                self.session = None
                self.core = None
                self.target = None
                self.programmer = None

    def program_elf(self):
        """
        Programa el ELF usando FileProgrammer (pyOCD respetará las direcciones LMA).
        """
        if not os.path.isfile(self.elf_path):
            raise FileNotFoundError(f"No existe ELF: {self.elf_path}")
        print(f"[INFO] Programando ELF: {self.elf_path}")
        self.programmer.program(self.elf_path)
        print("[INFO] Programación completada.")

    def obtener_vector_base_desde_elf(self):
        """
        Devuelve la dirección (sh_addr) de la sección .isr_vector del ELF.
        Lanza excepción si no encuentra la sección.
        """
        with open(self.elf_path, 'rb') as f:
            ef = ELFFile(f)
            sec = ef.get_section_by_name('.isr_vector')
            if sec is None:
                raise ValueError("No se encontró la sección .isr_vector en el ELF.")
            return sec['sh_addr']

    def boot_from_elf_vector(self, force_program=True, halt_before_program=True):
        """
        Programa (opcional) y arranca el MCU de forma automática usando la dirección
        de .isr_vector del ELF. Comporta:
            - si vector_base está en RAM (0x2000...), escribe VTOR=vector_base,
              carga SP/PC desde memoria y resume() => ejecución desde RAM.
            - si vector_base está en FLASH (0x0800...), hará reset() para arrancar desde Flash.
        Parámetros:
            force_program: si True siempre programa el ELF (recomendado para reinicios limpios).
            halt_before_program: si True intenta reset_and_halt() antes de programar (necesario para RAM).
        """
        # 1) Opcional: halt antes de programar (muy importante si vamos a escribir RAM)
        if halt_before_program:
            try:
                print("[INFO] Intentando reset_and_halt() antes de programar...")
                self.core.reset_and_halt()
                time.sleep(0.01)
                print("[INFO] Core detenido (halt).")
            except Exception as e:
                print(f"[WARN] No se pudo haltear el core antes de programar: {e}")

        # 2) Programar ELF si lo solicitamos
        if force_program:
            self.program_elf()

        # 3) Obtener la dirección de la tabla de vectores desde el ELF
        try:
            vector_base = self.obtener_vector_base_desde_elf()
        except Exception as e:
            raise RuntimeError(f"[ERROR] No se pudo obtener .isr_vector desde ELF: {e}")

        print(f"[INFO] .isr_vector.sh_addr detectado en ELF: 0x{vector_base:08X}")

        # 4) Leer SP y ResetHandler desde la memoria del target (en vector_base)
        try:
            sp = self.core.read_memory(vector_base)
            reset_handler = self.core.read_memory(vector_base + 4)
        except Exception as e:
            raise RuntimeError(f"[ERROR] No se pudo leer SP/ResetHandler desde target en 0x{vector_base:08X}: {e}")

        print(f"[INFO] SP leído: 0x{sp:08X}, ResetHandler leído: 0x{reset_handler:08X}")

        # 5) Si la tabla está en RAM -> configurar VTOR, escribir SP/PC y resume
        if 0x20000000 <= vector_base <= 0x2007FFFF:
            print("[INFO] Vector table en RAM detectada. Arrancando desde RAM...")
            try:
                # escribir VTOR

                self.core.write_memory(VTOR_ADDR, vector_base)
                time.sleep(0.005)
                vtor_read = self.core.read_memory(VTOR_ADDR)
                print(f"[INFO] VTOR escrito: 0x{vtor_read:08X}")
            except Exception as e:
                raise RuntimeError(f"[ERROR] No se pudo escribir VTOR: {e}")

            # escribir SP y PC en core
            try:
                self.core.write_core_register('sp', sp)
                self.core.write_core_register('pc', reset_handler)
                print(f"[INFO] SP/PC escritos en core: SP=0x{sp:08X}, PC=0x{reset_handler:08X}")
            except Exception as e:
                # intentar con r13/r15 si falla
                try:
                    self.core.write_core_register('r13', sp)
                    self.core.write_core_register('r15', reset_handler)
                    print("[INFO] SP/PC escritos en core usando r13/r15.")
                except Exception as e2:
                    raise RuntimeError(f"[ERROR] No se pudo escribir SP/PC en el core: {e} / {e2}")

            # reanudar ejecución (sin reset final)
            try:

                self.core.resume()
                print("[INFO] MCU reanudado: ejecutando ELF desde RAM.")
            except Exception as e:
                raise RuntimeError(f"[ERROR] No se pudo reanudar el core: {e}")

        # 6) Si la tabla está en FLASH -> reset para arrancar desde Flash
        elif (0x08000000 <= vector_base <= 0x080FFFFF) or (vector_base >= 0x08000000):
            print("[INFO] Vector table en Flash detectada. Se realizará reset para arrancar desde Flash.")
            try:
                # Asegurarse de que el core no esté en un estado que impida el reset
                # reset() hará que la CPU arranque desde la tabla de vectores en Flash
                self.core.reset()
                time.sleep(0.02)
                print("[INFO] MCU reseteado para arrancar desde Flash.")
            except Exception as e:
                raise RuntimeError(f"[ERROR] No se pudo resetear el core para arrancar desde Flash: {e}")

        else:
            # Direcciones fuera de los rangos esperados; avisar y tratar como RAM por defecto
            print(f"[WARN] Vector_base 0x{vector_base:08X} fuera de rangos RAM/FLASH comunes. Intentando arrancar desde esa dirección.")
            try:
                self.core.write_memory(VTOR_ADDR, vector_base)
                self.core.write_core_register('sp', sp)
                self.core.write_core_register('pc', reset_handler)

                #self.core.resume()
                print("[INFO] Intento de arranque desde dirección no estándar completado.")
            except Exception as e:
                raise RuntimeError(f"[ERROR] No se pudo arrancar desde vector_base no estándar: {e}")


# ------------------------ EJEMPLO DE USO ------------------------ #
if __name__ == '__main__':
    # Ajusta estas opciones si necesitas forzar target_override, etc.
    opts = {
        "frequency": 1800000,
        "connect_mode": "under_reset",
        "halt_on_connect": True,
        "resume_on_disconnect": False,
        "reset_type": "hw",
        "vector_catch": "reset,hardfault,memmanage,busfault,usagefault",
        "enable_semihosting": False
    }

    # Cambia la ruta al ELF que quieras probar
    elf_path = r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"

    # Abro sesión y arranco según .isr_vector del ELF
    try:
        with MCU_RAM(opts, elf_path) as mcu:
            print("[INFO] Sesión abierta. Preparando arranque desde ELF...")
            # force_program=True (programa siempre), halt_before_program=True (haltar antes de programar)
            mcu.boot_from_elf = mcu.boot_from_elf if hasattr(mcu, 'boot_from_elf') else None  # compatibilidad
            # Llamamos al método: programar y arrancar según .isr_vector del ELF
            mcu.boot_from_elf = mcu.boot_from_elf if False else None  # placeholder (no hace nada)
            # Usamos la función dedicada:
            mcu.boot_from_elf = None  # limpia
            # Llamamos al método 'boot_from_elf_vector' directamente:
            mcu.boot_from_elf_vector(force_program=True, halt_before_program=True)

            # Aquí puedes realizar lecturas/escrituras o tus inyecciones de falla
            # Ejemplo sencillo de lectura/escritura:
            try:
                v = mcu.core.read_memory(0x20000000)
                print(f"Valor en 0x20000000: {hex(v)}")
                mcu.core.write_memory(0x20000000, 0x1234)
                print("Escribimos 0x1234 en 0x20000000")
                v2 = mcu.core.read_memory(0x20000000)
                print(f"Nuevo valor en 0x20000000: {hex(v2)}")
            except Exception as e:
                print(f"[WARN] Error leyendo/escribiendo memoria: {e}")

    except Exception as e:
        print(f"[ERROR] Excepción principal: {e}")


if __name__ == '__main__':
    # Opciones de conexión (ajusta si hace falta)
    opts = {
        "frequency": 1800000,
        "connect_mode": "under_reset",
        "halt_on_connect": True,
        "resume_on_disconnect": False,
        "reset_type": "hw",
        "vector_catch": "reset,hardfault,memmanage,busfault,usagefault",
        "enable_semihosting": False
    }

    # Ruta al ELF (ajusta según tu sistema)
    elf_path = r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"

    try:
        with MCU_RAM(opts, elf_path) as mcu:
            print("[INFO] Sesión abierta. Programando y arrancando según .isr_vector (se dejará detenido).")
            # Programa y arranca según la tabla de vectores; el método intentará halt antes de programar
            mcu.boot_from_elf_vector(force_program=True, halt_before_program=True)

            # Asegurarnos de que el core esté detenido y mostrar PC/SP
            try:
                mcu.core.halt()
            except Exception:
                # Puede ya estar detenido; seguir de todas formas
                pass

            try:
                pc = mcu.core.read_core_register('pc')
                sp = mcu.core.read_core_register('sp')
                print(f"[INFO] CPU actualmente detenida. PC=0x{pc:08X}, SP=0x{sp:08X}")
            except Exception as e:
                print(f"[WARN] No se pudieron leer registros: {e}")

            print('se va a reprogramar el micro')
            mcu.core.resume()
            time.sleep(3)
            mcu.core.reset_and_halt()
            mcu.core.resume()
            time.sleep(3)
            mcu.core.halt()
            mcu.boot_from_elf_vector(force_program=True, halt_before_program=True)
            mcu.core.resume()


    except Exception as e:
        print(f"[ERROR] Excepción principal: {e}")

