import great_expectations as gx
from datetime import date
 
context = gx.get_context(mode="file", project_root_dir="./gx_project")
 
connection_string = "postgresql+psycopg2://postgres:Menara1230?@localhost:5432/Banque_simulee"
 
# --- Data source (récupère si existe, sinon crée) ---
if "ma_banque" in context.data_sources.all():
    data_source = context.data_sources.get("ma_banque")
else:
    data_source = context.data_sources.add_postgres(
        "ma_banque", connection_string=connection_string
    )
 
today_date = date.today().isoformat()
print(today_date)
 
 
# ============ TABLE CLIENTS ============
 
try:
    data_asset_clients = data_source.get_asset("clients")
except LookupError:
    data_asset_clients = data_source.add_table_asset(name="clients", table_name="clients")
 
try:
    batch_def_clients = data_asset_clients.get_batch_definition("batch_clients")
except LookupError:
    batch_def_clients = data_asset_clients.add_batch_definition_whole_table("batch_clients")
 
batch = batch_def_clients.get_batch()
 
try:
    suite_clients = context.suites.get(name="regles_clients")
    suite_clients.expectations = []
except gx.exceptions.DataContextError:
    suite_clients = context.suites.add(gx.ExpectationSuite(name="regles_clients"))
 
# Complétude email
suite_clients.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="email", mostly=0.95))
 
# Complétude téléphone
suite_clients.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="telephone", mostly=0.95))
 
# Exactitude date_naissance <= aujourd'hui
suite_clients.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="date_naissance", max_value=today_date, mostly=0.99))
 
# Exactitude email contient @
suite_clients.add_expectation(gx.expectations.ExpectColumnValuesToMatchRegex(column="email", regex=".*@.*", mostly=0.98))
 
# Unicité : doublons
suite_clients.add_expectation(
    gx.expectations.UnexpectedRowsExpectation(
        unexpected_rows_query="""
            SELECT nom, prenom, date_naissance, COUNT(*) as nb
            FROM {batch}
            GROUP BY nom, prenom, date_naissance
            HAVING COUNT(*) > 1
        """
    )
)
 
try:
    validation_definition_clients = context.validation_definitions.get(name="validation_clients")
except gx.exceptions.DataContextError:
    validation_definition_clients = context.validation_definitions.add(
        gx.ValidationDefinition(data=batch_def_clients, suite=suite_clients, name="validation_clients")
    )
 
try:
    checkpoint_clients = context.checkpoints.get(name="checkpoint_clients")
except gx.exceptions.DataContextError:
    checkpoint_clients = context.checkpoints.add(
        gx.checkpoint.checkpoint.Checkpoint(name="checkpoint_clients", validation_definitions=[validation_definition_clients])
    )
 
checkpoint_result_clients = checkpoint_clients.run()
 
 
# ============ TABLE COMPTES ============
 
try:
    data_asset_cmpt = data_source.get_asset("comptes")
except LookupError:
    data_asset_cmpt = data_source.add_table_asset(name="comptes", table_name="comptes")
 
try:
    batch_def_cmpt = data_asset_cmpt.get_batch_definition("batch_comptes")
except LookupError:
    batch_def_cmpt = data_asset_cmpt.add_batch_definition_whole_table("batch_comptes")
 
batch_cmpt = batch_def_cmpt.get_batch()
 
try:
    suite_cmpt = context.suites.get(name="regles_comptes")
    suite_cmpt.expectations = []
except gx.exceptions.DataContextError:
    suite_cmpt = context.suites.add(gx.ExpectationSuite(name="regles_comptes"))
 
# Exactitude solde non négatif
suite_cmpt.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="solde", min_value=0, mostly=0.99))
 
# Cohérence date_ouverture >= date_creation_compte du client
suite_cmpt.add_expectation(
    gx.expectations.UnexpectedRowsExpectation(
        unexpected_rows_query="""
            SELECT co.compte_id, co.date_ouverture, cl.date_creation_compte
            FROM {batch} co
            JOIN clients cl ON co.client_id = cl.client_id
            WHERE co.date_ouverture < cl.date_creation_compte
        """
    )
)
 
try:
    validation_definition_cmpt = context.validation_definitions.get(name="validation_comptes")
except gx.exceptions.DataContextError:
    validation_definition_cmpt = context.validation_definitions.add(
        gx.ValidationDefinition(data=batch_def_cmpt, suite=suite_cmpt, name="validation_comptes")
    )
 
try:
    checkpoint_cmpt = context.checkpoints.get(name="checkpoint_comptes")
except gx.exceptions.DataContextError:
    checkpoint_cmpt = context.checkpoints.add(
        gx.checkpoint.checkpoint.Checkpoint(name="checkpoint_comptes", validation_definitions=[validation_definition_cmpt])
    )
 
checkpoint_result_cmpt = checkpoint_cmpt.run()
 
 
# ============ TABLE TRANSACTIONS ============
 
try:
    data_asset_trns = data_source.get_asset("transactions")
except LookupError:
    data_asset_trns = data_source.add_table_asset(name="transactions", table_name="transactions")
 
try:
    batch_def_trns = data_asset_trns.get_batch_definition("batch_transactions")
except LookupError:
    batch_def_trns = data_asset_trns.add_batch_definition_whole_table("batch_transactions")
 
batch_trns = batch_def_trns.get_batch()
 
try:
    suite_trns = context.suites.get(name="regles_transactions")
    suite_trns.expectations = []
except gx.exceptions.DataContextError:
    suite_trns = context.suites.add(gx.ExpectationSuite(name="regles_transactions"))
 
# Exactitude montant strictement positif
suite_trns.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="montant", min_value=0, strict_min=True, mostly=0.99))
 
# Exactitude montant non aberrant (3 sigmas)
suite_trns.add_expectation(
    gx.expectations.ExpectColumnValueZScoresToBeLessThan(column="montant", threshold=3, double_sided=True, mostly=0.99)
)
 
# Cohérence : transaction postérieure à la clôture du compte
suite_trns.add_expectation(
    gx.expectations.UnexpectedRowsExpectation(
        unexpected_rows_query="""
            SELECT t.transaction_id, t.date_transaction, c.date_cloture
            FROM {batch} t
            JOIN comptes c ON t.compte_id = c.compte_id
            WHERE c.date_cloture IS NOT NULL 
              AND t.date_transaction > c.date_cloture
        """
    )
)
 
# Fraîcheur : transaction >= ouverture du compte
suite_trns.add_expectation(
    gx.expectations.UnexpectedRowsExpectation(
        unexpected_rows_query="""
            SELECT t.transaction_id, t.date_transaction, c.date_ouverture
            FROM {batch} t
            JOIN comptes c ON t.compte_id = c.compte_id
            WHERE t.date_transaction < c.date_ouverture
        """
    )
)
 
# Unicité : doublons
suite_trns.add_expectation(
    gx.expectations.UnexpectedRowsExpectation(
        unexpected_rows_query="""
            SELECT compte_id, date_transaction, montant, type_operation, COUNT(*)
            FROM {batch}
            GROUP BY compte_id, date_transaction, montant, type_operation
            HAVING COUNT(*) > 1
        """
    )
)
 
try:
    validation_definition_trns = context.validation_definitions.get(name="validation_transactions")
except gx.exceptions.DataContextError:
    validation_definition_trns = context.validation_definitions.add(
        gx.ValidationDefinition(data=batch_def_trns, suite=suite_trns, name="validation_transactions")
    )
 
try:
    checkpoint_trns = context.checkpoints.get(name="checkpoint_transactions")
except gx.exceptions.DataContextError:
    checkpoint_trns = context.checkpoints.add(
        gx.checkpoint.checkpoint.Checkpoint(name="checkpoint_transactions", validation_definitions=[validation_definition_trns])
    )
 
checkpoint_result_trns = checkpoint_trns.run()
 
 
# ============ RÉSULTATS ET DATA DOCS ============
 
print("Checkpoint exécuté, succès global (clients) :", checkpoint_result_clients.success)
print("Checkpoint exécuté, succès global (comptes) :", checkpoint_result_cmpt.success)
print("Checkpoint exécuté, succès global (transactions) :", checkpoint_result_trns.success)
 
context.build_data_docs()
context.open_data_docs()