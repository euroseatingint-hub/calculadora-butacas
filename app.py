import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
import numpy as np
from py3dbp import Packer, Bin, Item

# --- FUNCIONES DE DIBUJO 3D ---
def get_cube_mesh(x, y, z, dx, dy, dz, color, name):
    # Definir los 8 vértices del cubo
    x_coords = [x, x+dx, x+dx, x, x, x+dx, x+dx, x]
    y_coords = [y, y, y+dy, y+dy, y, y, y+dy, y+dy]
    z_coords = [z, z, z, z, z+dz, z+dz, z+dz, z+dz]

    # Definir las caras mediante índices de vértices (triángulos)
    # Plotly usa i, j, k para conectar vértices
    return go.Mesh3d(
        x=x_coords, y=y_coords, z=z_coords,
        i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
        j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
        k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
        color=color,
        opacity=1.0,
        name=name,
        flatshading=True,
        showscale=False,
        hoverinfo='name'
    )

def draw_truck_3d(bin_obj, items_in_bin, bin_w, bin_h, bin_d):
    fig = go.Figure()
    
    # 1. Dibujar el contorno del camión (Wireframe)
    # Definimos las líneas del cubo contenedor
    lines_x = [0, bin_w, bin_w, 0, 0, 0, bin_w, bin_w, 0, 0, bin_w, bin_w, bin_w, bin_w, 0, 0]
    lines_y = [0, 0, bin_h, bin_h, 0, 0, 0, bin_h, bin_h, 0, 0, 0, bin_h, bin_h, bin_h, bin_h]
    lines_z = [0, 0, 0, 0, 0, bin_d, bin_d, bin_d, bin_d, bin_d, bin_d, 0, 0, bin_d, bin_d, 0]
    
    fig.add_trace(go.Scatter3d(
        x=lines_x, y=lines_y, z=lines_z,
        mode='lines',
        line=dict(color='black', width=4),
        name='Paredes Camión',
        hoverinfo='none'
    ))

    # 2. Dibujar las cajas
    # Paleta de colores para diferenciar items
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE', '#F1948A']
    
    for idx, item in enumerate(items_in_bin):
        # Asignar un color basado en el nombre (hash simple) para que los iguales tengan igual color
        color_idx = hash(item.name.split('-')[0]) % len(colors)
        item_color = colors[color_idx]
        
        # Convertir a float para evitar errores de Decimal
        x, y, z = float(item.position[0]), float(item.position[1]), float(item.position[2])
        w, h, d = float(item.width), float(item.height), float(item.depth)
        
        fig.add_trace(get_cube_mesh(x, y, z, w, h, d, item_color, item.name))

    # Configuración de la cámara y ejes
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Ancho (mm)', range=[0, bin_w+100]),
            yaxis=dict(title='Alto (mm)', range=[0, bin_h+100]),
            zaxis=dict(title='Largo (mm)', range=[0, bin_d+100]),
            aspectmode='data' # Proporción real 1:1:1
        ),
        margin=dict(l=0, r=0, b=0, t=0),
        height=600
    )
    return fig

# --- CONFIGURACIÓN APP ---
st.set_page_config(page_title="Visualizador Logístico 3D", layout="wide", page_icon="🚛")
st.title("🚛 Visualizador de Carga 3D")

# --- 1. CARGA ---
st.sidebar.header("1. Datos")
uploaded_file = st.sidebar.file_uploader("Sube 'datos.xlsx'", type=["xlsx"])

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        df_cajas = pd.read_excel(xls, "CATALOGO_CAJAS")
        df_reglas = pd.read_excel(xls, "REGLAS_EMPAQUETADO")
        df_receta = pd.read_excel(xls, "RECETA_MODELOS")
        df_vehiculos = pd.read_excel(xls, "VEHICULOS_CONTENEDORES")
        df_palets = pd.read_excel(xls, "PALETS_SOPORTES")
        df_comp = pd.read_excel(xls, "COMPONENTES")
        
        for df in [df_cajas, df_reglas, df_receta, df_vehiculos, df_palets, df_comp]:
            df.columns = df.columns.str.strip()
            
        st.sidebar.success("✅ Datos cargados")
    except Exception as e:
        st.error(f"Error datos: {e}"); st.stop()

    # --- 2. INPUTS ---
    st.header("⚙️ Pedido")
    c1, c2, c3 = st.columns(3)
    with c1: modelo = st.selectbox("Modelo", df_receta['Nombre_Modelo'].unique())
    with c2: cantidad = st.number_input("Cantidad", 1, 10000, 200)
    with c3: modo = st.radio("Modo", ["📦 A Granel", "🧱 Paletizado"])

    info_palet = None
    if modo == "🧱 Paletizado":
        p_nom = st.selectbox("Palet", df_palets['Nombre'].unique())
        info_palet = df_palets[df_palets['Nombre'] == p_nom].iloc[0]

    st.divider()
    v_nom = st.selectbox("Vehículo", df_vehiculos['Tipo'].unique())
    datos_camion = df_vehiculos[df_vehiculos['Tipo'] == v_nom].iloc[0]
    holgura = st.slider("Holgura (%)", 0, 10, 2) / 100

    # --- 3. CÁLCULO ---
    if st.button("🚀 Calcular y Visualizar 3D", type="primary"):
        receta = df_receta[df_receta['Nombre_Modelo'] == modelo]
        items_load = []
        
        # Limites camión
        cam_h = datos_camion['Alto_Interior_mm'] * (1 - holgura)
        
        # Generación de Items (Lógica Simplificada para brevedad, misma que v4.3)
        with st.spinner("Calculando geometría 3D..."):
            for _, row in receta.iterrows():
                comp_id = row['ID_Componente']
                total = cantidad * row['Cantidad_x_Butaca']
                regla = df_reglas[df_reglas['ID_Componente (Qué meto)'] == comp_id]
                if regla.empty: continue
                
                caja_id = regla.iloc[0]['ID_Caja (Dónde lo meto)']
                uds_caja = regla.iloc[0]['Cantidad_x_Caja']
                caja_dat = df_cajas[df_cajas['ID_Caja'] == caja_id].iloc[0]
                peso_u = df_comp[df_comp['ID_Componente'] == comp_id].iloc[0]['Peso_Neto_Unitario_kg']
                
                num_cajas = math.ceil(total / uds_caja)
                
                if modo == "📦 A Granel":
                    p_bulto = (uds_caja * peso_u) + caja_dat['Peso_Vacio_kg']
                    for i in range(num_cajas):
                        items_load.append(Item(f"{comp_id}-{i}", int(caja_dat['Ancho_mm']), int(caja_dat['Alto_mm']), int(caja_dat['Largo_mm']), float(p_bulto)))
                else:
                    # Lógica Palet (Resumida)
                    base = int(info_palet['Largo_mm']/caja_dat['Largo_mm']) * int(info_palet['Ancho_mm']/caja_dat['Ancho_mm'])
                    if base == 0: base = int(info_palet['Largo_mm']/caja_dat['Ancho_mm']) * int(info_palet['Ancho_mm']/caja_dat['Largo_mm'])
                    if base == 0: st.error("Caja muy grande"); st.stop()
                    
                    capas = min(caja_dat['Max_Apilable'], int((cam_h - info_palet['Alto_Base_mm'])/caja_dat['Alto_mm']))
                    x_palet = base * capas
                    if x_palet == 0: x_palet = 1
                    n_palets = math.ceil(num_cajas / x_palet)
