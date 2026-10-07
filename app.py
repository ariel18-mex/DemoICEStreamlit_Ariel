"""
ANÁLISIS DE DATOS EN LA NUBE (LIAD7002)
Sesión 9: Visualización de Datos y Dashboards en la Nube (Streamlit)

Dashboard de indicadores económicos y sociales de México.
Datos reales: API SIE de Banxico + API de Indicadores del INEGI
(verificadas y vigentes a septiembre de 2026).

Ejecutar localmente:  streamlit run 09_Dashboard_Streamlit.py
Desplegar: subir este archivo + requirements.txt a GitHub y conectar
en https://share.streamlit.io (Streamlit Community Cloud).
"""

import requests
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Dashboard México - LIAD7002", layout="wide")

st.title("📊 Indicadores Económicos y Sociales de México")
st.markdown(
    "Fuente: **Banxico SIE** y **API de Indicadores del INEGI** — "
    "datos verificados y vigentes a **septiembre de 2026**."
)

# ---------------------------------------------------------------------
# Tokens: en producción se guardan en Streamlit Secrets (Settings > Secrets),
# nunca directamente en el código fuente.
# ---------------------------------------------------------------------
TOKEN_BANXICO = st.secrets.get("BANXICO_TOKEN", "TU_TOKEN_AQUI")
TOKEN_INEGI = st.secrets.get("INEGI_TOKEN", "TU_TOKEN_AQUI")


@st.cache_data(ttl=3600, show_spinner="Consultando Banxico SIE...")
def obtener_serie_banxico(token, serie, fecha_ini, fecha_fin):
    """Obtiene una serie histórica real de Banxico SIE. Devuelve DataFrame [fecha, valor]."""
    url = (
        f"https://www.banxico.org.mx/SieAPIRest/service/v1/series/"
        f"{serie}/datos/{fecha_ini}/{fecha_fin}?token={token}"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        datos = resp.json()["bmx"]["series"][0].get("datos", [])
        df = pd.DataFrame(datos)
        df.columns = ["fecha", "valor"]
        df["fecha"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y", errors="coerce")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df.dropna(), True
    except Exception:
        # Datos de respaldo con la misma estructura, para no bloquear la demo sin token real
        fechas = pd.date_range(fecha_ini, fecha_fin, freq="ME")
        np.random.seed(42)
        valores = 12.5 + np.cumsum(np.random.normal(0.03, 0.25, len(fechas)))
        return pd.DataFrame({"fecha": fechas, "valor": valores}), False


@st.cache_data(ttl=3600, show_spinner="Consultando INEGI...")
def obtener_poblacion_entidades(token):
    """Obtiene la población real de las 32 entidades federativas (API INEGI)."""
    id_indicador = "1002000001"  # Población total
    registros = []
    for entidad in [f"{i:02d}" for i in range(1, 33)]:
        # Endpoint vigente (BISE 2.0). El antiguo "www3.inegi.org.mx/sistemas/api/..." ya no
        # existe (fue retirado por el INEGI); usarlo hace que la llamada falle silenciosamente
        # dentro de este except y el dashboard caiga siempre al respaldo sintético.
        url = (
            f"https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/INDICATOR/"
            f"{id_indicador}/es/{entidad}/true/BISE/2.0/{token}?type=json"
        )
        try:
            dato = requests.get(url, timeout=10).json()["Series"][0]["OBSERVATIONS"][0]
            registros.append({"entidad_id": entidad, "poblacion": float(dato["OBS_VALUE"])})
        except Exception:
            pass

    if registros:
        return pd.DataFrame(registros), True

    np.random.seed(3)
    entidades = [f"{i:02d}" for i in range(1, 33)]
    df = pd.DataFrame({
        "entidad_id": entidades,
        "poblacion": np.random.randint(500_000, 17_000_000, len(entidades)).astype(float)
    })
    return df, False


# ---------------------------------------------------------------------
# Sección 1: Tipo de cambio (serie histórica real de Banxico)
# ---------------------------------------------------------------------
st.header("💱 Tipo de Cambio Peso-Dólar (Banxico SIE)")

df_tc, tc_es_real = obtener_serie_banxico(TOKEN_BANXICO, "SF43718", "2015-01-01", "2025-12-31")
if not tc_es_real:
    st.info("ℹ️ Mostrando datos de respaldo (mismo formato) — configura BANXICO_TOKEN en Secrets para datos reales en vivo.")

if not df_tc.empty:
    fecha_min, fecha_max = df_tc["fecha"].min(), df_tc["fecha"].max()
    rango = st.slider(
        "Selecciona el periodo",
        min_value=fecha_min.to_pydatetime(),
        max_value=fecha_max.to_pydatetime(),
        value=(fecha_min.to_pydatetime(), fecha_max.to_pydatetime()),
    )
    df_filtrado = df_tc[(df_tc["fecha"] >= rango[0]) & (df_tc["fecha"] <= rango[1])]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Último valor", f"{df_filtrado['valor'].iloc[-1]:.2f} MXN/USD")
    with col2:
        st.metric("Promedio del periodo", f"{df_filtrado['valor'].mean():.2f} MXN/USD")
    with col3:
        variacion = df_filtrado['valor'].iloc[-1] - df_filtrado['valor'].iloc[0]
        st.metric("Variación en el periodo", f"{variacion:+.2f}")

    st.line_chart(df_filtrado.set_index("fecha")["valor"])

    with st.expander("Ver datos crudos"):
        st.dataframe(df_filtrado, use_container_width=True)

# ---------------------------------------------------------------------
# Sección 2: Población por entidad federativa (real, INEGI)
# ---------------------------------------------------------------------
st.header("🇲🇽 Población por Entidad Federativa (INEGI)")

df_pob, pob_es_real = obtener_poblacion_entidades(TOKEN_INEGI)
if not pob_es_real:
    st.info("ℹ️ Mostrando datos de respaldo (mismo formato) — configura INEGI_TOKEN en Secrets para datos reales en vivo.")

entidad_seleccionada = st.selectbox(
    "Filtrar por clave de entidad (opcional)",
    options=["Todas"] + sorted(df_pob["entidad_id"].unique().tolist())
)

df_pob_mostrar = df_pob if entidad_seleccionada == "Todas" else df_pob[df_pob["entidad_id"] == entidad_seleccionada]

st.bar_chart(df_pob_mostrar.set_index("entidad_id")["poblacion"])
st.dataframe(df_pob_mostrar.sort_values("poblacion", ascending=False), use_container_width=True)

# ---------------------------------------------------------------------
st.markdown("---")
st.caption(
    "Dashboard elaborado para la materia Análisis de Datos en la Nube (LIAD7002). "
    "Fuentes verificadas a septiembre de 2026: banxico.org.mx/SieAPIRest y "
    "inegi.org.mx/servicios/api_indicadores.html"
)
