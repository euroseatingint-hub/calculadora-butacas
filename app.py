import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- CONFIGURACIÓN PÁGINA ---
st.set_page_config(page_title="Calculadora Logística 3D", layout="wide", page_icon="🚛")

# --- FUNCIONES ---
@st.cache_data
def cargar_excel(archivo):
    xls = pd.ExcelFile(archivo)
    return {sheet: pd.read_excel(xls, sheet).rename(columns=lambda x: x.strip()) for sheet in xls.sheet_names}

def draw_truck_3d_horizontal(bin_obj, width_mm, height_mm, length_mm):
    """
    Dibuja el camión tumbado correctamente en el suelo.
    Ejes Plotly: X=Ancho, Y=Largo (Profundidad), Z=Alto
    """
    fig = go.Figure()
    
    # Dimensiones para el dibujo (convertidas a metros para mejor visualización o mantenemos mm)
    # Usaremos mm pero ajustaremos la cámara
    W, H, L = float(width_mm), float(height_mm), float(length_mm)
    
    # 1. Dibujar Contenedor (Wireframe)
    # Definimos las 8 esquinas: (x, y, z) -> (Ancho, Largo, Alto)
    # Suelo
    fig.add_trace(go.Scatter3d(x=[0, W, W, 0, 0], y=[0, 0, L, L, 0], z=[0, 0, 0, 0, 0],
                               mode='lines', line=dict(color='black', width=4), name='Suelo'))
    # Techo
    fig.add_trace(go.Scatter3d(x=[0, W, W, 0, 0], y=[0, 0, L, L, 0], z=[H, H, H, H, H],
                               mode='lines', line=dict(color='gray', width=2), name='Techo'))
    # Pilares
    fig.add_trace(go.Scatter3d(x=[0, 0], y=[0, 0], z=[0, H], mode='lines', line=dict(color='gray', width=2), showlegend=False))
    fig.add_trace(go.Scatter3d(x=[W, W], y=[0, 0], z=[0, H], mode='lines', line=dict(color='gray', width=2), showlegend=False))
    fig.add_trace(go.Scatter3d(x=[W, W], y=[L, L], z=[0, H], mode='lines', line=dict(color='gray', width=2), showlegend=False))
    fig.add_trace(go.Scatter3d(x=[0, 0], y=[L, L], z=[0, H], mode='lines', line=dict(color='gray', width=2), showlegend=False))

    # 2. Dibujar Cajas
    # Paleta de colores
    colors = ['#E74C3C', '#3498DB', '#F1C40F', '#2ECC71', '#9B59B6', '#E67E22', '#1ABC9C']
    
    for item in bin_obj.items:
        # Mapeo de coordenadas py3dbp (W, H, D) a Plotly (X, Z, Y)
        # En py3dbp: Width=X, Height=Y, Depth=Z (normalmente). 
        # Pero nosotros hemos cargado: W=Ancho, H=Alto, D=Largo.
        
        # Posición
        x = float(item.position[0]) # Ancho
        z = float(item.position[1]) # Alto (py3dbp lo trata como Y a veces, depende de cómo lo metimos)
        y = float(item.position[2]) # Largo (Depth)
        
        # Dimensiones
        dx = float(item.width)
        dz = float(item.height)
        dy = float(item.depth)
        
        # Color hash
        c = colors[hash(item.name.split('-')[1]) % len(colors)] # Hash basado en componente
        
        # Cubo Sólido
        fig.add_trace(go.Mesh3d(
            # Coordenadas X (Ancho)
            x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
            # Coordenadas Y (Largo/Profundidad) -> OJO AQUÍ EL CAMBIO
            y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
            # Coordenadas Z (Alto)
            z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
            
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            color=c, opacity=1.0, flatshading=True, name=item.name, hoverinfo='name'
        ))

    # Ajustes de Cámara para verlo "desde arriba en diagonal"
    camera = dict(eye=dict(x=2.0, y=0.5, z=1.5))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Ancho (mm)', range=[0, W+100], backgroundcolor="white"),
            yaxis=dict(title='Largo (mm)', range=[0, L+100], backgroundcolor="white"), # El largo ahora es Y
            zaxis=dict(title='Alto (mm)', range=[0, H+100], backgroundcolor="lightgrey"),
            aspectmode='data', # Proporción real
        ),
        margin=dict(l=0,r=0,b=0,t=0),
        height=600,
        showlegend=False,
        scene_camera=camera
    )
    return fig

# --- APP ---
st.title("🚛 Calculadora Logística: Grupaje y Paletización")

if 'pedido' not in st.session_state: st.session_state.pedido = []

# 1. LATERAL
st.sidebar.header("1. Datos")
f = st.sidebar.file_uploader("Sube 'datos.xlsx'", type=["xlsx"])

if f:
    try:
        dfs = cargar_excel(f)
        st.sidebar.success("✅ Datos Cargados")
    except Exception as e:
        st.error(f"Error: {e}"); st.stop()

    # 2. PEDIDO
    st.header("🛒 Tu Pedido")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1: mod = st.selectbox("Modelo", dfs['RECETA_MODELOS']['Nombre_Modelo'].unique())
    with c2: cant = st.number_input("Cantidad", 1, value=50)
    with c3: 
        st.write(""); st.write("")
        if st.button("➕ Añadir"): st.session_state.pedido.append({"Modelo": mod, "Cantidad": cant})

    if st.session_state.pedido:
        st.dataframe(pd.DataFrame(st.session_state.pedido), use_container_width=True)
        if st.button("🗑️ Limpiar"): st.session_state.pedido = []; st.rerun()

    st.divider()

    # 3. TRANSPORTE
    st.header("⚙️ Configuración")
    colA, colB, colC = st.columns(3)
    with colA: modo = st.radio("Modo", ["📦 A Granel", "🧱 Paletizado"])
    with colB: vehic = st.selectbox("Vehículo", dfs['VEHICULOS_CONTENEDORES']['Tipo'].unique())
    with colC:
        p_info = None
        if modo == "🧱 Paletizado":
            p_nom = st.selectbox("Palet", dfs['PALETS_SOPORTES']['Nombre'].unique())
            p_info = dfs['PALETS_SOPORTES'][dfs['PALETS_SOPORTES']['Nombre'] == p_nom].iloc[0]

    # 4. CÁLCULO
    if st.button("🚀 Calcular (Versión Corregida)", type="primary", disabled=not st.session_state.pedido):
        
        camion = dfs['VEHICULOS_CONTENEDORES'][dfs['VEHICULOS_CONTENEDORES']['Tipo'] == vehic].iloc[0]
        items_load = []
        
        # --- DEBUG: Comprobación de medidas ---
        st.info("🔍 Analizando medidas antes de calcular...")
        
        with st.spinner("Generando bultos..."):
            for l in st.session_state.pedido:
                receta = dfs['RECETA_MODELOS'][dfs['RECETA_MODELOS']['Nombre_Modelo'] == l['Modelo']]
                
                for _, row in receta.iterrows():
                    # Buscar reglas
                    regla = dfs['REGLAS_EMPAQUETADO'][dfs['REGLAS_EMPAQUETADO']['ID_Componente (Qué meto)'] == row['ID_Componente']]
                    if regla.empty: continue
                    
                    caja = dfs['CATALOGO_CAJAS'][dfs['CATALOGO_CAJAS']['ID_Caja'] == regla.iloc[0]['ID_Caja (Dónde lo meto)']].iloc[0]
                    peso_u = dfs['COMPONENTES'][dfs['COMPONENTES']['ID_Componente'] == row['ID_Componente']].iloc[0]['Peso_Neto_Unitario_kg']
                    
                    # Cálculos básicos
                    total_piezas = l['Cantidad'] * row['Cantidad_x_Butaca']
                    piezas_caja = regla.iloc[0]['Cantidad_x_Caja']
                    num_cajas = math.ceil(total_piezas / piezas_caja)
                    
                    # LOGICA PALETIZADO MEJORADA
                    if modo == "🧱 Paletizado":
                        # 1. Calcular Base (Cajas por capa)
                        # Intento 1: Orientación normal
                        base = int(p_info['Largo_mm'] / caja['Largo_mm']) * int(p_info['Ancho_mm'] / caja['Ancho_mm'])
                        # Intento 2: Orientación rotada
                        if base == 0:
                            base = int(p_info['Largo_mm'] / caja['Ancho_mm']) * int(p_info['Ancho_mm'] / caja['Largo_mm'])
                        
                        if base == 0:
                            st.error(f"❌ ERROR: La caja {caja['ID_Caja']} ({caja['Largo_mm']}x{caja['Ancho_mm']}) es más grande que el palet ({p_info['Largo_mm']}x{p_info['Ancho_mm']}).")
                            st.stop()
                            
                        # 2. Calcular Altura
                        # Altura disponible en camión
                        h_util_camion = camion['Alto_Interior_mm'] * 0.95 # 5% margen seguridad
                        h_util_palet = h_util_camion - p_info['Alto_Base_mm']
                        
                        capas_por_altura = int(h_util_palet / caja['Alto_mm'])
                        capas = min(caja['Max_Apilable'], capas_por_altura)
                        if capas < 1: capas = 1
                        
                        cajas_por_palet = base * capas
                        num_palets = math.ceil(num_cajas / cajas_por_palet)
                        
                        # Dimensiones finales del Bulto Paletizado
                        dim_L = int(p_info['Largo_mm'])
                        dim_W = int(p_info['Ancho_mm'])
                        dim_H = int(p_info['Alto_Base_mm'] + (capas * caja['Alto_mm']))
                        
                        peso_neto = cajas_por_palet * ((piezas_caja * peso_u) + caja['Peso_Vacio_kg'])
                        peso_bruto = peso_neto + p_info['Peso_Vacio_kg']
                        
                        # Crear Items para el Tetris
                        for p in range(num_palets):
                            # ID único: PAL-Modelo-Componente-Indice
                            # py3dbp usa (w, h, d). Nosotros pasamos (Ancho, Alto, Largo)
                            items_load.append(Item(
                                name=f"PAL-{l['Modelo'][:3]}-{row['ID_Componente'][:4]}-{p}",
                                width=dim_W, height=dim_H, depth=dim_L, weight=float(peso_bruto)
                            ))
                            
                    else:
                        # LOGICA A GRANEL
                        peso_caja = (piezas_caja * peso_u) + caja['Peso_Vacio_kg']
                        for i in range(num_cajas):
                            items_load.append(Item(
                                name=f"CJ-{l['Modelo'][:3]}-{row['ID_Componente'][:4]}-{i}",
                                width=int(caja['Ancho_mm']), height=int(caja['Alto_mm']), depth=int(caja['Largo_mm']), weight=float(peso_caja)
                            ))

            # --- VERIFICACIÓN DE MEDIDAS (DEBUG) ---
            if items_load:
                ex = items_load[0]
                st.warning(f"💡 REVISIÓN DE DATOS: El sistema ha generado bultos de ejemplo con estas medidas: \n"
                           f"Ancho: {ex.width} mm | Largo: {ex.depth} mm | Alto: {ex.height} mm. \n"
                           f"Si esto te parece muy pequeño o muy grande, revisa tu Excel.")

            # --- EMPAQUETADO ---
            packer = Packer()
            
            # Definir Camión: py3dbp Bin(width, height, depth, weight)
            # Para que salga tumbado: Width=Ancho, Height=Alto, Depth=Largo
            bin_W = int(camion['Ancho_Interior_mm'])
            bin_H = int(camion['Alto_Interior_mm'])
            bin_L = int(camion['Largo_Interior_mm'])
            max_weight = int(camion['Carga_Max_kg'])
            
            # Crear flota (hasta 20 camiones)
            for i in range(20):
                packer.add_bin(Bin(f"Camión {i+1}", bin_W, bin_H, bin_L, max_weight))
            
            for it in items_load: packer.add_item(it)
            
            packer.pack()
            
            # --- RESULTADOS ---
            # Filtrar camiones vacíos
            used_bins = [b for b in packer.bins if len(b.items) > 0]
            
            st.divider()
            if not used_bins:
                st.error("❌ No cabe nada. Verifica que las cajas no sean más grandes que el camión.")
            else:
                c_tot = len(used_bins)
                st.success(f"✅ RESULTADO: Se necesitan {c_tot} camiones")
                
                tabs = st.tabs([b.name for b in used_bins])
                for i, b in enumerate(used_bins):
                    with tabs[i]:
                        # Métricas
                        v_used = sum([float(it.width)*float(it.height)*float(it.depth) for it in b.items])
                        v_tot = float(b.width)*float(b.height)*float(b.depth)
                        pct = (v_used/v_tot)*100
                        peso = sum([float(it.weight) for it in b.items])
                        
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Ocupación Volumétrica", f"{round(pct, 1)}%")
                        m2.metric("Peso Total", f"{int(peso)} kg")
                        m3.metric("Bultos", len(b.items))
                        
                        # GRÁFICO 3D CORREGIDO (HORIZONTAL)
                        st.subheader("Vista 3D")
                        # Pasamos (Ancho, Alto, Largo)
                        fig = draw_truck_3d_horizontal(b, b.width, b.height, b.depth)
                        st.plotly_chart(fig, use_container_width=True, key=f"plot_{i}")
                        
                        # DETALLE DE CARGA
                        st.write("📋 **Lista de Bultos en este camión:**")
                        data_items = []
                        for item in b.items:
                            data_items.append({
                                "Ref": item.name,
                                "Dimensiones (mm)": f"{int(item.width)}x{int(item.depth)}x{int(item.height)}", # Visualmente L x W x H
                                "Peso": f"{int(item.weight)} kg",
                                "Posición": f"X:{int(float(item.position[0]))} Y:{int(float(item.position[2]))} Z:{int(float(item.position[1]))}"
                            })
                        st.dataframe(pd.DataFrame(data_items), use_container_width=True)

else:
    st.info("👋 Sube el archivo Excel.")

