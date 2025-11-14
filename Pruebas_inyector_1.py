#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M_inyector_flash_gui_ready_nasa.py

Versión del injector preparada para integrar con una GUI (PySide) y
con reporte estilo "NASA-STYLE" (clasificación de OK / HANG / NO_ESCRITA / NO_LEIDO / ERRORES).
- No contiene rutas hardcodeadas de ELF (se pasan por parámetros o por la GUI).
- Métodos públicos: set_elf_paths, cargar_elves_desde_gui
- Usa MCU_RAM para programar/inyectar en FLASH y MCU para la sesión principal (RAM/registro).
"""

import csv
import os
import time
from datetime import datetime
from M_deteccion_stop import detectar_while_infinito

# wrappers de gestión de sesión (asegúrate de que existen y funcionan)
from M_gestion_MCU_ram import MCU_RAM
from M_gestion_mcu import MCU

# ---------- utilidades ----------
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
    try:
        if val is None:
            return "0x00000000"
        ival = int(val)
        return f"0x{(ival & 0xFFFFFFFF):08X}"
    except Exception:
        return "0x00000000"


# ---------- clases ----------
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
    def __init__(self, mcu=None, csv_file=None, elf_main_path=None, elf_ram_path=None, main_opts=None):
        """
        mcu: (opcional) sesión principal ya abierta (instancia devuelta por MCU(opts, elf))
        csv_file: ruta al CSV con lista de fallas
        elf_main_path: ruta al ELF principal (puede ser None; la GUI puede establecerlo luego)
        elf_ram_path: ruta al ELF alterno para programar en RAM (usada en inyecciones FLASH)
        main_opts: opciones pyOCD principales (dict)
        """
        self.mcu = mcu
        self.core = getattr(mcu, 'core', None) if mcu is not None else None
        self.session = getattr(mcu, 'session', None) if mcu is not None else None

        self.csv_file = csv_file
        self.elf_path = elf_main_path
        self.elf_ram_path = elf_ram_path
        self.opts = main_opts or {}

        # contadores y listas
        self.lista_fallas = []
        self.no_inyectadas = 0
        self.no_inyectadas_valor_no_escrito = 0
        self.no_lectura = 0

        # NASA-style counters
        self.hangs = 0
        self.ok = 0
        self.errores_bp = 0
        self.no_escritas = 0
        self.no_leido = 0

        # Si se dio un CSV, lo cargamos; si no, GUI puede llamar cargar_csv() luego.
        if self.csv_file:
            self.cargar_csv()

        # intentar detectar stop_address solo si existe elf principal
        if self.elf_path:
            try:
                resultado = detectar_while_infinito(self.elf_path)
                addr_salto, _ = resultado
                self.stop_address = addr_salto
                print(f"[INFO] Stop address detectada: 0x{self.stop_address:08X}")
            except Exception as e:
                self.stop_address = None
                print(f"[WARNING] No se pudo detectar stop_address (elf_main missing o error): {e}")
        else:
            self.stop_address = None

        # inicializar archivos si CSV ya cargado
        if self.lista_fallas:
            self.inicializar_archivos()
        else:
            # Si la GUI carga el CSV después, inicializará archivos entonces.
            self.campaign_dir = None

    # ---------- API para la GUI ----------
    def set_elf_paths(self, elf_main=None, elf_ram=None):
        """Establece rutas ELF desde la GUI o desde otro script."""
        if elf_main:
            self.elf_path = elf_main
            try:
                resultado = detectar_while_infinito(self.elf_path)
                addr_salto, _ = resultado
                self.stop_address = addr_salto
                print(f"[INFO] Stop address detectada (elf_main): 0x{self.stop_address:08X}")
            except Exception as e:
                print(f"[WARNING] No se pudo detectar stop_address en elf_main: {e}")

        if elf_ram:
            self.elf_ram_path = elf_ram
            print(f"[INFO] elf_ram_path establecido: {self.elf_ram_path}")

    def cargar_elves_desde_gui(self, elf_main, elf_ram):
        """Conveniencia para la GUI: establece ambos ELF de una llamada."""
        self.set_elf_paths(elf_main=elf_main, elf_ram=elf_ram)

    def cargar_csv(self, csv_file=None):
        """Carga lista de fallas. Puede pasarse la ruta o usar la ya guardada."""
        path = csv_file or self.csv_file
        if not path:
            raise ValueError("No hay ruta CSV para cargar.")
        self.csv_file = path
        self.lista_fallas = []
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
        # inicializar archivos
        self.inicializar_archivos()

    # ---------- archivos y snapshots ----------
    def inicializar_archivos(self):
        campaign_name = datetime.now().strftime("campaign_%Y%m%d_%H%M%S")
        base_dir = os.path.dirname(self.csv_file) if self.csv_file else os.getcwd()
        self.campaign_dir = os.path.join(base_dir, campaign_name)
        os.makedirs(self.campaign_dir, exist_ok=True)
        print(f"[INFO] Carpeta de campaña creada: {self.campaign_dir}")

        self.snapshot_before_csv = os.path.join(self.campaign_dir, 'snapshots_before.csv')
        self.snapshot_after_csv = os.path.join(self.campaign_dir, 'snapshots_after.csv')
        self.snapshot_after_stable_csv = os.path.join(self.campaign_dir, 'snapshots_after_stable.csv')

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

    # ---------- snapshots / lectura ----------
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

    # ---------- flujo de inyección ----------
    def inject(self, falla, max_retries=10, delay=0.05):
        ubic = (falla.ubicacion or '').lower()

        # limpiar BP temporales (salvo stop)
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

        if ubic in ['flash']:
            # Para FLASH: necesitamos elf_ram_path (provisto por GUI)
            if not getattr(self, 'elf_ram_path', None):
                print("[ERROR] elf_ram_path no establecido. Pasa la ruta desde la GUI con set_elf_paths().")
                self.no_inyectadas += 1
                self.log_falla(falla, None, None, None, "NO_INYECTADA_NO_ELF_RAM")
                self.errores_bp += 1
                return

            # cerrar sesión principal para liberar probe si estaba abierta
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

            # abrir sesión temporal MCU_RAM y programar/inyectar dentro del context manager
            try:
                with MCU_RAM(self.opts, self.elf_ram_path) as mcu_ram:
                    print("[INFO] Sesión temporal abierta para programar e inyectar (FLASH).")
                    # programa e intenta arrancar desde .isr_vector (usa boot_from_elf_vector)
                    if falla.direccion_breakpoint:
                        try:
                            mcu_ram.core.set_breakpoint(falla.direccion_breakpoint, mcu_ram.core.BreakpointType.HW)
                            print(f"[INFO] BP colocado antes del resume: 0x{falla.direccion_breakpoint:08X}")
                        except Exception as e:
                            print(f"[WARNING] No se pudo establecer BP antes del resume: {e}")

                    try:
                        mcu_ram.core.reset_and_halt()
                        mcu_ram.core.resume()
                        time.sleep(1)
                        mcu_ram.core.halt()
                        ret = mcu_ram.boot_from_elf_vector(force_program=True, halt_before_program=True)
                        mcu_ram.core.resume()
                        time.sleep(1)
                        # boot_from_elf_vector puede devolver (sp,pc) o no; intentar capturar ambos
                        sp_val = None
                        pc_val = None
                        if isinstance(ret, tuple) and len(ret) >= 2:
                            sp_val, pc_val = ret[0], ret[1]
                        else:
                            sp_val = getattr(mcu_ram, 'sp_inicial', None)
                            pc_val = getattr(mcu_ram, 'pc_reset', None)
                        print(f"[DEBUG] ELF RAM: sp={sp_val}, pc={pc_val}")
                    except Exception as e:
                        print(f"[WARNING] boot_from_elf_vector (RAM ELF) dió warning/error: {e}")

                    # asignar core temporal y ejecutar inyección FLASH usando ese core
                    self.mcu = mcu_ram
                    self.core = getattr(mcu_ram, 'core', None)
                    self.session = getattr(mcu_ram, 'session', None)

                    # ejecutar flujo de inyección FLASH (usa self.core del mcu_ram)
                    return self._inj_memoria_flash(falla, 256, delay)

            except Exception as e:
                print(f"[ERROR] Falló reprogramación/inyección FLASH: {e}")
                self.no_inyectadas += 1
                try:
                    self.log_falla(falla, None, None, None, "NO_INYECTADA_REPROG_ERROR")
                except Exception:
                    pass
                self.errores_bp += 1
                return

        elif ubic in ['flash']:
            # Asegurar que se tenga ruta de ELF para RAM
            if not getattr(self, 'elf_ram_path', None):
                print("[ERROR] elf_ram_path no establecido. Pasa la ruta desde la GUI con set_elf_paths().")
                self.no_inyectadas += 1
                self.errores_bp += 1
                return

            # Abrir sesión MCU_RAM solo una vez
            if not getattr(self, 'mcu_ram', None):
                try:
                    print("[INFO] Abriendo sesión MCU_RAM persistente para inyecciones FLASH...")
                    self.mcu_ram = MCU_RAM(self.opts, self.elf_ram_path)
                    self.mcu_ram.__enter__()  # abrir manualmente
                    print("[INFO] Sesión MCU_RAM abierta correctamente.")
                except Exception as e:
                    print(f"[ERROR] No se pudo abrir sesión MCU_RAM: {e}")
                    self.no_inyectadas += 1
                    self.errores_bp += 1
                    return

            mcu_ram = self.mcu_ram
            core_ram = getattr(mcu_ram, 'core', None)

            try:
                # Reprogramar ELF en RAM antes de cada falla (entorno limpio)
                print("[INFO] Reprogramando ELF en RAM para nueva falla...")
                ret = mcu_ram.boot_from_elf_vector(force_program=True, halt_before_program=True)
                sp_val, pc_val = None, None
                if isinstance(ret, tuple) and len(ret) >= 2:
                    sp_val, pc_val = ret
                else:
                    sp_val = getattr(mcu_ram, 'sp_inicial', None)
                    pc_val = getattr(mcu_ram, 'pc_reset', None)
                print(f"[DEBUG] ELF RAM: SP={sp_val}, PC={pc_val}")

                # Ejecutar la inyección usando el core persistente
                return self._inj_memoria_flash(falla, 256, delay, core=core_ram)

            except Exception as e:
                print(f"[ERROR] Falló reprogramación/inyección FLASH: {e}")
                self.no_inyectadas += 1
                self.errores_bp += 1
                try:
                    self.log_falla(falla, None, None, None, "NO_INYECTADA_REPROG_ERROR")
                except Exception:
                    pass
                return


        elif ubic == 'registro':
            # asegurar sesión principal abierta
            if self.core is None:
                try:
                    temp_mcu = MCU(self.opts, self.elf_path)
                    self.mcu = temp_mcu.__enter__()
                    self.core = getattr(self.mcu, 'core', None)
                    self.session = getattr(self.mcu, 'session', None)
                except Exception as e:
                    print(f"[ERROR] No se pudo abrir sesión principal para registro: {e}")
                    self.no_inyectadas += 1
                    self.errores_bp += 1
                    return
            return self._inj_memoria(falla, 4, delay)

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
                    self.errores_bp += 1
                    return
            return self._inj_memoria(falla, 256, delay)

        else:
            print(f"[WARNING] Inyección realizada en {ubic} {falla.ubicacion}")
            self.no_inyectadas += 1
            self.errores_bp += 1

    # ---------- implementación genérica para RAM/REGISTRO ----------
    def _inj_memoria(self, falla, tamano_bytes, delay):
        if self.core is None:
            print("[ERROR] No hay sesión/core disponible para inyectar.")
            self.no_inyectadas += 1
            try:
                self.log_falla(falla, None, None, None, "NO_INYECTADA_SIN_SESION")
            except Exception:
                pass
            self.errores_bp += 1
            return

        print(f"[INFO] ==== Iniciando falla ID {falla.id_falla} ====")
        print(f"[INFO] Dirección de inyección: 0x{(falla.direccion_inyeccion or 0):08X}")
        print(f"[INFO] Breakpoint temporal: 0x{(falla.direccion_breakpoint or 0):08X}")
        print(f"[INFO] Tipo de falla: {falla.tipo}")
        print(f"[INFO] Ubicación: {falla.ubicacion}")

        # para RAM/registro se permite reset_and_halt (si procede)
        try:
            if falla.ubicacion and falla.ubicacion.lower() in ['ram', 'registro']:
                try:
                    self.core.reset_and_halt()
                    print("[INFO] MCU reseteado y detenido (RAM/registro)")
                except Exception as e:
                    print(f"[WARNING] No se pudo reset_and_halt (RAM/registro): {e}")
            else:
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
            self.errores_bp += 1
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
            self.errores_bp += 1
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
                # leer PC actual
                try:
                    pc = self.core.read_core_register('pc')
                except Exception:
                    pc = None

                # contar HANG solo si no llegó a stop_address
                if pc != self.stop_address:
                    print(f"[⚠️] TIMEOUT esperando BP → HANG en falla {falla.id_falla}")
                    try:
                        self.log_falla(falla, None, None, None, "HANG_NO_LLEGO_A_STOP_ADDRESS")
                    except Exception:
                        pass
                    self.hangs += 1

                    # reiniciar MCU tras HANG
                    try:
                        self.core.reset_and_halt()
                        print("[INFO] MCU reiniciada tras HANG")
                    except Exception as e:
                        print(f"[WARNING] No se pudo reiniciar MCU tras HANG: {e}")

                return

            if self.core.is_halted():
                try:
                    pc = self.core.read_core_register('pc')
                except Exception:
                    pc = None
                print(f"[INFO] MCU detenido en PC=0x{(pc or 0):08X}")

                # --- Caso 1: llegó al stop_address antes del breakpoint ---
                if pc == self.stop_address:
                    print(f"[⚠️] MCU llegó al stop_address antes del breakpoint. Falla NO aplicada.")
                    try:
                        self.log_falla(falla, None, None, None, "NO_APLICADA_STOP_PREVIO")
                    except Exception:
                        pass
                    self.no_inyectadas += 1
                    self.errores_bp += 1
                    try:
                        self.core.reset_and_halt()
                        print("[INFO] MCU reiniciada tras NO_APLICADA.")
                    except Exception as e:
                        print(f"[WARNING] No se pudo reiniciar MCU tras NO_APLICADA: {e}")
                    return

                # --- Caso 2: llegó al breakpoint temporal (inyectar falla) ---
                if pc == bp_addr:
                    # snapshot before
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

                    # aplicar falla
                    print("[INFO] Aplicando falla...")
                    valor_con_falla = falla.aplicar(self.core)

                    try:
                        valor_leido = self.core.read_memory(falla.direccion_inyeccion, 32)
                    except Exception:
                        valor_leido = None
                        self.no_lectura += 1

                    # snapshot after
                    reg_post = self.snapshot_registros()
                    mem_post = self.snapshot_memoria_bloque(falla.direccion_inyeccion, tamano_bytes)
                    if len(mem_post) == 0:
                        mem_post = [0]
                    snap_post = self.construir_snapshot_dict(reg_post, mem_post)
                    self.guardar_snapshot('after', falla.id_falla, falla.id_falla, snap_post)

                    # Clasificación NASA-STYLE
                    if valor_con_falla is None:
                        estado = "NO_INYECTADA_APLICANDO"
                        self.errores_bp += 1
                    elif valor_leido is None:
                        estado = "NO_LEIDO"
                        self.no_leido += 1
                    else:
                        try:
                            if int(valor_leido) != int(valor_con_falla):
                                estado = "NO_ESCRITA"
                                self.no_escritas += 1
                            else:
                                estado = "OK"
                                self.ok += 1
                        except Exception:
                            estado = "NO_LEIDO"
                            self.no_leido += 1

                    try:
                        self.log_falla(falla, valor_original, valor_con_falla, valor_leido, estado)
                    except Exception as e:
                        print(f"[WARNING] Error al loggear falla: {e}")

                    try:
                        self.core.remove_breakpoint(bp_addr)
                    except Exception:
                        pass
                    try:
                        if self.stop_address is not None:
                            self.core.set_breakpoint(self.stop_address, self.core.BreakpointType.HW)
                    except Exception:
                        pass

                    print("[INFO] Reanudando ejecución para esperar stop_address…")
                    try:
                        self.core.resume()
                    except Exception:
                        pass

                    # --- Esperar a que llegue al stop_address tras la falla ---
                    start_stop = time.time()
                    while True:
                        if time.time() - start_stop > 5.0:
                            print(f"[⚠️] MCU no alcanzó stop_address tras aplicar falla. Clasificado como HANG.")
                            try:
                                self.log_falla(falla, valor_original, valor_con_falla, valor_leido, "HANG_POST_FALLA")
                            except Exception:
                                pass
                            self.hangs += 1
                            try:
                                self.core.reset_and_halt()
                                print("[INFO] MCU reiniciada tras HANG_POST_FALLA.")
                            except Exception as e:
                                print(f"[WARNING] No se pudo reiniciar MCU tras HANG_POST_FALLA: {e}")
                            return

                        if self.core.is_halted():
                            try:
                                pc_final = self.core.read_core_register('pc')
                            except Exception:
                                pc_final = None
                            if pc_final == self.stop_address:
                                print(f"[✅] Falla ID {falla.id_falla} COMPLETADA y llegó al stop_address.")
                                return
                        time.sleep(0.05)


            time.sleep(delay)

    # ---------- implementación para FLASH (usa sesión 'mcu_ram' activa) ----------
    def _inj_memoria_flash(self, falla, tamano_bytes, delay):
        if self.core is None:
            print("[ERROR] No hay sesión/core disponible para inyectar FLASH.")
            self.no_inyectadas += 1
            try:
                self.log_falla(falla, None, None, None, "NO_INYECTADA_SIN_SESION")
            except Exception:
                pass
            self.errores_bp += 1
            return

        print(f"[INFO] ==== Iniciando falla FLASH ID {falla.id_falla} ====")
        print(f"[INFO] Dirección de inyección: 0x{(falla.direccion_inyeccion or 0):08X}")
        print(f"[INFO] Breakpoint temporal: 0x{(falla.direccion_breakpoint or 0):08X}")
        print(f"[INFO] Tipo de falla: {falla.tipo}")
        print(f"[INFO] Ubicación: {falla.ubicacion}")

        # Importante: NO reset_and_halt() si quieres conservar ELF en RAM
        try:
            self.core.halt()
            print("[INFO] MCU detenido (HALT) para conservar ELF en RAM")
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
            self.errores_bp += 1
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

        #try:
        #    self.core.set_breakpoint(bp_addr, self.core.BreakpointType.HW)
        #    print(f"[INFO] BP temporal puesto en 0x{bp_addr:08X}")
        #except Exception as e:
        #    print(f"[WARNING] No se pudo establecer BP temporal: {e}")
        #    self.no_inyectadas += 1
        #    try:
        #        self.log_falla(falla, None, None, None, "NO_INYECTADA_BP_ERROR")
        #    except Exception:
        #        pass
        #    self.errores_bp += 1
        #    return

        try:
            self.core.resume()
            print("[INFO] MCU reanudado, esperando BP temporal…")
        except Exception as e:
            print(f"[WARNING] No se pudo resume(): {e}")

        start = time.time()
        while True:
            if time.time() - start > 5.0:
                # leer PC actual
                try:
                    pc = self.core.read_core_register('pc')
                except Exception:
                    pc = None

                # contar HANG solo si no llegó a stop_address
                if pc != self.stop_address:
                    print(f"[⚠️] TIMEOUT esperando BP → HANG en falla {falla.id_falla}")
                    try:
                        self.log_falla(falla, None, None, None, "HANG_NO_LLEGO_A_STOP_ADDRESS")
                    except Exception:
                        pass
                    self.hangs += 1

                    # reiniciar MCU tras HANG
                    try:
                        self.core.reset_and_halt()
                        print("[INFO] MCU reiniciada tras HANG")
                    except Exception as e:
                        print(f"[WARNING] No se pudo reiniciar MCU tras HANG: {e}")

                return

            if self.core.is_halted():
                try:
                    pc = self.core.read_core_register('pc')
                except Exception:
                    pc = None
                print(f"[INFO] MCU detenido en PC=0x{(pc or 0):08X}")

                # --- Caso 1: llegó al stop_address antes del breakpoint ---
                if pc == self.stop_address:
                    print(f"[⚠️] MCU llegó al stop_address antes del breakpoint. Falla NO aplicada.")
                    try:
                        self.log_falla(falla, None, None, None, "NO_APLICADA_STOP_PREVIO")
                    except Exception:
                        pass
                    self.no_inyectadas += 1
                    self.errores_bp += 1
                    try:
                        self.core.reset_and_halt()
                        print("[INFO] MCU reiniciada tras NO_APLICADA.")
                    except Exception as e:
                        print(f"[WARNING] No se pudo reiniciar MCU tras NO_APLICADA: {e}")
                    return

                # --- Caso 2: llegó al breakpoint temporal (inyectar falla) ---
                if pc == bp_addr:
                    # snapshot before
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

                    # aplicar falla
                    print("[INFO] Aplicando falla...")
                    valor_con_falla = falla.aplicar(self.core)

                    try:
                        valor_leido = self.core.read_memory(falla.direccion_inyeccion, 32)
                    except Exception:
                        valor_leido = None
                        self.no_lectura += 1

                    # snapshot after
                    reg_post = self.snapshot_registros()
                    mem_post = self.snapshot_memoria_bloque(falla.direccion_inyeccion, tamano_bytes)
                    if len(mem_post) == 0:
                        mem_post = [0]
                    snap_post = self.construir_snapshot_dict(reg_post, mem_post)
                    self.guardar_snapshot('after', falla.id_falla, falla.id_falla, snap_post)

                    # Clasificación NASA-STYLE
                    if valor_con_falla is None:
                        estado = "NO_INYECTADA_APLICANDO"
                        self.errores_bp += 1
                    elif valor_leido is None:
                        estado = "NO_LEIDO"
                        self.no_leido += 1
                    else:
                        try:
                            if int(valor_leido) != int(valor_con_falla):
                                estado = "NO_ESCRITA"
                                self.no_escritas += 1
                            else:
                                estado = "OK"
                                self.ok += 1
                        except Exception:
                            estado = "NO_LEIDO"
                            self.no_leido += 1

                    try:
                        self.log_falla(falla, valor_original, valor_con_falla, valor_leido, estado)
                    except Exception as e:
                        print(f"[WARNING] Error al loggear falla: {e}")

                    try:
                        self.core.remove_breakpoint(bp_addr)
                    except Exception:
                        pass
                    try:
                        if self.stop_address is not None:
                            self.core.set_breakpoint(self.stop_address, self.core.BreakpointType.HW)
                    except Exception:
                        pass

                    print(f"[INFO] Reanudando ejecución para esperar stop_address…")
                    try:
                        self.core.resume()
                    except Exception:
                        pass

                    # --- Esperar a que llegue al stop_address tras la falla ---
                    start_stop = time.time()
                    while True:
                        if time.time() - start_stop > 5.0:
                            print(f"[⚠️] MCU no alcanzó stop_address tras aplicar falla. Clasificado como HANG.")
                            try:
                                self.log_falla(falla, valor_original, valor_con_falla, valor_leido, "HANG_POST_FALLA")
                            except Exception:
                                pass
                            self.hangs += 1
                            try:
                                self.core.reset_and_halt()
                                print("[INFO] MCU reiniciada tras HANG_POST_FALLA.")
                            except Exception as e:
                                print(f"[WARNING] No se pudo reiniciar MCU tras HANG_POST_FALLA: {e}")
                            return

                        if self.core.is_halted():
                            try:
                                pc_final = self.core.read_core_register('pc')
                            except Exception:
                                pc_final = None
                            if pc_final == self.stop_address:
                                print(f"[✅] Falla FLASH {falla.id_falla} COMPLETADA y llegó al stop_address.")
                                return
                        time.sleep(0.05)

            #self.core.reset()
            time.sleep(delay)

    # ---------- ejecutar campaña ----------
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

        # NASA-style percentages
        total = total_fallas = total_fallas
        p_ok = (self.ok / total) * 100 if total else 0
        p_hang = (self.hangs / total) * 100 if total else 0
        p_no_escrita = (self.no_escritas / total) * 100 if total else 0
        p_no_leido = (self.no_leido / total) * 100 if total else 0
        p_error_bp = (self.errores_bp / total) * 100 if total else 0

        print("\n\n========== NASA-STYLE FAULT INJECTION REPORT ==========")
        print(f"Total fallas analizadas:             {total}")
        print("---------------------------------------------")
        print(f"[OK] Fallas toleradas:               {self.ok}  ({p_ok:.2f}%)")
        print(f"[HANG] No llegó a BP (timeout):      {self.hangs}  ({p_hang:.2f}%)")
        print(f"[NO_ESCRITA] Fallas no aplicadas:    {self.no_escritas}  ({p_no_escrita:.2f}%)")
        print(f"[NO_LEIDO] Error al leer memoria:    {self.no_leido}  ({p_no_leido:.2f}%)")
        print(f"[APLICACIÓN ERROR] No se pudo inyectar: {self.errores_bp}  ({p_error_bp:.2f}%)")
        print(f"HANGs: {self.hangs}")

        print("--------------------------------------------------------")
        print(f"Tiempo total de campaña: {tiempo_total:.2f} segundos")
        print("=========================================================\n")

        resumen_path = os.path.join(self.campaign_dir or os.getcwd(), "resumen.txt")
        try:
            with open(resumen_path, "w") as f:
                f.write("========== NASA-STYLE FAULT INJECTION REPORT ==========\n")
                f.write(f"Total fallas analizadas: {total}\n\n")
                f.write(f"[OK] Fallas toleradas: {self.ok} ({p_ok:.2f}%)\n")
                f.write(f"[HANG] No llegó a BP: {self.hangs} ({p_hang:.2f}%)\n")
                f.write(f"[NO_ESCRITA] No escrita: {self.no_escritas} ({p_no_escrita:.2f}%)\n")
                f.write(f"[NO_LEIDO] Error de lectura: {self.no_leido} ({p_no_leido:.2f}%)\n")
                f.write(f"[ERROR_APLICACIÓN] No inyectadas: {self.errores_bp} ({p_error_bp:.2f}%)\n\n")
                f.write(f"Tiempo total de campaña: {tiempo_total:.2f} segundos\n")
                f.write("========================================================\n")
            print(f"[INFO] Resumen guardado en: {resumen_path}")
        except Exception as e:
            print(f"[ERROR] No se pudo guardar el resumen: {e}")


# ---------- ejemplo de uso desde GUI / script ----------
def main_example():
    opts = {
        "frequency": 1800000,
        "connect_mode": "under_reset",
        "halt_on_connect": True,
        "resume_on_disconnect": False,
        "reset_type": "hw",
        "vector_catch": "reset,hardfault,memmanage,busfault,usagefault",
        "enable_semihosting": False
    }

    # La GUI debe pasar estas rutas; aquí son ejemplos
    elf_main = r"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"
    elf_ram = r"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file = os.path.join(script_dir, "LISTA_INYECCION.csv")

    # Abrir sesión principal (opcional — útil para fallas en RAM/registro)
    try:
        with MCU(opts, elf_main) as mcu:
            injector = FaultInjector(mcu=mcu, csv_file=csv_file, elf_main_path=elf_main, elf_ram_path=elf_ram, main_opts=opts)
            # Alternativamente la GUI podría llamar:
            # injector.cargar_elves_desde_gui(elf_main, elf_ram)
            # injector.cargar_csv(csv_file)  # si no pasó csv al constructor

            print("[INFO] Inyección de fallas iniciada (desde ejemplo).")
            injector.ejecutar()
            print("[INFO] Inyección de fallas completada (ejemplo).")
    except Exception as e:
        print(f"[ERROR] Falló la inicialización o ejecución (ejemplo): {e}")


if __name__ == '__main__':
    main_example()
