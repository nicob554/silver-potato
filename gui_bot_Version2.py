import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import asyncio
import sys
import io
import json
import os
from datetime import datetime

from telegram import Bot

CONFIG_FILE = "./bot_config.json"

# ── redirect stdout ──────────────────────────────────────────────────────────
class TextRedirector(io.TextIOBase):
    def __init__(self, widget):
        self.widget = widget

    def write(self, s):
        self.widget.configure(state="normal")
        self.widget.insert(tk.END, s)
        self.widget.see(tk.END)
        self.widget.configure(state="disabled")
        return len(s)

    def flush(self):
        pass


# ── App ──────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bot Presenze Telegram")
        self.resizable(True, True)
        self._running = False
        self._loop_thread = None
        self._build_ui()
        self._load_config()

    # ── UI ────────────────���──────────────────────────────────────────────────
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        nb = ttk.Notebook(self)
        nb.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        tab_run    = ttk.Frame(nb)
        tab_groups = ttk.Frame(nb)
        nb.add(tab_run,    text="  Run  ")
        nb.add(tab_groups, text="  Gruppi  ")

        self._build_tab_run(tab_run, pad)
        self._build_tab_groups(tab_groups, pad)

    # ── TAB RUN ──────────────────────────────────────────────────────────────
    def _build_tab_run(self, parent, pad):
        parent.columnconfigure(0, weight=1)

        # Token
        frame_cfg = ttk.LabelFrame(parent, text="Configurazione Bot")
        frame_cfg.grid(row=0, column=0, sticky="ew", **pad)
        frame_cfg.columnconfigure(1, weight=1)

        ttk.Label(frame_cfg, text="Token:").grid(row=0, column=0, sticky="w", **pad)
        self.var_token = tk.StringVar(value="8703193795:AAFaoujnMt9cu3HeO5BXgeWIBCwnGoh-prk")
        self.entry_token = ttk.Entry(frame_cfg, textvariable=self.var_token, width=55, show="*")
        self.entry_token.grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(frame_cfg, text="👁", width=3,
                   command=self._toggle_token).grid(row=0, column=2, padx=4)

        # Scheduling
        frame_sched = ttk.LabelFrame(parent, text="Scheduling invio sondaggio")
        frame_sched.grid(row=1, column=0, sticky="ew", **pad)

        giorni = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
        ttk.Label(frame_sched, text="Giorno:").grid(row=0, column=0, sticky="w", **pad)
        self.var_giorno = tk.StringVar(value="Venerdì")
        ttk.Combobox(frame_sched, textvariable=self.var_giorno, values=giorni,
                     state="readonly", width=12).grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(frame_sched, text="Ora:").grid(row=0, column=2, sticky="w", **pad)
        self.var_ora = tk.StringVar(value="16")
        ttk.Spinbox(frame_sched, textvariable=self.var_ora, from_=0, to=23,
                    width=4, format="%02.0f").grid(row=0, column=3, sticky="w", **pad)

        ttk.Label(frame_sched, text="Minuto:").grid(row=0, column=4, sticky="w", **pad)
        self.var_minuto = tk.StringVar(value="52")
        ttk.Spinbox(frame_sched, textvariable=self.var_minuto, from_=0, to=59,
                    width=4, format="%02.0f").grid(row=0, column=5, sticky="w", **pad)

        # Sondaggio
        frame_poll = ttk.LabelFrame(parent, text="Sondaggio")
        frame_poll.grid(row=2, column=0, sticky="ew", **pad)
        frame_poll.columnconfigure(1, weight=1)

        ttk.Label(frame_poll, text="Domanda:").grid(row=0, column=0, sticky="w", **pad)
        self.var_domanda = tk.StringVar(value="Weekly Attendance\nM = Morning\nA = Afternoon")
        ttk.Entry(frame_poll, textvariable=self.var_domanda, width=55).grid(row=0, column=1, sticky="ew", **pad)

        ttk.Label(frame_poll, text="Opzioni\n(una per riga):").grid(row=1, column=0, sticky="nw", **pad)
        self.txt_opzioni = tk.Text(frame_poll, height=12, width=35)
        self.txt_opzioni.grid(row=1, column=1, sticky="ew", **pad)
        self.txt_opzioni.insert(tk.END,
            "Monday M\nMonday A\nTuesday M\nTuesday A\n"
            "Wednesday M\nWednesday A\nThursday M\nThursday A\n"
            "Friday M\nFriday A\nNot coming"
        )

        # Bottoni
        frame_btn = ttk.Frame(parent)
        frame_btn.grid(row=3, column=0, sticky="ew", **pad)

        self.btn_start = ttk.Button(frame_btn, text="▶  Avvia bot",        command=self._start)
        self.btn_stop  = ttk.Button(frame_btn, text="⏹  Ferma bot",        command=self._stop, state="disabled")
        self.btn_test  = ttk.Button(frame_btn, text="📨  Invia ora (test)", command=self._send_now)
        self.btn_save  = ttk.Button(frame_btn, text="💾  Salva config",     command=self._save_config)
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop.pack(side="left",  padx=4)
        self.btn_test.pack(side="left",  padx=4)
        self.btn_save.pack(side="left",  padx=4)

        self.lbl_status = ttk.Label(frame_btn, text="⚫ Fermo")
        self.lbl_status.pack(side="left", padx=12)

        # Log
        frame_log = ttk.LabelFrame(parent, text="Log")
        frame_log.grid(row=4, column=0, sticky="nsew", **pad)
        parent.rowconfigure(4, weight=1)

        self.log = scrolledtext.ScrolledText(frame_log, height=10, width=80,
                                             state="disabled", font=("Courier", 9), wrap="word")
        self.log.pack(fill="both", expand=True, padx=4, pady=4)
        sys.stdout = TextRedirector(self.log)

    # ── TAB GRUPPI ───────────────────────────────────────────────────────────
    def _build_tab_groups(self, parent, pad):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent,
                  text="Aggiungi tutti i gruppi a cui vuoi mandare il sondaggio.\n"
                       "Se un gruppo non ha thread (= manda sul Generale), lascia vuoto il campo Thread IDs.",
                  foreground="gray"
                  ).grid(row=0, column=0, sticky="w", **pad)

        # Treeview
        frame_tree = ttk.Frame(parent)
        frame_tree.grid(row=1, column=0, sticky="nsew", **pad)
        frame_tree.columnconfigure(0, weight=1)
        frame_tree.rowconfigure(0, weight=1)

        cols = ("name", "chat_id", "threads")
        self.tree = ttk.Treeview(frame_tree, columns=cols, show="headings", height=10)
        self.tree.heading("name",     text="Nome gruppo")
        self.tree.heading("chat_id",  text="Chat ID")
        self.tree.heading("threads",  text="Thread IDs (separati da virgola)")
        self.tree.column("name",    width=160)
        self.tree.column("chat_id", width=150)
        self.tree.column("threads", width=220)
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)

        # Form aggiunta
        frame_form = ttk.LabelFrame(parent, text="Aggiungi / Modifica gruppo")
        frame_form.grid(row=2, column=0, sticky="ew", **pad)

        ttk.Label(frame_form, text="Nome:").grid(row=0, column=0, sticky="w", **pad)
        self.var_g_name = tk.StringVar()
        ttk.Entry(frame_form, textvariable=self.var_g_name, width=22).grid(row=0, column=1, **pad)

        ttk.Label(frame_form, text="Chat ID:").grid(row=0, column=2, sticky="w", **pad)
        self.var_g_chatid = tk.StringVar()
        ttk.Entry(frame_form, textvariable=self.var_g_chatid, width=18).grid(row=0, column=3, **pad)

        ttk.Label(frame_form, text="Thread IDs\n(vuoto = Generale):").grid(row=0, column=4, sticky="w", **pad)
        self.var_g_threads = tk.StringVar()
        ttk.Entry(frame_form, textvariable=self.var_g_threads, width=22).grid(row=0, column=5, **pad)

        # Bottoni gestione
        frame_gbtn = ttk.Frame(parent)
        frame_gbtn.grid(row=3, column=0, sticky="w", **pad)

        ttk.Button(frame_gbtn, text="➕ Aggiungi",  command=self._add_group).pack(side="left", padx=4)
        ttk.Button(frame_gbtn, text="✏️ Aggiorna",  command=self._update_group).pack(side="left", padx=4)
        ttk.Button(frame_gbtn, text="➖ Rimuovi",   command=self._remove_group).pack(side="left", padx=4)
        ttk.Button(frame_gbtn, text="⬆ Carica sel.", command=self._load_selected).pack(side="left", padx=4)

        # Gruppo default
        self.tree.insert("", tk.END, values=("Physia", "-1003589438312", "2"))

    # ── gestione gruppi ──────────────────────────────────────────────────────
    def _add_group(self):
        name    = self.var_g_name.get().strip()
        chat_id = self.var_g_chatid.get().strip()
        threads = self.var_g_threads.get().strip()

        if not name or not chat_id:
            messagebox.showwarning("Attenzione", "Nome e Chat ID sono obbligatori.")
            return

        self.tree.insert("", tk.END, values=(name, chat_id, threads))
        self.var_g_name.set("")
        self.var_g_chatid.set("")
        self.var_g_threads.set("")

    def _remove_group(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Attenzione", "Seleziona un gruppo da rimuovere.")
            return
        self.tree.delete(sel[0])

    def _load_selected(self):
        """Carica i dati della riga selezionata nel form per modificarli."""
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        self.var_g_name.set(vals[0])
        self.var_g_chatid.set(vals[1])
        self.var_g_threads.set(vals[2])

    def _update_group(self):
        """Aggiorna la riga selezionata con i valori nel form."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Attenzione", "Seleziona prima un gruppo dalla lista, poi premi 'Aggiorna'.")
            return
        name    = self.var_g_name.get().strip()
        chat_id = self.var_g_chatid.get().strip()
        threads = self.var_g_threads.get().strip()
        if not name or not chat_id:
            messagebox.showwarning("Attenzione", "Nome e Chat ID sono obbligatori.")
            return
        self.tree.item(sel[0], values=(name, chat_id, threads))

    def _get_groups(self):
        """
        Ritorna lista di dict:
        [{"name": ..., "chat_id": int, "threads": [int, ...] o []}, ...]
        """
        groups = []
        for row in self.tree.get_children():
            vals = self.tree.item(row, "values")
            name    = vals[0]
            chat_id = int(vals[1])
            threads_raw = vals[2].strip()
            if threads_raw:
                threads = [int(t.strip()) for t in threads_raw.split(",") if t.strip()]
            else:
                threads = []   # nessun thread → manda su Generale
            groups.append({"name": name, "chat_id": chat_id, "threads": threads})
        return groups

    # ── helpers ──────────────────────────────────────────────────────────────
    def _get_options(self):
        return [l.strip() for l in self.txt_opzioni.get("1.0", tk.END).splitlines() if l.strip()]

    def _get_weekday(self):
        giorni = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
        return giorni.index(self.var_giorno.get())

    def _toggle_token(self):
        self.entry_token.configure(
            show="" if self.entry_token.cget("show") == "*" else "*"
        )

    def _log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    # ── invio sondaggio ──────────────────────────────────────────────────────
    async def _manda_sondaggio(self):
        bot     = Bot(token=self.var_token.get().strip())
        groups  = self._get_groups()
        options = self._get_options()
        domanda = self.var_domanda.get()

        if not groups:
            self._log("Nessun gruppo configurato!")
            return

        for group in groups:
            chat_id = group["chat_id"]
            threads = group["threads"]
            name    = group["name"]

            # Se non ci sono thread IDs manda una volta senza thread (Generale)
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
                    self._log(f"  ✅ Inviato a '{name}' ({dest})")
                except Exception as e:
                    dest = f"thread {thread_id}" if thread_id else "Generale"
                    self._log(f"  ❌ Errore '{name}' ({dest}): {e}")

    # ── loop scheduling ──────────────────────────────────────────────────────
    async def _loop(self):
        gia_inviato = False
        self._log("Bot avviato. In attesa dello scheduling...")

        while self._running:
            now           = datetime.now()
            target_day    = self._get_weekday()
            target_hour   = int(self.var_ora.get())
            target_minute = int(self.var_minuto.get())

            if (now.weekday() == target_day and
                    now.hour == target_hour and
                    now.minute == target_minute):
                if not gia_inviato:
                    self._log("Orario raggiunto, invio sondaggi...")
                    await self._manda_sondaggio()
                    gia_inviato = True

            # reset il giorno dopo
            if now.weekday() == (target_day + 2) % 7:
                gia_inviato = False

            await asyncio.sleep(30)

        self._log("Bot fermato.")

    def _run_loop(self):
        asyncio.run(self._loop())

    # ── start / stop ─────────────────────────────────────────────────────────
    def _start(self):
        if self._running:
            return
        self._running = True
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.lbl_status.configure(text="🟢 In esecuzione")
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()

    def _stop(self):
        self._running = False
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.lbl_status.configure(text="⚫ Fermo")

    def _send_now(self):
        def _send():
            try:
                asyncio.run(self._manda_sondaggio())
            except Exception as e:
                self._log(f"Errore: {e}")
        threading.Thread(target=_send, daemon=True).start()

    # ── config save / load ───────────────────────────────────────────────────
    def _save_config(self):
        cfg = {
            "token":   self.var_token.get(),
            "giorno":  self.var_giorno.get(),
            "ora":     self.var_ora.get(),
            "minuto":  self.var_minuto.get(),
            "domanda": self.var_domanda.get(),
            "opzioni": self.txt_opzioni.get("1.0", tk.END).strip(),
            "groups":  self._get_groups(),
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        self._log("Config salvata.")

    def _load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)

        self.var_token.set(cfg.get("token", ""))
        self.var_giorno.set(cfg.get("giorno", "Venerdì"))
        self.var_ora.set(cfg.get("ora", "16"))
        self.var_minuto.set(cfg.get("minuto", "52"))
        self.var_domanda.set(cfg.get("domanda", ""))

        if "opzioni" in cfg:
            self.txt_opzioni.delete("1.0", tk.END)
            self.txt_opzioni.insert(tk.END, cfg["opzioni"])

        if "groups" in cfg:
            # svuota e ricarica
            for row in self.tree.get_children():
                self.tree.delete(row)
            for g in cfg["groups"]:
                threads_str = ", ".join(str(t) for t in g.get("threads", []))
                self.tree.insert("", tk.END, values=(g["name"], g["chat_id"], threads_str))


# ── entry point ───────────────────��──────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()