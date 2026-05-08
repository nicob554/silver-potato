import asyncio
from telegram import Bot
from datetime import datetime

TOKEN = "8703193795:AAFaoujnMt9cu3HeO5BXgeWIBCwnGoh-prk"
CHAT_ID = -1003589438312           #il CHAT_ID lo devi cambiare con quello del gruppo,
THREAD_ID=2                     #per trovarlo devi mettere il bot nel gruppo (@presenzephysis_bot)
                                #scrivere un messaggio di prova poi vai su: https://api.telegram.org/bot8703193795:AAFaoujnMt9cu3HeO5BXgeWIBCwnGoh-prk/getUpdates   
                                #aggiorna la pagina, lì troverai gli ultimi messaggi del bot, vedrai che ci sono dei poll di prova
                                #devi cercare un numero negativo (che non sia -5009076359 che è il chat id del gruppo di test che ho fatto)
                                #inserisci il chat id trovato al posto di questo: -5009076359
                                #infine installa python-telegram-bot, asyncio non dovrebbe essercene bisogno



bot = Bot(token=TOKEN)

async def manda_sondaggio():
    await bot.send_poll(
        chat_id=CHAT_ID,
        message_thread_id=THREAD_ID,
        question="Weekly Attendance\nM = Morning\nA = Afternoon",
        options=[
            "Monday M",
            "Monday A",
            "Tuesday M",
            "Tuesday A",
            "Wednesday M",
            "Wednesday A",
            "Thursday M",
            "Thursday A",
            "Friday M",
            "Friday A",
            "Not coming"
        ],
        is_anonymous=False,
        allows_multiple_answers=True
    )

async def loop():
    gia_inviato = False

    while True:
        now = datetime.now()

        # sabato 12:00
        if now.weekday() == 4 and now.hour == 16 and now.minute == 52:
            if not gia_inviato:
                await manda_sondaggio()
                print("Sondaggio inviato")
                gia_inviato = True

        # reset domenica
        if now.weekday() == 6:
            gia_inviato = False

        await asyncio.sleep(30)

asyncio.run(loop())