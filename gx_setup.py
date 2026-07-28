import great_expectations as gx

context = gx.get_context()

connection_string = "postgresql+psycopg2://postgres:Menara1230?@localhost:5432/Banque_simulee"

data_source = context.data_sources.add_postgres(
    "ma_banque", connection_string=connection_string
)
#print("Connexion à la base configurée avec succès")

data_asset = data_source.add_table_asset(name="clients", table_name="clients")
batch_def = data_asset.add_batch_definition_whole_table("batch_clients")
batch = batch_def.get_batch();
#{print("Connexion à la table clients réussie, aperçu des données :")
#print(batch.head())

suite = context.suites.add(gx.ExpectationSuite(name="regles_clients"))
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToNotBeNull(column="email")
)

#print("Regle cree avec succes !!")

validation_results = batch.validate(suite)
print("Résultat de la validation :\n")
print(validation_results)