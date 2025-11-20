from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame,
    QFileDialog, QListWidget, QMessageBox, QApplication,
    QGraphicsDropShadowEffect, QTableWidget, QTableWidgetItem,
    QProgressDialog, QScrollArea, QWidget
)
from PySide6.QtCore import Qt
from pathlib import Path
import csv
import sys

from GUI_TEMA import tema_oscuro
from M_acomplado2 import ACOPLADO


COLUMNAS_ESPERADAS = [
    "FAULT_ID", "UBICACION", "TIPO_FALLA",
    "DIRECCION STOP", "DIRECCION INYECCION",
    "MASCARA", "BIT"
]


# ============================================================
#  VENTANA SECUNDARIA – TABLA COMPLETA DEL CSV
# ============================================================
class VentanaTablaCSV(QDialog):
    def __init__(self, ruta_csv, micro, rutas, parent=None):
        super().__init__(parent)
        self.ruta_csv = ruta_csv
        self.micro = micro
        self.rutas = rutas

        self.setWindowTitle("Contenido completo del CSV")
        self.setMinimumSize(900, 600)

        tema_oscuro(self)
        self._estilos()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # --------------------------
        # Estado del sistema
        # --------------------------
        card_estado = self._card_translucido("Estado del sistema")
        lbl_estado = QLabel(
            f"<b>Microcontrolador:</b> {self.micro}<br>"
            f"<b>ELF Flash:</b> {Path(self.rutas['elf_flash']).name}<br>"
            f"<b>MAP Flash:</b> {Path(self.rutas['map_flash']).name}<br>"
            f"<b>ELF RAM:</b> {Path(self.rutas['elf_ram']).name}<br>"
            f"<b>MAP RAM:</b> {Path(self.rutas['map_ram']).name}"
        )
        lbl_estado.setWordWrap(True)
        lbl_estado.setProperty("class", "estado")
        card_estado.layout().addWidget(lbl_estado)
        layout.addWidget(card_estado)

        # --------------------------
        # Tabla CSV con scrollbar
        # --------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        cont = QWidget()
        cont_layout = QVBoxLayout(cont)

        self.table = QTableWidget()
        cont_layout.addWidget(self.table)

        scroll.setWidget(cont)
        layout.addWidget(scroll)

        self._cargar_csv()

        # --------------------------
        # Botones
        # --------------------------
        btns = QHBoxLayout()

        btn_back = QPushButton("Atrás")
        btn_back.setCursor(Qt.PointingHandCursor)
        btn_back.setProperty("class", "sal")
        btn_back.clicked.connect(self.close)
        btns.addWidget(btn_back)

        btn_run = QPushButton("Ejecutar campaña")
        btn_run.setCursor(Qt.PointingHandCursor)
        btn_run.setProperty("class", "cta")
        btn_run.clicked.connect(self._ejecutar_campaña)
        btns.addWidget(btn_run)

        layout.addLayout(btns)

    # ============================================================
    def _estilos(self):
        css = """
        QFrame[class="Card"] {
            background-color: #1A1E27;
            border: 1px solid #2C3340;
            border-radius: 10px;
        }
        QFrame[class="CardTrans"] {
            background-color: rgba(26,30,39,0.45);
            border-radius: 10px;
            border: 1px solid #2C3340;
        }
        QLabel[class="h2"] {
            font-size: 15px;
            font-weight: 600;
        }
        QLabel[class="estado"] {
            color: #B8C0CC;
            font-size: 13px;
        }

        /* ===============================
           SCROLLBAR PREMIUM
        =============================== */
        QScrollBar:vertical {
            background: #11151C;
            width: 8px;
            margin: 2px 0 2px 0;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background-color: #2B323C;
            border-radius: 4px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #3A4350;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            background: none;
            height: 0px;
        }
        """
        self.setStyleSheet(self.styleSheet() + css)

    # ============================================================
    def _card_translucido(self, titulo):
        frame = QFrame()
        frame.setProperty("class", "CardTrans")
        frame.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 10, 14, 10)
        lbl = QLabel(titulo)
        lbl.setProperty("class", "h2")
        lay.addWidget(lbl)
        return frame

    # ============================================================
    def _cargar_csv(self):
        with open(self.ruta_csv, "r") as f:
            reader = csv.reader(f)
            datos = list(reader)

        header = datos[0]
        self.table.setColumnCount(len(header))
        self.table.setHorizontalHeaderLabels(header)
        self.table.setRowCount(len(datos) - 1)

        for i, fila in enumerate(datos[1:]):
            for j, valor in enumerate(fila):
                self.table.setItem(i, j, QTableWidgetItem(valor))

    # ============================================================
    def _ejecutar_campaña(self):

        progreso = QProgressDialog(
            "Ejecutando campaña de inyección...",
            None, 0, 0, self
        )
        progreso.setWindowTitle("Por favor espera")
        progreso.setCancelButton(None)
        progreso.setWindowModality(Qt.ApplicationModal)
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

        try:
            acop = ACOPLADO(
                elf_flash=self.rutas["elf_flash"],
                map_flash=self.rutas["map_flash"],
                elf_ram=self.rutas["elf_ram"],
                map_ram=self.rutas["map_ram"],
                microcontrolador=self.micro,
                periferico="GPIOD",
                numero_fallas=1,
                ubicacion="flash",
                tipo_falla="replay"
            )
            acop.reproducir_csv(self.ruta_csv, abrir_gui=True)

            progreso.close()
            QMessageBox.information(self, "Listo", "Campaña completada.")

        except Exception as e:
            progreso.close()
            QMessageBox.critical(self, "Error", str(e))


# ============================================================
#  VENTANA PRINCIPAL – REPRODUCCIÓN CSV
# ============================================================
class VentanaCSV(QDialog):
    def __init__(self, micro, rutas):
        super().__init__()
        self.setWindowTitle("Reproducir campaña desde CSV")
        self.setMinimumWidth(750)

        self.micro = micro
        self.rutas = rutas
        self.ruta_actual_csv = None

        tema_oscuro(self)
        self._estilos()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # --------------------------
        # Estado del sistema
        # --------------------------
        card_estado = self._card_translucido("Estado del sistema")
        lbl_estado = QLabel(
            f"<b>Microcontrolador:</b> {self.micro}<br>"
            f"<b>ELF Flash:</b> {Path(self.rutas['elf_flash']).name}<br>"
            f"<b>MAP Flash:</b> {Path(self.rutas['map_flash']).name}<br>"
            f"<b>ELF RAM:</b> {Path(self.rutas['elf_ram']).name}<br>"
            f"<b>MAP RAM:</b> {Path(self.rutas['map_ram']).name}"
        )
        lbl_estado.setWordWrap(True)
        lbl_estado.setProperty("class", "estado")

        card_estado.layout().addWidget(lbl_estado)
        layout.addWidget(card_estado)

        # --------------------------
        # Selección CSV
        # --------------------------
        card_sel = self._card("Seleccionar archivo CSV")
        btn = QPushButton("Seleccionar archivo…")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setProperty("class", "bon")
        btn.clicked.connect(self._seleccionar_archivo)
        card_sel.layout().addWidget(btn)
        layout.addWidget(card_sel)

        # --------------------------
        # Vista rápida con ScrollArea PREMIUM
        # --------------------------
        card_lista = self._card_translucido("Vista rápida del CSV")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        cont = QWidget()
        cont_layout = QVBoxLayout(cont)

        self.lista_widget = QListWidget()
        cont_layout.addWidget(self.lista_widget)

        scroll.setWidget(cont)
        card_lista.layout().addWidget(scroll)

        layout.addWidget(card_lista)

        # --------------------------
        # Botones inferiores
        # --------------------------
        btns = QHBoxLayout()

        self.btn_ver_tabla = QPushButton("Ver tabla completa")
        self.btn_ver_tabla.setCursor(Qt.PointingHandCursor)
        self.btn_ver_tabla.setProperty("class", "bon")
        self.btn_ver_tabla.setEnabled(False)
        self.btn_ver_tabla.clicked.connect(self._abrir_tabla)

        self.btn_ejecutar = QPushButton("Ejecutar campaña")
        self.btn_ejecutar.setCursor(Qt.PointingHandCursor)
        self.btn_ejecutar.setProperty("class", "cta")
        self.btn_ejecutar.setEnabled(False)
        self.btn_ejecutar.clicked.connect(self._ejecutar_directo)

        btn_back = QPushButton("Atrás")
        btn_back.setCursor(Qt.PointingHandCursor)
        btn_back.setProperty("class", "sal")
        btn_back.clicked.connect(self.close)

        btns.addWidget(self.btn_ver_tabla)
        btns.addWidget(self.btn_ejecutar)
        btns.addWidget(btn_back)
        layout.addLayout(btns)

    # ============================================================
    def _estilos(self):
        css = """
        QFrame[class="Card"] {
            background-color: #1A1E27;
            border: 1px solid #2C3340;
            border-radius: 10px;
        }
        QFrame[class="CardTrans"] {
            background-color: rgba(26,30,39,0.45);
            border-radius: 10px;
            border: 1px solid #2C3340;
        }
        QLabel[class="h2"] {
            font-size: 15px;
            font-weight: 600;
        }
        QLabel[class="estado"] {
            color: #B8C0CC;
            font-size: 13px;
        }
        QListWidget {
            background-color: #11151C;
            border: 1px solid #2C3340;
            border-radius: 8px;
            color: white;
        }

        /* ===============================
           SCROLLBAR PREMIUM
        =============================== */
        QScrollBar:vertical {
            background: #11151C;
            width: 8px;
            margin: 2px 0 2px 0;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background-color: #2B323C;
            border-radius: 4px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #3A4350;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            background: none;
            height: 0px;
        }
        """
        self.setStyleSheet(self.styleSheet() + css)

    # ============================================================
    def _card(self, titulo):
        frame = QFrame()
        frame.setProperty("class", "Card")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lbl = QLabel(titulo)
        lbl.setProperty("class", "h2")
        lay.addWidget(lbl)
        return frame

    def _card_translucido(self, titulo):
        frame = QFrame()
        frame.setProperty("class", "CardTrans")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lbl = QLabel(titulo)
        lbl.setProperty("class", "h2")
        lay.addWidget(lbl)
        return frame

    # ============================================================
    def _seleccionar_archivo(self):
        archivo, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo CSV",
            str(Path.home()), "CSV (*.csv)"
        )
        if not archivo:
            return

        try:
            with open(archivo, "r") as f:
                reader = csv.DictReader(f)

                if reader.fieldnames != COLUMNAS_ESPERADAS:
                    QMessageBox.warning(self, "Formato incorrecto",
                                        "El CSV no coincide con el formato esperado.")
                    return

                self.lista_widget.clear()
                for fila in reader:
                    self.lista_widget.addItem(
                        f"ID {fila['FAULT_ID']} | {fila['UBICACION']} | "
                        f"{fila['TIPO_FALLA']} | STOP={fila['DIRECCION STOP']} | "
                        f"INY={fila['DIRECCION INYECCION']} | MASK={fila['MASCARA']}"
                    )

                self.ruta_actual_csv = archivo
                self.btn_ver_tabla.setEnabled(True)
                self.btn_ejecutar.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Error al leer CSV", str(e))

    # ============================================================
    def _abrir_tabla(self):
        ventana = VentanaTablaCSV(
            self.ruta_actual_csv, self.micro, self.rutas, self
        )
        ventana.exec()

    # ============================================================
    def _ejecutar_directo(self):

        progreso = QProgressDialog(
            "Ejecutando campaña de inyección...",
            None, 0, 0, self
        )
        progreso.setWindowTitle("Por favor espera")
        progreso.setCancelButton(None)
        progreso.setWindowModality(Qt.ApplicationModal)
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

        try:
            acop = ACOPLADO(
                elf_flash=self.rutas["elf_flash"],
                map_flash=self.rutas["map_flash"],
                elf_ram=self.rutas["elf_ram"],
                map_ram=self.rutas["map_ram"],
                microcontrolador=self.micro,
                periferico="GPIOD",
                numero_fallas=1,
                ubicacion="flash",
                tipo_falla="replay"
            )

            acop.reproducir_csv(self.ruta_actual_csv, abrir_gui=True)

            progreso.close()
            QMessageBox.information(self, "Finalizado",
                                    "La campaña se completó correctamente.")

        except Exception as e:
            progreso.close()
            QMessageBox.critical(self, "Error durante ejecución", str(e))


# ============================================================
# MAIN DE PRUEBA
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

    ventana = VentanaCSV(micro_demo, rutas_demo)
    ventana.show()

    sys.exit(app.exec())
