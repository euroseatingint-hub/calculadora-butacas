import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import math

# Configuración de la página
st.set_page_config(page_title="Calculadora Logística 2.0", layout="wide", page_icon="🚛")

# Título y Estilo
st.title("🚛 Calculadora de Carga y Volumetría")
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; border-radius: 10px; padding: 20px; text-align: center;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

# --- 1. CARGA DE DATOS ---
st.sidebar.header("1. Configuración")
uploaded_file = st.sidebar.file_uploader("Sube 'datos.xlsx'", type=["xlsx"])

if uploaded_file:
    try:
        # Cargar todas las hojas necesarias
        xls = pd.ExcelFile(uploaded_file)
        df_cajas = pd.read_excel(xls, "CATALOGO_CAJAS")
        df_comp = pd.read_excel(xls, "COMPONENTES")
        df_reglas = pd.read_excel(xls, "REGLAS_EMPAQUETADO")
        df_receta = pd.read_excel(xls, "RECETA_MODELOS")
        df_vehiculos = pd.read_excel(xls, "VEHICULOS_CONTENEDORES")
        df_palets = pd.read_excel(xls, "PALETS_SOPORTES") # Nueva hoja
        
        # Limpieza de espacios en blanco en los nombres de columnas y datos
        for df in [df_cajas, df_comp, df_reglas, df_receta, df_vehiculos, df_palets]:
            df.columns = df.columns.str.strip()
            
        st.sidebar.success("✅ Datos cargados")
        
    except Exception as e:
        st.error(f"Error al leer el Excel: {e}")
        st.stop()

    # --- 2. CONFIGURACIÓN DEL PEDIDO ---
    st.header("📦 Configurar Pedido")
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        lista_modelos = df_receta['Nombre_Modelo'].unique()
        modelo_selec = st.selectbox("Modelo de Butaca", lista_modelos)
        
    with col_b:
        cantidad = st.number_input("Cantidad de Butacas", min_value=1, value=100)

    with col_c:
        modo_carga = st.radio("Modo de Carga", ["A Granel (Cajas sueltas)", "Paletizado"], index=0)

    # Selección de Palet (Solo si es modo paletizado)
    palet_selec = None
    info_palet = None
    if modo_carga == "Paletizado":
        nombres_palets = df_palets['Nombre'].unique()
        nombre_palet = st.selectbox("Selecciona el tipo de Palet", nombres_palets)
        info_palet = df_palets[df_palets['Nombre'] == nombre_palet].iloc[0]
        st.info(f"Dimensiones Palet: {info_palet['Largo_mm']}x{info_palet['Ancho_mm']} mm - Altura Base: {info_palet['Alto_Base_mm']} mm")

    st.divider()

    # --- 3. SELECCIÓN DE VEHÍCULO ---
    st.header("🚚 Configurar Transporte")
    col_v1, col_v2 = st.columns(2)
    
    with col_v1:
        tipo_transporte = st.radio("Tipo de Transporte", ["Ver Todos", "Camión (Carretera)", "Contenedor (Marítimo)"], horizontal=True)
    
    with col_v2:
        # Filtrar lista de vehículos según selección
        if tipo_transporte == "Camión (Carretera)":
            filtro_v = df_vehiculos[df_vehiculos['Tipo'].str.contains("Camion|Tráiler|Lona", case=False, na=False)]
        elif tipo_transporte == "Contenedor (Marítimo)":
            filtro_v = df_vehiculos[df_vehiculos['Tipo'].str.contains("Contenedor|20|40", case=False, na=False)]
        else:
            filtro_v = df_vehiculos
            
        vehiculo_nombre = st.selectbox("Selecciona Vehículo", filtro_v['Tipo'].unique())
        datos_camion = df_vehiculos[df_vehiculos['Tipo'] == vehiculo_nombre].iloc[0]

    # --- 4. MOTOR DE CÁLCULO ---
    if st.button("🚀 Calcular Ocupación", type="primary"):
        
        receta_modelo = df_receta[df_receta['Nombre_Modelo'] == modelo_selec]
        
        # Acumuladores globales
        total_peso_carga = 0
        total_volumen_carga_m3 = 0
        total_palets_usados = 0
        detalle_logistica = []

        # -- PROCESAR CADA COMPONENTE --
        for index, row in receta_modelo.iterrows():
            componente_id = row['ID_Componente']
            cant_x_butaca = row['Cantidad_x_Butaca']
            total_piezas = cantidad * cant_x_butaca
            
            # Buscar regla
            regla = df_reglas[df_reglas['ID_Componente (Qué meto)'] == componente_id]
            if regla.empty:
                st.error(f"❌ Falta regla para: {componente_id}")
                st.stop()
                
            caja_id = regla.iloc[0]['ID_Caja (Dónde lo meto)']
            uds_por_caja = regla.iloc[0]['Cantidad_x_Caja']
            
            # Buscar datos caja (CON SEGURIDAD)
            filtro_caja = df_cajas[df_cajas['ID_Caja'] == caja_id]
            if filtro_caja.empty:
                st.error(f"❌ La caja '{caja_id}' no existe en el Catálogo.")
                st.stop()
            info_caja = filtro_caja.iloc[0]
            
            # Buscar datos peso componente
            filtro_comp = df_comp[df_comp['ID_Componente'] == componente_id]
            peso_unitario = filtro_comp.iloc[0]['Peso_Neto_Unitario_kg'] if not filtro_comp.empty else 0
            
            # -- CÁLCULOS --
            num_cajas = math.ceil(total_piezas / uds_por_caja)
            
            # Peso
            peso_contenido_total = total_piezas * peso_unitario
            peso_carton_total = num_cajas * info_caja['Peso_Vacio_kg']
            peso_lote = peso_contenido_total + peso_carton_total
            total_peso_carga += peso_lote
            
            # Volumen Caja Individual (m3)
            vol_caja_m3 = (info_caja['Largo_mm'] * info_caja['Ancho_mm'] * info_caja['Alto_mm']) / 1e9
            
            # LOGICA SEGÚN MODO DE CARGA
            if modo_carga == "A Granel (Cajas sueltas)":
                vol_lote = num_cajas * vol_caja_m3
                total_volumen_carga_m3 += vol_lote
                desc_extra = f"{num_cajas} cajas sueltas"
                
            else: # PALETIZADO
                # 1. Cuántas cajas caben en la base del palet?
                # (Simplificación: Área palet / Área caja) - Se puede mejorar con algoritmo de rectángulo
                # Asumimos sin rotación compleja para asegurar
                filas_largo = int(info_palet['Largo_mm'] / info_caja['Largo_mm'])
                filas_ancho = int(info_palet['Ancho_mm'] / info_caja['Ancho_mm'])
                base_cajas = filas_largo * filas_ancho
                
                # Si no cabe ninguna en esa orientación, probamos girar la caja 90 grados mentalmente
                if base_cajas == 0:
                     filas_largo_g = int(info_palet['Largo_mm'] / info_caja['Ancho_mm'])
                     filas_ancho_g = int(info_palet['Ancho_mm'] / info_caja['Largo_mm'])
                     base_cajas = filas_largo_g * filas_ancho_g
                
                if base_cajas == 0:
                    st.error(f"❌ La caja {caja_id} es más grande que el palet seleccionado.")
                    st.stop()

                # 2. Cuántas alturas (capas)?
                # Limitado por Max Apilable de la caja o Altura Máxima Camión (aprox 2.5m - 15cm palet)
                max_apil_caja = info_caja['Max_Apilable']
                altura_disponible_palet = datos_camion['Alto_Interior_mm'] - info_palet['Alto_Base_mm']
                max_capas_por_altura = int(altura_disponible_palet / info_caja['Alto_mm'])
                
                capas_reales = min(max_apil_caja, max_capas_por_altura)
                cajas_por_palet = base_cajas * capas_reales
                
                # 3. Total Palets para este componente
                num_palets = math.ceil(num_cajas / cajas_por_palet)
                total_palets_usados += num_palets
                
                # Volumen ocupado por los palets (incluyendo madera y aire)
                # Altura del palet cargado = Base + (Capas * Alto Caja)
                altura_palet_cargado = info_palet['Alto_Base_mm'] + (capas_reales * info_caja['Alto_mm'])
                vol_palet_unitario = (info_palet['Largo_mm'] * info_palet['Ancho_mm'] * altura_palet_cargado) / 1e9
                
                total_volumen_carga_m3 += (num_palets * vol_palet_unitario)
                
                # Sumar peso de la madera de los palets
                total_peso_carga += (num_palets * info_palet['Peso_Vacio_kg'])
                
                desc_extra = f"{num_palets} palets ({cajas_por_palet} cajas/palet)"

            detalle_logistica.append({
                "Componente": componente_id,
                "Caja": caja_id,
                "Cantidad Piezas": total_piezas,
                "Logística": desc_extra,
                "Peso (kg)": round(peso_lote, 1),
                "Volumen (m3)": round(total_volumen_carga_m3, 2) # Acumulado parcial visual
            })

        # --- RESULTADOS FINALES ---
        st.write("---")
        st.subheader("📊 Resultados de la Simulación")
        
        # DATOS DEL CAMIÓN
        vol_camion_real = (datos_camion['Largo_Interior_mm'] * datos_camion['Ancho_Interior_mm'] * datos_camion['Alto_Interior_mm']) / 1e9
        area_suelo_camion = (datos_camion['Largo_Interior_mm'] * datos_camion['Ancho_Interior_mm']) / 1e6 # m2
        
        # CÁLCULO DE OCUPACIÓN
        if modo_carga == "Paletizado":
            # Ocupación por SUELO (Area)
            area_palet = (info_palet['Largo_mm'] * info_palet['Ancho_mm']) / 1e6
            area_ocupada = total_palets_usados * area_palet
            ocupacion_pct = (area_ocupada / area_suelo_camion) * 100
            metro_lineal = (total_palets_usados * info_palet['Largo_mm'] / 2) / 1000 # Estimación burda LDM
            texto_ocupacion = f"Espacio de Suelo: {round(area_ocupada,1)} m² de {round(area_suelo_camion,1)} m²"
            
            # KPI Extra para palets
            st.info(f"🧱 Total Palets: **{total_palets_usados}** | Estibados en suelo (no remontables)")
            
        else:
            # Ocupación por VOLUMEN (Granel)
            factor_estiba = 0.90 # 10% de pérdida por huecos
            vol_util = vol_camion_real * factor_estiba
            ocupacion_pct = (total_volumen_carga_m3 / vol_util) * 100
            texto_ocupacion = f"Volumen Carga: {round(total_volumen_carga_m3,1)} m³ (Capacidad útil: {round(vol_util,1)} m³)"

        # MOSTRAR KPIS
        k1, k2, k3 = st.columns(3)
        k1.metric("Ocupación Vehículo", f"{round(ocupacion_pct, 1)}%", delta_color="inverse")
        k2.metric("Peso Total", f"{int(total_peso_carga)} kg", f"Máx {datos_camion['Carga_Max_kg']} kg")
        k3.metric("Modo", modo_carga)
        
        # BARRA DE PROGRESO
        color_barra = "green"
        if ocupacion_pct > 85: color_barra = "orange"
        if ocupacion_pct > 100: color_barra = "red"
        
        st.write(texto_ocupacion)
        st.progress(min(ocupacion_pct/100, 1.0))
        
        if ocupacion_pct > 100:
            st.error(f"❌ ¡NO CABE! Necesitas {round(ocupacion_pct/100, 1)} vehículos de este tipo.")
        elif total_peso_carga > datos_camion['Carga_Max_kg']:
            st.warning("⚠️ CUIDADO: Caben por espacio, pero EXCEDES EL PESO MÁXIMO.")
        else:
            st.success("✅ El envío es viable.")

        # DETALLE
        with st.expander("Ver desglose detallado por componente"):
            st.dataframe(pd.DataFrame(detalle_logistica))

else:
    st.info("👋 Sube tu archivo 'datos.xlsx' en el menú lateral para empezar.")
