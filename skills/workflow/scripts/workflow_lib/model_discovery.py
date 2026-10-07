"""Bounded advisory discovery cache. No provider calls or website enumeration."""
import hashlib
import json
from copy import deepcopy


def discovery_key(host, account, policy):
    return hashlib.sha256(json.dumps([host,account,policy],separators=(',',':')).encode()).hexdigest()


def store_discovery(cache, key, result, now, ttl):
    if ttl <= 0 or ttl > 3600:raise ValueError('discovery TTL must be in (0,3600] seconds')
    cache[key]={'result':deepcopy(result),'recorded_at':now,'expires_at':now+ttl}


def cached_discovery(cache, key, now, refresh=False, availability_failure=False):
    entry=cache.get(key)
    if refresh or availability_failure:
        cache.pop(key,None);return None
    if not entry or now < entry['recorded_at'] or now >= entry['expires_at']:return None
    return deepcopy(entry['result'])
