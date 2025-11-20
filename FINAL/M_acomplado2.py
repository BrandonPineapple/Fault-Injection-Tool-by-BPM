import os
import subprocess
import sys
import webbrowser
import time

from pathlib import Path
from M_analisis_archivos_elf import ElfAnalyzer
from M_analizador_svd import ListaRegistros
from M_generador_lista_fallas_mejorado import RandomFaultGenerator
from Pruebas_inyector_2 import FaultInjector
from M_gestion_mcu import MCU
from M_golden import GOLDEN
from M_analizador import analizar_campana_avanzado


class ACOPLADO:
    def __init__(self, elf_flash, map_flash, elf_ram, map_ram,
                 microcontrolador, periferico, numero_fallas,
                 ubicacion, tipo_falla):
        # Entradas necesarias
        self.elf_flash = Path(elf_flash)
        self.map_flash = Path(map_flash)
        self.elf_ram = Path(elf_ram)
        self.map_ram = Path(map_ram)
        self.microcontrolador = microcontrolador
        self.periferico = periferico
        self.numero_fallas = numero_fallas
        self.ubicacion = ubicacion
        self.tipo_falla = tipo_falla

        self.opts = {
            "frequency": 1800000,
            "connect_mode": "under_reset",
            "halt_on_connect": True,
            "resume_on_disconnect": False,
            "reset_type": "hw",
            "vector_catch": "reset,hardfault,memmanage,busfault,usagefault",
            "enable_semihosting": False
        }

        # Directorio donde están los archivos SVD
        self.svd_repo = Path(__file__).resolve().parent / "cmsis-svd-data" / "data"
        # Para guardar CSVs
        self.out_dir = Path(__file__).resolve().parent

    # ------------------------------------------------------------------
    # Flujo principal pseudo: ram y regsitros
    # ------------------------------------------------------------------
    def pseudo(self, abrir_gui=True):
        print("\n[ACOPLADO] === Iniciando pseudo_ram ===\n")

        self._modulo_elf()
        self._modulo_svd()
        self._modulo_generador_fallas()
        self._modulo_inyeccion_fallas()
        self._modulo_golden()
        self._modulo_analizador(abrir_gui)

        print("\n[ACOPLADO] === Finalizó pseudo_ram ===\n")

    # ------------------------------------------------------------------
    # Flujo principal pseudo: flash
    # ------------------------------------------------------------------
    def pseudo_flash(self, abrir_gui=True):

        self._modulo_elf_flash()
        self._modulo_svd()
        self._modulo_generador_fallas_flash()
        self._modulo_inyeccion_fallas()
        self._modulo_golden()
        self._modulo_analizador(abrir_gui)

        print("\n[ACOPLADO] === Finalizó pseudo_ram ===\n")

    # ------------------------------------------------------------------
    # Flujo principal inyeccion por usuario
    # ------------------------------------------------------------------
    def usuario(self, abrir_gui=True):

        self._modulo_inyeccion_fallas_usuario()
        self._modulo_golden_usuario()
        self._modulo_analizador(abrir_gui)

        print("\n[ACOPLADO] === Finalizó pseudo_ram ===\n")

    # ------------------------------------------------------------------
    # Flujo principal inyeccion por usuario
    # ------------------------------------------------------------------
    def reproducir_csv(self, ruta_csv, abrir_gui=True):
        print("\n[ACOPLADO] === Reproduciendo fallas desde CSV externo ===\n")
        self._modulo_inyeccion_fallas_csv(ruta_csv)
        self._modulo_golden()
        self._modulo_analizador(abrir_gui)
        print("\n[ACOPLADO] === Finalizó reproducción desde CSV ===\n")

    # ------------------------------------------------------------------
    # Módulo 1: Análisis ELF
    # ------------------------------------------------------------------
    def _modulo_elf(self):
        print("[ACOPLADO] Ejecutando módulo: análisis ELF...")
        analizador = ElfAnalyzer(self.elf_flash)
        analizador.list_exec_addresses()
        analizador.generate_csv()
        print("[ACOPLADO] Módulo análisis ELF completado.\n")

    def _modulo_elf_flash(self):
        print("[ACOPLADO] Ejecutando módulo: análisis ELF...")
        analizador = ElfAnalyzer(self.elf_ram)
        analizador.list_exec_addresses()
        analizador.generate_csv()
        print("[ACOPLADO] Módulo análisis ELF completado.\n")


    # ------------------------------------------------------------------
    # Módulo 2: Analizador SVD
    # ------------------------------------------------------------------
    def _modulo_svd(self):
        print("[ACOPLADO] Ejecutando módulo: análisis SVD...")
        generator = ListaRegistros(self.microcontrolador, self.svd_repo)
        generator.generador_lista_fallas()
        generator.save_results(self.out_dir)
        generator.save_results_peripheral(self.periferico, self.out_dir)
        print("[ACOPLADO] Módulo análisis SVD completado.\n")

    # ------------------------------------------------------------------
    # Módulo 3: Generador de fallas pseudoaleatorio
    # ------------------------------------------------------------------
    def _modulo_generador_fallas(self):
        print("[ACOPLADO] Ejecutando módulo: generador de fallas...")
        flash_csv = self.out_dir / "DIRECCIONES_EJECUTABLE.csv"
        reg_csv = self.out_dir / "LISTA_FALLAS_PERIFERICO.csv"
        map_path = self.map_flash
        out_csv = self.out_dir / "LISTA_INYECCION.csv"

        gen = RandomFaultGenerator(
            flash_csv=flash_csv,
            reg_csv=reg_csv,
            elf_path=self.elf_flash,
            map_path=map_path
        )

        gen.load_flash_csv()
        gen.load_reg_csv()
        faults = gen.generate_random_faults(self.numero_fallas, self.ubicacion, self.tipo_falla)
        gen.save_to_csv(faults, out_csv)

        print("[ACOPLADO] Módulo generador de fallas completado.\n")

    def _modulo_generador_fallas_flash(self):
        print("[ACOPLADO] Ejecutando módulo: generador de fallas...")
        flash_csv = self.out_dir / "DIRECCIONES_EJECUTABLE.csv"
        reg_csv = self.out_dir / "LISTA_FALLAS_PERIFERICO.csv"
        out_csv = self.out_dir / "LISTA_INYECCION.csv"

        gen = RandomFaultGenerator(
            flash_csv=flash_csv,
            reg_csv=reg_csv,
            elf_path=self.elf_ram,
            map_path=self.map_ram
        )

        gen.load_flash_csv()
        gen.load_reg_csv()
        faults = gen.generate_random_faults(self.numero_fallas, self.ubicacion, self.tipo_falla)
        gen.save_to_csv(faults, out_csv)

        print("[ACOPLADO] Módulo generador de fallas completado.\n")

    # ------------------------------------------------------------------
    # Módulo 4: Inyección de fallas
    # ------------------------------------------------------------------
    def _modulo_inyeccion_fallas(self):
        elf_main = str(self.elf_flash)
        elf_ram = str(self.elf_ram)
        csv_file = str(self.out_dir / "LISTA_INYECCION.csv")

        print(f"[DEBUG] CSV path: {csv_file}, ELF main: {elf_main}, ELF RAM: {elf_ram}")

        try:
            with MCU(self.opts, elf_main) as mcu:
                injector = FaultInjector(
                    mcu=mcu,
                    csv_file=csv_file,
                    elf_main_path=elf_main,
                    elf_ram_path=elf_ram,
                    main_opts=self.opts
                )
                print("[INFO] Inyección de fallas iniciada.")
                injector.ejecutar()
                print("[INFO] Inyección de fallas completada.")
        except Exception as e:
            print(f"[ERROR] Falló la inyección de fallas: {e}")

    def _modulo_inyeccion_fallas_usuario(self):
        elf_main = str(self.elf_flash)
        elf_ram = str(self.elf_ram)
        csv_file = str(self.out_dir / "LISTA_INYECCION_USUARIO.csv")

        print(f"[DEBUG] CSV path: {csv_file}, ELF main: {elf_main}, ELF RAM: {elf_ram}")

        try:
            with MCU(self.opts, elf_main) as mcu:
                injector = FaultInjector(
                    mcu=mcu,
                    csv_file=csv_file,
                    elf_main_path=elf_main,
                    elf_ram_path=elf_ram,
                    main_opts=self.opts
                )
                print("[INFO] Inyección de fallas iniciada.")
                injector.ejecutar()
                print("[INFO] Inyección de fallas completada.")
        except Exception as e:
            print(f"[ERROR] Falló la inyección de fallas: {e}")

    def _modulo_inyeccion_fallas_csv(self, ruta_csv):
        elf_main = str(self.elf_flash)
        elf_ram = str(self.elf_ram)
        csv_file = str(Path(ruta_csv))

        if not os.path.exists(csv_file):
            print(f"[ERROR] No se encontró el CSV especificado: {csv_file}")
            return

        print(f"[DEBUG] CSV path: {csv_file}, ELF main: {elf_main}, ELF RAM: {elf_ram}")

        try:
            with MCU(self.opts, elf_main) as mcu:
                injector = FaultInjector(
                    mcu=mcu,
                    csv_file=csv_file,
                    elf_main_path=elf_main,
                    elf_ram_path=elf_ram,
                    main_opts=self.opts
                )
                print("[INFO] Inyección de fallas iniciada desde CSV externo.")
                injector.ejecutar()
                print("[INFO] Inyección de fallas completada.")
        except Exception as e:
            print(f"[ERROR] Falló la inyección de fallas desde CSV externo: {e}")

    # ------------------------------------------------------------------
    # Módulo 5: GOLDEN
    # ------------------------------------------------------------------
    def _modulo_golden(self):
        print("\n[ACOPLADO] Ejecutando módulo: GOLDEN...\n")
        elf_main = str(self.elf_flash)
        elf_ram = str(self.elf_ram)
        csv_file = str(self.out_dir / "LISTA_INYECCION.csv")

        if not os.path.exists(csv_file):
            print(f"[ERROR] CSV de fallas no encontrado: {csv_file}")
            return

        try:
            with MCU(self.opts, elf_main) as mcu:
                injector = GOLDEN(
                    mcu=mcu,
                    csv_file=csv_file,
                    elf_main_path=elf_main,
                    elf_ram_path=elf_ram,
                    main_opts=self.opts
                )
                num_fallas = len(injector.lista_fallas)
                print(f"[INFO] GOLDEN cargado con {num_fallas} fallas")
                if num_fallas > 0:
                    injector.ejecutar()
                    print("[INFO] Ejecución GOLDEN completada.")
        except Exception as e:
            print(f"[ERROR] Falló GOLDEN: {e}")

    def _modulo_golden_usuario(self):
        print("\n[ACOPLADO] Ejecutando módulo: GOLDEN...\n")
        elf_main = str(self.elf_flash)
        elf_ram = str(self.elf_ram)
        csv_file = str(self.out_dir / "LISTA_INYECCION_USUARIO.csv")

        if not os.path.exists(csv_file):
            print(f"[ERROR] CSV de fallas no encontrado: {csv_file}")
            return

        try:
            with MCU(self.opts, elf_main) as mcu:
                injector = GOLDEN(
                    mcu=mcu,
                    csv_file=csv_file,
                    elf_main_path=elf_main,
                    elf_ram_path=elf_ram,
                    main_opts=self.opts
                )
                num_fallas = len(injector.lista_fallas)
                print(f"[INFO] GOLDEN cargado con {num_fallas} fallas")
                if num_fallas > 0:
                    injector.ejecutar()
                    print("[INFO] Ejecución GOLDEN completada.")
        except Exception as e:
            print(f"[ERROR] Falló GOLDEN: {e}")

    # ------------------------------------------------------------------
    # Módulo 6: Analizador avanzado + Streamlit
    # ------------------------------------------------------------------
    def _modulo_analizador(self, abrir_gui=True):
        print("[ACOPLADO] Ejecutando módulo: Analizador Avanzado...")
        analizar_campana_avanzado()
        if abrir_gui:
            streamlit_file = Path(__file__).parent / "M_iterativo.py"
            subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(streamlit_file)])
            # Esperar 2 segundos y abrir navegador en localhost
            time.sleep(2)
            webbrowser.open("http://localhost:8501")


# ----------------------------------------------------------------------
# MAIN PARA PROBAR EL ACOPLAMIENTO COMPLETO
# ----------------------------------------------------------------------
if __name__ == "__main__":

    #Entradas de la GUI
    elf_flash = "/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"
    map_flash = "/Users/apple/Documents/PruebasST/LED/Debug/LED.map"
    elf_ram = "/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"
    map_ram = "/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.map"
    micro = "stm32f407g-disc1"
    peri= 'GPIOD'
    num_fallas = 100
    ubi = 'flash'
    tipo_falla = 'todos'

    acop = ACOPLADO(
        elf_flash=elf_flash,
        map_flash=map_flash,
        elf_ram=elf_ram,
        map_ram=map_ram,
        microcontrolador=micro,
        periferico=peri,
        numero_fallas=num_fallas,
        ubicacion=ubi,
        tipo_falla=tipo_falla
    )

    acop.pseudo_flash()



