"""
Plex Collection Manager API
Flask backend for creating and managing Plex collections via drag-and-drop UI.
Proxied by nginx at /capi/
"""

import os
import time
import yaml
import requests
from functools import wraps
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# Prevent plexapi from phoning home to plex.tv
# MUST be set before importing plexapi
import plexapi
plexapi.X_PLEX_IDENTIFIER = 'collection-manager-webhead'
plexapi.BASE_HEADERS['X-Plex-Client-Identifier'] = 'collection-manager-webhead'
plexapi.BASE_HEADERS['X-Plex-Provides'] = ''
plexapi.BASE_HEADERS['X-Plex-Product'] = 'Collection Manager'
plexapi.BASE_HEADERS['X-Plex-Version'] = '1.0.0'

from plexapi.server import PlexServer

# =============================================================================
# CONFIGURATION
# =============================================================================
PLEX_URL = os.environ.get('PLEX_URL', 'http://10.0.0.222:32400')
PLEX_TOKEN = os.environ['PLEX_TOKEN']
ADMIN_KEY = os.environ['ADMIN_KEY']
KELLY_KEY = os.environ['KELLY_KEY']
KELLY_COLLECTION_TITLE = "Kelly's Collection"

KOMETA_MOVIE_YML = '/app/kometa/movie_collections.yml'
KOMETA_TV_YML = '/app/kometa/tv_collections.yml'

app = Flask(__name__)
CORS(app)

# =============================================================================
# PLEX CONNECTION
# =============================================================================
_plex_server = None

def get_server():
    global _plex_server
    if _plex_server is None:
        _plex_server = PlexServer(PLEX_URL, PLEX_TOKEN)
    return _plex_server

def reset_server():
    """Reset cached server connection (e.g. after error)."""
    global _plex_server
    _plex_server = None

# =============================================================================
# CACHING (same pattern as announcement-api)
# =============================================================================
_cache = {}

def cached(key, ttl_seconds, fetcher):
    now = time.time()
    entry = _cache.get(key)
    if entry and (now - entry['ts']) < ttl_seconds:
        return entry['data']
    try:
        data = fetcher()
        _cache[key] = {'data': data, 'ts': now}
        return data
    except Exception as e:
        if entry:
            return entry['data']
        raise e

def invalidate_cache(prefix=''):
    keys_to_delete = [k for k in _cache if k.startswith(prefix)] if prefix else list(_cache.keys())
    for k in keys_to_delete:
        del _cache[k]

# =============================================================================
# KOMETA DETECTION
# =============================================================================
_kometa_titles = set()

def load_kometa_titles():
    global _kometa_titles
    titles = set()
    for path in [KOMETA_MOVIE_YML, KOMETA_TV_YML]:
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
            if data and 'collections' in data:
                for title in data['collections']:
                    titles.add(title)
        except Exception:
            pass
    _kometa_titles = titles

load_kometa_titles()

def is_kometa_managed(title):
    return title in _kometa_titles

# =============================================================================
# AUTH
# =============================================================================
def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Accept key from header or query param (needed for <img src=> tags)
        key = request.headers.get('X-Admin-Key') or request.args.get('k')
        if key != ADMIN_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def require_kelly(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-Kelly-Key') or request.args.get('k')
        if key != KELLY_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

def get_kelly_collection():
    """Find Kelly's Collection in the Movies library."""
    server = get_server()
    for section in server.library.sections():
        if section.type == 'movie':
            for col in section.collections():
                if col.title == KELLY_COLLECTION_TITLE:
                    return col, section
    return None, None

# =============================================================================
# HELPER: serialize items
# =============================================================================
def serialize_item(item):
    return {
        'ratingKey': str(item.ratingKey),
        'title': item.title,
        'year': getattr(item, 'year', None),
        'type': item.type,
        'thumb': f'/capi/poster/{item.ratingKey}' if item.thumb else None,
        'addedAt': item.addedAt.isoformat() if getattr(item, 'addedAt', None) else None,
    }

def serialize_collection(col, include_kometa=True):
    result = {
        'ratingKey': str(col.ratingKey),
        'title': col.title,
        'titleSort': getattr(col, 'titleSort', col.title) or col.title,
        'summary': getattr(col, 'summary', '') or '',
        'thumb': f'/capi/poster/{col.ratingKey}' if col.thumb else None,
        'smart': col.smart if hasattr(col, 'smart') else False,
        'childCount': col.childCount if hasattr(col, 'childCount') else 0,
    }
    if include_kometa:
        result['kometaManaged'] = is_kometa_managed(col.title)
    return result

# =============================================================================
# ENDPOINTS
# =============================================================================

@app.route('/capi/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/capi/libraries')
@require_admin
def list_libraries():
    def fetch():
        server = get_server()
        sections = server.library.sections()
        return {
            'libraries': [
                {
                    'key': str(s.key),
                    'title': s.title,
                    'type': s.type,
                    'count': s.totalSize,
                }
                for s in sections
            ]
        }
    try:
        data = cached('libraries', 300, fetch)
        return jsonify(data)
    except Exception as e:
        reset_server()
        return jsonify({'error': str(e)}), 500


@app.route('/capi/libraries/<key>/items')
@require_admin
def get_library_items(key):
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 50))
    search = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'titleSort')
    offset = (page - 1) * size

    try:
        server = get_server()
        section = server.library.sectionByID(int(key))

        if search:
            # Search returns all matches — paginate in Python
            cache_key = f'search:{key}:{search}'
            def do_search():
                results = section.search(title=search)
                return [serialize_item(item) for item in results]
            all_results = cached(cache_key, 60, do_search)
            total = len(all_results)
            items = all_results[offset:offset + size]
        else:
            # Fetch all and cache, then slice for pagination
            # plexapi container_start/container_size are unreliable
            cache_key = f'items_all:{key}'
            def do_fetch():
                results = section.all()
                return [serialize_item(item) for item in results]
            all_results = cached(cache_key, 120, do_fetch)
            total = len(all_results)
            items = all_results[offset:offset + size]

        return jsonify({
            'items': items,
            'totalSize': total,
            'page': page,
            'pageSize': size,
        })
    except Exception as e:
        reset_server()
        return jsonify({'error': str(e)}), 500


@app.route('/capi/poster/<rating_key>')
@require_admin
def get_poster(rating_key):
    try:
        resp = requests.get(
            f'{PLEX_URL}/library/metadata/{rating_key}/thumb',
            params={
                'X-Plex-Token': PLEX_TOKEN,
                'width': 300,
                'height': 450,
            },
            stream=True,
            timeout=10,
        )
        if resp.status_code != 200:
            return Response('Not found', status=404)

        headers = {
            'Content-Type': resp.headers.get('Content-Type', 'image/jpeg'),
            'Cache-Control': 'public, max-age=86400, immutable',
        }
        return Response(resp.iter_content(8192), headers=headers)
    except Exception:
        return Response('Error', status=500)


@app.route('/capi/libraries/<key>/collections')
@require_admin
def get_library_collections(key):
    def fetch():
        server = get_server()
        section = server.library.sectionByID(int(key))
        collections = section.collections()
        return {
            'collections': [serialize_collection(c) for c in collections]
        }
    try:
        data = cached(f'collections:{key}', 30, fetch)
        return jsonify(data)
    except Exception as e:
        reset_server()
        return jsonify({'error': str(e)}), 500


@app.route('/capi/collections/<rating_key>/items')
@require_admin
def get_collection_items(rating_key):
    try:
        server = get_server()
        collection = server.fetchItem(int(rating_key))
        items = collection.items()
        return jsonify({
            'collection': serialize_collection(collection),
            'items': [serialize_item(item) for item in items],
        })
    except Exception as e:
        reset_server()
        return jsonify({'error': str(e)}), 500


@app.route('/capi/collections', methods=['POST'])
@require_admin
def create_collection():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    library_key = data.get('libraryKey')
    title = data.get('title', '').strip()
    summary = data.get('summary', '').strip()
    item_keys = data.get('itemKeys', [])

    if not library_key or not title or not item_keys:
        return jsonify({'error': 'libraryKey, title, and itemKeys are required'}), 400

    try:
        server = get_server()
        section = server.library.sectionByID(int(library_key))

        # Fetch items in the specified order
        items = []
        for rk in item_keys:
            try:
                items.append(server.fetchItem(int(rk)))
            except Exception:
                pass

        if not items:
            return jsonify({'error': 'No valid items found'}), 400

        collection = section.createCollection(title=title, items=items)
        if summary:
            collection.editSummary(summary)

        # Invalidate collection cache
        invalidate_cache(f'collections:{library_key}')

        return jsonify({
            'success': True,
            'collection': serialize_collection(collection),
        })
    except Exception as e:
        reset_server()
        return jsonify({'error': str(e)}), 500


@app.route('/capi/collections/<rating_key>', methods=['PUT'])
@require_admin
def update_collection(rating_key):
    t_start = time.time()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    title = data.get('title')
    summary = data.get('summary')
    item_keys = data.get('itemKeys')

    stats = {'added': 0, 'removed': 0, 'reordered': 0, 'plexCalls': 0}

    try:
        server = get_server()
        collection = server.fetchItem(int(rating_key))
        stats['plexCalls'] += 1

        # Update title
        if title is not None:
            collection.editTitle(title.strip())
            stats['plexCalls'] += 1

        # Update summary
        if summary is not None:
            collection.editSummary(summary.strip())
            stats['plexCalls'] += 1

        # Update items and ordering
        if item_keys is not None:
            current_items = collection.items()
            stats['plexCalls'] += 1
            current_keys = set(str(item.ratingKey) for item in current_items)
            new_keys = set(item_keys)

            # Add new items
            to_add = [k for k in item_keys if k not in current_keys]
            if to_add:
                add_items = []
                for rk in to_add:
                    try:
                        add_items.append(server.fetchItem(int(rk)))
                        stats['plexCalls'] += 1
                    except Exception:
                        pass
                if add_items:
                    collection.addItems(add_items)
                    stats['plexCalls'] += 1
                    stats['added'] = len(add_items)

            # Remove items no longer in the list
            to_remove = [item for item in current_items if str(item.ratingKey) not in new_keys]
            if to_remove:
                collection.removeItems(to_remove)
                stats['plexCalls'] += 1
                stats['removed'] = len(to_remove)

            # Reorder: move each item after the previous one
            if len(item_keys) > 1:
                # Refresh the items list after add/remove
                refreshed = collection.items()
                stats['plexCalls'] += 1
                items_map = {str(i.ratingKey): i for i in refreshed}

                # Move first item to beginning
                first = items_map.get(item_keys[0])
                if first:
                    try:
                        collection.moveItem(first)
                        stats['plexCalls'] += 1
                        stats['reordered'] += 1
                    except Exception:
                        pass

                # Move remaining items after the previous one
                for i in range(1, len(item_keys)):
                    current = items_map.get(item_keys[i])
                    prev = items_map.get(item_keys[i - 1])
                    if current and prev:
                        try:
                            collection.moveItem(current, after=prev)
                            stats['plexCalls'] += 1
                            stats['reordered'] += 1
                        except Exception:
                            pass

        # Invalidate caches
        invalidate_cache('collections:')

        elapsed = round(time.time() - t_start, 2)
        stats['elapsed'] = elapsed
        stats['totalItems'] = len(item_keys) if item_keys else 0

        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        reset_server()
        return jsonify({'error': str(e)}), 500


@app.route('/capi/collections/<rating_key>', methods=['DELETE'])
@require_admin
def delete_collection(rating_key):
    try:
        server = get_server()
        collection = server.fetchItem(int(rating_key))
        collection.delete()

        invalidate_cache('collections:')

        return jsonify({'success': True})
    except Exception as e:
        reset_server()
        return jsonify({'error': str(e)}), 500


@app.route('/capi/libraries/<key>/collections/order', methods=['PUT'])
@require_admin
def reorder_collections(key):
    """Reorder collections by setting titleSort to zero-padded indices."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    collection_keys = data.get('collectionKeys', [])
    if not collection_keys:
        return jsonify({'error': 'collectionKeys required'}), 400

    try:
        server = get_server()
        for idx, rk in enumerate(collection_keys):
            try:
                col = server.fetchItem(int(rk))
                sort_title = f'{idx:06d}'
                col.editSortTitle(sort_title)
            except Exception as e:
                print(f"Failed to set sort title for {rk}: {e}")

        invalidate_cache('collections:')
        return jsonify({'success': True})
    except Exception as e:
        reset_server()
        return jsonify({'error': str(e)}), 500


# =============================================================================
# KELLY'S COLLECTION ENDPOINTS
# =============================================================================

def kelly_serialize_item(item):
    return {
        'ratingKey': str(item.ratingKey),
        'title': item.title,
        'year': getattr(item, 'year', None),
        'type': item.type,
        'thumb': f'/capi/kelly/poster/{item.ratingKey}' if item.thumb else None,
        'addedAt': item.addedAt.isoformat() if getattr(item, 'addedAt', None) else None,
    }

@app.route('/capi/kelly/collection')
@require_kelly
def kelly_get_collection():
    try:
        collection, section = get_kelly_collection()
        if not collection:
            return jsonify({'error': "Kelly's Collection not found"}), 404
        items = collection.items()
        return jsonify({
            'collection': serialize_collection(collection, include_kometa=False),
            'items': [kelly_serialize_item(item) for item in items],
        })
    except Exception as e:
        reset_server()
        return jsonify({'error': str(e)}), 500


@app.route('/capi/kelly/collection', methods=['PUT'])
@require_kelly
def kelly_update_collection():
    t_start = time.time()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    item_keys = data.get('itemKeys')
    if item_keys is None:
        return jsonify({'error': 'itemKeys required'}), 400

    stats = {'added': 0, 'removed': 0, 'reordered': 0, 'plexCalls': 0}

    try:
        collection, section = get_kelly_collection()
        if not collection:
            return jsonify({'error': "Kelly's Collection not found"}), 404
        stats['plexCalls'] += 1

        current_items = collection.items()
        stats['plexCalls'] += 1
        current_keys = set(str(item.ratingKey) for item in current_items)
        new_keys = set(item_keys)

        server = get_server()

        # Add new items
        to_add = [k for k in item_keys if k not in current_keys]
        if to_add:
            add_items = []
            for rk in to_add:
                try:
                    add_items.append(server.fetchItem(int(rk)))
                    stats['plexCalls'] += 1
                except Exception:
                    pass
            if add_items:
                collection.addItems(add_items)
                stats['plexCalls'] += 1
                stats['added'] = len(add_items)

        # Remove items no longer in the list
        to_remove = [item for item in current_items if str(item.ratingKey) not in new_keys]
        if to_remove:
            collection.removeItems(to_remove)
            stats['plexCalls'] += 1
            stats['removed'] = len(to_remove)

        # Reorder
        if len(item_keys) > 1:
            refreshed = collection.items()
            stats['plexCalls'] += 1
            items_map = {str(i.ratingKey): i for i in refreshed}

            first = items_map.get(item_keys[0])
            if first:
                try:
                    collection.moveItem(first)
                    stats['plexCalls'] += 1
                    stats['reordered'] += 1
                except Exception:
                    pass

            for i in range(1, len(item_keys)):
                current = items_map.get(item_keys[i])
                prev = items_map.get(item_keys[i - 1])
                if current and prev:
                    try:
                        collection.moveItem(current, after=prev)
                        stats['plexCalls'] += 1
                        stats['reordered'] += 1
                    except Exception:
                        pass

        invalidate_cache('collections:')

        elapsed = round(time.time() - t_start, 2)
        stats['elapsed'] = elapsed
        stats['totalItems'] = len(item_keys)

        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        reset_server()
        return jsonify({'error': str(e)}), 500


@app.route('/capi/kelly/search')
@require_kelly
def kelly_search():
    search = request.args.get('q', '').strip()
    if not search:
        return jsonify({'items': []})

    try:
        # Use the same library that contains Kelly's collection
        collection, section = get_kelly_collection()
        if not section:
            return jsonify({'error': 'Movies library not found'}), 404

        cache_key = f'kelly_search:{search}'
        def do_search():
            results = section.search(title=search)
            return [kelly_serialize_item(item) for item in results[:20]]
        items = cached(cache_key, 60, do_search)
        return jsonify({'items': items})
    except Exception as e:
        reset_server()
        return jsonify({'error': str(e)}), 500


@app.route('/capi/kelly/poster/<rating_key>')
@require_kelly
def kelly_get_poster(rating_key):
    try:
        resp = requests.get(
            f'{PLEX_URL}/library/metadata/{rating_key}/thumb',
            params={
                'X-Plex-Token': PLEX_TOKEN,
                'width': 300,
                'height': 450,
            },
            stream=True,
            timeout=10,
        )
        if resp.status_code != 200:
            return Response('Not found', status=404)

        headers = {
            'Content-Type': resp.headers.get('Content-Type', 'image/jpeg'),
            'Cache-Control': 'public, max-age=86400, immutable',
        }
        return Response(resp.iter_content(8192), headers=headers)
    except Exception:
        return Response('Error', status=500)


# =============================================================================
# RUN
# =============================================================================
if __name__ == '__main__':
    print(f"Collection Manager API starting...")
    print(f"Plex URL: {PLEX_URL}")
    print(f"Kometa titles loaded: {len(_kometa_titles)}")
    app.run(host='0.0.0.0', port=5000, debug=False)
