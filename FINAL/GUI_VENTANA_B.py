from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame,
    QComboBox, QLineEdit, QMessageBox, QApplication, QSpinBox, QListWidget,
    QGraphicsDropShadowEffect, QProgressDialog
)
from PySide6.QtCore import Qt
from pathlib import Path
import csv
import sys

from GUI_TEMA import tema_oscuro
from M_acomplado2 import ACOPLADO


# ============================================================
#  VALIDADOR PARA DIRECCIONES DE 8 BYTES EXACTO
# ============================================================
def validar_direccion_8bytes(texto: str):
    if not texto.startswith("0x"):
        texto = "0x" + texto

    try:
        numero = int(texto, 16)
        direccion = f"0x{numero:08X}"
        if len(direccion) != 10:
            return None
        return direccion
    except:
        return None


# ============================================================
#  VENTANA MODO USUARIO – CAMPAÑA MANUAL
# ============================================================
class VentanaB(QDialog):

    def __init__(self, micro, rutas):
        super().__init__()

        # ---- DATOS DESDE LA GUI PRINCIPAL ----
        self.micro = micro
        self.elf_flash = rutas.get("elf_flash")
        self.map_flash = rutas.get("map_flash")
        self.elf_ram = rutas.get("elf_ram")
        self.map_ram = rutas.get("map_ram")

        # ---- COUNTER PARA SEPARADORES ----
        self.contador_campanas = 0

        # ---- CONFIG GENERAL ----
        self.setWindowTitle("Modo Usuario – Generación Manual de Fallas")
        self.setMinimumWidth(650)

        tema_oscuro(self)
        self._estilos()

        self.lista_fallas = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ====================================================
        # CARD – Estado del sistema (DISEÑO PREMIUM)
        # ====================================================
        card_estado = self._card_translucido("Estado del sistema")

        lbl_estado = QLabel(
            f"<b>Microcontrolador:</b> {self.micro}<br>"
            f"<b>ELF Flash:</b> {Path(self.elf_flash).name}<br>"
            f"<b>MAP Flash:</b> {Path(self.map_flash).name}<br>"
            f"<b>ELF RAM:</b> {Path(self.elf_ram).name}<br>"
            f"<b>MAP RAM:</b> {Path(self.map_ram).name}"
        )
        lbl_estado.setProperty("class", "estado")
        lbl_estado.setWordWrap(True)

        card_estado.layout().addWidget(lbl_estado)
        layout.addWidget(card_estado)
        self._sombras(card_estado)

        # ====================================================
        # CARD – Información general
        # ====================================================
        card_info = self._card("Configuración general")
        lay = card_info.layout()

        fila = QHBoxLayout()
        lay.addLayout(fila)

        fila.addWidget(QLabel("Número máximo de fallas:"))
        self.spin_num = QSpinBox()
        self.spin_num.setRange(1, 999999)
        self.spin_num.setFixedWidth(120)
        fila.addWidget(self.spin_num)

        layout.addWidget(card_info)
        self._sombras(card_info)

        # ====================================================
        # CARD – Fallas individuales
        # ====================================================
        card_fallas = self._card("Configuración de cada falla")
        layf = card_fallas.layout()

        # UBICACIÓN
        fila1 = QHBoxLayout()
        layf.addLayout(fila1)
        fila1.addWidget(QLabel("Ubicación:"))
        self.combo_ubi = QComboBox()
        self.combo_ubi.addItems(["RAM", "FLASH", "REGISTRO"])
        self.combo_ubi.setMinimumWidth(170)
        fila1.addWidget(self.combo_ubi)

        # TIPO
        fila2 = QHBoxLayout()
        layf.addLayout(fila2)
        fila2.addWidget(QLabel("Tipo de falla:"))
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["bitflip", "stuck-at-0", "stuck-at-1"])
        self.combo_tipo.setMinimumWidth(170)
        fila2.addWidget(self.combo_tipo)

        # DIRECCIÓN STOP
        fila3 = QHBoxLayout()
        layf.addLayout(fila3)
        fila3.addWidget(QLabel("Dirección STOP (8 bytes):"))
        self.in_stop = QLineEdit()
        self.in_stop.setPlaceholderText("Ej: 0x20001000")
        fila3.addWidget(self.in_stop)

        # DIRECCIÓN INYECCIÓN
        fila4 = QHBoxLayout()
        layf.addLayout(fila4)
        fila4.addWidget(QLabel("Dirección INYECCIÓN (8 bytes):"))
        self.in_iny = QLineEdit()
        self.in_iny.setPlaceholderText("Ej: 0x20002000")
        fila4.addWidget(self.in_iny)

        # BIT
        fila5 = QHBoxLayout()
        layf.addLayout(fila5)
        fila5.addWidget(QLabel("Bit (0–31):"))
        self.spin_bit = QSpinBox()
        self.spin_bit.setRange(0, 31)
        self.spin_bit.setFixedWidth(80)
        self.spin_bit.setValue(0)
        fila5.addWidget(self.spin_bit)

        # BOTÓN PARA AGREGAR FALLA
        btn_add = QPushButton("Agregar falla a la lista")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setProperty("class", "cta")
        btn_add.clicked.connect(self._agregar_falla)
        layf.addWidget(btn_add)

        layout.addWidget(card_fallas)
        self._sombras(card_fallas)

        # ====================================================
        # LISTA DE FALLAS
        # ====================================================
        card_lista = self._card_translucido("Fallas agregadas")
        self.lista_widget = QListWidget()
        card_lista.layout().addWidget(self.lista_widget)
        layout.addWidget(card_lista)
        self._sombras(card_lista)

        # ====================================================
        # BOTONES FINALES
        # ====================================================
        botones = QHBoxLayout()

        btn_new = QPushButton("Nueva campaña")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.setProperty("class", "bon")
        btn_new.clicked.connect(self._nueva_campana)

        btn_run = QPushButton("Generar CSV y ejecutar campaña")
        btn_run.setCursor(Qt.PointingHandCursor)
        btn_run.setProperty("class", "cta")
        btn_run.clicked.connect(self._generar_y_ejecutar)

        btn_salir = QPushButton("Atrás")
        btn_salir.setCursor(Qt.PointingHandCursor)
        btn_salir.setProperty("class", "sal")
        btn_salir.clicked.connect(self.close)

        botones.addWidget(btn_new)
        botones.addWidget(btn_run)
        botones.addWidget(btn_salir)

        layout.addLayout(botones)

    # ============================================================
    #   DISEÑO
    # ============================================================
    def _card(self, titulo):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setProperty("class", "Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        lbl = QLabel(titulo)
        lbl.setProperty("class", "h2")
        layout.addWidget(lbl)
        return frame

    def _card_translucido(self, titulo):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setProperty("class", "CardTrans")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        lbl = QLabel(titulo)
        lbl.setProperty("class", "h2")
        layout.addWidget(lbl)
        return frame

    def _sombras(self, widget):
        sombra = QGraphicsDropShadowEffect()
        sombra.setBlurRadius(14)
        sombra.setXOffset(0)
        sombra.setYOffset(2)
        sombra.setColor(Qt.black)
        widget.setGraphicsEffect(sombra)

    def _estilos(self):
        css = """
        QFrame[class="Card"] {
            background-color: #1A1E27;
            border: 1px solid #2C3340;
            border-radius: 10px;
        }
        QFrame[class="CardTrans"] {
            background-color: rgba(26,30,39,0.45);
            border: 1px solid #2C3340;
            border-radius: 10px;
        }
        QLineEdit, QListWidget {
            background-color: #11151C;
            border: 1px solid #2C3340;
            border-radius: 6px;
            color: #EEE;
        }
        QLabel[class="h2"] {
            font-size: 15px;
            font-weight: 600;
            color: #E3E8F0;
        }
        QLabel[class="estado"] {
            font-size: 12px;
            color: #B8C0CC;
        }
        """
        self.setStyleSheet(self.styleSheet() + css)

    # ============================================================
    #   BOTÓN NUEVA CAMPAÑA
    # ============================================================
    def _nueva_campana(self):
        self.lista_fallas.clear()
        self.lista_widget.clear()
        QMessageBox.information(self, "Nueva campaña", "La lista fue limpiada.")

    # ============================================================
    #   AGREGAR FALLA
    # ============================================================
    def _agregar_falla(self):
        max_fallas = self.spin_num.value()
        if len(self.lista_fallas) >= max_fallas:
            QMessageBox.warning(self, "Límite alcanzado",
                                f"Ya tienes las {max_fallas} fallas permitidas.")
            return

        N = len(self.lista_fallas) + 1
        ubic = self.combo_ubi.currentText()
        tipo = self.combo_tipo.currentText()

        stop = validar_direccion_8bytes(self.in_stop.text())
        if stop is None:
            QMessageBox.warning(self, "Error", "Dirección STOP inválida (8 bytes).")
            return

        iny = validar_direccion_8bytes(self.in_iny.text())
        if iny is None:
            QMessageBox.warning(self, "Error", "Dirección INYECCIÓN inválida (8 bytes).")
            return

        bit = self.spin_bit.value()
        mascara = f"0x{1 << bit:08X}"

        falla = {
            "FAULT_ID": N,
            "UBICACION": ubic,
            "TIPO_FALLA": tipo,
            "DIRECCION STOP": stop,
            "DIRECCION INYECCION": iny,
            "MASCARA": mascara,
            "BIT": bit
        }

        self.lista_fallas.append(falla)
        self.lista_widget.addItem(
            f"Falla {N}: {ubic} – {tipo} – STOP={stop} – INY={iny} – MASK={mascara}"
        )

        self.in_stop.clear()
        self.in_iny.clear()
        self.spin_bit.setValue(0)

    # ============================================================
    #  GENERAR CSV + INDICADOR + EJECUTAR CAMPAÑA
    # ============================================================
    def _generar_y_ejecutar(self):
        if not self.lista_fallas:
            QMessageBox.warning(self, "Error", "Debes agregar al menos una falla.")
            return

        nombre_csv = "LISTA_INYECCION_USUARIO.csv"

        # ----------------------------
        # 1) GENERAR CSV
        # ----------------------------
        try:
            with open(nombre_csv, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow([
                    "FAULT_ID", "UBICACION", "TIPO_FALLA",
                    "DIRECCION STOP", "DIRECCION INYECCION",
                    "MASCARA", "BIT"
                ])
                for fila in self.lista_fallas:
                    w.writerow([
                        fila["FAULT_ID"], fila["UBICACION"], fila["TIPO_FALLA"],
                        fila["DIRECCION STOP"], fila["DIRECCION INYECCION"],
                        fila["MASCARA"], fila["BIT"]
                    ])
        except Exception as e:
            QMessageBox.critical(self, "Error",
                                 f"No se pudo escribir el CSV:\n{e}")
            return

        # ----------------------------
        # 2) INDICADOR PREMIUM
        # ----------------------------
        progreso = QProgressDialog(
            "Ejecutando campaña de inyección del usuario...",
            None,
            0, 0,
            self
        )
        progreso.setWindowTitle("Por favor espera")
        progreso.setWindowModality(Qt.ApplicationModal)
        progreso.setCancelButton(None)
        progreso.setMinimumWidth(380)

        progreso.setStyleSheet("""
            QProgressDialog {
                background-color: #1A1E27;
                color: #E3E8F0;
                font-size: 14px;
                border: 1px solid #2C3340;
                border-radius: 8px;
            }
            QProgressBar {
                background-color: #11151C;
                border: 1px solid #2C3340;
                border-radius: 6px;
                height: 12px;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 6px;
            }
        """)

        progreso.show()
        QApplication.processEvents()

        # ----------------------------
        # 3) EJECUTAR CAMPAÑA
        # ----------------------------
        try:
            acop = ACOPLADO(
                elf_flash=self.elf_flash,
                map_flash=self.map_flash,
                elf_ram=self.elf_ram,
                map_ram=self.map_ram,
                microcontrolador=self.micro,
                periferico="GENERAL",
                numero_fallas=len(self.lista_fallas),
                ubicacion="usuario",
                tipo_falla="manual"
            )

            acop.usuario(abrir_gui=True)

        except Exception as e:
            progreso.close()
            QMessageBox.critical(self, "Error campaña",
                                 f"Ocurrió un error ejecutando la campaña:\n{e}")
            return

        progreso.close()

        QMessageBox.information(
            self, "Campaña finalizada",
            "La campaña manual de inyección ha terminado correctamente."
        )

        # ----------------------------
        # 4) AGREGAR SEPARADOR VISUAL
        # ----------------------------
        self.contador_campanas += 1
        sep = f"───── FIN DE CAMPAÑA #{self.contador_campanas} ─────"
        self.lista_widget.addItem(sep)


# ============================================================
#  MAIN DE PRUEBA
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    tema_oscuro(app)

    rutas_demo = {
        "elf_flash": "/Users/apple/Documents/PruebasST/LED/Debug/LED.elf",
        "map_flash": "/Users/apple/Documents/PruebasST/LED/Debug/LED.map",
        "elf_ram": "/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf",
        "map_ram": "/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.map",
    }

    micro_demo = "stm32f407g-disc1"

    ventana = VentanaB(micro_demo, rutas_demo)
    ventana.show()

    sys.exit(app.exec())
