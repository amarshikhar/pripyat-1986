from azure.cosmos import CosmosClient
import json
import os

conn = os.environ['COSMOS_CONNECTION_STRING']
client = CosmosClient.from_connection_string(conn)
container = client.get_database_client('pripyat-db').get_container_client('insag7')

with open('insag7_data.json') as f:
    docs = json.load(f)
for doc in docs:
    container.upsert_item(doc)
    print(f"Uploaded: {doc['title']}")
print('Done!')
