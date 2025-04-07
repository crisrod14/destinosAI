import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
import google.auth
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import io
from openai import OpenAI
from typing import Dict, List
import sqlite3
from datetime import datetime
import json
from google.oauth2 import service_account
import pickle

# Configuración de la página (debe ser la primera llamada a Streamlit)
st.set_page_config(
    page_title="Destinos AI",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cargar variables de entorno
load_dotenv()

# Configurar OpenAI
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    st.error("No se encontró la clave API de OpenAI. Por favor, verifica tu archivo .env")
    st.stop()

# Crear el cliente de OpenAI una sola vez
client = OpenAI(api_key=api_key)

# Configuración de Google Sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.file']
SHEET_ID = '1OCZfwayh4yUplVjGc2xZTrroYvO22SiC48sbGbKylt8'  # ID correcto de la hoja
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pickle'

# Título y descripción
st.title("✈️ JetSMART Content Manager")
st.markdown("""
    Esta aplicación te permite gestionar el contenido turístico para los destinos de JetSMART.
    Puedes visualizar, editar y generar nuevo contenido automáticamente.
""")

# Función para autenticación con Google Sheets
def get_google_sheets_service():
    """Inicializar y retornar el servicio de Google Sheets"""
    creds = None
    
    # Cargar credenciales existentes si están disponibles
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            try:
                creds = pickle.load(token)
            except Exception as e:
                st.error(f"Error al cargar el token: {str(e)}")
                os.remove(TOKEN_FILE)  # Eliminar token inválido
    
    # Si no hay credenciales válidas, solicitar autorización
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                st.error(f"Error al refrescar el token: {str(e)}")
                creds = None
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0, success_message="Autenticación exitosa!")
                # Guardar las credenciales para la próxima ejecución
                with open(TOKEN_FILE, 'wb') as token:
                    pickle.dump(creds, token)
            except Exception as e:
                st.error(f"Error en el flujo de autorización: {str(e)}")
                return None
    
    try:
        # Construir el servicio
        service = build('sheets', 'v4', credentials=creds)
        return service
    except Exception as e:
        st.error(f"Error al construir el servicio: {str(e)}")
        return None

# Inicializar el servicio de Google Sheets
sheet_service = get_google_sheets_service()

# Función para cargar datos desde Google Sheets
def load_sheet_data():
    try:
        service = get_google_sheets_service()
        spreadsheet_id = os.getenv('GOOGLE_DRIVE_FILE_ID')
        
        # Obtener los valores de la hoja
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="'Hoja 1'"  # Mantener Hoja 1 para lectura
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            st.error("No se encontraron datos en la hoja.")
            return None
            
        # Convertir a DataFrame
        df = pd.DataFrame(values[1:], columns=values[0])
        
        # Reemplazar valores vacíos con cadenas vacías
        df = df.fillna('')
        
        return df
    except Exception as e:
        st.error(f"Error al cargar los datos: {str(e)}")
        return None

def verify_or_create_sheet():
    """Verificar si la hoja existe y crearla si no existe"""
    global SHEET_ID
    try:
        # Intentar obtener información de la hoja
        sheet_metadata = sheet_service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
        st.write("Debug - Hoja existente encontrada")
        
        # Verificar que la hoja 'Destinos' existe
        sheet_exists = False
        for sheet in sheet_metadata.get('sheets', []):
            if sheet['properties']['title'] == 'Destinos':
                sheet_exists = True
                break
        
        if not sheet_exists:
            # Crear la hoja 'Destinos' si no existe
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': 'Destinos'
                        }
                    }
                }]
            }
            sheet_service.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID,
                body=body
            ).execute()
            st.write("Debug - Hoja 'Destinos' creada")
        
        return True
    except Exception as e:
        st.write("Debug - La hoja no existe o hay un error, creando una nueva...")
        try:
            # Crear una nueva hoja de cálculo
            spreadsheet = {
                'properties': {
                    'title': 'Destinos JetSMART'
                },
                'sheets': [{
                    'properties': {
                        'title': 'Destinos'
                    }
                }]
            }
            spreadsheet = sheet_service.spreadsheets().create(body=spreadsheet).execute()
            SHEET_ID = spreadsheet['spreadsheetId']
            st.success(f"Nueva hoja creada con ID: {SHEET_ID}")
            return True
        except Exception as create_error:
            st.error(f"Error al crear la hoja: {str(create_error)}")
            return False

def save_sheet_data(df):
    try:
        st.write("Debug - Iniciando guardado en Google Sheets")
        
        if not sheet_service:
            st.error("Error: No se ha configurado el servicio de Google Sheets")
            return False
        
        try:
            # Verificar que la hoja existe
            if not verify_or_create_sheet():
                st.error("Error: No se pudo verificar o crear la hoja")
                return False
            
            # Asegurarse de que tenemos todas las columnas necesarias
            required_columns = [
                'LOCATION', 'NAV_BAR', 'NAV_ACERCA DE', 'NAV_QUE_HACER_EN', 'NAV_CUANDO_IR_A',
                'NAV_LOS_IMPERDIBLES_DE', 'CARD_CONOCE_LA_CIUDAD_DE', 'TITLE_CONOCE_LA_CIUDAD_DE',
                'IMG_CONOCE_LA_CIUDAD_DE', 'DESCRIP_CONOCE_LA_CIUDAD_DE', 'CARD_ACERCA_DEL_AEROPUERTO',
                'IMG_ACERCA_DEL_AEROPUERTO', 'SUBTITLE_ACERCA_DEL_AEROPUERTO', 'DESCRIP_ACERCA_DEL_AEROPUERTO',
                'CARD_QUE_HACER_EN', 'TITLE_QUE_HACER_EN', 'IMG_QUE_HACER_EN', 'SUBTITLE_QUE_HACER_EN',
                'DESCRIP_QUE_HACER_EN', 'CARD_CUANDO_IR_A', 'TITLE_CUANDO_IR_A', 'SUBTITLE_CUANDO_IR_A',
                'IMG_1_CUANDO_IR_A', 'DESCRIP_CUANDO_IR_A', 'IMG_2_CUANDO_IR_A',
                'CARD_CONOCE_LOS_IMPERDIBLES_DE', 'TITLE_CONOCE_LOS_IMPERDIBLES_DE',
                'IMG_CONOCE_LOS_IMPERDIBLES_DE', 'DESCRIP_CONOCE_LOS_IMPERDIBLES_DE',
                'SUBCARD_1_TITLE_CONOCE_LOS_IMPERDIBLES_DE', 'SUBCARD_1_IMG_CONOCE_LOS_IMPERDIBLES_DE',
                'SUBCARD_1_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE', 'SUBCARD_2_TITLE_CONOCE_LOS_IMPERDIBLES_DE',
                'SUBCARD_2_IMG_CONOCE_LOS_IMPERDIBLES_DE', 'SUBCARD_2_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE',
                'SUBCARD_3_TITLE_CONOCE_LOS_IMPERDIBLES_DE', 'SUBCARD_3_IMG_CONOCE_LOS_IMPERDIBLES_DE',
                'SUBCARD_3_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE', 'SUBCARD_4_TITLE_CONOCE_LOS_IMPERDIBLES_DE',
                'SUBCARD_4_IMG_CONOCE_LOS_IMPERDIBLES_DE', 'SUBCARD_4_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE',
                'CARD_DATOS_IMPORTANTES', 'IMG_DATOS_IMPORTANTES', 'DESCRIP_DATOS_IMPORTANTES'
            ]
            
            # Asegurarse de que el DataFrame tiene todas las columnas necesarias
            for col in required_columns:
                if col not in df.columns:
                    df[col] = ''
            
            # Reordenar las columnas según el orden requerido
            df = df[required_columns]
            
            # Convertir el DataFrame a una lista de listas para Google Sheets
            values = [required_columns]  # Primero los encabezados
            
            # Convertir los valores del DataFrame a strings y reemplazar None/NaN por cadenas vacías
            for _, row in df.iterrows():
                row_values = []
                for col in required_columns:
                    val = row[col]
                    if pd.isna(val) or val is None:
                        val = ''
                    row_values.append(str(val))
                values.append(row_values)
            
            st.write(f"Debug - Preparados {len(values)} registros para enviar")
            
            # Limpiar la hoja existente
            sheet_service.spreadsheets().values().clear(
                spreadsheetId=SHEET_ID,
                range='Destinos!A:ZZ'  # Limpia todas las columnas
            ).execute()
            
            st.write("Debug - Hoja limpiada exitosamente")
            
            # Escribir los nuevos datos
            body = {
                'values': values,
                'majorDimension': 'ROWS'
            }
            
            result = sheet_service.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range='Destinos!A1',  # Comienza desde A1
                valueInputOption='RAW',
                body=body
            ).execute()
            
            st.write(f"Debug - Datos guardados exitosamente: {result.get('updatedCells')} celdas actualizadas")
            st.write(f"Debug - Rango actualizado: {result.get('updatedRange')}")
            st.success(f"✅ Datos guardados en Google Sheets. ID de la hoja: {SHEET_ID}")
            return True
            
        except Exception as e:
            st.error(f"Error específico al guardar en Google Sheets: {str(e)}")
            return False
            
    except Exception as e:
        st.error(f"Error general al guardar en Google Sheets: {str(e)}")
        return False

# Función para generar contenido con IA
def generate_content(location: str) -> Dict[str, str]:
    try:
        st.write("Debug - Iniciando generación de contenido para:", location)
        
        # Inicializar el diccionario con valores por defecto
        content_dict = {
            'LOCATION': location,
            'NAV_BAR': '',
            'NAV_ACERCA DE': location,
            'NAV_QUE_HACER_EN': location,
            'NAV_CUANDO_IR_A': location,
            'NAV_LOS_IMPERDIBLES_DE': location,
            'CARD_CONOCE_LA_CIUDAD_DE': '',
            'TITLE_CONOCE_LA_CIUDAD_DE': location,
            'IMG_CONOCE_LA_CIUDAD_DE': 'URL_IMG',
            'DESCRIP_CONOCE_LA_CIUDAD_DE': '',
            'CARD_ACERCA_DEL_AEROPUERTO': '',
            'IMG_ACERCA_DEL_AEROPUERTO': 'URL_IMG',
            'SUBTITLE_ACERCA_DEL_AEROPUERTO': '',
            'DESCRIP_ACERCA_DEL_AEROPUERTO': '',
            'CARD_QUE_HACER_EN': '',
            'TITLE_QUE_HACER_EN': location,
            'IMG_QUE_HACER_EN': 'URL_IMG',
            'SUBTITLE_QUE_HACER_EN': '',
            'DESCRIP_QUE_HACER_EN': '',
            'CARD_CUANDO_IR_A': '',
            'TITLE_CUANDO_IR_A': location,
            'SUBTITLE_CUANDO_IR_A': '',
            'IMG_1_CUANDO_IR_A': 'URL_IMG',
            'DESCRIP_CUANDO_IR_A': '',
            'IMG_2_CUANDO_IR_A': 'URL_IMG',
            'CARD_CONOCE_LOS_IMPERDIBLES_DE': '',
            'TITLE_CONOCE_LOS_IMPERDIBLES_DE': location,
            'IMG_CONOCE_LOS_IMPERDIBLES_DE': 'URL_IMG',
            'DESCRIP_CONOCE_LOS_IMPERDIBLES_DE': '',
            'SUBCARD_1_TITLE_CONOCE_LOS_IMPERDIBLES_DE': '',
            'SUBCARD_1_IMG_CONOCE_LOS_IMPERDIBLES_DE': 'URL_IMG',
            'SUBCARD_1_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE': '',
            'SUBCARD_2_TITLE_CONOCE_LOS_IMPERDIBLES_DE': '',
            'SUBCARD_2_IMG_CONOCE_LOS_IMPERDIBLES_DE': 'URL_IMG',
            'SUBCARD_2_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE': '',
            'SUBCARD_3_TITLE_CONOCE_LOS_IMPERDIBLES_DE': '',
            'SUBCARD_3_IMG_CONOCE_LOS_IMPERDIBLES_DE': 'URL_IMG',
            'SUBCARD_3_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE': '',
            'SUBCARD_4_TITLE_CONOCE_LOS_IMPERDIBLES_DE': '',
            'SUBCARD_4_IMG_CONOCE_LOS_IMPERDIBLES_DE': 'URL_IMG',
            'SUBCARD_4_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE': '',
            'CARD_DATOS_IMPORTANTES': '',
            'IMG_DATOS_IMPORTANTES': 'URL_IMG',
            'DESCRIP_DATOS_IMPORTANTES': ''
        }
        
        # Generar el prompt para OpenAI
        prompt = f"""
        Actúa como un redactor profesional especializado en turismo y SEO para aerolíneas low-cost como JetSMART. Tu tarea es generar contenido completo, útil y atractivo para {location} que será publicado en la sección de guía de destinos del sitio web.

        🔍 Tu contenido debe seguir la estructura exacta de un Excel, tal como en el ejemplo de Antofagasta. Cada celda debe contener el tipo de información que corresponde, sin agregar campos nuevos ni alterar los existentes.

        📚 ESTRUCTURA QUE DEBES COMPLETAR:

        DESCRIP_CONOCE_LA_CIUDAD_DE:
        [Introduce el destino destacando su identidad, estilo de viaje (aventura, descanso, cultura), lo más representativo y actual: paisajes, ambiente, vida local o eventos.]

        SUBTITLE_ACERCA_DEL_AEROPUERTO:
        [Nombre del aeropuerto]

        DESCRIP_ACERCA_DEL_AEROPUERTO:
        [Explica dónde está ubicado, cómo se conecta con la ciudad, cuánto demora el trayecto, y qué medios existen (transporte público, transfer, aplicaciones de transporte).]

        SUBTITLE_QUE_HACER_EN:
        [Subtítulo atractivo para la sección]

        DESCRIP_QUE_HACER_EN:
        [Recomienda actividades variadas: cultura, gastronomía, vida urbana, naturaleza. Puedes incluir panoramas clásicos y otros más actuales o únicos del lugar.]

        SUBTITLE_CUANDO_IR_A:
        [Resumen de temporada ideal]

        DESCRIP_CUANDO_IR_A:
        [Describe la mejor época para visitar según clima, actividades, festivales, precios o experiencias especiales. Incluye ventajas de temporada alta y baja.]

        DESCRIP_CONOCE_LOS_IMPERDIBLES_DE:
        [Haz un resumen general de los panoramas más llamativos, sin repetir literalmente los 4 que vendrán, pero puedes anticiparlos sutilmente.]

        SUBCARD_1_TITLE_CONOCE_LOS_IMPERDIBLES_DE:
        [Nombre del primer panorama imperdible]

        SUBCARD_1_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE:
        [¿Qué es? ¿Qué se hace? ¿Por qué es imperdible? ¿Es gratuito o de pago? Precio estimado si aplica. Tips útiles.]

        SUBCARD_2_TITLE_CONOCE_LOS_IMPERDIBLES_DE:
        [Nombre del segundo panorama imperdible]

        SUBCARD_2_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE:
        [Descripción detallada siguiendo el mismo formato]

        SUBCARD_3_TITLE_CONOCE_LOS_IMPERDIBLES_DE:
        [Nombre del tercer panorama imperdible]

        SUBCARD_3_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE:
        [Descripción detallada siguiendo el mismo formato]

        SUBCARD_4_TITLE_CONOCE_LOS_IMPERDIBLES_DE:
        [Nombre del cuarto panorama imperdible]

        SUBCARD_4_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE:
        [Descripción detallada siguiendo el mismo formato]

        DESCRIP_DATOS_IMPORTANTES:
        [Consejos prácticos para el viaje incluyendo transporte, clima, seguridad, costumbres locales y tips para turistas.]

        💡 IMPORTANTE: Para cada panorama imperdible, asegúrate de proporcionar un título claro y descriptivo en el campo SUBCARD_X_TITLE_CONOCE_LOS_IMPERDIBLES_DE.

        Responde SOLO con el contenido solicitado para cada campo, manteniendo el formato exacto de los nombres de los campos.
        """
        
        # Llamar a OpenAI para generar el contenido
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un experto en contenido turístico para JetSMART. Genera contenido atractivo y útil para viajeros."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        # Procesar la respuesta y actualizar el diccionario
        content = response.choices[0].message.content
        lines = content.split('\n')
        
        current_field = None
        current_value = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Buscar campos en la línea
            field_found = False
            for field in content_dict.keys():
                if line.startswith(field + ':'):
                    # Si teníamos un campo anterior, guardamos su valor
                    if current_field and current_value:
                        content_dict[current_field] = ' '.join(current_value)
                    
                    # Comenzamos con el nuevo campo
                    current_field = field
                    current_value = [line.split(':', 1)[1].strip()]
                    field_found = True
                    break
                    
            # Si no encontramos un nuevo campo, agregamos la línea al valor actual
            if not field_found and current_field:
                current_value.append(line)
        
        # No olvidar guardar el último campo
        if current_field and current_value:
            content_dict[current_field] = ' '.join(current_value)
        
        return content_dict
    except Exception as e:
        st.error(f"Error al generar contenido: {str(e)}")
        return None

# Función para mostrar y editar contenido
def show_edit_content(location_data: pd.Series):
    edited_data = {}
    
    # Sección de navegación
    st.subheader("Navegación")
    nav_fields = ['NAV_BAR', 'NAV_ACERCA DE', 'NAV_QUE_HACER_EN', 'NAV_CUANDO_IR_A', 'NAV_LOS_IMPERDIBLES_DE']
    for field in nav_fields:
        value = location_data[field] if pd.notna(location_data[field]) else ''
        edited_data[field] = st.text_input(field, value=value)
    
    # Sección "Conoce la ciudad"
    st.subheader("Conoce la ciudad")
    city_fields = [
        'CARD_CONOCE_LA_CIUDAD_DE',
        'TITLE_CONOCE_LA_CIUDAD_DE',
        'IMG_CONOCE_LA_CIUDAD_DE',
        'DESCRIP_CONOCE_LA_CIUDAD_DE'
    ]
    for field in city_fields:
        value = location_data[field] if pd.notna(location_data[field]) else ''
        if 'DESCRIP' in field:
            edited_data[field] = st.text_area(field, value=value, height=200)
        else:
            edited_data[field] = st.text_input(field, value=value)
    
    # Sección "Acerca del Aeropuerto"
    st.subheader("Acerca del Aeropuerto")
    airport_fields = [
        'CARD_ACERCA_DEL_AEROPUERTO',
        'IMG_ACERCA_DEL_AEROPUERTO',
        'SUBTITLE_ACERCA_DEL_AEROPUERTO',
        'DESCRIP_ACERCA_DEL_AEROPUERTO'
    ]
    for field in airport_fields:
        value = location_data[field] if pd.notna(location_data[field]) else ''
        if 'DESCRIP' in field:
            edited_data[field] = st.text_area(field, value=value, height=150)
        else:
            edited_data[field] = st.text_input(field, value=value)
    
    # Sección "Qué hacer en"
    st.subheader("Qué hacer en")
    todo_fields = [
        'CARD_QUE_HACER_EN',
        'TITLE_QUE_HACER_EN',
        'IMG_QUE_HACER_EN',
        'SUBTITLE_QUE_HACER_EN',
        'DESCRIP_QUE_HACER_EN'
    ]
    for field in todo_fields:
        value = location_data[field] if pd.notna(location_data[field]) else ''
        if 'DESCRIP' in field:
            edited_data[field] = st.text_area(field, value=value, height=150)
        else:
            edited_data[field] = st.text_input(field, value=value)
    
    # Sección "Cuándo ir a"
    st.subheader("Cuándo ir a")
    when_fields = [
        'CARD_CUANDO_IR_A',
        'TITLE_CUANDO_IR_A',
        'SUBTITLE_CUANDO_IR_A',
        'IMG_1_CUANDO_IR_A',
        'DESCRIP_CUANDO_IR_A',
        'IMG_2_CUANDO_IR_A'
    ]
    for field in when_fields:
        value = location_data[field] if pd.notna(location_data[field]) else ''
        if 'DESCRIP' in field:
            edited_data[field] = st.text_area(field, value=value, height=150)
        else:
            edited_data[field] = st.text_input(field, value=value)
    
    # Sección "Conoce los imperdibles"
    st.subheader("Conoce los imperdibles")
    # Campos principales
    main_imperdibles_fields = [
        'CARD_CONOCE_LOS_IMPERDIBLES_DE',
        'TITLE_CONOCE_LOS_IMPERDIBLES_DE',
        'IMG_CONOCE_LOS_IMPERDIBLES_DE',
        'DESCRIP_CONOCE_LOS_IMPERDIBLES_DE'
    ]
    for field in main_imperdibles_fields:
        value = location_data[field] if pd.notna(location_data[field]) else ''
        if 'DESCRIP' in field:
            edited_data[field] = st.text_area(field, value=value, height=150)
        else:
            edited_data[field] = st.text_input(field, value=value)
    
    # Subcards de imperdibles
    for i in range(1, 5):
        st.markdown(f"##### Imperdible {i}")
        subcard_fields = [
            f'SUBCARD_{i}_TITLE_CONOCE_LOS_IMPERDIBLES_DE',
            f'SUBCARD_{i}_IMG_CONOCE_LOS_IMPERDIBLES_DE',
            f'SUBCARD_{i}_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE'
        ]
        for field in subcard_fields:
            value = location_data[field] if pd.notna(location_data[field]) else ''
            if 'DESCRIP' in field:
                edited_data[field] = st.text_area(field, value=value, height=100)
            else:
                edited_data[field] = st.text_input(field, value=value)
    
    # Sección "Datos importantes"
    st.subheader("Datos importantes")
    data_fields = [
        'CARD_DATOS_IMPORTANTES',
        'IMG_DATOS_IMPORTANTES',
        'DESCRIP_DATOS_IMPORTANTES'
    ]
    for field in data_fields:
        value = location_data[field] if pd.notna(location_data[field]) else ''
        if 'DESCRIP' in field:
            edited_data[field] = st.text_area(field, value=value, height=150)
        else:
            edited_data[field] = st.text_input(field, value=value)
    
    return edited_data

# Función para probar la generación de contenido
def test_content_generation(location: str):
    with st.spinner(f"Generando contenido para {location}..."):
        st.info(f"Debug - Iniciando generación de contenido para: {location}")
        st.info("Debug - API Key configurada: Sí" if api_key else "No")
        st.info("Debug - Enviando prompt a OpenAI...")
        
        content = generate_content(location)
        if content:
            st.success(f"✅ Contenido generado exitosamente para {location}")
            return content
        else:
            st.error(f"❌ Error al generar contenido para {location}")
            return None

def init_db():
    """Inicializar la base de datos SQLite"""
    try:
        conn = sqlite3.connect('destinos.db')
        cursor = conn.cursor()
        
        # Crear tabla si no existe
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS destinos (
                location TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Verificar que la tabla existe y tiene la estructura correcta
        cursor.execute("PRAGMA table_info(destinos)")
        columns = cursor.fetchall()
        required_columns = {'location', 'content', 'last_updated'}
        existing_columns = {col[1] for col in columns}
        
        if not required_columns.issubset(existing_columns):
            st.error("Error: La tabla no tiene la estructura correcta")
            return False
        
        conn.commit()
        conn.close()
        st.write("Debug - Base de datos inicializada correctamente")
        return True
    except Exception as e:
        st.error(f"Error al inicializar la base de datos: {str(e)}")
        return False

def save_to_db(location, content):
    try:
        st.write("Debug - Iniciando guardado en base de datos local")
        
        # Asegurarse de que la base de datos está inicializada
        if not init_db():
            st.error("Error al inicializar la base de datos")
            return False
            
        # Guardar en la base de datos SQLite
        conn = sqlite3.connect('destinos.db')
        cursor = conn.cursor()
        
        # Verificar si el registro existe
        cursor.execute('SELECT * FROM destinos WHERE location = ?', (location,))
        exists = cursor.fetchone()
        
        if exists:
            st.write(f"Debug - Actualizando registro existente para {location}")
        else:
            st.write(f"Debug - Creando nuevo registro para {location}")
        
        # Convertir el diccionario a JSON para almacenamiento
        try:
            content_json = json.dumps(content, ensure_ascii=False)
        except Exception as json_error:
            st.error(f"Error al convertir contenido a JSON: {str(json_error)}")
            return False
        
        # Insertar o actualizar en la base de datos
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO destinos (location, content, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (location, content_json))
            
            conn.commit()
            st.write(f"Debug - Contenido guardado en SQLite para {location}")
            
            # Verificar que el registro se guardó correctamente
            cursor.execute('SELECT * FROM destinos WHERE location = ?', (location,))
            saved_record = cursor.fetchone()
            if not saved_record:
                st.error("Error: El registro no se guardó correctamente")
                return False
                
        except Exception as db_error:
            st.error(f"Error al guardar en la base de datos: {str(db_error)}")
            return False
        finally:
            conn.close()
        
        # Luego guardamos en Google Sheets
        try:
            # Cargar todos los datos de la base de datos
            conn = sqlite3.connect('destinos.db')
            cursor = conn.cursor()
            cursor.execute('SELECT location, content FROM destinos')
            rows = cursor.fetchall()
            conn.close()
            
            # Convertir los datos a DataFrame
            all_data = []
            for row in rows:
                location_data = row[0]
                content_data = json.loads(row[1])
                all_data.append(content_data)
            
            df = pd.DataFrame(all_data)
            st.write("Debug - DataFrame creado con todos los registros")
            st.write(f"Debug - Columnas en el DataFrame: {df.columns.tolist()}")
            
            # Intentar guardar en Google Sheets
            if save_sheet_data(df):
                st.success(f"✅ Contenido guardado exitosamente para {location} en base de datos y Google Sheets")
                return True
            else:
                st.warning(f"⚠️ Contenido guardado en la base de datos pero hubo un error al guardar en Google Sheets")
                return False
                
        except Exception as sheet_error:
            st.error(f"Error al guardar en Google Sheets: {str(sheet_error)}")
            st.warning("✓ Contenido guardado solo en la base de datos local")
            return True
            
    except Exception as e:
        st.error(f"Error al guardar en la base de datos: {str(e)}")
        return False

def load_from_db():
    """Cargar datos desde SQLite"""
    try:
        conn = sqlite3.connect('destinos.db')
        query = "SELECT location, content FROM destinos"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df.empty:
            # Convertir JSON a columnas
            content_df = pd.json_normalize([json.loads(content) for content in df['content']])
            return content_df
        return pd.DataFrame(columns=expected_columns)
    except Exception as e:
        st.error(f"Error al cargar desde la base de datos: {str(e)}")
        return None

def sync_with_sheets():
    """Sincronizar datos con Google Sheets con mejor manejo de errores"""
    try:
        df = load_from_db()
        if df is not None and not df.empty:
            service = get_google_sheets_service()
            if service is None:
                st.error("❌ No se pudo obtener el servicio de Google Sheets")
                return False
                
            success = save_sheet_data(df)
            if success:
                st.success("✅ Datos sincronizados con Google Sheets")
            else:
                st.warning("⚠️ No se pudo sincronizar con Google Sheets, pero los datos están seguros en la base de datos local")
        else:
            st.warning("⚠️ No hay datos para sincronizar")
    except Exception as e:
        st.error(f"❌ Error en la sincronización: {str(e)}")
        return False

def get_google_credentials():
    """Obtiene las credenciales de Google Sheets"""
    try:
        creds = None
        # El archivo token.pickle almacena los tokens de acceso y actualización del usuario
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # Si no hay credenciales válidas, solicita al usuario que se autentique
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Guarda las credenciales para la próxima ejecución
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        return creds
    except Exception as e:
        st.error(f"Error al obtener credenciales de Google: {str(e)}")
        return None

def connect_to_google_sheets():
    try:
        creds = get_google_credentials()
        if not creds:
            st.warning("No se pudo conectar con Google Sheets. La aplicación funcionará con almacenamiento local.")
            return None

        service = build('sheets', 'v4', credentials=creds)
        return service
    except Exception as e:
        st.warning(f"No se pudo conectar con Google Sheets: {str(e)}. La aplicación funcionará con almacenamiento local.")
        return None

def clean_database():
    """Limpiar la base de datos y mantener solo Antofagasta"""
    try:
        conn = sqlite3.connect('destinos.db')
        c = conn.cursor()
        
        # Obtener el contenido de Antofagasta
        c.execute("SELECT content FROM destinos WHERE location = 'ANTOFAGASTA'")
        antofagasta_content = c.fetchone()
        
        # Eliminar todos los registros
        c.execute("DELETE FROM destinos")
        
        # Si existe el contenido de Antofagasta, volver a insertarlo
        if antofagasta_content:
            c.execute("INSERT INTO destinos (location, content) VALUES (?, ?)", 
                     ('ANTOFAGASTA', antofagasta_content[0]))
        
        conn.commit()
        conn.close()
        st.success("✅ Base de datos limpiada exitosamente. Solo se mantiene Antofagasta.")
    except Exception as e:
        st.error(f"Error al limpiar la base de datos: {str(e)}")

def main():
    # Inicializar la base de datos
    init_db()
    
    # Verificar credenciales de Google al inicio
    if 'google_creds' not in st.session_state:
        st.session_state.google_creds = get_google_credentials()
    
    if st.session_state.google_creds is None:
        st.error("No se pudieron obtener las credenciales de Google. Por favor, verifica tu conexión y credenciales.")
        return
    
    # Agregar botón para limpiar la base de datos
    if st.sidebar.button("🔄 Limpiar Base de Datos (Mantener solo Antofagasta)"):
        clean_database()
        st.experimental_rerun()
    
    # Verificar credenciales de Google Sheets
    service = get_google_sheets_service()
    if service is None:
        st.warning("⚠️ No se pudo conectar con Google Sheets. La aplicación funcionará con almacenamiento local.")
    
    # Cargar los datos al iniciar
    if 'df' not in st.session_state:
        df = None
        # Intentar cargar desde la base de datos primero
        df = load_from_db()
        if df is not None:
            st.session_state.df = df
            st.info("ℹ️ Datos cargados desde la base de datos local")
        else:
            # Si no hay datos locales, intentar cargar desde Google Sheets
            if service is not None:
                df = load_sheet_data()
                if df is not None:
                    save_to_db(df)  # Guardar en la base de datos local
                    st.session_state.df = df
                    st.success("✅ Datos cargados desde Google Sheets y guardados localmente")
            
            if df is None:
                # Si no hay datos en ninguna fuente, crear DataFrame vacío
                df = pd.DataFrame(columns=expected_columns)
                st.session_state.df = df
                st.info("ℹ️ No se encontraron datos previos. Se iniciará con una base de datos vacía.")

    # Sidebar para agregar nuevos destinos
    with st.sidebar:
        st.header("Nuevos Destinos")
        new_locations = st.text_area(
            "Ingresa nuevos destinos (uno por línea)",
            height=100
        )
        
        if st.button("Generar Contenido"):
            if new_locations:
                locations = [loc.strip() for loc in new_locations.split('\n') if loc.strip()]
                for location in locations:
                    if location not in st.session_state.df['LOCATION'].values:
                        new_content = test_content_generation(location)
                        if new_content:
                            # Crear un nuevo DataFrame con el contenido generado
                            new_row = pd.DataFrame([new_content])
                            
                            # Asegurarse de que las columnas estén en el orden correcto
                            for col in st.session_state.df.columns:
                                if col not in new_row.columns:
                                    new_row[col] = ''
                            new_row = new_row[st.session_state.df.columns]
                            
                            # Concatenar con el DataFrame existente
                            st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                            
                            # Guardar automáticamente en la base de datos
                            if save_to_db(location, new_content):
                                st.success(f"✨ Contenido guardado exitosamente para {location}")
                                # Intentar sincronizar con Google Sheets
                                sync_with_sheets()
                            else:
                                st.error(f"Error al guardar el contenido para {location}")
                    else:
                        st.warning(f"⚠️ {location} ya existe en la base de datos")

    # Contenido principal
    if 'df' in st.session_state:
        # Selector de destino
        locations = st.session_state.df['LOCATION'].unique()
        selected_location = st.selectbox(
            "Selecciona un destino para ver o editar su contenido",
            locations
        )
        
        # Mostrar contenido del destino seleccionado
        if selected_location:
            st.markdown("---")
            st.subheader(f"📍 Contenido de {selected_location}")
            location_data = st.session_state.df[st.session_state.df['LOCATION'] == selected_location].iloc[0]
            
            # Mostrar y editar contenido
            edited_data = show_edit_content(location_data)
            
            # Botón para guardar cambios
            if st.button("💾 Guardar Cambios"):
                for col, value in edited_data.items():
                    st.session_state.df.loc[st.session_state.df['LOCATION'] == selected_location, col] = value
                
                # Guardar automáticamente en la base de datos
                if save_to_db(selected_location, edited_data):
                    st.success("✅ Cambios guardados exitosamente!")
                    # Intentar sincronizar con Google Sheets
                    sync_with_sheets()
                else:
                    st.error("❌ Error al guardar los cambios")

if __name__ == "__main__":
    main() 