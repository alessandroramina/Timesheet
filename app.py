import datetime
import logging

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

import config
import monday_client as mc

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("timesheet_app")

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

# Timer attivo per utente: stato tenuto in memoria di processo (si perde se il
# server viene riavviato). Non è un dato monday: serve solo per il cronometro
# stile Toggl lato UI. Il risultato finale, una volta fermato il timer, viene
# comunque scritto su monday.com come ogni altra voce — niente DB separato
# (decisione utente 06.10.2026: "mix" tra timer Toggl-style e integrazione
# diretta con monday, non l'architettura standalone del Piano v1).
ACTIVE_TIMERS = {}  # user_id (str) -> dict


def current_user():
    if "user_id" not in session:
        return None
    return {"id": session["user_id"], "name": session["user_name"], "email": session["user_email"]}


def _load_dashboard_data():
    standard_products = mc.get_standard_products()  # catalogo statico, nessuna chiamata API
    try:
        projects = mc.get_active_portfolio_projects() + standard_products
        macro_opts = mc.get_dropdown_labels(config.BOARD_CONCEPT, config.COL_CONCEPT_MACRO_CATEGORIA)
        categoria_opts = mc.get_dropdown_labels(config.BOARD_CONCEPT, config.COL_CONCEPT_CATEGORIA_PRODOTTO)
        error = None
    except mc.MondayError as exc:
        projects, macro_opts, categoria_opts = standard_products, [], []
        error = f"Errore API monday: {exc}"
    return projects, macro_opts, categoria_opts, error


def _render_dashboard(user, error=None, result=None, prefill=None):
    projects, macro_opts, categoria_opts, dash_error = _load_dashboard_data()
    today = datetime.date.today().isoformat()
    try:
        registrate_oggi = mc.get_hours_logged_on_date(user["id"], today)
    except mc.MondayError:
        registrate_oggi = 0.0
    return render_template(
        "dashboard.html",
        user=user,
        projects=projects,
        macro_categoria_options=macro_opts,
        categoria_prodotto_options=categoria_opts,
        task_catalog=config.TASK_CATALOG,
        today=today,
        dry_run=config.DRY_RUN,
        error=error or dash_error,
        result=result,
        timer=ACTIVE_TIMERS.get(str(user["id"])),
        prefill=prefill,
        daily_capacity=config.DEFAULT_DAILY_CAPACITY_HOURS,
        registrate_oggi=registrate_oggi,
    )


@app.route("/api/capacity")
def api_capacity():
    """Ore già registrate dall'utente in una data, per aggiornare dal vivo il
    pannello 'Impatto in tempo reale' quando si cambia la data del form."""
    user = current_user()
    if not user:
        return jsonify({"error": "not_logged_in"}), 401
    data_iso = request.args.get("data") or datetime.date.today().isoformat()
    try:
        registrate = mc.get_hours_logged_on_date(user["id"], data_iso)
    except mc.MondayError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({
        "data": data_iso,
        "contrattuali": config.DEFAULT_DAILY_CAPACITY_HOURS,
        "registrate": registrate,
    })


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        passphrase = request.form.get("passphrase", "")
        if config.APP_SHARED_PASSPHRASE and passphrase != config.APP_SHARED_PASSPHRASE:
            error = "Passphrase errata."
            return render_template("login.html", error=error, require_passphrase=True)
        try:
            user = mc.get_user_by_email(email)
        except mc.MondayError as exc:
            error = f"Errore API monday: {exc}"
            user = None
        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            return redirect(url_for("dashboard"))
        if not error:
            error = "Email non trovata tra gli utenti monday.com del tuo account."
    return render_template("login.html", error=error, require_passphrase=bool(config.APP_SHARED_PASSPHRASE))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    return _render_dashboard(user)


@app.route("/timer/start", methods=["POST"])
def timer_start():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    uid = str(user["id"])
    categoria = request.form.get("categoria", "")
    task_nome = request.form.get("task_nome", "")

    error = None
    if uid in ACTIVE_TIMERS:
        error = "Hai già un timer in corso: fermalo prima di avviarne un altro."
    elif not categoria or not task_nome:
        error = "Seleziona categoria e attività prima di avviare il timer."
    else:
        ACTIVE_TIMERS[uid] = {
            "start_iso": datetime.datetime.now().isoformat(timespec="seconds"),
            "categoria": categoria,
            "task_nome": task_nome,
            "project_id": request.form.get("project_id") or None,
            "project_name": request.form.get("project_name", ""),
        }

    return _render_dashboard(user, error=error)


@app.route("/timer/stop", methods=["POST"])
def timer_stop():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    uid = str(user["id"])
    timer = ACTIVE_TIMERS.pop(uid, None)

    prefill = None
    if timer:
        start = datetime.datetime.fromisoformat(timer["start_iso"])
        elapsed_hours = (datetime.datetime.now() - start).total_seconds() / 3600
        prefill = {
            "categoria": timer["categoria"],
            "task_nome": timer["task_nome"],
            "project_id": timer["project_id"],
            "project_name": timer["project_name"],
            "ore": max(round(elapsed_hours * 4) / 4, 0.25),  # arrotonda al quarto d'ora
        }

    return _render_dashboard(user, prefill=prefill)


@app.route("/submit", methods=["POST"])
def submit():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    categoria = request.form.get("categoria", "")
    task_nome = request.form.get("task_nome", "")
    project_id = request.form.get("project_id") or None
    project_name = request.form.get("project_name") or ""
    if project_id and project_id.startswith("std:"):
        # Prodotto della gamma standard a listino (config.STANDARD_PRODUCTS):
        # non è un item monday reale, quindi niente board_relation — il nome
        # viene comunque preservato in Note Tecniche (vedi create_timesheet_entry).
        project_id = None
    data_iso = request.form.get("data")
    ore_raw = request.form.get("ore")
    note = request.form.get("note", "")

    errors = []
    if not categoria or not task_nome:
        errors.append("Seleziona una categoria e un'attività.")
    if not data_iso:
        errors.append("Indica una data.")
    elif data_iso > datetime.date.today().isoformat():
        errors.append("La data non può essere futura.")
    try:
        ore = float(ore_raw)
        if not (0 < ore <= 24):
            errors.append("Le ore devono essere comprese tra 0 e 24.")
    except (TypeError, ValueError):
        errors.append("Ore non valide.")
        ore = None

    result = None
    if not errors:
        try:
            result = mc.create_timesheet_entry(
                persona_user_id=user["id"],
                persona_name=user["name"],
                progetto_item_id=project_id,
                progetto_nome=project_name,
                task_categoria=categoria,
                task_nome=task_nome,
                data_iso=data_iso,
                ore=ore,
                note=note,
            )
        except mc.MondayError as exc:
            errors.append(f"Errore API monday: {exc}")

    return _render_dashboard(user, error="; ".join(errors) if errors else None, result=result)


def _is_editable(data_iso):
    """Una voce è modificabile solo entro config.EDIT_WINDOW_DAYS dalla data a
    cui si riferisce (richiesta utente 07.10.2026)."""
    try:
        data = datetime.date.fromisoformat(data_iso)
    except (TypeError, ValueError):
        return False
    return (datetime.date.today() - data).days <= config.EDIT_WINDOW_DAYS


@app.route("/entries")
def entries():
    """Scheda 'Le mie voci': elenco delle proprie voci Timesheet raggruppate
    per giornata, con indicazione di quali sono ancora modificabili."""
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    error = None
    try:
        my_entries = mc.get_my_timesheet_entries(user["id"])
    except mc.MondayError as exc:
        my_entries = []
        error = f"Errore API monday: {exc}"

    groups = []
    current_data, current_list = None, None
    for e in my_entries:
        e["editable"] = _is_editable(e["data"])
        if e["data"] != current_data:
            current_data, current_list = e["data"], []
            groups.append({"data": current_data, "voci": current_list})
        current_list.append(e)

    return render_template("entries.html", user=user, groups=groups, error=error, dry_run=config.DRY_RUN)


@app.route("/entries/<item_id>/edit", methods=["GET", "POST"])
def edit_entry(item_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    my_entries = {e["id"]: e for e in mc.get_my_timesheet_entries(user["id"])}
    entry = my_entries.get(item_id)
    if not entry:
        return redirect(url_for("entries"))
    if not _is_editable(entry["data"]):
        return redirect(url_for("entries"))

    if request.method == "POST":
        project_id = request.form.get("project_id") or None
        project_name = request.form.get("project_name") or ""
        if project_id and project_id.startswith("std:"):
            project_id = None
        data_iso = request.form.get("data")
        ore_raw = request.form.get("ore")
        note = request.form.get("note", "")

        errors = []
        if not _is_editable(entry["data"]):
            errors.append("Questa voce non è più modificabile (oltre 7 giorni dalla data originale).")
        if not data_iso:
            errors.append("Indica una data.")
        elif data_iso > datetime.date.today().isoformat():
            errors.append("La data non può essere futura.")
        try:
            ore = float(ore_raw)
            if not (0 < ore <= 24):
                errors.append("Le ore devono essere comprese tra 0 e 24.")
        except (TypeError, ValueError):
            errors.append("Ore non valide.")
            ore = None

        if not errors:
            try:
                mc.update_timesheet_entry(item_id, data_iso, ore, note, project_id)
            except mc.MondayError as exc:
                errors.append(f"Errore API monday: {exc}")
            if not errors:
                return redirect(url_for("entries"))

        projects, macro_opts, categoria_opts, _ = _load_dashboard_data()
        entry = {**entry, "data": data_iso, "ore": ore_raw, "note": note,
                 "progetto_id": project_id, "progetto_nome": project_name}
        return render_template(
            "edit_entry.html", user=user, entry=entry, projects=projects,
            macro_categoria_options=macro_opts, categoria_prodotto_options=categoria_opts,
            today=datetime.date.today().isoformat(), dry_run=config.DRY_RUN,
            error="; ".join(errors),
        )

    projects, macro_opts, categoria_opts, dash_error = _load_dashboard_data()
    return render_template(
        "edit_entry.html", user=user, entry=entry, projects=projects,
        macro_categoria_options=macro_opts, categoria_prodotto_options=categoria_opts,
        today=datetime.date.today().isoformat(), dry_run=config.DRY_RUN, error=dash_error,
    )


if __name__ == "__main__":
    # host 0.0.0.0: raggiungibile da altri PC sulla stessa rete Lago (richiesta utente).
    # Non esporre su reti non fidate: nessuna autenticazione con password.
    app.run(host="0.0.0.0", port=5000, debug=config.DRY_RUN)
