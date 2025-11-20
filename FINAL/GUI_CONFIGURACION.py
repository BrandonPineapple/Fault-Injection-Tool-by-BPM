from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QProgressBar, QTextEdit, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, QThread, Signal
from M_configuracion_automatica import MICROCONTROLADORES, Configurador

# =========================
# Tema oscuro
# =========================
def tema_oscuro(widget: QWidget):
    widget.setStyleSheet("""
    QWidget {
        background-color: #0C1016;
        color: #E5E9F0;
        font-family: "Inter", "Segoe UI", Arial;
        font-size: 13px;
    }

    QLabel.h1 {
        font-size: 24px;
        font-weight: 800;
        color: #FFFFFF;
    }
    QLabel.h2 {
        font-size: 16px;
        font-weight: 600;
        color: #D6DCE6;
    }
    QLabel.caption {
        font-size: 12px;
        color: #9BA2AE;
    }

    /* ComboBox */
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
    QComboBox::down-arrow {
        image: url(down-arrow.png);
        width: 12px;
        height: 12px;
    }
    QComboBox QAbstractItemView {
        background-color: #1a1d25;
        border: 1px solid #2c3a50;
        selection-background-color: #2563eb;
        selection-color: white;
    }
    QComboBox QAbstractItemView::item:disabled {
        color: #6d7480;
        font-style: italic;
    }
    QComboBox[placeholder="true"] {
        color: #7d8694;
        font-style: italic;
    }

    /* Botones */
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

    /* ScrollBar vertical */
    QScrollBar:vertical {
        background: #0C1016;
        width: 10px;
        margin: 2px;
        border-radius: 5px;
    }
    QScrollBar::handle:vertical {
        background-color: #2B323C;
        border-radius: 5px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #3A4350;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;
    }

    /* Reglas */
    QFrame#Rule {
        background-color: #252C37;
        min-height: 2px;
        max-height: 2px;
        border-radius: 1px;
    }
    """)


# =========================
# Hilo de instalación
# =========================
class InstalacionThread(QThread):
    progreso = Signal(int)
    mensaje = Signal(str)

    def __init__(self, micro):
        super().__init__()
        self.micro = micro

    def run(self):
        try:
            configurador = Configurador(self.micro)

            # Verificar Git
            self.mensaje.emit('🔍 Verificando Git...')
            msgs = configurador.verificar_git()
            for i, m in enumerate(msgs):
                self.mensaje.emit(m)
                self.progreso.emit(int((i+1)/len(msgs)*20))

            # Instalar librerías
            self.mensaje.emit('📦 Instalando librerías...')
            msgs = configurador.instalar_librerias()
            for i, m in enumerate(msgs):
                self.mensaje.emit(m)
                self.progreso.emit(20 + int((i+1)/len(msgs)*50))

            # Instalar paquete micro
            self.mensaje.emit('⚙️ Instalando pack del micro...')
            ok, msg = configurador.instalar_paquete_micro()
            self.mensaje.emit(msg)
            self.progreso.emit(80)

            # Clonar CMSIS-SVD
            self.mensaje.emit('📥 Clonando CMSIS-SVD...')
            msgs = configurador.clonar_svd()
            for m in msgs:
                self.mensaje.emit(m)

            self.progreso.emit(100)
            self.mensaje.emit('✅ Instalación completa')
        except Exception as e:
            self.mensaje.emit(f"❌ Error en hilo de instalación: {e}")


# =========================
# Ventana de configuración
# =========================
class ConfigWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Configuración de la herramienta')
        self.setMinimumSize(500, 400)
        tema_oscuro(self)

        layout = QVBoxLayout(self)

        # Label
        layout.addWidget(QLabel('Selecciona el microcontrolador:'))

        # ComboBox con placeholder y cursiva
        self.opciones = QComboBox()
        self.opciones.addItem("— Selecciona un microcontrolador —")
        self.opciones.model().item(0).setEnabled(False)  # Deshabilitado para placeholder
        self.opciones.setCurrentIndex(0)
        self.opciones.setProperty("placeholder", True)  # Para stylesheet
        for micro in MICROCONTROLADORES.keys():
            self.opciones.addItem(micro)
        layout.addWidget(self.opciones)

        # Forzar que el style se aplique
        self.opciones.style().unpolish(self.opciones)
        self.opciones.style().polish(self.opciones)
        self.opciones.update()

        # Botón instalar
        self.btn_instalar = QPushButton('Instalar paquetes y librerías')
        self.btn_instalar.setProperty('class', 'cta')
        self.btn_instalar.clicked.connect(self._instalar)
        layout.addWidget(self.btn_instalar)

        # ProgressBar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        # Consola
        self.consola = QTextEdit()
        self.consola.setReadOnly(True)
        layout.addWidget(self.consola)

        # Botón cerrar
        self.btn_cerrar = QPushButton('Cerrar')
        self.btn_cerrar.setProperty('class', 'sal')
        self.btn_cerrar.clicked.connect(self.close)
        layout.addWidget(self.btn_cerrar)

    # ----------------------
    # Función instalar
    # ----------------------
    def _instalar(self):
        micro = self.opciones.currentText()
        if micro.startswith("—"):
            QMessageBox.warning(
                self,
                "Microcontrolador no seleccionado",
                "Debes seleccionar un microcontrolador antes de continuar."
            )
            return

        # Bloquear botones durante la instalación
        self.btn_cerrar.setEnabled(False)
        self.btn_instalar.setEnabled(False)

        self.thread = InstalacionThread(micro)
        self.thread.progreso.connect(self.progress.setValue)
        self.thread.mensaje.connect(self._imprimir_consola)

        # Al terminar el hilo, desbloquear botones
        self.thread.finished.connect(lambda: self.btn_cerrar.setEnabled(True))
        self.thread.finished.connect(lambda: self.btn_instalar.setEnabled(True))

        self.thread.start()

    def _imprimir_consola(self, msg):
        self.consola.append(msg)
        self.consola.verticalScrollBar().setValue(
            self.consola.verticalScrollBar().maximum()
        )
