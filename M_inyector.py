import csv
import os
import time
from datetime import datetime

from M_deteccion_stop import detectar_while_infinito


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
    def __init__(self, core, session, csv_file, elf_path):
        self.core = core
        self.session = session
        self.csv_file = csv_file
        self.elf_path = elf_path

        self.lista_fallas = []
        self.no_inyectadas = 0
        self.no_inyectadas_valor_no_escrito = 0
        self.no_lectura = 0

        # cargamos fallas primero (necesario para decidir headers dinámicos)
        self.cargar_csv()

        resultado = detectar_while_infinito(self.elf_path)
        addr_salto, _ = resultado
        self.stop_address = addr_salto
        print(f"[INFO] Stop address detectada: 0x{self.stop_address:08X}")

        try:
            self.core.set_breakpoint(self.stop_address, self.core.BreakpointType.HW)
        except Exception as e:
            print(f"[WARNING] No se pudo establecer bp stop: {e}")

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
        # crear carpeta de campaña
        campaign_name = datetime.now().strftime("campaign_%Y%m%d_%H%M%S")
        self.campaign_dir = os.path.join(os.path.dirname(self.csv_file), campaign_name)
        os.makedirs(self.campaign_dir, exist_ok=True)
        print(f"[INFO] Carpeta de campaña creada: {self.campaign_dir}")

        # paths
        self.snapshot_before_csv = os.path.join(self.campaign_dir, 'snapshots_before.csv')
        self.snapshot_after_csv = os.path.join(self.campaign_dir, 'snapshots_after.csv')
        self.snapshot_after_stable_csv = os.path.join(self.campaign_dir, 'snapshots_after_stable.csv')

        # decidir si hay alguna falla de RAM/FLASH
        hay_memoria = any((f.ubicacion or '').lower() in ['ram', 'flash'] for f in self.lista_fallas)

        # mem cols count: si hay memoria -> 256, else -> 1 (solo MEM_0)
        self.mem_cols_count = 256 if hay_memoria else 1

        # construir header dinámico
        mem_cols = [f"MEM_{i}" for i in range(self.mem_cols_count)]
        header = ['Test_ID', 'Fault_ID', 'PC', 'SP', 'LR'] + [f'R{i}' for i in range(13)] + mem_cols

        for path in [self.snapshot_before_csv, self.snapshot_after_csv, self.snapshot_after_stable_csv]:
            try:
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                print(f"[INFO] Creado archivo: {path} (MEM cols: {self.mem_cols_count})")
            except Exception as e:
                print(f"[WARNING] No se pudo crear {path}: {e}")

        # Archivo de log de fallas aplicadas (faults_log.csv) - MASCARA en hex
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
        # Convertir registros a hex (0xXXXXXXXX)
        snap['PC'] = _to_hex_safe(registros.get('pc', 0))
        snap['SP'] = _to_hex_safe(registros.get('sp', 0))
        snap['LR'] = _to_hex_safe(registros.get('lr', 0))

        for i in range(13):
            snap[f'R{i}'] = _to_hex_safe(registros.get(f'r{i}', 0))

        # MEM_0..MEM_{mem_cols_count-1} en hex; si memoria corta, rellenar con ceros
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

        # Añadir MEM cols según mem_cols_count
        for i in range(self.mem_cols_count):
            row.append(snap.get(f'MEM_{i}', _to_hex_safe(0)))

        with open(path, 'a', newline='') as f:
            csv.writer(f).writerow(row)

    def log_falla(self, falla, valor_original, valor_con_falla, valor_leido, estado):
        """
        Registra en faults_log.csv:
        Mascara guardada en hex (opcion A).
        Valores originales/filtrados guardados en hex mediante _to_hex_safe.
        """
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

        # Caso RAM/FLASH
        if ubic in ['ram']:
            return self._inj_memoria(falla, 256, delay)

        # Caso REGISTRO (1 palabra)
        elif ubic == 'registro':
            return self._inj_memoria(falla, 4, delay)

        else:
            print(f"[WARNING] Inyección realizada en {ubic} {falla.ubicacion}")
            self.no_inyectadas += 1


    # =============================================================
    # FUNCIÓN GENÉRICA PARA RAM Y REGISTRO
    # =============================================================
    def _inj_memoria(self, falla, tamano_bytes, delay):
        """
        Flujo genérico para inyectar en memoria o registros periféricos.
        tamano_bytes: 256 para RAM/FLASH, 4 para registro (1 palabra)
        """

        print(f"\n[INFO] ==== Iniciando falla ID {falla.id_falla} ====")
        print(f"[INFO] Dirección de inyección: 0x{(falla.direccion_inyeccion or 0):08X}")
        print(f"[INFO] Breakpoint temporal: 0x{(falla.direccion_breakpoint or 0):08X}")
        print(f"[INFO] Tipo de falla: {falla.tipo}")
        print(f"[INFO] Ubicación: {falla.ubicacion}")

        # Reset
        try:
            self.core.reset_and_halt()
            print("[INFO] MCU reseteado y detenido")
        except Exception as e:
            print(f"[WARNING] No se pudo reset_and_halt: {e}")

        # Breakpoint temporal
        bp_addr = falla.direccion_breakpoint
        if bp_addr is None:
            print(f"[WARNING] Falla {falla.id_falla} sin direccion_breakpoint")
            self.no_inyectadas += 1
            try:
                self.log_falla(falla, None, None, None, "NO_INYECTADA_SIN_BP")
            except Exception:
                pass
            return

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

        # Reanudar
        try:
            self.core.resume()
            print("[INFO] MCU reanudado, esperando BP temporal…")
        except Exception as e:
            print(f"[WARNING] No se pudo resume(): {e}")

        # Esperar BP temporal
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
                return

            if self.core.is_halted():
                try:
                    pc = self.core.read_core_register('pc')
                except Exception:
                    pc = None
                print(f"[INFO] MCU detenido en PC=0x{(pc or 0):08X}")

                if pc == bp_addr:
                    print(f"[INFO] BP temporal alcanzado para falla {falla.id_falla}")

                    # Snapshot BEFORE
                    reg_pre = self.snapshot_registros()
                    mem_pre = self.snapshot_memoria_bloque(falla.direccion_inyeccion, tamano_bytes)
                    if len(mem_pre) == 0:
                        mem_pre = [0]

                    # Valor original (primer elemento)
                    try:
                        valor_original = int(mem_pre[0])
                    except Exception:
                        valor_original = 0

                    # imprimir valor antes (MEM_0)
                    try:
                        print(f"[INFO] Valor antes de falla (MEM_0): 0x{valor_original:08X}")
                    except Exception:
                        print("[INFO] Valor antes de falla (MEM_0): 0x00000000")

                    snap_pre = self.construir_snapshot_dict(reg_pre, mem_pre)
                    self.guardar_snapshot('before', falla.id_falla, falla.id_falla, snap_pre)

                    # Inyectar falla (usando aplicar())
                    valor_con_falla = falla.aplicar(self.core)
                    if valor_con_falla is None:
                        print("[ERROR] No se pudo aplicar la falla")
                    else:
                        try:
                            print(f"[INFO] Valor con falla aplicado: 0x{int(valor_con_falla):08X}")
                        except Exception:
                            print("[INFO] Valor con falla aplicado: 0x00000000")

                    # Verificar lectura posterior
                    try:
                        valor_leido = self.core.read_memory(falla.direccion_inyeccion, 32)
                        try:
                            print(f"[INFO] Valor leído después: 0x{int(valor_leido):08X}")
                        except Exception:
                            print("[INFO] Valor leído después: 0x00000000")
                    except Exception:
                        valor_leido = None
                        self.no_lectura += 1
                        print("[WARNING] No se pudo leer valor después de la inyección")

                    # Snapshot AFTER
                    reg_post = self.snapshot_registros()
                    mem_post = self.snapshot_memoria_bloque(falla.direccion_inyeccion, tamano_bytes)
                    if len(mem_post) == 0:
                        mem_post = [0]
                    snap_post = self.construir_snapshot_dict(reg_post, mem_post)
                    self.guardar_snapshot('after', falla.id_falla, falla.id_falla, snap_post)

                    # Determinar estado y actualizar contadores
                    estado = 'OK'
                    if valor_con_falla is None:
                        estado = 'ERROR_APLICANDO'
                    elif valor_leido is None:
                        estado = 'NO_LEIDO'
                    elif int(valor_leido) != int(valor_con_falla):
                        estado = 'NO_ESCRITA'
                        self.no_inyectadas_valor_no_escrito += 1

                    if estado == 'NO_ESCRITA':
                        print("[WARNING] La falla NO se escribió correctamente")
                    elif estado == 'ERROR_APLICANDO':
                        print("[ERROR] Error aplicando la falla")
                    else:
                        print("[INFO] Falla escrita correctamente ✅")

                    # Loggear la falla en faults_log.csv
                    try:
                        self.log_falla(falla, valor_original, valor_con_falla, valor_leido, estado)
                    except Exception as e:
                        print(f"[WARNING] Error al loggear falla: {e}")

                    # Remover bp temporal
                    try:
                        self.core.remove_breakpoint(bp_addr)
                        print("[INFO] BP temporal removido")
                    except Exception:
                        print("[WARNING] No se pudo remover BP temporal")

                    # Continuar hasta stop address
                    try:
                        self.core.resume()
                        print("[INFO] Reanudando hacia stop_address…")
                    except Exception as e:
                        print(f"[WARNING] No se pudo resume() tras inyección: {e}")

                    break

            time.sleep(delay)

        # ----------------------------------------------------------
        # Esperar STOP_ADDRESS (BP fijo)
        # ----------------------------------------------------------
        start = time.time()
        while True:
            if time.time() - start > 5.0:
                self.no_lectura += 1
                print(f"[WARNING] Timeout esperando stop_address para falla {falla.id_falla}")
                return

            if self.core.is_halted():
                try:
                    pc_now = self.core.read_core_register('pc')
                except Exception:
                    pc_now = None
                print(f"[INFO] MCU detenido en PC=0x{(pc_now or 0):08X}")

                if pc_now == self.stop_address:
                    print(f"[INFO] Stop_address alcanzado: 0x{self.stop_address:08X}")

                    reg_stable = self.snapshot_registros()
                    mem_stable = self.snapshot_memoria_bloque(falla.direccion_inyeccion, tamano_bytes)
                    if len(mem_stable) == 0:
                        mem_stable = [0]
                    snap_stable = self.construir_snapshot_dict(reg_stable, mem_stable)
                    self.guardar_snapshot('after_stable', falla.id_falla, falla.id_falla, snap_stable)

                    print(f"[✅] Falla {falla.id_falla} COMPLETADA\n")
                    return

            time.sleep(delay)

    def ejecutar(self):
        print("\n[INFO] ================= INICIANDO CAMPAÑA =================")
        self.tiempo_total_inicio = time.time()

        total_fallas = len(self.lista_fallas)

        for falla in self.lista_fallas:
            self.inject(falla)

        tiempo_total = time.time() - self.tiempo_total_inicio

        fallas_no_iny = self.no_inyectadas
        fallas_no_escritas = self.no_inyectadas_valor_no_escrito
        errores_lectura = self.no_lectura

        fallas_correctas = total_fallas - (fallas_no_iny + fallas_no_escritas)

        # Evitar división entre 0
        if total_fallas > 0:
            p_correctas = (fallas_correctas / total_fallas) * 100
            p_no_iny = (fallas_no_iny / total_fallas) * 100
            p_no_escritas = (fallas_no_escritas / total_fallas) * 100
            p_lectura = (errores_lectura / total_fallas) * 100
        else:
            p_correctas = p_no_iny = p_no_escritas = p_lectura = 0.0

        # ============================
        #   IMPRIMIR RESUMEN
        # ============================
        print("\n\n========== RESUMEN DE CAMPAÑA ==========")
        print(f"Fallas totales: {total_fallas}")
        print(f"Fallas inyectadas correctamente: {fallas_correctas} ({p_correctas:.2f}%)")
        print(f"Fallas NO inyectadas: {fallas_no_iny} ({p_no_iny:.2f}%)")
        print(f"Fallas con valor NO escrito: {fallas_no_escritas} ({p_no_escritas:.2f}%)")
        print(f"Errores de lectura: {errores_lectura} ({p_lectura:.2f}%)")
        print(f"Tiempo total de campaña: {tiempo_total:.2f} segundos")
        print("========================================\n")

        # ============================
        #   GUARDAR RESUMEN EN ARCHIVO
        # ============================
        resumen_path = os.path.join(self.campaign_dir, "resumen.txt")

        try:
            with open(resumen_path, "w") as f:
                f.write("========== RESUMEN DE CAMPAÑA ==========\n")
                f.write(f"Fallas totales: {total_fallas}\n")
                f.write(f"Fallas inyectadas correctamente: {fallas_correctas} ({p_correctas:.2f}%)\n")
                f.write(f"Fallas NO inyectadas: {fallas_no_iny} ({p_no_iny:.2f}%)\n")
                f.write(f"Fallas con valor NO escrito: {fallas_no_escritas} ({p_no_escritas:.2f}%)\n")
                f.write(f"Errores de lectura: {errores_lectura} ({p_lectura:.2f}%)\n")
                f.write(f"Tiempo total de campaña: {tiempo_total:.2f} segundos\n")
                f.write("========================================\n")

            print(f"[INFO] Resumen guardado en: {resumen_path}")

        except Exception as e:
            print(f"[ERROR] No se pudo guardar el resumen: {e}")


def main():
    from M_gestion_mcu import MCU

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
    #"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"
    #"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.map"
    #"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"
    #"/Users/apple/Documents/PruebasST/LED/Debug/LED.map"
    try:
        with MCU(opts, elf_path) as mcu:
            core = mcu.core
            injector = FaultInjector(core, mcu.session, csv_file, elf_path)

            print("[INFO] Inyección de fallas iniciada")
            injector.ejecutar()
            print("[INFO] Inyección de fallas completada")

    except Exception as e:
        print(f"[ERROR] Falló la inicialización o ejecución: {e}")


if __name__ == '__main__':
    main()

