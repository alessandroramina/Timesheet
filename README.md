# Timesheet — prototipo

App Flask minimale per la consuntivazione ore, pensata per il workspace monday.com
"UT test" (vedi `CLAUDE.md` per il contesto completo e le regole operative).

Stato: **prototipo iniziale**, mai testato contro i dati reali (il token monday
di questa macchina non era attivo durante lo sviluppo — vedi sezione "Prima del
primo utilizzo reale").

## Setup

```bash
cd MONDAY/APP
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # poi compila MONDAY_API_TOKEN e FLASK_SECRET_KEY
python app.py
```

L'app parte in **DRY-RUN** (`.env` → `DRY_RUN=true`): le voci di timesheet
vengono solo loggate in console, nessuna scrittura reale su monday.com.
Passa a `DRY_RUN=false` solo dopo aver verificato lo schema reale (vedi sotto).

## Deploy pubblico (Render, collegato a questo repo GitHub)

Per avere un link stabile raggiungibile anche da fuori la rete Lago, senza
tenere un PC sempre acceso:

1. Crea un account su [render.com](https://render.com) (gratuito per un
   prototipo) e collega il repo GitHub `alessandroramina/Timesheet`.
2. Nuovo **Web Service** da quel repo. Render rileva automaticamente il
   `Procfile` incluso (`gunicorn app:app`); se chiede la root directory,
   indica `APP/Timesheet`.
3. Imposta le variabili d'ambiente nel pannello Render (mai nel codice):
   `MONDAY_API_TOKEN`, `FLASK_SECRET_KEY`, `DRY_RUN` e soprattutto
   **`APP_SHARED_PASSPHRASE`** — obbligatoria qui, perché l'app sarà
   raggiungibile da chiunque su internet: senza, basterebbe conoscere
   un'email @lago.it valida per accedere come quella persona (il login non
   ha altra password). Scegli una passphrase e comunicala solo a chi deve
   usare l'app.
4. Ogni push su `main` ridistribuisce automaticamente la nuova versione.
5. Lascia `DRY_RUN=true` finché lo schema reale della board Timesheet non è
   stato verificato (vedi sotto) — anche in produzione.

## Accesso da altri PC sulla rete Lago

L'app ascolta su `0.0.0.0:5000`, quindi è raggiungibile da qualunque PC sulla
stessa rete aziendale, non solo da questo. Per condividere il link:

1. Trova l'IP di questo PC sulla rete Lago: `ipconfig` → "Indirizzo IPv4".
2. Comunica ai colleghi: `http://<quel-IP>:5000`
3. Ognuno effettua il login con la **propria** email monday.com (nessuna
   password: è un prototipo interno, non esporlo fuori dalla rete aziendale).
4. Se il firewall di Windows blocca la connessione, va autorizzata una regola
   in ingresso per la porta 5000 (o Python) sulla rete privata.

Limite noto: il link cambia se questo PC cambia IP (es. riconnessione wifi) e
l'app è raggiungibile solo quando questo PC è acceso con `python app.py` attivo.

## Prima del primo utilizzo reale

1. Riattiva/verifica il token monday in `.env`.
2. Esegui `python scripts/inspect_timesheet_schema.py`: stampa le colonne reali
   della board Timesheet e il mapping che l'app è riuscita a risolvere per
   titolo. Se qualche chiave risulta "NON TROVATA", la board Timesheet si
   discosta dalla specifica IE_TAN e va rivista (manualmente, o aggiornando
   `config.TIMESHEET_EXPECTED_COLUMNS`).
3. Testa in DRY-RUN con un tuo utente di prova, controllando il payload
   loggato prima di passare a `DRY_RUN=false`.

## Decisioni di design prese (vedi CLAUDE.md §5.3 per le alternative scartate)

- **Identità**: login per email monday.com. Su rete interna fidata nessuna
  password aggiuntiva è richiesta; se `APP_SHARED_PASSPHRASE` è valorizzata
  (obbligatorio per il deploy pubblico, vedi sopra) va digitata anche quella.
  Non è comunque un'autenticazione robusta: chiunque conosca sia un'email
  @lago.it sia la passphrase condivisa accede come quella persona.
- **"Progetti/task miei"**: task assegnati nella colonna Referente/persona di
  Project Plan Standard e dei sotto-elementi Concept.
- **Collegamento Progetto**: dropdown separato sui progetti attivi di
  Portfolio Progetti, perché oggi non esiste un collegamento diretto
  task → progetto in Project Plan Standard (board unica condivisa, non ancora
  duplicata per progetto).
- **Scrittura su Effort Effettivo**: non implementata in questa prima
  versione — l'app crea solo l'item in Timesheet. Il roll-up (opzione (a) del
  CLAUDE.md: mirror a somma via board_relation) va aggiunto dopo aver
  verificato la board Timesheet reale.
- **Validazione**: ore tra 0 e 24, data non futura.

## Struttura

```
app.py                 # route Flask (login, dashboard, submit)
monday_client.py       # wrapper GraphQL, risoluzione colonne per titolo, dry-run
config.py              # ID board/gruppi, flag DRY_RUN, mapping colonne attese
templates/, static/    # UI semplice, nessun framework JS
scripts/inspect_timesheet_schema.py  # verifica schema reale (sola lettura)
```
