import csv

# Opciones para el usuario
ubicaciones = {1: "RAM", 2: "FLASH", 3: "REGISTRO"}
tipos_fallas = {1: "bitflip", 2: "stuck-at-0", 3: "stuck-at-1"}


def solicitar_entero(msg, minimo=None, maximo=None):
    while True:
        try:
            valor = int(input(msg))
            if (minimo is not None and valor < minimo) or (maximo is not None and valor > maximo):
                print(f"Debe estar entre {minimo} y {maximo}.")
                continue
            return valor
        except ValueError:
            print("Ingrese un número válido.")


def solicitar_direccion_8bytes(msg):
    """
    Solicita una dirección hexadecimal estrictamente de 8 bytes (32 bits)
    Formato obligatorio: 0xXXXXXXXX
    """
    while True:
        valor = input(msg).strip()

        if not valor.startswith("0x"):
            valor = "0x" + valor

        try:
            numero = int(valor, 16)
            # formatear a 8 bytes y comparar
            direccion_formateada = f"0x{numero:08X}"

            if len(direccion_formateada) != 10:  # 0x + 8 hex chars = 10
                print("La dirección debe ser exactamente de 8 bytes (0xXXXXXXXX).")
                continue

            return direccion_formateada

        except ValueError:
            print("Ingrese un valor hexadecimal válido. Ejemplo: 0x20000000")


def solicitar_mascara_un_bit(msg):
    """
    La máscara debe tener un solo bit activo dentro de 32 bits.
    """
    while True:
        valor = input(msg).strip()

        if not valor.startswith("0x"):
            valor = "0x" + valor

        try:
            m = int(valor, 16)

            # Validar que solo tenga un bit activo
            if m == 0 or (m & (m - 1)) != 0 or m > 0xFFFFFFFF:
                print("La máscara debe tener EXACTAMENTE un solo bit activo (32 bits).")
                continue

            mascara = f"0x{m:08X}"

            # Calcular bit automáticamente
            bit = (m.bit_length() - 1)

            return mascara, bit

        except ValueError:
            print("Máscara inválida. Ejemplos válidos: 0x00000001, 0x00000080, 0x80000000")


def generar_y_exportar_fallas():
    """
    Genera fallas con restricciones:
      - Direcciones de 8 bytes hex
      - Mascara de 1 bit
      - Bit calculado automáticamente
    """
    lista = []

    num_fallas = solicitar_entero("Número de fallas a generar: ", 1, 999)

    nombre_csv = "LISTA_INYECCION_USUARIO.csv"

    for i in range(1, num_fallas + 1):
        print(f"\n--- Falla {i} ---")

        # UBICACIÓN
        ub = solicitar_entero("Ubicación (1=RAM, 2=FLASH, 3=REGISTROS): ", 1, 3)
        ubicacion = ubicaciones[ub]

        # TIPO FALLA
        tipo = solicitar_entero("Tipo (1=bitflip, 2=stuck-at-0, 3=stuck-at-1): ", 1, 3)
        tipo_falla = tipos_fallas[tipo]

        # DIRECCIONES de 8 bytes
        direccion_stop = solicitar_direccion_8bytes("Dirección STOP (8 bytes hex): ")
        direccion_iny = solicitar_direccion_8bytes("Dirección INYECCIÓN (8 bytes hex): ")

        # Máscara y bit calculado automáticamente
        mascara, bit = solicitar_mascara_un_bit("Máscara (1 solo bit activo): ")

        lista.append({
            "FAULT_ID": i,
            "UBICACION": ubicacion,
            "TIPO_FALLA": tipo_falla,
            "DIRECCION STOP": direccion_stop,
            "DIRECCION INYECCION": direccion_iny,
            "MASCARA": mascara,
            "BIT": bit
        })

    # Exportar a CSV
    with open(nombre_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "FAULT_ID", "UBICACION", "TIPO_FALLA",
            "DIRECCION STOP", "DIRECCION INYECCION",
            "MASCARA", "BIT"
        ])
        for fila in lista:
            writer.writerow([
                fila["FAULT_ID"], fila["UBICACION"], fila["TIPO_FALLA"],
                fila["DIRECCION STOP"], fila["DIRECCION INYECCION"],
                fila["MASCARA"], fila["BIT"]
            ])

    print(f"\nCSV generado correctamente: {nombre_csv}\n")
    return lista


# ----------- MAIN ----------
if __name__ == "__main__":
    lista_fallas = generar_y_exportar_fallas()

    print("\n=== Resumen de fallas ingresadas ===")
    for f in lista_fallas:
        print(f)
