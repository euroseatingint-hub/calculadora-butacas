import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Configuración de la página
st.set_page_config(page_title="Calculadora Logística Butacas", layout="wide")

st.title("🚛 Calculadora de Carga y Volumetría")

# 1. CARGA DE DATOS
st.sidebar.header("1. Subir Datos")
uploaded_file = st.sidebar.file_uploader("Sube tu archivo Excel (datos.xlsx)", type=["xlsx"])

if uploaded_file:
    # Cargar las hojas del Excel
    try:
        df_cajas = pd.read_excel(uploaded_file, sheet_name="CATALOGO_CAJAS")
        df_comp = pd.read_excel(uploaded_file, sheet_name="COMPONENTES")
        df_reglas = pd.read_excel(uploaded_file, sheet_name="REGLAS_EMPAQUETADO")
        df_receta = pd.read_excel(uploaded_file, sheet_name="RECETA_MODELOS")
        df_vehiculos = pd.read_excel(uploaded_file, sheet_name="VEHICULOS_CONTENEDORES")
        
        st.sidebar.success("✅ Datos cargados correctamente")
    except Exception as e:
        st.error(f"Error al leer el Excel: {e}")
        st.stop()

    # 2. SELECCIÓN DE PEDIDO
    st.header("2. Configurar Pedido")
    col1, col2 = st.columns(2)
    
    with col1:
        # Obtener lista de modelos únicos
        lista_modelos = df_receta['Nombre_Modelo'].unique()
        modelo_selec = st.selectbox("Selecciona el Modelo de Butaca", lista_modelos)
        
    with col2:
        cantidad = st.number_input("Número de Butacas", min_value=1, value=100)

    # 3. CÁLCULO DE BULTOS (La lógica potente)
    if st.button("Calcular Envío"):
        st.divider()
        
        # A. Desglose de componentes
        receta_modelo = df_receta[df_receta['Nombre_Modelo'] == modelo_selec]
        
        lista_bultos = []
        peso_total_envio = 0
        volumen_total_envio = 0
        
        st.subheader("📦 Detalle de Bultos Generados")
        
        # Tabla resumen para mostrar al usuario
        resumen_bultos = []

        for index, row in receta_modelo.iterrows():
            componente_id = row['ID_Componente']
            cantidad_por_butaca = row['Cantidad_x_Butaca']
            total_piezas = cantidad * cantidad_por_butaca
            
            # Buscar regla de empaquetado
            regla = df_reglas[df_reglas['ID_Componente (Qué meto)'] == componente_id]
            
            if regla.empty:
                st.warning(f"⚠️ No hay regla de empaquetado para: {componente_id}")
                continue
            
            # Tomamos la primera regla encontrada (asumimos estandarización)
            caja_id = regla.iloc[0]['ID_Caja (Dónde lo meto)']
            uds_por_caja = regla.iloc[0]['Cantidad_x_Caja']
            
            # Calcular número de cajas necesarias
            num_cajas = -(-total_piezas // uds_por_caja) # División hacia arriba (techo)
            
            # Datos de la caja física
            info_caja = df_cajas[df_cajas['ID_Caja'] == caja_id].iloc[0]
            
            # Datos del componente (peso)
            info_comp = df_comp[df_comp['ID_Componente'] == componente_id].iloc[0]
            peso_unitario_pieza = info_comp['Peso_Neto_Unitario_kg']
            
            # Cálculos de Peso y Volumen
            peso_contenido = uds_por_caja * peso_unitario_pieza # Peso lleno ideal
            # Ajuste para la última caja que puede no ir llena
            piezas_ultimo_bulto = total_piezas % uds_por_caja
            if piezas_ultimo_bulto == 0: piezas_ultimo_bulto = uds_por_caja
            
            peso_caja_vacia = info_caja['Peso_Vacio_kg']
            
            # Peso total de este lote de cajas
            # (Num_cajas - 1) * peso_lleno + 1 * peso_ultimo
            peso_lote = ((num_cajas - 1) * (peso_contenido + peso_caja_vacia)) + \
                        ((piezas_ultimo_bulto * peso_unitario_pieza) + peso_caja_vacia)
            
            # Volumen (convertir mm a m3)
            largo_m = info_caja['Largo_mm'] / 1000
            ancho_m = info_caja['Ancho_mm'] / 1000
            alto_m = info_caja['Alto_mm'] / 1000
            vol_unitario_m3 = largo_m * ancho_m * alto_m
            vol_lote_m3 = num_cajas * vol_unitario_m3
            
            peso_total_envio += peso_lote
            volumen_total_envio += vol_lote_m3
            
            resumen_bultos.append({
                "Contenido": componente_id,
                "Tipo Caja": caja_id,
                "Cantidad Cajas": int(num_cajas),
                "Dimensiones (mm)": f"{info_caja['Largo_mm']}x{info_caja['Ancho_mm']}x{info_caja['Alto_mm']}",
                "Volumen Total (m3)": round(vol_lote_m3, 2),
                "Peso Total (kg)": round(peso_lote, 2)
            })

        # Mostrar tabla de resultados
        df_resumen = pd.DataFrame(resumen_bultos)
        st.dataframe(df_resumen, use_container_width=True)
        
        # 4. COMPARACIÓN CON VEHÍCULOS
        st.header("🚚 Selección de Transporte")
        
        vehiculo_selec = st.selectbox("Elige vehículo para simular:", df_vehiculos['Tipo'])
        datos_camion = df_vehiculos[df_vehiculos['Tipo'] == vehiculo_selec].iloc[0]
        
        # Volumen útil del camión (convertir mm a m3)
        vol_camion_m3 = (datos_camion['Largo_Interior_mm']/1000) * \
                        (datos_camion['Ancho_Interior_mm']/1000) * \
                        (datos_camion['Alto_Interior_mm']/1000)
        
        # Factor de estiba (A granel se pierde un 10-15% de espacio por huecos)
        factor_estiba = 0.85 
        vol_util_real = vol_camion_m3 * factor_estiba
        
        ocupacion_pct = (volumen_total_envio / vol_util_real) * 100
        
        # Métricas visuales
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Volumen de la Carga", f"{round(volumen_total_envio, 2)} m³")
        kpi2.metric("Volumen Útil Vehículo", f"{round(vol_util_real, 2)} m³")
        kpi3.metric("Peso Total Estimado", f"{round(peso_total_envio, 2)} kg")
        
        st.subheader(f"📊 Ocupación Estimada: {round(ocupacion_pct, 1)}%")
        
        # Barra de progreso visual
        bar_color = "green" if ocupacion_pct <= 90 else "orange" if ocupacion_pct <= 100 else "red"
        st.progress(min(ocupacion_pct/100, 1.0))
        
        if ocupacion_pct > 100:
            st.error(f"¡CUIDADO! La carga excede la capacidad del camión en un {round(ocupacion_pct - 100, 1)}%. Necesitas un segundo vehículo.")
        elif ocupacion_pct < 100 and datos_camion['Carga_Max_kg'] < peso_total_envio:
             st.warning(f"¡ALERTA DE PESO! Caben por volumen, pero te pasas de Kilos. Máx: {datos_camion['Carga_Max_kg']} kg.")
        else:
            st.success("✅ La carga entra correctamente en el vehículo.")

        # Visualización 3D Simplificada (Cubo de Volumen)
        fig = go.Figure(data=[
            go.Bar(name='Capacidad Camión', x=['Volumen'], y=[vol_util_real], marker_color='lightgrey'),
            go.Bar(name='Tu Carga', x=['Volumen'], y=[volumen_total_envio], marker_color=bar_color)
        ])
        fig.update_layout(barmode='overlay', title="Comparativa Visual de Volumen")
        st.plotly_chart(fig, use_container_width=True)

else:
    st.info("👋 Por favor, sube el archivo Excel 'datos.xlsx' en el menú de la izquierda para empezar.")