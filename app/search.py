from app.es import get_es_instance


async def search_users(query: str):
    """Wyszukuje użytkowników w Elasticsearch"""
    es_client = get_es_instance()
    response = await es_client.search(
        index="users",
        body={
            "query": {
                "prefix": {"username": query},
            }
        },
    )
    return [hit["_source"] for hit in response["hits"]["hits"]]
