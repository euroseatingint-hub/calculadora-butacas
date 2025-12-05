import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Visualizador Logístico V13", layout="wide", page_icon="🚛")

# --- FUNCIONES GRÁFICAS (Bordes + Colores Fijos) ---
def get_cube_lines_coords(x, y, z, dx, dy, dz):
    """ Genera las coordenadas para dibujar las líneas de un cubo (bordes) """
    # 8 Vértices
    v = [
        [x, y, z], [x+dx, y, z], [x+dx, y+dy, z], [x, y+dy, z], # Base 0-3
        [x, y, z+dz], [x+dx, y, z+dz], [x+dx, y+dy, z+dz], [x, y+dy, z+dz] # Techo 4-7
    ]
    # 12 Aristas (con None para cortar la línea y no hacer diagonales raras)
    xe, ye, ze = [], [], []
    # Base
    for i in [0,1, 1,2, 2,3, 3,0]: 
        xe.extend([v[i][0]]); ye.extend([v[i][1]]); ze.extend([v[i][2]])
    xe.append(None); ye.append(None); ze.append(None)
    # Techo
    for i in [4,5, 5,6, 6,7, 7,4]:
        xe.extend([v[i][0]]); ye.extend([v[i][1]]); ze.extend([v[i][2]])
    xe.append(None); ye.append(None); ze.append(None)
    # Columnas
    for i, j in [(0,4), (1,5), (2,6), (3,7)]:
        xe.extend([v[i][0], v[j][0], None])
        ye.extend([v[i][1], v[j][1], None])
        ze.extend([v[i][2], v[j][2], None])
        
    return xe, ye, ze

def draw_truck_final(bin_obj, w, h, d):
    fig = go.Figure()
    
    # 1. Contenedor (Gris claro)
    cx, cy, cz = get_cube_lines_coords(0, 0, 0, float(w), float(d), float(h))
    fig.add_trace(go.Scatter3d(x=cx, y=cy, z=cz, mode='lines', line=dict(color='lightgrey', width=4), name='Contenedor'))
    
    # 2. Cajas/Palets
    # Colores fijos para tipos comunes para consistencia visual
    color_map = {
        'asiento': '#E74C3C', # Rojo
        'respaldo': '#3498DB', # Azul
        'carcasa': '#F1C40F', # Amarillo
        'costado': '#9B59B6', # Violeta
        'brazo': '#9B59B6',
        'herraje': '#2ECC71', # Verde
        'base': '#7F8C8D'     # Gris
    }
    fallback_colors = ['#E67E22', '#1ABC9C', '#34495E', '#D35400']
    
    for item in bin_obj.items:
        # Mapeo Ejes: py3dbp(w,h,d) -> Plotly(x, z=alto, y=profundidad)
        dx, dz, dy = float(item.width), float(item.height), float(item.depth)
        x, z, y = float(item.position[0]), float(item.position[1]), float(item.position[2])
        
        # Determinar color
        name_lower = item.name.lower()
        c = fallback_colors[hash(item.name) % len(fallback_colors)]
        for key, color in color_map.items():
            if key in name_lower:
                c = color
                break
        
        # A. Cubo Sólido (Semi-transparente)
        fig.add_trace(go.Mesh3d(
            x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
            y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
            z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            color=c, opacity=0.8, flatshading=True, name=item.name, hoverinfo='name'
        ))
        
        # B. Bordes Negros (Líneas)
        lx, ly, lz = get_cube_lines_coords(x, y, z, dx, dy, dz)
        fig.add_trace(go.Scatter3d(
            x=lx, y=ly, z=lz, mode='lines', line=dict(color='black', width=3), hoverinfo='skip', showlegend=False
        ))

    # Configuración Escena
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Ancho (mm)', range=[0, float(w)], backgroundcolor="#FDFEFE"),
            yaxis=dict(title='Largo (mm)', range=[0, float(d)], backgroundcolor="#FDFEFE"),
            zaxis=dict(title='Alto (mm)', range=[0, float(h)], backgroundcolor="#EBEDEF"),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=0), height=600, showlegend=False
    )
    return fig

# --- DATOS ---
@st.cache_data
def cargar_excel(archivo):
    xls = pd.ExcelFile(archivo)
    return {sheet: pd.read_excel(xls, sheet).rename(columns=lambda x: x.strip()) for sheet in xls.sheet_names}

def buscar_regla(nombre, df_reglas):
    """ Búsqueda 'fuzzy' simple """
    nombre_c = str(nombre).lower().replace(" ", "")
    for idx, row in df_reglas.iterrows():
        regla_c = str(row['ID_Componente (Qué meto)']).lower().replace(" ", "")
        # Coincidencia si uno contiene al otro
        if regla_c in nombre_c or nombre_c in regla_c:
            return row
    return None

# --- APP ---
st.sidebar.title("🛠️ Opciones")
if st.sidebar.button("🗑️ RESETEAR APP"):
    st.session_state.clear()
    st.rerun()

st.title("🚛 Visualizador Logístico V13")

# Inicializar Estado
if 'pedido' not in st.session_state: st.session_state.pedido = []

# 1. CARGA
f = st.sidebar.file_uploader("1. Sube Excel", type=["xlsx"])
if f:
    try:
        dfs = cargar_excel(f)
        st.sidebar.success("✅ Datos OK")
    except:
        st.error("Error al leer Excel"); st.stop()

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
    if st.button("🚀 CALCULAR", type="primary", disabled=not st.session_state.pedido):
        
        vehiculo = dfs['VEHICULOS_CONTENEDORES'][dfs['VEHICULOS_CONTENEDORES']['Tipo'] == vehic_nom].iloc[0]
        items_load = []
        log_missing = []
        
        with st.spinner("Procesando..."):
            for l in st.session_state.pedido:
                receta = dfs['RECETA_MODELOS'][dfs['RECETA_MODELOS']['Nombre_Modelo'] == l['Modelo']]
                
                for _, row in receta.iterrows():
                    comp_id = row['ID_Componente']
                    
                    # BUSCAR REGLA
                    regla_row = buscar_regla(comp_id, dfs['REGLAS_EMPAQUETADO'])
                    
                    if regla_row is None:
                        log_missing.append(comp_id)
                        continue
                    
                    # DATOS CAJA
                    caja_id = regla_row['ID_Caja (Dónde lo meto)']
                    try:
                        caja = dfs['CATALOGO_CAJAS'][dfs['CATALOGO_CAJAS']['ID_Caja'] == caja_id].iloc[0]
                    except:
                        st.error(f"La caja {caja_id} no existe en el catálogo."); st.stop()

                    # Corrección CM -> MM
                    dim = {'L': caja['Largo_mm'], 'W': caja['Ancho_mm'], 'H': caja['Alto_mm']}
                    for k,v in dim.items(): 
                        if v < 200: dim[k] = v * 10 
                    
                    # Peso
                    try: 
                        peso_u = dfs['COMPONENTES'][dfs['COMPONENTES']['ID_Componente'] == regla_row['ID_Componente (Qué meto)']].iloc[0]['Peso_Neto_Unitario_kg']
                    except: peso_u = 5

                    total_piezas = l['Cantidad'] * row['Cantidad_x_Butaca']
                    piezas_caja = regla_row['Cantidad_x_Caja']
                    num_cajas = math.ceil(total_piezas / piezas_caja)
                    
                    if modo == "🧱 Paletizado":
                        # Lógica Palet
                        base_L = int(p_info['Largo_mm'] / dim['L']) * int(p_info['Ancho_mm'] / dim['W'])
                        base_W = int(p_info['Largo_mm'] / dim['W']) * int(p_info['Ancho_mm'] / dim['L'])
                        base = max(base_L, base_W)
                        
                        if base == 0: st.error(f"Caja {caja_id} no cabe en palet"); st.stop()
                        
                        h_util = vehiculo['Alto_Interior_mm'] * 0.95
                        capas = min(caja['Max_Apilable'], int((h_util - p_info['Alto_Base_mm'])/dim['H']))
                        if capas < 1: capas = 1
                        
                        items_por_palet = base * capas
                        n_palets = math.ceil(num_cajas / items_por_palet)
                        
                        h_p = p_info['Alto_Base_mm'] + (capas * dim['H'])
                        w_p = (items_por_palet * ((piezas_caja*peso_u) + caja['Peso_Vacio_kg'])) + p_info['Peso_Vacio_kg']
                        
                        for p in range(n_palets):
                            items_load.append(Item(f"PAL-{comp_id}-{p}", int(p_info['Ancho_mm']), int(h_p), int(p_info['Largo_mm']), float(w_p)))
                    else:
                        w_b = (piezas_caja*peso_u) + caja['Peso_Vacio_kg']
                        for i in range(num_cajas):
                            items_load.append(Item(f"CJ-{comp_id}-{i}", int(dim['W']), int(dim['H']), int(dim['L']), float(w_b)))

        # ALERTA DE COMPONENTES PERDIDOS
        if log_missing:
            st.warning(f"⚠️ ¡ATENCIÓN! No se han encontrado reglas para estos componentes: {list(set(log_missing))}. Revisa los nombres en el Excel.")

        if not items_load:
            st.error("No hay bultos para cargar.")
        else:
            # PACKING INTELIGENTE (Solo los camiones necesarios)
            # Calculamos volumen total para estimar
            vol_total = sum([i.width * i.height * i.depth for i in items_load])
            vol_camion = float(vehiculo['Ancho_Interior_mm']*vehiculo['Alto_Interior_mm']*vehiculo['Largo_Interior_mm'])
            min_camiones = math.ceil(vol_total / (vol_camion * 0.9)) # 90% eficiencia estimada
            
            packer = Packer()
            # Creamos un número razonable de camiones (minimo estimado + 2 extra)
            for i in range(min_camiones + 2):
                packer.add_bin(Bin(f"{vehiculo['Tipo']} #{i+1}", int(vehiculo['Ancho_Interior_mm']), int(vehiculo['Alto_Interior_mm']), int(vehiculo['Largo_Interior_mm']), int(vehiculo['Carga_Max_kg'])))
            
            for it in items_load: packer.add_item(it)
            packer.pack()
            
            used_bins = [b for b in packer.bins if len(b.items) > 0]
            
            st.success(f"✅ Se necesitan: **{len(used_bins)}** vehículo(s)")
            
            tabs = st.tabs([b.name for b in used_bins])
            for i, b in enumerate(used_bins):
                with tabs[i]:
                    st.plotly_chart(draw_truck_final(b, b.width, b.height, b.depth), use_container_width=True)
                    
                    # Tabla
                    d = [{"ID": x.name, "Dimensiones": f"{int(x.width)}x{int(x.depth)}x{int(x.height)}", "Peso": f"{int(x.weight)}"} for x in b.items]
                    st.dataframe(pd.DataFrame(d), use_container_width=True)
else:
    st.info("Sube el Excel.")
