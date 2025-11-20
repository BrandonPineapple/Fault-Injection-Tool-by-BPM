# Librerías principales
import os.path
import sys
import GUI_CONFIGURACION
from GUI_SELECCION import InyectorWindow

from PySide6.QtGui import QPixmap, Qt, QAction, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy, QSpacerItem,
    QMessageBox, QGraphicsOpacityEffect
)


# Nombre de variables
TITULO_GUI = 'Herramienta de inyección de fallas para microcontroladores'
SUBTITULO_GUI = 'Tesis FI-UNAM'
VERSION_GUI = 'vo.1'
NOMBRE_GUI = 'Brandon Martínez Piña'
LOGO = 'LIESE.jpg'


# Tema oscuro aplicado al widget raíz
def tema_oscuro(widget: QWidget):
    widget.setStyleSheet('''

    QWidget {
        background-color: #0f1115;
        color: #e6e6e6;
        font-family: "Inter", 'Segoe UI', Arial, sans-serif; 
    }

    QFrame#Card {
        background-color: #151922;
        border: 1px solid #1f2430;
        border-radius: 16px;
    }

    QLabel.h1 {
        font-size: 24px; 
        font-weight: 800; 
        color: #f3f4f6;
    }

    QLabel.h2 {
        font-size: 14px; 
        color: #aab0bb;
    }

    QLabel.caption {
        font-size: 11px;
        color: #8c92a1;
    }

    QLabel.h3 {
        font-size: 12px;
        color: #b0b3b8;
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

    QPushButton.sal {
        background-color: #7f1d1d;
        border: 1px solid #991b1b;
        color: #fef2f2;
    }

    QPushButton.sal:hover {
        background-color: #b91c1c;
        border-color: #dc2626;
    }

    QPushButton.sal:pressed {
        background-color: #450a0a;
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

    QFrame#Rule {
        background-color: #202634;
        max-height: 2px;
    }
    ''')


# Centrar la ventana en pantalla
def center_on_screen(widget: QWidget):
    widget.adjustSize()
    fg = widget.frameGeometry()
    screen = widget.screen().availableGeometry().center()
    fg.moveCenter(screen)
    widget.move(fg.topLeft())


# =====================================================
#               VENTANA PRINCIPAL
# =====================================================
class WelcomeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(TITULO_GUI)
        self.setMinimumSize(880, 560)

        # Atajos
        self._crear_acciones()

        # Contenido raíz
        root = QWidget()
        tema_oscuro(root)
        self.setCentralWidget(root)

        # Tarjeta
        card = QFrame(objectName='Card')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        header.setSpacing(16)

        # Logo
        logo_label = QLabel()
        logo_label.setFixedSize(72, 72)
        logo_label.setScaledContents(True)

        if LOGO and os.path.exists(LOGO):
            logo_label.setPixmap(QPixmap(LOGO))
        else:
            logo_label.setStyleSheet('''
                QLabel {
                    background-color: #0f1115; 
                    border: 2px solid #223049; 
                    border-radius: 36px;
                }
            ''')

        # Títulos
        title_box = QVBoxLayout()
        lbl_title = QLabel(TITULO_GUI)
        lbl_title.setProperty("class", "h1")

        lbl_subtitle = QLabel(f'{SUBTITULO_GUI} • {VERSION_GUI}')
        lbl_subtitle.setProperty("class", "h2")

        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_subtitle)

        lbl_autor = QLabel(f"Por: {NOMBRE_GUI}")
        lbl_autor.setAlignment(Qt.AlignCenter)
        lbl_autor.setProperty("class", "h3")

        header.addWidget(logo_label)
        header.addLayout(title_box)
        header.addStretch(1)

        # Regla
        rule = QFrame(objectName="Rule")

        # Texto central
        hero = QLabel(
            "Bienvenido/a. Este asistente te guiará para preparar el entorno, "
            "cargar el ELF, seleccionar regiones de memoria y ejecutar campañas "
            "de inyección de fallas."
        )
        hero.setAlignment(Qt.AlignCenter)
        hero.setWordWrap(True)
        hero.setProperty("class", "h2")

        # Botones
        btn_start = QPushButton("Comenzar inyección")
        btn_start.setCursor(Qt.PointingHandCursor)
        btn_start.setProperty("class", "cta")
        btn_start.clicked.connect(self._on_start)

        btn_config = QPushButton("Configuración")
        btn_config.setCursor(Qt.PointingHandCursor)
        btn_config.clicked.connect(self._on_config)

        btn_salir = QPushButton("Salir")
        btn_salir.setCursor(Qt.PointingHandCursor)
        btn_salir.setProperty("class", "sal")
        btn_salir.clicked.connect(self.close)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(12)
        buttons_row.addStretch(1)
        buttons_row.addWidget(btn_config)
        buttons_row.addWidget(btn_salir)
        buttons_row.addWidget(btn_start)

        # Footer
        footer = QLabel(
            "Atajos: Ctrl+N (Comenzar) • Ctrl+M (Configuración) • Esc (Salir) • F1 (Acerca de)"
        )
        footer.setAlignment(Qt.AlignCenter)
        footer.setProperty("class", "caption")

        # Armar tarjeta
        card_layout.addLayout(header)
        card_layout.addWidget(rule)
        card_layout.addStretch(1)
        card_layout.addWidget(hero)
        card_layout.addStretch(1)
        card_layout.addLayout(buttons_row)
        card_layout.addWidget(footer)

        # Layout raíz
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.addStretch(1)
        root_layout.addWidget(card)
        root_layout.addWidget(lbl_autor)
        root_layout.addStretch(1)

        # Drag & Drop desactivado
        self.setAcceptDrops(False)

        # Centrar
        center_on_screen(self)

    # =====================================================
    #    ACCIONES / ATAJOS DEL TECLADO
    # =====================================================
    def _crear_acciones(self):
        act_about = QAction("Acerca de...", self)
        act_about.setShortcut(Qt.Key_F1)
        act_about.triggered.connect(self._on_about)
        self.addAction(act_about)

        act_star = QAction("Comenzar inyección", self)
        act_star.setShortcut(Qt.CTRL | Qt.Key_N)
        act_star.triggered.connect(self._on_start)
        self.addAction(act_star)

        act_config = QAction("Configuración", self)
        act_config.setShortcut(Qt.CTRL | Qt.Key_M)
        act_config.triggered.connect(self._on_config)
        self.addAction(act_config)

        act_salir = QAction("Salir", self)
        act_salir.setShortcut(Qt.Key_Escape)
        act_salir.triggered.connect(self.close)
        self.addAction(act_salir)

    # =====================================================
    #                  CALLBACKS
    # =====================================================
    def _on_start(self):
        # *** NO USAMOS exec() ***
        self.hide()

        self.ventana_inyector = InyectorWindow()
        self.ventana_inyector.setModal(False)
        self.ventana_inyector.destroyed.connect(self.show)
        self.ventana_inyector.show()

    def _on_config(self):
        self.hide()

        self.config_dialog = GUI_CONFIGURACION.ConfigWindow()

        # Cuando cierre la ventana (con aceptar, cancelar, o X)
        self.config_dialog.finished.connect(self.show)

        self.config_dialog.setModal(False)
        self.config_dialog.show()

    def _on_about(self):
        QMessageBox.information(
            self,
            "Acerca de",
            f"{TITULO_GUI}\n{SUBTITULO_GUI}\nVersión {VERSION_GUI}\n\n"
            "Pantalla de bienvenida diseñada con PySide6.\n© 2025"
        )

    # =====================================================
    #          UTILIDADES
    # =====================================================
    def _mostrar_info(self, titulo: str, texto: str):
        QMessageBox.information(self, titulo, texto)


# =====================================================
#                       MAIN
# =====================================================
if __name__ == '__main__':
    app = QApplication([])
    ventana = WelcomeWindow()
    ventana.show()
    app.exec()

