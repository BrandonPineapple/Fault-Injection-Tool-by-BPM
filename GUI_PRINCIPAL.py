# Librerías principales
import os.path
import sys
import GUI_CONFIGURACION

from PySide6.QtGui import QPixmap, Qt, QAction, QIcon
from PySide6.QtWidgets import (  # Widgets y layouts que usas en la GUI
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy, QSpacerItem,
    QMessageBox, QGraphicsOpacityEffect  # Efecto para hacer fade-in real en widgets hijos
)


# Nombre de varibales a utilizar para la ventana principal
TITULO_GUI = 'Inyector de fallas basado en depuración para microcontroladores'
SUBTITULO_GUI = 'Tesis FI-UNAM'
VERSION_GUI = 'vo.1'
NOMBRE_GUI = 'Brandon Martínez Piña'
LOGO = 'LIESE.jpg'


# Función que me va a permitir establecer un fondo para la GUI
def tema_oscuro(widget: QWidget):
    widget.setStyleSheet('''

    /* Estilo default para todos los widgets */
    QWidget {
        background-color: #0f1115;
        color: #e6e6e6;
        font-family: "Inter", 'Segoe UI', Arial, sans-serif; 
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


# Esta funcíon me va a permitir centrar la aplicación al centro de la pantalla
def center_on_screen(widget: QWidget):
    widget.adjustSize()  # Ajusta al widget a su contenido optimo
    fg = widget.frameGeometry()  # Obtiene un rectangulo que representa a toda la pantalla de la GUI
    screen = widget.screen().availableGeometry().center()  # Obtiene la pantalla de donde s emuestra el widget
    fg.moveCenter(screen)  # Mueve el rectangulo de la widget al centro de la pantalla
    widget.move(
        fg.topLeft())  # Mueve la ventana a la posión determinada por la esquina superior izuqierda del rectandulo fg


class WelcomeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(TITULO_GUI)  # Se define el nombre de la ventana
        self.setMinimumSize(880, 560)  # Se define un tamaño mínimo de la ventana
        # self.setWindowIcon(self._icono_app())  # Se define un icono para la apliación

        # Atajos dentro de la ventana
        self._crear_acciones()

        # Contenido
        root = QWidget()  # Se crea un Widget y se le llama root
        tema_oscuro(root)  # Se aplica el tema oscuro a root
        self.setCentralWidget(root)  # Indica que root será la widget principal

        # Cotenido de la tarjeta con información
        card = QFrame(objectName='Card')  # Widget contenedor y le asigna el monombre de card
        card_layout = QVBoxLayout(card)  # Se define u layout vertical y se colocan dentro de card
        card_layout.setContentsMargins(24, 24, 24, 24)  # Define los margens intenros del layout
        card_layout.setSpacing(16)  # define el espacio entre los diferentes widget dentro dle layout

        # Encabezado
        header = QHBoxLayout()  # Se define un layout horizontal
        header.setSpacing(16)  # Se define un espaciado dentro de los elemtnos intenros del layout

        # Logo
        logo_label = QLabel()  # Crea un widget etiqueta
        logo_label.setFixedSize(72, 72)  # Se fija el tamaño del logo a 72x72 pixeles
        logo_label.setScaledContents(True)  # Se escala automaticamente la imagen al tamaño del widget
        if LOGO and os.path.exists(LOGO):  # Verifica si existe una imagen de logo sino, pone un circulo
            logo_label.setPixmap(QPixmap(LOGO))
        else:
            logo_label.setStyleSheet('''
                QLabel {
                    background-color: #0f1115; 
                    border: 2px solid #223049; 
                    border-radius: 36px;}
            ''')

        # Configuración de los títulos
        title_box = QVBoxLayout()  # Se define un layout vertical
        lbl_tittle = QLabel(TITULO_GUI, objectName='title')  # Etiqueta que muestra el titulo
        lbl_tittle.setObjectName('title')  # A la etiqueta le asigna un nombre
        lbl_tittle.setProperty('class', 'h1')  # Le asigna una clase a la etiqueta
        lbl_tittle.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter)  # Alinea a la etiqueta a la izquierda y centrado dentro del recuadro del texto
        lbl_tittle.setStyleSheet('')  # Se deja vacío para el estilo ya definido anteriormente

        lbl_subtitle = QLabel(f'{SUBTITULO_GUI} • {VERSION_GUI}')  # Se define el subittulo
        lbl_subtitle.setProperty('class', 'h2')  # Se le aisgna una clase al subititulo

        title_box.addWidget(lbl_tittle)  # Agrega el widget label title al layout vertical
        title_box.addWidget(lbl_subtitle)  # Agrega el widget label subtitle al layout vertical

        # Texto de autor debajo de la tarjeta
        lbl_autor = QLabel(f"Por: {NOMBRE_GUI}")
        lbl_autor.setAlignment(Qt.AlignCenter)  # Centrar el texto horizontalmente
        lbl_autor.setProperty('class', 'h3')  # Puedes usar la misma clase que el footer para estilo

        header.addWidget(logo_label)  # Agrega el logo al layout horizontal
        header.addLayout(title_box)  # Agrega la caja de titulos al layout horizontal
        header.addStretch(1)  # Espaciado flexible para dejar todo pegado a la izquierda

        # Regla
        rule = QFrame(objectName='Rule')  # Define un widget que es un contenedor y le asigna el nombre de regla
        rule.setFrameShape(QFrame.NoFrame)  # No tendrá marco el Frame

        # Mensaje Central
        hero = QLabel(f'''
            Bienvenido/a. Este asistente te guiará para preparar el entorno, cargar el binario/ELF, seleccionar regiones de memoria y ejecutar campañas de inyección de fallas.  
                        ''')  # Se define un mensaje para la GUI
        hero.setAlignment(Qt.AlignCenter)  # Se alinea el texto al centro
        hero.setWordWrap(True)  # permite que el texto se ajuste a varias líneas
        hero.setProperty('class', 'h2')  # Se le asigna una clase al mensaje central

        # Botones principales
        btn_start = QPushButton('Comenzar inyección')  # Se define un pushbutton para la inyección de fallas
        btn_start.setCursor(Qt.PointingHandCursor)  # Cambia el cursor por una manita, para indicar que es clickeable
        btn_start.setProperty('class', 'cta')  # Se define una clase al boton
        btn_start.clicked.connect(
            self._on_start)  # Se conecta el evento clic con un método de clase que se ejecutara cuando se presione el boton

        btn_config = QPushButton('Configuración')  # Se define un boton para la configuración
        btn_config.setCursor(Qt.PointingHandCursor)  # Cambia el cursor por una manita, para indicar que es clickeable
        btn_config.clicked.connect(
            self._on_config)  # Se conecta el evento clic con un método de clase que se ejecutara cuando se presione el boton

        btn_salir = QPushButton('Salir')  # Se define un boton para la salir
        btn_salir.setCursor(Qt.PointingHandCursor)  # Cambia el cursor por una manita, para indicar que es clickeable
        btn_salir.setProperty('class', 'sal')
        btn_salir.clicked.connect(self.close)

        buttons_row = QHBoxLayout()  # Se define un layout donde se van a almacenar los botones
        buttons_row.setSpacing(12)  # Se define un espaciado entre botones
        buttons_row.addStretch(1)  # Se agrega un espaciador flexible empujando los botones a la derecha
        buttons_row.addWidget(btn_config)  # Se agregan al layout el boton de config
        buttons_row.addWidget(btn_salir)  # Se agregan al layout el boton de salir
        buttons_row.addWidget(btn_start)  # Se agregan al layout el boton de start

        # Pie con tips
        footer = QLabel("Atajos:  Ctrl+N (Comenzar) • Ctrl+M (Configuración) • Esc (Salir) • F1 (Acerca de)"
                        )  # Se define un mensaje como pie
        footer.setAlignment(Qt.AlignCenter)
        footer.setProperty('class', 'caption')

        # Ensamble de la tarjeta
        card_layout.addLayout(header)  # Se agrega al layout de la carta el layout del header
        card_layout.addWidget(rule)  # Se agrega al layout de la carta el widget rule
        card_layout.addStretch(1)  # Se agrega un espaciador flexible
        card_layout.addWidget(hero)  # Se agrega widget del mensaje central
        card_layout.addStretch(1)  # Se agrega un espaciador flexible
        card_layout.addLayout(buttons_row)  # Se agrega al layout card el layour de los botones
        card_layout.addWidget(footer)  # Se agrega al layout card el widget del fooet

        # Layout raíz con
        root_layout = QVBoxLayout(root)  # Se crea un layout vertical y se asigna el Widget principal
        root_layout.setContentsMargins(24, 24, 24, 24)  # Se define un margen del layout
        root_layout.addStretch(1)  # Se agrega un espaciador flexible antes del card
        root_layout.addWidget(card)  # Se agrega el widget card al layout
        root_layout.addWidget(lbl_autor)
        root_layout.addStretch(1)  # Espaciador flexible, para que card quede centrado del layout

        # Soporte drag & drop de archivos
        self.setAcceptDrops(False)

        # Centrar
        center_on_screen(self)

    # ---------- Drag & Drop ----------
    # instancia que me va a permitir arrastra arhcivo .elf, .bin y .map
    def dragEnterEvent(self, event, /):
        if event.mimeData().hasUrls():  # Verifica si lo que arrastras contiene URLS
            for url in event.mimeData().urls():  # Recorre todos los elementos arrastrados
                if url.toLocalFile().lower().endswith(
                        ('.elf', '.bin', '.map')):  # Si es un arhcivo .elf, .bin o .map es aceptado
                    event.acceptProposedAction()  # Acepta el drop
                    return  # Sale para no seguir revisando más archivo
        event.ignore()  # Si no se cumple lo anterior lo ignora

    def dropEvent(self, event, /):
        paths = []  # Se crea una lista donde se almacenan las rutas de los arhcivos validos
        for url in event.mimeData().urls():  # Recorre todas las urls de los arhcivos que se soltaron sobre el widget
            p = url.toLocalFile()  # Convierte cada Qurl a una ruta local de arhicvo en el sistema
            if p.lower().endswith(('.elf', '.bin',
                                   '.map')):  # Convierte en minusculas el arhichivo y verifica si temrina en .elf, .bin o .map
                paths.append(p)  # Se agrega la ruta a la lista paths
        if paths:  # Si hay almenos un elemtno en paths, ejecuta el bloque if
            self._mostar_info(  # LLama el metodo _mostrar_info para mostar un mensaje
                "Archivo(s) detectado(s)",
                "Se recibieron:\n\n" + "\n".join(paths) +
                "\n\n(En la siguiente pantalla podrás seleccionar regiones, "
                "direcciones y tipo de inyección)."
            )

    # ---------- Acciones / Atajos ----------
    def _crear_acciones(self):  # Define una instancia para las acciones dentro del widget
        act_about = QAction('Acerca de...', self)  # crea una accion
        act_about.setShortcut(Qt.Key_F1)  # Define unn atajo
        act_about.triggered.connect(
            self._on_about)  # Conecta la señal al metodo _on_about, que s eejecutará al activarse la acción
        self.addAction(
            act_about)  # La ventana prinicpal, mantiene una lista de acciones que pueden activarse por atajos del teclado

        act_star = QAction('Comenzar inyección', self)  # Se define una accion para el atajo de inyeccion de fallas
        act_star.setShortcut(Qt.CTRL | Qt.Key_N)  # Se define un atajo para esta accion
        act_star.triggered.connect(self._on_start)  # Se conecta la señal de disparo con el método _on_start
        self.addAction(act_star)  # Se añade la accion al widget

        act_config = QAction('Configuración', self)  # Se define una accion para el atajo de configuración
        act_config.setShortcut(Qt.CTRL | Qt.Key_M)  # Se define un atajo para esta accion
        act_config.triggered.connect(self._on_config)  # Se conecta la señal de disparo con el método _on_config
        self.addAction(act_config)  # Se añade la accion al widget

        act_salir = QAction("Salir", self)  # Se define una accion para el atajo de salir
        act_salir.setShortcut(Qt.Key_Escape)  # Se define un atajo para esta accion
        act_salir.triggered.connect(self.close)  # Se conecta la señal de disparo con el método close
        self.addAction(act_salir)  # Se añade la accion al widget

    # ---------- Callbacks de botones ----------
    def _on_start(self):
        # Aquí más adelante: navegar a tu “ventana de campaña”
        self._mostrar_info(
            "Comenzar inyección",
            "Aquí iniciarías el flujo para:\n"
            "1) Seleccionar dispositivo/sonda\n"
            "2) Cargar .elf/.bin\n"
            "3) Elegir regiones (RAM, Flash, registros)\n"
            "4) Definir tipo de falla (bit-flip, stuck-at, etc.)\n"
            "5) Ejecutar campaña y registrar resultados\n\n"
            "👉 Podemos crear esa pantalla enseguida."
        )

    def _on_config(self):
        config_dialog = GUI_CONFIGURACION.ConfigWindow()
        config_dialog.exec()

    def _on_about(self):
        QMessageBox.information(
            self, "Acerca de",
            f"{TITULO_GUI}\n{SUBTITULO_GUI}\nVersión {VERSION_GUI}\n\n"
            "Pantalla de bienvenida diseñada con PySide6.\n"
            "© 2025"
        )

    # ---------- Utilidades ----------
    def _mostrar_info(self, titulo: str, texto: str):
        QMessageBox.information(self, titulo, texto)  # Se muestra una caja de mensaje con el titulo y la cadena


# def _icono_app(self) -> QIcon:
# Icono simple vectorial embebido (fallback); puedes cambiarlo por un .ico/.png
#    icon = QIcon()
# Si tienes un archivo de icono, descomenta:
# icon.addFile("nuevo.png")
#   return icon


def main():
    # High DPI y comportamiento consistente de fuentes
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)

    win = WelcomeWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    app = QApplication([])
    ventana = WelcomeWindow()
    ventana.show()
    app.exec()
# main()