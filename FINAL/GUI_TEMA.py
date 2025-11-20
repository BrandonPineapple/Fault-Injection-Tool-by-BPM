# Función que me va a permitir establecer un fondo para la GUI
from PySide6.QtWidgets import QWidget


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
        
        
    /* Pushbotton */ 
    QPushButton.bon {
        background-color: #1f2937;
        border: 1px solid #263244;
        border-radius: 10px;
        padding: 10px 14px;
        font-weight: 600;
        }

    /* Pushbotton cuando esta el mouse por encima */ 
     QPushButton.bon:hover {
        background-color: #253245;
        border-color: #2c3a50;
        }

    /* Pushbotton cuando se presiona*/
    QPushButton.bon:pressed {
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
