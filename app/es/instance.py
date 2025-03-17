from elasticsearch import AsyncElasticsearch

ES_HOST = "http://elasticsearch:9200"

es = AsyncElasticsearch(hosts=[ES_HOST])


def get_es_instance() -> AsyncElasticsearch:
    return es
