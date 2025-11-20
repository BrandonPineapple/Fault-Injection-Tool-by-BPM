#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd
import matplotlib.pyplot as plt

from M_detector_campana import obtener_ultima_carpeta_campania


# =====================================================
# Utilidad: HEX → INT
# =====================================================
def hex_to_int(x):
    try:
        return int(str(x), 16)
    except Exception:
        return None


# =====================================================
# Resolver el estado final por prioridad
# =====================================================
def resolver_estado_final(faultlog, fid):
    filas = faultlog[faultlog["Fault_ID"] == fid]
    if filas.empty:
        return "DESCONOCIDO"

    estados = filas["Estado"].astype(str).str.upper().tolist()

    if any("HANG_POST_FALLA" in e for e in estados):
        return "HANG_POST_FALLA"
    if any("HANG_NO_LLEGO" in e for e in estados):
        return "HANG_NO_LLEGO_A_STOP_ADDRESS"
    if any("NO_ESCRITA" in e for e in estados):
        return "NO_ESCRITA"
    if any("NO_APLICADA" in e or "NO_INYECTADA" in e for e in estados):
        return "NO_APLICADA"
    if any("NO_LEIDO" in e for e in estados):
        return "NO_LEIDO"
    if any(e == "OK" for e in estados):
        return "OK"
    return "OTRO"


# =====================================================
# Comparación GOLD vs AFTER_STABLE
# =====================================================
def comparar_gold_vs_after(row_gold, row_after, mem_cols):
    cambios = {
        "criticos": False,
        "generales": False,
        "ram": False
    }

    # Críticos
    for reg in ["PC", "SP", "LR"]:
        if hex_to_int(row_gold.get(reg)) != hex_to_int(row_after.get(reg)):
            cambios["criticos"] = True

    # Generales R0–R12
    for i in range(13):
        reg = f"R{i}"
        if hex_to_int(row_gold.get(reg)) != hex_to_int(row_after.get(reg)):
            cambios["generales"] = True

    # Memoria
    ram_cambiada = []
    for col in mem_cols:
        if hex_to_int(row_gold.get(col)) != hex_to_int(row_after.get(col)):
            ram_cambiada.append(col)

    cambios["ram"] = len(ram_cambiada) > 0

    return {
        "RegCriticos": cambios["criticos"],
        "RegGenerales": cambios["generales"],
        "RamCambiada": cambios["ram"],
        "NumBytesRAM": len(ram_cambiada),
        "OffsetsRAM": ram_cambiada
    }


# =====================================================
# Helper para % y conteo
# =====================================================
def make_autopct(values):
    total = sum(values)

    def autopct(pct):
        if pct < 0.5:
            return ""
        cantidad = int(round(pct * total / 100.0))
        return f"{pct:.1f}%\n({cantidad})"

    return autopct


# =====================================================
# Gráfico 1: Clasificación técnica (silenciosa / propagada / no_aplicada)
# =====================================================
def grafico_clasificacion_tecnica(df, output_path):

    counts = df["Clasificacion"].value_counts().reindex(
        ["silenciosa", "propagada", "no_aplicada"],
        fill_value=0
    )

    if counts.sum() == 0:
        return

    colores = {
        "silenciosa": "#2ECC71",
        "propagada": "#E74C3C",
        "no_aplicada": "#F1C40F"
    }

    etiquetas = {
        "silenciosa": "Silenciosa",
        "propagada": "Propagada",
        "no_aplicada": "No aplicada"
    }

    categorias = [c for c in counts.index if counts[c] > 0]
    valores = [counts[c] for c in categorias]
    cols = [colores[c] for c in categorias]
    labels = [etiquetas[c] for c in categorias]

    fig, ax = plt.subplots(figsize=(8, 8), dpi=150)

    wedges, texts, autotexts = ax.pie(
        valores,
        labels=labels,
        autopct=make_autopct(valores),
        colors=cols,
        pctdistance=0.75,
        textprops={'fontsize': 11},
        wedgeprops={'linewidth': 1.2, 'edgecolor': 'white'}
    )

    centro = plt.Circle((0, 0), 0.50, fc="white")
    fig.gca().add_artist(centro)

    plt.title("Clasificación de la falla.", fontsize=16)
    plt.tight_layout()

    out = os.path.join(output_path, "grafico_clasificacion.png")
    plt.savefig(out)
    plt.close()
    print("[INFO] Gráfico técnico:", out)


# =====================================================
# Gráfico 2: Estados del inyector
# =====================================================
def grafico_inyector_estados(faultlog, output_path):

    estados_finales = []
    for fid in sorted(faultlog["Fault_ID"].unique()):
        estado_final = resolver_estado_final(faultlog, fid)
        estados_finales.append(estado_final)

    serie = pd.Series(estados_finales, name="Estado_Final")

    def map_categoria(e):
        e = str(e).upper()
        if e == "OK":
            return "OK"
        if "HANG_POST" in e:
            return "Hang después de la falla"
        if "HANG_NO_LLEGO" in e:
            return "Hang antes del stop"
        if "NO_ESCRITA" in e:
            return "No escrita"
        if "NO_APLICADA" in e:
            return "Falla no inyectada"
        if "NO_LEIDO" in e:
            return "No leído"
        return "Otro"

    categorias = serie.map(map_categoria)
    counts = categorias.value_counts()

    colores = {
        "OK": "#27AE60",
        "Hang después de la falla": "#C0392B",
        "Hang antes del stop": "#E67E22",
        "No escrita": "#F1C40F",
        "No aplicada": "#3498DB",
        "No leído": "#95A5A6",
        "Otro": "#7F8C8D"
    }

    vals = [counts[c] for c in counts.index]
    cols = [colores.get(c, "#BBBBBB") for c in counts.index]
    labels = counts.index.tolist()

    fig, ax = plt.subplots(figsize=(8, 8), dpi=150)

    wedges, texts, autotexts = ax.pie(
        vals,
        labels=labels,
        autopct=make_autopct(vals),
        colors=cols,
        pctdistance=0.75,
        textprops={'fontsize': 11},
        wedgeprops={'linewidth': 1.2, 'edgecolor': 'white'}
    )

    centro = plt.Circle((0, 0), 0.50, fc="white")
    fig.gca().add_artist(centro)

    plt.title("Clasificación a detalle", fontsize=16)
    plt.tight_layout()

    out = os.path.join(output_path, "grafico_inyector.png")
    plt.savefig(out)
    plt.close()
    print("[INFO] Gráfico inyector:", out)


# =====================================================
# ANALIZADOR PRINCIPAL
# =====================================================
def analizar_campana_avanzado():
    print("\n[INFO] Buscando última campaña...")
    camp_path = obtener_ultima_carpeta_campania()
    print("[INFO] Última campaña encontrada:", camp_path)

    gold = pd.read_csv(os.path.join(camp_path, "snapshots_gold.csv"))
    after_st = pd.read_csv(os.path.join(camp_path, "snapshots_after_stable.csv"))
    faultlog = pd.read_csv(os.path.join(camp_path, "faults_log.csv"))

    mem_cols = [c for c in gold.columns if c.startswith("MEM_")]

    resultados = []

    print("[INFO] Analizando fallas...")

    for _, g in gold.iterrows():

        fid = g["Fault_ID"]
        estado_final = resolver_estado_final(faultlog, fid)
        fila_after = after_st[after_st["Fault_ID"] == fid]

        # Estados del inyector que significan NO APLICADA
        ESTADOS_NO_APLICADA = [
            "NO_ESCRITA",
            "NO_APLICADA",
            "NO_INYECTADA",
            "NO_APLICADA_STOP_PREVIO",
            "NO_LEIDO",
            "HANG_NO_LLEGO_A_STOP_ADDRESS"
        ]

        # 1) HANG_POST_FALLA → Propagada
        if estado_final == "HANG_POST_FALLA":
            clas = "propagada"
            met = {"RegCriticos": True, "RegGenerales": True,
                   "RamCambiada": True, "NumBytesRAM": 0, "OffsetsRAM": []}

        # 2) SI EL INYECTOR INDICA QUE NO SE APLICÓ
        elif estado_final in ESTADOS_NO_APLICADA:
            clas = "no_aplicada"
            met = {"RegCriticos": False, "RegGenerales": False,
                   "RamCambiada": False, "NumBytesRAM": 0, "OffsetsRAM": []}

        # 3) SI NO EXISTE AFTER_STABLE → TAMPOCO SE APLICÓ
        elif fila_after.empty:
            clas = "no_aplicada"
            met = {"RegCriticos": False, "RegGenerales": False,
                   "RamCambiada": False, "NumBytesRAM": 0, "OffsetsRAM": []}

        # 4) SÍ EXISTE AFTER_STABLE → comparar
        else:
            a = fila_after.iloc[0]
            met = comparar_gold_vs_after(g, a, mem_cols)

            if (not met["RegCriticos"]) and (not met["RegGenerales"]) and (not met["RamCambiada"]):
                clas = "silenciosa"
            else:
                clas = "propagada"

        resultados.append({
            "Fault_ID": fid,
            "Clasificacion": clas,
            "Estado_Final_Inyector": estado_final,
            **met
        })

    # Guardar CSV
    df = pd.DataFrame(resultados)
    out_csv = os.path.join(camp_path, "analisis_avanzado.csv")
    df.to_csv(out_csv, index=False)
    print("[INFO] Archivo analisis_avanzado.csv generado:", out_csv)

    # Gráficos
    grafico_clasificacion_tecnica(df, camp_path)
    grafico_inyector_estados(faultlog, camp_path)

    print("[INFO] Análisis COMPLETO.\n")
    return df, camp_path


# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    analizar_campana_avanzado()
