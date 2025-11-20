from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QRadioButton, QButtonGroup,
    QMessageBox, QApplication, QWidget,
    QHBoxLayout, QFrame, QSpinBox, QGraphicsDropShadowEffect,
    QProgressDialog
)
from PySide6.QtCore import Qt
from pathlib import Path
from M_acomplado2 import ACOPLADO
from cmsis_svd.parser import SVDParser
from GUI_TEMA import tema_oscuro


# =====================================================
#   LECTOR DE PERIFÉRICOS DESDE SVD
# =====================================================
class ListaRegistros:
    def __init__(self, micro: str, svd_repo: Path):
        self.micro = micro
        self.svd_repo = svd_repo

        self.micro_svds = {
            "stm32f407g-disc1": "STM32F407.svd",
            "nucleo-f446re": "STM32F446.svd"
        }

    def find_svd_path(self) -> Path:
        svd_file = self.micro_svds.get(self.micro)
        if not svd_file:
            raise ValueError(f"❌ Micro {self.micro} no definido")

        matches = list(self.svd_repo.rglob(svd_file))
        if not matches:
            raise FileNotFoundError(f"❌ No se encontró {svd_file}")

        return matches[0]

    def obtener_perifericos_completos(self):
        svd_path = self.find_svd_path()
        parser = SVDParser.for_xml_file(svd_path)
        device = parser.get_device()

        display, siglas = [], []

        for p in device.peripherals:
            if not p.name:
                continue
            nombre = p.name
            descripcion = getattr(p, "description", "Sin descripción")
            display.append(f"{nombre} – {descripcion}")
            siglas.append(nombre)

        pares = list(zip(display, siglas))
        pares.sort(key=lambda x: x[0])

        display = [d for d, _ in pares]
        siglas = [s for _, s in pares]
        return display, siglas


# =====================================================
#   VENTANA CONFIGURACIÓN AUTOMÁTICA
# =====================================================
class VentanaA(QDialog):
    def __init__(self, micro, rutas_dict):
        super().__init__()
        self.setWindowTitle("Modo Automático – Configuración")
        self.setMinimumWidth(620)

        tema_oscuro(self)
        self._estilos()

        self.micro = micro
        self.rutas = rutas_dict

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # =====================================================
        # PANEL ESTADO DEL SISTEMA
        # =====================================================
        card_estado = self._card_translucido("Estado del sistema")

        lbl_estado = QLabel(
            f"<b>Microcontrolador:</b> {self.micro}<br>"
            f"<b>ELF Flash:</b> {Path(self.rutas['elf_flash']).name}<br>"
            f"<b>MAP Flash:</b> {Path(self.rutas['map_flash']).name}<br>"
            f"<b>ELF RAM:</b> {Path(self.rutas['elf_ram']).name}<br>"
            f"<b>MAP RAM:</b> {Path(self.rutas['map_ram']).name}"
        )
        lbl_estado.setProperty("class", "estado")
        lbl_estado.setWordWrap(True)

        card_estado.layout().addWidget(lbl_estado)
        layout.addWidget(card_estado)
        self._sombras(card_estado)

        # =====================================================
        # NÚMERO DE FALLAS
        # =====================================================
        card_fallas = self._card("Número de fallas a ejecutar")
        self.spin_fallas = QSpinBox()
        self.spin_fallas.setRange(1, 10_000_000)
        self.spin_fallas.setFixedWidth(120)
        card_fallas.layout().addWidget(self.spin_fallas)
        layout.addWidget(card_fallas)
        self._sombras(card_fallas)

        # =====================================================
        # UBICACIÓN + DESCRIPCIÓN
        # =====================================================
        card_ubi = self._card("Ubicación de la inyección")

        radios_layout = QVBoxLayout()
        self.radio_flash = QRadioButton("FLASH")
        self.radio_ram = QRadioButton("RAM")
        self.radio_reg = QRadioButton("REGISTROS")
        self.radio_ram.setChecked(True)

        grupo = QButtonGroup(self)
        for r in (self.radio_flash, self.radio_ram, self.radio_reg):
            grupo.addButton(r)
            radios_layout.addWidget(r)

        cont = QWidget()
        cont.setLayout(radios_layout)
        card_ubi.layout().addWidget(cont)

        self.label_desc = QLabel("")
        self.label_desc.setProperty("class", "desc")
        self.label_desc.setWordWrap(True)
        card_ubi.layout().addWidget(self.label_desc)

        layout.addWidget(card_ubi)
        self._sombras(card_ubi)

        self.radio_flash.toggled.connect(self._actualizar_descripcion)
        self.radio_ram.toggled.connect(self._actualizar_descripcion)
        self.radio_reg.toggled.connect(self._actualizar_descripcion)

        # =====================================================
        # TIPO DE FALLA
        # =====================================================
        card_tipo = self._card("Tipo de falla")
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["bitflip", "stuck-at-0", "stuck-at-1", "todos"])
        self.combo_tipo.setMinimumWidth(260)
        card_tipo.layout().addWidget(self.combo_tipo)
        layout.addWidget(card_tipo)
        self._sombras(card_tipo)

        # =====================================================
        # PERIFÉRICO
        # =====================================================
        self.card_per = self._card("Selecciona el periférico")
        self.combo_periferico = QComboBox()
        self.combo_periferico.setMinimumWidth(430)
        self.card_per.layout().addWidget(self.combo_periferico)
        layout.addWidget(self.card_per)
        self._sombras(self.card_per)

        svd_repo = Path(__file__).resolve().parent / "cmsis-svd-data" / "data"
        analizador = ListaRegistros(self.micro, svd_repo)
        self.display_list, self.siglas_list = analizador.obtener_perifericos_completos()

        self.combo_periferico.addItems(self.display_list)
        self.selected_acronym = self.siglas_list[0]
        self.combo_periferico.currentIndexChanged.connect(self._update_sel)

        self.card_per.hide()
        self._actualizar_descripcion()

        # =====================================================
        # BOTONES
        # =====================================================
        botones = QHBoxLayout()
        botones.setSpacing(12)

        btn_back = QPushButton("Atrás")
        btn_back.setCursor(Qt.PointingHandCursor)
        btn_back.setProperty("class", "sal")
        btn_back.clicked.connect(self.close)

        btn_run = QPushButton("Ejecutar campaña")
        btn_run.setCursor(Qt.PointingHandCursor)
        btn_run.setProperty("class", "cta")
        btn_run.clicked.connect(self._run)

        botones.addWidget(btn_back)
        botones.addWidget(btn_run)
        layout.addLayout(botones)

    # =====================================================
    #   CARDS
    # =====================================================
    def _card(self, titulo):
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setProperty("class", "Card")

        layout = QVBoxLayout(card)
        layout.setSpacing(6)
        layout.setContentsMargins(14, 12, 14, 12)

        lbl = QLabel(titulo)
        lbl.setProperty("class", "h2")
        layout.addWidget(lbl)

        return card

    def _card_translucido(self, titulo):
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setProperty("class", "CardTrans")

        layout = QVBoxLayout(card)
        layout.setSpacing(6)
        layout.setContentsMargins(14, 12, 14, 12)

        lbl = QLabel(titulo)
        lbl.setProperty("class", "h2")
        layout.addWidget(lbl)

        return card

    # =====================================================
    def _sombras(self, widget):
        sombra = QGraphicsDropShadowEffect()
        sombra.setBlurRadius(16)
        sombra.setXOffset(0)
        sombra.setYOffset(2)
        sombra.setColor(Qt.black)
        widget.setGraphicsEffect(sombra)

    # =====================================================
    # ESTILO GENERAL + FIX DEL COMBOBOX
    # =====================================================
    def _estilos(self):
        css = """

        /* --------- CARDS ----------- */
        QFrame[class="Card"] {
            background-color: #1A1E27;
            border: 1px solid #2C3340;
            border-radius: 10px;
        }

        /* Transparente tipo "información no editable" */
        QFrame[class="CardTrans"] {
            background-color: rgba(26, 30, 39, 0.45);
            border: 1px solid #2C3340;
            border-radius: 10px;
        }

        QLabel[class="h2"] {
            font-size: 15px;
            font-weight: 600;
            color: #E3E8F0;
            margin-bottom: 3px;
        }

        QLabel[class="estado"] {
            font-size: 12px;
            color: #B8C0CC;
        }

        QLabel[class="desc"] {
            font-size: 12px;
            color: #9CA7B5;
        }

        /* ===============================
               COMBOBOX PREMIUM
        =============================== */
        QComboBox {
            background-color: #1f2937;
            border: 1px solid #2c3a50;
            border-radius: 8px;
            padding: 6px 30px 6px 12px;
            color: #e6e6e6;
            font-weight: 500;
        }

        QComboBox:hover {
            background-color: #253245;
            border-color: #3a4b63;
        }

        QComboBox::drop-down {
            border: none;
            width: 26px;
            border-left: 1px solid #2c3a50;
        }

        QComboBox QAbstractItemView {
            background-color: #11151C;
            border: 1px solid #2c3a50;
            padding: 4px;
            outline: none;
            selection-background-color: #2563eb;
            selection-color: white;
        }

        QScrollBar:vertical {
            background: #11151C;
            width: 8px;
        }

        QScrollBar::handle:vertical {
            background-color: #2B323C;
            border-radius: 4px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #3A4350;
        }
        """

        self.setStyleSheet(self.styleSheet() + css)

    # =====================================================
    def _actualizar_descripcion(self):
        if self.radio_flash.isChecked():
            self.card_per.hide()
            self.label_desc.setText(
                "El código ejecutable se carga completamente en RAM. Permite inyectar fallas tanto en el código como en los datos."
            )
        elif self.radio_ram.isChecked():
            self.card_per.hide()
            self.label_desc.setText(
                "Inyecta fallas en variables, buffers y estructuras almacenadas en RAM."
            )
        else:
            self.card_per.show()
            self.label_desc.setText(
                "Inyecta fallas en los registros de configuración del periférico seleccionado."
            )

    def _update_sel(self, index):
        self.selected_acronym = self.siglas_list[index]

    # =====================================================
    #     MÉTODO RUN CON INDICADOR DE PROGRESO
    # =====================================================
    def _run(self):
        numero = self.spin_fallas.value()

        ubicacion = (
            "flash" if self.radio_flash.isChecked()
            else "RAM" if self.radio_ram.isChecked()
            else "Registro"
        )

        tipo = self.combo_tipo.currentText()
        periferico = self.selected_acronym

        acop = ACOPLADO(
            elf_flash=self.rutas["elf_flash"],
            map_flash=self.rutas["map_flash"],
            elf_ram=self.rutas["elf_ram"],
            map_ram=self.rutas["map_ram"],
            microcontrolador=self.micro,
            periferico=periferico,
            numero_fallas=numero,
            ubicacion=ubicacion,
            tipo_falla=tipo
        )

        # ---------------------------------------------
        #  INDICADOR DE PROGRESO ELEGANTE
        # ---------------------------------------------
        progreso = QProgressDialog(
            "Ejecutando campaña de inyección...",
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

        if ubicacion == "flash":
            acop.pseudo_flash()
        else:
            acop.pseudo()

        progreso.close()

        QMessageBox.information(self, "Finalizado", "La campaña terminó.")


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    # ---- App ----
    app = QApplication(sys.argv)

    # ---- Micro de prueba ----
    micro = "stm32f407g-disc1"

    # ---- Rutas de prueba (ajusta a tus archivos reales) ----
    rutas_ejemplo = {
        "elf_flash": "/Users/apple/Documents/PruebasST/LED/Debug/LED.elf",
        "map_flash": "/Users/apple/Documents/PruebasST/LED/Debug/LED.map",
        "elf_ram": "/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.elf",
        "map_ram": "/Users/apple/Documents/PruebasST/ScriptPruebas/Debug/ScriptPruebas.map",
    }

    # ---- Crear y mostrar ventana ----
    ventana = VentanaA(micro, rutas_ejemplo)
    ventana.show()

    sys.exit(app.exec())
