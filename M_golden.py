import csv
import os
import time
from datetime import datetime

from M_deteccion_stop import detectar_while_infinito
from M_gestion_MCU_ram import MCU_RAM
from M_gestion_mcu import  MCU

def parse_int_optional(s):
    if s is None:
        return None
    s = str(s).strip()
    if s == '':
        return None
    try:
        return int(s,0)
    except ValueError:
        raise ValueError(f'Valor numérico inválido: {s}')


def _to_hex_safe(val):
    try:
        if val is None:
            return '0x00000000'
        ival = int(val)
        return f'0x{(ival & 0xFFFFFFFF):08X}'
    except Exception:
        return '0x00000000'

class FALLAGOLD:
    def __init__(self, id_falla, direccion_inyeccion, ubicacion):
        self.id_falla = id_falla
        self.direccion_inyeccion = direccion_inyeccion
        self.ubicacion = ubicacion

class GOLDEN:
    def __init__(self, mcu = None, csv_file = None, elf_main_path = None, elf_ram_path = None, main_opts=None):
        self.mcu = mcu
        self.core = getattr(mcu, 'core', None) if mcu is not None  else None
        self.session = getattr(mcu, 'session', None) if mcu is not None else None

        self.csv_file = csv_file
        self.elf_path = elf_main_path
        self.elf_ram_path = elf_ram_path
        self.opts =main_opts or {}
        self.lista_fallas = []

        if self.csv_file:
            self.cargar_csv()

        for path, label, attr in [
            (self.elf_path, "elf_main", "stop_address"),
            (self.elf_ram_path, "elf_ram", "stop_address_flash")
        ]:
            if path:
                try:
                    addr, _ = detectar_while_infinito(path)
                    setattr(self, attr, addr)
                    print(f"[INFO] Stop address detectada ({label}): 0x{addr:08X}")
                except Exception as e:
                    setattr(self, attr, None)
                    print(f"[WARNING] No se pudo detectar stop_address ({label}): {e}")
            else:
                setattr(self, attr, None)

        if self.lista_fallas:
            self.inicializar_archivos()
        else:
            self.campaign_dir = None

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
            try:
                resultado2 = detectar_while_infinito(self.elf_ram_path)
                addr_salto2, _ = resultado2
                self.stop_address_flash = addr_salto2
                print(f"[INFO] Stop address detectada (elf_main): 0x{self.stop_address:08X}")
            except Exception as e:
                print(f"[WARNING] No se pudo detectar stop_address en elf_main: {e}")

    def cargar_elves_desde_gui(self, elf_main, elf_ram):
        """Conveniencia para la GUI: establece ambos ELF de una llamada."""
        self.set_elf_paths(elf_main=elf_main, elf_ram=elf_ram)

    def cargar_csv(self, csv_file = None):
        path = csv_file or self.csv_file
        if not path:
            raise ValueError(f'No hay ruta CSV para cargar')
        self.csv_file = path
        self.lista_fallas = []
        with open(self.csv_file, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    id_falla = int(row['FAULT_ID'])
                    ubic = (row.get('UBICACION') or '').strip()
                    dir_iny = parse_int_optional(row.get('DIRECCION INYECCION'))
                    falla = FALLAGOLD(id_falla, dir_iny, ubic)
                    self.lista_fallas.append(falla)
                except Exception as e:
                    print(f'[WARNING] Fila ignorada: {e}')
        print(f'[INFO] {len(self.lista_fallas)} fallas cargadas')
        self.inicializar_archivos()

    def obtener_ultima_campania(self, base_dir=None):
        base_dir = base_dir or (os.path.dirname(self.csv_file) if self.csv_file else os.getcwd())
        if not os.path.exists(base_dir):
            return None
        subs = [os.path.join(base_dir, d) for d in os.listdir(base_dir)
                if os.path.isdir(os.path.join(base_dir, d))]
        if not subs:
            return None
        subs.sort(key=os.path.getmtime)
        return subs[-1]

    def inicializar_archivos(self):
        base_dir = os.path.dirname(self.csv_file) if self.csv_file else os.getcwd()

        if getattr(self, 'campaign_dir', None) and os.path.isdir(self.campaign_dir):
            campaign_dir = self.campaign_dir
        else:
            ultima = self.obtener_ultima_campania(base_dir)
            if ultima:
                campaign_dir = ultima
            else:
                campaign_name = datetime.now().strftime("campaign_%Y%m%d_%H%M%S")
                campaign_dir = os.path.join(base_dir, campaign_name)
                os.makedirs(campaign_dir, exist_ok=True)
                print(f"[INFO] Carpeta de campaña creada: {campaign_dir}")

        self.campaign_dir = campaign_dir
        self.snapshot_gold_csv = os.path.join(self.campaign_dir, 'snapshots_gold.csv')

        hay_memoria = any((f.ubicacion or '').lower() in ['ram', 'flash'] for f in self.lista_fallas)
        self.mem_cols_count = 256 if hay_memoria else 1
        mem_cols = [f"MEM_{i}" for i in range(self.mem_cols_count)]
        header = ['Test_ID','Fault_ID', 'PC', 'SP', 'LR'] + [f'R{i}' for i in range(13)] + mem_cols

        try:
            with open(self.snapshot_gold_csv, 'w', newline='') as f:
                csv.writer(f).writerow(header)
            print(f"[INFO] Creado archivo: {self.snapshot_gold_csv} (MEM cols: {self.mem_cols_count})")
        except Exception as e:
            print(f"[WARNING] No se pudo crear {self.snapshot_gold_csv}: {e}")

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
        path = self.snapshot_gold_csv if tipo == 'gold' else None
        if path is None:
            return

        row = [test_id, fault_id, snap['PC'], snap['SP'], snap['LR']]
        row += [snap[f'R{i}'] for i in range(13)]

        for i in range(self.mem_cols_count):
            row.append(snap.get(f'MEM_{i}', _to_hex_safe(0)))

        with open(path, 'a', newline='') as f:
            csv.writer(f).writerow(row)

    def esperar_halt(self, timeout=5.0):
        if self.core is None:
            return False
        t0 = time.time()
        while not self.core.is_halted():
            if time.time() - t0 > timeout:
                return False
            time.sleep(0.01)
        return True

    def inject(self, falla, delay = 0.5):
        ubic = (falla.ubicacion or '').lower()

        if ubic in ['flash']:
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

            try:
                with MCU_RAM(self.opts, self.elf_ram_path) as mcu_ram:
                    print("[INFO] Sesión temporal abierta para programar e inyectar (FLASH).")
                    try:
                        mcu_ram.core.set_breakpoint(self.stop_address_flash, mcu_ram.core.BreakpointType.HW)
                        print(f"[INFO] BP colocado antes del resume: 0x{self.stop_address_flash:08X}")
                    except Exception as e:
                        print(f"[WARNING] No se pudo establecer BP antes del resume: {e}")

                    try:
                        mcu_ram.core.reset_and_halt()
                        mcu_ram.core.resume()
                        time.sleep(delay)
                        mcu_ram.core.halt()
                        ret = mcu_ram.boot_from_elf_vector(force_program=True, halt_before_program=True)
                        mcu_ram.core.halt()
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
                    resultado = self._inj_memoria_flash(falla, 256, delay)

                # ✅ Al salir del with → sesión temporal YA se cerró
                # Limpieza de referencias para evitar estados corruptos
                self.mcu = None
                self.core = None
                self.session = None

                # ✅ Ahora sí devolver resultado
                return resultado

            except Exception as e:
                print(f"[ERROR] Falló reprogramación/inyección FLASH: {e}")

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
                    return
            try:
                self.core.set_breakpoint(self.stop_address, self.core.BreakpointType.HW)
            except Exception as e:
                print(f"[WARNING] No se pudo establecer bp stop: {e}")
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
                    return
            try:
                self.core.set_breakpoint(self.stop_address, self.core.BreakpointType.HW)
            except Exception as e:
                print(f"[WARNING] No se pudo establecer bp stop: {e}")
            return self._inj_memoria(falla, 256, delay)

    def _inj_memoria(self, falla, tamano_bytes, delay):

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
        try:
            self.core.resume()
            print("[INFO] MCU reanudado, esperando BP temporal…")
        except Exception as e:
            print(f"[WARNING] No se pudo resume(): {e}")

        while True:
            if self.core.is_halted():
                try:
                    pc = self.core.read_core_register('pc')
                except Exception:
                    pc = None
                print(f"[INFO] MCU detenido en PC=0x{(pc or 0):08X}")

                if pc == self.stop_address:
                    # snapshot GOLD
                    reg_pre = self.snapshot_registros()
                    mem_pre = self.snapshot_memoria_bloque(falla.direccion_inyeccion, tamano_bytes)
                    if len(mem_pre) == 0:
                        mem_pre = [0]
                    snap_pre = self.construir_snapshot_dict(reg_pre, mem_pre)
                    self.guardar_snapshot('gold', falla.id_falla, falla.id_falla, snap_pre)
                    print(f"[INFO] Snapshot GOLD guardado para falla #{falla.id_falla}")
                    return  # 🔹 Sal del while → pasa a la siguiente falla

            time.sleep(delay)

    def _inj_memoria_flash(self, falla, tamano_bytes, delay):
        try:
            self.core.halt()
            print("[INFO] MCU detenido (HALT) para conservar ELF en RAM")
        except Exception as e:
            print(f"[WARNING] No se pudo detener MCU antes de inyectar FLASH: {e}")
        try:
            self.core.resume()
            print("[INFO] MCU reanudado, esperando BP temporal…")
        except Exception as e:
            print(f"[WARNING] No se pudo resume(): {e}")


        while True:
            if self.core.is_halted():
                try:
                    pc = self.core.read_core_register('pc')
                except Exception:
                    pc = None
                print(f"[INFO] MCU detenido en PC=0x{(pc or 0):08X}")

                if pc == self.stop_address_flash:
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
                    self.guardar_snapshot('gold', falla.id_falla, falla.id_falla, snap_pre)
                    try:
                        self.core.resume()
                        self.core.reset_and_halt()
                    except Exception:
                        pass
                    return
            #self.core.reset()
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
            injector = GOLDEN(mcu=mcu, csv_file=csv_file, elf_main_path=elf_main, elf_ram_path=elf_ram, main_opts=opts)
            # Alternativamente la GUI podría llamar:
            # injector.cargar_elves_desde_gui(elf_main, elf_ram)
            # injector.cargar_csv(csv_file)  # si no pasó csv al constructor

            injector.ejecutar()
    except Exception as e:
        print(f"[ERROR] Falló la inicialización o ejecución (ejemplo): {e}")


if __name__ == '__main__':
    main_example()



