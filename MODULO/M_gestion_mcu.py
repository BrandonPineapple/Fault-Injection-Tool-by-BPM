#------------------------MODULO DE GESTION DE SESION MCU-------------------------------#
from pyocd.core.helpers import ConnectHelper
from pyocd.flash.file_programmer import FileProgrammer

class MCU:
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

    def __enter__(self):
        """
        Se ejecuta automáticamente al entrar en un bloque 'with'.
        Abre la sesión con pyOCD, programa el ELF y obtiene el core.
        """
        #Cear sesión con pyOCD usando las opociones de configuración
        self.session = ConnectHelper.session_with_chosen_probe(options=self.opts)
        self.session.open()

        #Se obtiene el target (MCU)
        self.target = self.session.board.target
        #Se guarda el core principal de CPU
        self.core = getattr(self.target, "selected_core", self.target)

        #Se progarma el MCU con el arhcivo ELF
        FileProgrammer(self.session).program(self.elf_path)
        return self # Retornar objeto para usarlo dentro del 'with'

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Se ejecuta automáticamente al salir del bloque 'with'.
        Cierra la sesión de manera segura.
        """
        if self.session:
            self.session.close()
            self.session = None
            self.core = None
            self.target = None


if __name__ == '__main__':
    opts = {
        # "target_override": "stm32f407vg",  # fuerza el modelo correcto del MCU
        "frequency": 1800000,  # 2 MHz (confiable; sube/baja según tu cableado)
        "connect_mode": "under_reset",  # conecta y deja la CPU detenida
        "halt_on_connect": True,  # asegura el alto al conectar (útil para alterar memoria/regs)
        "resume_on_disconnect": False,  # no reanudar al salir de la sesión
        "reset_type": "hw",  # reset por hardware (determinista)
        "vector_catch": "reset,hardfault,memmanage,busfault,usagefault",  # atrapa faults para análisis
        "enable_semihosting": False  # actívalo solo si lo necesitas
    }
    elf_path = r"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"
    #"/Users/apple/Documents/PruebasST/LED/Debug/LED.elf"
    #"/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf"
    with MCU(opts, elf_path) as mcu:
        core = mcu.core
        target = mcu.target
        print(f'Sesión abierta, listo para usarse core y target')

        # Ejemplo: reset y haltear la CPU
        core.reset_and_halt()
        print(f"PC inicial: 0x{core.read_core_register('pc'):08X}")

        # Ejemplo: leer memoria
        valor = core.read_memory(0x20000000)
        print(f"Valor en 0x20000000: {hex(valor)}")

        # Ejemplo: escribir memoria
        core.write_memory(0x20000000, 0x1234)
        print(f"Escribimos 0x1234 en 0x20000000")
        valor = core.read_memory(0x20000000)
        print(f"Valor en 0x20000000: {hex(valor)}")
        core.resume()
        core.reset()
