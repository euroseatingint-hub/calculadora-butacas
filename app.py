import streamlit as st
import pandas as pd
import math
from py3dbp import Packer, Bin, Item

# Configuración de la página
st.set_page_config(page_title="Planificador Logístico Maestro", layout="wide", page_icon="🚛")

st.title("🚛 Planificador Maestro: Multi-Camión y Paletización")
st.markdown("Calcula automáticamente cuántos camiones necesitas y optimiza la carga (Tetris 3D).")

# --- 1. CARGA DE DATOS ---
st.sidebar.header("1. Carga de Datos")
uploaded_file = st.sidebar.file_uploader("Sube 'datos.xlsx'", type=["xlsx"])

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        df_cajas = pd.read_excel(xls, "CATALOGO_CAJAS")
        df_reglas = pd.read_excel(xls, "REGLAS_EMPAQUETADO")
        df_receta = pd.read_excel(xls, "RECETA_MODELOS")
        df_vehiculos = pd.read_excel(xls, "VEHICULOS_CONTENEDORES")
        df_palets = pd.read_excel(xls, "PALETS_SOPORTES") # Necesario para palets
        df_comp = pd.read_excel(xls, "COMPONENTES")
        
        # Limpieza de columnas
        for df in [df_cajas, df_reglas, df_receta, df_vehiculos, df_palets, df_comp]:
            df.columns = df.columns.str.strip()
            
        st.sidebar.success("✅ Datos cargados")
    except Exception as e:
        st.error(f"Error crítico leyendo el Excel: {e}")
        st.stop()

    # --- 2. CONFIGURACIÓN ---
    st.header("⚙️ Configuración del Pedido")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        modelo_selec = st.selectbox("Modelo de Butaca", df_receta['Nombre_Modelo'].unique())
    with c2:
        cantidad = st.number_input("Cantidad Total", min_value=1, value=200)
    with c3:
        modo_carga = st.radio("Modo de Envío", ["📦 A Granel (Cajas sueltas)", "🧱 Paletizado"])

    # Selector de Palet (Solo si aplica)
    info_palet = None
    if modo_carga == "🧱 Paletizado":
        palet_nombre = st.selectbox("Tipo de Palet", df_palets['Nombre'].unique())
        info_palet = df_palets[df_palets['Nombre'] == palet_nombre].iloc[0]
        st.info(f"Palet Base: {info_palet['Largo_mm']}x{info_palet['Ancho_mm']} mm | Altura taco: {info_palet['Alto_Base_mm']} mm")

    st.divider()
    
    st.header("🚚 Vehículo")
    vehiculo_nombre = st.selectbox("Selecciona Vehículo", df_vehiculos['Tipo'].unique())
    datos_camion = df_vehiculos[df_vehiculos['Tipo'] == vehiculo_nombre].iloc[0]
    
    # Margen de seguridad (Las cajas se abomban)
    holgura = st.slider("Margen de Holgura (%)", 0, 10, 2) / 100

    # --- 3. PROCESAMIENTO ---
    if st.button("🚀 Calcular Flota Necesaria", type="primary"):
        
        # A. GENERAR LA LISTA DE BULTOS (ITEMS)
        receta_modelo = df_receta[df_receta['Nombre_Modelo'] == modelo_selec]
        items_para_cargar = []
        
        st.spinner("Generando bultos y paletizando virtualmente...")
        
        # Dimensiones útiles del camión (para limitar altura de palets)
        alto_camion_util = datos_camion['Alto_Interior_mm'] * (1 - holgura)
        
        for index, row in receta_modelo.iterrows():
            componente_id = row['ID_Componente']
            total_piezas = cantidad * row['Cantidad_x_Butaca']
            
            # Buscar Regla y Caja
            regla = df_reglas[df_reglas['ID_Componente (Qué meto)'] == componente_id]
            if regla.empty: st.error(f"Falta regla para {componente_id}"); st.stop()
            
            caja_id = regla.iloc[0]['ID_Caja (Dónde lo meto)']
            uds_por_caja = regla.iloc[0]['Cantidad_x_Caja']
            
            # Info Caja
            caja_data = df_cajas[df_cajas['ID_Caja'] == caja_id].iloc[0]
            
            # Info Peso Componente
            comp_data = df_comp[df_comp['ID_Componente'] == componente_id]
            peso_unitario = comp_data.iloc[0]['Peso_Neto_Unitario_kg'] if not comp_data.empty else 0
            
            # Calcular cajas necesarias
            num_cajas_totales = math.ceil(total_piezas / uds_por_caja)
            
            # --- LÓGICA GRANEL ---
            if modo_carga == "📦 A Granel (Cajas sueltas)":
                peso_bulto = (uds_por_caja * peso_unitario) + caja_data['Peso_Vacio_kg']
                for i in range(num_cajas_totales):
                    items_para_cargar.append(Item(
                        partno=f"{componente_id}-{i}",
                        name=f"Caja {componente_id}",
                        typeof='cube',
                        w=int(caja_data['Ancho_mm']),
                        h=int(caja_data['Alto_mm']),
                        d=int(caja_data['Largo_mm']),
                        weight=peso_bulto
                    ))
            
            # --- LÓGICA PALETIZADO ---
            else:
                # 1. Calcular cuántas cajas caben en un palet (Base)
                filas_l = int(info_palet['Largo_mm'] / caja_data['Largo_mm'])
                filas_a = int(info_palet['Ancho_mm'] / caja_data['Ancho_mm'])
                base_cajas = filas_l * filas_a
                
                # Intentar rotada si cabe mejor
                if base_cajas == 0:
                     base_cajas = int(info_palet['Largo_mm'] / caja_data['Ancho_mm']) * \
                                  int(info_palet['Ancho_mm'] / caja_data['Largo_mm'])
                
                if base_cajas == 0:
                    st.error(f"La caja {caja_id} es más grande que el palet.")
                    st.stop()
                    
                # 2. Calcular Altura Máxima
                altura_disponible = alto_camion_util - info_palet['Alto_Base_mm']
                max_capas_altura = int(altura_disponible / caja_data['Alto_mm'])
                capas_reales = min(caja_data['Max_Apilable'], max_capas_altura)
                
                cajas_por_palet = base_cajas * capas_reales
                
                # 3. Crear los Palets Virtuales
                num_palets_necesarios = math.ceil(num_cajas_totales / cajas_por_palet)
                
                altura_total_palet = info_palet['Alto_Base_mm'] + (capas_reales * caja_data['Alto_mm'])
                peso_neto_palet = (cajas_por_palet * ((uds_por_caja * peso_unitario) + caja_data['Peso_Vacio_kg']))
                peso_bruto_palet = peso_neto_palet + info_palet['Peso_Vacio_kg']
                
                # Crear Items "Palet" para el optimizador
                for p in range(num_palets_necesarios):
                    # Identificar si es el último palet (puede ir menos lleno, pero ocupa lo mismo de volumen o menos altura)
                    # Simplificación: Asumimos altura completa para seguridad
                    items_para_cargar.append(Item(
                        partno=f"PAL-{componente_id}-{p}",
                        name=f"Palet {componente_id}",
                        typeof='cube',
                        w=int(info_palet['Ancho_mm']),
                        h=int(altura_total_palet), # Altura real calculada
                        d=int(info_palet['Largo_mm']),
                        weight=peso_bruto_palet
                    ))

        # B. PROCESO DE CARGA MULTI-CAMIÓN
        packer = Packer()
        # Añadimos muchos camiones (Bins) potenciales (ej. 10 camiones). El algoritmo usará el 1, luego el 2...
        # Aplicamos la holgura al camión
        ancho_u = int(datos_camion['Ancho_Interior_mm'] * (1 - holgura))
        alto_u = int(datos_camion['Alto_Interior_mm'] * (1 - holgura))
        largo_u = int(datos_camion['Largo_Interior_mm'] * (1 - holgura))
        carga_u = int(datos_camion['Carga_Max_kg'])

        for i in range(20): # Límite de 20 camiones para evitar bucles infinitos
            packer.add_bin(Bin(f"Camión {i+1}", ancho_u, alto_u, largo_u, carga_u))

        # Añadir todos los ítems
        for item in items_para_cargar:
            packer.add_item(item)

        packer.pack()

        # --- 4. RESULTADOS ---
        st.divider()
        st.subheader("📋 Resultado de la Flota")
        
        camiones_usados = []
        for b in packer.bins:
            if len(b.items) > 0:
                camiones_usados.append(b)

        st.metric("TOTAL CAMIONES NECESARIOS", len(camiones_usados))
        
        # Detalle por camión
        tabs = st.tabs([b.name for b in camiones_usados])
        
        for i, b in enumerate(camiones_usados):
            with tabs[i]:
                items_dentro = len(b.items)
                vol_ocupado = b.get_volume_used() / 1e9
                vol_total = (b.width * b.height * b.depth) / 1e9
                pct = (vol_ocupado / vol_total) * 100
                peso_total = sum([item.weight for item in b.items])
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Bultos a bordo", items_dentro)
                c2.metric("Ocupación Volumétrica", f"{round(pct, 2)}%")
                c3.metric("Peso Total", f"{int(peso_total)} kg", f"Máx {datos_camion['Carga_Max_kg']}")
                
                st.progress(pct/100)
                
                if peso_total > datos_camion['Carga_Max_kg']:
                    st.error("⚠️ Este camión excede el peso máximo permitido.")
                
                # Tabla detallada de qué lleva este camión
                datos_carga = []
                for item in b.items:
                    datos_carga.append({
                        "Bulto": item.name,
                        "Dimensiones (mm)": f"{item.get_dimension()[0]}x{item.get_dimension()[1]}x{item.get_dimension()[2]}",
                        "Posición (X,Y,Z)": f"{int(float(item.position[0]))}, {int(float(item.position[1]))}, {int(float(item.position[2]))}",
                        "Peso": f"{int(item.weight)} kg"
                    })
                
                st.dataframe(pd.DataFrame(datos_carga))

        # Mostrar items que no cupieron ni en 20 camiones (Error raro)
        if len(camiones_usados) > 0 and len(camiones_usados[-1].unfitted_items) > 0:
            st.error("❌ Hay bultos que no caben en ningún camión (probablemente son más grandes que el propio camión).")
else:
    st.info("👋 Sube tu Excel para comenzar.")
