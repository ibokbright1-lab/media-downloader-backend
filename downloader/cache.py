# downloader/cache.py

cache_store = {}

def set_cache(key, value):
    cache_store[key] = value

def get_cache(key):
    return cache_store.get(key)

def delete_cache(key):
    if key in cache_store:
        del cache_store[key]