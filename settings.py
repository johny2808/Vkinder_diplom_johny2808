# DB options

driver = "postgresql"
username = "postgres"
password = "postgres"
host = "localhost"
port = "5432"
database = "VKinder"
encoding = "utf-8"
dsn = f"{driver}://{username}:{password}@{host}:{port}/{database}"

drop_db = False  # Drop DB?  (True or False)
