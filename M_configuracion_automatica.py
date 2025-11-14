import os
import platform
import subprocess
import sys
from pathlib import Path

# ---------------------------
# Librerías generales a instalar
# ---------------------------
LIBRERIAS = ['pip', 'pyocd', 'pyelftools', 'cmsis-svd', 'pandas', 'numpy','matplotlib', 'streamlit']

# ---------------------------
# Microcontroladores y sus packs
# ---------------------------
MICROCONTROLADORES = {
    'stm32f407g-disc1': "STM32F407VGTx",
    'msp430fr5994-launchpad': "MSP430FR5994",
    'tiva-c-tm4c1294': "TM4C1294NCPDT"
}


class Configurador:
    def __init__(self, micro_nombre):
        self.micro_nombre = micro_nombre
        self.micro = MICROCONTROLADORES.get(micro_nombre)
        self.svd_repo = Path("cmsis-svd-data")

    # -------------------------------------------------
    # Ejecutor universal (sirve igual en terminal o IDE)
    # -------------------------------------------------
    def ejecutar(self, comando, mostrar_salida=True):
        """Ejecuta un comando en cualquier entorno (terminal o IDE)."""
        try:
            if mostrar_salida:
                subprocess.check_call(comando, shell=True)
            else:
                subprocess.check_output(comando, shell=True)
            return True
        except subprocess.CalledProcessError:
            return False

    # -------------------------------------------------
    # Verificar Git
    # -------------------------------------------------
    def verificar_git(self):
        """Verifica si Git está instalado y lo instala si es necesario."""
        print("🔍 Verificando Git...")
        if not self.ejecutar("git --version", mostrar_salida=False):
            print("⚠️ Git no está instalado. Instalando...")
            sistema = platform.system()

            if sistema == "Windows":
                self.ejecutar("winget install --id Git.Git -e --source winget")
            elif sistema == "Darwin":
                self.ejecutar("xcode-select --install")
            else:
                print("❌ Este script solo es compatible con Windows y macOS.")
                sys.exit(1)
        else:
            print("✅ Git está instalado.\n")

    # -------------------------------------------------
    # Instalar librerías de Python
    # -------------------------------------------------
    def instalar_librerias(self):
        """Instala las librerías necesarias mediante pip."""
        print("📦 Instalando librerías generales...")
        for libreria in LIBRERIAS:
            comando = f"{sys.executable} -m pip install --upgrade {libreria}"
            if self.ejecutar(comando):
                print(f"✅ {libreria} instalada o actualizada")
            else:
                print(f"❌ Error al instalar {libreria}")

    # -------------------------------------------------
    # Instalar paquete pyOCD
    # -------------------------------------------------
    def instalar_paquete_micro(self):
        """Instala el pack pyOCD correspondiente al microcontrolador."""
        if not self.micro:
            print("❌ Microcontrolador no definido.")
            return

        print(f"\n⚙️ Instalando soporte para {self.micro_nombre} ({self.micro})...")
        self.ejecutar(f"{sys.executable} -m pyocd pack update")
        self.ejecutar(f"{sys.executable} -m pyocd pack install {self.micro}")
        print(f"✅ Pack {self.micro} instalado o ya existente.\n")

    # -------------------------------------------------
    # Clonar CMSIS-SVD
    # -------------------------------------------------
    def clonar_svd(self):
        """Clona el repositorio CMSIS-SVD si no existe."""
        if not self.svd_repo.exists():
            print("📥 Clonando repositorio CMSIS-SVD...")
            if self.ejecutar("git clone https://github.com/cmsis-svd/cmsis-svd-data.git"):
                print("✅ Repositorio clonado correctamente.\n")
            else:
                print("❌ Error al clonar el repositorio.\n")
        else:
            print("ℹ️ Repositorio CMSIS-SVD ya existe, omitiendo clonación.\n")


# -------------------------------------------------
# Ejecución principal (idéntico en terminal o IDE)
# -------------------------------------------------
if __name__ == '__main__':
    print("🚀 Iniciando configuración automática...\n")

    micro = 'stm32f407g-disc1'  # 🔧 Cambia el micro si lo deseas
    configurador = Configurador(micro)

    configurador.verificar_git()
    configurador.instalar_librerias()
    configurador.instalar_paquete_micro()
    configurador.clonar_svd()

    print("\n🎉 Configuración completa.")

