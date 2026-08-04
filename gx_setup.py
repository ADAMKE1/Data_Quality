import great_expectations as gx
from datetime import date

context = gx.get_context()

connection_string = "postgresql+psycopg2://postgres:Menara1230?@localhost:5432/Banque_simulee"

data_source = context.data_sources.add_postgres(
    "ma_banque", connection_string=connection_string
)
#print("Connexion à la base configurée avec succès")

#Partie clients
data_asset_clients = data_source.add_table_asset(name="clients", table_name="clients")
batch_def_clients = data_asset_clients.add_batch_definition_whole_table("batch_clients")
batch = batch_def_clients.get_batch();
#{print("Connexion à la table clients réussie, aperçu des données :")
#print(batch.head())

today_date = date.today().isoformat();
print(today_date)
suite_clients= context.suites.add(gx.ExpectationSuite(name="regles_clients"))

#Exactitude email non nul
suite_clients.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="email", mostly= 0.95))

#Exactitude telephone non nul
suite_clients.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="telephone", mostly= 0.95))

#Cohérence date_naissance inférieur à date actuelle
suite_clients.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="date_naissance", max_value = today_date, mostly= 0.99))

#Exactitude email contenant @
suite_clients.add_expectation(gx.expectations.ExpectColumnValuesToMatchRegex(column="email", regex = ".*@.*", mostly= 0.98))

#Unicité Nbre de doublons
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

# Créer une définition de validation (relie le batch et la suite)
validation_definition_clients = context.validation_definitions.add(
    gx.ValidationDefinition(
        data=batch_def_clients,
        suite=suite_clients,
        name="validation_clients"
    )
)

# Créer un checkpoint (celui qui exécute ET sauvegarde les résultats)
checkpoint_clients = context.checkpoints.add(
    gx.checkpoint.checkpoint.Checkpoint(
        name="checkpoint_clients",
        validation_definitions=[validation_definition_clients]
    )
)

# Lancer le checkpoint (ça valide ET enregistre pour les Data Docs)
checkpoint_result_clients = checkpoint_clients.run()






#Partie Comptes
data_asset_cmpt = data_source.add_table_asset(name = "comptes", table_name= "comptes")
batch_def_cmpt = data_asset_cmpt.add_batch_definition_whole_table("batch_comptes")
batch_cmpt = batch_def_cmpt.get_batch()

suite_cmpt = context.suites.add(gx.ExpectationSuite(name = "regles_comptes"))

#Exactitude solde non négatif
suite_cmpt.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column="solde", min_value = 0, mostly= 0.99))

# Cohérence date_ouverture >= date_creation_compte du client (croise 2 tables -> requête SQL)
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

# Checkpoint comptes
validation_definition_cmpt = context.validation_definitions.add(
    gx.ValidationDefinition(data=batch_def_cmpt, suite=suite_cmpt, name="validation_comptes")
)
checkpoint_cmpt = context.checkpoints.add(
    gx.checkpoint.checkpoint.Checkpoint(name="checkpoint_comptes", validation_definitions=[validation_definition_cmpt])
)
checkpoint_result_cmpt = checkpoint_cmpt.run()





#Partie Transactions
data_asset_trns = data_source.add_table_asset(name = "transactions", table_name= "transactions")
batch_def_trns = data_asset_trns.add_batch_definition_whole_table("batch_transactions")
batch_trns = batch_def_trns.get_batch()

suite_trns = context.suites.add(gx.ExpectationSuite(name= "regles_transactions"))
suite_trns.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(column= "montant", min_value= 0, strict_min= True, mostly= 0.99))

# Montant non aberrant
suite_trns.add_expectation(
    gx.expectations.ExpectColumnValueZScoresToBeLessThan(column="montant", threshold=3, double_sided=True, mostly= 0.99)
)

# Cohérence : transaction sur compte non clôturé
suite_trns.add_expectation(
    gx.expectations.UnexpectedRowsExpectation(
        unexpected_rows_query="""
            SELECT t.transaction_id, t.compte_id, c.statut
            FROM {batch} t
            JOIN comptes c ON t.compte_id = c.compte_id
            WHERE c.statut = 'Clôturé'
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
#Unicité : Nbre de doublons
suite_trns.add_expectation(
    gx.expectations.UnexpectedRowsExpectation(
        unexpected_rows_query="""
            SELECT compte_id, date_transaction, montant, type_operation, COUNT(*)
            FROM {batch}
            GROUP BY compte_id, date_transaction, montant, type_operation
            HAVING COUNT(*) > 1;
        """
    )
)

# Checkpoint transactions
validation_definition_trns = context.validation_definitions.add(
    gx.ValidationDefinition(data=batch_def_trns, suite=suite_trns, name="validation_transactions")
)
checkpoint_trns = context.checkpoints.add(
    gx.checkpoint.checkpoint.Checkpoint(name="checkpoint_transactions", validation_definitions=[validation_definition_trns])
)
checkpoint_result_trns = checkpoint_trns.run()



print("Checkpoint exécuté, succès global :", checkpoint_result_clients.success)
print("Checkpoint exécuté, succès global :", checkpoint_result_cmpt.success)
print("Checkpoint exécuté, succès global :", checkpoint_result_trns.success)

# Régénérer les Data Docs avec ces résultats
context.build_data_docs()
context.open_data_docs()