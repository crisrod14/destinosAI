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

# Configuración de la página
st.set_page_config(
    page_title="JetSMART Content Manager",
    page_icon="✈️",
    layout="wide"
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

# Título y descripción
st.title("✈️ JetSMART Content Manager")
st.markdown("""
    Esta aplicación te permite gestionar el contenido turístico para los destinos de JetSMART.
    Puedes visualizar, editar y generar nuevo contenido automáticamente.
""")

# Función para autenticación con Google Sheets
def get_google_sheets_service():
    """Obtener servicio de Google Sheets con manejo de errores mejorado"""
    try:
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = None
        
        # Verificar si existe el archivo credentials.json
        if not os.path.exists('credentials.json'):
            st.error("❌ No se encontró el archivo credentials.json")
            st.info("Por favor, asegúrate de tener el archivo credentials.json en el directorio del proyecto")
            return None
        
        # Verificar/cargar token existente
        if os.path.exists('token.json'):
            try:
                creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            except Exception as e:
                st.warning("⚠️ El token existente no es válido, se generará uno nuevo")
                if os.path.exists('token.json'):
                    os.remove('token.json')
                creds = None
        
        # Si no hay credenciales válidas, solicitar autorización
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    st.warning("⚠️ Error al refrescar el token, se solicitará nueva autorización")
                    creds = None
            
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                    
                    # Guardar las credenciales para la próxima ejecución
                    with open('token.json', 'w') as token:
                        token.write(creds.to_json())
                    st.success("✅ Nuevas credenciales generadas exitosamente")
                except Exception as e:
                    st.error(f"❌ Error durante la autorización: {str(e)}")
                    return None
        
        # Construir el servicio
        try:
            service = build('sheets', 'v4', credentials=creds)
            return service
        except Exception as e:
            st.error(f"❌ Error al construir el servicio de Google Sheets: {str(e)}")
            return None
            
    except Exception as e:
        st.error(f"❌ Error en la autenticación de Google Sheets: {str(e)}")
        return None

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

# Función para guardar datos en Google Sheets
def save_sheet_data(df):
    try:
        service = get_google_sheets_service()
        spreadsheet_id = os.getenv('GOOGLE_DRIVE_FILE_ID')
        
        # Reemplazar NaN con cadenas vacías y convertir todos los valores a string
        df_clean = df.fillna('')
        
        # Lista completa de columnas en el orden correcto
        expected_columns = [
            'LOCATION',
            'NAV_BAR',
            'NAV_ACERCA DE',
            'NAV_QUE_HACER_EN',
            'NAV_CUANDO_IR_A',
            'NAV_LOS_IMPERDIBLES_DE',
            'CARD_CONOCE_LA_CIUDAD_DE',
            'TITLE_CONOCE_LA_CIUDAD_DE',
            'IMG_CONOCE_LA_CIUDAD_DE',
            'DESCRIP_CONOCE_LA_CIUDAD_DE',
            'CARD_ACERCA_DEL_AEROPUERTO',
            'IMG_ACERCA_DEL_AEROPUERTO',
            'SUBTITLE_ACERCA_DEL_AEROPUERTO',
            'DESCRIP_ACERCA_DEL_AEROPUERTO',
            'CARD_QUE_HACER_EN',
            'TITLE_QUE_HACER_EN',
            'IMG_QUE_HACER_EN',
            'SUBTITLE_QUE_HACER_EN',
            'DESCRIP_QUE_HACER_EN',
            'CARD_CUANDO_IR_A',
            'TITLE_CUANDO_IR_A',
            'SUBTITLE_CUANDO_IR_A',
            'IMG_1_CUANDO_IR_A',
            'DESCRIP_CUANDO_IR_A',
            'IMG_2_CUANDO_IR_A',
            'CARD_CONOCE_LOS_IMPERDIBLES_DE',
            'TITLE_CONOCE_LOS_IMPERDIBLES_DE',
            'IMG_CONOCE_LOS_IMPERDIBLES_DE',
            'DESCRIP_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_1_TITLE_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_1_IMG_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_1_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_2_TITLE_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_2_IMG_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_2_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_3_TITLE_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_3_IMG_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_3_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_4_TITLE_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_4_IMG_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_4_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE',
            'CARD_DATOS_IMPORTANTES',
            'IMG_DATOS_IMPORTANTES',
            'DESCRIP_DATOS_IMPORTANTES'
        ]
        
        # Asegurarse de que el DataFrame tenga todas las columnas en el orden correcto
        for col in expected_columns:
            if col not in df_clean.columns:
                df_clean[col] = ''
        
        # Reordenar las columnas
        df_clean = df_clean[expected_columns]
        
        # Convertir DataFrame a lista de valores, asegurando que todo sea string
        values = [expected_columns]  # Primera fila son los encabezados
        for _, row in df_clean.iterrows():
            values.append([str(val) if pd.notna(val) else '' for val in row])
        
        # Construir el rango basado en el número de filas y columnas
        num_rows = len(values)
        num_cols = len(expected_columns)
        
        st.write("Debug - Preparando datos para guardar:")
        st.write(f"- Número de filas: {num_rows}")
        st.write(f"- Número de columnas: {num_cols}")
        
        try:
            # Obtener metadata del spreadsheet
            sheet_metadata = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()
            
            # Convertir número de columnas a letras
            def num_to_col_letter(n):
                result = ""
                while n > 0:
                    n, remainder = divmod(n - 1, 26)
                    result = chr(65 + remainder) + result
                return result
            
            last_col = num_to_col_letter(num_cols)
            range_name = f"'Destinos'!A1:{last_col}{num_rows}"
            
            st.write(f"Debug - Rango a escribir: {range_name}")
            
            # Limpiar el contenido existente en la hoja Destinos
            clear_result = service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range="'Destinos'",
                body={}
            ).execute()
            
            # Escribir los nuevos datos
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body={'values': values}
            ).execute()
            
            st.success(f"✅ Se actualizaron {result.get('updatedCells')} celdas en la hoja 'Destinos'")
            return True
            
        except Exception as e:
            st.error(f"Error al actualizar la hoja 'Destinos': {str(e)}")
            if hasattr(e, 'content'):
                st.error(f"Detalles adicionales: {e.content.decode('utf-8') if isinstance(e.content, bytes) else e.content}")
            return False
            
    except Exception as e:
        st.error(f"❌ Error al guardar los datos: {str(e)}")
        if hasattr(e, 'content'):
            st.error(f"Detalles adicionales: {e.content.decode('utf-8') if isinstance(e.content, bytes) else e.content}")
        return False

# Función para generar contenido con IA
def generate_content(location: str) -> Dict[str, str]:
    try:
        st.write("Debug - Iniciando generación de contenido para:", location)
        st.write("Debug - API Key configurada:", "Sí" if api_key else "No")
        
        # Lista ordenada de campos esperados
        expected_fields = [
            'LOCATION',
            'NAV_BAR',
            'NAV_ACERCA DE',
            'NAV_QUE_HACER_EN',
            'NAV_CUANDO_IR_A',
            'NAV_LOS_IMPERDIBLES_DE',
            'CARD_CONOCE_LA_CIUDAD_DE',
            'TITLE_CONOCE_LA_CIUDAD_DE',
            'IMG_CONOCE_LA_CIUDAD_DE',
            'DESCRIP_CONOCE_LA_CIUDAD_DE',
            'CARD_ACERCA_DEL_AEROPUERTO',
            'IMG_ACERCA_DEL_AEROPUERTO',
            'SUBTITLE_ACERCA_DEL_AEROPUERTO',
            'DESCRIP_ACERCA_DEL_AEROPUERTO',
            'CARD_QUE_HACER_EN',
            'TITLE_QUE_HACER_EN',
            'IMG_QUE_HACER_EN',
            'SUBTITLE_QUE_HACER_EN',
            'DESCRIP_QUE_HACER_EN',
            'CARD_CUANDO_IR_A',
            'TITLE_CUANDO_IR_A',
            'SUBTITLE_CUANDO_IR_A',
            'IMG_1_CUANDO_IR_A',
            'DESCRIP_CUANDO_IR_A',
            'IMG_2_CUANDO_IR_A',
            'CARD_CONOCE_LOS_IMPERDIBLES_DE',
            'TITLE_CONOCE_LOS_IMPERDIBLES_DE',
            'IMG_CONOCE_LOS_IMPERDIBLES_DE',
            'DESCRIP_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_1_TITLE_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_1_IMG_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_1_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_2_TITLE_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_2_IMG_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_2_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_3_TITLE_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_3_IMG_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_3_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_4_TITLE_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_4_IMG_CONOCE_LOS_IMPERDIBLES_DE',
            'SUBCARD_4_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE',
            'CARD_DATOS_IMPORTANTES',
            'IMG_DATOS_IMPORTANTES',
            'DESCRIP_DATOS_IMPORTANTES'
        ]
        
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
        
        prompt = f"""
        Actúa como un creador de contenido especializado en turismo y panoramas, con experiencia redactando para aerolíneas low-cost como JetSMART.
        Genera contenido para la ciudad de {location}. Solo necesito que generes el contenido para las siguientes descripciones, manteniendo el resto de campos vacíos o con sus valores por defecto:

        DESCRIP_CONOCE_LA_CIUDAD_DE: [descripción detallada de la ciudad, similar a: "La Perla Del Norte" o Capital Minera se ubica al Norte de la costa del pacífico y se destaca por su gastronomía, historia, patrimonio, paisajes, turismo aventura, entretención y vida nocturna, todo lo que hará de tu viaje una experiencia totalmente SMART.]

        SUBTITLE_ACERCA_DEL_AEROPUERTO: [nombre del aeropuerto]
        DESCRIP_ACERCA_DEL_AEROPUERTO: [descripción detallada del aeropuerto y cómo llegar a la ciudad]

        SUBTITLE_QUE_HACER_EN: [subtítulo breve]
        DESCRIP_QUE_HACER_EN: [descripción de actividades y lugares para visitar]

        TITLE_CUANDO_IR_A: [título breve]
        SUBTITLE_CUANDO_IR_A: [subtítulo sobre la mejor época]
        DESCRIP_CUANDO_IR_A: [descripción detallada sobre cuándo visitar]

        SUBCARD_1_TITLE_CONOCE_LOS_IMPERDIBLES_DE: [nombre del primer lugar imperdible]
        SUBCARD_1_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE: [descripción del primer lugar]

        SUBCARD_2_TITLE_CONOCE_LOS_IMPERDIBLES_DE: [nombre del segundo lugar imperdible]
        SUBCARD_2_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE: [descripción del segundo lugar]

        SUBCARD_3_TITLE_CONOCE_LOS_IMPERDIBLES_DE: [nombre del tercer lugar imperdible]
        SUBCARD_3_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE: [descripción del tercer lugar]

        SUBCARD_4_TITLE_CONOCE_LOS_IMPERDIBLES_DE: [nombre del cuarto lugar imperdible]
        SUBCARD_4_DESCRIP__CONOCE_LOS_IMPERDIBLES_DE: [descripción del cuarto lugar]

        DESCRIP_DATOS_IMPORTANTES: [información práctica sobre la ciudad]

        Responde SOLO con el contenido solicitado, manteniendo el formato exacto de los nombres de los campos.
        """
        
        st.write("Debug - Enviando prompt a OpenAI...")
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un experto en contenido turístico para JetSMART. Genera solo el contenido solicitado, manteniendo los nombres de los campos exactamente como se muestran."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        st.write("Debug - Respuesta recibida de OpenAI")
        content = response.choices[0].message.content
        
        # Procesar la respuesta línea por línea
        current_field = None
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Buscar campos que coincidan exactamente con los esperados
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    field = parts[0].strip()
                    value = parts[1].strip()
                    if field in expected_fields:
                        content_dict[field] = value
                        st.write(f"Debug - Campo actualizado: {field}")
            elif current_field and current_field in expected_fields:
                content_dict[current_field] += ' ' + line
        
        # Verificar que los campos principales tengan contenido
        main_fields = [
            'DESCRIP_CONOCE_LA_CIUDAD_DE',
            'DESCRIP_ACERCA_DEL_AEROPUERTO',
            'DESCRIP_QUE_HACER_EN',
            'DESCRIP_CUANDO_IR_A',
            'DESCRIP_DATOS_IMPORTANTES'
        ]
        empty_fields = [field for field in main_fields if not content_dict[field]]
        if empty_fields:
            st.warning(f"Los siguientes campos importantes están vacíos: {', '.join(empty_fields)}")
        
        return content_dict
    except Exception as e:
        st.error(f"Error al generar contenido: {str(e)}")
        st.error(f"Detalles adicionales del error: {type(e).__name__}")
        import traceback
        st.error(f"Traceback: {traceback.format_exc()}")
        return {}

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
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS destinos
                    (location TEXT PRIMARY KEY, 
                     content JSON,
                     last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
        st.success("✅ Base de datos inicializada correctamente")
    except Exception as e:
        st.error(f"Error al inicializar la base de datos: {str(e)}")

def save_to_db(df, location=None):
    """Guardar datos en SQLite"""
    try:
        conn = sqlite3.connect('destinos.db')
        if location:
            # Guardar solo la fila específica
            row = df[df['LOCATION'] == location].iloc[0]
            content = row.to_json()
            conn.execute('''INSERT OR REPLACE INTO destinos (location, content, last_updated) 
                          VALUES (?, ?, CURRENT_TIMESTAMP)''', 
                       (location, content))
        else:
            # Guardar todo el DataFrame
            for _, row in df.iterrows():
                content = row.to_json()
                conn.execute('''INSERT OR REPLACE INTO destinos (location, content, last_updated) 
                              VALUES (?, ?, CURRENT_TIMESTAMP)''', 
                           (row['LOCATION'], content))
        conn.commit()
        conn.close()
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

def main():
    # Inicializar la base de datos
    init_db()
    
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
                            if save_to_db(st.session_state.df, location):
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
                if save_to_db(st.session_state.df, selected_location):
                    st.success("✅ Cambios guardados exitosamente!")
                    # Intentar sincronizar con Google Sheets
                    sync_with_sheets()
                else:
                    st.error("❌ Error al guardar los cambios")

if __name__ == "__main__":
    main() 