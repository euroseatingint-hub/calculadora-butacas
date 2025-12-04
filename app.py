import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- CONFIGURACIÓN PÁGINA ---
st.set_page_config(page_title="Calculadora Logística PRO", layout="wide", page_icon="🚛")

# --- FUNCIONES ---
@st.cache_data
def cargar_excel(archivo):
    xls = pd.ExcelFile(archivo)
    return {sheet: pd.read_excel(xls, sheet).rename(columns=lambda x: x.strip()) for sheet in xls.sheet_names}

def corregir_medidas(valor):
    """Detecta si el usuario puso cm en vez de mm (heurística: si es < 400mm es sospechoso para una butaca)"""
    if valor > 0 and valor < 200: 
        return valor * 10
    return valor

def draw_truck_3d_optimized(bin_obj, width_mm, height_mm, length_mm):
    """
    Dibuja el camión HORIZONTAL.
    Mapeo de Ejes py3dbp -> Plotly:
    py3dbp X (Ancho) -> Plotly X
    py3dbp Y (Alto)  -> Plotly Z (Altura/Up)
    py3dbp Z (Largo) -> Plotly Y (Profundidad)
    """
    fig = go.Figure()
    
    W, H, L = float(width_mm), float(height_mm), float(length_mm)
    
    # 1. Wireframe del Camión (Solo líneas)
    # Suelo (Z=0)
    fig.add_trace(go.Scatter3d(x=[0, W, W, 0, 0], y=[0, 0, L, L, 0], z=[0, 0, 0, 0, 0],
                               mode='lines', line=dict(color='black', width=3), name='Suelo', hoverinfo='none'))
    # Techo (Z=H)
    fig.add_trace(go.Scatter3d(x=[0, W, W, 0, 0], y=[0, 0, L, L, 0], z=[H, H, H, H, H],
                               mode='lines', line=dict(color='grey', width=2), name='Techo', hoverinfo='none'))
    # Pilares
    for x_c, y_c in [(0,0), (W,0), (W,L), (0,L)]:
        fig.add_trace(go.Scatter3d(x=[x_c, x_c], y=[y_c, y_c], z=[0, H], mode='lines', line=dict(color='grey', width=2), showlegend=False, hoverinfo='none'))

    # 2. Cajas (Optimizadas con Scatter3D transparente + Mesh ligero si son pocas)
    # Para optimizar, usamos Mesh3d pero solo dibujamos si el usuario lo pide
    
    colors = ['#E74C3C', '#3498DB', '#F1C40F', '#2ECC71', '#9B59B6', '#E67E22', '#1ABC9C']
    
    for item in bin_obj.items:
        # Recuperamos dimensiones originales
        # En py3dbp (packer): w=Ancho, h=Alto, d=Largo
        w_box, h_box, d_box = float(item.width), float(item.height), float(item.depth)
        
        # Posición original
        x_pos, y_pos, z_pos = float(item.position[0]), float(item.position[1]), float(item.position[2])
        
        # TRUCO: Intercambiamos Y y Z para Plotly
        # Plotly X = py3dbp X (Ancho)
        # Plotly Y = py3dbp Z (Largo/Profundidad)
        # Plotly Z = py3dbp Y (Alto)
        
        px = x_pos
        py = z_pos # SWAP
        pz = y_pos # SWAP
        
        dx = w_box
        dy = d_box # SWAP dimensión
        dz = h_box # SWAP dimensión
        
        c = colors[hash(item.name.split('-')[1]) % len(colors)]
        
        # Dibujamos cubo
        fig.add_trace(go.Mesh3d(
            x=[px, px+dx, px+dx, px, px, px+dx, px+dx, px],
            y=[py, py, py+dy, py+dy, py, py, py+dy, py+dy],
            z=[pz, pz, pz, pz, pz+dz, pz+dz, pz+dz, pz+dz],
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            color=c, opacity=0.9, flatshading=True, name=item.name, hoverinfo='name'
        ))

    # Cámara aérea diagonal
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Ancho (mm)', range=[0, W+100], backgroundcolor="#F0F0F0"),
            yaxis=dict(title='Largo (mm)', range=[0, L+100], backgroundcolor="#F0F0F0"),
            zaxis=dict(title='Alto (mm)', range=[0, H+100], backgroundcolor="#D0D0D0"),
            aspectmode='data'
        ),
        margin=dict(l=0,r=0,b=0,t=0), height=500, showlegend=False
    )
    return fig

# --- APP ---
st.title("🚛 Calculadora Logística PRO")

# Inicialización de estado
if 'pedido' not in st.session_state: st.session_state.pedido = []

# BARRA LATERAL
st.sidebar.header("1. Archivo de Datos")
f = st.sidebar.file_uploader("Sube 'datos.xlsx'", type=["xlsx"])

if f:
    try:
        dfs = cargar_excel(f)
        st.sidebar.success("✅ Excel leído correctamente")
    except Exception as e:
        st.error(f"Error al leer Excel: {e}"); st.stop()

    # ZONA DE PEDIDO
    st.header("2. Composición del Pedido")
    
    # Aviso de limpieza
    if len(st.session_state.pedido) > 0:
        st.warning(f"⚠️ Tienes {len(st.session_state.pedido)} líneas en el pedido actual. Si quieres calcular algo nuevo, borra primero.")
    
    c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
    with c1: mod = st.selectbox("Modelo", dfs['RECETA_MODELOS']['Nombre_Modelo'].unique())
    with c2: cant = st.number_input("Nº Butacas", 1, value=50)
    with c3: 
        st.write(""); st.write("")
        if st.button("➕ Añadir"): st.session_state.pedido.append({"Modelo": mod, "Cantidad": cant})
    with c4:
        st.write(""); st.write("")
        if st.button("🗑️ BORRAR", type="primary"): st.session_state.pedido = []; st.rerun()

    # Tabla resumen
    if st.session_state.pedido:
        df_show = pd.DataFrame(st.session_state.pedido)
        df_show['Total Piezas Aprox'] = df_show['Cantidad'] * 4 # Estimación visual
        st.dataframe(df_show, use_container_width=True)

    st.divider()

    # CONFIGURACIÓN
    st.header("3. Transporte")
    cA, cB, cC = st.columns(3)
    with cA: modo = st.radio("Método", ["📦 A Granel", "🧱 Paletizado"])
    with cB: vehic = st.selectbox("Vehículo", dfs['VEHICULOS_CONTENEDORES']['Tipo'].unique())
    with cC:
        p_info = None
        if modo == "🧱 Paletizado":
            p_nom = st.selectbox("Palet", dfs['PALETS_SOPORTES']['Nombre'].unique())
            p_info = dfs['PALETS_SOPORTES'][dfs['PALETS_SOPORTES']['Nombre'] == p_nom].iloc[0]

    # BOTÓN CALCULAR
    if st.button("🚀 CALCULAR DISTRIBUCIÓN", type="primary", disabled=not st.session_state.pedido):
        
        camion = dfs['VEHICULOS_CONTENEDORES'][dfs['VEHICULOS_CONTENEDORES']['Tipo'] == vehic].iloc[0]
        items_load = []
        
        with st.spinner("Optimizando carga..."):
            for l in st.session_state.pedido:
                receta = dfs['RECETA_MODELOS'][dfs['RECETA_MODELOS']['Nombre_Modelo'] == l['Modelo']]
                
                for _, row in receta.iterrows():
                    regla = dfs['REGLAS_EMPAQUETADO'][dfs['REGLAS_EMPAQUETADO']['ID_Componente (Qué meto)'] == row['ID_Componente']]
                    if regla.empty: continue
                    
                    caja_raw = dfs['CATALOGO_CAJAS'][dfs['CATALOGO_CAJAS']['ID_Caja'] == regla.iloc[0]['ID_Caja (Dónde lo meto)']].iloc[0]
                    # CORRECCIÓN AUTOMÁTICA DE MEDIDAS (CM -> MM)
                    caja = caja_raw.copy()
                    caja['Largo_mm'] = corregir_medidas(caja['Largo_mm'])
                    caja['Ancho_mm'] = corregir_medidas(caja['Ancho_mm'])
                    caja['Alto_mm'] = corregir_medidas(caja['Alto_mm'])
                    
                    peso_u = dfs['COMPONENTES'][dfs['COMPONENTES']['ID_Componente'] == row['ID_Componente']].iloc[0]['Peso_Neto_Unitario_kg']
                    
                    total_piezas = l['Cantidad'] * row['Cantidad_x_Butaca']
                    piezas_caja = regla.iloc[0]['Cantidad_x_Caja']
                    num_cajas = math.ceil(total_piezas / piezas_caja)
                    
                    if modo == "🧱 Paletizado":
                        # Lógica Palet
                        # Intento 1: Normal
                        base = int(p_info['Largo_mm'] / caja['Largo_mm']) * int(p_info['Ancho_mm'] / caja['Ancho_mm'])
                        # Intento 2: Rotado
                        if base == 0:
                             base = int(p_info['Largo_mm'] / caja['Ancho_mm']) * int(p_info['Ancho_mm'] / caja['Largo_mm'])
                        
                        if base == 0: continue # No cabe
                        
                        h_util = camion['Alto_Interior_mm'] * 0.95
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

            # Empaquetado
            packer = Packer()
            # Mapeo Bin: W=Ancho, H=Alto, D=Largo
            bin_W, bin_H, bin_L = int(camion['Ancho_Interior_mm']), int(camion['Alto_Interior_mm']), int(camion['Largo_Interior_mm'])
            max_w = int(camion['Carga_Max_kg'])
            
            for i in range(20):
                packer.add_bin(Bin(f"Camión {i+1}", bin_W, bin_H, bin_L, max_w))
            
            for it in items_load: packer.add_item(it)
            packer.pack()
            
            used_bins = [b for b in packer.bins if len(b.items) > 0]
            
            st.divider()
            
            if not used_bins:
                st.error("❌ No cabe nada. Revisa las medidas.")
            else:
                st.success(f"✅ SE NECESITAN {len(used_bins)} CAMIONES")
                
                tabs = st.tabs([b.name for b in used_bins])
                for i, b in enumerate(used_bins):
                    with tabs[i]:
                        vol_u = sum([float(it.width)*float(it.height)*float(it.depth) for it in b.items])/1e9
                        vol_t = (float(b.width)*float(b.height)*float(b.depth))/1e9
                        peso = sum([float(it.weight) for it in b.items])
                        
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Ocupación", f"{round((vol_u/vol_t)*100,1)}%")
                        m2.metric("Peso", f"{int(peso)} kg")
                        m3.metric("Bultos", len(b.items))
                        
                        # CHECKBOX 3D (Para que no cargue lento)
                        if st.checkbox(f"👁️ Ver Gráfico 3D ({b.name})", key=f"chk_{i}"):
                            st.plotly_chart(draw_truck_3d_optimized(b, b.width, b.height, b.depth), use_container_width=True)
                        else:
                            st.info("Activa la casilla de arriba para ver el gráfico 3D.")
                        
                        # Tabla Detalle
                        det = [{"Ref": it.name, 
                                "Medidas (Ancho x Largo x Alto)": f"{int(it.width)}x{int(it.depth)}x{int(it.height)}", 
                                "Peso": f"{int(it.weight)}"} for it in b.items]
                        st.dataframe(pd.DataFrame(det), use_container_width=True)
else:
    st.info("👋 Sube el Excel para comenzar.")
