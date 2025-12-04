import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- CONFIGURACIÓN PÁGINA ---
st.set_page_config(page_title="Calculadora Logística V10", layout="wide", page_icon="📦")

# --- FUNCIONES ---
@st.cache_data
def cargar_excel(archivo):
    xls = pd.ExcelFile(archivo)
    return {sheet: pd.read_excel(xls, sheet).rename(columns=lambda x: x.strip()) for sheet in xls.sheet_names}

def draw_container_3d(bin_obj, w_mm, h_mm, d_mm, title):
    """ Dibuja el contenedor/camión en horizontal """
    fig = go.Figure()
    
    W, H, L = float(w_mm), float(h_mm), float(d_mm)
    
    # 1. Contenedor (Wireframe)
    # Suelo
    fig.add_trace(go.Scatter3d(x=[0, W, W, 0, 0], y=[0, 0, L, L, 0], z=[0, 0, 0, 0, 0],
                               mode='lines', line=dict(color='black', width=3), name='Suelo', hoverinfo='none'))
    # Techo
    fig.add_trace(go.Scatter3d(x=[0, W, W, 0, 0], y=[0, 0, L, L, 0], z=[H, H, H, H, H],
                               mode='lines', line=dict(color='lightgrey', width=2), name='Techo', hoverinfo='none'))
    # Paredes verticales
    for xc, yc in [(0,0), (W,0), (W,L), (0,L)]:
        fig.add_trace(go.Scatter3d(x=[xc, xc], y=[yc, yc], z=[0, H], mode='lines', line=dict(color='lightgrey', width=2), showlegend=False, hoverinfo='none'))

    # 2. Bultos
    colors = ['#E74C3C', '#3498DB', '#F1C40F', '#2ECC71', '#9B59B6', '#E67E22', '#1ABC9C']
    
    for item in bin_obj.items:
        # Recuperar dimensiones originales
        # Mapeo: py3dbp (w,h,d) -> Plotly (x, z, y)
        dx, dz, dy = float(item.width), float(item.height), float(item.depth)
        x, z, y = float(item.position[0]), float(item.position[1]), float(item.position[2])
        
        c = colors[hash(item.name.split('-')[1]) % len(colors)]
        
        fig.add_trace(go.Mesh3d(
            x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
            y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
            z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            color=c, opacity=1.0, flatshading=True, name=item.name, hoverinfo='name'
        ))

    fig.update_layout(
        title=title,
        scene=dict(
            xaxis=dict(title='Ancho (mm)', range=[0, W+100], backgroundcolor="#F4F6F6"),
            yaxis=dict(title='Largo (mm)', range=[0, L+100], backgroundcolor="#F4F6F6"),
            zaxis=dict(title='Alto (mm)', range=[0, H+100], backgroundcolor="#E5E8E8"),
            aspectmode='data'
        ),
        margin=dict(l=0,r=0,b=0,t=30), height=500, showlegend=False
    )
    return fig

# --- INICIALIZACIÓN DE MEMORIA (SESSION STATE) ---
if 'pedido' not in st.session_state: st.session_state.pedido = []
if 'resultados' not in st.session_state: st.session_state.resultados = None # Aquí guardaremos el cálculo

# --- APP ---
st.title("🚛 Calculadora Logística Inteligente")

# 1. CARGA
st.sidebar.header("1. Datos")
f = st.sidebar.file_uploader("Sube 'datos.xlsx'", type=["xlsx"])
if not f:
    st.info("👋 Sube el Excel para empezar."); st.stop()

try:
    dfs = cargar_excel(f)
    st.sidebar.success("✅ Datos listos")
except Exception as e:
    st.error(f"Error: {e}"); st.stop()

# 2. PEDIDO
st.header("🛒 Configurar Pedido")
c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
with c1: mod = st.selectbox("Modelo", dfs['RECETA_MODELOS']['Nombre_Modelo'].unique())
with c2: cant = st.number_input("Cantidad", 1, value=50)
with c3: 
    st.write(""); st.write("")
    if st.button("➕ Añadir"): 
        st.session_state.pedido.append({"Modelo": mod, "Cantidad": cant})
        st.session_state.resultados = None # Si cambias el pedido, borramos el resultado anterior
with c4:
    st.write(""); st.write("")
    if st.button("🗑️ Borrar"): 
        st.session_state.pedido = []
        st.session_state.resultados = None
        st.rerun()

if st.session_state.pedido:
    st.dataframe(pd.DataFrame(st.session_state.pedido), use_container_width=True)

st.divider()

# 3. TRANSPORTE
st.header("⚙️ Configuración")
cA, cB, cC = st.columns(3)
with cA: modo = st.radio("Método", ["📦 A Granel", "🧱 Paletizado"], on_change=lambda: st.session_state.update(resultados=None))
with cB: vehic_nombre = st.selectbox("Vehículo", dfs['VEHICULOS_CONTENEDORES']['Tipo'].unique(), on_change=lambda: st.session_state.update(resultados=None))
with cC:
    p_info = None
    if modo == "🧱 Paletizado":
        p_nom = st.selectbox("Palet", dfs['PALETS_SOPORTES']['Nombre'].unique(), on_change=lambda: st.session_state.update(resultados=None))
        p_info = dfs['PALETS_SOPORTES'][dfs['PALETS_SOPORTES']['Nombre'] == p_nom].iloc[0]

# 4. BOTÓN DE CÁLCULO
if st.button("🚀 CALCULAR", type="primary", disabled=not st.session_state.pedido):
    
    vehiculo = dfs['VEHICULOS_CONTENEDORES'][dfs['VEHICULOS_CONTENEDORES']['Tipo'] == vehic_nombre].iloc[0]
    items_load = []
    
    # --- GENERACIÓN DE BULTOS ---
    with st.spinner("Calculando volúmenes..."):
        for l in st.session_state.pedido:
            receta = dfs['RECETA_MODELOS'][dfs['RECETA_MODELOS']['Nombre_Modelo'] == l['Modelo']]
            for _, row in receta.iterrows():
                regla = dfs['REGLAS_EMPAQUETADO'][dfs['REGLAS_EMPAQUETADO']['ID_Componente (Qué meto)'] == row['ID_Componente']]
                if regla.empty: continue
                
                caja = dfs['CATALOGO_CAJAS'][dfs['CATALOGO_CAJAS']['ID_Caja'] == regla.iloc[0]['ID_Caja (Dónde lo meto)']].iloc[0]
                peso_u = dfs['COMPONENTES'][dfs['COMPONENTES']['ID_Componente'] == row['ID_Componente']].iloc[0]['Peso_Neto_Unitario_kg']
                
                total_piezas = l['Cantidad'] * row['Cantidad_x_Butaca']
                piezas_caja = regla.iloc[0]['Cantidad_x_Caja']
                num_cajas = math.ceil(total_piezas / piezas_caja)
                
                if modo == "🧱 Paletizado":
                    # Lógica Palet
                    base = int(p_info['Largo_mm'] / caja['Largo_mm']) * int(p_info['Ancho_mm'] / caja['Ancho_mm'])
                    if base == 0: base = int(p_info['Largo_mm'] / caja['Ancho_mm']) * int(p_info['Ancho_mm'] / caja['Largo_mm'])
                    
                    if base == 0: 
                        st.error(f"Error: La caja {caja['ID_Caja']} es más grande que el palet."); st.stop()
                    
                    h_util = vehiculo['Alto_Interior_mm'] * 0.98
                    capas = min(caja['Max_Apilable'], int((h_util - p_info['Alto_Base_mm'])/caja['Alto_mm']))
                    if capas < 1: capas = 1
                    
                    items_por_palet = base * capas
                    n_palets = math.ceil(num_cajas / items_por_palet)
                    
                    h_p = p_info['Alto_Base_mm'] + (capas * caja['Alto_mm'])
                    w_p = (items_por_palet * ((piezas_caja*peso_u) + caja['Peso_Vacio_kg'])) + p_info['Peso_Vacio_kg']
                    
                    for p in range(n_palets):
                        items_load.append(Item(f"PAL-{l['Modelo'][:3]}-{row['ID_Componente'][:4]}-{p}", 
                                               int(p_info['Ancho_mm']), int(h_p), int(p_info['Largo_mm']), float(w_p)))
                else:
                    # Granel
                    w_b = (piezas_caja*peso_u) + caja['Peso_Vacio_kg']
                    for i in range(num_cajas):
                        items_load.append(Item(f"CJ-{l['Modelo'][:3]}-{row['ID_Componente'][:4]}-{i}", 
                                               int(caja['Ancho_mm']), int(caja['Alto_mm']), int(caja['Largo_mm']), float(w_b)))

    # --- EMPAQUETADO INTELIGENTE (NO 20 CAMIONES FIJOS) ---
    # 1. Calculamos volumen total de carga
    vol_total_carga = sum([it.width * it.height * it.depth for it in items_load])
    vol_camion = float(vehiculo['Ancho_Interior_mm'] * vehiculo['Alto_Interior_mm'] * vehiculo['Largo_Interior_mm'])
    
    # Estimamos camiones mínimos (con un factor de eficiencia del 85%)
    estimacion = math.ceil(vol_total_carga / (vol_camion * 0.85))
    num_bins_inicial = max(1, estimacion + 1) # Creamos la estimación + 1 de margen, no 20.
    
    packer = Packer()
    # Mapeo: Ancho, Alto, Largo
    bin_W = int(vehiculo['Ancho_Interior_mm'])
    bin_H = int(vehiculo['Alto_Interior_mm'])
    bin_L = int(vehiculo['Largo_Interior_mm'])
    max_w = int(vehiculo['Carga_Max_kg'])
    
    # Usamos el nombre REAL del vehículo seleccionado
    nombre_vehiculo = vehiculo['Tipo'] 
    
    for i in range(num_bins_inicial + 5): # Damos un margen de seguridad pequeño
        packer.add_bin(Bin(f"{nombre_vehiculo} #{i+1}", bin_W, bin_H, bin_L, max_w))
    
    for it in items_load: packer.add_item(it)
    
    packer.pack()
    
    # Guardamos en MEMORIA (Session State) para que no se borre al clicar
    st.session_state.resultados = {
        "bins": [b for b in packer.bins if len(b.items) > 0],
        "vehiculo": vehiculo,
        "total_bultos": len(items_load),
        "unfitted": packer.bins[-1].unfitted_items if packer.bins else []
    }

# --- 5. MOSTRAR RESULTADOS (DESDE MEMORIA) ---
if st.session_state.resultados:
    res = st.session_state.resultados
    bins_usados = res['bins']
    vehiculo_info = res['vehiculo']
    
    st.divider()
    
    if not bins_usados and not res['unfitted']:
        st.warning("El pedido no generó bultos.")
    elif not bins_usados and res['unfitted']:
         st.error(f"❌ ERROR CRÍTICO: Ningún bulto cabe en el {vehiculo_info['Tipo']}. \n"
                  f"El bulto más pequeño mide: {res['unfitted'][0].width}x{res['unfitted'][0].depth}x{res['unfitted'][0].height} mm.\n"
                  f"El vehículo mide: {vehiculo_info['Ancho_Interior_mm']}x{vehiculo_info['Largo_Interior_mm']}x{vehiculo_info['Alto_Interior_mm']} mm.")
    else:
        st.success(f"✅ Se necesitan **{len(bins_usados)}** unidades de **{vehiculo_info['Tipo']}**")
        
        # Tabs para cada vehículo
        tabs = st.tabs([b.name for b in bins_usados])
        
        for i, b in enumerate(bins_usados):
            with tabs[i]:
                # Métricas
                vol_u = sum([float(it.width)*float(it.height)*float(it.depth) for it in b.items])
                vol_t = float(b.width)*float(b.height)*float(b.depth)
                pct = (vol_u/vol_t)*100
                peso = sum([float(it.weight) for it in b.items])
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Ocupación", f"{round(pct,1)}%")
                m2.metric("Peso", f"{int(peso)} kg")
                m3.metric("Bultos", len(b.items))
                
                # Checkbox para 3D (Ahora NO borra los datos porque se leen de session_state)
                ver_3d = st.checkbox(f"👁️ Ver 3D ({b.name})", value=True, key=f"chk_{i}")
                
                if ver_3d:
                    # Pasamos dimensiones correctas: Ancho, Alto, Largo
                    fig = draw_container_3d(b, b.width, b.height, b.depth, b.name)
                    st.plotly_chart(fig, use_container_width=True)
                
                # Tabla
                det = [{"Ref": it.name, 
                        "Medidas (Ancho x Largo x Alto)": f"{int(it.width)} x {int(it.depth)} x {int(it.height)}", 
                        "Peso": f"{int(it.weight)} kg",
                        "Posición": f"X:{int(float(item.position[0]))} Y:{int(float(item.position[2]))} Z:{int(float(item.position[1]))}"} 
                       for item in b.items]
                st.dataframe(pd.DataFrame(det), use_container_width=True)
        
        # Mostrar items que no cupieron (si los hay)
        # Normalmente packer.bins[-1] tiene los unfitted, pero revisamos todos
        all_unfitted = []
        for b in packer.bins: 
             if hasattr(b, 'unfitted_items'): all_unfitted.extend(b.unfitted_items)
             
        if all_unfitted:
            st.error(f"⚠️ Hay {len(all_unfitted)} bultos que no han cabido (revisar tamaños).")
