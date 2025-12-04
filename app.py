import streamlit as st
import pandas as pd
import math
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- FUNCIONES AUXILIARES ---
@st.cache_data
def cargar_excel(archivo):
    xls = pd.ExcelFile(archivo)
    df_cajas = pd.read_excel(xls, "CATALOGO_CAJAS")
    df_reglas = pd.read_excel(xls, "REGLAS_EMPAQUETADO")
    df_receta = pd.read_excel(xls, "RECETA_MODELOS")
    df_vehiculos = pd.read_excel(xls, "VEHICULOS_CONTENEDORES")
    df_palets = pd.read_excel(xls, "PALETS_SOPORTES")
    df_comp = pd.read_excel(xls, "COMPONENTES")
    
    for df in [df_cajas, df_reglas, df_receta, df_vehiculos, df_palets, df_comp]:
        df.columns = df.columns.str.strip()
        
    return df_cajas, df_reglas, df_receta, df_vehiculos, df_palets, df_comp

def get_cube_mesh(x, y, z, dx, dy, dz, color, name):
    return go.Mesh3d(
        x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
        y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
        z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
        i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
        j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
        k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
        color=color, opacity=1.0, name=name, flatshading=True, showscale=False, hoverinfo='name'
    )

def draw_truck_3d(bin_obj, w, h, d):
    fig = go.Figure()
    # Contorno Camión
    lines_x = [0, w, w, 0, 0, 0, w, w, 0, 0, w, w, w, w, 0, 0]
    lines_y = [0, 0, h, h, 0, 0, 0, h, h, 0, 0, 0, h, h, h, h]
    lines_z = [0, 0, 0, 0, 0, d, d, d, d, d, d, 0, 0, d, d, 0]
    fig.add_trace(go.Scatter3d(x=lines_x, y=lines_y, z=lines_z, mode='lines', line=dict(color='black', width=4), name='Camión'))

    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE']
    for item in bin_obj.items:
        color = colors[hash(item.name.split('-')[0]) % len(colors)]
        fig.add_trace(get_cube_mesh(float(item.position[0]), float(item.position[1]), float(item.position[2]),
                                    float(item.width), float(item.height), float(item.depth), color, item.name))

    fig.update_layout(scene=dict(xaxis=dict(range=[0, w+100]), yaxis=dict(range=[0, h+100]), zaxis=dict(range=[0, d+100]), aspectmode='data'), margin=dict(l=0,r=0,b=0,t=0), height=600)
    return fig

# --- CONFIGURACIÓN PÁGINA ---
st.set_page_config(page_title="Calculadora Grupaje 3D", layout="wide", page_icon="🚛")
st.title("🚛 Calculadora de Carga: Pedidos Mixtos (Grupaje)")

# --- ESTADO DE SESIÓN (CARRITO) ---
if 'pedido' not in st.session_state:
