async def init_indices(es_client):
    await init_user_index(es_client)
    return True


async def create_index_if_not_exists(es_client, index_name, index_body):
    if not await es_client.indices.exists(index=index_name):
        await es_client.indices.create(index=index_name, body=index_body)


async def init_user_index(es_client):
    index_name = "users"
    index_body = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
        "mappings": {
            "properties": {
                "username": {"type": "text"},
            }
        },
    }

    await create_index_if_not_exists(es_client, index_name, index_body)
    return True


async def index_user(es_client, user_id: str, username: str):
    await es_client.index(
        index="users",
        id=user_id,
        body={"id": user_id, "username": username},
    )
