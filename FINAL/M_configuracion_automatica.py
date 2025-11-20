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
    'nucleo-f446re': "stm32f446retx"
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
        mensajes = []
        msg = "🔍 Verificando Git..."
        print(msg)
        mensajes.append(msg)

        if not self.ejecutar("git --version", mostrar_salida=False):
            msg = "⚠️ Git no está instalado. Instalando..."
            print(msg)
            mensajes.append(msg)
            sistema = platform.system()

            if sistema == "Windows":
                self.ejecutar("winget install --id Git.Git -e --source winget")
            elif sistema == "Darwin":
                self.ejecutar("xcode-select --install")
            else:
                msg = "❌ Este script solo es compatible con Windows y macOS."
                print(msg)
                mensajes.append(msg)
                sys.exit(1)
        else:
            msg = "✅ Git está instalado.\n"
            print(msg)
            mensajes.append(msg)

        return mensajes

    # -------------------------------------------------
    # Instalar librerías de Python
    # -------------------------------------------------
    def instalar_librerias(self):
        mensajes = []
        print("📦 Instalando librerías generales...")
        mensajes.append("📦 Instalando librerías...")
        for libreria in LIBRERIAS:
            comando = f"{sys.executable} -m pip install --upgrade {libreria}"
            if self.ejecutar(comando):
                print(f"✅ {libreria} instalada o actualizada")
                mensajes.append(f"✅ {libreria} instalada o actualizada")
            else:
                print(f"❌ Error al instalar {libreria}")
                mensajes.append(f"❌ Error al instalar {libreria}")
        return mensajes


    # -------------------------------------------------
    # Instalar paquete pyOCD
    # -------------------------------------------------
    def instalar_paquete_micro(self):
        """Instala el pack pyOCD correspondiente al microcontrolador."""
        if not self.micro:
            print("❌ Microcontrolador no definido.")
            return False, "❌ Microcontrolador no definido."

        try:
            print(f"\n⚙️ Instalando soporte para {self.micro_nombre} ({self.micro})...")
            self.ejecutar(f"{sys.executable} -m pyocd pack update")
            self.ejecutar(f"{sys.executable} -m pyocd pack install {self.micro}")
            print(f"✅ Pack {self.micro} instalado o ya existente.\n")
            return True, f"✅ Pack {self.micro} instalado."
        except Exception as e:
            return False, f"❌ Error instalando pack: {e}"

    # -------------------------------------------------
    # Clonar CMSIS-SVD
    # -------------------------------------------------
    def clonar_svd(self):
        """Clona el repositorio CMSIS-SVD si no existe."""
        mensajes = []

        if not self.svd_repo.exists():
            msg = "📥 Clonando repositorio CMSIS-SVD..."
            print(msg)
            mensajes.append(msg)
            if self.ejecutar("git clone https://github.com/cmsis-svd/cmsis-svd-data.git"):
                msg = "✅ Repositorio clonado correctamente.\n"
                print(msg)
                mensajes.append(msg)
            else:
                msg = "❌ Error al clonar el repositorio.\n"
                print(msg)
                mensajes.append(msg)
        else:
            msg = "ℹ️ Repositorio CMSIS-SVD ya existe, omitiendo clonación.\n"
            print(msg)
            mensajes.append(msg)

        return mensajes

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

#    print("\n🎉 Configuración completa.")

