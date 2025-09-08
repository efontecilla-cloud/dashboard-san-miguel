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
        
        # Calcular velocidad de venta (ventas por mes promedio)
        # Fecha inicio: Diciembre 2021
        from datetime import datetime
        fecha_inicio = datetime(2021, 12, 1)
        fecha_actual = datetime.now()
        
        # Calcular velocidad por año (excluyendo la fila TOTAL)
        velocidades_año = {}
        for año in tabla_pivot.index[:-1]:  # Excluir 'TOTAL'
            if año == 'TOTAL':
                continue
            año_int = int(año)
            
            # Calcular meses transcurridos en ese año
            if año_int == 2021:
                meses_año = 1  # Solo diciembre
            elif año_int == fecha_actual.year:
                meses_año = fecha_actual.month
            else:
                meses_año = 12
            
            ventas_año = tabla_pivot.loc[año, 'TOTAL']
            velocidades_año[año] = ventas_año / meses_año if meses_año > 0 else 0
        
        # Velocidad total (desde diciembre 2021 hasta ahora)
        total_ventas = tabla_pivot.loc['TOTAL', 'TOTAL']
        meses_totales = ((fecha_actual.year - 2021) * 12 + fecha_actual.month) - 11  # Desde dic 2021
        velocidad_total = total_ventas / meses_totales if meses_totales > 0 else 0
        
        # Agregar columna de velocidad
        tabla_pivot['VEL/MES'] = 0.0
        for año in velocidades_año:
            tabla_pivot.loc[año, 'VEL/MES'] = velocidades_año[año]
        tabla_pivot.loc['TOTAL', 'VEL/MES'] = velocidad_total
        
        # Crear nombres de meses
        meses_nombres = {
            1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
            7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
        }
        
        # Crear la tabla HTML (modificar el header y body)
        tabla_html = html.Table([
            # Header
            html.Thead([
                html.Tr([html.Th("AÑO", className="text-center", style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'})] + 
                    [html.Th(meses_nombres.get(mes, f"M{mes}"), className="text-center",
                            style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'}) 
                        for mes in sorted(tabla_pivot.columns[:-2])] +  # Excluir TOTAL y VEL/MES
                    [html.Th("TOTAL", className="text-center", 
                            style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'}),
                     html.Th("VEL/MES", className="text-center", 
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
                    for mes in sorted(tabla_pivot.columns[:-2])],  # Excluir TOTAL y VEL/MES
                    html.Td(html.B(str(int(tabla_pivot.loc[año, 'TOTAL']))), 
                        className="text-center",
                        style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'} if año == 'TOTAL' else {'background-color': '#f8f9fa', 'font-weight': 'bold'}),
                    html.Td(html.B(f"{tabla_pivot.loc[año, 'VEL/MES']:.1f}"), 
                        className="text-center",
                        style={'background-color': '#2d2c55', 'color': 'white', 'font-weight': 'bold'} if año == 'TOTAL' else {'background-color': '#e8f4f8', 'font-weight': 'bold'})
                ], style={'background-color': '#2d2c55'} if año == 'TOTAL' else {})
                for año in tabla_pivot.index
            ])  
        ], className="table table-striped table-sm table-bordered")
        
        return html.Div([
            html.P(f"📊 Total ventas analizadas: {len(df_con_fecha)} | Velocidad desde Dic 2021", 
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

def obtener_color_estado(estado):
    """Función para obtener el color según el estado"""
    estado_limpio = str(estado).strip()
    
    # Diccionario de colores actualizado
    colores = {
        'Escritura': '#28A745',    # Verde
        'Promesa': '#FFC107',      # Amarillo  
        'Reserva': '#FF8C00',      # Naranja
        'Disponible': '#DC3545',   # Rojo
        'Stock Ausente': '#6C757D' # Gris
    }
    
    return colores.get(estado_limpio, '#CCCCCC')  # Gris claro por defecto

def crear_grafico_3d(df_filtrado, vista_explosion=False):
    """Crear gráfico 3D del edificio con layout 2 filas"""
    
    # Layout 2 filas con sectores específicos
    posiciones = {
        # Vista Coquimbo (fila superior)
        2: (0, 0), 1: (1.3, 0), 9: (3.3, 0), 8: (4.3, 0),
        # Vista La Serena (fila inferior)
        3: (0, 0.7), 4: (1.3, 0.7), 5: (2.6, 0.7), 6: (3.3, 0.7), 7: (4.3, 0.7)
    }
    
    escalera_pos = (2.3, 0)
    fig = go.Figure()
    
    # Crear cubos para cada departamento
    for _, depto in df_filtrado.iterrows():
        sector = int(depto.get('SECTOR', depto.get('TIPO', 0)))
        if sector not in posiciones:
            continue
            
        x, y = posiciones[sector]
        z = depto['PISO']  # Usar directamente el piso
        
        # Determinar el ancho según el sector
        if sector == 5:
            ancho = 0.7
        elif sector in [4, 3, 2]:
            ancho = 1.3
        else:
            ancho = 1.0
        
        # Obtener color y datos
        estado = str(depto['ESTADO']).strip()
        color = obtener_color_estado(estado)
        
        precio = depto.get('PRECIO', 0)
        superficie = depto.get('M2', 0)
        uf_m2 = depto.get('UF/M2', 0)
        tipologia_display = depto.get('TIPOLOGIA', 'N/A')
        
        # Información de fecha
        fecha_info = ""
        if 'FECHA' in depto.index and pd.notna(depto['FECHA']):
            fecha_info = f"<span style='color:#0C0404;'><b>Fecha:</b></span> <b>{depto['FECHA'].strftime('%d/%m/%Y')}</b><br>"
        
        # Vista según sectores
        if sector in [2, 1, 9, 8]:
            vista_sector = "Vista Coquimbo"
        elif sector in [3, 4, 5, 6, 7]:
            vista_sector = "Vista La Serena"
        else:
            vista_sector = "N/A"
        
        hover_text = f"""<b style='color:#0C0404; font-size:14px;'>🏢 Sector {sector} - Piso {z}</b><br>
        <span style='color:#0C0404;'><b>Estado:</b></span> <b>{estado}</b><br>
        <span style='color:#0C0404;'><b>Precio:</b></span> <b>UF {precio:,.0f}</b><br>
        <span style='color:#0C0404;'><b>Superficie:</b></span> <b>{superficie} m²</b><br>
        <span style='color:#0C0404;'><b>UF/m²:</b></span> <b>{uf_m2:.2f}</b><br>
        <span style='color:#0C0404;'><b>Tipología:</b></span> <b>{tipologia_display}</b><br>
        <span style='color:#0C0404;'><b>Vista:</b></span> <b>{vista_sector}</b><br>
        {fecha_info}"""
        
        # Resto del código del cubo permanece igual...
        fig.add_trace(go.Mesh3d(
            x=[x, x+ancho, x+ancho, x, x, x+ancho, x+ancho, x],
            y=[y, y, y+0.7, y+0.7, y, y, y+0.7, y+0.7],
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
        edges_x = [x, x+ancho, x+ancho, x, x, x, x+ancho, x+ancho, x+ancho, x+ancho, x, x, x, x+ancho, x+ancho, x]
        edges_y = [y, y, y+0.7, y+0.7, y, y, y, y, y+0.7, y+0.7, y+0.7, y+0.7, y, y, y+0.7, y+0.7]
        edges_z = [z, z, z, z, z, z+1, z+1, z+1, z+1, z, z, z+1, z+1, z+1, z+1, z]
        
        fig.add_trace(go.Scatter3d(
            x=edges_x, y=edges_y, z=edges_z,
            mode='lines',
            line=dict(color='black', width=1),
            showlegend=False,
            hoverinfo='skip'
        ))
    
    # Escaleras
    pisos_filtrados = df_filtrado['PISO'].unique() if len(df_filtrado) > 0 else []
    for piso in pisos_filtrados:
        x_esc, y_esc = escalera_pos
        
        fig.add_trace(go.Mesh3d(
            x=[x_esc, x_esc+1.0, x_esc+1.0, x_esc, x_esc, x_esc+1.0, x_esc+1.0, x_esc],
            y=[y_esc, y_esc, y_esc+0.7, y_esc+0.7, y_esc, y_esc, y_esc+0.7, y_esc+0.7],
            z=[piso, piso, piso, piso, piso+1, piso+1, piso+1, piso+1],
            i=[7, 0, 0, 0, 4, 4, 6, 1, 4, 0, 3, 6],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 6, 5, 5, 7, 7],
            color='#E9ECEF',
            opacity=1.0,
            hovertemplate=f"<b style='color:#2C3E50;'>🚶‍♂️ ESCALERAS</b><br>Piso {piso}<extra></extra>",
            showscale=False
        ))
    
    # Layout
    z_max = max(df_filtrado['PISO']) + 1 if len(df_filtrado) > 0 else 16
    
    fig.update_layout(
        scene=dict(
            xaxis=dict(showticklabels=False, title='', showgrid=False, range=[0, 6]),
            yaxis=dict(showticklabels=False, title='', showgrid=False, range=[0, 2]),
            zaxis=dict(showticklabels=False, title='', showgrid=False, range=[1.5, z_max]),
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.2)),
            aspectmode='manual',
            aspectratio=dict(x=2, y=1, z=3),
            bgcolor='#F8F9FA'
        ),
        showlegend=False,
        height=600,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        transition={'duration': 500, 'easing': 'cubic-in-out'},
        uirevision='constant'  # Mantiene estado de vista
    )
    
    return fig

# Crear la aplicación Dash
app = dash.Dash(__name__, 
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                assets_folder='assets',
                suppress_callback_exceptions=True)

# IMPORTANTE: Para deploy
server = app.server

# Configurar servicio de archivos estáticos
@server.route('/assets/<filename>')
def download_file(filename):
    return send_from_directory('assets', filename)

# Debug: verificar archivos
if os.path.exists('assets'):
    assets_files = os.listdir('assets')
    print(f"📁 Assets encontrados: {assets_files}")
    if 'LOGO.png' in assets_files:
        print("✅ LOGO.png encontrado")
    else:
        print("❌ LOGO.png no encontrado")
else:
    print("❌ Carpeta assets no existe")

# Cargar datos globalmente
print("🔄 Cargando datos...")
df_global = cargar_datos("Datos.xlsx")

# Layout de la aplicación
app.layout = dbc.Container([
    
    # Header principal
    dbc.Row([
        dbc.Col([
            html.Div([
                dbc.Row([
                    dbc.Col([
                        html.H1("🏢 Dashboard Miraolas", 
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
                            html.Label("Seleccionar Vista:", className="fw-bold mb-2"),
                            dcc.Dropdown(
                                id='filtro-vista',
                                options=[
                                    {'label': '🌊 Todas las vistas', 'value': 'todas'},
                                    {'label': '🏔️ Vista La Serena', 'value': 'la_serena'},
                                    {'label': '🌅 Vista Coquimbo', 'value': 'coquimbo'}
                                ],
                                value='todas',
                                placeholder="Seleccionar vista",
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
                    # NUEVA FILA PARA EL SLIDER DE PRECIOS
                    dbc.Row([
                        dbc.Col([
                            html.Label("Rango de Precios (UF):", className="fw-bold mb-2"),
                            dcc.RangeSlider(
                                id='filtro-precio-slider',
                                min=0,
                                max=10000,
                                step=50,
                                marks={},
                                value=[0, 10000],
                                tooltip={"placement": "bottom", "always_visible": True},
                                className="mb-3"
                            ),
                            html.Div(id="precio-range-display", className="text-center text-muted small")
                        ], width=12)
                    ], className="mt-3"),
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
                                        {'label': '🔴 Disponibles', 'value': 'Disponible'},
                                        {'label': '🟠 Reservas', 'value': 'Reserva'},
                                        {'label': '🟡 Promesas', 'value': 'Promesa'},
                                        {'label': '🟢 Escrituras', 'value': 'Escritura'}
                                    ],
                                    value=['Disponible', 'Reserva', 'Promesa', 'Escritura'],
                                    multi=True,
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
                        type="dot",  # Cambiar de "circle" a "dot"
                        color="#2d2c55",
                        delay_show=100,
                        delay_hide=200,
                        children=[
                            dcc.Graph(
                                id='grafico-3d',
                                config={
                                    'displayModeBar': True,
                                    'displaylogo': False,
                                    'modeBarButtonsToRemove': ['pan2d', 'lasso2d']
                                },
                                animate=True,
                                style={'transition': 'opacity 0.3s ease-in-out'}
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
    
    
], fluid=True, style={'backgroundColor': '#F8F9FA', 'minHeight': '100vh', 'padding': '20px'})

# Callbacks
# Callbacks

@app.callback(
    [Output('filtro-pisos', 'options'),
     Output('filtro-pisos', 'value'),
     Output('filtro-tipologia', 'options'),
     Output('filtro-tipologia', 'value'),
     Output('filtro-precio-slider', 'min'),
     Output('filtro-precio-slider', 'max'),
     Output('filtro-precio-slider', 'value'),
     Output('filtro-precio-slider', 'marks')],
    [Input('filtro-pisos', 'id')]
)
def inicializar_filtros(_):
    if df_global is not None:
        # Opciones de pisos
        pisos_disponibles = sorted(df_global['PISO'].unique())
        opciones_pisos = [{'label': f'Piso {piso}', 'value': piso} for piso in pisos_disponibles]
        
        # Opciones de tipología
        if 'TIPOLOGIA' in df_global.columns:
            tipologias_disponibles = sorted(df_global['TIPOLOGIA'].dropna().unique())
            opciones_tipologia = [{'label': f'{tip}', 'value': tip} for tip in tipologias_disponibles]
        else:
            opciones_tipologia = []
        
        # Configuración del slider de precios
        if 'PRECIO' in df_global.columns:
            precios = df_global['PRECIO'].dropna()
            precio_min = int(precios.min())
            precio_max = int(precios.max())
            
            # Crear marcas cada 500 UF aproximadamente
            step_marks = (precio_max - precio_min) // 8
            step_marks = max(500, step_marks)  # Mínimo 500 UF entre marcas
            
            marks = {}
            for i in range(precio_min, precio_max + 1, step_marks):
                if i <= precio_max:
                    marks[i] = f'UF {i:,}'
            
            # Asegurar que tenemos marca en el máximo
            marks[precio_max] = f'UF {precio_max:,}'
            
            return (opciones_pisos, pisos_disponibles, opciones_tipologia, [], 
                   precio_min, precio_max, [precio_min, precio_max], marks)
        else:
            return opciones_pisos, pisos_disponibles, opciones_tipologia, [], 0, 10000, [0, 10000], {}
    
    return [], [], [], [], 0, 10000, [0, 10000], {}

@app.callback(
    Output('precio-range-display', 'children'),
    [Input('filtro-precio-slider', 'value')]
)
def actualizar_display_precio(rango_precio):
    if rango_precio:
        return f"Rango seleccionado: UF {rango_precio[0]:,} - UF {rango_precio[1]:,}"
    return ""

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
     Input('filtro-vista', 'value'),
     Input('filtro-estados', 'value'),
     Input('filtro-tipologia', 'value'),
     Input('filtro-precio-slider', 'value')]
)
def actualizar_dashboard(pisos_seleccionados, vista_seleccionada, estados_seleccionados, 
                        tipologias_seleccionadas, rango_precio):
    if df_global is None:
        fig_vacia = go.Figure()
        fig_vacia.add_annotation(text="❌ No se pudieron cargar los datos", x=0.5, y=0.5)
        return fig_vacia, html.Div("Error en datos"), "Error", html.Div("Error"), html.Div("Error")
    
    # Filtrar datos por pisos
    if pisos_seleccionados and len(pisos_seleccionados) > 0:
        df_filtrado = df_global[df_global['PISO'].isin(pisos_seleccionados)]
    else:
        df_filtrado = df_global.copy()
    
    # Filtrar por vista
    vistas_sectores = {
        'coquimbo': [2, 1, 9, 8],
        'la_serena': [3, 4, 5, 6, 7]
    }
    
    if vista_seleccionada in vistas_sectores:
        sectores_filtrados = vistas_sectores[vista_seleccionada]
        columna_sector = 'SECTOR' if 'SECTOR' in df_filtrado.columns else 'TIPO'
        df_filtrado = df_filtrado[df_filtrado[columna_sector].isin(sectores_filtrados)]
    
    # Filtrar por estados
    if estados_seleccionados and len(estados_seleccionados) > 0:
        df_filtrado = df_filtrado[df_filtrado['ESTADO'].isin(estados_seleccionados)]
    
    # Filtrar por tipología
    if tipologias_seleccionadas and len(tipologias_seleccionadas) > 0 and 'TIPOLOGIA' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['TIPOLOGIA'].isin(tipologias_seleccionadas)]

    # Filtrar por rango de precios
    if rango_precio and 'PRECIO' in df_filtrado.columns:
        df_filtrado = df_filtrado[
            (df_filtrado['PRECIO'] >= rango_precio[0]) & 
            (df_filtrado['PRECIO'] <= rango_precio[1])
        ]
    
    # Crear gráfico 3D con animaciones
    fig_3d = crear_grafico_3d(df_filtrado, vista_explosion=False)
    
    # Análisis temporal
    if 'FECHA' in df_global.columns:
        df_vendidos = df_global[df_global['FECHA'].notna()]
        
        # Aplicar filtros al análisis temporal
        if not df_vendidos.empty:
            if pisos_seleccionados and len(pisos_seleccionados) > 0:
                df_vendidos = df_vendidos[df_vendidos['PISO'].isin(pisos_seleccionados)]
            
            if vista_seleccionada in vistas_sectores:
                sectores_filtrados = vistas_sectores[vista_seleccionada]
                columna_sector = 'SECTOR' if 'SECTOR' in df_vendidos.columns else 'TIPO'
                df_vendidos = df_vendidos[df_vendidos[columna_sector].isin(sectores_filtrados)]
            
            if tipologias_seleccionadas and len(tipologias_seleccionadas) > 0 and 'TIPOLOGIA' in df_vendidos.columns:
                df_vendidos = df_vendidos[df_vendidos['TIPOLOGIA'].isin(tipologias_seleccionadas)]
            
            if rango_precio and 'PRECIO' in df_vendidos.columns:
                df_vendidos = df_vendidos[
                    (df_vendidos['PRECIO'] >= rango_precio[0]) & 
                    (df_vendidos['PRECIO'] <= rango_precio[1])
                ]
    else:
        df_vendidos = pd.DataFrame()
    
    # Crear tablas
    tabla_ventas = crear_tabla_ventas_mensuales(df_vendidos)
    tabla_precios = crear_tabla_precios_mensuales(df_vendidos)
    
# Calcular métricas básicas
    total_precio = df_filtrado['PRECIO'].sum() if 'PRECIO' in df_filtrado.columns else 0
    total_m2 = df_filtrado['M2'].sum() if 'M2' in df_filtrado.columns else 0
    promedio_uf_m2 = df_filtrado['UF/M2'].mean() if 'UF/M2' in df_filtrado.columns and len(df_filtrado) > 0 else 0
    total_departamentos = len(df_filtrado)
    
    # Calcular meses para agotar stock (solo disponibles)
    df_disponibles = df_filtrado[df_filtrado['ESTADO'] == 'Disponible']
    stock_disponible = len(df_disponibles)
    
    # Calcular velocidad de venta desde datos vendidos
    meses_para_agotar = "N/A"
    if 'FECHA' in df_global.columns:
        df_vendidos_calc = df_global[df_global['FECHA'].notna()]
        if not df_vendidos_calc.empty:
            from datetime import datetime
            fecha_actual = datetime.now()
            meses_totales = ((fecha_actual.year - 2021) * 12 + fecha_actual.month) - 11  # Desde dic 2021
            if meses_totales > 0:
                velocidad_mensual = len(df_vendidos_calc) / meses_totales
                if velocidad_mensual > 0 and stock_disponible > 0:
                    meses_para_agotar = round(stock_disponible / velocidad_mensual, 1)
    
    # Métricas por estado COMPLETAS
    estados = ['Disponible', 'Reserva', 'Promesa', 'Escritura']
    metricas_por_estado = {}
    
    for estado in estados:
        df_estado = df_filtrado[df_filtrado['ESTADO'] == estado]
        metricas_por_estado[estado] = {
            'cantidad': len(df_estado),
            'precio': df_estado['PRECIO'].sum() if 'PRECIO' in df_estado.columns else 0,
            'm2': df_estado['M2'].sum() if 'M2' in df_estado.columns else 0,
            'uf_m2': df_estado['UF/M2'].mean() if 'UF/M2' in df_estado.columns and len(df_estado) > 0 else 0
        }
    
    # Componente de métricas MEJORADO
    metricas_componente = html.Div([
        # Métricas Principales
        html.H5("📊 MÉTRICAS PRINCIPALES", className="text-center mb-3", 
                style={'color': '#2C3E50', 'fontWeight': 'bold'}),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H4(f"{total_departamentos}", className="mb-0 metric-number", 
                            style={'color': '#6C757D', 'fontWeight': 'bold'}),
                    html.Small("Total Departamentos", className="text-muted")
                ], className="text-center p-2 border rounded metric-card")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H4(f"UF {total_precio:,.0f}", className="mb-0 metric-number", 
                            style={'color': '#007BFF', 'fontWeight': 'bold'}),
                    html.Small("Total Precio", className="text-muted")
                ], className="text-center p-2 border rounded metric-card")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H4(f"{total_m2:,.0f} m²", className="mb-0 metric-number", 
                            style={'color': '#FF6B6B', 'fontWeight': 'bold'}),
                    html.Small("Total Superficie", className="text-muted")
                ], className="text-center p-2 border rounded metric-card")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H4(f"{meses_para_agotar}" + (" meses" if isinstance(meses_para_agotar, (int, float)) else ""), 
                           className="mb-0 metric-number", 
                           style={'color': '#FF6B35', 'fontWeight': 'bold'}),
                    html.Small("Para Agotar Stock", className="text-muted")
                ], className="text-center p-2 border rounded metric-card")
            ], width=3)
        ], className="mb-4"),
        
        html.Hr(),
        
        # Resumen por Estado EXPANDIDO
        html.H5("📈 RESUMEN POR ESTADO", className="text-center mb-3", 
                style={'color': '#2C3E50', 'fontWeight': 'bold'}),
        
        # DISPONIBLES
        html.H6("🔴 DISPONIBLES", className="mb-2", style={'color': '#DC3545', 'fontWeight': 'bold'}),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Disponible']['cantidad']}", 
                           className="mb-0", style={'color': '#DC3545'}),
                    html.Small("Cantidad", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"UF {metricas_por_estado['Disponible']['precio']:,.0f}", 
                           className="mb-0", style={'color': '#DC3545'}),
                    html.Small("Precio Total", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Disponible']['m2']:,.0f} m²", 
                           className="mb-0", style={'color': '#DC3545'}),
                    html.Small("Superficie", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Disponible']['uf_m2']:.1f}", 
                           className="mb-0", style={'color': '#DC3545'}),
                    html.Small("Prom. UF/m²", className="text-muted")
                ], className="text-center p-1")
            ], width=3)
        ], className="mb-2"),
        
        # RESERVAS
        html.H6("🟠 RESERVAS", className="mb-2", style={'color': '#FF8C00', 'fontWeight': 'bold'}),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Reserva']['cantidad']}", 
                           className="mb-0", style={'color': '#FF8C00'}),
                    html.Small("Cantidad", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"UF {metricas_por_estado['Reserva']['precio']:,.0f}", 
                           className="mb-0", style={'color': '#FF8C00'}),
                    html.Small("Precio Total", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Reserva']['m2']:,.0f} m²", 
                           className="mb-0", style={'color': '#FF8C00'}),
                    html.Small("Superficie", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Reserva']['uf_m2']:.1f}", 
                           className="mb-0", style={'color': '#FF8C00'}),
                    html.Small("Prom. UF/m²", className="text-muted")
                ], className="text-center p-1")
            ], width=3)
        ], className="mb-2"),
        
        # PROMESAS
        html.H6("🟡 PROMESAS", className="mb-2", style={'color': '#FFC107', 'fontWeight': 'bold'}),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Promesa']['cantidad']}", 
                           className="mb-0", style={'color': '#FFC107'}),
                    html.Small("Cantidad", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"UF {metricas_por_estado['Promesa']['precio']:,.0f}", 
                           className="mb-0", style={'color': '#FFC107'}),
                    html.Small("Precio Total", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Promesa']['m2']:,.0f} m²", 
                           className="mb-0", style={'color': '#FFC107'}),
                    html.Small("Superficie", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Promesa']['uf_m2']:.1f}", 
                           className="mb-0", style={'color': '#FFC107'}),
                    html.Small("Prom. UF/m²", className="text-muted")
                ], className="text-center p-1")
            ], width=3)
        ], className="mb-2"),
        
        # ESCRITURAS
        html.H6("🟢 ESCRITURAS", className="mb-2", style={'color': '#28A745', 'fontWeight': 'bold'}),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Escritura']['cantidad']}", 
                           className="mb-0", style={'color': '#28A745'}),
                    html.Small("Cantidad", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"UF {metricas_por_estado['Escritura']['precio']:,.0f}", 
                           className="mb-0", style={'color': '#28A745'}),
                    html.Small("Precio Total", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Escritura']['m2']:,.0f} m²", 
                           className="mb-0", style={'color': '#28A745'}),
                    html.Small("Superficie", className="text-muted")
                ], className="text-center p-1")
            ], width=3),
            dbc.Col([
                html.Div([
                    html.H6(f"{metricas_por_estado['Escritura']['uf_m2']:.1f}", 
                           className="mb-0", style={'color': '#28A745'}),
                    html.Small("Prom. UF/m²", className="text-muted")
                ], className="text-center p-1")
            ], width=3)
        ])
    ], className="animated-component")
    
    # Información de filtros simplificada
    filtros_texto = []
    
    if rango_precio:
        precio_texto = f"UF {rango_precio[0]:,} - UF {rango_precio[1]:,}"
        filtros_texto.append(f"💰 {precio_texto}")
    
    if pisos_seleccionados and len(pisos_seleccionados) > 0:
        if len(pisos_seleccionados) <= 3:
            pisos_texto = ", ".join([f"P{p}" for p in sorted(pisos_seleccionados)])
        else:
            pisos_texto = f"P{min(pisos_seleccionados)}-P{max(pisos_seleccionados)}"
        filtros_texto.append(f"🏢 {pisos_texto}")
    
    vista_texto = {
        'todas': '🌊 Todas',
        'coquimbo': '🌅 Coquimbo',
        'la_serena': '🏔️ La Serena'
    }
    filtros_texto.append(vista_texto.get(vista_seleccionada, '🌊 Todas'))
    
    if tipologias_seleccionadas and len(tipologias_seleccionadas) > 0:
        if len(tipologias_seleccionadas) <= 2:
            tip_texto = ", ".join(tipologias_seleccionadas)
        else:
            tip_texto = f"{len(tipologias_seleccionadas)} tipologías"
        filtros_texto.append(f"🏠 {tip_texto}")
    
    # Contadores por estado
    contadores = [f"🔴{metricas_por_estado['Disponible']['cantidad']}", 
                  f"🟠{metricas_por_estado['Reserva']['cantidad']}", 
                  f"🟡{metricas_por_estado['Promesa']['cantidad']}", 
                  f"🟢{metricas_por_estado['Escritura']['cantidad']}"]
    
    info_text = html.Div([
        html.P([
            html.Strong(f"📊 {total_departamentos} departamentos | "),
            " | ".join(filtros_texto)
        ], className="mb-1"),
        html.P(" | ".join(contadores), className="mb-0")
    ])
    
    return fig_3d, metricas_componente, info_text, tabla_ventas, tabla_precios


if __name__ == "__main__":
    app.run(debug=True)
    app.run(debug=True)