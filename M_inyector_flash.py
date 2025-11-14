#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M_inyector_flash.py

Inyector de fallas con reprogramación temporal del MCU (ELF alterno) ANTES de
cada falla que tenga ubic == 'flash'. Evita abrir dos sesiones simultáneas al probe.

Cambios clave implementados:
- Para fallas FLASH: se abre una sesión temporal MCU_RAM, se programa el ELF alterno
  y SE INYECTA MIENTRAS ESA SESIÓN ESTÁ ABIERTA (no se reabre la sesión principal
  antes de inyectar). Esto evita que un "reopen" reseteé la CPU y borre el ELF en RAM.
- Para fallas RAM/REGISTRO: se usa la sesión principal (MCU) que se abrió al inicio.
- No se usa reset_and_halt() antes de inyectar en FLASH; sólo se hace halt() (si es necesario)
  para conservar la ejecución en RAM.

Asegúrate de ajustar rutas de ELF y los wrappers MCU/MCU_RAM si usan nombres distintos.
"""

import csv
import os
import time
from datetime import datetime
from M_deteccion_stop import detectar_while_infinito

# IMPORTS de gestión de MCU (asegúrate de que estos módulos existan y funcionen)
from M_gestion_MCU_ram import MCU_RAM
from M_gestion_mcu import MCU


def parse_int_optional(s):
    if s is None:
        return None
    s = str(s).strip()
    if s == '':
        return None
    try:
        return int(s, 0)
    except ValueError:
        raise ValueError(f"Valor numérico inválido: {s}")


def _to_hex_safe(val):
    """
    Convierte un valor entero a '0xXXXXXXXX' de 8 dígitos.
    Si val no es entero válido, devuelve '0x00000000'.
    """
    try:
        if val is None:
            return "0x00000000"
        ival = int(val)
        return f"0x{(ival & 0xFFFFFFFF):08X}"
    except Exception:
        return "0x00000000"


class FALLA:
    def __init__(self, id_falla, direccion_inyeccion, direccion_breakpoint, mascara, tipo, ubicacion):
        self.id_falla = id_falla
        self.direccion_inyeccion = direccion_inyeccion
        self.direccion_breakpoint = direccion_breakpoint
        self.mascara = mascara
        self.tipo = tipo
        self.ubicacion = ubicacion

    def aplicar(self, core):
        if self.direccion_inyeccion is None or self.mascara is None:
            return None

        try:
            valor_actual = core.read_memory(self.direccion_inyeccion, 32)
        except Exception as e:
            print(f"[WARNING] No se pudo leer memoria para aplicar falla (addr {self.direccion_inyeccion}): {e}")
            return None

        tipo_lower = str(self.tipo).lower() if self.tipo else ''
        valor_con_falla = None

        if 'bitflip' in tipo_lower or 'biflip' in tipo_lower:
            valor_con_falla = valor_actual ^ self.mascara
        elif 'stuck' in tipo_lower and '0' in tipo_lower:
            valor_con_falla = valor_actual & ~self.mascara
        elif 'stuck' in tipo_lower and '1' in tipo_lower:
            valor_con_falla = valor_actual | self.mascara
        else:
            print(f"[WARNING] Tipo de falla desconocido: {self.tipo}")
            return None

        try:
            core.write_memory(self.direccion_inyeccion, valor_con_falla, 32)
        except Exception as e:
            print(f"[WARNING] No se pudo escribir la falla en memoria (addr {self.direccion_inyeccion}): {e}")
            return None

        return valor_con_falla


class FaultInjector:
    def __init__(self, mcu, csv_file, main_elf_path, main_opts):
        """
        Recibe una sesión principal (mcu) abierta con MCU(opts, elf) como contexto.
        Guarda rutas y opts para poder reabrir la sesión principal cuando sea necesario.
        """
        # sesión principal (puede ser None si no se abrió)
        self.mcu = mcu
        self.core = getattr(mcu, 'core', None)
        self.session = getattr(mcu, 'session', None)

        self.csv_file = csv_file
        self.elf_path = main_elf_path
        self.opts = main_opts

        self.lista_fallas = []
        self.no_inyectadas = 0
        self.no_inyectadas_valor_no_escrito = 0
        self.no_lectura = 0

        # cargamos fallas
        self.cargar_csv()

        resultado = detectar_while_infinito(self.elf_path)
        addr_salto, _ = resultado
        self.stop_address = addr_salto
        print(f"[INFO] Stop address detectada: 0x{self.stop_address:08X}")

        # NOTA: NO ponemos stop_address automáticamente aquí (evita resets al reabrir sesiones)
        # Se podrá poner cuando haga sentido en el flujo.

        # Inicializa archivos (header dinámico según lista_fallas)
        self.inicializar_archivos()

    def cargar_csv(self):
        with open(self.csv_file, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    id_falla = int(row['FAULT_ID'])
                    ubic = (row.get('UBICACION') or '').strip()
                    dir_iny = parse_int_optional(row.get('DIRECCION INYECCION'))
                    dir_bp = parse_int_optional(row.get('DIRECCION STOP'))
                    mascara = parse_int_optional(row.get('MASCARA'))
                    tipo = row.get('TIPO_FALLA')

                    falla = FALLA(id_falla, dir_iny, dir_bp, mascara, tipo, ubic)
                    self.lista_fallas.append(falla)

                except Exception as e:
                    print(f"[WARNING] Fila ignorada: {e}")

        print(f"[INFO] {len(self.lista_fallas)} fallas cargadas.")

    def inicializar_archivos(self):
        campaign_name = datetime.now().strftime("campaign_%Y%m%d_%H%M%S")
        self.campaign_dir = os.path.join(os.path.dirname(self.csv_file), campaign_name)
        os.makedirs(self.campaign_dir, exist_ok=True)
        print(f"[INFO] Carpeta de campaña creada: {self.campaign_dir}")

        # snapshot files
        self.snapshot_before_csv = os.path.join(self.campaign_dir, 'snapshots_before.csv')
        self.snapshot_after_csv = os.path.join(self.campaign_dir, 'snapshots_after.csv')
        self.snapshot_after_stable_csv = os.path.join(self.campaign_dir, 'snapshots_after_stable.csv')

        # decidir mem cols
        hay_memoria = any((f.ubicacion or '').lower() in ['ram', 'flash'] for f in self.lista_fallas)
        self.mem_cols_count = 256 if hay_memoria else 1

        mem_cols = [f"MEM_{i}" for i in range(self.mem_cols_count)]
        header = ['Test_ID', 'Fault_ID', 'PC', 'SP', 'LR'] + [f'R{i}' for i in range(13)] + mem_cols

        for path in [self.snapshot_before_csv, self.snapshot_after_csv, self.snapshot_after_stable_csv]:
            try:
                with open(path, 'w', newline='') as f:
                    csv.writer(f).writerow(header)
                print(f"[INFO] Creado archivo: {path} (MEM cols: {self.mem_cols_count})")
            except Exception as e:
                print(f"[WARNING] No se pudo crear {path}: {e}")

        self.faults_log_csv = os.path.join(self.campaign_dir, 'faults_log.csv')
        try:
            with open(self.faults_log_csv, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Fault_ID',
                    'Direccion_Inyeccion',
                    'Direccion_BP',
                    'Tipo',
                    'Mascara',
                    'Ubicacion',
                    'Valor_Original',
                    'Valor_Falla',
                    'Valor_Leido',
                    'Estado'
                ])
            print(f"[INFO] Archivo de log de fallas creado: {self.faults_log_csv}")
        except Exception as e:
            print(f"[WARNING] No se pudo crear faults_log.csv: {e}")

    def snapshot_registros(self):
        if self.core is None:
            return {}
        if not self.esperar_halt():
            print("[WARNING] esperar_halt() falló al intentar leer registros")
            return {}

        regs = {}
        try:
            regs['pc'] = self.core.read_core_register('pc')
        except Exception:
            regs['pc'] = 0
        try:
            regs['sp'] = self.core.read_core_register('sp')
        except Exception:
            regs['sp'] = 0
        try:
            regs['lr'] = self.core.read_core_register('lr')
        except Exception:
            regs['lr'] = 0

        for i in range(13):
            try:
                regs[f'r{i}'] = self.core.read_core_register(f'r{i}')
            except Exception:
                regs[f'r{i}'] = 0

        return regs

    def snapshot_memoria_bloque(self, direccion, tamano_bytes):
        mem = []
        if tamano_bytes is None or tamano_bytes <= 0:
            return mem
        for ofs in range(0, tamano_bytes, 4):
            try:
                mem.append(self.core.read_memory(direccion + ofs, 32))
            except Exception:
                mem.append(0)
        return mem

    def construir_snapshot_dict(self, registros, memoria):
        snap = {}
        snap['PC'] = _to_hex_safe(registros.get('pc', 0))
        snap['SP'] = _to_hex_safe(registros.get('sp', 0))
        snap['LR'] = _to_hex_safe(registros.get('lr', 0))

        for i in range(13):
            snap[f'R{i}'] = _to_hex_safe(registros.get(f'r{i}', 0))

        for i in range(self.mem_cols_count):
            val = memoria[i] if i < len(memoria) else 0
            snap[f'MEM_{i}'] = _to_hex_safe(val)

        return snap

    def guardar_snapshot(self, tipo, test_id, fault_id, snap):
        if tipo == 'before':
            path = self.snapshot_before_csv
        elif tipo == 'after':
            path = self.snapshot_after_csv
        else:
            path = self.snapshot_after_stable_csv

        row = [test_id, fault_id, snap['PC'], snap['SP'], snap['LR']]
        row += [snap[f'R{i}'] for i in range(13)]
        for i in range(self.mem_cols_count):
            row.append(snap.get(f'MEM_{i}', _to_hex_safe(0)))

        with open(path, 'a', newline='') as f:
            csv.writer(f).writerow(row)

    def log_falla(self, falla, valor_original, valor_con_falla, valor_leido, estado):
        try:
            with open(self.faults_log_csv, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    falla.id_falla,
                    _to_hex_safe(falla.direccion_inyeccion),
                    _to_hex_safe(falla.direccion_breakpoint),
                    falla.tipo,
                    _to_hex_safe(falla.mascara),
                    falla.ubicacion,
                    _to_hex_safe(valor_original),
                    _to_hex_safe(valor_con_falla),
                    _to_hex_safe(valor_leido),
                    estado
                ])
        except Exception as e:
            print(f"[WARNING] No se pudo escribir en faults_log.csv: {e}")

    def esperar_halt(self, timeout=5.0):
        if self.core is None:
            return False
        t0 = time.time()
        while not self.core.is_halted():
            if time.time() - t0 > timeout:
                return False
            time.sleep(0.01)
        return True

    # ------------------------------------------------------------------
    #   INYECCIÓN DE FALLA
    # ------------------------------------------------------------------
    def inject(self, falla, max_retries=10, delay=0.05):

        ubic = (falla.ubicacion or '').lower()

        # Limpiar breakpoints temporales sin tocar bp_stop
        try:
            if self.core is not None:
                for bp in self.core.get_breakpoints():
                    addr = getattr(bp, 'address', None)
                    if addr is None and isinstance(bp, dict):
                        addr = bp.get('address')

                    if addr not in [None, self.stop_address]:
                        try:
                            self.core.remove_breakpoint(addr)
                        except Exception:
                            pass
        except Exception:
            pass

        # Caso FLASH: antes de inyectar, crear sesión temporal MCU_RAM, programar y INYECTAR mientras esa sesión está abierta
        if ubic in ['flash']:
            opts2 = self.opts.copy()
            elf_path2 = r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"

            # Cerrar sesión principal si está abierta (liberar probe)
            if self.session is not None:
                try:
                    try:
                        self.session.close()
                    except Exception:
                        pass
                finally:
                    self.mcu = None
                    self.core = None
                    self.session = None

            # Abrir sesión temporal y hacer TODO dentro del context manager
            try:
                with MCU_RAM(opts2, elf_path2) as mcu_ram:
                    print("[INFO] Sesión temporal abierta para programar e inyectar (FLASH).")

                    # Intentar preparar el core sin reset: boot_from_elf_vector ya programa y posiciona PC/SP
                    try:
                        print(f"[INFO] Programando ELF alterno: {elf_path2}")
                        mcu_ram.boot_from_elf_vector(force_program=True, halt_before_program=True)
                    except Exception as e:
                        print(f"[ERROR] Error programando ELF alterno: {e}")
                        raise

                    # asignar core temporal para la inyección
                    self.mcu = mcu_ram
                    self.core = getattr(mcu_ram, 'core', None)
                    self.session = getattr(mcu_ram, 'session', None)

                    # Ahora inyectar mientras la sesión mcu_ram está abierta
                    result = self._inj_memoria_flash(falla, 256, delay)

                    # Al salir del with la sesión temporal se cerrará automáticamente
                    return result

            except Exception as e:
                print(f"[ERROR] Falló reprogramación/inyección FLASH: {e}")
                self.no_inyectadas += 1
                try:
                    self.log_falla(falla, None, None, None, "NO_INYECTADA_REPROG_ERROR")
                except Exception:
                    pass
                return

        # Caso REGISTRO (1 palabra)
        elif ubic == 'registro':
            # Asegurar sesión principal abierta
            if self.core is None:
                try:
                    # reabrir sesión principal
                    temp_mcu = MCU(self.opts, self.elf_path)
                    self.mcu = temp_mcu.__enter__()
                    self.core = getattr(self.mcu, 'core', None)
                    self.session = getattr(self.mcu, 'session', None)
                except Exception as e:
                    print(f"[ERROR] No se pudo abrir sesión principal para registro: {e}")
                    self.no_inyectadas += 1
                    return
            return self._inj_memoria(falla, 4, delay)

        # Caso RAM (256 bytes)
        elif ubic == 'ram':
            if self.core is None:
                try:
                    temp_mcu = MCU(self.opts, self.elf_path)
                    self.mcu = temp_mcu.__enter__()
                    self.core = getattr(self.mcu, 'core', None)
                    self.session = getattr(self.mcu, 'session', None)
                except Exception as e:
                    print(f"[ERROR] No se pudo abrir sesión principal para RAM: {e}")
                    self.no_inyectadas += 1
                    return
            return self._inj_memoria(falla, 256, delay)

        else:
            print(f"[WARNING] Inyección realizada en {ubic} {falla.ubicacion}")
            self.no_inyectadas += 1

    # =============================================================
    # Implementación genérica para RAM/REGISTRO
    # =============================================================
    def _inj_memoria(self, falla, tamano_bytes, delay):
        if self.core is None:
            print("[ERROR] No hay sesión/core disponible para inyectar.")
            self.no_inyectadas += 1
            try:
                self.log_falla(falla, None, None, None, "NO_INYECTADA_SIN_SESION")
            except Exception:
                pass
            return

        print(f"[INFO] ==== Iniciando falla ID {falla.id_falla} ====")
        print(f"[INFO] Dirección de inyección: 0x{(falla.direccion_inyeccion or 0):08X}")
        print(f"[INFO] Breakpoint temporal: 0x{(falla.direccion_breakpoint or 0):08X}")
        print(f"[INFO] Tipo de falla: {falla.tipo}")
        print(f"[INFO] Ubicación: {falla.ubicacion}")

        # PARA RAM/REGISTRO podemos usar reset (si se desea)
        try:
            if falla.ubicacion and falla.ubicacion.lower() in ['ram', 'registro']:
                try:
                    self.core.reset_and_halt()
                    print("[INFO] MCU reseteado y detenido (RAM/registro)")
                except Exception as e:
                    print(f"[WARNING] No se pudo reset_and_halt (RAM/registro): {e}")
            else:
                # por defecto solo halt
                try:
                    self.core.halt()
                    print("[INFO] MCU detenido (halt)")
                except Exception:
                    pass
        except Exception:
            pass

        bp_addr = falla.direccion_breakpoint
        if bp_addr is None:
            print(f"[WARNING] Falla {falla.id_falla} sin direccion_breakpoint")
            self.no_inyectadas += 1
            try:
                self.log_falla(falla, None, None, None, "NO_INYECTADA_SIN_BP")
            except Exception:
                pass
            return

        # intentar quitar stop_address temporal si existe
        try:
            for bp in list(self.core.get_breakpoints()):
                addr = getattr(bp, 'address', None)
                if addr is None and isinstance(bp, dict):
                    addr = bp.get('address')
                if addr == self.stop_address:
                    try:
                        self.core.remove_breakpoint(addr)
                        print(f"[INFO] Stop_address temporalmente removido: 0x{addr:08X}")
                    except Exception:
                        print("[WARNING] No se pudo remover stop_address temporalmente")
        except Exception:
            pass

        try:
            self.core.set_breakpoint(bp_addr, self.core.BreakpointType.HW)
            print(f"[INFO] BP temporal puesto en 0x{bp_addr:08X}")
        except Exception as e:
            print(f"[WARNING] No se pudo establecer BP temporal: {e}")
            self.no_inyectadas += 1
            try:
                self.log_falla(falla, None, None, None, "NO_INYECTADA_BP_ERROR")
            except Exception:
                pass
            try:
                self.core.set_breakpoint(self.stop_address, self.core.BreakpointType.HW)
            except Exception:
                pass
            return

        try:
            self.core.resume()
            print("[INFO] MCU reanudado, esperando BP temporal…")
        except Exception as e:
            print(f"[WARNING] No se pudo resume(): {e}")

        # esperar BP temporal
        start = time.time()
        while True:
            if time.time() - start > 5.0:
                self.no_inyectadas += 1
                try:
                    self.core.remove_breakpoint(bp_addr)
                except Exception:
                    pass
                print(f"[WARNING] Timeout esperando BP inyección para falla {falla.id_falla}")
                try:
                    self.log_falla(falla, None, None, None, "NO_INYECTADA_TIMEOUT_BP")
                except Exception:
                    pass
                try:
                    self.core.set_breakpoint(self.stop_address, self.core.BreakpointType.HW)
                except Exception:
                    pass
                return

            if self.core.is_halted():
                try:
                    pc = self.core.read_core_register('pc')
                except Exception:
                    pc = None
                print(f"[INFO] MCU detenido en PC=0x{(pc or 0):08X}")

                if pc == bp_addr:
                    # realizar inyección igual que en la versión original
                    reg_pre = self.snapshot_registros()
                    mem_pre = self.snapshot_memoria_bloque(falla.direccion_inyeccion, tamano_bytes)
                    if len(mem_pre) == 0:
                        mem_pre = [0]

                    try:
                        valor_original = int(mem_pre[0])
                    except Exception:
                        valor_original = 0

                    snap_pre = self.construir_snapshot_dict(reg_pre, mem_pre)
                    self.guardar_snapshot('before', falla.id_falla, falla.id_falla, snap_pre)

                    valor_con_falla = falla.aplicar(self.core)

                    try:
                        valor_leido = self.core.read_memory(falla.direccion_inyeccion, 32)
                    except Exception:
                        valor_leido = None
                        self.no_lectura += 1

                    reg_post = self.snapshot_registros()
                    mem_post = self.snapshot_memoria_bloque(falla.direccion_inyeccion, tamano_bytes)
                    if len(mem_post) == 0:
                        mem_post = [0]
                    snap_post = self.construir_snapshot_dict(reg_post, mem_post)
                    self.guardar_snapshot('after', falla.id_falla, falla.id_falla, snap_post)

                    estado = 'OK'
                    if valor_con_falla is None:
                        estado = 'ERROR_APLICANDO'
                    elif valor_leido is None:
                        estado = 'NO_LEIDO'
                    else:
                        try:
                            if int(valor_leido) != int(valor_con_falla):
                                estado = 'NO_ESCRITA'
                                self.no_inyectadas_valor_no_escrito += 1
                        except Exception:
                            estado = 'NO_LEIDO'

                    try:
                        self.log_falla(falla, valor_original, valor_con_falla, valor_leido, estado)
                    except Exception as e:
                        print(f"[WARNING] Error al loggear falla: {e}")

                    try:
                        self.core.remove_breakpoint(bp_addr)
                    except Exception:
                        pass

                    try:
                        self.core.set_breakpoint(self.stop_address, self.core.BreakpointType.HW)
                    except Exception:
                        pass

                    try:
                        self.core.resume()
                    except Exception:
                        pass

                    break

            time.sleep(delay)

    def _inj_memoria_flash(self, falla, tamano_bytes, delay):
        # Se espera que self.core apunte al core del MCU_RAM activo (sesión temporal abierta)
        if self.core is None:
            print("[ERROR] No hay sesión/core disponible para inyectar FLASH.")
            self.no_inyectadas += 1
            try:
                self.log_falla(falla, None, None, None, "NO_INYECTADA_SIN_SESION")
            except Exception:
                pass
            return

        print(f"[INFO] ==== Iniciando falla FLASH ID {falla.id_falla} ====")
        print(f"[INFO] Dirección de inyección: 0x{(falla.direccion_inyeccion or 0):08X}")
        print(f"[INFO] Breakpoint temporal: 0x{(falla.direccion_breakpoint or 0):08X}")
        print(f"[INFO] Tipo de falla: {falla.tipo}")
        print(f"[INFO] Ubicación: {falla.ubicacion}")

        # IMPORTANTE: NO reset_and_halt() aquí ni en el flujo FLASH, solo halt()
        try:
            try:
                self.core.halt()
                print("[INFO] MCU detenido (HALT) para conservar ELF en RAM")
            except Exception:
                pass
        except Exception as e:
            print(f"[WARNING] No se pudo detener MCU antes de inyectar FLASH: {e}")

        bp_addr = falla.direccion_breakpoint
        if bp_addr is None:
            print(f"[WARNING] Falla {falla.id_falla} sin direccion_breakpoint")
            self.no_inyectadas += 1
            try:
                self.log_falla(falla, None, None, None, "NO_INYECTADA_SIN_BP")
            except Exception:
                pass
            return

        # quitar stop_address temporal si existe
        try:
            for bp in list(self.core.get_breakpoints()):
                addr = getattr(bp, 'address', None)
                if addr is None and isinstance(bp, dict):
                    addr = bp.get('address')
                if addr == self.stop_address:
                    try:
                        self.core.remove_breakpoint(addr)
                        print(f"[INFO] Stop_address temporalmente removido: 0x{addr:08X}")
                    except Exception:
                        print("[WARNING] No se pudo remover stop_address temporalmente")
        except Exception:
            pass

        try:
            self.core.set_breakpoint(bp_addr, self.core.BreakpointType.HW)
            print(f"[INFO] BP temporal puesto en 0x{bp_addr:08X}")
        except Exception as e:
            print(f"[WARNING] No se pudo establecer BP temporal: {e}")
            self.no_inyectadas += 1
            try:
                self.log_falla(falla, None, None, None, "NO_INYECTADA_BP_ERROR")
            except Exception:
                pass
            return

        try:
            self.core.resume()
            print("[INFO] MCU reanudado, esperando BP temporal…")
        except Exception as e:
            print(f"[WARNING] No se pudo resume(): {e}")

        # esperar BP temporal
        start = time.time()
        while True:
            if time.time() - start > 5.0:
                self.no_inyectadas += 1
                try:
                    self.core.remove_breakpoint(bp_addr)
                except Exception:
                    pass
                print(f"[WARNING] Timeout esperando BP inyección para falla {falla.id_falla}")
                try:
                    self.log_falla(falla, None, None, None, "NO_INYECTADA_TIMEOUT_BP")
                except Exception:
                    pass
                try:
                    self.core.set_breakpoint(self.stop_address, self.core.BreakpointType.HW)
                except Exception:
                    pass
                return

            if self.core.is_halted():
                try:
                    pc = self.core.read_core_register('pc')
                except Exception:
                    pc = None
                print(f"[INFO] MCU detenido en PC=0x{(pc or 0):08X}")

                if pc == bp_addr:
                    # Snapshot BEFORE
                    reg_pre = self.snapshot_registros()
                    mem_pre = self.snapshot_memoria_bloque(falla.direccion_inyeccion, tamano_bytes)
                    if len(mem_pre) == 0:
                        mem_pre = [0]

                    try:
                        valor_original = int(mem_pre[0])
                    except Exception:
                        valor_original = 0

                    snap_pre = self.construir_snapshot_dict(reg_pre, mem_pre)
                    self.guardar_snapshot('before', falla.id_falla, falla.id_falla, snap_pre)

                    # Inyectar
                    valor_con_falla = falla.aplicar(self.core)

                    try:
                        valor_leido = self.core.read_memory(falla.direccion_inyeccion, 32)
                    except Exception:
                        valor_leido = None
                        self.no_lectura += 1

                    reg_post = self.snapshot_registros()
                    mem_post = self.snapshot_memoria_bloque(falla.direccion_inyeccion, tamano_bytes)
                    if len(mem_post) == 0:
                        mem_post = [0]
                    snap_post = self.construir_snapshot_dict(reg_post, mem_post)
                    self.guardar_snapshot('after', falla.id_falla, falla.id_falla, snap_post)

                    estado = 'OK'
                    if valor_con_falla is None:
                        estado = 'ERROR_APLICANDO'
                    elif valor_leido is None:
                        estado = 'NO_LEIDO'
                    else:
                        try:
                            if int(valor_leido) != int(valor_con_falla):
                                estado = 'NO_ESCRITA'
                                self.no_inyectadas_valor_no_escrito += 1
                        except Exception:
                            estado = 'NO_LEIDO'

                    try:
                        self.log_falla(falla, valor_original, valor_con_falla, valor_leido, estado)
                    except Exception as e:
                        print(f"[WARNING] Error al loggear falla: {e}")

                    try:
                        self.core.remove_breakpoint(bp_addr)
                    except Exception:
                        pass

                    try:
                        self.core.set_breakpoint(self.stop_address, self.core.BreakpointType.HW)
                    except Exception:
                        pass

                    try:
                        self.core.resume()
                    except Exception:
                        pass

                    print(f"[✅] Falla FLASH {falla.id_falla} COMPLETADA")
                    return

            time.sleep(delay)

    def ejecutar(self):
        print("[INFO] ================= INICIANDO CAMPAÑA =================")
        self.tiempo_total_inicio = time.time()

        total_fallas = len(self.lista_fallas)

        for falla in self.lista_fallas:
            try:
                self.inject(falla)
            except Exception as e:
                print(f"[ERROR] Error inyectando falla {falla.id_falla}: {e}")
                # continuar con la siguiente falla

        tiempo_total = time.time() - self.tiempo_total_inicio

        fallas_no_iny = self.no_inyectadas
        fallas_no_escritas = self.no_inyectadas_valor_no_escrito
        errores_lectura = self.no_lectura

        fallas_correctas = total_fallas - (fallas_no_iny + fallas_no_escritas)

        if total_fallas > 0:
            p_correctas = (fallas_correctas / total_fallas) * 100
            p_no_iny = (fallas_no_iny / total_fallas) * 100
            p_no_escritas = (fallas_no_escritas / total_fallas) * 100
            p_lectura = (errores_lectura / total_fallas) * 100
        else:
            p_correctas = p_no_iny = p_no_escritas = p_lectura = 0.0

        print("========== RESUMEN DE CAMPAÑA ==========")
        print(f"Fallas totales: {total_fallas}")
        print(f"Fallas inyectadas correctamente: {fallas_correctas} ({p_correctas:.2f}%)")
        print(f"Fallas NO inyectadas: {fallas_no_iny} ({p_no_iny:.2f}%)")
        print(f"Fallas con valor NO escrito: {fallas_no_escritas} ({p_no_escritas:.2f}%)")
        print(f"Errores de lectura: {errores_lectura} ({p_lectura:.2f}%)")
        print(f"Tiempo total de campaña: {tiempo_total:.2f} segundos")
        print("========================================")

        resumen_path = os.path.join(self.campaign_dir, "resumen.txt")
        try:
            with open(resumen_path, "w") as f:
                f.write("========== RESUMEN DE CAMPAÑA ==========")
                f.write(f"Fallas totales: {total_fallas}")
                f.write(f"Fallas inyectadas correctamente: {fallas_correctas} ({p_correctas:.2f}%)")
                f.write(f"Fallas NO inyectadas: {fallas_no_iny} ({p_no_iny:.2f}%)")
                f.write(f"Fallas con valor NO escrito: {fallas_no_escritas} ({p_no_escritas:.2f}%)")
                f.write(f"Errores de lectura: {errores_lectura} ({p_lectura:.2f}%)")
                f.write(f"Tiempo total de campaña: {tiempo_total:.2f} segundos")
                f.write("========================================")
            print(f"[INFO] Resumen guardado en: {resumen_path}")
        except Exception as e:
            print(f"[ERROR] No se pudo guardar el resumen: {e}")


def main():
    opts = {
            "frequency": 1800000,
            "connect_mode": "under_reset",
            "halt_on_connect": True,
            "resume_on_disconnect": False,
            "reset_type": "hw",
            "vector_catch": "reset,hardfault,memmanage,busfault,usagefault",
            "enable_semihosting": False
    }
    elf_path = r"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file = os.path.join(script_dir, "LISTA_INYECCION.csv")

    try:
        # Abrir sesión principal con MCU(...) como hiciste originalmente
        with MCU(opts, elf_path) as mcu:
            injector = FaultInjector(mcu, csv_file, elf_path, opts)

            print("[INFO] Inyección de fallas iniciada")
            injector.ejecutar()
            print("[INFO] Inyección de fallas completada")

    except Exception as e:
        print(f"[ERROR] Falló la inicialización o ejecución: {e}")


if __name__ == '__main__':
    main()
