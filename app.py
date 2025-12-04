import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Calculadora Logística V11", layout="wide", page_icon="📦")

# --- FUNCIONES DE DIBUJO ---
def draw_cube_with_edges(fig, x, y, z, dx, dy, dz, color, name):
    """ Dibuja un cubo sólido con bordes negros para mejor visibilidad """
    # 1. Caras Sólidas (Mesh)
    fig.add_trace(go.Mesh3d(
        x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
        y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
        z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
        i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
        j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
        k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
        color=color, opacity=0.9, flatshading=True, name=name, hoverinfo='name'
    ))
    
    # 2. Bordes (Líneas)
    # Definir la secuencia de líneas para dibujar el cubo de un trazo (o varios)
    lines_x = [x, x+dx, x+dx, x, x, x, x+dx, x+dx, x, x, x+dx, x+dx, x+dx, x+dx, x, x]
    lines_y = [y, y, y+dy, y+dy, y, y, y, y+dy, y+dy, y, y, y, y+dy, y+dy, y+dy, y]
    lines_z = [z, z, z, z, z, z+dz, z+dz, z+dz, z+dz, z+dz, z+dz, z, z, z+dz, z+dz, z+dz]
    
    fig.add_trace(go.Scatter3d(
        x=lines_x, y=lines_y, z=lines_z,
        mode='lines', line=dict(color='black', width=3), hoverinfo='none', showlegend=False
    ))

def draw_truck_3d_final(bin_obj, w_mm, h_mm, d_mm):
    fig = go.Figure()
    W, H, L = float(w_mm), float(h_mm), float(d_mm)

    # Dibujar Contenedor (Solo contorno)
    lines_x = [0, W, W, 0, 0, 0, W, W, 0, 0, W, W, W, W, 0, 0]
    lines_y = [0, 0, L, L, 0, 0, 0, L, L, 0, 0, 0, L, L, L, L]
    lines_z = [0, 0, 0, 0, 0, H, H, H, H, H, H, 0, 0, H, H, 0]
    
    fig.add_trace(go.Scatter3d(x=lines_x, y=lines_y, z=lines_z, mode='lines', line=dict(color='grey', width=4), name='Contenedor'))

    # Dibujar Cajas
    # Paleta de colores extendida
    colors = ['#FF5733', '#33FF57', '#3357FF', '#F333FF', '#33FFF5', '#F5FF33', '#FF8C33', '#8C33FF']
    
    for item in bin_obj.items:
        # Recuperar dimensiones y posiciones
        # Mapeo: py3dbp (w, h, d) -> Plotly (x, z, y)
        dx, dz, dy = float(item.width), float(item.height), float(item.depth)
        x, z, y = float(item.position[0]), float(item.position[1]), float(item.position[2])
        
        # Color basado en el nombre (intentando agrupar por tipo)
        try:
            seed_text = item.name.split('-')[1] # Usar la parte del componente (ej: asiento)
        except:
            seed_text = item.name
        
        c = colors[hash(seed_text) % len(colors)]
        
        draw_cube_with_edges(fig, x, y, z, dx, dy, dz, c, item.name)

    # Configuración de Escena (Vista Horizontal)
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Ancho (mm)', range=[0, W+100], backgroundcolor="#f0f2f6"),
            yaxis=dict(title='Largo (mm)', range=[0, L+100], backgroundcolor="#f0f2f6"),
            zaxis=dict(title='Alto (mm)', range=[0, H+100], backgroundcolor="#dce1e8"),
            aspectmode='data', # Proporción real 1:1
            camera=dict(eye=dict(x=1.5, y=0.5, z=1.5))
        ),
        margin=dict(l=0, r=0, b=0, t=0), height=600, showlegend=False
    )
    return fig

# --- FUNCIONES DE DATOS ---
@st.cache_data
def cargar_excel(archivo):
    xls = pd.ExcelFile(archivo)
    return {sheet: pd.read_excel(xls, sheet).rename(columns=lambda x: x.strip()) for sheet in xls.sheet_names}

def buscar_regla_inteligente(componente_id, df_reglas):
    """ Intenta encontrar la regla incluso si el ID no es exacto """
    # 1. Búsqueda exacta
    regla = df_reglas[df_reglas['ID_Componente (Qué meto)'] == componente_id]
    if not regla.empty: return regla
    
    # 2. Búsqueda por coincidencia parcial (ignora mayúsculas/espacios)
    comp_clean = componente_id.lower().replace(" ", "")
    
    def match_loose(val):
        if not isinstance(val, str): return False
        return val.lower().replace(" ", "") in comp_clean or comp_clean in val.lower().replace(" ", "")
        
    regla_loose = df_reglas[df_reglas['ID_Componente (Qué meto)'].apply(match_loose)]
    return regla_loose

# --- APP PRINCIPAL ---
st.title("🚛 Calculadora Logística PRO V11")

if 'pedido' not in st.session_state: st.session_state.pedido = []

# 1. CARGA DE DATOS
st.sidebar.header("1. Datos")
f = st.sidebar.file_uploader("Sube 'datos.xlsx'", type=["xlsx"])

if f:
    try:
        dfs = cargar_excel(f)
        st.sidebar.success("✅ Datos cargados")
    except Exception as e:
        st.error(f"Error Excel: {e}"); st.stop()

    # 2. PEDIDO
    st.header("🛒 Configurar Pedido")
    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
    with c1: mod = st.selectbox("Modelo", dfs['RECETA_MODELOS']['Nombre_Modelo'].unique())
    with c2: cant = st.number_input("Cantidad", 1, value=50)
    with c3: 
        st.write(""); st.write("")
        if st.button("➕ Añadir"): st.session_state.pedido.append({"Modelo": mod, "Cantidad": cant})
    with c4:
        st.write(""); st.write("")
        if st.button("🗑️ Borrar"): st.session_state.pedido = []; st.rerun()

    if st.session_state.pedido:
        st.dataframe(pd.DataFrame(st.session_state.pedido), use_container_width=True)

    st.divider()

    # 3. TRANSPORTE
    st.header("⚙️ Configuración")
    cA, cB, cC = st.columns(3)
    with cA: modo = st.radio("Método", ["📦 A Granel", "🧱 Paletizado"])
    with cB: vehic_nom = st.selectbox("Vehículo", dfs['VEHICULOS_CONTENEDORES']['Tipo'].unique())
    with cC:
        p_info = None
        if modo == "🧱 Paletizado":
            p_nom = st.selectbox("Palet", dfs['PALETS_SOPORTES']['Nombre'].unique())
            p_info = dfs['PALETS_SOPORTES'][dfs['PALETS_SOPORTES']['Nombre'] == p_nom].iloc[0]

    # 4. CÁLCULO
    if st.button("🚀 CALCULAR", type="primary", disabled=not st.session_state.pedido):
        
        vehiculo = dfs['VEHICULOS_CONTENEDORES'][dfs['VEHICULOS_CONTENEDORES']['Tipo'] == vehic_nom].iloc[0]
        items_load = []
        warnings_log = []
        
        with st.spinner("Procesando..."):
            for l in st.session_state.pedido:
                receta = dfs['RECETA_MODELOS'][dfs['RECETA_MODELOS']['Nombre_Modelo'] == l['Modelo']]
                
                for _, row in receta.iterrows():
                    comp_id = row['ID_Componente']
                    # Usamos el buscador inteligente
                    regla = buscar_regla_inteligente(comp_id, dfs['REGLAS_EMPAQUETADO'])
                    
                    if regla.empty:
                        warnings_log.append(f"⚠️ Ignorado: {comp_id} (No hay regla de empaquetado)")
                        continue
                    
                    # Tomar la primera coincidencia
                    caja_id = regla.iloc[0]['ID_Caja (Dónde lo meto)']
                    try:
                        caja = dfs['CATALOGO_CAJAS'][dfs['CATALOGO_CAJAS']['ID_Caja'] == caja_id].iloc[0]
                    except:
                        warnings_log.append(f"❌ Error: La caja {caja_id} de la regla no existe en el catálogo.")
                        continue

                    # Corregir unidades (cm -> mm) si es necesario
                    dim_caja = {'L': caja['Largo_mm'], 'W': caja['Ancho_mm'], 'H': caja['Alto_mm']}
                    for k, v in dim_caja.items():
                        if v < 200: dim_caja[k] = v * 10 # Autocorrección cm -> mm
                    
                    # Peso unitario
                    try:
                        peso_u = dfs['COMPONENTES'][dfs['COMPONENTES']['ID_Componente'] == regla.iloc[0]['ID_Componente (Qué meto)']].iloc[0]['Peso_Neto_Unitario_kg']
                    except:
                        peso_u = 5.0 # Valor por defecto si falla
                    
                    total_piezas = l['Cantidad'] * row['Cantidad_x_Butaca']
                    piezas_caja = regla.iloc[0]['Cantidad_x_Caja']
                    num_cajas = math.ceil(total_piezas / piezas_caja)
                    
                    if modo == "🧱 Paletizado":
                        # Lógica Paletizado
                        base_L = int(p_info['Largo_mm'] / dim_caja['L']) * int(p_info['Ancho_mm'] / dim_caja['W'])
                        base_W = int(p_info['Largo_mm'] / dim_caja['W']) * int(p_info['Ancho_mm'] / dim_caja['L'])
                        base = max(base_L, base_W)
                        
                        if base == 0: 
                            warnings_log.append(f"❌ La caja {caja_id} es más grande que el palet.")
                            continue
                            
                        h_util = vehiculo['Alto_Interior_mm'] * 0.98
                        capas = min(caja['Max_Apilable'], int((h_util - p_info['Alto_Base_mm'])/dim_caja['H']))
                        if capas < 1: capas = 1
                        
                        items_por_palet = base * capas
                        n_palets = math.ceil(num_cajas / items_por_palet)
                        
                        h_p = p_info['Alto_Base_mm'] + (capas * dim_caja['H'])
                        w_p = (items_por_palet * ((piezas_caja*peso_u) + caja['Peso_Vacio_kg'])) + p_info['Peso_Vacio_kg']
                        
                        # Generar descripción del contenido
                        contenido_desc = f"{items_por_palet} cajas de {comp_id}"
                        
                        for p in range(n_palets):
                            items_load.append(Item(
                                f"PAL-{comp_id}-{p}", # Nombre único
                                int(p_info['Ancho_mm']), int(h_p), int(p_info['Largo_mm']), float(w_p)
                            ))
                    else:
                        # Lógica Granel
                        w_b = (piezas_caja*peso_u) + caja['Peso_Vacio_kg']
                        for i in range(num_cajas):
                            items_load.append(Item(
                                f"CJ-{comp_id}-{i}", 
                                int(dim_caja['W']), int(dim_caja['H']), int(dim_caja['L']), float(w_b)
                            ))

        # --- MOSTRAR AVISOS ---
        if warnings_log:
            with st.expander("⚠️ Alertas de Datos (Revisar)", expanded=True):
                for w in set(warnings_log): st.write(w)
                st.caption("Si faltan componentes, revisa que los nombres en RECETA y REGLAS coincidan.")

        if not items_load:
            st.error("No hay carga válida para procesar."); st.stop()

        # --- PACKING ---
        packer = Packer()
        # Dimensiones Vehículo (W=Ancho, H=Alto, D=Largo)
        bin_dims = [int(vehiculo['Ancho_Interior_mm']), int(vehiculo['Alto_Interior_mm']), int(vehiculo['Largo_Interior_mm'])]
        
        # Crear flota dinámica
        for i in range(20):
            packer.add_bin(Bin(f"{vehiculo['Tipo']} #{i+1}", bin_dims[0], bin_dims[1], bin_dims[2], int(vehiculo['Carga_Max_kg'])))
        
        for it in items_load: packer.add_item(it)
        packer.pack()
        
        # Filtrar vacíos
        used_bins = [b for b in packer.bins if len(b.items) > 0]
        
        # --- RESULTADOS ---
        st.divider()
        st.success(f"✅ RESULTADO: **{len(used_bins)} Vehículo(s)** necesario(s)")
        
        tabs = st.tabs([b.name for b in used_bins])
        for i, b in enumerate(used_bins):
            with tabs[i]:
                # Métricas
                vol_u = sum([float(it.width)*float(it.height)*float(it.depth) for it in b.items])
                vol_t = float(b.width)*float(b.height)*float(b.depth)
                pct = (vol_u/vol_t)*100
                peso = sum([float(it.weight) for it in b.items])
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Ocupación", f"{round(pct,1)}%")
                c2.metric("Peso", f"{int(peso)} kg")
                c3.metric("Bultos", len(b.items))
                
                # Checkbox 3D
                if st.checkbox(f"👁️ Ver 3D ({b.name})", value=True, key=f"v3d_{i}"):
                    st.plotly_chart(draw_truck_3d_final(b, b.width, b.height, b.depth), use_container_width=True)
                
                # Tabla Manifiesto Mejorada
                data_det = []
                for item in b.items:
                    # Extraer componente del nombre para mostrarlo limpio
                    try: nom_comp = item.name.split('-')[1]
                    except: nom_comp = item.name
                    
                    data_det.append({
                        "Bulto ID": item.name,
                        "Contenido": nom_comp,
                        "Medidas (mm)": f"{int(item.width)} x {int(item.depth)} x {int(item.height)}",
                        "Peso": f"{int(item.weight)} kg"
                    })
                st.dataframe(pd.DataFrame(data_det), use_container_width=True)
else:
    st.info("👋 Sube tu Excel.")
