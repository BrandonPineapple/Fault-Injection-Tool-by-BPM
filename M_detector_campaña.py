import os

def obtener_ultima_carpeta_campania():
    """
    Detecta automáticamente la última carpeta 'campaign_' que fue creada en el
    MISMO directorio donde se encuentra este archivo .py.

    Esto significa que el usuario NO tiene que escribir ninguna ruta.
    Funciona aunque muevas el proyecto a otra computadora o carpeta.
    """

    # Carpeta donde se encuentra ESTE archivo .py
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Buscar subcarpetas dentro de base_dir que empiecen con 'campaign_'
    subdirs = [
        os.path.join(base_dir, d)
        for d in os.listdir(base_dir)
        if d.startswith("campaign_") and os.path.isdir(os.path.join(base_dir, d))
    ]

    if not subdirs:
        raise ValueError(f"❌ No se encontraron carpetas 'campaign_' en: {base_dir}")

    # Ordenar las campañas por fecha (la más reciente al final)
    subdirs.sort(key=os.path.getmtime)

    # Retornar la última creada
    return subdirs[-1]


# ===========================================================
# EJEMPLO DE USO — PARA PROBAR QUE FUNCIONA
# ===========================================================

if __name__ == "__main__":
    try:
        ruta = obtener_ultima_carpeta_campania()
        print("📁 Última campaña detectada:")
        print(ruta)

        # Mostrar los archivos que contiene la campaña
        print("\n📄 Archivos encontrados dentro de esa campaña:")
        for f in os.listdir(ruta):
            print("  -", f)

    except Exception as e:
        print("\n❌ ERROR:")
        print(e)
