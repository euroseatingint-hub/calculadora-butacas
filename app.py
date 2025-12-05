import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Planificador Logístico V15", layout="wide", page_icon="🚛")

# --- FUNCIONES GRÁFICAS REALISTAS ---
def get_cube_lines_coords(x, y, z, dx, dy, dz):
    """ Coordenadas para wireframe """
    v = [[x, y, z], [x+dx, y, z], [x+dx, y+dy, z], [x, y+dy, z],
         [x, y, z+dz], [x+dx, y, z+dz], [x+dx, y+dy, z+dz], [x, y+dy, z+dz]]
    xe, ye, ze = [], [], []
    # Aristas inferiores
    for i, j in [(0,1), (1,2), (2,3), (3,0)]: 
        xe.extend([v[i][0], v[j][0], None]); ye.extend([v[i][1], v[j][1], None]); ze.extend([v[i][2], v[j][2], None])
    # Aristas superiores
    for i, j in [(4,5), (5,6), (6,7), (7,4)]:
        xe.extend([v[i][0], v[j][0], None]); ye.extend([v[i][1], v[j][1], None]); ze.extend([v[i][2], v[j][2], None])
    # Aristas verticales
    for i, j in [(0,4), (1,5), (2,6), (3,7)]:
        xe.extend([v[i][0], v[j][0], None]); ye.extend([v[i][1], v[j][1], None]); ze.extend([v[i][2], v[j][2], None])
    return xe, ye, ze

def draw_truck_realistic(bin_obj, w, h, d):
    fig = go.Figure()
    W, H, L = float(w), float(h), float(d)

    # 1. El Camión (Contenedor Wireframe Sólido)
    # Dibujamos el contorno con líneas gruesas
    lines_x = [0, W, W, 0, 0, 0, W, W, 0, 0, W, W, W, W, 0, 0]
    lines_y = [0, 0, L, L, 0, 0, 0, L, L, 0, 0, 0, L, L, L, L]
    lines_z = [0, 0, 0, 0, 0, H, H, H, H, H, H, 0, 0, H, H, 0]
    fig.add_trace(go.Scatter3d(x=lines_x, y=lines_y, z=lines_z, mode='lines', line=dict(color='#2C3E50', width=5), name='Contenedor', hoverinfo='none'))
    
    # 2. Cajas con Bordes y Colores Sólidos
    color_map = {'asiento': '#E74C3C', 'respaldo': '#3498DB', 'carcasa': '#F1C40F', 'costado': '#8E44AD', 'pal': '#795548'} # Palets marrones
    fallback_colors = ['#1ABC9C', '#D35400', '#27AE60', '#C0392B']

    for i, item in enumerate(bin_obj.items):
        dx, dz, dy = float(item.width), float(item.height), float(item.depth)
        x, z, y = float(item.position[0]), float(item.position[1]), float(item.position[2])
        
        # Determinar color
        c = fallback_colors[i % len(fallback_colors)]
        name_lower = item.name.lower()
        for key, val in color_map.items():
            if key in name_lower: c = val; break

        # A. Cuerpo Sólido (Mesh opaco para dar peso)
        fig.add_trace(go.Mesh3d(
            x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
            y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
            z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            color=c, opacity=1.0, flatshading=True, name=item.name, hoverinfo='name'
        ))
        
        # B. Bordes Negros Definidos
        lx, ly, lz = get_cube_lines_coords(x, y, z, dx, dy, dz)
        fig.add_trace(go.Scatter3d(x=lx, y=ly, z=lz, mode='lines', line=dict(color='black', width=3), showlegend=False, hoverinfo='skip'))

    # Configuración de Escena Realista
    fig.update_layout(
        scene=dict(
            # Eje Z (Alto) con suelo oscuro
            zaxis=dict(title='Alto (mm)', range=[0, H*1.05], backgroundcolor="#BDC3C7", gridcolor="white", showbackground=True, zerolinecolor="black", zerolinewidth=3),
            # Ejes X e Y (Suelo) más claros
            xaxis=dict(title='Ancho (mm)', range=[0, W*1.05], backgroundcolor="#ECF0F1", gridcolor="#BDC3C7"),
            yaxis=dict(title='Largo (mm)', range=[0, L*1.05], backgroundcolor="#ECF0F1", gridcolor="#BDC3C7"),
            aspectmode='data',
            # Iluminación para dar volumen
            camera=dict(eye=dict(x=1.7, y=-1.7, z=1.2), up=dict(x=0, y=0, z=1))
        ),
        margin=dict(l=0,r=0,b=0,t=30), height=700, title_text=f"Vista 3D - {bin_obj.name}"
    )
    return fig

# --- DATOS ---
@st.cache_data
def cargar_excel(archivo):
    xls = pd.ExcelFile(archivo)
    return {sheet: pd.read_excel(xls, sheet).rename(columns=lambda x: x.strip()) for sheet in xls.sheet_names}

def buscar_regla(nombre, df_reglas):
    nombre_c = str(nombre).lower().replace(" ", "")
    for idx, row in df_reglas.iterrows():
        regla_c = str(row['ID_Componente (Qué meto)']).lower().replace(" ", "")
        if regla_c in nombre_c or nombre_c in regla_c: return row
    return None

# --- APP ---
st.sidebar.title("🛠️ Panel Control")
if st.sidebar.button("🗑️ RESETEAR APP", type="primary"):
    st.session_state.clear()
    st.rerun()

st.title("🚛 Planificador Logístico V15 (Vista Realista)")

if 'pedido' not in st.session_state: st.session_state.pedido = []

# 1. CARGA
f = st.sidebar.file_uploader("1. Sube Excel", type=["xlsx"])
if f:
    try: dfs = cargar_excel(f); st.sidebar.success("Datos Cargados")
    except: st.error("Error Excel"); st.stop()

    # 2. PEDIDO
    st.header("1. Pedido")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: mod = st.selectbox("Modelo", dfs['RECETA_MODELOS']['Nombre_Modelo'].unique())
    with c2: cant = st.number_input("Cantidad", 1, value=50)
    with c3: 
        st.write(""); st.write("")
        if st.button("➕ Añadir"): st.session_state.pedido.append({"Modelo": mod, "Cantidad": cant})

    if st.session_state.pedido:
        st.dataframe(pd.DataFrame(st.session_state.pedido), use_container_width=True)
        if st.button("Borrar Lista"): st.session_state.pedido = []; st.rerun()
    
    st.divider()

    # 3. TRANSPORTE
    st.header("2. Transporte")
    ca, cb, cc = st.columns(3)
    with ca: modo = st.radio("Modo", ["📦 A Granel", "🧱 Paletizado"])
    with cb: vehic_nom = st.selectbox("Vehículo", dfs['VEHICULOS_CONTENEDORES']['Tipo'].unique())
    with cc:
        p_info = None
        if modo == "🧱 Paletizado":
            p_nom = st.selectbox("Palet", dfs['PALETS_SOPORTES']['Nombre'].unique())
            p_info = dfs['PALETS_SOPORTES'][dfs['PALETS_SOPORTES']['Nombre'] == p_nom].iloc[0]

    # 4. CÁLCULO
    if st.button("🚀 CALCULAR DISTRIBUCIÓN", type="primary", disabled=not st.session_state.pedido):
        
        vehiculo = dfs['VEHICULOS_CONTENEDORES'][dfs['VEHICULOS_CONTENEDORES']['Tipo'] == vehic_nom].iloc[0]
        items_load = []
        total_cajas_reales = 0
        
        with st.spinner("Procesando y optimizando..."):
            for l in st.session_state.pedido:
                receta = dfs['RECETA_MODELOS'][dfs['RECETA_MODELOS']['Nombre_Modelo'] == l['Modelo']]
                for _, row in receta.iterrows():
                    regla = buscar_regla(row['ID_Componente'], dfs['REGLAS_EMPAQUETADO'])
                    if regla is None: continue
                    caja_id = regla['ID_Caja (Dónde lo meto)']
                    try: caja = dfs['CATALOGO_CAJAS'][dfs['CATALOGO_CAJAS']['ID_Caja'] == caja_id].iloc[0]
                    except: continue
                    
                    L, W, H = caja['Largo_mm'], caja['Ancho_mm'], caja['Alto_mm']
                    if L < 200: L*=10; W*=10; H*=10 # Autocorrección mm

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
                    else:
                        w_b = (piezas_caja*peso_u) + caja['Peso_Vacio_kg']
                        for i in range(num_cajas):
                            items_load.append(Item(f"CJ-{row['ID_Componente'][:4]}-{i}", int(W), int(H), int(L), float(w_b)))

        if not items_load: st.error("No hay carga."); st.stop()

        # ORDENAR POR VOLUMEN (IMPORTANTE PARA GRAVEDAD)
        items_load.sort(key=lambda x: x.width * x.height * x.depth, reverse=True)

        # PACKING
        vol_total = sum([i.width * i.height * i.depth for i in items_load])
        vol_vehic = float(vehiculo['Ancho_Interior_mm']*vehiculo['Alto_Interior_mm']*vehiculo['Largo_Interior_mm'])
        n_bins = math.ceil(vol_total / (vol_vehic * 0.85))
        packer = Packer()
        for i in range(n_bins + 2):
            packer.add_bin(Bin(f"{vehiculo['Tipo']} #{i+1}", int(vehiculo['Ancho_Interior_mm']), int(vehiculo['Alto_Interior_mm']), int(vehiculo['Largo_Interior_mm']), int(vehiculo['Carga_Max_kg'])))
        for it in items_load: packer.add_item(it)
        packer.pack()
        used = [b for b in packer.bins if len(b.items) > 0]
        
        # --- RESULTADOS ---
        st.divider()
        st.success(f"✅ Resultado: **{len(used)}** vehículo(s)")
        k1, k2, k3 = st.columns(3)
        k1.metric("Bultos Cargados (Palets/Cajas)", sum([len(b.items) for b in used]))
        k2.metric("📦 Total Cajas Reales", total_cajas_reales)
        k3.metric("Peso Total", f"{int(sum([sum([float(it.weight) for it in b.items]) for b in used]))} kg")

        tabs = st.tabs([b.name for b in used])
        for i, b in enumerate(used):
            with tabs[i]:
                # GRÁFICO REALISTA
                st.plotly_chart(draw_truck_realistic(b, b.width, b.height, b.depth), use_container_width=True)
                
                # Tabla
                data = [{"Ref": x.name, "Medidas (AxLxA)": f"{int(x.width)}x{int(x.depth)}x{int(x.height)}", "Posición (X,Y,Z)": f"{int(float(x.position[0]))},{int(float(x.position[2]))},{int(float(x.position[1]))}"} for x in b.items]
                st.dataframe(pd.DataFrame(data), use_container_width=True)
else:
    st.info("Sube Excel.")
