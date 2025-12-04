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
    
    # Dibujar contorno del camión (Wireframe)
    # Ejes: X=Ancho, Y=Alto, Z=Largo
    lines_x = [0, w, w, 0, 0, 0, w, w, 0, 0, w, w, w, w, 0, 0]
    lines_y = [0, 0, h, h, 0, 0, 0, h, h, 0, 0, 0, h, h, h, h]
    lines_z = [0, 0, 0, 0, 0, d, d, d, d, d, d, 0, 0, d, d, 0]
    
    fig.add_trace(go.Scatter3d(
        x=lines_x, y=lines_y, z=lines_z,
        mode='lines', line=dict(color='black', width=5),
        name='Paredes Camión', hoverinfo='none'
    ))
    
    # Colores para distinguir items
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE', '#D2B4DE']
    
    for item in bin_obj.items:
        # Generar color basado en el nombre del componente
        c = colors[hash(item.name.split('-')[0]) % len(colors)]
        
        # Coordenadas
        x, y, z = float(item.position[0]), float(item.position[1]), float(item.position[2])
        dx, dy, dz = float(item.width), float(item.height), float(item.depth)
        
        # Crear cubo sólido
        fig.add_trace(go.Mesh3d(
            x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
            y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
            z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
            color=c, opacity=1.0, flatshading=True, name=item.name
        ))

    # AJUSTE VISUAL (Para que no se vea vertical)
    # Forzamos que la escala visual sea real (1 metro = 1 metro en pantalla)
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Ancho (X)', range=[0, w+100], showbackground=False),
            yaxis=dict(title='Alto (Y)', range=[0, h+100], showbackground=False),
            zaxis=dict(title='Largo (Z)', range=[0, d+100], showbackground=False),
            aspectmode='data', # ESTO ES CLAVE: Mantiene la proporción real
            camera=dict(
                eye=dict(x=2, y=1, z=0.5) # Posición de la cámara para ver profundidad
            )
        ),
        margin=dict(l=0,r=0,b=0,t=0), 
        height=600,
        showlegend=False
    )
    return fig

# --- APP PRINCIPAL ---
st.title("🚛 Calculadora Logística 3D - Versión Final")

if 'pedido' not in st.session_state:
    st.session_state.pedido = []

# --- 1. DATOS ---
st.sidebar.header("1. Carga de Datos")
f = st.sidebar.file_uploader("Sube 'datos.xlsx'", type=["xlsx"])

if f:
    try:
        dfs = cargar_excel(f)
        st.sidebar.success("✅ Datos listos")
    except Exception as e:
        st.error(f"Error Excel: {e}"); st.stop()

    # --- 2. PEDIDO ---
    st.header("🛒 Configurar Pedido")
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

    # --- 3. TRANSPORTE ---
    st.header("⚙️ Configuración de Envío")
    cc1, cc2, cc3 = st.columns(3)
    with cc1: modo = st.radio("Formato", ["📦 A Granel", "🧱 Paletizado"])
    with cc2: vehic = st.selectbox("Vehículo", dfs['VEHICULOS_CONTENEDORES']['Tipo'].unique())
    with cc3: 
        palet_info = None
        if modo == "🧱 Paletizado":
            p_nom = st.selectbox("Palet Base", dfs['PALETS_SOPORTES']['Nombre'].unique())
            palet_info = dfs['PALETS_SOPORTES'][dfs['PALETS_SOPORTES']['Nombre'] == p_nom].iloc[0]

    # --- 4. CÁLCULO ---
    if st.button("🚀 Calcular Distribución", type="primary", disabled=not st.session_state.pedido):
        
        items_load = []
        camion_data = dfs['VEHICULOS_CONTENEDORES'][dfs['VEHICULOS_CONTENEDORES']['Tipo'] == vehic].iloc[0]
        
        with st.spinner("Optimizando espacio y generando 3D..."):
            # Generación de Items
            for l in st.session_state.pedido:
                receta = dfs['RECETA_MODELOS'][dfs['RECETA_MODELOS']['Nombre_Modelo'] == l['Modelo']]
                for _, row in receta.iterrows():
                    # Buscar Regla
                    regla = dfs['REGLAS_EMPAQUETADO'][dfs['REGLAS_EMPAQUETADO']['ID_Componente (Qué meto)'] == row['ID_Componente']]
                    if regla.empty: continue
                    
                    # Datos Caja y Peso
                    caja = dfs['CATALOGO_CAJAS'][dfs['CATALOGO_CAJAS']['ID_Caja'] == regla.iloc[0]['ID_Caja (Dónde lo meto)']].iloc[0]
                    peso_u = dfs['COMPONENTES'][dfs['COMPONENTES']['ID_Componente'] == row['ID_Componente']].iloc[0]['Peso_Neto_Unitario_kg']
                    
                    # Cálculo cantidades
                    total_p = l['Cantidad'] * row['Cantidad_x_Butaca']
                    num_c = math.ceil(total_p / regla.iloc[0]['Cantidad_x_Caja'])
                    
                    if modo == "📦 A Granel":
                        peso_b = (regla.iloc[0]['Cantidad_x_Caja'] * peso_u) + caja['Peso_Vacio_kg']
                        for i in range(num_c):
                            items_load.append(Item(f"{l['Modelo'][:3]}-{row['ID_Componente']}-{i}", int(caja['Ancho_mm']), int(caja['Alto_mm']), int(caja['Largo_mm']), float(peso_b)))
                    else:
                        # Paletizado
                        base = int(palet_info['Largo_mm']/caja['Largo_mm']) * int(palet_info['Ancho_mm']/caja['Ancho_mm'])
                        if base == 0: base = int(palet_info['Largo_mm']/caja['Ancho_mm']) * int(palet_info['Ancho_mm']/caja['Largo_mm'])
                        if base == 0: continue
                        
                        capas = min(caja['Max_Apilable'], int((camion_data['Alto_Interior_mm']*0.98 - palet_info['Alto_Base_mm'])/caja['Alto_mm']))
                        if capas < 1: capas = 1
                        
                        # Agrupación en palets
                        items_por_palet = base * capas
                        n_palets = math.ceil(num_c / items_por_palet)
                        
                        h_p = palet_info['Alto_Base_mm'] + (capas * caja['Alto_mm'])
                        w_p = ((items_por_palet) * ((regla.iloc[0]['Cantidad_x_Caja'] * peso_u) + caja['Peso_Vacio_kg'])) + palet_info['Peso_Vacio_kg']
                        
                        for p in range(n_palets):
                            # Nombre descriptivo para la tabla: PALET-Modelo-Componente
                            items_load.append(Item(f"PAL-{l['Modelo'][:3]}-{row['ID_Componente']}-{p}", int(palet_info['Ancho_mm']), int(h_p), int(palet_info['Largo_mm']), float(w_p)))

            # Empaquetado (Bin Packing)
            packer = Packer()
            # Crear hasta 20 camiones vacíos
            for i in range(20): 
                packer.add_bin(Bin(f"Camión {i+1}", int(camion_data['Ancho_Interior_mm']), int(camion_data['Alto_Interior_mm']), int(camion_data['Largo_Interior_mm']), int(camion_data['Carga_Max_kg'])))
            
            for it in items_load: packer.add_item(it)
            packer.pack()
            
            # FILTRAR: Solo camiones que tengan algo dentro
            used_bins = [b for b in packer.bins if len(b.items) > 0]
            
            # --- RESULTADOS ---
            st.divider()
            
            if not used_bins:
                st.error("❌ No cabe nada. Revisa las medidas de las cajas vs camión.")
            else:
                st.success(f"✅ Se necesitan {len(used_bins)} Vehículo(s)")
                
                # Crear pestañas solo para los camiones usados
                tabs = st.tabs([b.name for b in used_bins])
                
                for i, b in enumerate(used_bins):
                    with tabs[i]:
                        # Datos Generales
                        vol = sum([float(it.width)*float(it.height)*float(it.depth) for it in b.items])/1e9
                        vol_tot = (float(b.width)*float(b.height)*float(b.depth))/1e9
                        peso = sum([float(it.weight) for it in b.items])
                        
                        k1, k2, k3 = st.columns(3)
                        k1.metric("Ocupación Volumétrica", f"{round((vol/vol_tot)*100, 1)}%")
                        k2.metric("Peso Carga", f"{int(peso)} kg", f"Máx {camion_data['Carga_Max_kg']}")
                        k3.metric("Total Bultos", len(b.items))
                        
                        # GRÁFICO 3D (Con KEY única para evitar error)
                        st.subheader("Vista 3D")
                        st.plotly_chart(draw_truck_3d(b, float(b.width), float(b.height), float(b.depth)), use_container_width=True, key=f"plot_truck_{i}")
                        
                        # TABLA DE DETALLE (MANIFIESTO)
                        st.subheader("📋 Manifiesto de Carga (Detalle de Bultos)")
                        detalle_data = []
                        for item in b.items:
                            detalle_data.append({
                                "ID Bulto": item.name,
                                "Dimensiones (mm)": f"{int(item.width)} x {int(item.depth)} x {int(item.height)}", # X, Z, Y
                                "Peso (kg)": f"{int(item.weight)}",
                                "Posición (X, Z, Y)": f"{int(float(item.position[0]))}, {int(float(item.position[2]))}, {int(float(item.position[1]))}"
                            })
                        st.dataframe(pd.DataFrame(detalle_data), use_container_width=True)

else:
    st.info("👋 Sube el archivo 'datos.xlsx' en el menú lateral.")
