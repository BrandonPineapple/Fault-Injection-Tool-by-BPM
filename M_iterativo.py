#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd
import streamlit as st


# =====================================================
# Función para detectar todas las campañas
# =====================================================
def obtener_todas_las_campanas():
    """
    Regresa todas las carpetas campaign_ ordenadas por fecha.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))

    campañas = [
        d for d in os.listdir(base_dir)
        if d.startswith("campaign_") and os.path.isdir(os.path.join(base_dir, d))
    ]

    # ordenar por fecha de creación
    campañas.sort(key=lambda f: os.path.getmtime(os.path.join(base_dir, f)))

    return campañas


# =====================================================
# Cargar CSVs de una campaña
# =====================================================
def cargar_campana(nombre):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ruta = os.path.join(base_dir, nombre)

    gold_path = os.path.join(ruta, "snapshots_gold.csv")
    after_path = os.path.join(ruta, "snapshots_after_stable.csv")
    fault_path = os.path.join(ruta, "faults_log.csv")
    analisis_path = os.path.join(ruta, "analisis_avanzado.csv")

    gold = pd.read_csv(gold_path)
    after = pd.read_csv(after_path)
    faultlog = pd.read_csv(fault_path)
    analisis = pd.read_csv(analisis_path)

    # --- Corrección para evitar errores de pyarrow ---
    gold = gold.astype(str)
    after = after.astype(str)
    faultlog = faultlog.astype(str)
    analisis = analisis.astype(str)

    return gold, after, faultlog, analisis, ruta


# =====================================================
# Dashboard principal
# =====================================================
def main():
    st.set_page_config(
        page_title="Dashboard Inyector de Fallas",
        layout="wide"
    )

    st.title("🚀 Dashboard Interactivo — Análisis de Inyección de Fallas")
    st.markdown("Visualiza campañas, fallas, registros y propagación de forma dinámica.")

    # -------------------------------------------------
    # Selección de campaña
    # -------------------------------------------------
    st.sidebar.header("📁 Selección de campaña")
    campañas = obtener_todas_las_campanas()

    if len(campañas) == 0:
        st.error("No se encontraron campañas.")
        return

    seleccion = st.sidebar.selectbox(
        "Selecciona campaña:",
        options=campañas,
        index=len(campañas) - 1
    )

    gold, after, faultlog, analisis, ruta = cargar_campana(seleccion)
    st.sidebar.success(f"Campaña cargada: {seleccion}")

    # -------------------------------------------------
    # Resumen técnico
    # -------------------------------------------------
    st.header("📊 Resumen técnico")

    # Calculamos métricas reales desde 'analisis_avanzado.csv'
    total = len(analisis)
    silenciosas = len(analisis[analisis["Clasificacion"] == "silenciosa"])
    propagadas = len(analisis[analisis["Clasificacion"] == "propagada"])
    no_aplicadas = len(analisis[analisis["Clasificacion"] == "no_aplicada"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total analizadas", total)
    col2.metric("Silenciosas", silenciosas)
    col3.metric("Propagadas", propagadas)
    col4.metric("No aplicadas", no_aplicadas)

    # -------------------------------------------------
    # Gráficos
    # -------------------------------------------------
    st.header("📈 Gráficos")

    colA, colB = st.columns(2)

    with colA:
        st.subheader("Clasificación Técnica (silenciosa/propagada/no aplicada)")
        path = os.path.join(ruta, "grafico_clasificacion_tecnica.png")
        if os.path.exists(path):
            st.image(path)
        else:
            st.warning("No se encontró grafico_clasificacion_tecnica.png")

    with colB:
        st.subheader("Clasificación del Inyector (OK / hangs / no escrita, etc.)")
        path = os.path.join(ruta, "grafico_inyector.png")
        if os.path.exists(path):
            st.image(path)
        else:
            st.warning("No se encontró grafico_inyector.png")

    # -------------------------------------------------
    # Tablas
    # -------------------------------------------------
    st.header("📄 Tablas")

    st.subheader("Gold snapshots")
    st.dataframe(gold, use_container_width=True)

    st.subheader("After Stable snapshots")
    st.dataframe(after, use_container_width=True)

    st.subheader("Fault Log")
    st.dataframe(faultlog, use_container_width=True)

    st.subheader("Análisis Avanzado")
    st.dataframe(analisis, use_container_width=True)

    # -------------------------------------------------
    # Detalle por Fault_ID
    # -------------------------------------------------
    st.header("🔍 Detalle por Fault_ID")

    ids = sorted(analisis["Fault_ID"].unique())
    fid = st.selectbox("Selecciona Fault_ID", ids)

    st.subheader(f"Detalle para Fault_ID {fid}")

    # Buscamos filas correspondientes
    gold_row = gold[gold["Fault_ID"] == fid].iloc[0]
    after_row = after[after["Fault_ID"] == fid].iloc[0]
    anal_row = analisis[analisis["Fault_ID"] == fid].iloc[0]

    st.write(f"**Clasificación Técnica:** {anal_row['Clasificacion']}")
    st.write(f"**Estado Inyector:** {anal_row['Estado_Final_Inyector']}")

    # Comparación GOLD vs AFTER
    st.subheader("Comparación GOLD vs AFTER")
    comp_df = pd.DataFrame({
        "Registro": gold_row.index,
        "GOLD": gold_row.values,
        "AFTER": after_row.values
    })

    comp_df = comp_df.astype(str)  # evitar errores pyarrow
    st.dataframe(comp_df, use_container_width=True)


# =====================================================
# Run
# =====================================================
if __name__ == "__main__":
    main()
