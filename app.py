import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Esencial para permitir que el portal web le envíe datos

# ================= CONFIGURACIÓN DE VARIABLES =================
# En Render, estas variables las configuraremos en la sección "Environment"
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "tu_base_id_aqui")
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME", "Solicitudes")
AIRTABLE_PAT = os.environ.get("AIRTABLE_PAT", "tu_token_airtable_aqui")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "tu_token_telegram_aqui")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "tu_chat_id_aqui")
# ==============================================================

@app.route('/api/solicitar', methods=['POST'])
def solicitar_cancion():
    # Recibir los datos del frontend (JSON)
    data = request.get_json()

    cancion = data.get('cancion', '').strip()
    artista = data.get('artista', '').strip()
    nombre = data.get('nombre', '').strip()
    dedicatoria = data.get('dedicatoria', '').strip()

    # Validación básica de seguridad
    if not cancion or not artista or not nombre:
        return jsonify({'error': 'Faltan campos obligatorios'}), 400

    # 1. GUARDAR EN AIRTABLE
    url_airtable = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers_airtable = {
        "Authorization": f"Bearer {AIRTABLE_PAT}",
        "Content-Type": "application/json"
    }
    payload_airtable = {
        "fields": {
            "Cancion": cancion,                  # Sin acento, igual que en tu tabla
            "quien_canta": artista,              # Tu columna de artista
            "Nombre_solicitante": nombre,        # Tu columna de usuario
            "Dedicatoria": dedicatoria, 
            "Estado": "💈 En Cola"               # O el estado inicial que prefieras
        }
    }

    # Intentamos guardar en Airtable primero
    try:
        requests.post(url_airtable, json=payload_airtable, headers=headers_airtable, timeout=10)
    except Exception as e:
        print(f"Error en Airtable: {e}")
        # Si Airtable falla, podemos decidir si detenemos el proceso o seguimos con Telegram
        return jsonify({'error': 'Error guardando en la base de datos'}), 500

    # 2. ENVIAR NOTIFICACIÓN A TELEGRAM AL DJ
    texto_telegram = (
        "🎧 *NUEVA PETICIÓN*\n\n"
        f"🎵 *Pista:* {cancion}\n"
        f"🎤 *Artista:* {artista}\n"
        f"👤 *Pide:* {nombre}\n"
        f"💬 *Nota:* {dedicatoria}"
    )

    url_telegram = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload_telegram = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto_telegram,
        "parse_mode": "Markdown",
        # Botones interactivos para que el DJ gestione la petición rápido
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "✅ Puesta", "callback_data": "puesta"},
                    {"text": "❌ Omitida", "callback_data": "omitida"}
                ]
            ]
        }
    }

    try:
        requests.post(url_telegram, json=payload_telegram, timeout=10)
    except Exception as e:
        print(f"Error en Telegram: {e}")
        # Aquí no retornamos error 500 porque la canción ya se guardó en Airtable

    # Respuesta de éxito al portal web
    return jsonify({'status': 'ok', 'mensaje': 'Enviado exitosamente'}), 200

# Ruta de prueba para verificar que el servidor está vivo
@app.route('/', methods=['GET'])
def health_check():
    return "API DJ Nova Sets Activa y Funcionando 🎧", 200

if __name__ == '__main__':
    # Puerto para pruebas locales
    app.run(host='0.0.0.0', port=5000, debug=True)