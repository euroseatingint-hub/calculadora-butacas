import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Planificador Logístico V18", layout="wide", page_icon="🚛")

# --- FUNCIONES GRÁFICAS (REALISTAS) ---
def get_cube_edges(x, y, z, dx, dy, dz):
    """ Coordenadas para dibujar las líneas negras (bordes) """
    v = [[x, y, z], [x+dx, y, z], [x+dx, y+dy, z], [x, y+dy, z],
         [x, y, z+dz], [x+dx, y, z+dz], [x+dx, y+dy, z+dz], [x, y+dy, z+dz]]
    xe, ye, ze = [], [], []
    # Aristas (Base, Techo, Verticales)
    for i, j in [(0,1), (1,2), (2,3), (3,0), (4,5), (5,6), (6,7), (7,4), (0,4), (1,5), (2,6), (3,7)]:
        xe.extend([v[i][0], v[j][0], None])
        ye.extend([v[i][1], v[j][1], None])
        ze.extend([v[i][2], v[j][2], None])
    return xe, ye, ze

def draw_truck_final(bin_obj, w, h, d):
    fig = go.Figure()
    W, H, L = float(w), float(h), float(d)

    # 1. Contenedor (Suelo y Paredes Transparentes)
    # Suelo Gris Oscuro
    fig.add_trace(go.Mesh3d(
        x=[0, W, W, 0], y=[0, 0, L, L], z=[0, 0, 0, 0],
        color='#7f8c8d', opacity=0.6, name='Suelo'
    ))
    
    # Límites (Wireframe)
    lx, ly, lz = get_cube_edges(0, 0, 0, W, L, H)
    fig.add_trace(go.Scatter3d(x=lx, y=ly, z=lz, mode='lines', line=dict(color='black', width=5), hoverinfo='none', name='Límites'))

    # 2. Cajas
    color_map = {'asiento': '#E74C3C', 'respaldo': '#3498DB', 'carcasa': '#F1C40F', 'costado': '#8E44AD', 'pal': '#D35400', 'base': '#95A5A6'}
    fallback = ['#16A085', '#27AE60', '#2980B9', '#8E44AD']

    for i, item in enumerate(bin_obj.items):
        # Mapeo Ejes: py3dbp(w,h,d) -> Plotly(x=Ancho, z=Alto, y=Largo)
        dx, dz, dy = float(item.width), float(item.height), float(item.depth)
        x, z, y = float(item.position[0]), float(item.position[1]), float(item.position[2])
        
        # Color
        c = fallback[i % len(fallback)]
        for k, v in color_map.items():
            if k in item.name.lower(): c = v; break

        # Cubo Sólido
        fig.add_trace(go.Mesh3d(
            x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
            y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
            z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            color=c, opacity=1.0, flatshading=True, name=item.name, hoverinfo='name'
        ))
        # Bordes Negros
        ex, ey, ez = get_cube_edges(x, y, z, dx, dy, dz)
        fig.add_trace(go.Scatter3d(x=ex, y=ey, z=ez, mode='lines', line=dict(color='black', width=3), showlegend=False, hoverinfo='skip'))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Ancho (mm)', range=[0, W*1.05], backgroundcolor="#ecf0f1"),
            yaxis=dict(title='Largo (mm)', range=[0, L*1.05], backgroundcolor="#ecf0f1"),
            zaxis=dict(title='Alto (mm)', range=[0, H*1.05], backgroundcolor="#bdc3c7"),
            aspectmode='data', 
            camera=dict(eye=dict(x=1.7, y=-1.7, z=1.2)) # Vista isométrica
        ),
        margin=dict(l=0, r=0, b=0, t=30), height=700, title=f"Vista 3D: {bin_obj.name}"
    )
    return fig

# --- DATOS ---
@st.cache_data
def cargar_excel(archivo):
    xls = pd.ExcelFile(archivo)
    return {sheet: pd.read_excel(xls, sheet).rename(columns=lambda x: x.strip()) for sheet in xls.sheet_names}

def buscar_regla(nombre, df_reglas):
    n = str(nombre).lower().replace(" ", "")
    for idx, row in df_reglas.iterrows():
        r = str(row['ID_Componente (Qué meto)']).lower().replace(" ", "")
        if r in n or n in r: return row
    return None

# --- APP ---
st.sidebar.title("🛠️ Panel Control")
if st.sidebar.button("🗑️ RESETEAR APP", type="primary"):
    st.session_state.clear()
    st.rerun()

st.title("🚛 Planificador Logístico V18 (Estable)")

if 'pedido' not in st.session_state: st.session_state.pedido = []

# 1. CARGA
f = st.sidebar.file_uploader("1. Sube Excel", type=["xlsx"])
if f:
    try: dfs = cargar_excel(f); st.sidebar.success("Excel OK")
    except: st.error("Error Excel"); st.stop()

    # 2. PEDIDO
    st.header("1. Configurar Pedido")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: mod = st.selectbox("Modelo", dfs['RECETA_MODELOS']['Nombre_Modelo'].unique())
    with c2: cant = st.number_input("Cantidad", 1, value=50)
    with c3: 
        st.write(""); st.write("")
        if st.button("➕ Añadir"): st.session_state.pedido.append({"Modelo": mod, "Cantidad": cant})

    if st.session_state.pedido:
        st.dataframe(pd.DataFrame(st.session_state.pedido), use_container_width=True)
        if st.button("Limpiar Lista"): st.session_state.pedido = []; st.rerun()
    
    st.divider()

    # 3. TRANSPORTE
    st.header("2. Transporte")
    ca, cb, cc = st.columns(3)
    with ca: modo = st.radio("Formato", ["📦 A Granel", "🧱 Paletizado"])
    with cb: vehic_nom = st.selectbox("Vehículo", dfs['VEHICULOS_CONTENEDORES']['Tipo'].unique())
    with cc:
        p_info = None
        if modo == "🧱 Paletizado":
            p_nom = st.selectbox("Palet", dfs['PALETS_SOPORTES']['Nombre'].unique())
            p_info = dfs['PALETS_SOPORTES'][dfs['PALETS_SOPORTES']['Nombre'] == p_nom].iloc[0]

    # 4. CÁLCULO
    if st.button("🚀 CALCULAR", type="primary", disabled=not st.session_state.pedido):
        
        vehiculo = dfs['VEHICULOS_CONTENEDORES'][dfs['VEHICULOS_CONTENEDORES']['Tipo'] == vehic_nom].iloc[0]
        items_load = []
        volumen_total = 0
        total_cajas_reales = 0
        
        with st.spinner("Procesando datos..."):
            for l in st.session_state.pedido:
                receta = dfs['RECETA_MODELOS'][dfs['RECETA_MODELOS']['Nombre_Modelo'] == l['Modelo']]
                for _, row in receta.iterrows():
                    regla = buscar_regla(row['ID_Componente'], dfs['REGLAS_EMPAQUETADO'])
                    if regla is None: continue
                    try: caja = dfs['CATALOGO_CAJAS'][dfs['CATALOGO_CAJAS']['ID_Caja'] == regla['ID_Caja (Dónde lo meto)']].iloc[0]
                    except: continue

                    L, W, H = caja['Largo_mm'], caja['Ancho_mm'], caja['Alto_mm']
                    if L < 200: L*=10; W*=10; H*=10 # Corrección mm
                    
                    try: peso_u = dfs['COMPONENTES'][dfs['COMPONENTES']['ID_Componente'] == regla['ID_Componente (Qué meto)']].iloc[0]['Peso_Neto_Unitario_kg']
                    except: peso_u = 5
                    
                    piezas_caja = regla['Cantidad_x_Caja']
                    num_cajas = math.ceil((l['Cantidad'] * row['Cantidad_x_Butaca']) / piezas_caja)
                    total_cajas_reales += num_cajas
                    
                    if modo == "🧱 Paletizado":
                        base_L = int(p_info['Largo_mm'] / L) * int(p_info['Ancho_mm'] / W)
                        base_W = int(p_info['Largo_mm'] / W) * int(p_info['Ancho_mm'] / L)
                        base = max(base_L, base_W)
                        if base == 0: continue
                        
                        h_disp = vehiculo['Alto_Interior_mm'] * 0.98 - p_info['Alto_Base_mm']
                        capas = min(caja['Max_Apilable'], int(h_disp / H))
                        if capas < 1: capas = 1
                        
                        items_p_palet = base * capas
                        n_palets = math.ceil(num_cajas / items_p_palet)
                        
                        h_final = p_info['Alto_Base_mm'] + (capas * H)
                        w_p = (items_p_palet * ((piezas_caja*peso_u) + caja['Peso_Vacio_kg'])) + p_info['Peso_Vacio_kg']
                        
                        for p in range(n_palets):
                            items_load.append(Item(f"PAL-{row['ID_Componente'][:4]}-{p}", int(p_info['Ancho_mm']), int(h_final), int(p_info['Largo_mm']), float(w_p)))
                            volumen_total += (int(p_info['Ancho_mm']) * int(h_final) * int(p_info['Largo_mm']))
                    else:
                        w_b = (piezas_caja*peso_u) + caja['Peso_Vacio_kg']
                        for i in range(num_cajas):
                            items_load.append(Item(f"CJ-{row['ID_Componente'][:4]}-{i}", int(W), int(H), int(L), float(w_b)))
                            volumen_total += (int(W) * int(H) * int(L))

        if not items_load: st.error("No hay carga válida."); st.stop()

        # KPIs PREVIOS
        vol_camion = float(vehiculo['Ancho_Interior_mm']*vehiculo['Alto_Interior_mm']*vehiculo['Largo_Interior_mm'])
        st.info(f"📊 Volumen Carga: **{round(volumen_total/1e9, 2)} m³** | Capacidad Vehículo: **{round(vol_camion/1e9, 2)} m³**")

        # SORTING Y PACKING (ESTÁNDAR PARA EVITAR CRASH)
        # Ordenar por volumen para simular gravedad
        items_load.sort(key=lambda x: x.width * x.height * x.depth, reverse=True)
        
        packer = Packer()
        # Solo 1 camión en modo análisis
        packer.add_bin(Bin(vehiculo['Tipo'], int(vehiculo['Ancho_Interior_mm']), int(vehiculo['Alto_Interior_mm']), int(vehiculo['Largo_Interior_mm']), int(vehiculo['Carga_Max_kg'])))
        
        for it in items_load: packer.add_item(it)
        packer.pack()
        
        b = packer.bins[0]
        
        # RESULTADOS
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Bultos DENTRO", len(b.items))
        c2.metric("Bultos FUERA", len(b.unfitted_items), delta_color="inverse")
        
        # Corrección del cálculo de porcentaje (evitar TypeError)
        v_real = sum([float(i.width) * float(i.height) * float(i.depth) for i in b.items])
        try:
            pct = (v_real / vol_camion) * 100
        except: pct = 0
            
        c3.metric("Ocupación Real", f"{round(pct, 1)}%")

        # VISUALIZACIÓN
        st.subheader("Vista 3D Realista")
        if len(b.items) > 0:
            st.plotly_chart(draw_truck_final(b, b.width, b.height, b.depth), use_container_width=True)
        else:
            st.warning("Camión vacío.")

        if b.unfitted_items:
            st.error(f"❌ {len(b.unfitted_items)} bultos no han cabido.")
            with st.expander("Ver lista de sobrantes"):
                d = [{"Ref": i.name, "Medidas": f"{int(i.width)}x{int(i.depth)}x{int(i.height)}"} for i in b.unfitted_items]
                st.dataframe(pd.DataFrame(d))
else:
    st.info("Sube Excel.")
