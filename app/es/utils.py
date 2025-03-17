import asyncio


async def wait_for_elasticsearch(es_client, timeout: int = 60):
    for _ in range(timeout):
        try:
            if await es_client.ping():
                return True
        except Exception:
            pass
        await asyncio.sleep(1)
    return False
