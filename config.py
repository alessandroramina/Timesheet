import os
from dotenv import load_dotenv

load_dotenv()

MONDAY_API_TOKEN = os.environ.get("MONDAY_API_TOKEN", "")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() != "false"

# Una voce di Timesheet è modificabile solo entro questo numero di giorni
# dalla data a cui si riferisce; oltre, resta bloccata (richiesta utente
# 07.10.2026, scheda "Le mie voci").
EDIT_WINDOW_DAYS = 7

# Capacità giornaliera standard per il pannello "Impatto in tempo reale"
# (ispirato alle schermate mockup Impresoft). Nessun dato di "ore contrattuali"
# per utente esiste oggi su monday: 8h è l'assunzione di default per un
# full-time, usata finché non serve differenziarla per persona.
DEFAULT_DAILY_CAPACITY_HOURS = 8

WORKSPACE_ID = 7639398  # "UT test" — unico workspace autorizzato (vedi CLAUDE.md §0.4)

BOARD_CONCEPT = 5104232424
BOARD_CONCEPT_SUBITEMS = 5104232439
BOARD_PORTFOLIO = 5104295696
BOARD_PROJECT_PLAN = 5104295692
BOARD_TIMESHEET = 5104668132

GROUP_PORTFOLIO_ATTIVI = "group_mm78c19v"  # Portfolio Progetti > "Progetti Attivi"

# Collegamento Portfolio -> Concept (board_relation, scrivibile). Usato per
# leggere Macro/Categoria direttamente dal Concept collegato invece che dal
# mirror lookup_mm7atnnv/lookup_mm7a1ev2 su Portfolio: il mirror può restare
# non aggiornato per un ritardo di sincronizzazione lato monday (verificato
# 07.10.2026: 19 item su 20 avevano il mirror vuoto pur avendo Macro/Categoria
# già compilate sul Concept sorgente) — leggere dalla fonte evita il problema.
COL_PORTFOLIO_LINK_CONCEPT = "board_relation_mm7amzrr"

# Mirror (lookup) da Concept su Portfolio Progetti — non più usati per leggere
# Macro/Categoria (vedi sopra), tenuti solo per riferimento.
COL_PORTFOLIO_MACRO_CATEGORIA = "lookup_mm7atnnv"
COL_PORTFOLIO_CATEGORIA_PRODOTTO = "lookup_mm7a1ev2"

# Colonne dropdown originali su Concept, da cui si leggono le etichette reali
# (mai hardcodate: vedi monday_client.get_dropdown_labels) e il valore Macro/
# Categoria effettivo di ogni item.
COL_CONCEPT_MACRO_CATEGORIA = "dropdown_mm77gq3m"
COL_CONCEPT_CATEGORIA_PRODOTTO = "dropdown_mm7727xq"

# Catalogo attività per la consuntivazione ore, allineato al foglio "Attività"
# di Storico e master/Master2.xlsx (fonte autorevole più recente, non monday.com;
# sostituisce la versione precedente basata su Master.xlsx). Ogni voce giustifica
# le ore di una giornata; viene salvata come testo in "Note Tecniche" (nessuna
# board_relation reale, decisione utente 06.10.2026: non sono item monday
# esistenti). Duplicati tra colonne del foglio originale ("Contatto / Pass.
# fornitori", "Costificazione", "Test interni", presenti sia in SVILUPPO che
# INDUSTRIALIZZAZIONE) assegnati alla prima categoria in cui comparivano.
TASK_CATALOG = {
    "SVILUPPO": [
        "Ricerca R&D", "Modellazione 3D / 2D", "Specifiche Svil. - Ind.", "Risk Analysis",
        "Contatto / Pass. fornitori", "Realizz. / Mont. prototipi", "Costificazione",
        "Test interni", "Riunione R&D",
    ],
    "INDUSTRIALIZZAZIONE": [
        "Specifiche / Regole costr. / Gamma", "Test esterni", "Doc tecnica (I.M. e S.P.)",
        "Go_NoGo", "Check industrializzati / Passaggi",
    ],
    "SPECIALI": ["Sviluppo Fattibilità", "Sviluppo Speciali"],
    "ALTRO": [
        "Service Back-Office", "Service Produzione", "Service Postvendita", "Service Acquisti",
        "Service Comm. / Prog. / Arch.", "Service diretto cliente", "Service fornitore",
        "Service Design", "Service Qualità", "Service altri uffici",
        "Controllo Ordini proforma/conferma", "Ordine e pulizia", "Corso di formazione",
        "Riunioni", "TimeSheet", "Permesso / Ferie", "Malattia",
    ],
    "COMPLIANCE": [
        "Contract e Discover", "Export e Internazionalizzazione", "Prodotto", "Services",
        "Sostenibilità",
    ],
    "CODIFICA": [
        "Codifica Nuovi Prodotti", "Codifica Speciali", "Creazione / Svil. Listino Vendita",
        "Prototipi", "Manutenzione", "Sviluppo Fabbrica", "Attività per Retail",
    ],
    "METRON": [
        "Manutenzione Metron", "Speciali", "Sviluppo Prodotto", "PYH", "Altro",
    ],
}

# Gamma prodotti standard a listino (fornita dall'utente 06.10.2026), per
# arricchire "Nome Prodotto" oltre ai soli progetti attivi di Portfolio
# Progetti. Non sono item monday reali: non hanno un id da collegare via
# board_relation, quindi in create_timesheet_entry il nome viene scritto come
# testo in "Note Tecniche" invece che come collegamento (stesso trattamento
# del catalogo attività). Macro Categoria e Categoria Prodotto qui usano
# ESATTAMENTE le etichette del dropdown Concept (mai modificate, come
# richiesto): "macro_categorie" è una lista perché alcuni prodotti potrebbero
# coprire più ambienti. Mapping non ovvi, da rivedere se non corretti:
# "Pensili-Boiserie" -> separato in "Hanging Units" / "Boiserie"; "Punto
# Storage" -> "Shelves" (nessuna etichetta più vicina); "Mensole" -> "Shelves";
# "Consolle" -> "Consoles". "Hall" eliminata come macro categoria per questo
# catalogo (07.10.2026, caso ambiguo): rimossa anche dai Concept item reali
# che la avevano selezionata (vedi monday_client / verifica eseguita).
STANDARD_PRODUCTS = [
    {"name": n, "macro_categorie": ["Living room"], "categoria_prodotto": "Wall Units"}
    for n in [
        "36e8 Wall Units", "36e8 Wall units With display cabinet", "30MM Wall units",
        "Air Wall Units", "Lagolinea Wall Units", "Materia Wall Units",
        "Materia Aqua Wall Units", "N.O.W. Wall Units",
    ]
] + [
    {"name": n, "macro_categorie": ["Living room"], "categoria_prodotto": "TV Units"}
    for n in [
        "36e8 TV Units", "36e8 TV units With display cabinet", "36e8 Aqua TV Units",
        "36e8 Glass TV Units", "Air TV Units", "Materia TV Units", "Materia Aqua TV Units",
        "N.O.W. TV Units",
    ]
] + [
    {"name": n, "macro_categorie": ["Living room"], "categoria_prodotto": "Sofa and Armchairs"}
    for n in [
        "Air Sofa", "Air Soft Sofa", "Air Soft Free Sofa", "Altana Sofa", "Biza Sofa",
        "Happening Sofa", "Hero Sofa", "Londy Sofa", "N.O.W. Sofa", "Sand Sofa",
        "Air Armchair", "Air Soft Armchair", "Altana Armchair", "Biza Armchair",
        "Chama Armchair - Chama Sofa", "Colombina Armchair", "Happening Armchair",
        "Huggy Armchair", "Mezz'Aria Armchair", "Nacho Armchair", "Zeppelin Armchair",
    ]
] + [
    {"name": n, "macro_categorie": ["Living room"], "categoria_prodotto": "Hanging Units"}
    for n in ["36e8 hanging Units", "N.O.W. hanging Units", "Materia Hanging Units"]
] + [
    {"name": "Punto Storage", "macro_categorie": ["Living room"], "categoria_prodotto": "Shelves"},
    {"name": "Boiserie", "macro_categorie": ["Living room"], "categoria_prodotto": "Boiserie"},
] + [
    {"name": n, "macro_categorie": ["Living room"], "categoria_prodotto": "Shelves"}
    for n in ["Air_Shelf", "Cartesio_Shelf", "Dub_Shelf", "Glasserie_Shelf"]
] + [
    {"name": n, "macro_categorie": ["Living room", "Study"], "categoria_prodotto": "Bookshelves"}
    for n in [
        "Air_bookshelf", "Lagolinea bookshelves", "Pentagram bookshelves", "30MM bookshelves",
        "30MM weightless bookshelves",
    ]
] + [
    {"name": n, "macro_categorie": ["Living room"], "categoria_prodotto": "Consoles"}
    for n in ["36e8 Consolle", "36e8 Glass Consolle", "Materia Consolle", "Fine Consolle",
              "Deba Consolle", "Air Consolle"]
] + [
    {"name": n, "macro_categorie": ["Living room"], "categoria_prodotto": "Mirrors"}
    for n in ["36e8 Mirror", "Pleasure Mirror", "Glass Mirror", "Punto_Mirror", "Fuze Mirror",
              "Kibi Mirror", "Melty Mirror", "Era Mirror"]
] + [
    {"name": n, "macro_categorie": ["Living room"], "categoria_prodotto": "Coffee Tables"}
    for n in [
        "36e8 Coffee Table", "Air Coffee Table", "Air Round Coffee Table",
        "Air Soft Coffee Table", "Alberoni Coffee Table", "Blendie Coffee Table",
        "Correr Slim Coffee Table", "Layers Coffee Table", "Lean Coffee Table",
        "Londy Coffee Table", "Materia Coffee Table", "Pleasure Coffee Table",
        "Snip Coffee Table", "Tell Coffee Table", "Upglass Coffee Table", "Yama Coffee Table",
    ]
] + [
    {"name": n, "macro_categorie": ["Dining room"], "categoria_prodotto": "Sideboard"}
    for n in [
        "36e8 Sideboard", "36e8 Aqua Sideboard", "36e8 Glass Sideboard", "Air Sideboard",
        "Materia Sideboard", "Materia Aqua Sideboard", "N.O.W. Sideboard", "Plenum Sideboard",
    ]
] + [
    {"name": n, "macro_categorie": ["Dining room"], "categoria_prodotto": "Lights and Accessories"}
    for n in ["Glee Lamp", "Chic Lamp", "Y Centerpiece"]
] + [
    {"name": n, "macro_categorie": ["Dining room"], "categoria_prodotto": "Tables"}
    for n in [
        "Air Table", "Air Extendable Table", "Air Slim Table", "Air Soft Table",
        "Alberoni Table", "Chapeau Table", "Correr Table", "Correr Slim Table", "Hoa Table",
        "Janeiro Table", "Loto Table", "Meet Table", "P&J Table", "Stratum Table", "U Table",
        "Wadi Table",
    ]
] + [
    # Il foglio raggruppa Chairs / Stools / Benches sotto un'unica schermata:
    # mantenuto come un'unica categoria "Chairs and Stools" (etichetta esatta
    # monday), pur comprendendo anche le panche, su indicazione dell'utente.
    {"name": n, "macro_categorie": ["Dining room"], "categoria_prodotto": "Chairs and Stools"}
    for n in [
        "Amida chair", "Aqualta chair", "Colombina chair", "Colombina dining chair",
        "Dangla chair", "Ermes chair", "Mezz'aria chair", "Nacho chair", "Pletra chair",
        "Novice chair", "Ruffle chair", "Steps chair", "Woop chair", "Zeppelin chair",
        "Beat stool", "Colombina stool", "Steps stool",
        "Air Bench", "Softswing - Softbench",
    ]
] + [
    {"name": n, "macro_categorie": ["Study"], "categoria_prodotto": "Desk - Home Office"}
    for n in [
        "Air Desk", "Lagolinea Desk", "Livre Desk", "Bookshelves with desks",
        "Morgana Drawer", "36e8 Desk", "36e8 Drawer",
    ]
] + [
    {"name": n, "macro_categorie": ["Bedroom"], "categoria_prodotto": "Beds"}
    for n in [
        "Air Bed", "Bed-in Bed", "Bounty Bed", "Colletto Bed", "Fluttua Bed",
        "Roundy Air Bed", "Roundy Fluttua Bed", "Steel Bed", "Vele Bed", "Mattresses",
    ]
] + [
    {"name": n, "macro_categorie": ["Bedroom"], "categoria_prodotto": "Bedside Tables"}
    for n in [
        "36e8 Bedside Tables", "36e8 Aqua Bedside Tables", "Air Bedside Tables",
        "Air Round Bedside Tables", "Class Bedside Tables", "Hom Bedside Tables",
        "Livre Bedside Tables", "Materia Bedside Tables", "Materia Aqua Bedside Tables",
        "Morgana Bedside Tables", "Snip Bedside Table", "Upglass Bedside Tables",
    ]
] + [
    {"name": n, "macro_categorie": ["Bedroom"], "categoria_prodotto": "Dressers"}
    for n in [
        "36e8 Dressers", "36e8 Aqua Dressers", "36e8 Glass Dressers", "Air Dressers",
        "Materia Dressers", "Materia Aqua Dressers", "Morgana Dressers",
    ]
] + [
    {"name": n, "macro_categorie": ["Bedroom"], "categoria_prodotto": "Wardrobes"}
    for n in [
        "N.O.W. Wardrobes", "N.O.W. Quick Wardrobes", "N.O.W. Quick Sliding Wardrobes",
        "N.O.W. Sliding Wardrobes", "Groove Wardrobes", "Cut Wardrobes", "Key Wardrobes",
        "Flapp Wardrobes", "Smart Wardrobes", "Et Voilà Wardrobes",
    ]
] + [
    {"name": n, "macro_categorie": ["Bedroom"], "categoria_prodotto": "Walk-in Closets"}
    for n in ["Air", "Outfit Walk-in Closets", "Vista Walk-in Closets"]
] + [
    # Macro Kitchen: uso le etichette specifiche "Kitchen - ..." del dropdown
    # Concept (diverse da "Wall Units" generico già usato per Living room),
    # non quelle scritte genericamente nella richiesta.
    {"name": n, "macro_categorie": ["Kitchen"], "categoria_prodotto": "Kitchen - Base Unit"}
    for n in ["Base Unit 36e8 CUT", "Base unit 36e8", "Base unit features"]
] + [
    {"name": n, "macro_categorie": ["Kitchen"], "categoria_prodotto": "Kitchen - Wall Units"}
    for n in ["36e8 CUT Wall Units", "36e8 Wall Units", "N.O.W. Wall Units"]
] + [
    {"name": n, "macro_categorie": ["Kitchen"], "categoria_prodotto": "Kitchen - Tall Units"}
    for n in ["Tall Unit 36e8 CUT", "Tall unit 36e8", "N.O.W. Tall unit", "Tall unit features"]
] + [
    {"name": n, "macro_categorie": ["Kitchen"], "categoria_prodotto": "Kitchen - Tops"}
    for n in ["Breakfast bars", "Peninsulas", "Top"]
] + [
    # ATTENZIONE: nessuna etichetta "Bathroom ..." esiste nel dropdown Categoria
    # Prodotto di Concept (solo le "Kitchen - ..." sono specifiche per reparto;
    # per Bathroom non c'è un equivalente "Bathroom - Base Unit"). Non ho
    # inventato una nuova etichetta dropdown (richiesta esplicita: non
    # modificare le categorie prodotto) — questi prodotti sono quindi tracciati
    # col testo letterale "Bathroom Base Units", che però non comparirà mai
    # filtrando per Categoria Prodotto (nessuna opzione corrisponde), solo con
    # "Tutte". Da chiarire con l'utente se serve una soluzione diversa.
    {"name": n, "macro_categorie": ["Bathroom"], "categoria_prodotto": "Bathroom Base Units"}
    for n in ["36e8 CUT bathroom base unit", "36e8 bathroom base unit", "Bathroom base unit feature"]
]

# Titoli colonna attesi nella board Timesheet, secondo la specifica IE_TAN cap.5.
# La struttura reale NON è mai stata verificata (CLAUDE.md §2): l'app li risolve
# per titolo a runtime (vedi monday_client.resolve_timesheet_columns) invece di
# usare ID hardcoded, così si adatta da sola e segnala cosa manca.
TIMESHEET_EXPECTED_COLUMNS = {
    "persona": ["persona", "person", "utente"],
    "progetto": ["progetto"],
    "task": ["task collegato", "task", "attività"],
    "data": ["data"],
    "ore": ["ore lavorate", "ore"],
    "note": ["note tecniche", "note"],
}
