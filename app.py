import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ================= CONFIGURACIÓN DE VARIABLES =================
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "tu_base_id_aqui")
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME", "Cancion_solicitud")
AIRTABLE_PAT = os.environ.get("AIRTABLE_PAT", "tu_token_airtable_aqui")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "tu_token_telegram_aqui")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "tu_chat_id_aqui")
# ==============================================================

@app.route('/api/solicitar', methods=['POST'])
def solicitar_cancion():
    data = request.get_json()
    cancion = data.get('cancion', '').strip()
    artista = data.get('artista', '').strip()
    nombre = data.get('nombre', '').strip()
    dedicatoria = data.get('dedicatoria', '').strip()

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
            # Capturamos el ID único que Airtable le asignó a esta fila
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

    # Solo mostramos los botones si Airtable nos devolvió el ID correctamente
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

    return jsonify({'status': 'ok', 'mensaje': 'Enviado exitosamente'}), 200


# ==============================================================
# NUEVA RUTA: RECIBIR LOS CLICS DE LOS BOTONES DE TELEGRAM
# ==============================================================
@app.route('/api/telegram-webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    
    # Verificamos si la petición viene de un clic en un botón (callback_query)
    if "callback_query" in data:
        callback = data["callback_query"]
        callback_id = callback["id"]
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        callback_data = callback["data"] # Ejemplo: "puesta_rec123ABC"
        
        # Separamos la acción del ID de Airtable
        partes = callback_data.split('_')
        if len(partes) == 2:
            accion, record_id = partes
            
            # ATENCIÓN: Estos textos deben existir exactamente igual en tu columna "Estado" de Airtable
            nuevo_estado = "✅ Ya Sonó" if accion == "puesta" else "❌ Omitida"
                
            # 1. Actualizamos el registro en Airtable (usando PATCH)
            url_update = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
            headers = {
                "Authorization": f"Bearer {AIRTABLE_PAT}",
                "Content-Type": "application/json"
            }
            payload_update = {"fields": {"Estado": nuevo_estado}}
            requests.patch(url_update, json=payload_update, headers=headers)
            
            # 2. Quitamos los botones del mensaje de Telegram para que no los vuelvan a pulsar
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup", json={
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": {"inline_keyboard": []} # Botones vacíos
            })
            
            # 3. Le respondemos a Telegram para que deje de parpadear el botón
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={
                "callback_query_id": callback_id,
                "text": f"Canción {nuevo_estado}"
            })
            
    return jsonify({"status": "ok"}), 200

# ==============================================================

@app.route('/', methods=['GET'])
def health_check():
    return "API DJ Nova Sets Activa y Funcionando 🎧", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
