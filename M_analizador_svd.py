#------------------------MODULO ANALIZADOR DE REGISTROS SVD-------------------------------#
from pathlib import Path
from cmsis_svd.parser import SVDParser  # Permite leer y analizar .svd
import csv

class ListaRegistros:
    def __init__(self, micro: str, svd_repo: Path):
        self.micro = micro
        self.svd_repo = svd_repo
        self.lista_fallas = []          # Lista completa de bits
        self.peripherals_dict = {}      # Diccionario: periférico -> lista de bits
        self.micro_svds = {"stm32f407g-disc1": "STM32F407.svd"}

    def find_svd_path(self) -> Path:
        svd_file = self.micro_svds.get(self.micro)
        if not svd_file:
            raise ValueError(f"❌ Micro {self.micro} no está definido en micro_svds")
        matches = list(self.svd_repo.rglob(svd_file))
        if not matches:
            raise FileNotFoundError(f"❌ No se encontró el archivo {svd_file} en {self.svd_repo}")
        print(f"✅ Usando archivo SVD: {matches[0]}")
        return matches[0]

    def generador_lista_fallas(self):
        """Carga el SVD y genera la lista de bits a inyectar y diccionario por periférico"""
        svd_path = self.find_svd_path()
        parser = SVDParser.for_xml_file(svd_path)
        device = parser.get_device()

        self.lista_fallas = []
        self.peripherals_dict = {}

        for peripheral in device.peripherals:
            peripheral_bits = []
            for reg in peripheral.registers:
                if "RESERVED" in reg.name.upper():
                    continue

                reg_addr = peripheral.base_address + reg.address_offset
                reg_size = reg.size or 32
                reg_access = str(reg.access or "unknown")

                if reg.fields:
                    for field in reg.fields:
                        if "RESERVED" in field.name.upper():
                            continue
                        field_access = str(field.access or reg_access)
                        if "READ_WRITE" not in field_access.upper():
                            continue
                        for bit in range(field.bit_width):
                            absolute_byte_addr = reg_addr + (field.bit_offset + bit) // 8
                            aligned_addr = absolute_byte_addr & ~0x3
                            bit_in_word = (absolute_byte_addr % 4) * 8 + ((field.bit_offset + bit) % 8)
                            bit_dict = {
                                "PERIFERICO": peripheral.name,
                                "REGISTRO": reg.name,
                                "CAMPO": field.name,
                                "DIRECCION": hex(aligned_addr),
                                "BIT": bit_in_word,
                                "TIPO DE ACCESO": field_access,
                                "MASCARA": f"0x{(1 << bit_in_word):08X}"
                            }
                            self.lista_fallas.append(bit_dict)
                            peripheral_bits.append(bit_dict)
                else:
                    if "READ_WRITE" in reg_access.upper():
                        for bit in range(reg_size):
                            absolute_byte_addr = reg_addr + bit // 8
                            aligned_addr = absolute_byte_addr & ~0x3
                            bit_in_word = (absolute_byte_addr % 4) * 8 + (bit % 8)
                            bit_dict = {
                                "PERIFERICO": peripheral.name,
                                "REGISTRO": reg.name,
                                "CAMPO": field.name,
                                "DIRECCION": hex(aligned_addr),
                                "BIT": bit_in_word,
                                "TIPO DE ACCESO": field_access,
                                "MASCARA": f"0x{(1 << bit_in_word):08X}"
                            }
                            self.lista_fallas.append(bit_dict)
                            peripheral_bits.append(bit_dict)

            self.peripherals_dict[peripheral.name] = peripheral_bits

        print(f"🔢 Total de bits listos para inyección: {len(self.lista_fallas)}")

    def save_results(self, out_dir: Path):
        """Guarda CSV completo"""
        if not self.lista_fallas:
            raise RuntimeError('⚠️ No se ha generado la lista de bits. Llama primero a generador_lista_fallas()')
        csv_path = out_dir / f'LISTA_FALLAS_TOTALES_REGISTROS.csv'
        fieldnames = ['PERIFERICO', 'REGISTRO', 'CAMPO', 'DIRECCION', 'BIT', 'TIPO DE ACCESO', 'MASCARA']
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for b in self.lista_fallas:
                writer.writerow(b)
        print(f"✅ CSV completo generado en: {csv_path}")

    def filtrar_periferico(self, peripheral_name: str):
        """Devuelve solo los registros del periférico indicado"""
        if not self.lista_fallas:
            raise RuntimeError('⚠️ No se ha generado la lista de bits. Llama primero a generador_lista_fallas()')
        filtrados = self.peripherals_dict.get(peripheral_name.upper(), [])
        if not filtrados:
            print(f"⚠️ No se encontraron registros para el periférico {peripheral_name}")
        return filtrados

    def save_results_peripheral(self, peripheral_name: str, out_dir: Path):
        """Guarda CSV solo con los registros del periférico indicado"""
        registros = self.filtrar_periferico(peripheral_name)
        if not registros:
            return
        csv_path = out_dir / f'LISTA_FALLAS_PERIFERICO.csv'
        fieldnames = ['PERIFERICO', 'REGISTRO', 'CAMPO', 'DIRECCION', 'BIT', 'TIPO DE ACCESO', 'MASCARA']
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for b in registros:
                writer.writerow(b)
        print(f"✅ CSV filtrado generado para {peripheral_name} en: {csv_path}")


# ---------------------------
# Main para pruebas
# ---------------------------
if __name__ == '__main__':
    micro = "stm32f407g-disc1"
    svd_repo = Path(__file__).resolve().parent / "cmsis-svd-data" / "data"
    out_dir = Path(__file__).resolve().parent

    generator = ListaRegistros(micro, svd_repo)
    generator.generador_lista_fallas()
    generator.save_results(out_dir)  # CSV completo

    # Filtrar solo registros de un periférico y guardar CSV
    generator.save_results_peripheral("GPIOD", out_dir)
