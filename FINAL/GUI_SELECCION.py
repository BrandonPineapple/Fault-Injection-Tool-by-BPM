from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QFileDialog, QButtonGroup, QRadioButton, QMessageBox,
    QScrollArea, QWidget, QComboBox
)
from PySide6.QtCore import Qt
from M_configuracion_automatica import MICROCONTROLADORES
import os
from GUI_VENATANA_A import VentanaA
from GUI_VENTANA_B import VentanaB
from GUI_VENTANA_C import VentanaCSV

# ============================================================
#  TEMA OSCURO PROFESIONAL FI-UNAM / NASA STYLE
# ============================================================
def tema_oscuro(widget: QWidget):
    widget.setStyleSheet('''

    QWidget {
        background-color: #0C1016;
        color: #E5E9F0;
        font-family: "Inter", "Segoe UI", Arial;
        font-size: 13px;
    }

    QFrame[section="panel"] {
        background-color: #151A22;
        border: 1px solid #252C37;
        border-radius: 10px;
        padding: 16px 18px;
        margin-bottom: 16px;
    }

    QFrame[section="panel"]:hover {
        border-color: #344154;
        background-color: #181E27;
    }

    QFrame#HeaderPanel {
        background-color: #141923;
        border-radius: 10px;
        border: 1px solid #283347;
        padding: 16px 18px;
        margin-bottom: 16px;
        border-left: 4px solid #0056B3;
    }

    QFrame[section="subpanel"] {
        background-color: #11151C;
        border: 1px solid #232935;
        border-radius: 8px;
        padding: 10px 12px;
        margin-top: 6px;
        margin-bottom: 6px;
    }

    QFrame[section="subpanel"]:hover {
        border-color: #3A4558;
        background-color: #151A22;
    }

    QLabel.h1 {
        font-size: 24px;
        font-weight: 800;
        color: #FFFFFF;
        letter-spacing: 0.3px;
    }

    QLabel.h2 {
        font-size: 16px;
        font-weight: 600;
        color: #D6DCE6;
        margin-bottom: 4px;
    }

    QLabel.h3 {
        font-size: 14px;
        font-weight: 500;
        color: #E1E5EB;
    }

    QLabel.caption {
        font-size: 12px;
        color: #9BA2AE;
    }

    /* =======================================================
       COMBOBOX (CON PLACEHOLDER PROFESIONAL)
    ======================================================= */
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
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 24px;
        border-left: 1px solid #2c3a50;
    }

    QComboBox QAbstractItemView {
        background-color: #1a1d25;
        border: 1px solid #2c3a50;
        selection-background-color: #2563eb;
        selection-color: white;
    }

    /* --- PLACEHOLDER TENUE (lista) --- */
    QComboBox QAbstractItemView::item:disabled {
        color: #6d7480;
        font-style: italic;
    }

    /* --- PLACEHOLDER cuando el combo está cerrado --- */
    QComboBox[placeholder="true"] {
        color: #7d8694;
        font-style: italic;
    }

    QPushButton {
        background-color: #1f2937;
        border: 1px solid #263244;
        border-radius: 10px;
        padding: 10px 14px;
        font-weight: 600;
    }

    QPushButton:hover {
        background-color: #253245;
        border-color: #2c3a50;
    }

    QPushButton:pressed {
        background-color: #1a2433;
    }

    QPushButton.cta {
        background-color: #2563eb;
        border: 1px solid #1e50bb;
        color: white;
    }

    QPushButton.cta:hover {
        background-color: #2b6ef5;
    }

    QPushButton.cta:pressed {
        background-color: #1e55c9;
    }

    QPushButton.sal {
        background-color: #7f1d1d;
        border: 1px solid #991b1b;
        border-radius: 10px;
        padding: 10px 14px;
        font-weight: 600;
        color: #fef2f2;
    }

    QPushButton.sal:hover {
        background-color: #b91c1c;
        border-color: #dc2626;
    }

    QPushButton.sal:pressed {
        background-color: #450a0a;
    }

    QScrollBar:vertical {
        background: #0C1016;
        width: 10px;
        margin: 2px;
    }

    QScrollBar::handle:vertical {
        background-color: #2B323C;
        border-radius: 4px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: #3A4350;
    }

    QFrame#Rule {
        background-color: #252C37;
        min-height: 2px;
        max-height: 2px;
        border-radius: 1px;
    }

    ''')


# ============================================================
#  VENTANA DE CONFIGURACIÓN DE INYECCIÓN
# ============================================================
class InyectorWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configuración de inyección")
        self.setMinimumSize(900, 630)

        tema_oscuro(self)

        self.rutas = {k: None for k in ["elf_flash", "elf_ram", "map_flash", "map_ram"]}
        self.labels_estado = {}
        self.micro_seleccionado = None
        self.modo_seleccionado = None

        # ROOT
        layout_root = QVBoxLayout(self)
        layout_root.setContentsMargins(24, 24, 20, 14)
        layout_root.setSpacing(12)

        # SCROLL
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")
        container = QWidget()
        scroll_layout = QVBoxLayout(container)

        # =====================================================
        # HEADER
        # =====================================================
        panel_title = QFrame()
        panel_title.setObjectName("HeaderPanel")
        lay_title = QVBoxLayout(panel_title)

        title = QLabel("Configuración de Archivos y Tipo de Inyección")
        title.setProperty("class", "h1")

        subtitle = QLabel("Carga los binarios requeridos, selecciona tu MCU y el modo de inyección.")
        subtitle.setProperty("class", "h2")

        lay_title.addWidget(title)
        lay_title.addWidget(subtitle)

        scroll_layout.addWidget(panel_title)

        # =====================================================
        # MCU PANEL (CON PLACEHOLDER)
        # =====================================================
        panel_mcu = QFrame()
        panel_mcu.setProperty("section", "panel")
        lay_mcu = QVBoxLayout(panel_mcu)

        lbl_mcu = QLabel("Microcontrolador")
        lbl_mcu.setProperty("class", "h2")

        combo = QComboBox()
        combo.setFixedWidth(260)

        # ---------- PLACEHOLDER PROFESIONAL ----------
        combo.addItem("— Selecciona un microcontrolador —")
        combo.model().item(0).setEnabled(False)
        combo.setProperty("placeholder", "true")

        # ---------- OPCIONES REALES ----------
        for nombre in MICROCONTROLADORES.keys():
            combo.addItem(nombre)

        combo.currentTextChanged.connect(self._cambiar_mcu)

        desc_mcu = QLabel("• Selecciona el modelo del microcontrolador para esta sesión de inyección.")
        desc_mcu.setProperty("class", "caption")

        lay_mcu.addWidget(lbl_mcu)
        lay_mcu.addWidget(combo)
        lay_mcu.addWidget(desc_mcu)

        scroll_layout.addWidget(panel_mcu)

        # (todo lo demás queda igual)
        # -------------------------------------------------------
        # ARCHIVOS, TIPOS DE INYECCIÓN, VALIDACIÓN, ETC.
        # -------------------------------------------------------

        # =====================================================
        # PANEL ARCHIVOS
        # =====================================================
        panel_arch = QFrame()
        panel_arch.setProperty("section", "panel")
        lay_arch = QVBoxLayout(panel_arch)

        lbl_arch = QLabel("Archivos requeridos")
        lbl_arch.setProperty("class", "h2")
        lay_arch.addWidget(lbl_arch)

        def fila(nombre, clave, desc_txt):
            wrapper = QFrame()
            wrapper.setProperty("section", "subpanel")
            lay = QVBoxLayout(wrapper)

            fila_h = QHBoxLayout()

            estado = QLabel()
            estado.setFixedWidth(20)
            estado.setAlignment(Qt.AlignCenter)
            self.labels_estado[clave] = estado
            self._actualizar_icono(clave)

            lbl = QLabel(nombre)
            lbl.setProperty("class", "h3")

            lbl_path = QLabel("Ningún archivo seleccionado")
            lbl_path.setMinimumWidth(340)
            lbl_path.setWordWrap(True)
            lbl_path.setProperty("class", "caption")

            btn = QPushButton("Seleccionar archivo")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedWidth(160)

            def seleccionar():
                filtros = "Archivos ELF/MAP/BIN (*.elf *.map *.bin)"
                ruta, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo", "", filtros)
                if ruta:
                    self.rutas[clave] = ruta
                    lbl_path.setText(ruta)
                    self._actualizar_icono(clave)

            btn.clicked.connect(seleccionar)

            fila_h.addWidget(estado)
            fila_h.addWidget(lbl)
            fila_h.addStretch()
            fila_h.addWidget(lbl_path)
            fila_h.addWidget(btn)

            desc = QLabel("• " + desc_txt)
            desc.setProperty("class", "caption")

            lay.addLayout(fila_h)
            lay.addWidget(desc)

            return wrapper

        lay_arch.addWidget(fila("ELF (FLASH)", "elf_flash",
                                "Ejecutable final almacenado en memoria FLASH."))

        lay_arch.addWidget(fila("ELF (RAM)", "elf_ram",
                                "Ejecutable para carga y ejecución desde RAM."))

        lay_arch.addWidget(fila("MAP (FLASH)", "map_flash",
                                "Mapa de memoria del binario almacenado en FLASH."))

        lay_arch.addWidget(fila("MAP (RAM)", "map_ram",
                                "Mapa de memoria del binario cargado en RAM."))

        scroll_layout.addWidget(panel_arch)

        # =====================================================
        # PANEL TIPO INYECCIÓN
        # =====================================================
        panel_tipo = QFrame()
        panel_tipo.setProperty("section", "panel")
        lay_tipo = QVBoxLayout(panel_tipo)

        lbl_tipo = QLabel("Seleccione el modo de operación")
        lbl_tipo.setProperty("class", "h2")

        group = QButtonGroup(self)

        r1 = QRadioButton("Generación Automática")
        r1.setProperty("class", "h3")

        r2 = QRadioButton("Lista Definida por el Usuario")
        r2.setProperty("class", "h3")

        r3 = QRadioButton('Reproducir desde CSV')
        r3.setProperty('class', 'h3')

        group.addButton(r1)
        group.addButton(r2)
        group.addButton(r3)

        lay_tipo.addWidget(lbl_tipo)
        lay_tipo.addWidget(r1)
        lay_tipo.addWidget(r2)
        lay_tipo.addWidget(r3)

        desc_scroll = QScrollArea()
        desc_scroll.setWidgetResizable(True)
        desc_scroll.setMinimumHeight(120)
        desc_scroll.setMaximumHeight(140)
        desc_scroll.setStyleSheet("border:1px solid #252C37; border-radius:6px;")

        desc_frame = QFrame()
        desc_layout = QVBoxLayout(desc_frame)

        self.descripcion = QLabel("Selecciona un modo de operación para ver la descripción detallada.")
        self.descripcion.setWordWrap(True)
        self.descripcion.setProperty("class", "caption")

        desc_layout.addWidget(self.descripcion)
        desc_scroll.setWidget(desc_frame)

        lay_tipo.addWidget(desc_scroll)

        r1.toggled.connect(lambda s: self._cambiar_descripcion(1, s))
        r2.toggled.connect(lambda s: self._cambiar_descripcion(2, s))
        r3.toggled.connect(lambda s: self._cambiar_descripcion(3, s))

        scroll_layout.addWidget(panel_tipo)



        scroll.setWidget(container)
        layout_root.addWidget(scroll)

        # =====================================================
        # BOTONES FINALES
        # =====================================================
        botones = QHBoxLayout()
        botones.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setProperty("class", "sal")
        btn_cancel.clicked.connect(self.close)

        btn_ok = QPushButton("Continuar")
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setProperty("class", "cta")
        btn_ok.clicked.connect(self._continuar)

        botones.addWidget(btn_cancel)
        botones.addWidget(btn_ok)
        layout_root.addLayout(botones)

    # ============================================================
    #  CALLBACKS
    # ============================================================
    def _cambiar_mcu(self, nombre):
        if nombre.startswith("—"):
            self.micro_seleccionado = None
        else:
            self.micro_seleccionado = nombre

    def _actualizar_icono(self, clave):
        ruta = self.rutas[clave]
        lbl = self.labels_estado[clave]

        if ruta and os.path.exists(ruta):
            lbl.setText("<span style='font-size:14px;color:#5CFF5C;'>●</span>")
        else:
            lbl.setText("<span style='font-size:14px;color:#FF5C5C;'>●</span>")

    def _cambiar_descripcion(self, modo, activo):
        if not activo:
            return

        if modo == 1:
            # MODO A: GENERACIÓN AUTOMÁTICA
            txt = (
                "<b>Generación Automática:</b><br>"
                "• Genera una lista completa de fallas usando el ELF, MAP y registros del MCU.<br>"
                "• Direcciones válidas detectadas automáticamente.<br>"
                "• Ideal para campañas grandes y pruebas masivas.<br>"
                "<span style='color:#8f96a3;'>Usado para obtener cobertura amplia del sistema.</span>"
            )

        elif modo == 2:
            # MODO B: LISTA DEFINIDA POR EL USUARIO
            txt = (
                "<b>Lista Definida por el Usuario:</b><br>"
                "• El usuario define manualmente cada falla a inyectar.<br>"
                "• Reglas estrictas: direcciones de 8 bytes y máscaras de 1 bit.<br>"
                "• Se genera automáticamente el archivo <i>LISTA_INYECCION_USUARIO.csv</i>.<br>"
                "<span style='color:#8f96a3;'>Ideal para análisis dirigidos y experimentos controlados.</span>"
            )

        elif modo == 3:
            # MODO C: REPRODUCCIÓN DESDE CSV EXISTENTE
            txt = (
                "<b>Reproducir desde CSV:</b><br>"
                "• Permite cargar un archivo CSV externo con una lista ya definida de fallas.<br>"
                "• Perfecto para repetir campañas previas o comparar resultados.<br>"
                "• Compatible con listas generadas en los modos Automático (A) o Usuario (B).<br>"
                "<span style='color:#8f96a3;'>Útil para reproducibilidad científica y validación.</span>"
            )

        else:
            txt = "Selecciona un modo para ver la descripción."

        self.descripcion.setText(txt)
        self.modo_seleccionado = modo

    def _continuar(self):
        # 1) Validaciones básicas
        if self.micro_seleccionado is None:
            QMessageBox.warning(self, "Microcontrolador no seleccionado",
                                "Debes seleccionar un microcontrolador.")
            return

        if any(v is None for v in self.rutas.values()):
            QMessageBox.warning(self, "Faltan archivos",
                                "Debes cargar los 4 archivos antes de continuar.")
            return

        if self.modo_seleccionado is None:
            QMessageBox.warning(self, "Modo no seleccionado",
                                "Selecciona un tipo de inyección.")
            return

        # 2) Si el modo es 'Generación Automática' → abrir VentanaA
        if self.modo_seleccionado == 1:
            # Abrimos la ventana del modo automático
            ventana_auto = VentanaA(self.micro_seleccionado, self.rutas)

            # Opciones:
            # a) Ocultar esta ventana mientras se configura la automática:
            self.hide()
            ventana_auto.exec()  # modal, espera a que termine
            self.show()
            # b) Si prefieres cerrar del todo esta ventana después:
            # ventana_auto.exec()
            # self.accept()
            return

        if self.modo_seleccionado == 2:
            ventana_usuario = VentanaB(
                micro=self.micro_seleccionado,
                rutas=self.rutas
            )

            self.hide()
            ventana_usuario.exec()
            self.show()
            return

        # -------------------------------
        # MODO 3 – Reproducir desde CSV
        # -------------------------------
        if self.modo_seleccionado == 3:
            ventana_csv = VentanaCSV(
                self.micro_seleccionado,
                self.rutas
            )

            self.hide()
            ventana_csv.exec()
            self.show()
            return

        # 3) Si el modo NO es automático, seguimos el flujo normal
        self.accept()

