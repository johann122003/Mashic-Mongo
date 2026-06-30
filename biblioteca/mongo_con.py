from pymongo import MongoClient

# Conexión real a tu base de datos
client = MongoClient('mongodb+srv://admin:UDLA@clusterudla01.ifo6ppk.mongodb.net/')
db = client['MashicDB'] # Tu base de datos