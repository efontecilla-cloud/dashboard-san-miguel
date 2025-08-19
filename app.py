import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime
import numpy as np
import os
from flask import send_from_directory


def cargar_datos(archivo_excel):
    try:
        df = pd.read_excel(archivo_excel)
        print(f"Datos cargados: {len(df)} departamentos")
        print(f"Columnas encontradas: {list(df.columns)}")
        
        # Limpiar columnas numéricas que pueden tener espacios o comas
        if 'PRECIO' in df.columns:
            df['PRECIO'] = pd.to_numeric(df['PRECIO'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
        if 'M2' in df.columns:
            df['M2'] = pd.to_numeric(df['M2'].astype(str).str.replace(',', '.'), errors='coerce')
        if 'UF/M2' in df.columns:
            df['UF/M2'] = pd.to_numeric(df['UF/M2'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
        
        # Debug: mostrar estados únicos encontrados
        if 'ESTADO' in df.columns:
            estados_unicos = df['ESTADO'].unique()
            print(f"Estados encontrados: {list(estados_unicos)}")
        
        # Procesar fechas si existe la columna
        if 'FECHA' in df.columns:
            print(f"Procesando columna FECHA...")
            print(f"Primeras 10 fechas raw: {df['FECHA'].head(10).tolist()}")
            print(f"Tipos de datos en FECHA: {df['FECHA'].dtype}")
            
            # Crear una copia para trabajar
            df['FECHA_ORIGINAL'] = df['FECHA'].copy()
            
            # Si ya son datetime, mantenerlas
            if df['FECHA'].dtype == 'datetime64[ns]':
                print("Las fechas ya están en formato datetime")
            else:
                # Intentar múltiples formatos de fecha
                df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
                
                # Si falló, intentar formato específico dd.mm.yyyy
                if df['FECHA'].isna().all():
                    print("Intentando formato dd.mm.yyyy...")
                    df['FECHA'] = pd.to_datetime(df['FECHA_ORIGINAL'], format='%d.%m.%Y', errors='coerce')
                
                # Si aún falló, intentar otros formatos comunes
                if df['FECHA'].isna().all():
                    print("Intentando otros formatos...")
                    for formato in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y']:
                        try:
                            df['FECHA'] = pd.to_datetime(df['FECHA_ORIGINAL'], format=formato, errors='coerce')
                            if not df['FECHA'].isna().all():
                                print(f"Formato exitoso: {formato}")
                                break
                        except:
                            continue
                
                # Si todavía falló, intentar conversión automática más agresiva
                if df['FECHA'].isna().all():
                    print("Intentando conversión automática...")
                    # Limpiar y convertir strings
                    df['FECHA_CLEAN'] = df['FECHA_ORIGINAL'].astype(str).str.strip()
                    df['FECHA'] = pd.to_datetime(df['FECHA_CLEAN'], errors='coerce', dayfirst=True)
            
            print(f"Fechas después del procesamiento - primeras 10: {df['FECHA'].head(10).tolist()}")
            print(f"Fechas no nulas: {df['FECHA'].notna().sum()}")
            print(f"Fechas nulas: {df['FECHA'].isna().sum()}")
            
            # Filtrar fechas falsas (01.01.1900 significa "sin fecha real")
            fechas_antes = df['FECHA'].notna().sum()
            df.loc[df['FECHA'].dt.year == 1900, 'FECHA'] = pd.NaT
            fechas_despues = df['FECHA'].notna().sum()
            
            print(f"Fechas 1900 filtradas: {fechas_antes - fechas_despues}")
            print(f"Fechas válidas finales: {fechas_despues}")
            
            if fechas_despues > 0:
                fecha_min = df['FECHA'].min()
                fecha_max = df['FECHA'].max()
                print(f"Rango de fechas válidas: {fecha_min} - {fecha_max}")
                
                # Agregar columnas auxiliares para análisis temporal
                df['AÑO'] = df['FECHA'].dt.year
                df['MES'] = df['FECHA'].dt.month
                df['AÑO_MES'] = df['FECHA'].dt.to_period('M')
            else:
                print("⚠️ No se encontraron fechas válidas para análisis temporal")
                
        else:
            print("⚠️ No se encontró columna FECHA")
            
        return df
    except Exception as e:
        print(f"Error cargando datos: {e}")
        import traceback
        traceback.print_exc()
        return None

def crear_tabla_ventas_mensuales(df_vendidos):
    """Crear tabla de ventas por mes y año"""
    if df_vendidos.empty:
        return html.Div([
            html.H6("📊 Sin datos de ventas", className="text-center text-muted"),
            html.P("No hay propiedades vendidas para mostrar", className="text-center text-muted")
        ])
    
    if 'FECHA' not in df_vendidos.columns:
        return html.Div([
            html.H6("📊 Sin columna de fechas", className="text-center text-muted"),
            html.P("Los datos no contienen información de fechas", className="text-center text-muted")
        ])
    
    # Filtrar solo las propiedades vendidas (con fecha)
    df_con_fecha = df_vendidos.dropna(subset=['FECHA'])
    
    if df_con_fecha.empty:
        return html.Div([
            html.H6("📊 Sin fechas válidas", className="text-center text-muted"),
            html.P("No hay ventas con fechas válidas para analizar", className="text-center text-muted")
        ])
    
    try:
        # Crear tabla pivote
        tabla_pivot = df_con_fecha.groupby(['AÑO', 'MES']).size().unstack(fill_value=0)
        
        # Agregar totales
        tabla_pivot['TOTAL'] = tabla_pivot.sum(axis=1)
        tabla_pivot.loc['TOTAL'] = tabla_pivot.sum(axis=0)
        
        # Crear nombres de meses
        meses_nombres = {
            1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
            7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
        }
        
        # Crear la tabla HTML
        tabla_html = html.Table([
            # Header
            html.Thead([
                html.Tr([html.Th("AÑO", className="text-center", style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'})] + 
                    [html.Th(meses_nombres.get(mes, f"M{mes}"), className="text-center",
                            style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'}) 
                        for mes in sorted(tabla_pivot.columns[:-1])] +
                    [html.Th("TOTAL", className="text-center", 
                            style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'})])
            ]),
            # Body
            html.Tbody([
                html.Tr([
                    html.Td(html.B(str(int(año))) if año != 'TOTAL' else html.B("TOTAL"), 
                        className="text-center",
                        style={'font-weight': 'bold', 'background-color': '#2d2c55', 'color': 'white'} if año == 'TOTAL' else {'font-weight': 'bold'}),
                    *[html.Td(str(int(tabla_pivot.loc[año, mes])) if tabla_pivot.loc[año, mes] > 0 else "-",
                            className="text-center",
                            style={'background-color': '#2d2c55', 'color': 'white'} if año == 'TOTAL' else {}) 
                    for mes in sorted(tabla_pivot.columns[:-1])],
                    html.Td(html.B(str(int(tabla_pivot.loc[año, 'TOTAL']))), 
                        className="text-center",
                        style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'} if año == 'TOTAL' else {'background-color': '#f8f9fa', 'font-weight': 'bold'})
                ], style={'background-color': '#2d2c55'} if año == 'TOTAL' else {})
                for año in tabla_pivot.index
            ])  
        ], className="table table-striped table-sm table-bordered")
        
        return html.Div([
            html.P(f"📊 Total ventas analizadas: {len(df_con_fecha)}", 
                   className="text-center text-muted mb-2"),
            tabla_html
        ])
        
    except Exception as e:
        print(f"Error creando tabla: {e}")
        return html.Div([
            html.H6("❌ Error procesando datos", className="text-center text-danger"),
            html.P(f"Error: {str(e)}", className="text-center text-muted")
        ])

def crear_tabla_precios_mensuales(df_vendidos):
    """Crear tabla de precios promedio UF/m² por mes y año"""
    if df_vendidos.empty:
        return html.Div([
            html.H6("📊 Sin datos de precios", className="text-center text-muted"),
            html.P("No hay propiedades vendidas para mostrar", className="text-center text-muted")
        ])
    
    if 'FECHA' not in df_vendidos.columns:
        return html.Div([
            html.H6("📊 Sin columna de fechas", className="text-center text-muted"),
            html.P("Los datos no contienen información de fechas", className="text-center text-muted")
        ])
    
    # Filtrar solo las propiedades vendidas (con fecha)
    df_con_fecha = df_vendidos.dropna(subset=['FECHA'])
    
    if df_con_fecha.empty:
        return html.Div([
            html.H6("📊 Sin fechas válidas", className="text-center text-muted"),
            html.P("No hay ventas con fechas válidas para analizar", className="text-center text-muted")
        ])
    
    if 'UF/M2' not in df_con_fecha.columns:
        return html.Div([
            html.H6("📊 Sin datos UF/m²", className="text-center text-muted"),
            html.P("No hay información de precios UF/m²", className="text-center text-muted")
        ])
    
    try:
        # Crear tabla pivote con promedio de UF/M2
        tabla_pivot = df_con_fecha.groupby(['AÑO', 'MES'])['UF/M2'].mean().unstack(fill_value=0)
        
        # Agregar promedio total por año
        tabla_pivot['PROMEDIO'] = df_con_fecha.groupby('AÑO')['UF/M2'].mean()
        
        # Agregar promedio total por mes
        promedios_mes = df_con_fecha.groupby('MES')['UF/M2'].mean()
        promedio_general = df_con_fecha['UF/M2'].mean()
        
        # Crear fila de totales
        fila_totales = {}
        for mes in tabla_pivot.columns[:-1]:  # Excluir columna PROMEDIO
            if mes in promedios_mes.index:
                fila_totales[mes] = promedios_mes[mes]
            else:
                fila_totales[mes] = 0
        fila_totales['PROMEDIO'] = promedio_general
        
        # Agregar fila de totales
        tabla_pivot.loc['PROMEDIO'] = pd.Series(fila_totales)
        
        # Crear nombres de meses
        meses_nombres = {
            1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
            7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
        }
        
        # Crear la tabla HTML
        tabla_html = html.Table([
            # Header
            html.Thead([
                html.Tr([html.Th("AÑO", className="text-center", style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'})] + 
                    [html.Th(meses_nombres.get(mes, f"M{mes}"), className="text-center",
                            style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'}) 
                        for mes in sorted(tabla_pivot.columns[:-1])] +
                    [html.Th("PROMEDIO", className="text-center", 
                            style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'})])
            ]),
            # Body
            html.Tbody([
                html.Tr([
                    html.Td(html.B(str(int(año))) if año != 'PROMEDIO' else html.B("PROMEDIO"), 
                        className="text-center",
                        style={'font-weight': 'bold', 'background-color': '#2d2c55', 'color': 'white'} if año == 'PROMEDIO' else {'font-weight': 'bold'}),
                    *[html.Td(f"{tabla_pivot.loc[año, mes]:.1f}" if tabla_pivot.loc[año, mes] > 0 else "-",
                            className="text-center",
                            style={'background-color': '#2d2c55', 'color': 'white'} if año == 'PROMEDIO' else {}) 
                    for mes in sorted(tabla_pivot.columns[:-1])],
                    html.Td(html.B(f"{tabla_pivot.loc[año, 'PROMEDIO']:.1f}"), 
                        className="text-center",
                        style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'} if año == 'PROMEDIO' else {'background-color': '#e8f4f8', 'font-weight': 'bold'})
                ], style={'background-color': '#2d2c55'} if año == 'PROMEDIO' else {})
                for año in tabla_pivot.index
            ])
        ], className="table table-striped table-sm table-bordered")
        
        return html.Div([
            html.P(f"💰 Precios promedio UF/m² por período", 
                   className="text-center text-muted mb-2"),
            tabla_html
        ])
        
    except Exception as e:
        print(f"Error creando tabla precios: {e}")
        return html.Div([
            html.H6("❌ Error procesando precios", className="text-center text-danger"),
            html.P(f"Error: {str(e)}", className="text-center text-muted")
        ])

def crear_grafico_3d(df_filtrado):
    """Crear gráfico 3D del edificio con layout 3x3"""
    
    colores_estados = {
        'Disponible': '#28A745',    # Verde
        'Reserva': '#FFC107',       # Amarillo  
        'Promesa': '#DC3545',       # Rojo
        'Stock Ausente': '#6C757D'  # Gris
    }
    
    # Layout 3x3 con escaleras en el centro (posición 1,1)
    # Tipos y sus orientaciones:
    posiciones = {
        2: (0, 2),  # Poniente-Norte (izquierda arriba)
        3: (1, 2),  # Norte (centro arriba)  
        4: (2, 2),  # Norte-Oriente (derecha arriba)
        5: (2, 1),  # Oriente (derecha centro)
        6: (2, 0),  # Oriente-Sur (derecha abajo)
        7: (1, 0),  # Sur (centro abajo)
        8: (0, 0),  # Sur-Poniente (izquierda abajo)
        1: (0, 1)   # Poniente (izquierda centro)
        # Escaleras en (1, 1) - centro
    }
    
    escalera_pos = (1, 1)
    
    fig = go.Figure()
    
    # Crear cubos para cada departamento
    for _, depto in df_filtrado.iterrows():
        tipo = int(depto['TIPO'])
        if tipo not in posiciones:
            continue
            
        x, y = posiciones[tipo]
        z = depto['PISO']
        
        # Normalizar el estado para asegurar coincidencia exacta
        estado_normalizado = str(depto['ESTADO']).strip()
        color = colores_estados.get(estado_normalizado, '#CCCCCC')
        
        # Debug: verificar que el estado se esté leyendo correctamente
        if estado_normalizado not in colores_estados:
            print(f"⚠️ Estado desconocido: '{estado_normalizado}' - usando color gris por defecto")
        
        precio = depto.get('PRECIO', 0)
        superficie = depto.get('M2', 0)
        uf_m2 = depto.get('UF/M2', 0)
        tipologia = depto.get('TIPOLOGIA', 'N/A')
        
        # Información de fecha si está disponible
        fecha_info = ""
        if 'FECHA' in depto.index and pd.notna(depto['FECHA']):
            fecha_info = f"<span style='color:#0C0404;'><b>Fecha:</b></span> <b>{depto['FECHA'].strftime('%d/%m/%Y')}</b><br>"
        
        # Mapeo de orientaciones
        orientaciones = {
            1: 'Poniente',
            2: 'Poniente-Norte', 
            3: 'Norte',
            4: 'Norte-Oriente',
            5: 'Oriente',
            6: 'Oriente-Sur',
            7: 'Sur',
            8: 'Sur-Poniente'
        }
        
        orientacion = orientaciones.get(tipo, 'N/A')
        
        hover_text = f"""<b style='color:#0C0404; font-size:14px;'>🏢 Tipo {tipo} - Piso {z}</b><br>
        <span style='color:#0C0404;'><b>Estado:</b></span> <b>{estado_normalizado}</b><br>
        <span style='color:#0C0404;'><b>Precio:</b></span> <b>UF {precio:,.0f}</b><br>
        <span style='color:#0C0404;'><b>Superficie:</b></span> <b>{superficie} m²</b><br>
        <span style='color:#0C0404;'><b>UF/m²:</b></span> <b>{uf_m2:.2f}</b><br>
        <span style='color:#0C0404;'><b>Tipología:</b></span> <b>{tipologia}</b><br>
        <span style='color:#0C0404;'><b>Orientación:</b></span> <b>{orientacion}</b><br>
        {fecha_info}"""
        
        # Cubo del departamento
        fig.add_trace(go.Mesh3d(
            x=[x, x+1, x+1, x, x, x+1, x+1, x],
            y=[y, y, y+1, y+1, y, y, y+1, y+1],
            z=[z, z, z, z, z+1, z+1, z+1, z+1],
            i=[7, 0, 0, 0, 4, 4, 6, 1, 4, 0, 3, 6],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 6, 5, 5, 7, 7],
            color=color,
            opacity=1.0,
            hovertemplate=hover_text + "<extra></extra>",
            showscale=False
        ))
        
        # Bordes del cubo
        edges_x = [x, x+1, x+1, x, x, x, x+1, x+1, x+1, x+1, x, x, x, x+1, x+1, x]
        edges_y = [y, y, y+1, y+1, y, y, y, y, y+1, y+1, y+1, y+1, y, y, y+1, y+1]
        edges_z = [z, z, z, z, z, z+1, z+1, z+1, z+1, z, z, z+1, z+1, z+1, z+1, z]
        
        fig.add_trace(go.Scatter3d(
            x=edges_x, y=edges_y, z=edges_z,
            mode='lines',
            line=dict(color='black', width=1),
            showlegend=False,
            hoverinfo='skip'
        ))
    
    # Escaleras (centro del edificio)
    pisos_filtrados = df_filtrado['PISO'].unique() if len(df_filtrado) > 0 else []
    for piso in pisos_filtrados:
        x_esc, y_esc = escalera_pos
        
        fig.add_trace(go.Mesh3d(
            x=[x_esc, x_esc+1, x_esc+1, x_esc, x_esc, x_esc+1, x_esc+1, x_esc],
            y=[y_esc, y_esc, y_esc+1, y_esc+1, y_esc, y_esc, y_esc+1, y_esc+1],
            z=[piso, piso, piso, piso, piso+1, piso+1, piso+1, piso+1],
            i=[7, 0, 0, 0, 4, 4, 6, 1, 4, 0, 3, 6],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 6, 5, 5, 7, 7],
            color='#E9ECEF',
            opacity=1.0,
            hovertemplate=f"<b style='color:#2C3E50;'>🚶‍♂️ ESCALERAS</b><br>Piso {piso}<extra></extra>",
            showscale=False
        ))
    
    fig.update_layout(
        scene=dict(
            xaxis=dict(showticklabels=False, title='', showgrid=False, range=[0, 3]),
            yaxis=dict(showticklabels=False, title='', showgrid=False, range=[0, 3]),
            zaxis=dict(showticklabels=False, title='', showgrid=False, 
                      range=[1.5, max(df_filtrado['PISO']) + 1] if len(df_filtrado) > 0 else [1.5, 16]),
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.2)),
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=3),
            bgcolor='#F8F9FA'
        ),
        showlegend=False,
        height=600,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig



# Crear la aplicación Dash con configuración de assets
app = dash.Dash(__name__, 
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                assets_folder='assets',
                suppress_callback_exceptions=True)

# IMPORTANTE: Para deploy
server = app.server

# Configurar servicio de archivos estáticos para producción
@server.route('/assets/<filename>')
def download_file(filename):
    return send_from_directory('assets', filename)

# Debug: verificar archivos
if os.path.exists('assets'):
    assets_files = os.listdir('assets')
    print(f"📁 Assets encontrados: {assets_files}")
    if 'LOGO.PNG' in assets_files:
        print("✅ LOGO.PNG encontrado")
    else:
        print("❌ LOGO.PNG no encontrado")
else:
    print("❌ Carpeta assets no existe")


# Cargar datos globalmente
print("🔄 Cargando datos...")
df_global = cargar_datos("Datos.xlsx")

# Layout de la aplicación
app.layout = dbc.Container([
    
    # Header principal con fondo azul
    dbc.Row([
        dbc.Col([
            html.Div([
                dbc.Row([
                    dbc.Col([
                        html.H1("🏢 Dashboard San Miguel Etapa 2", 
                            className="display-4 mb-2",
                            style={'color': 'white', 'fontWeight': 'bold'}),
                        html.P("Pagina web creada y administrada por Banmerchant", 
                            className="lead", style={'color': '#E8E9EA'})
                    ], width=10),
                    dbc.Col([
                        html.Img(
                            src="/assets/LOGO.png",
                            style={
                                'height': '80px',
                                'width': 'auto',
                                'float': 'right'
                            }
                        )
                    ], width=2, className="d-flex align-items-center justify-content-end")
                ])
            ], className="rounded shadow-sm p-4 mb-4", style={'background-color': '#2d2c55'})
        ], width=12)
    ]),
        
    # Panel de filtros y estadísticas
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4("🔍 Filtros y Controles", className="mb-0", style={'color': 'white'})
                ], style={'background-color': '#2d2c55'}),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Seleccionar Pisos:", className="fw-bold mb-2"),
                            dcc.Dropdown(
                                id='filtro-pisos',
                                multi=True,
                                placeholder="Todos los pisos seleccionados por defecto",
                                className="mb-3"
                            ),
                        ], width=4),
                        dbc.Col([
                            html.Label("Seleccionar Orientación:", className="fw-bold mb-2"),
                            dcc.Dropdown(
                                id='filtro-orientacion',
                                options=[
                                    {'label': '🧭 Todas las orientaciones', 'value': 'todas'},
                                    {'label': '⬆️ Norte (N)', 'value': 'norte'},
                                    {'label': '➡️ Oriente (E)', 'value': 'oriente'},
                                    {'label': '⬇️ Sur (S)', 'value': 'sur'},
                                    {'label': '⬅️ Poniente (W)', 'value': 'poniente'}
                                ],
                                value='todas',
                                placeholder="Seleccionar orientación",
                                className="mb-3"
                            ),
                        ], width=4),
                        dbc.Col([
                            html.Label("Seleccionar Tipología:", className="fw-bold mb-2"),
                            dcc.Dropdown(
                                id='filtro-tipologia',
                                multi=True,
                                placeholder="Todas las tipologías",
                                className="mb-3"
                            ),
                        ], width=4)
                    ]),
                    dbc.Row([
                        dbc.Col([
                            html.Label("Vista Rápida:", className="fw-bold mb-2"),
                            dbc.ButtonGroup([
                                dbc.Button("🏠 Todos", id="btn-todos", 
                                          style={'background-color': '#2d2c55', 'border-color': '#2d2c55', 'color': 'white'}, 
                                          size="sm"),
                                dbc.Button("🏔️ Pisos Altos", id="btn-altos", 
                                          style={'background-color': '#2d2c55', 'border-color': '#2d2c55', 'color': 'white'}, 
                                          size="sm"),
                                dbc.Button("🏪 Pisos Bajos", id="btn-bajos", 
                                          style={'background-color': '#2d2c55', 'border-color': '#2d2c55', 'color': 'white'}, 
                                          size="sm"),
                            ], className="d-grid")
                        ], width=6),
                        dbc.Col([
                            html.Label("Estados:", className="fw-bold mb-2"),
                            dcc.Dropdown(
                                id='filtro-estados',
                                options=[
                                    {'label': '📊 Todos los estados', 'value': 'todos'},
                                    {'label': '🟢 Solo Disponibles', 'value': 'disponible'},
                                    {'label': '🟡 Solo Reservas', 'value': 'reserva'},
                                    {'label': '🔴 Solo Promesas', 'value': 'promesa'}
                                ],
                                value='todos',
                                placeholder="Seleccionar estados"
                            ),
                        ], width=6)
                    ]),
                    html.Hr(),
                    html.Div(id="info-filtros", className="text-muted")
                ])
            ], className="shadow-sm")
        ], width=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("📊 Métricas Generales", className="mb-0", style={'color': 'white'})
                ], style={'background-color': '#2d2c55'}),
                dbc.CardBody([
                    html.Div(id="metricas-resumen", className="text-center")
                ])
            ], className="shadow-sm")
        ], width=4)
    ], className="mb-4"),
    
    # Gráfico 3D principal con tablas laterales
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4("🏢 Visualización 3D", className="mb-0", style={'color': 'white'})
                ], style={'background-color': '#2d2c55'}),
                dbc.CardBody([
                    dcc.Loading(
                        id="loading-3d",
                        type="circle",
                        children=[
                            dcc.Graph(
                                id='grafico-3d',
                                config={
                                    'displayModeBar': True,
                                    'displaylogo': False,
                                    'modeBarButtonsToRemove': ['pan2d', 'lasso2d']
                                }
                            )
                        ]
                    )
                ])
            ], className="shadow-sm")
        ], width=8),
        dbc.Col([
            # Tabla de ventas mensuales
            dbc.Card([
                dbc.CardHeader([
                    html.H5("📊 Ventas por Mes/Año", className="mb-0", style={'color': 'white'})
                ], style={'background-color': '#2d2c55'}),
                dbc.CardBody([
                    html.Div(
                        id="tabla-ventas-mensuales",
                        style={'maxHeight': '300px', 'overflowY': 'auto'}
                    )
                ], style={'padding': '10px'})
            ], className="shadow-sm mb-3"),
            
            # Tabla de precios mensuales
            dbc.Card([
                dbc.CardHeader([
                    html.H5("💰 Precios UF/m² por Mes/Año", className="mb-0", style={'color': 'white'})
                ], style={'background-color': '#2d2c55'}),
                dbc.CardBody([
                    html.Div(
                        id="tabla-precios-mensuales",
                        style={'maxHeight': '300px', 'overflowY': 'auto'}
                    )
                ], style={'padding': '10px'})
            ], className="shadow-sm")
        ], width=4)
    ], className="mb-4"),
    
    # Información de orientaciones
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4("🧭 Mapa de Orientaciones", className="mb-0", style={'color': 'white'})
                ], style={'background-color': '#2d2c55'}),
                dbc.CardBody([
                    html.Div([
                        html.P("Distribución de tipos por orientación:", className="mb-3 fw-bold"),
                        dbc.Row([
                            dbc.Col([
                                html.Div([
                                    html.H6("⬆️ NORTE", className="text-center mb-2", style={'color': '#007BFF'}),
                                    html.P("• Tipo 2: Poniente-Norte", className="mb-1"),
                                    html.P("• Tipo 3: Norte", className="mb-1"),
                                    html.P("• Tipo 4: Norte-Oriente", className="mb-0")
                                ], className="border rounded p-3", style={'border-color': '#4a4a7a !important'})
                            ], width=3),
                            dbc.Col([
                                html.Div([
                                    html.H6("➡️ ORIENTE", className="text-center mb-2", style={'color': '#28A745'}),
                                    html.P("• Tipo 3: Norte", className="mb-1"),
                                    html.P("• Tipo 4: Norte-Oriente", className="mb-1"),
                                    html.P("• Tipo 5: Oriente", className="mb-0")
                                ], className="border rounded p-3", style={'border-color': '#4a4a7a !important'})
                            ], width=3),
                            dbc.Col([
                                html.Div([
                                    html.H6("⬇️ SUR", className="text-center mb-2", style={'color': '#FFC107'}),
                                    html.P("• Tipo 6: Oriente-Sur", className="mb-1"),
                                    html.P("• Tipo 7: Sur", className="mb-1"),
                                    html.P("• Tipo 8: Sur-Poniente", className="mb-0")
                                ], className="border rounded p-3", style={'border-color': '#4a4a7a !important'})
                            ], width=3),
                            dbc.Col([
                                html.Div([
                                    html.H6("⬅️ PONIENTE", className="text-center mb-2", style={'color': '#DC3545'}),
                                    html.P("• Tipo 8: Sur-Poniente", className="mb-1"),
                                    html.P("• Tipo 1: Poniente", className="mb-1"),
                                    html.P("• Tipo 2: Poniente-Norte", className="mb-0")
                                ], className="border rounded p-3", style={'border-color': '#4a4a7a !important'})
                            ], width=3)
                        ])
                    ])
                ])
            ], className="shadow-sm")
        ], width=12)
    ])
    
], fluid=True, style={'backgroundColor': '#F8F9FA', 'minHeight': '100vh', 'padding': '20px'})

# Callbacks

@app.callback(
    [Output('filtro-pisos', 'options'),
     Output('filtro-pisos', 'value'),
     Output('filtro-tipologia', 'options'),
     Output('filtro-tipologia', 'value')],
    [Input('filtro-pisos', 'id')]
)
def inicializar_filtros(_):
    if df_global is not None:
        # Opciones de pisos (del 2 al 15)
        pisos_disponibles = sorted(df_global['PISO'].unique())
        opciones_pisos = [{'label': f'Piso {piso}', 'value': piso} for piso in pisos_disponibles]
        
        # Opciones de tipología
        if 'TIPOLOGIA' in df_global.columns:
            tipologias_disponibles = sorted(df_global['TIPOLOGIA'].dropna().unique())
            opciones_tipologia = [{'label': f'{tip}', 'value': tip} for tip in tipologias_disponibles]
        else:
            opciones_tipologia = []
        
        return opciones_pisos, pisos_disponibles, opciones_tipologia, []
    return [], [], [], []

@app.callback(
    Output('filtro-pisos', 'value', allow_duplicate=True),
    [Input('btn-todos', 'n_clicks'),
     Input('btn-altos', 'n_clicks'),
     Input('btn-bajos', 'n_clicks')],
    prevent_initial_call=True
)
def botones_vista_rapida(btn_todos, btn_altos, btn_bajos):
    if df_global is None:
        return []
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    pisos_disponibles = sorted(df_global['PISO'].unique())
    
    if button_id == 'btn-todos':
        return pisos_disponibles
    elif button_id == 'btn-altos':
        # Pisos altos: del 9 al 15
        return [p for p in pisos_disponibles if p >= 9]
    elif button_id == 'btn-bajos':
        return [p for p in pisos_disponibles if p <= 8]
    
    return dash.no_update

@app.callback(
    [Output('grafico-3d', 'figure'),
     Output('metricas-resumen', 'children'),
     Output('info-filtros', 'children'),
     Output('tabla-ventas-mensuales', 'children'),
     Output('tabla-precios-mensuales', 'children')],
    [Input('filtro-pisos', 'value'),
     Input('filtro-orientacion', 'value'),
     Input('filtro-estados', 'value'),
     Input('filtro-tipologia', 'value')]
)
def actualizar_dashboard(pisos_seleccionados, orientacion_seleccionada, estados_seleccionados, tipologias_seleccionadas):
    if df_global is None:
        fig_vacia = go.Figure()
        fig_vacia.add_annotation(text="❌ No se pudieron cargar los datos", x=0.5, y=0.5)
        return fig_vacia, html.Div("Error en datos"), "Error", html.Div("Error"), html.Div("Error")
    
    # Filtrar datos por pisos
    if pisos_seleccionados and len(pisos_seleccionados) > 0:
        df_filtrado = df_global[df_global['PISO'].isin(pisos_seleccionados)]
    else:
        df_filtrado = df_global.copy()
    
    # Filtrar por orientación
    orientaciones_tipos = {
        'norte': [2, 3, 4],      # ARRIBA: Tipos 2, 3, 4
        'oriente': [6, 4, 5],    # DERECHA: Tipos 3, 4, 5  
        'sur': [6, 7, 8],        # ABAJO: Tipos 6, 7, 8
        'poniente': [8, 1, 2]    # IZQUIERDA: Tipos 8, 1, 2
    }
    
    if orientacion_seleccionada in orientaciones_tipos:
        tipos_filtrados = orientaciones_tipos[orientacion_seleccionada]
        df_filtrado = df_filtrado[df_filtrado['TIPO'].isin(tipos_filtrados)]
    
    # Filtrar por estados
    if estados_seleccionados == 'disponible':
        df_filtrado = df_filtrado[df_filtrado['ESTADO'] == 'Disponible']
    elif estados_seleccionados == 'reserva':
        df_filtrado = df_filtrado[df_filtrado['ESTADO'] == 'Reserva']
    elif estados_seleccionados == 'promesa':
        df_filtrado = df_filtrado[df_filtrado['ESTADO'] == 'Promesa']
    
    # Filtrar por tipología
    if tipologias_seleccionadas and len(tipologias_seleccionadas) > 0 and 'TIPOLOGIA' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['TIPOLOGIA'].isin(tipologias_seleccionadas)]
    
    # Crear gráfico 3D
    fig_3d = crear_grafico_3d(df_filtrado)
    
    # Para análisis temporal, usar solo datos vendidos (que tienen fecha real, no 1900)
    if 'FECHA' in df_global.columns:
        df_vendidos = df_global[df_global['FECHA'].notna()]
        print(f"Debug: {len(df_vendidos)} ventas con fecha encontradas de {len(df_global)} total")
    else:
        df_vendidos = pd.DataFrame()
        print("Debug: No hay columna FECHA en los datos")
        
    # Aplicar los mismos filtros al análisis temporal
    if not df_vendidos.empty:
        if pisos_seleccionados and len(pisos_seleccionados) > 0:
            df_vendidos = df_vendidos[df_vendidos['PISO'].isin(pisos_seleccionados)]
        
        if orientacion_seleccionada in orientaciones_tipos:
            tipos_filtrados = orientaciones_tipos[orientacion_seleccionada]
            df_vendidos = df_vendidos[df_vendidos['TIPO'].isin(tipos_filtrados)]
        
        if tipologias_seleccionadas and len(tipologias_seleccionadas) > 0 and 'TIPOLOGIA' in df_vendidos.columns:
            df_vendidos = df_vendidos[df_vendidos['TIPOLOGIA'].isin(tipologias_seleccionadas)]
    
    # Crear análisis temporal
    tabla_ventas = crear_tabla_ventas_mensuales(df_vendidos)
    tabla_precios = crear_tabla_precios_mensuales(df_vendidos)
    
    # Calcular métricas totales
    total_precio = df_filtrado['PRECIO'].sum() if 'PRECIO' in df_filtrado.columns else 0
    total_m2 = df_filtrado['M2'].sum() if 'M2' in df_filtrado.columns else 0
    promedio_uf_m2 = df_filtrado['UF/M2'].mean() if 'UF/M2' in df_filtrado.columns and len(df_filtrado) > 0 else 0
    total_departamentos = len(df_filtrado)
    
    # Calcular métricas por estado
    estados = ['Disponible', 'Reserva', 'Promesa']
    metricas_por_estado = {}
    
    for estado in estados:
        df_estado = df_filtrado[df_filtrado['ESTADO'] == estado]
        metricas_por_estado[estado] = {
            'cantidad': len(df_estado),
            'precio': df_estado['PRECIO'].sum() if 'PRECIO' in df_estado.columns else 0,
            'm2': df_estado['M2'].sum() if 'M2' in df_estado.columns else 0,
            'uf_m2': df_estado['UF/M2'].mean() if 'UF/M2' in df_estado.columns and len(df_estado) > 0 else 0
        }
    
    # Crear componente de métricas
    metricas_componente = html.Div([
        # Métricas Totales
        html.H5("📊 MÉTRICAS TOTALES", className="text-center mb-3", style={'color': '#2C3E50', 'fontWeight': 'bold'}),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H4(f"{total_departamentos}", className="mb-0", style={'color': '#6C757D', 'fontWeight': 'bold'}),
                    html.Small("Total Departamentos", className="text-muted")
                ], className="text-center p-2 border rounded")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H4(f"UF {total_precio:,.0f}", className="mb-0", style={'color': '#007BFF', 'fontWeight': 'bold'}),
                    html.Small("Total Precio", className="text-muted")
                ], className="text-center p-2 border rounded")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H4(f"{total_m2:,.1f} m²", className="mb-0", style={'color': '#FF6B6B', 'fontWeight': 'bold'}),
                    html.Small("Total Superficie", className="text-muted")
                ], className="text-center p-2 border rounded")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H4(f"{promedio_uf_m2:.2f}", className="mb-0", style={'color': '#9C27B0', 'fontWeight': 'bold'}),
                    html.Small("Promedio UF/m²", className="text-muted")
                ], className="text-center p-2 border rounded")
            ], width=3)
        ], className="mb-4"),
        
        # Separador
        html.Hr(),
        
        # Métricas por Estado
        html.H5("📈 MÉTRICAS POR ESTADO", className="text-center mb-3", style={'color': '#2C3E50', 'fontWeight': 'bold'}),
        
        # DISPONIBLES
        html.H6("🟢 DISPONIBLES", className="mb-2", style={'color': '#28A745', 'fontWeight': 'bold'}),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Disponible']['cantidad']}", className="mb-0", style={'color': '#28A745'}),
                    html.Small("Cantidad", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"UF {metricas_por_estado['Disponible']['precio']:,.0f}", className="mb-0", style={'color': '#28A745'}),
                    html.Small("Precio Total", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Disponible']['m2']:,.1f} m²", className="mb-0", style={'color': '#28A745'}),
                    html.Small("Superficie", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Disponible']['uf_m2']:.2f}", className="mb-0", style={'color': '#28A745'}),
                    html.Small("Prom. UF/m²", className="text-muted")
                ], className="text-center p-1")
            ], width=3)
        ], className="mb-2"),
        
        # RESERVAS
        html.H6("🟡 RESERVAS", className="mb-2", style={'color': '#FFC107', 'fontWeight': 'bold'}),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Reserva']['cantidad']}", className="mb-0", style={'color': '#FFC107'}),
                    html.Small("Cantidad", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"UF {metricas_por_estado['Reserva']['precio']:,.0f}", className="mb-0", style={'color': '#FFC107'}),
                    html.Small("Precio Total", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Reserva']['m2']:,.1f} m²", className="mb-0", style={'color': '#FFC107'}),
                    html.Small("Superficie", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Reserva']['uf_m2']:.2f}", className="mb-0", style={'color': '#FFC107'}),
                    html.Small("Prom. UF/m²", className="text-muted")
                ], className="text-center p-1")
            ], width=3)
        ], className="mb-2"),
        
        # PROMESAS
        html.H6("🔴 PROMESAS", className="mb-2", style={'color': '#DC3545', 'fontWeight': 'bold'}),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Promesa']['cantidad']}", className="mb-0", style={'color': '#DC3545'}),
                    html.Small("Cantidad", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"UF {metricas_por_estado['Promesa']['precio']:,.0f}", className="mb-0", style={'color': '#DC3545'}),
                    html.Small("Precio Total", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Promesa']['m2']:,.1f} m²", className="mb-0", style={'color': '#DC3545'}),
                    html.Small("Superficie", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Promesa']['uf_m2']:.2f}", className="mb-0", style={'color': '#DC3545'}),
                    html.Small("Prom. UF/m²", className="text-muted")
                ], className="text-center p-1")
            ], width=3)
        ])
    ])
    
    # Información de filtros mejorada
    total_disponibles = metricas_por_estado['Disponible']['cantidad']
    total_reservas = metricas_por_estado['Reserva']['cantidad']
    total_promesas = metricas_por_estado['Promesa']['cantidad']
    
    # Crear texto descriptivo de filtros
    filtros_texto = []
    
    if pisos_seleccionados and len(pisos_seleccionados) > 0:
        pisos_texto = ", ".join([f"Piso {p}" for p in sorted(pisos_seleccionados)])
        filtros_texto.append(f"Pisos: {pisos_texto}")
    else:
        filtros_texto.append("Pisos: Todos")
    
    orientacion_texto = {
        'todas': 'Todas las orientaciones',
        'norte': '⬆️ Norte únicamente',
        'oriente': '➡️ Oriente únicamente',
        'sur': '⬇️ Sur únicamente',
        'poniente': '⬅️ Poniente únicamente'
    }
    filtros_texto.append(f"Orientación: {orientacion_texto.get(orientacion_seleccionada, 'Todas')}")
    
    estado_texto = {
        'todos': 'Todos los estados',
        'disponible': '🟢 Solo Disponibles',
        'reserva': '🟡 Solo Reservas',
        'promesa': '🔴 Solo Promesas'
    }
    filtros_texto.append(f"Estados: {estado_texto.get(estados_seleccionados, 'Todos')}")
    
    if tipologias_seleccionadas and len(tipologias_seleccionadas) > 0:
        tip_texto = ", ".join(tipologias_seleccionadas)
        filtros_texto.append(f"Tipologías: {tip_texto}")
    
    info_text = html.Div([
        html.P([
            "📊 ", html.Strong("Filtros aplicados: "), " | ".join(filtros_texto)
        ], className="mb-1"),
        html.P([
            html.Strong(f"Total: {total_departamentos} departamentos | "),
            html.Span(f"🟢 {total_disponibles} Disponibles", className="me-3"),
            html.Span(f"🟡 {total_reservas} Reservas", className="me-3"),
            html.Span(f"🔴 {total_promesas} Promesas")
        ], className="mb-0")
    ])
    
    return fig_3d, metricas_componente, info_text, tabla_ventas, tabla_precios


if __name__ == "__main__":
    app.run(debug=True)
