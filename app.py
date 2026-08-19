import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Esencial para permitir que el portal web le envíe datos

# ================= CONFIGURACIÓN DE VARIABLES =================
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "tu_base_id_aqui")
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME", "Cancion_solicitud")
AIRTABLE_PAT = os.environ.get("AIRTABLE_PAT", "tu_token_airtable_aqui")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "tu_token_telegram_aqui")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "tu_chat_id_aqui")
# ==============================================================

@app.route('/api/solicitar', methods=['POST'])
def solicitar_cancion():
    # Recibir los datos del frontend
    data = request.get_json()

    cancion = data.get('cancion', '').strip()
    artista = data.get('artista', '').strip()
    nombre = data.get('nombre', '').strip()
    dedicatoria = data.get('dedicatoria', '').strip()

    # Validación básica
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
            "Cancion": cancion,                  
            "quien_canta": artista,              
            "Nombre_solicitante": nombre,        
            "Dedicatoria": dedicatoria
        }
    }

    record_id = None
    try:
        res_airtable = requests.post(url_airtable, json=payload_airtable, headers=headers_airtable, timeout=10)
        if res_airtable.status_code == 200:
            # Capturamos el ID único de la fila para los botones
            record_id = res_airtable.json().get('id')
        else:
            print(f"⚠️ ERROR DE AIRTABLE: {res_airtable.text}")
    except Exception as e:
        print(f"Error de conexión en Airtable: {e}")

    # 2. ENVIAR NOTIFICACIÓN A TELEGRAM AL DJ
    texto_telegram = (
        "🎧 *NUEVA PETICIÓN*\n\n"
        f"🎵 *Pista:* {cancion}\n"
        f"🎤 *Artista:* {artista}\n"
        f"👤 *Pide:* {nombre}\n"
        f"💬 *Nota:* {dedicatoria}"
    )

    # Solo agregamos los botones si Airtable nos devolvió el ID
    botones = []
    if record_id:
        botones = [
            [
                {"text": "✅ Puesta", "callback_data": f"puesta_{record_id}"},
                {"text": "❌ Omitida", "callback_data": f"omitida_{record_id}"}
            ]
        ]

    url_telegram = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload_telegram = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto_telegram,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": botones} if botones else {}
    }

    try:
        requests.post(url_telegram, json=payload_telegram, timeout=10)
    except Exception as e:
        print(f"Error en Telegram: {e}")

    # Respuesta de éxito al portal web
    return jsonify({'status': 'ok', 'mensaje': 'Enviado exitosamente'}), 200


# ==============================================================
# NUEVA RUTA: RECIBIR LOS CLICS DE LOS BOTONES DE TELEGRAM
# ==============================================================
@app.route('/api/telegram-webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    
    if "callback_query" in data:
        callback = data["callback_query"]
        callback_id = callback["id"]
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        callback_data = callback["data"]
        
        # Recuperamos el texto original del mensaje
        texto_original = callback["message"].get("text", "")
        
        partes = callback_data.split('_')
        if len(partes) == 2:
            accion, record_id = partes
            
            # Definimos el estado para Airtable y el "Sello" visual para Telegram
            if accion == "puesta":
                nuevo_estado = "👍 Aceptada"
                sello_telegram = "\n\n✨ ESTATUS: ACEPTADA ✨"
            else:
                nuevo_estado = "❌ Rechazada"
                sello_telegram = "\n\n🚫 ESTATUS: RECHAZADA 🚫"
                
            # 1. Actualizamos el registro en Airtable
            url_update = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
            headers = {
                "Authorization": f"Bearer {AIRTABLE_PAT}",
                "Content-Type": "application/json"
            }
            payload_update = {"fields": {"Estado": nuevo_estado}}
            requests.patch(url_update, json=payload_update, headers=headers)
            
            # 2. Editamos el mensaje en Telegram (Agregamos el sello y quitamos botones)
            nuevo_texto = texto_original + sello_telegram
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": nuevo_texto,
                "reply_markup": {"inline_keyboard": []} 
            })
            
            # 3. Le respondemos a Telegram para que deje de cargar el botoncito
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={
                "callback_query_id": callback_id,
                "text": f"Canción {nuevo_estado}"
            })
            
    return jsonify({"status": "ok"}), 200

# ==============================================================

# Ruta de prueba para verificar que el servidor está vivo
@app.route('/', methods=['GET'])
def health_check():
    return "API DJ Nova Sets Activa y Funcionando 🎧", 200

if __name__ == '__main__':
    # Puerto para pruebas locales
    app.run(host='0.0.0.0', port=5000, debug=True)
