import asyncio
import json
import os
import sys
from datetime import datetime
from telegram import Bot

CONFIG_FILE = "./bot_config.json"
CSV_FILE = "./gruppi.csv"

def _log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
    sys.stdout.flush()

def get_weekday_index(giorno_str):
    giorni = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    try:
        return giorni.index(giorno_str.strip().capitalize())
    except ValueError:
        return None

# ── CARICAMENTO GRUPPI E ORARI DA CSV ────────────────────────────────────────
def load_groups_from_csv():
    """Legge il file CSV e restituisce la lista dei gruppi con i rispettivi orari."""
    if not os.path.exists(CSV_FILE):
        _log(f"⚠️ Errore: Il file '{CSV_FILE}' non esiste!")
        try:
            with open(CSV_FILE, "w", encoding="utf-8") as f:
                f.write("Nome,Chat ID,Thread IDs,Giorno,Ora,Minuto\n")
                f.write("Physia,-1003589438312,2,Venerdì,16,52\n")
            _log(f"📁 Generato file di esempio '{CSV_FILE}'. Modificalo su VS Code e riavvia.")
        except Exception as e:
            _log(f"❌ Impossibile creare il file CSV: {e}")
        sys.exit(1)

    groups = []
    try:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if not lines:
            return groups

        # Saltiamo la riga di intestazione
        for idx, line in enumerate(lines[1:], start=2):
            line = line.strip()
            if not line:
                continue
            
            parti = line.split(",")
            if len(parti) < 6:
                _log(f"⚠️ Riga {idx} ignorata: mancano dei campi (richiesti: Nome,Chat ID,Thread IDs,Giorno,Ora,Minuto)")
                continue
            
            name = parti[0].strip()
            chat_id_raw = parti[1].strip()
            threads_raw = parti[2].strip()
            giorno_raw = parti[3].strip()
            ora_raw = parti[4].strip()
            minuto_raw = parti[5].strip()

            if not name or not chat_id_raw:
                continue

            # Validazione Chat ID
            try:
                chat_id = int(chat_id_raw)
            except ValueError:
                _log(f"❌ Chat ID non valido alla riga {idx} ({name}): {chat_id_raw}")
                continue

            # Validazione Giorno
            target_day = get_weekday_index(giorno_raw)
            if target_day is None:
                _log(f"❌ Giorno '{giorno_raw}' non valido alla riga {idx} ({name}). Usa Lunedì, Martedì, ecc.")
                continue

            # Validazione Ora e Minuto
            try:
                ora = int(ora_raw)
                minuto = int(minuto_raw)
                if not (0 <= ora <= 23 and 0 <= minuto <= 59):
                    raise ValueError
            except ValueError:
                _log(f"❌ Orario non valido alla riga {idx} ({name}): {ora_raw}:{minuto_raw}")
                continue

            # Parsing dei Thread (separati da punto e virgola se multipli)
            threads = []
            if threads_raw:
                for t in threads_raw.replace(";", " ").split():
                    if t.strip():
                        try:
                            threads.append(int(t.strip()))
                        except ValueError:
                            _log(f"❌ Thread ID non valido '{t}' alla riga {idx}")

            groups.append({
                "name": name,
                "chat_id": chat_id,
                "threads": threads,
                "target_day": target_day,
                "target_hour": ora,
                "target_minute": minuto,
                "id_univoco": f"{chat_id}_{threads_raw}_{giorno_raw}_{ora}_{minuto}" # Identificativo per evitare doppi invii nello stesso minuto
            })
            
        return groups
    except Exception as e:
        _log(f"❌ Errore durante la lettura del file dei gruppi: {e}")
        return []

# ── CARICAMENTO CONFIGURAZIONE GENERALE (JSON) ───────────────────────────────
def load_config():
    default_config = {
        "token": "8703193795:AAFaoujnMt9cu3HeO5BXgeWIBCwnGoh-prk",
        "domanda": "Weekly Attendance\nM = Morning\nA = Afternoon",
        "opzioni": "Monday M\nMonday A\nTuesday M\nTuesday A\nWednesday M\nWednesday A\nThursday M\nThursday A\nFriday M\nFriday A\nNot coming"
    }

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        _log(f"📁 File di configurazione '{CONFIG_FILE}' creato.")
        return default_config

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ── INVIO SONDAGGIO SINGOLO GRUPPO ───────────────────────────────────────────
async def manda_sondaggio_a_gruppo(bot, config, group):
    domanda = config["domanda"]
    options = [opt.strip() for opt in config["opzioni"].splitlines() if opt.strip()]
    
    chat_id = group["chat_id"]
    threads = group["threads"]
    name = group["name"]

    destinations = threads if threads else [None]

    for thread_id in destinations:
        try:
            kwargs = dict(
                chat_id=chat_id,
                question=domanda,
                options=options,
                is_anonymous=False,
                allows_multiple_answers=True
            )
            if thread_id is not None:
                kwargs["message_thread_id"] = thread_id

            await bot.send_poll(**kwargs)
            dest = f"thread {thread_id}" if thread_id else "Generale"
            _log(f"  ✅ Inviato a '{name}' ({dest})")
        except Exception as e:
            dest = f"thread {thread_id}" if thread_id else "Generale"
            _log(f"  ❌ Errore '{name}' ({dest}): {e}")

# ── LOOP PRINCIPALE ─────────────────────────────────────────────────────────
async def main():
    _log("Avvio del Bot Presenze Telegram (Senza GUI, Orari personalizzati nel CSV)...")
    
    # Registro per tenere traccia di cosa è già stato inviato e in quale giorno dell'anno
    # Struttura: { "id_univoco": giorno_dell_anno }
    registro_invii = {}

    while True:
        config = load_config()
        groups = load_groups_from_csv()
        bot = Bot(token=config["token"].strip())

        now = datetime.now()
        giorno_corrente_anno = now.timetuple().tm_yday

        for group in groups:
            # Verifica se siamo nel giorno, ora e minuto corretti per questo specifico gruppo
            if (now.weekday() == group["target_day"] and
                    now.hour == group["target_hour"] and
                    now.minute == group["target_minute"]):
                
                id_invio = group["id_univoco"]
                
                # Se non è ancora stato inviato OGGI per questa pianificazione
                if registro_invii.get(id_invio) != giorno_corrente_anno:
                    _log(f"Orario raggiunto per '{group['name']}'. Invio in corso...")
                    await manda_sondaggio_a_gruppo(bot, config, group)
                    registro_invii[id_invio] = giorno_corrente_anno

        # Pulisce i vecchi record del registro passati da più di 2 giorni per non appesantire la memoria
        for k in list(registro_invii.keys()):
            if abs(giorno_corrente_anno - registro_invii[k]) > 2:
                del registro_invii[k]

        # Controlla lo schedule ogni 30 secondi
        await asyncio.sleep(30)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log("Bot arrestato manualmente.")