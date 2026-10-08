"""Client minimale per l'API GraphQL di monday.com.

Regole del progetto (vedi CLAUDE.md in questa cartella):
- nessuna scrittura reale finché config.DRY_RUN è True;
- mai hardcodare ID di colonna "a memoria": si risolvono per titolo a runtime,
  perché la struttura delle board (in particolare Timesheet) non è mai stata
  verificata da Claude;
- il token API vive solo in .env, mai nel codice o nei log.
"""
import json
import logging

import requests

import config

API_URL = "https://api.monday.com/v2"
log = logging.getLogger("monday_client")

_column_cache = {}  # board_id -> {column_id: {"title": ..., "type": ...}}


class MondayError(RuntimeError):
    pass


def _request(query, variables=None):
    if not config.MONDAY_API_TOKEN:
        raise MondayError("MONDAY_API_TOKEN non configurato (.env)")
    resp = requests.post(
        API_URL,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": config.MONDAY_API_TOKEN, "API-Version": "2024-10"},
        timeout=20,
    )
    resp.raise_for_status()
    body = resp.json()
    if "errors" in body:
        raise MondayError(json.dumps(body["errors"]))
    return body["data"]


def get_board_columns(board_id):
    if board_id not in _column_cache:
        data = _request(
            "query($id: [ID!]) { boards(ids: $id) { columns { id title type } } }",
            {"id": [board_id]},
        )
        boards = data.get("boards") or []
        columns = boards[0]["columns"] if boards else []
        _column_cache[board_id] = {c["id"]: c for c in columns}
    return _column_cache[board_id]


def find_column_id(board_id, title_candidates, type_filter=None):
    """Trova l'id della prima colonna il cui titolo contiene uno dei candidati
    (case-insensitive). Ritorna None se non trovata, invece di indovinare."""
    columns = get_board_columns(board_id)
    for col_id, col in columns.items():
        if type_filter and col["type"] != type_filter:
            continue
        title_lower = col["title"].strip().lower()
        if any(cand.lower() in title_lower for cand in title_candidates):
            return col_id
    return None


def resolve_timesheet_columns():
    """Mappa {chiave logica: column_id} per la board Timesheet, risolta per
    titolo. Le chiavi non trovate restano None e vengono segnalate: significa
    che la board reale si discosta dalla specifica e va controllata a mano
    (CLAUDE.md §2, riga Timesheet 'NON verificata')."""
    resolved = {}
    for key, candidates in config.TIMESHEET_EXPECTED_COLUMNS.items():
        resolved[key] = find_column_id(config.BOARD_TIMESHEET, candidates)
    missing = [k for k, v in resolved.items() if v is None]
    if missing:
        log.warning("Colonne Timesheet non trovate per titolo: %s", missing)
    return resolved


def get_user_by_email(email):
    data = _request(
        "query($emails: [String]) { users(emails: $emails) { id name email } }",
        {"emails": [email]},
    )
    users = data.get("users") or []
    return users[0] if users else None


def get_items_with_columns(board_id, limit=200):
    """Legge tutti gli item di una board (una sola pagina, limite alto: le
    board di progetto oggi hanno al massimo ~100 item)."""
    data = _request(
        """query($id: [ID!], $limit: Int) {
            boards(ids: $id) {
              items_page(limit: $limit) {
                items {
                  id
                  name
                  group { id title }
                  column_values { id text value }
                }
              }
            }
        }""",
        {"id": [board_id], "limit": limit},
    )
    boards = data.get("boards") or []
    return boards[0]["items_page"]["items"] if boards else []


def _person_ids_from_value(raw_value):
    if not raw_value:
        return set()
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return set()
    persons = parsed.get("personsAndTeams") or []
    return {str(p["id"]) for p in persons if p.get("kind") == "person"}


def get_my_tasks(board_id, user_id, referente_titles=("referente",)):
    """Ritorna gli item della board dove la colonna persona (trovata per
    titolo) contiene user_id."""
    person_col = find_column_id(board_id, referente_titles, type_filter="multiple-person")
    if person_col is None:
        person_col = find_column_id(board_id, referente_titles)
    if person_col is None:
        log.warning("Colonna persona non trovata su board %s (titoli cercati: %s)", board_id, referente_titles)
        return []

    items = get_items_with_columns(board_id)
    mine = []
    for item in items:
        col_values = {cv["id"]: cv for cv in item["column_values"]}
        cv = col_values.get(person_col)
        if cv and str(user_id) in _person_ids_from_value(cv.get("value")):
            mine.append(item)
    return mine


def get_dropdown_labels(board_id, column_id):
    """Ritorna le etichette (in ordine) di una colonna dropdown, lette dal
    settings_str reale della board — mai hardcodate, per non disallinearsi se
    qualcuno modifica le opzioni su monday (vedi trappola etichette esatte)."""
    data = _request(
        "query($id: [ID!]) { boards(ids: $id) { columns { id settings_str } } }",
        {"id": [board_id]},
    )
    boards = data.get("boards") or []
    columns = boards[0]["columns"] if boards else []
    for col in columns:
        if col["id"] == column_id:
            settings = json.loads(col["settings_str"] or "{}")
            labels = settings.get("labels") or []
            # "labels" è una lista di {"id": N, "name": "..."}: ordina per id.
            # monday permette etichette duplicate per testo (es. due "Bedside
            # Tables" con id diversi, non eliminabili via API — vedi trappola
            # etichette dropdown): dedup qui per nome, l'app ne mostra una sola.
            ordered = [l["name"] for l in sorted(labels, key=lambda l: l["id"])]
            seen = set()
            deduped = []
            for name in ordered:
                if name not in seen:
                    seen.add(name)
                    deduped.append(name)
            return deduped
    return []


def _lookup_text(cv):
    """Le colonne lookup (mirror) hanno quasi sempre "text" null: il valore
    reale va letto da "value", un JSON che può essere una stringa o una lista
    (mirror multi-selezione). Ritorna "" se il mirror è vuoto (dato non
    compilato sull'item Concept di origine)."""
    if not cv:
        return ""
    if cv.get("text"):
        return cv["text"]
    raw = cv.get("value")
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return ""
    if isinstance(parsed, list):
        return ", ".join(str(p) for p in parsed)
    return str(parsed) if parsed is not None else ""


def _portfolio_to_concept_ids(board_id):
    """Mappa {portfolio_item_id: concept_item_id}, letta dalla board_relation
    verso Concept (tipizzata esplicitamente: la query generica su board_relation
    restituisce sempre null, stessa trappola già nota per "dependency")."""
    data = _request(
        """query($id: [ID!]) {
            boards(ids: $id) {
              items_page(limit: 200) {
                items {
                  id
                  column_values(types: [board_relation]) {
                    id
                    ... on BoardRelationValue { linked_item_ids }
                  }
                }
              }
            }
        }""",
        {"id": [board_id]},
    )
    boards = data.get("boards") or []
    items = boards[0]["items_page"]["items"] if boards else []
    mapping = {}
    for item in items:
        for cv in item["column_values"]:
            if cv["id"] == config.COL_PORTFOLIO_LINK_CONCEPT:
                ids = cv.get("linked_item_ids") or []
                if ids:
                    mapping[item["id"]] = ids[0]
    return mapping


def get_active_portfolio_projects():
    items = get_items_with_columns(config.BOARD_PORTFOLIO)
    active = [i for i in items if i["group"]["id"] == config.GROUP_PORTFOLIO_ATTIVI]
    portfolio_to_concept = _portfolio_to_concept_ids(config.BOARD_PORTFOLIO)

    concept_ids = [portfolio_to_concept[i["id"]] for i in active if i["id"] in portfolio_to_concept]
    concept_items = {c["id"]: c for c in get_items_with_columns(config.BOARD_CONCEPT)} if concept_ids else {}

    result = []
    for item in active:
        concept_id = portfolio_to_concept.get(item["id"])
        concept = concept_items.get(concept_id) if concept_id else None
        macro, categoria = "", ""
        if concept:
            cvs = {cv["id"]: cv for cv in concept["column_values"]}
            macro = _lookup_text(cvs.get(config.COL_CONCEPT_MACRO_CATEGORIA))
            categoria = _lookup_text(cvs.get(config.COL_CONCEPT_CATEGORIA_PRODOTTO))
        result.append({
            "id": item["id"],
            "name": item["name"],
            "macro_categoria": macro,
            "categoria_prodotto": categoria,
            "is_real": True,  # ha un item_id Portfolio reale: scrivibile via board_relation
        })
    return result


def get_hours_logged_on_date(user_id, data_iso):
    """Somma le 'Ore Lavorate' già registrate su Timesheet per un utente in
    una data, per il pannello 'Impatto in tempo reale' (capacità giornaliera).
    Sola lettura, nessun impatto su DRY_RUN."""
    columns = resolve_timesheet_columns()
    persona_col = columns.get("persona")
    data_col = columns.get("data")
    ore_col = columns.get("ore")
    if not (persona_col and data_col and ore_col):
        return 0.0

    items = get_items_with_columns(config.BOARD_TIMESHEET)
    total = 0.0
    for item in items:
        cvs = {cv["id"]: cv for cv in item["column_values"]}
        persona_cv = cvs.get(persona_col)
        data_cv = cvs.get(data_col)
        ore_cv = cvs.get(ore_col)
        if not (persona_cv and data_cv and ore_cv):
            continue
        if str(user_id) not in _person_ids_from_value(persona_cv.get("value")):
            continue
        if (data_cv.get("text") or "") != data_iso:
            continue
        try:
            total += float(ore_cv.get("text") or 0)
        except (TypeError, ValueError):
            pass
    return total


def get_standard_products():
    """Gamma prodotti standard a listino (config.STANDARD_PRODUCTS): non sono
    item monday reali, quindi hanno un id sintetico "std:<n>" e is_real=False
    — create_timesheet_entry li scrive come testo in Note Tecniche invece che
    come board_relation (vedi config.py per il mapping Macro/Categoria)."""
    return [
        {
            "id": f"std:{i}",
            "name": p["name"],
            "macro_categoria": ", ".join(p["macro_categorie"]),
            "categoria_prodotto": p["categoria_prodotto"],
            "is_real": False,
        }
        for i, p in enumerate(config.STANDARD_PRODUCTS)
    ]


def _timesheet_progetto_links():
    """{item_id: {"nome": display_value, "id": linked_item_id o None}} per il
    collegamento Progetto (board_relation) di ogni item Timesheet. Query
    tipizzata: quella generica su board_relation restituisce sempre null
    (stessa trappola già nota)."""
    columns = resolve_timesheet_columns()
    progetto_col = columns.get("progetto")
    if not progetto_col:
        return {}
    data = _request(
        """query($id: [ID!]) {
            boards(ids: $id) { items_page(limit: 200) { items {
                id
                column_values(types: [board_relation]) {
                  id
                  ... on BoardRelationValue { display_value linked_item_ids }
                }
            } } }
        }""",
        {"id": [config.BOARD_TIMESHEET]},
    )
    boards = data.get("boards") or []
    items = boards[0]["items_page"]["items"] if boards else []
    result = {}
    for item in items:
        for cv in item["column_values"]:
            if cv["id"] == progetto_col:
                ids = cv.get("linked_item_ids") or []
                result[item["id"]] = {"nome": cv.get("display_value") or "", "id": ids[0] if ids else None}
    return result


def get_my_timesheet_entries(user_id):
    """Voci Timesheet dell'utente loggato, per la scheda 'Le mie voci'. Sola
    lettura, nessun impatto su DRY_RUN."""
    columns = resolve_timesheet_columns()
    persona_col, data_col, ore_col, note_col = (
        columns.get("persona"), columns.get("data"), columns.get("ore"), columns.get("note"),
    )
    items = get_items_with_columns(config.BOARD_TIMESHEET)
    progetto_links = _timesheet_progetto_links()

    mine = []
    for item in items:
        cvs = {cv["id"]: cv for cv in item["column_values"]}
        persona_cv = cvs.get(persona_col) if persona_col else None
        if not persona_cv or str(user_id) not in _person_ids_from_value(persona_cv.get("value")):
            continue
        link = progetto_links.get(item["id"], {})
        mine.append({
            "id": item["id"],
            "data": (cvs.get(data_col) or {}).get("text") or "",
            "ore": (cvs.get(ore_col) or {}).get("text") or "",
            "note": (cvs.get(note_col) or {}).get("text") or "",
            "progetto_nome": link.get("nome", ""),
            "progetto_id": link.get("id"),
        })
    mine.sort(key=lambda e: e["data"], reverse=True)
    return mine


def update_timesheet_entry(item_id, data_iso, ore, note, progetto_item_id=None):
    """Modifica una voce Timesheet esistente (data/ore/nota/progetto). La
    verifica che la voce sia ancora nella finestra modificabile va fatta PRIMA
    di chiamare questa funzione (vedi config.EDIT_WINDOW_DAYS in app.py).
    In DRY_RUN (default) non scrive nulla: logga solo il payload."""
    columns = resolve_timesheet_columns()
    column_values = {}
    if columns.get("data"):
        column_values[columns["data"]] = {"date": data_iso}
    if columns.get("ore"):
        column_values[columns["ore"]] = ore
    if columns.get("note"):
        column_values[columns["note"]] = note
    if columns.get("progetto"):
        column_values[columns["progetto"]] = {"item_ids": [int(progetto_item_id)]} if progetto_item_id else {"item_ids": []}

    payload = {"board_id": config.BOARD_TIMESHEET, "item_id": item_id, "column_values": column_values}

    if config.DRY_RUN:
        log.info("[DRY-RUN] Nessuna modifica reale. Payload che verrebbe inviato:\n%s", json.dumps(payload, indent=2, ensure_ascii=False))
        return {"dry_run": True, "payload": payload}

    data = _request(
        """mutation($board: ID!, $item: ID!, $values: JSON!) {
            change_multiple_column_values(board_id: $board, item_id: $item, column_values: $values) { id }
        }""",
        {"board": config.BOARD_TIMESHEET, "item": item_id, "values": json.dumps(column_values)},
    )
    log.info("Timesheet item modificato: %s", data)
    return {"dry_run": False, "item": data["change_multiple_column_values"], "payload": payload}


def create_timesheet_entry(persona_user_id, persona_name, progetto_item_id, progetto_nome,
                            task_categoria, task_nome, data_iso, ore, note):
    """Crea un item nella board Timesheet. Il progetto è un collegamento reale
    (board_relation a Portfolio Progetti) SOLO se progetto_item_id è valorizzato;
    per i prodotti della gamma standard a listino (config.STANDARD_PRODUCTS,
    nessun item monday reale) progetto_item_id è None e il nome viene comunque
    preservato come testo in "Note Tecniche", stesso trattamento dell'attività
    (categoria + voce dal catalogo, config.TASK_CATALOG) che non popola mai
    "Task Collegato" (decisione utente 06.10.2026).
    In DRY_RUN (default) non scrive nulla: logga solo il payload."""
    columns = resolve_timesheet_columns()
    item_name = f"{persona_name} - {data_iso}"
    prefisso = f"[{task_categoria}] {task_nome}"
    if progetto_nome and not progetto_item_id:
        prefisso += f" — Prodotto: {progetto_nome}"
    nota_completa = prefisso + (f" — {note}" if note else "")

    column_values = {}
    if columns.get("data"):
        column_values[columns["data"]] = {"date": data_iso}
    if columns.get("ore"):
        column_values[columns["ore"]] = ore
    if columns.get("note"):
        column_values[columns["note"]] = nota_completa
    if columns.get("persona"):
        column_values[columns["persona"]] = {"personsAndTeams": [{"id": int(persona_user_id), "kind": "person"}]}
    if columns.get("progetto") and progetto_item_id:
        column_values[columns["progetto"]] = {"item_ids": [int(progetto_item_id)]}

    payload = {
        "board_id": config.BOARD_TIMESHEET,
        "item_name": item_name,
        "column_values": column_values,
        "context": {
            "progetto_nome": progetto_nome,
            "task_categoria": task_categoria,
            "task_nome": task_nome,
        },
    }

    if config.DRY_RUN:
        log.info("[DRY-RUN] Nessuna scrittura reale. Payload che verrebbe inviato:\n%s", json.dumps(payload, indent=2, ensure_ascii=False))
        return {"dry_run": True, "payload": payload}

    data = _request(
        """mutation($board: ID!, $name: String!, $values: JSON!) {
            create_item(board_id: $board, item_name: $name, column_values: $values) { id }
        }""",
        {
            "board": config.BOARD_TIMESHEET,
            "name": item_name,
            "values": json.dumps(column_values),
        },
    )
    log.info("Timesheet item creato: %s", data)
    return {"dry_run": False, "item": data["create_item"], "payload": payload}
