"""FastAPI dependencies for dependency injection."""



from stockvaluefinder.db.base import get_db


async def get_cache():
    """Dependency to get cache client (TODO: implement Redis cache).
    
    Yields:
        Cache client instance
    """
    # TODO: Implement Redis cache client
    yield None


__all__ = ["get_db", "get_cache"]
