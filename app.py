import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- FUNCIONES AUXILIARES ---
@st.cache_data
def cargar_excel(archivo):
    xls = pd.ExcelFile(archivo)
    df_cajas = pd.read_excel(xls, "CATALOGO_CAJAS")
    df_reglas = pd.read_excel(xls, "REGLAS_EMPAQUETADO")
    df_receta = pd.read_excel(xls, "RECETA_MODELOS")
    df_vehiculos = pd.read_excel(xls, "VEHICULOS_CONTENEDORES")
    df_palets = pd.read_excel(xls, "PALETS_SOPORTES")
    df_comp = pd.read_excel(xls, "COMPONENTES")
    
    for df in [df_cajas, df_reglas, df_receta, df_vehiculos, df_palets, df_comp]:
        df.columns = df.columns.str.strip()
        
    return df_cajas, df_reglas, df_receta, df_vehiculos, df_palets, df_comp

def get_cube_mesh(x, y, z, dx, dy, dz, color, name):
    return go.Mesh3d(
        x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
        y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
        z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
        i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
        j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
        k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
        color=color, opacity=1.0, name=name, flatshading=True, showscale=False, hoverinfo='name'
    )

def draw_truck_3d(bin_obj, w, h, d):
    fig = go.Figure()
    # Contorno Camión
    lines_x = [0, w, w, 0, 0, 0, w, w, 0, 0, w, w, w, w, 0, 0]
    lines_y = [0, 0, h, h, 0, 0, 0, h, h, 0, 0, 0, h, h, h, h]
    lines_z = [0, 0, 0, 0, 0, d, d, d, d, d, d, 0, 0, d, d, 0]
    fig.add_trace(go.Scatter3d(x=lines_x, y=lines_y, z=lines_z, mode='lines', line=dict(color='black', width=4), name='Camión'))

    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE']
    for item in bin_obj.items:
        color = colors[hash(item.name.split('-')[0]) % len(colors)]
        fig.add_trace(get_cube_mesh(float(item.position[0]), float(item.position[1]), float(item.position[2]),
                                    float(item.width), float(item.height), float(item.depth), color, item.name))

    fig.update_layout(scene=dict(xaxis=dict(range=[0, w+100]), yaxis=dict(range=[0, h+100]), zaxis=dict(range=[0, d+100]), aspectmode='data'), margin=dict(l=0,r=0,b=0,t=0), height=600)
    return fig

# --- CONFIGURACIÓN PÁGINA ---
st.set_page_config(page_title="Calculadora Grupaje 3D", layout="wide", page_icon="🚛")
st.title("🚛 Calculadora de Carga: Pedidos Mixtos (Grupaje)")

# --- ESTADO DE SESIÓN (CARRITO) ---
if 'pedido' not in st.session_state:
    st.session_state.pedido = []

# --- 1. CARGA ---
st.sidebar.header("1. Datos")
uploaded_file = st.sidebar.file_uploader("Sube 'datos.xlsx'", type=["xlsx"])

if uploaded_file:
    try:
        df_cajas, df_reglas, df_receta, df_vehiculos, df_palets, df_comp = cargar_excel(uploaded_file)
        st.sidebar.success("✅ Datos listos")
    except Exception as e:
        st.error(f"Error: {e}"); st.stop()

    # --- 2. GESTIÓN DEL PEDIDO (CARRITO) ---
    st.header("🛒 Configurar Pedido Mixto")
    
    col_add1, col_add2, col_add3 = st.columns([2, 1, 1])
    with col_add1:
        modelo_add = st.selectbox("Seleccionar Modelo", df_receta['Nombre_Modelo'].unique())
    with col_add2:
        cantidad_add = st.number_input("Cantidad", min_value=1, value=50, key="cant_input")
    with col_add3:
        st.write("") # Espacio para alinear botón
        st.write("")
        if st.button("➕ Añadir"):
            st.session_state.pedido.append({"Modelo": modelo_add, "Cantidad": cantidad_add})
            st.success(f"Añadido: {cantidad_add} x {modelo_add}")

    # Mostrar tabla del pedido actual
    if len(st.session_state.pedido) > 0:
        st.write("### 📋 Lista actual de carga:")
        df_pedido = pd.DataFrame(st.session_state.pedido)
        col_table, col_btn = st.columns([3, 1])
        with col_table:
            st.dataframe(df_pedido, use_container_width=True)
        with col_btn:
            if st.button("🗑️ Borrar Todo"):
                st.session_state.pedido = []
                st.rerun()
    else:
        st.info("El pedido está vacío. Añade modelos arriba.")

    st.divider()

    # --- 3. CONFIGURACIÓN TRANSPORTE ---
    st.header("⚙️ Transporte y Empaquetado")
    c1, c2, c3 = st.columns(3)
    with c1: modo = st.radio("Modo Carga", ["📦 A Granel", "🧱 Paletizado"])
    with c2: 
        v_nom = st.selectbox("Vehículo", df_vehiculos['Tipo'].unique())
        holgura = st.slider("Holgura (%)", 0, 10, 2) / 100
    with c3:
        info_palet = None
        if modo == "🧱 Paletizado":
            p_nom = st.selectbox("Tipo Palet", df_palets['Nombre'].unique())
            info_palet = df_palets[df_palets['Nombre'] == p_nom].iloc[0]

    # --- 4. CÁLCULO ---
    if st.button("🚀 Calcular Grupaje Completo", type="primary", disabled=(len(st.session_state.pedido)==0)):
        
        datos_camion = df_vehiculos[df_vehiculos['Tipo'] == v_nom].iloc[0]
        items_load = []
        
        with st.spinner("Procesando pedido mixto..."):
            # BUCLE PRINCIPAL: Iterar sobre cada línea del pedido
            for linea in st.session_state.pedido:
                mod = linea['Modelo']
                cant = linea['Cantidad']
                
                # Obtener receta de este modelo específico
                receta = df_receta[df_receta['Nombre_Modelo'] == mod]
                
                for _, row in receta.iterrows():
                    comp_id = row['ID_Componente']
                    total_piezas = cant * row['Cantidad_x_Butaca']
                    
                    # Buscar Reglas
                    regla = df_reglas[df_reglas['ID_Componente (Qué meto)'] == comp_id]
                    if regla.empty: st.warning(f"Saltando {comp_id}: No hay regla"); continue
                    
                    caja_id = regla.iloc[0]['ID_Caja (Dónde lo meto)']
                    uds_caja = regla.iloc[0]['Cantidad_x_Caja']
                    caja_dat = df_cajas[df_cajas['ID_Caja'] == caja_id].iloc[0]
                    peso_u = df_comp[df_comp['ID_Componente'] == comp_id].iloc[0]['Peso_Neto_Unitario_kg']
                    
                    num_cajas = math.ceil(total_piezas / uds_caja)
                    
                    # Generar Items
                    if modo == "📦 A Granel":
                        p_bulto = (uds_caja * peso_u) + caja_dat['Peso_Vacio_kg']
                        for i in range(num_cajas):
                            items_load.append(Item(f"{mod[:3]}-{comp_id}-{i}", int(caja_dat['Ancho_mm']), int(caja_dat['Alto_mm']), int(caja_dat['Largo_mm']), float(p_bulto)))
                    else:
                        # Paletizado
                        base = int(info_palet['Largo_mm']/caja_dat['Largo_mm']) * int(info_palet['Ancho_mm']/caja_dat['Ancho_mm'])
                        if base == 0: base = int(info_palet['Largo_mm']/caja_dat['Ancho_mm']) * int(info_palet['Ancho_mm']/caja_dat['Largo_mm'])
                        if base == 0: continue # Skip si no cabe
                        
                        cam_h = datos_camion['Alto_Interior_mm'] * (1 - holgura)
                        capas = min(caja_dat['Max_Apilable'], int((cam_h - info_palet['Alto_Base_mm'])/caja_dat['Alto_mm']))
                        if capas < 1: capas = 1
                        
                        x_palet = base * capas
                        n_palets = math.ceil(num_cajas / x_palet)
                        h_palet = info_palet['Alto_Base_mm'] + (capas * caja_dat['Alto_mm'])
                        w_palet = (x_palet * ((uds_caja * peso_u) + caja_dat['Peso_Vacio_kg'])) + info_palet['Peso_Vacio_kg']
                        
                        for p in range(n_palets):
                            items_load.append(Item(f"PAL-{mod[:3]}-{comp_id}-{p}", int(info_palet['Ancho_mm']), int(h_palet), int(info_palet['Largo_mm']), float(w_palet)))

            # EMPAQUETADO FINAL
            if not items_load:
                st.error("No se han generado bultos. Revisa los datos."); st.stop()

            packer = Packer()
            w_bin = int(datos_camion['Ancho_Interior_mm'] * (1-holgura))
            h_bin = int(datos_camion['Alto_Interior_mm'] * (1-holgura))
            d_bin = int(datos_camion['Largo_Interior_mm'] * (1-holgura))
            max_w = int(datos_camion['Carga_Max_kg'])
            
            for i in range(50): packer.add_bin(Bin(f"Camión {i+1}", w_bin, h_bin, d_bin, max_w))
            for it in items_load: packer.add_item(it)
            
            packer.pack()
            
            # --- RESULTADOS ---
            camiones_llenos = [b for b in packer.bins if len(b.items) > 0]
            
            st.divider()
            st.metric("🚛 FLOTA REQUERIDA", len(camiones_llenos))
            
            tabs = st.tabs([b.name for b in camiones_llenos])
            for i, b in enumerate(camiones_llenos):
                with tabs[i]:
                    vol = sum([float(it.width)*float(it.height)*float(it.depth) for it in b.items])/1e9
                    vol_tot = (float(b.width)*float(b.height)*float(b.depth))/1e9
                    peso = sum([float(it.weight) for it in b.items])
                    
                    c1, c2 = st.columns(2)
                    c1.metric("Ocupación Vol.", f"{round((vol/vol_tot)*100, 1)}%")
                    c2.metric("Peso Total", f"{int(peso)} kg")
                    
                    st.plotly_chart(draw_truck_3d(b, float(b.width), float(b.height), float(b.depth)), use_container_width=True)

else:
    st.info("👋 Sube el Excel
