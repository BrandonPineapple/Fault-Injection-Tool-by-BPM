import csv
import os
import time
from datetime import datetime


from M_deteccion_stop import detectar_while_infinito


def parse_int_optional(s):
    """
    Convierte una entrada opcional a int autodetectando la base.
    Devuelve None si s es None o cadena vacía.
    """
    if s is None:
        return None
    s = str(s).strip()
    if s == '':
        return None
    try:
        return int(s, 0)  # autodetecta base (0x.., 0o.., etc.)
    except ValueError:
        raise ValueError(f"Valor numérico inválido: {s}")


class FALLA:
    def __init__(self, id_falla, direccion_inyeccion, direccion_breakpoint, mascara, tipo, ubicacion):
        self.id_falla = id_falla    # Identificador de la falla
        self.direccion_inyeccion = direccion_inyeccion  # dirección de memoria a aplicar la falla
        self.direccion_breakpoint = direccion_breakpoint    # dirección donde se colocará el BP
        self.mascara = mascara  # valor (máscara) para modificar el valor
        self.tipo = tipo    # tipo de falla: 'bitflip', 'stuck-0', 'stuck-1', etc.
        self.ubicacion = ubicacion  # 'ram', 'registro', 'flash', etc.

    # Método que va a aplicar la falla
    def aplicar(self, core):
        if self.ubicacion is None or self.direccion_inyeccion is None or self.mascara is None:
            return None

        try:
            valor_actual = core.read_memory(self.direccion_inyeccion, 32)
        except:
            return None

        tipo_lower = str(self.tipo).lower() if self.tipo else ''
        if 'bitflip' in tipo_lower or 'biflip' in tipo_lower:
            valor_con_falla = valor_actual ^ self.mascara
        elif 'stuck' in tipo_lower and '0' in tipo_lower:
            valor_con_falla = valor_actual & ~self.mascara
        elif 'stuck' in tipo_lower and '1' in tipo_lower:
            valor_con_falla = valor_actual | self.mascara

        else:
            return None

        try:
            core.write_memory(self.direccion_inyeccion, valor_con_falla, 32)
        except:
            return None

        return valor_con_falla

class FaultInjector:
    def __init__(self, core, session, csv_file, elf_path):
        self.core = core
        self.session = session
        self.csv_file = csv_file
        self.lista_fallas = []

        self.no_inyectadas = 0
        self.no_inyectadas_valor_no_escrito = 0
        self.no_lectura = 0

        self.resultados = []
        self.elf_path = elf_path

        self.cargar_csv()

        resultado = detectar_while_infinito(self.elf_path)
        addr_salto, _ = resultado
        self.stop_address = addr_salto
        print(f"[INFO] Stop address detectada: 0x{self.stop_address:08X}")

        try:
            self.core.set_breakpoint(self.stop_address, self.core.BreakpointType.HW)
            print(f'[INFO] BP fijo en stop address 0x{self.stop_address:08x}')
        except Exception as e:
            print(f'[WARNING] No se pudo establecer el BP fijo en stop addres: {e}')

        #Inicializa arhcivos a escribir
        self.inicializar_archivos()
    #------------------------------
    #   Cargar CSV
    #------------------------------
    def cargar_csv(self):
        with open(self.csv_file, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    id_falla = int(row['FAULT_ID']) if row.get('FAULT_ID') else None
                    ubicacion = row.get('UBICACION') or ''
                    direccion_inyeccion = parse_int_optional(row.get('DIRECCION INYECCION'))
                    direccion_stopbp = parse_int_optional(row.get('DIRECCION STOP'))
                    mascara = parse_int_optional(row.get('MASCARA'))
                    tipo = row.get('TIPO_FALLA')

                    falla = FALLA(id_falla=id_falla,
                                  direccion_inyeccion=direccion_inyeccion,
                                  direccion_breakpoint=direccion_stopbp,
                                  mascara=mascara, tipo=tipo,
                                  ubicacion=ubicacion)
                    self.lista_fallas.append(falla)
                except Exception as e:
                    print(f'[WARNING] Fila ignorada por error de parseo: {e} -- fila {row}')

        print(f"[INFO] {len(self.lista_fallas)} fallas cargadas desde {self.csv_file}")

    #------------------------------
    #   Snapshots
    #------------------------------
    def inicializar_archivos(self):
        # Crear carpeta de campaña
        campaign_name = datetime.now().strftime("campaign_%Y%m%d_%H%M%S")
        self.campaign_dir = os.path.join(os.path.dirname(self.csv_file), campaign_name)
        os.makedirs(self.campaign_dir, exist_ok=True)

        print(f"[INFO] Carpeta de campaña creada: {self.campaign_dir}")

        # Paths de snapshot
        self.snapshot_before_csv = os.path.join(self.campaign_dir, 'snapshots_before.csv')
        self.snapshot_after_csv = os.path.join(self.campaign_dir, 'snapshots_after.csv')
        self.snapshot_after_stable_csv = os.path.join(self.campaign_dir, 'snapshots_after_stable.csv')

        # Encabezado estándar
        header = ['Test_ID', 'Fault_ID', 'PC', 'SP', 'LR'] + \
                 [f'R{i}' for i in range(13)] + \
                 [f'MEM_{i}' for i in range(256)]

        # Crear archivos con encabezado sólo si no existen
        for path in [self.snapshot_before_csv, self.snapshot_after_csv, self.snapshot_after_stable_csv]:
            if not os.path.exists(path):
                with open(path, mode='w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                print(f"[INFO] Creado archivo: {path}")
            else:
                print(f"[WARNING] Archivo ya existía, no se sobrescribió: {path}")

    def snapshot_registros(self):
        if not self.esperar_halt():
            print(f'[WARNING] CPU no detenido snapshot de registros')
            return {}
        registros = {}
        registros['pc'] = self.core.read_core_register('pc')
        registros['sp'] = self.core.read_core_register('sp')
        registros['lr'] = self.core.read_core_register('lr')
        for i in range(13):
            registros[f'r{i}'] = self.core.read_core_register(f'r{i}')
        return registros

    def snapshot_memoria_bloque(self, direccion, tamano_bytes = 256):
        memoria = []
        for offset in range(0, tamano_bytes, 4):
            memoria.append((self.core.read_memory(direccion + offset, 32)))
        return memoria

    def construir_snapshot_dict(self, registros, memoria):
        snapshot = {}

        snapshot['PC'] = registros.get('pc', 0)
        snapshot['SP'] = registros.get('sp', 0)
        snapshot['LR'] = registros.get('lr', 0)

        for i in range(13):
            snapshot[f'R{i}'] = registros.get(f'r{i}', 0)

        for i in range(256):
            snapshot[f'MEM_{i}'] = memoria[i] if i < len(memoria) else 0

        return snapshot

    def guardar_snapshot(self, snapshot_type, test_id, fault_id, registro_dict):
        """
        Guarda un snapshot en el CSV correspondiente.
        snapshot_type: 'before', 'after', 'after_stable'
        registro_dict: dict con {'PC':..., 'SP':..., 'R0':..., 'MEM_0':...}
        """
        if snapshot_type == 'before':
            path = self.snapshot_before_csv
        elif snapshot_type == 'after':
            path = self.snapshot_after_csv
        elif snapshot_type == 'after_stable':
            path = self.snapshot_after_stable_csv
        else:
            raise ValueError("Tipo de snapshot inválido")

        # Convierte dict a lista en el orden del header
        row = [test_id, fault_id, registro_dict['PC'], registro_dict['SP'], registro_dict['LR']]
        row += [registro_dict[f'R{i}'] for i in range(13)]
        row += [registro_dict[f'MEM_{i}'] for i in range(256)]

        # Guardar en CSV con append
        with open(path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def esperar_halt(self, timeout = 5.0):
        start = time.time()
        while not self.core.is_halted():
            if time.time() - start > timeout:
                return False
            time.sleep(0.01)
        return True

    def inject(self, falla, max_retries=10, delay=0.05):

        ubic = falla.ubicacion.lower()
        valor_con_falla = None

        if ubic in ['ram', 'flash']:
            self.core.reset_and_halt()
            self.core.set_breakpoint(falla.direccion_breakpoint, self.core.BreakpointType.HW)
            time.sleep(0.01)
            self.core.resume()

            reg_pre = self.snapshot_registros()
            mem_pre = self.snapshot_memoria_bloque(falla.direccion_inyeccion, 256)
            snap_pre = self.construir_snapshot_dict(reg_pre, mem_pre)
            self.guardar_snapshot('before', test_id=falla.id_falla, fault_id=falla.id_falla, registro_dict=snap_pre)

            #Espera la dirección de la inyección
            timeout = 5.0
            start_espera = time.time()
            while True:
                if (time.time() - start_espera) > timeout:
                    self.no_inyectadas += 1
                    try:
                        self.core.remove_breakpoint(falla.direccion_breakpoint)
                    except Exception as e:
                        print((f'[WARNING] No se pudo remover el breakpoin {e}'))
                    #tiempo_espera = time.time() - start_espera
                    #self.resultados.append(falla.id_falla, 'No aplicada', )
                    return

                if self.core.is_halted():
                    pc = self.core.read_core_register('pc')
                    if pc == falla.direccion_breakpoint:
                        valor_con_falla = falla.aplicar(self.core)
                        valor_leido = self.core.read_memory(falla.direccion_breakpoint, 32)
                        reg_post = self.snapshot_registros()
                        mem_post = self.snapshot_memoria_bloque(falla.direccion_inyeccion, 256)
                        snap_post = self.construir_snapshot_dict(reg_post, mem_post)
                        self.guardar_snapshot('after', falla.id_falla, falla.id_falla, snap_post)

                        if valor_leido != valor_con_falla:
                            self.no_inyectadas_valor_no_escrito += 1

                        try: self.core.remove_breakpoint(falla.direccion.breakpoint)
                        except Exception as e:
                            print(f'[WARNING] No se pudo remover el breakpoint {e}')

                        self.core.resume()
                        break
                time.sleep(delay)

            start_stop = time.time()
            timeout = 5.0
            while True:
                if (time.time() - start_stop) > timeout:
                    self.no_lectura += 1
                    tiempo_stop = time.time() - start_stop

                if self.core.is_halted():
                    pc = self.core.read_core_register('pc')
                    if pc == self.stop_address:
                        tiempo_stop = time.time() - start_stop
                        reg_stable = self.snapshot_registros()
                        mem_stable = self.snapshot_memoria_bloque(falla.direccion_inyeccion, 256)
                        snap_stable = self.construir_snapshot_dict(reg_stable, mem_stable)
                        self.guardar_snapshot('after_stable', falla.id_falla, falla.id_falla, snap_stable)

                        self.core.halt()
                        break

        elif ubic == 'registro':
            print(f'Hola')




        else:
            print(f"[WARNING] Ubicación desconocida {falla.ubicacion}, falla ID {falla.id_falla}")








