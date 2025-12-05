import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Analizador Logístico V16", layout="wide", page_icon="🚛")

# --- FUNCIONES GRÁFICAS (SÓLIDAS) ---
def get_cube_edges(x, y, z, dx, dy, dz):
    """ Retorna las coordenadas de las líneas negras (bordes) """
    # Base
    xe = [x, x+dx, x+dx, x, x, None]
    ye = [y, y, y+dy, y+dy, y, None]
    ze = [z, z, z, z, z, None]
    # Techo
    xe += [x, x+dx, x+dx, x, x, None]
    ye += [y, y, y+dy, y+dy, y, None]
    ze += [z+dz, z+dz, z+dz, z+dz, z+dz, None]
    # Pilares
    xe += [x, x, None, x+dx, x+dx, None, x+dx, x+dx, None, x, x, None]
    ye += [y, y, None, y, y, None, y+dy, y+dy, None, y+dy, y+dy, None]
    ze += [z, z+dz, None, z, z+dz, None, z, z+dz, None, z, z+dz, None]
    return xe, ye, ze

def draw_truck_analysis(bin_obj, w, h, d):
    fig = go.Figure()
    W, H, L = float(w), float(h), float(d)

    # 1. El Contenedor (Sólido translúcido para referencia)
    fig.add_trace(go.Mesh3d(
        x=[0, W, W, 0, 0, W, W, 0],
        y=[0, 0, L, L, 0, 0, L, L],
        z=[0, 0, 0, 0, H, H, H, H],
        i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
        j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
        k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
        color='gray', opacity=0.1, name='Espacio Aéreo'
    ))
    
    # Bordes del contenedor
    lx, ly, lz = get_cube_edges(0, 0, 0, W, L, H)
    fig.add_trace(go.Scatter3d(x=lx, y=ly, z=lz, mode='lines', line=dict(color='black', width=5), name='Límites Camión', hoverinfo='none'))

    # 2. Cajas
    # Colores fijos
    colors = {'asiento': '#E74C3C', 'respaldo': '#3498DB', 'carcasa': '#F1C40F', 'costado': '#8E44AD', 'pal': '#795548', 'base': '#95A5A6'}
    fallback = ['#16A085', '#D35400', '#2C3E50', '#8E44AD']

    for i, item in enumerate(bin_obj.items):
        # Mapeo: py3dbp (w,h,d) -> Plotly (x, z, y)
        # width -> X (Ancho)
        # height -> Z (Alto)
        # depth -> Y (Largo/Profundidad)
        dx, dz, dy = float(item.width), float(item.height), float(item.depth)
        x, z, y = float(item.position[0]), float(item.position[1]), float(item.position[2])

        # Color
        c = fallback[i % len(fallback)]
        for k, v in colors.items():
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
            xaxis=dict(title='Ancho (X)', range=[0, W*1.05], backgroundcolor="#ffffff", gridcolor="#cccccc"),
            yaxis=dict(title='Largo (Y)', range=[0, L*1.05], backgroundcolor="#ffffff", gridcolor="#cccccc"),
            zaxis=dict(title='Alto (Z)', range=[0, H*1.05], backgroundcolor="#eeeeee", gridcolor="white"),
            aspectmode='data',
            camera=dict(eye=dict(x=1.5, y=-1.5, z=1.5))
        ),
        margin=dict(l=0, r=0, b=0, t=30), height=700,
        title="Vista 3D: Eje Z es la Altura (Gravedad)"
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
    st.session_state.clear(); st.rerun()

st.title("🚛 Analizador de Carga V16 (Modo Detallado)")

if 'pedido' not in st.session_state: st.session_state.pedido = []

# 1. CARGA
f = st.sidebar.file_uploader("1. Sube Excel", type=["xlsx"])
if f:
    try: dfs = cargar_excel(f); st.sidebar.success("Excel OK")
    except: st.error("Error Excel"); st.stop()

    # 2. PEDIDO
    st.header("1. Tu Pedido")
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
    st.header("2. Vehículo y Formato")
    ca, cb, cc = st.columns(3)
    with ca: modo = st.radio("Formato", ["📦 A Granel", "🧱 Paletizado"])
    with cb: vehic_nom = st.selectbox("Vehículo", dfs['VEHICULOS_CONTENEDORES']['Tipo'].unique())
    with cc:
        p_info = None
        if modo == "🧱 Paletizado":
            p_nom = st.selectbox("Palet", dfs['PALETS_SOPORTES']['Nombre'].unique())
            p_info = dfs['PALETS_SOPORTES'][dfs['PALETS_SOPORTES']['Nombre'] == p_nom].iloc[0]

    # 4. CÁLCULO
    if st.button("🚀 ANALIZAR CARGA (1 CAMIÓN)", type="primary", disabled=not st.session_state.pedido):
        
        vehiculo = dfs['VEHICULOS_CONTENEDORES'][dfs['VEHICULOS_CONTENEDORES']['Tipo'] == vehic_nom].iloc[0]
        
        # A. GENERAR BULTOS
        items_load = []
        volumen_carga_total = 0
        peso_carga_total = 0
        
        with st.spinner("Generando bultos..."):
            for l in st.session_state.pedido:
                receta = dfs['RECETA_MODELOS'][dfs['RECETA_MODELOS']['Nombre_Modelo'] == l['Modelo']]
                for _, row in receta.iterrows():
                    regla = buscar_regla(row['ID_Componente'], dfs['REGLAS_EMPAQUETADO'])
                    if regla is None: continue
                    
                    try: caja = dfs['CATALOGO_CAJAS'][dfs['CATALOGO_CAJAS']['ID_Caja'] == regla['ID_Caja (Dónde lo meto)']].iloc[0]
                    except: continue

                    # Corrección MM
                    L, W, H = caja['Largo_mm'], caja['Ancho_mm'], caja['Alto_mm']
                    if L < 200: L*=10; W*=10; H*=10
                    
                    try: peso_u = dfs['COMPONENTES'][dfs['COMPONENTES']['ID_Componente'] == regla['ID_Componente (Qué meto)']].iloc[0]['Peso_Neto_Unitario_kg']
                    except: peso_u = 5
                    
                    piezas_caja = regla['Cantidad_x_Caja']
                    num_cajas = math.ceil((l['Cantidad'] * row['Cantidad_x_Butaca']) / piezas_caja)
                    
                    if modo == "🧱 Paletizado":
                        base_L = int(p_info['Largo_mm'] / L) * int(p_info['Ancho_mm'] / W)
                        base_W = int(p_info['Largo_mm'] / W) * int(p_info['Ancho_mm'] / L)
                        base = max(base_L, base_W)
                        if base == 0: continue
                        
                        h_util = vehiculo['Alto_Interior_mm'] * 0.98
                        capas = min(caja['Max_Apilable'], int((h_util - p_info['Alto_Base_mm'])/H))
                        if capas < 1: capas = 1
                        
                        items_p_palet = base * capas
                        n_palets = math.ceil(num_cajas / items_p_palet)
                        
                        h_final = p_info['Alto_Base_mm'] + (capas * H)
                        w_p = (items_p_palet * ((piezas_caja*peso_u) + caja['Peso_Vacio_kg'])) + p_info['Peso_Vacio_kg']
                        
                        for p in range(n_palets):
                            items_load.append(Item(f"PAL-{row['ID_Componente'][:4]}-{p}", int(p_info['Ancho_mm']), int(h_final), int(p_info['Largo_mm']), float(w_p)))
                            volumen_carga_total += (int(p_info['Ancho_mm']) * int(h_final) * int(p_info['Largo_mm']))
                            peso_carga_total += w_p
                    else:
                        w_b = (piezas_caja*peso_u) + caja['Peso_Vacio_kg']
                        for i in range(num_cajas):
                            items_load.append(Item(f"CJ-{row['ID_Componente'][:4]}-{i}", int(W), int(H), int(L), float(w_b)))
                            volumen_carga_total += (int(W) * int(H) * int(L))
                            peso_carga_total += w_b

        if not items_load: st.error("No hay carga."); st.stop()

        # B. ANÁLISIS DE VOLUMEN (KPIs)
        vol_camion = float(vehiculo['Ancho_Interior_mm']*vehiculo['Alto_Interior_mm']*vehiculo['Largo_Interior_mm'])
        pct_ocupacion_teorica = (volumen_carga_total / vol_camion) * 100
        
        st.info(f"""
        📊 **ANÁLISIS DE VIABILIDAD (ANTES DE CARGAR)**
        - Volumen de tu Carga: **{round(volumen_carga_total/1e9, 2)} m³**
        - Capacidad del Vehículo: **{round(vol_camion/1e9, 2)} m³**
        - Ocupación Teórica: **{round(pct_ocupacion_teorica, 1)}%**
        """)

        # C. PACKING (SOLO 1 CAMIÓN)
        # Ordenamos por AREA DE LA BASE (Ancho x Largo) descendente para crear "Suelo"
        # py3dbp: w=Ancho, h=Alto, d=Largo -> Base = w * d
        items_load.sort(key=lambda x: x.width * x.depth, reverse=True)

        packer = Packer()
        # Solo 1 bin para analizar por qué falla o cómo queda
        packer.add_bin(Bin(vehiculo['Tipo'], int(vehiculo['Ancho_Interior_mm']), int(vehiculo['Alto_Interior_mm']), int(vehiculo['Largo_Interior_mm']), int(vehiculo['Carga_Max_kg'])))
        
        for it in items_load: packer.add_item(it)
        packer.pack()
        
        b = packer.bins[0] # El único camión
        
        # --- RESULTADOS ---
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Bultos que CABEN", len(b.items))
        c2.metric("Bultos FUERA (No caben)", len(b.unfitted_items), delta_color="inverse")
        
        # Ocupación Real
        if len(b.items) > 0:
            v_real = sum([i.width * i.height * i.depth for i in b.items])
            pct_real = (v_real / vol_camion) * 100
            c3.metric("Ocupación Real 3D", f"{round(pct_real, 1)}%")
        else:
            c3.metric("Ocupación Real", "0%")

        # VISUALIZACIÓN
        st.subheader("Vista 3D (Carga Real)")
        if len(b.items) > 0:
            st.plotly_chart(draw_truck_analysis(b, b.width, b.height, b.depth), use_container_width=True)
        else:
            st.warning("El camión está vacío. Revisa si el primer bulto es más grande que el camión.")

        # TABLA DE SOBRANTES
        if len(b.unfitted_items) > 0:
            st.error(f"❌ **{len(b.unfitted_items)} Bultos se han quedado fuera.**")
            with st.expander("Ver lista de lo que NO cabe"):
                data_err = [{"Ref": x.name, "Medidas": f"{int(x.width)}x{int(x.depth)}x{int(x.height)}"} for x in b.unfitted_items]
                st.dataframe(pd.DataFrame(data_err))
else:
    st.info("Sube Excel.")
