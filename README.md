# JetSMART Content Manager

Aplicación web desarrollada con Streamlit para gestionar contenido turístico de destinos JetSMART. La aplicación permite generar, editar y almacenar contenido de manera eficiente utilizando IA y sincronización con Google Sheets.

## Características

- Generación automática de contenido turístico usando GPT-4
- Interfaz de usuario intuitiva para edición de contenido
- Almacenamiento local con SQLite
- Sincronización con Google Sheets
- Sistema de respaldo híbrido (local + cloud)
- Manejo de múltiples destinos turísticos

## Requisitos

- Python 3.8+
- Cuenta de Google Cloud Platform con API de Google Sheets habilitada
- API Key de OpenAI

## Instalación

1. Clonar el repositorio:
```bash
git clone [URL_DEL_REPOSITORIO]
cd [NOMBRE_DEL_DIRECTORIO]
```

2. Crear y activar entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
Crear un archivo `.env` en la raíz del proyecto con:
```
OPENAI_API_KEY=tu_api_key_de_openai
GOOGLE_DRIVE_FILE_ID=id_de_tu_google_sheet
```

5. Configurar credenciales de Google:
- Crear un proyecto en Google Cloud Console
- Habilitar la API de Google Sheets
- Descargar el archivo `credentials.json` y colocarlo en la raíz del proyecto

## Uso

1. Iniciar la aplicación:
```bash
streamlit run app.py
```

2. Acceder a la aplicación en el navegador:
```
http://localhost:8501
```

3. Para agregar nuevos destinos:
   - Ingresar el nombre del destino en el panel lateral
   - Hacer clic en "Generar Contenido"
   - Revisar y editar el contenido generado
   - Guardar los cambios

## Estructura del Proyecto

```
├── app.py                 # Aplicación principal
├── requirements.txt       # Dependencias del proyecto
├── .env                  # Variables de entorno
├── credentials.json      # Credenciales de Google Cloud
├── destinos.db          # Base de datos SQLite local
└── README.md            # Documentación
```

## Contribuir

1. Fork del repositorio
2. Crear una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit de tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles. 