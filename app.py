import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- CONFIGURACIÓN PÁGINA ---
st.set_page_config(page_title="Calculadora Grupaje 3D", layout="wide", page_icon="🚛")

# --- FUNCIONES ---
@st.cache_data
def cargar_excel(archivo):
    xls = pd.ExcelFile(archivo)
    return {sheet: pd.read_excel(xls, sheet).rename(columns=lambda x: x.strip()) for sheet in xls.sheet_names}

def draw_truck_3d(bin_obj, w, h, d):
    fig = go.Figure()
    lines_x = [0, w, w, 0, 0, 0, w, w, 0, 0, w, w, w, w, 0, 0]
    lines_y = [0, 0, h, h, 0, 0, 0, h, h, 0, 0, 0, h, h, h, h]
    lines_z = [0, 0, 0, 0, 0, d, d, d, d, d, d, 0, 0, d, d, 0]
    fig.add_trace(go.Scatter3d(x=lines_x, y=lines_y, z=lines_z, mode='lines', line=dict(color='black', width=4), name='Camión'))
    
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE']
    for item in bin_obj.items:
        c = colors[hash(item.name.split('-')[0]) % len(colors)]
        fig.add_trace(go.Mesh3d(
            x=[float(item.position[0]) + v for v in [0, float(item.width), float(item.width), 0, 0, float(item.width), float(item.width), 0]],
            y=[float(item.position[1]) + v for v in [0, 0, float(item.height), float(item.height), 0, 0, float(item.height), float(item.height)]],
            z=[float(item.position[2]) + v for v in [0, 0, 0, 0, float(item.depth), float(item.depth), float(item.depth), float(item.depth)]],
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2], j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3], k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            color=c, opacity=1.0, flatshading=True, name=item.name
        ))
    fig.update_layout(scene=dict(aspectmode='data'), margin=dict(l=0,r=0,b=0,t=0), height=500)
    return fig

# --- APP PRINCIPAL ---
st.title("🚛 Calculadora de Carga: Grupaje")

if 'pedido' not in st.session_state:
    st.session_state.pedido = []

st.sidebar.header("1. Datos")
f = st.sidebar.file_uploader("Sube 'datos.xlsx'", type=["xlsx"])

if f:
    try:
        dfs = cargar_excel(f)
        st.sidebar.success("✅ Datos listos")
    except Exception as e:
        st.error(f"Error: {e}"); st.stop()

    # CARRITO
    st.header("🛒 Configurar Pedido")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: mod = st.selectbox("Modelo", dfs['RECETA_MODELOS']['Nombre_Modelo'].unique())
    with c2: cant = st.number_input("Cantidad", 1, value=50)
    with c3: 
        st.write(""); st.write("")
        if st.button("➕ Añadir"): st.session_state.pedido.append({"Modelo": mod, "Cantidad": cant})

    if st.session_state.pedido:
        st.dataframe(pd.DataFrame(st.session_state.pedido), use_container_width=True)
        if st.button("🗑️ Borrar Todo"): st.session_state.pedido = []; st.rerun()
    
    st.divider()

    # CÁLCULO
    st.header("⚙️ Transporte")
    cc1, cc2, cc3 = st.columns(3)
    with cc1: modo = st.radio("Modo", ["📦 A Granel", "🧱 Paletizado"])
    with cc2: vehic = st.selectbox("Vehículo", dfs['VEHICULOS_CONTENEDORES']['Tipo'].unique())
    with cc3: 
        palet_info = None
        if modo == "🧱 Paletizado":
            p_nom = st.selectbox("Palet", dfs['PALETS_SOPORTES']['Nombre'].unique())
            palet_info = dfs['PALETS_SOPORTES'][dfs['PALETS_SOPORTES']['Nombre'] == p_nom].iloc[0]

    if st.button("🚀 Calcular", type="primary", disabled=not st.session_state.pedido):
        items_load = []
        camion = dfs['VEHICULOS_CONTENEDORES'][dfs['VEHICULOS_CONTENEDORES']['Tipo'] == vehic].iloc[0]
        
        with st.spinner("Calculando..."):
            for l in st.session_state.pedido:
                receta = dfs['RECETA_MODELOS'][dfs['RECETA_MODELOS']['Nombre_Modelo'] == l['Modelo']]
                for _, row in receta.iterrows():
                    regla = dfs['REGLAS_EMPAQUETADO'][dfs['REGLAS_EMPAQUETADO']['ID_Componente (Qué meto)'] == row['ID_Componente']]
                    if regla.empty: continue
                    
                    caja = dfs['CATALOGO_CAJAS'][dfs['CATALOGO_CAJAS']['ID_Caja'] == regla.iloc[0]['ID_Caja (Dónde lo meto)']].iloc[0]
                    peso_u = dfs['COMPONENTES'][dfs['COMPONENTES']['ID_Componente'] == row['ID_Componente']].iloc[0]['Peso_Neto_Unitario_kg']
                    
                    total_p = l['Cantidad'] * row['Cantidad_x_Butaca']
                    num_c = math.ceil(total_p / regla.iloc[0]['Cantidad_x_Caja'])
                    
                    if modo == "📦 A Granel":
                        peso_b = (regla.iloc[0]['Cantidad_x_Caja'] * peso_u) + caja['Peso_Vacio_kg']
                        for i in range(num_c):
                            items_load.append(Item(f"{l['Modelo'][:3]}-{row['ID_Componente']}-{i}", int(caja['Ancho_mm']), int(caja['Alto_mm']), int(caja['Largo_mm']), float(peso_b)))
                    else:
                        base = int(palet_info['Largo_mm']/caja['Largo_mm']) * int(palet_info['Ancho_mm']/caja['Ancho_mm'])
                        if base == 0: base = int(palet_info['Largo_mm']/caja['Ancho_mm']) * int(palet_info['Ancho_mm']/caja['Largo_mm'])
                        if base == 0: continue
                        
                        capas = min(caja['Max_Apilable'], int((camion['Alto_Interior_mm']*0.98 - palet_info['Alto_Base_mm'])/caja['Alto_mm']))
                        n_palets = math.ceil(num_c / (base * max(1, capas)))
                        h_p = palet_info['Alto_Base_mm'] + (capas * caja['Alto_mm'])
                        w_p = ((base*capas) * ((regla.iloc[0]['Cantidad_x_Caja'] * peso_u) + caja['Peso_Vacio_kg'])) + palet_info['Peso_Vacio_kg']
                        
                        for p in range(n_palets):
                            items_load.append(Item(f"PAL-{l['Modelo'][:3]}-{row['ID_Componente']}-{p}", int(palet_info['Ancho_mm']), int(h_p), int(palet_info['Largo_mm']), float(w_p)))

            packer = Packer()
            for i in range(20): packer.add_bin(Bin(f"C{i+1}", int(camion['Ancho_Interior_mm']*0.98), int(camion['Alto_Interior_mm']*0.98), int(camion['Largo_Interior_mm']*0.98), int(camion['Carga_Max_kg'])))
            for it in items_load: packer.add_item(it)
            packer.pack()
            
            used_bins = [b for b in packer.bins if len(b.items) > 0]
            st.metric("🚛 CAMIONES", len(used_bins))
            tabs = st.tabs([b.name for b in used_bins])
            for i, b in enumerate(used_bins):
                with tabs[i]:
                    st.plotly_chart(draw_truck_3d(b, float(b.width), float(b.height), float(b.depth)), use_container_width=True)
else:
    st.info("👋 Sube el Excel para empezar.")
