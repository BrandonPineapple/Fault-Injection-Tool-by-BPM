# Se immporta el script en donde se almacenan las acciones de la ventana de configuración

import script_configuracion

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QComboBox, QMessageBox, QDialog, QProgressBar, QTextEdit
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap

from script_configuracion import microcontroladores


# Función que me va a permitir establecer un fondo para la GUI
def tema_oscuro(widget: QWidget):
    widget.setStyleSheet('''

    /* Estilo default para todos los widgets */
    QWidget {
        background-color: #0f1115;
        color: #e6e6e6;
        font-family: "Inter", 'Segoe UI', Arial, sans-serif; 
    }

    /* ComboBox */
    QComboBox {
        background-color: #1f2937;   /* Fondo */
        border: 1px solid #2c3a50;   /* Borde */
        border-radius: 8px;          /* Bordes redondeados */
        padding: 6px 30px 6px 12px;  /* Espaciado: izq, der (deja espacio para la flecha) */
        color: #e6e6e6;              /* Texto */
        font-weight: 500;
    }

    /* Hover */
    QComboBox:hover {
        background-color: #253245;
        border-color: #3a4b63;
    }

    /* Cuando está desplegado */
    QComboBox::drop-down {
        border: none;
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 24px;
        border-left: 1px solid #2c3a50;
    }

    /* Flecha personalizada */
    QComboBox::down-arrow {
        image: url(down-arrow.png);   /* aquí puedes poner un ícono personalizado */
        width: 12px;
        height: 12px;
    }

    /* Lista desplegable */
    QComboBox QAbstractItemView {
        background-color: #1a1d25;
        border: 1px solid #2c3a50;
        selection-background-color: #2563eb;
        selection-color: white;
        outline: 0;
    }

    /* Contenedor principal tipo tarjeta */
    QFrame#Card {
        background-color: #151922;
        border: 1px solid #1f2430;
        border-radius: 16px;
    }

    /* Etiquetas con clase h1 */
    QLabel.h1 {
        font-size: 24px; 
        font-weight: 800; 
        color: #f3f4f6;
        letter-spacing: 0.2px;
        }

    /* Etiquetas con clase h2 */
    QLabel.h2 {
        font-size: 14px; 
        color: #aab0bb;
        }

    /* Etiquetas con clase caption */   
    QLabel.caption {
        font-size: 11px;
        color: #8c92a1;
        }

    /* Etiquetas con clase h3 */   
    QLabel.h3 {
        font-size: 12px;
        color: #b0b3b8;
        font-style: italic;
        }

    /* Pushbotton */ 
    QPushButton {
        background-color: #1f2937;
        border: 1px solid #263244;
        border-radius: 10px;
        padding: 10px 14px;
        font-weight: 600;
        }

    /* Pushbotton cuando esta el mouse por encima */ 
     QPushButton:hover {
        background-color: #253245;
        border-color: #2c3a50;
        }

    /* Pushbotton cuando se presiona*/
    QPushButton:pressed {
        background-color: #1a2433;
        }

    /* Pushbutton */
        QPushButton.sal {
            background-color: #7f1d1d;   /* Rojo oscuro */
            border: 1px solid #991b1b;   /* Borde rojo más fuerte */
            border-radius: 10px;
            padding: 10px 14px;
            font-weight: 600;
            color: #fef2f2;              /* Texto casi blanco con toque rosado */
        }

    /* Pushbutton cuando está el mouse por encima */
    QPushButton.sal:hover {
        background-color: #b91c1c;   /* Rojo más vivo */
        border-color: #dc2626;       /* Borde rojo intenso */
        }

    /* Pushbutton cuando se presiona */
    QPushButton.sal:pressed {
        background-color: #450a0a;   /* Rojo muy oscuro */
        }

    /* Pushbotton con etiqueta cta*/ 
    QPushButton.cta {
        background-color: #2563eb;
        border: 1px solid #1e50bb;
        color: white;
        }

    /* Pushbotton con etiqueta cta cuando esta el mouse por encima */ 
    QPushButton.cta:hover {
        background-color: #2b6ef5;
        }

    /* Pushbotton con etiqueta cta cuando se presiona*/
    QPushButton.cta:pressed {
        background-color: #1e55c9;
        }

    /* Línea decorativa */
    QFrame#Rule {
        background-color: #202634;
        max-height: 2px;
        min-height: 2px;
        }

    /* Barra superior */
    QMainWindow::separator { background: transparent; }

    ''')


class IntalacionThread(QThread):  # Se define una clase que me permite crear hilos de ejecución
    progreso = Signal(int)  # Define señales personalizadas, representa el porcentaje de progreso de (0-100)
    mensaje = Signal(str)  # Aqui se define una mensaje que se va a mostrar en la consola interna de la GUI

    def __init__(self, micro):
        super().__init__()
        self.micro = micro

    def run(self):  # instancia que va a ejecutar los scripts
        configurador = script_configuracion.Configurador(self.micro)  # se almacena en una variable la clase

        self.mensaje.emit('Actualizando librerías')  # Se emite un menssaje
        msgs = configurador.instalar_librerias()
        for i, m in enumerate(msgs):
            self.mensaje.emit(m)
            self.progreso.emit(0 + int((i + 1) / len(msgs) * 50))

        self.mensaje.emit('Actualizando packs...')
        self.progreso.emit(60)
        ok, msg = configurador.instalar_paquete()
        self.mensaje.emit(msg)

        self.progreso.emit(100)
        self.mensaje.emit('Instalación completa')


# Venatana de Configuración con consola

class ConfigWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Configuración de la herramienta')
        self.setMinimumSize(500, 400)

        tema_oscuro(self)

        seleccion_micro = QVBoxLayout(
            self)  # Se define un layout vertical en donde ira la selección del microcontrolador
        self.texto_opciones = QLabel('Selecciona el microcontrolador: ')
        self.opciones = QComboBox()  # Se define un combobox
        self.opciones.addItems(list(microcontroladores.keys()))  # Se añaden las opciones al combo box

        seleccion_micro.addWidget(self.texto_opciones)  # Se añade el widget del etiqueta al layout
        seleccion_micro.addWidget(self.opciones)  # Se añade el widget de combobox al layout

        self.btn_instalar = QPushButton('Instalar paquetes y librerías')
        self.btn_instalar.setCursor(Qt.PointingHandCursor)
        self.btn_instalar.setProperty('class', 'cta')
        seleccion_micro.addWidget(self.btn_instalar)
        self.btn_instalar.clicked.connect(self._instalar)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        seleccion_micro.addWidget(self.progress)

        self.consola = QTextEdit()
        self.consola.setReadOnly(True)
        seleccion_micro.addWidget(self.consola)

        self.btn_cerrar = QPushButton('Cerrar')
        self.btn_cerrar.setCursor(Qt.PointingHandCursor)
        self.btn_cerrar.setProperty('class', 'sal')
        seleccion_micro.addWidget(self.btn_cerrar)
        self.btn_instalar.setProperty('class', 'cta')
        seleccion_micro.addWidget(self.btn_instalar)
        self.btn_cerrar.clicked.connect(self.close)

    def _instalar(self):
        micro = self.opciones.currentText()
        self.btn_cerrar.setEnabled(False)
        self.thread = IntalacionThread(micro)
        self.thread.progreso.connect(self.progress.setValue)
        self.thread.mensaje.connect(self.imprimir_consola)
        self.thread.finished.connect(lambda: self.btn_cerrar.setEnabled(True))
        self.thread.start()

    def imprimir_consola(self, msg):
        self.consola.append(msg)
        self.consola.verticalScrollBar().setValue(self.consola.verticalScrollBar().maximum())





