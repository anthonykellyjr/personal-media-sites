"""
Announcement API for WebHead Media Status Hub
Endpoints:
  GET  /api/announcement - Get current announcement
  POST /api/announcement - Set announcement (requires admin key)
  POST /api/anon-request - Submit anonymous content request (ntfy + email)
  POST /api/issue-report - Submit issue report (ntfy + email)
  GET  /api/tautulli-stats - Get live stream stats + Plex health + bandwidth
  GET  /api/calendar - Get upcoming episodes from Sonarr
  GET  /api/recently-added-movies - Get recently added movies from Radarr
  GET  /api/disk-health - Get disk SMART health from Scrutiny
  GET  /api/speedtest - Get latest speedtest results
  GET  /api/plex-status - (kept for backwards compat, proxies to tautulli-stats)
  GET  /api/seerr-status - Check Seerr health
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
import json
import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

app = Flask(__name__)
CORS(app)

ANNOUNCEMENTS_FILE = '/app/announcements.json'
TEXT_REQUESTS_FILE = '/app/text_requests.json'
ADMIN_KEY = os.environ['ADMIN_KEY']
TAUTULLI_URL = os.environ.get('TAUTULLI_URL', 'http://10.0.0.222:8182')
TAUTULLI_API_KEY = os.environ['TAUTULLI_API_KEY']
SONARR_URL = os.environ.get('SONARR_URL', 'http://10.0.0.222:8989')
SONARR_API_KEY = os.environ['SONARR_API_KEY']
RADARR_URL = os.environ.get('RADARR_URL', 'http://10.0.0.222:7878')
RADARR_API_KEY = os.environ['RADARR_API_KEY']
PLEX_URL = os.environ.get('PLEX_URL', 'http://10.0.0.222:32400')
PLEX_TOKEN = os.environ['PLEX_TOKEN']
SCRUTINY_URL = os.environ.get('SCRUTINY_URL', 'http://scrutiny:8080')
SPEEDTEST_DB = os.environ.get('SPEEDTEST_DB', '/data/speedtest/database.sqlite')
MDBLIST_API_KEY = os.environ.get('MDBLIST_API_KEY', '')

# --- TTL Cache ---
_cache = {}

def cached(key, ttl_seconds, fetcher):
    """Simple in-memory TTL cache. Returns cached data if fresh, otherwise calls fetcher."""
    now = time.time()
    entry = _cache.get(key)
    if entry and (now - entry['ts']) < ttl_seconds:
        return entry['data']
    try:
        data = fetcher()
        _cache[key] = {'data': data, 'ts': now}
        return data
    except Exception as e:
        # On error, return stale cache if available
        if entry:
            return entry['data']
        raise e

# --- Announcements ---

def load_announcement():
    try:
        with open(ANNOUNCEMENTS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"enabled": False, "message": "", "severity": "info", "dismissible": True}

def save_announcement(data):
    with open(ANNOUNCEMENTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/api/announcement', methods=['GET'])
def get_announcement():
    return jsonify(load_announcement())

@app.route('/api/announcement', methods=['POST'])
def set_announcement():
    auth = request.headers.get('X-Admin-Key', '')
    if auth != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()

    # Generate a new version timestamp so clients reset their dismissed state
    version = int(time.time() * 1000)

    announcement = {
        "enabled": data.get('enabled', False),
        "message": data.get('message', ''),
        "severity": data.get('severity', 'info'),  # red, yellow, green, info
        "dismissible": data.get('dismissible', True),
        "version": version,  # Clients use this to know when to reset dismissed state
        "expiresAt": data.get('expiresAt')  # Unix timestamp in ms, or null for no expiry
    }
    save_announcement(announcement)
    return jsonify({"success": True, "announcement": announcement})

NTFY_URL = os.environ.get('NTFY_URL', 'http://ntfy:80')

# Email config (Gmail SMTP)
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
ADMIN_EMAIL_ADDR = os.environ.get('ADMIN_EMAIL', '')

def _send_ntfy(topic, title, message, tags=''):
    """Send a notification via ntfy."""
    try:
        requests.post(
            f"{NTFY_URL}/{topic}",
            data=message.encode('utf-8'),
            headers={'Title': title, 'Tags': tags} if tags else {'Title': title},
            timeout=5
        )
    except Exception as e:
        print(f"ntfy send error: {e}")

def _send_email(subject, body_text, body_html=None):
    """Send an email via Gmail SMTP. Fails silently if not configured."""
    if not SMTP_USER or not SMTP_PASS or not ADMIN_EMAIL_ADDR:
        print("Email not configured, skipping")
        return
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_USER
        msg['To'] = ADMIN_EMAIL_ADDR
        msg['Subject'] = subject
        msg.attach(MIMEText(body_text, 'plain'))
        if body_html:
            msg.attach(MIMEText(body_html, 'html'))
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Email send error: {e}")

def _load_text_requests():
    try:
        with open(TEXT_REQUESTS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _save_text_requests(items):
    with open(TEXT_REQUESTS_FILE, 'w') as f:
        json.dump(items, f, indent=2)

@app.route('/api/anon-request', methods=['POST'])
def anon_request():
    """Handle anonymous content requests from the request form (persist + ntfy + email)"""
    data = request.get_json()
    title = data.get('title', 'Unknown')
    ts_now = int(time.time())
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Persist for later admin matching
    items = _load_text_requests()
    new_id = (max((r.get('id', 0) for r in items), default=0)) + 1
    items.append({
        'id': new_id,
        'text': title,
        'createdAt': ts_now,
        'tmdbId': None,
        'mediaType': None,
        'matchedTitle': None,
        'matchedYear': None,
        'matchedAt': None,
    })
    _save_text_requests(items)

    print(f"Anonymous request received: {title}")
    _send_ntfy('requests', 'Content Request', f"Someone requested: {title}", 'movie_camera')
    _send_email(
        f"Content Request: {title}",
        f"Someone requested: {title}\n\nTime: {ts}",
        f"<h2>Content Request</h2><p><strong>Title:</strong> {title}</p>"
        f"<p><strong>Time:</strong> {ts}</p>"
    )
    return jsonify({"success": True, "message": "Request received"})

# --- Text-request admin endpoints (used by /requests-admin/) ---

def _require_admin():
    if request.headers.get('X-Admin-Key', '') != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    return None

@app.route('/api/text-requests', methods=['GET'])
def list_text_requests():
    """List all persisted anonymous text requests."""
    err = _require_admin()
    if err: return err
    items = _load_text_requests()
    items.sort(key=lambda r: r.get('createdAt', 0), reverse=True)
    return jsonify({'requests': items})

@app.route('/api/text-requests', methods=['POST'])
def add_text_requests():
    """Manually seed one or more text requests (admin backfill)."""
    err = _require_admin()
    if err: return err
    body = request.get_json() or {}
    texts = body.get('texts') or ([body['text']] if body.get('text') else [])
    texts = [t.strip() for t in texts if isinstance(t, str) and t.strip()]
    if not texts:
        return jsonify({"error": "Provide 'text' or non-empty 'texts'"}), 400
    items = _load_text_requests()
    next_id = (max((r.get('id', 0) for r in items), default=0)) + 1
    ts_now = int(time.time())
    added = []
    for t in texts:
        rec = {'id': next_id, 'text': t, 'createdAt': ts_now,
               'tmdbId': None, 'mediaType': None,
               'matchedTitle': None, 'matchedYear': None, 'matchedAt': None}
        items.append(rec)
        added.append(rec)
        next_id += 1
    _save_text_requests(items)
    return jsonify({'success': True, 'added': added})

@app.route('/api/text-requests/<int:req_id>/match', methods=['POST'])
def match_text_request(req_id):
    """Attach a TMDB id + media type to a text request."""
    err = _require_admin()
    if err: return err
    body = request.get_json() or {}
    tmdb_id = body.get('tmdbId')
    media_type = body.get('mediaType')
    if not tmdb_id or media_type not in ('movie', 'tv'):
        return jsonify({"error": "tmdbId and mediaType (movie|tv) required"}), 400
    items = _load_text_requests()
    for r in items:
        if r.get('id') == req_id:
            r['tmdbId'] = int(tmdb_id)
            r['mediaType'] = media_type
            r['matchedTitle'] = body.get('title')
            r['matchedYear'] = body.get('year')
            r['matchedAt'] = int(time.time())
            _save_text_requests(items)
            return jsonify({'success': True, 'request': r})
    return jsonify({"error": "Not found"}), 404

@app.route('/api/text-requests/<int:req_id>/match', methods=['DELETE'])
def unmatch_text_request(req_id):
    """Clear the match on a text request (so it returns to the unmatched list)."""
    err = _require_admin()
    if err: return err
    items = _load_text_requests()
    for r in items:
        if r.get('id') == req_id:
            r['tmdbId'] = None
            r['mediaType'] = None
            r['matchedTitle'] = None
            r['matchedYear'] = None
            r['matchedAt'] = None
            _save_text_requests(items)
            return jsonify({'success': True})
    return jsonify({"error": "Not found"}), 404

@app.route('/api/text-requests/<int:req_id>', methods=['DELETE'])
def delete_text_request(req_id):
    """Remove a text request (spam / duplicate)."""
    err = _require_admin()
    if err: return err
    items = _load_text_requests()
    new_items = [r for r in items if r.get('id') != req_id]
    if len(new_items) == len(items):
        return jsonify({"error": "Not found"}), 404
    _save_text_requests(new_items)
    return jsonify({'success': True})

@app.route('/api/text-requests/search', methods=['GET'])
def text_request_search():
    """Server-side proxy for Seerr multi-search (so the admin page doesn't need the Seerr key)."""
    err = _require_admin()
    if err: return err
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'results': []})
    try:
        # Seerr rejects '+'-encoded spaces (requires %20). Build the URL with quote()
        # instead of passing params={'query': ...}, which uses '+' for spaces.
        url = f'{SEERR_URL}/api/v1/search?query={quote(query)}&page=1&language=en'
        resp = requests.get(
            url,
            headers={'X-Api-Key': SEERR_API_KEY},
            timeout=8
        )
        out = []
        for item in resp.json().get('results', []):
            mt = item.get('mediaType')
            if mt not in ('movie', 'tv'):
                continue
            date_field = item.get('releaseDate') or item.get('firstAirDate') or ''
            year = None
            if len(date_field) >= 4:
                try: year = int(date_field[:4])
                except ValueError: pass
            poster = item.get('posterPath')
            out.append({
                'tmdbId': item.get('id'),
                'mediaType': mt,
                'title': item.get('title') or item.get('name') or 'Unknown',
                'year': year,
                'posterUrl': f'https://image.tmdb.org/t/p/w185{poster}' if poster else None,
            })
        return jsonify({'results': out[:20]})
    except Exception as e:
        return jsonify({'results': [], 'error': str(e)}), 500

@app.route('/api/issue-report', methods=['POST'])
def issue_report():
    """Handle media issue reports (ntfy + email)"""
    data = request.get_json()
    title = data.get('title', 'Unknown')
    media_type = data.get('mediaType', '')
    issue_label = data.get('issueLabel', 'Unknown issue')
    details = data.get('details', '')
    year = data.get('year', '')
    tmdb_id = data.get('tmdbId', '')
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    msg = f"{media_type}: {title}"
    if year:
        msg += f" ({year})"
    msg += f"\nIssue: {issue_label}"
    if details:
        msg += f"\nDetails: {details}"

    print(f"Issue report: {msg}")
    _send_ntfy('plex-issues', f"Issue: {title}", msg, 'warning')
    title_display = f"{title} ({year})" if year else title
    details_row = f'<tr><td style="padding:12px;font-weight:bold;vertical-align:top;">Details</td><td style="padding:12px;">{details}</td></tr>' if details else ''
    email_html = (
        f"<h2>Plex Issue Report</h2>"
        f"<table style='border-collapse:collapse;width:100%;max-width:600px;'>"
        f"<tr style='background:#f3f4f6;'><td style='padding:12px;font-weight:bold;'>Title</td>"
        f"<td style='padding:12px;'>{title_display}</td></tr>"
        f"<tr><td style='padding:12px;font-weight:bold;'>Type</td>"
        f"<td style='padding:12px;'>{media_type}</td></tr>"
        f"<tr style='background:#f3f4f6;'><td style='padding:12px;font-weight:bold;'>Issue</td>"
        f"<td style='padding:12px;'>{issue_label}</td></tr>"
        f"{details_row}"
        f"<tr style='background:#f3f4f6;'><td style='padding:12px;font-weight:bold;'>Time</td>"
        f"<td style='padding:12px;'>{ts}</td></tr>"
        f"</table>"
    )
    _send_email(f"Plex Issue: {title}", msg + f"\n\nTime: {ts}", email_html)
    return jsonify({"success": True, "message": "Issue reported"})

@app.route('/api/general-message', methods=['POST'])
def general_message():
    """Handle anonymous general messages from the status page."""
    data = request.get_json()
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({"success": False, "message": "Message cannot be empty"}), 400
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"General message received: {message[:100]}")
    _send_ntfy('general', 'Message from Status Hub', message, 'speech_balloon')
    _send_email(
        'Status Hub: Anonymous Message',
        f"Message:\n{message}\n\nTime: {ts}",
        f"<h2>Anonymous Message</h2><p style='white-space:pre-wrap;'>{message}</p>"
        f"<p><small>Sent from Status Hub at {ts}</small></p>"
    )
    return jsonify({"success": True, "message": "Message sent"})

# --- Plex Stats (merged: streams + health + bandwidth) ---

def _fetch_plex_stats():
    """Fetch Plex sessions and derive stream count, online status, and total bandwidth."""
    try:
        response = requests.get(
            f"{PLEX_URL}/status/sessions",
            params={'X-Plex-Token': PLEX_TOKEN},
            headers={'Accept': 'application/json'},
            timeout=5
        )
        data = response.json()
        mc = data.get('MediaContainer', {})
        stream_count = mc.get('size', 0)

        # Sum bandwidth from all active sessions (kbps)
        total_bandwidth = 0
        for meta in mc.get('Metadata', []):
            session = meta.get('Session', {})
            total_bandwidth += session.get('bandwidth', 0)

        return {
            'activeStreams': stream_count,
            'totalBandwidthKbps': total_bandwidth,
            'plexOnline': True
        }
    except Exception as e:
        print(f"Plex sessions error: {e}")
        return {
            'activeStreams': 0,
            'totalBandwidthKbps': 0,
            'plexOnline': False
        }

@app.route('/api/tautulli-stats', methods=['GET'])
def tautulli_stats():
    """Get active stream count, bandwidth, and Plex health status."""
    data = cached('plex_stats', 8, _fetch_plex_stats)
    return jsonify(data)

@app.route('/api/plex-status', methods=['GET'])
def plex_status():
    """Check if Plex is responding (now derived from tautulli-stats cache)."""
    data = cached('plex_stats', 8, _fetch_plex_stats)
    if data['plexOnline']:
        return jsonify({'status': 'online', 'message': 'Plex is online'})
    return jsonify({'status': 'offline', 'message': 'Plex not responding'})

# --- Calendar ---

def _fetch_calendar():
    start = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    end = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

    response = requests.get(
        f"{SONARR_URL}/api/v3/calendar",
        params={'start': start, 'end': end, 'includeSeries': 'true'},
        headers={'X-Api-Key': SONARR_API_KEY},
        timeout=10
    )

    if response.status_code != 200:
        return {'episodes': [], 'error': 'Failed to fetch calendar'}

    episodes = response.json()
    result = []
    for ep in episodes:
        series = ep.get('series', {})
        result.append({
            'id': ep.get('id'),
            'seriesTitle': series.get('title', 'Unknown'),
            'episodeTitle': ep.get('title', 'TBA'),
            'seasonNumber': ep.get('seasonNumber', 0),
            'episodeNumber': ep.get('episodeNumber', 0),
            'airDateUtc': ep.get('airDateUtc'),
            'overview': ep.get('overview', '')[:150] + '...' if ep.get('overview') and len(ep.get('overview', '')) > 150 else ep.get('overview', ''),
            'hasFile': ep.get('hasFile', False),
            'monitored': ep.get('monitored', True),
            'poster': next((img.get('remoteUrl') for img in series.get('images', []) if img.get('coverType') == 'poster'), None)
        })

    result.sort(key=lambda x: x.get('airDateUtc') or '')
    return {'episodes': result}

@app.route('/api/calendar', methods=['GET'])
def calendar():
    """Get upcoming episodes from Sonarr calendar."""
    try:
        data = cached('calendar', 300, _fetch_calendar)
        return jsonify(data)
    except Exception as e:
        print(f"Sonarr calendar error: {e}")
        return jsonify({'episodes': [], 'error': str(e)})

# --- Recently Added Movies (from Plex) ---

def _fetch_recent_movies():
    response = requests.get(
        f"{PLEX_URL}/library/sections/1/recentlyAdded",
        params={'X-Plex-Token': PLEX_TOKEN, 'X-Plex-Container-Start': 0, 'X-Plex-Container-Size': 100},
        headers={'Accept': 'application/json'},
        timeout=10
    )
    items = response.json().get('MediaContainer', {}).get('Metadata', [])
    result = []
    for m in items:
        rk = m.get('ratingKey')
        result.append({
            'id': rk,
            'ratingKey': rk,
            'title': m.get('title', 'Unknown'),
            'year': m.get('year'),
            'addedAt': m.get('addedAt'),
            'thumb': f"/api/plex-thumb?path={m['thumb']}" if m.get('thumb') else None,
            'url': f"https://app.plex.tv/desktop#!/server/{PLEX_MACHINE_ID}/details?key=%2Flibrary%2Fmetadata%2F{rk}"
        })
    return {'movies': result}

@app.route('/api/recently-added-movies', methods=['GET'])
def recently_added_movies():
    """Get recently added movies from Plex."""
    try:
        data = cached('recent_movies', 300, _fetch_recent_movies)
        return jsonify(data)
    except Exception as e:
        print(f"Plex recently added movies error: {e}")
        return jsonify({'movies': [], 'error': str(e)})


# --- Trending Movies (MDB List × Radarr) ---

def _fetch_trending_movies():
    """Fetch top watched movies from MDB List, filter to ones in Radarr library."""
    if not MDBLIST_API_KEY:
        return {'movies': [], 'error': 'MDBLIST_API_KEY not configured'}

    # 1. Get all Radarr movies with files → set of tmdbIds
    try:
        radarr_resp = requests.get(
            f"{RADARR_URL}/api/v3/movie",
            headers={'X-Api-Key': RADARR_API_KEY},
            timeout=15
        )
        radarr_movies = radarr_resp.json()
        radarr_by_tmdb = {}
        for m in radarr_movies:
            if m.get('hasFile') and m.get('tmdbId'):
                radarr_by_tmdb[m['tmdbId']] = m
    except Exception as e:
        print(f"Radarr fetch error: {e}")
        return {'movies': [], 'error': f'Radarr error: {e}'}

    # 2. Get MDB List "Most Popular Movies Top 20"
    try:
        mdb_resp = requests.get(
            'https://api.mdblist.com/lists/linaspurinis/trending-movies-list/items/',
            params={'apikey': MDBLIST_API_KEY},
            timeout=10
        )
        mdb_data = mdb_resp.json()
        # Response is {"movies": [...], "shows": []} — extract the movies list
        mdb_items = mdb_data.get('movies', mdb_data) if isinstance(mdb_data, dict) else mdb_data
    except Exception as e:
        print(f"MDB List fetch error: {e}")
        return {'movies': [], 'error': f'MDB List error: {e}'}

    # 3. Get Plex movie library → build title+year → ratingKey lookup
    plex_lookup = {}
    try:
        plex_resp = requests.get(
            f"{PLEX_URL}/library/sections/1/all",
            params={'X-Plex-Token': PLEX_TOKEN, 'type': 1},
            headers={'Accept': 'application/json'},
            timeout=15
        )
        for m in plex_resp.json().get('MediaContainer', {}).get('Metadata', []):
            key = (m.get('title', '').lower(), m.get('year'))
            plex_lookup[key] = m.get('ratingKey')
    except Exception as e:
        print(f"Plex library fetch for trending: {e}")

    # 4. Cross-reference: only movies we have in Radarr
    result = []
    for item in mdb_items:
        tmdb_id = item.get('id') or (item.get('ids', {}) or {}).get('tmdb') or item.get('tmdb_id')
        if not tmdb_id:
            continue
        radarr_movie = radarr_by_tmdb.get(tmdb_id)
        if not radarr_movie:
            continue

        poster = None
        for img in radarr_movie.get('images', []):
            if img.get('coverType') == 'poster':
                remote = img.get('remoteUrl', '')
                if remote:
                    poster = remote.replace('/original/', '/w300/')
                break

        title = radarr_movie.get('title', item.get('title', 'Unknown'))
        year = radarr_movie.get('year', item.get('year'))
        rk = plex_lookup.get((title.lower(), year))
        url = f"https://app.plex.tv/desktop#!/server/{PLEX_MACHINE_ID}/details?key=%2Flibrary%2Fmetadata%2F{rk}" if rk else None

        result.append({
            'id': tmdb_id,
            'title': title,
            'year': year,
            'poster': poster,
            'rank': item.get('rank', len(result) + 1),
            'url': url,
        })

    result.sort(key=lambda x: x.get('rank', 999))
    return {'movies': result}


@app.route('/api/trending-movies', methods=['GET'])
def trending_movies():
    """Get trending movies that are in the local Radarr library."""
    try:
        data = cached('trending_movies', 3600, _fetch_trending_movies)
        return jsonify(data)
    except Exception as e:
        print(f"Trending movies error: {e}")
        return jsonify({'movies': [], 'error': str(e)})


# --- Recently Added Episodes (from Plex) ---

def _fetch_recent_episodes():
    response = requests.get(
        f"{PLEX_URL}/library/sections/2/recentlyAdded",
        params={'X-Plex-Token': PLEX_TOKEN, 'X-Plex-Container-Start': 0, 'X-Plex-Container-Size': 60, 'type': 4},
        headers={'Accept': 'application/json'},
        timeout=10
    )
    items = response.json().get('MediaContainer', {}).get('Metadata', [])
    result = []
    for ep in items:
        series_rk = ep.get('grandparentRatingKey')
        result.append({
            'id': ep.get('ratingKey'),
            'ratingKey': ep.get('ratingKey'),
            'seriesTitle': ep.get('grandparentTitle', 'Unknown'),
            'title': ep.get('title', ''),
            'seasonNumber': ep.get('parentIndex', 0),
            'episodeNumber': ep.get('index', 0),
            'addedAt': ep.get('addedAt'),
            'thumb': f"/api/plex-thumb?path={ep['grandparentThumb']}" if ep.get('grandparentThumb') else None,
            'url': f"https://app.plex.tv/desktop#!/server/{PLEX_MACHINE_ID}/details?key=%2Flibrary%2Fmetadata%2F{series_rk}"
        })
    return {'episodes': result}

@app.route('/api/recently-added-episodes', methods=['GET'])
def recently_added_episodes():
    """Get recently added episodes from Plex."""
    try:
        data = cached('recent_episodes', 300, _fetch_recent_episodes)
        return jsonify(data)
    except Exception as e:
        print(f"Plex recently added episodes error: {e}")
        return jsonify({'episodes': [], 'error': str(e)})

# --- Disk Health (Scrutiny) ---

def _fetch_disk_health():
    response = requests.get(f"{SCRUTINY_URL}/api/summary", timeout=5)
    data = response.json()
    summary = data.get('data', {}).get('summary', {})

    total = len(summary)
    healthy = 0
    warning = 0
    failed = 0

    for wwn, info in summary.items():
        status = info.get('device', {}).get('device_status', 0)
        if status == 0:
            healthy += 1
        elif status == 1 or status == 2:
            warning += 1
        else:
            failed += 1

    return {'total': total, 'healthy': healthy, 'warning': warning, 'failed': failed}

@app.route('/api/disk-health', methods=['GET'])
def disk_health():
    """Get disk SMART health summary from Scrutiny."""
    try:
        data = cached('disk_health', 600, _fetch_disk_health)
        return jsonify(data)
    except Exception as e:
        print(f"Scrutiny disk health error: {e}")
        return jsonify({'total': 0, 'healthy': 0, 'warning': 0, 'failed': 0, 'error': str(e)})

# --- Speedtest (from SQLite DB) ---

def _fetch_speedtest():
    import sqlite3
    try:
        conn = sqlite3.connect(f'file:{SPEEDTEST_DB}?mode=ro', uri=True, timeout=3)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT upload, download, ping, created_at FROM results WHERE status = "completed" ORDER BY id DESC LIMIT 1')
        row = cur.fetchone()
        conn.close()
        if row:
            # upload/download are in bytes/sec, convert to Mbps
            return {
                'uploadMbps': round(row['upload'] * 8 / 1_000_000, 1),
                'downloadMbps': round(row['download'] * 8 / 1_000_000, 1),
                'ping': round(row['ping'], 1),
                'timestamp': row['created_at']
            }
    except Exception as e:
        print(f"Speedtest DB error: {e}")
    return {'uploadMbps': 0, 'downloadMbps': 0, 'ping': 0, 'timestamp': None}

@app.route('/api/speedtest', methods=['GET'])
def speedtest():
    """Get latest speedtest results from Speedtest Tracker DB."""
    data = cached('speedtest', 1800, _fetch_speedtest)
    return jsonify(data)

# --- Seerr Status (deep health check with alerting) ---

SEERR_URL = 'http://10.0.0.222:5055'
SEERR_API_KEY = os.environ['SEERR_API_KEY']
_seerr_last_status = {'status': None}  # track state for alerting

def _fetch_seerr_status():
    checks = {'api': False, 'search': False}
    message_parts = []

    # Check 1: Is Seerr API alive?
    try:
        resp = requests.get(f'{SEERR_URL}/api/v1/status', timeout=5)
        if resp.status_code == 200:
            checks['api'] = True
        else:
            message_parts.append(f'API returned {resp.status_code}')
    except Exception as e:
        message_parts.append(f'API unreachable: {e}')

    # Check 2: Can Seerr actually search? (test query)
    if checks['api']:
        try:
            resp = requests.get(
                f'{SEERR_URL}/api/v1/search',
                params={'query': 'test', 'page': 1, 'language': 'en'},
                headers={'X-Api-Key': SEERR_API_KEY},
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                if 'results' in data:
                    checks['search'] = True
                else:
                    message_parts.append('Search returned no results key')
            else:
                message_parts.append(f'Search returned {resp.status_code}')
        except Exception as e:
            message_parts.append(f'Search failed: {e}')

    # Determine overall status
    if checks['api'] and checks['search']:
        status = 'online'
        message = 'Seerr is online and searchable'
    elif checks['api']:
        status = 'degraded'
        message = 'Seerr API up but search broken'
    else:
        status = 'offline'
        message = '; '.join(message_parts) or 'Seerr is down'

    # Alert on state change
    prev = _seerr_last_status['status']
    if prev is not None and prev != status:
        if status in ('offline', 'degraded'):
            _send_ntfy('plex-issues', f'Seerr is {status.upper()}',
                       f'Request page may be broken.\n{message}', 'warning')
            _send_email(f'Seerr is {status.upper()}',
                        f'Request page health check failed.\n\n{message}')
        elif prev in ('offline', 'degraded') and status == 'online':
            _send_ntfy('plex-issues', 'Seerr is back ONLINE',
                       'Request page is working again.', 'white_check_mark')
            _send_email('Seerr is back ONLINE', 'Request page is working again.')

    _seerr_last_status['status'] = status

    return {'status': status, 'message': message, 'checks': checks}

@app.route('/api/seerr-status', methods=['GET'])
@app.route('/api/overseerr-status', methods=['GET'])
def seerr_status():
    """Deep health check: API alive + search working, with alerting."""
    try:
        data = cached('seerr_status', 20, _fetch_seerr_status)
        return jsonify(data)
    except Exception as e:
        return jsonify({'status': 'offline', 'message': str(e)})


# --- Recently Fulfilled Requests (from Seerr) ---

def _fetch_detail(req):
    """Fetch title/year/poster for a single Seerr request via its detail endpoint."""
    media = req.get('media', {})
    tmdb_id = media.get('tmdbId')
    media_type = req.get('type', media.get('mediaType', 'movie'))
    rating_key = media.get('ratingKey') or media.get('ratingKey4k') or ''
    added_at_str = media.get('mediaAddedAt') or req.get('updatedAt', '')

    # Convert ISO timestamp to Unix epoch
    added_at = None
    if added_at_str:
        try:
            dt = datetime.fromisoformat(added_at_str.replace('Z', '+00:00'))
            added_at = int(dt.timestamp())
        except Exception:
            pass

    title = 'Unknown'
    year = None
    poster_path = ''

    if tmdb_id:
        endpoint = 'movie' if media_type == 'movie' else 'tv'
        try:
            detail_resp = requests.get(
                f'{SEERR_URL}/api/v1/{endpoint}/{tmdb_id}',
                headers={'X-Api-Key': SEERR_API_KEY},
                timeout=5
            )
            if detail_resp.status_code == 200:
                detail = detail_resp.json()
                title = detail.get('title') or detail.get('name') or detail.get('originalTitle') or 'Unknown'
                poster_path = detail.get('posterPath') or ''
                date_field = detail.get('releaseDate') or detail.get('firstAirDate') or ''
                if len(date_field) >= 4:
                    try:
                        year = int(date_field[:4])
                    except ValueError:
                        pass
        except Exception as e:
            print(f"Seerr detail fetch error for {endpoint}/{tmdb_id}: {e}")

    result = {
        'title': title,
        'year': year,
        'type': media_type,
        'addedAt': added_at,
        'posterUrl': f'https://image.tmdb.org/t/p/w300{poster_path}' if poster_path else None,
    }

    if rating_key:
        result['plexUrl'] = f'https://app.plex.tv/desktop#!/server/{PLEX_MACHINE_ID}/details?key=%2Flibrary%2Fmetadata%2F{rating_key}'

    return result


def _fetch_anon_detail(req):
    """Look up a matched anon request via Seerr; return a display item only if Plex-available."""
    tmdb_id = req.get('tmdbId')
    media_type = req.get('mediaType')
    if not tmdb_id or media_type not in ('movie', 'tv'):
        return None
    endpoint = 'movie' if media_type == 'movie' else 'tv'
    try:
        resp = requests.get(
            f'{SEERR_URL}/api/v1/{endpoint}/{tmdb_id}',
            headers={'X-Api-Key': SEERR_API_KEY},
            timeout=5
        )
        if resp.status_code != 200:
            return None
        detail = resp.json()
    except Exception as e:
        print(f"Anon match detail error {endpoint}/{tmdb_id}: {e}")
        return None

    media_info = detail.get('mediaInfo') or {}
    # Seerr status: 4=partial, 5=available. Skip anything not yet available.
    if (media_info.get('status') or 0) < 4:
        return None

    title = detail.get('title') or detail.get('name') or req.get('matchedTitle') or 'Unknown'
    poster_path = detail.get('posterPath') or ''
    date_field = detail.get('releaseDate') or detail.get('firstAirDate') or ''
    year = req.get('matchedYear')
    if not year and len(date_field) >= 4:
        try: year = int(date_field[:4])
        except ValueError: pass

    added_at = None
    added_str = media_info.get('mediaAddedAt') or ''
    if added_str:
        try:
            dt = datetime.fromisoformat(added_str.replace('Z', '+00:00'))
            added_at = int(dt.timestamp())
        except Exception:
            pass
    if not added_at:
        added_at = req.get('matchedAt') or req.get('createdAt')

    rating_key = media_info.get('ratingKey') or media_info.get('ratingKey4k') or ''
    out = {
        'title': title,
        'year': year,
        'type': media_type,
        'addedAt': added_at,
        'posterUrl': f'https://image.tmdb.org/t/p/w300{poster_path}' if poster_path else None,
        'tmdbId': tmdb_id,
    }
    if rating_key:
        out['plexUrl'] = f'https://app.plex.tv/desktop#!/server/{PLEX_MACHINE_ID}/details?key=%2Flibrary%2Fmetadata%2F{rating_key}'
    return out


def _fetch_recently_fulfilled():
    """Fetch Seerr-fulfilled requests, plus any matched anonymous requests that are now available."""
    resp = requests.get(
        f'{SEERR_URL}/api/v1/request',
        params={'take': 25, 'skip': 0, 'filter': 'available', 'sort': 'modified'},
        headers={'X-Api-Key': SEERR_API_KEY},
        timeout=10
    )
    if resp.status_code != 200:
        return {'requests': [], 'error': f'Seerr returned {resp.status_code}'}

    results_list = resp.json().get('results', [])

    # Pull both Seerr-fulfilled details and matched anon-request details in parallel.
    matched_anon = [r for r in _load_text_requests() if r.get('tmdbId') and r.get('mediaType')]
    with ThreadPoolExecutor(max_workers=5) as executor:
        seerr_items = list(executor.map(_fetch_detail, results_list))
        anon_items = [x for x in executor.map(_fetch_anon_detail, matched_anon) if x]

    # Dedupe by (tmdbId, type) — prefer Seerr's record if both exist.
    seen = set()
    merged = []
    for it in seerr_items:
        # _fetch_detail doesn't expose tmdbId on the output, so dedupe by (title, year, type).
        soft_key = (it.get('title'), it.get('year'), it.get('type'))
        if soft_key in seen: continue
        seen.add(soft_key)
        merged.append(it)
    for it in anon_items:
        soft_key = (it.get('title'), it.get('year'), it.get('type'))
        if soft_key in seen: continue
        seen.add(soft_key)
        merged.append(it)

    merged.sort(key=lambda x: x.get('addedAt') or 0, reverse=True)
    return {'requests': merged}


@app.route('/api/recently-fulfilled', methods=['GET'])
def recently_fulfilled():
    """Get recently fulfilled requests from Seerr."""
    try:
        data = cached('recently_fulfilled', 300, _fetch_recently_fulfilled)
        return jsonify(data)
    except Exception as e:
        print(f"Recently fulfilled requests error: {e}")
        return jsonify({'requests': [], 'error': str(e)})

# --- Plex Library Search ---

PLEX_MACHINE_ID = 'b1260353b00ff078b4c700023867f78a4a15aa53'

@app.route('/api/search', methods=['GET'])
def plex_search():
    """Search Plex library, return results with direct links."""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'results': []})

    try:
        resp = requests.get(
            f"{PLEX_URL}/hubs/search",
            params={'query': query, 'X-Plex-Token': PLEX_TOKEN, 'limit': 10},
            headers={'Accept': 'application/json'},
            timeout=5
        )
        data = resp.json()
        results = []
        for hub in data.get('MediaContainer', {}).get('Hub', []):
            hub_type = hub.get('type', '')
            if hub_type not in ('movie', 'show'):
                continue
            for item in hub.get('Metadata', []):
                rating_key = item.get('ratingKey')
                thumb = item.get('thumb', '')
                results.append({
                    'title': item.get('title', ''),
                    'year': item.get('year'),
                    'type': hub_type,
                    'ratingKey': rating_key,
                    'thumb': f"/api/plex-thumb?path={thumb}" if thumb else None,
                    'url': f"https://app.plex.tv/desktop#!/server/{PLEX_MACHINE_ID}/details?key=%2Flibrary%2Fmetadata%2F{rating_key}"
                })
        return jsonify({'results': results[:10]})
    except Exception as e:
        print(f"Plex search error: {e}")
        return jsonify({'results': [], 'error': str(e)})


@app.route('/api/plex-thumb', methods=['GET'])
def plex_thumb():
    """Proxy Plex thumbnail to avoid exposing token to frontend."""
    path = request.args.get('path', '')
    if not path:
        return '', 404
    w = request.args.get('w', '300')
    h = request.args.get('h', '450')
    try:
        resp = requests.get(
            f"{PLEX_URL}/photo/:/transcode",
            params={'X-Plex-Token': PLEX_TOKEN, 'width': w, 'height': h, 'minSize': 1, 'upscale': 1, 'url': path},
            timeout=5
        )
        from flask import Response
        r = Response(resp.content, content_type=resp.headers.get('Content-Type', 'image/jpeg'))
        r.headers['Cache-Control'] = 'public, max-age=86400'
        return r
    except:
        return '', 404


# --- System Stats (Prometheus) ---

PROMETHEUS_URL = os.environ.get('PROMETHEUS_URL', 'http://10.0.0.222:9090')

def _fetch_system_stats():
    results = {}
    queries = {
        'cpu': '100-(avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))*100)',
        'mem': '100*(1-(node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes))',
        'disk_used': 'node_filesystem_size_bytes{mountpoint="/mnt/storage"}-node_filesystem_free_bytes{mountpoint="/mnt/storage"}',
        'disk_total': 'node_filesystem_size_bytes{mountpoint="/mnt/storage"}',
        'gpu_temp': 'nvidia_smi_temperature_gpu',
        'gpu_util': 'nvidia_smi_utilization_gpu_ratio * 100',
    }
    for key, query in queries.items():
        try:
            r = requests.get(f'{PROMETHEUS_URL}/api/v1/query', params={'query': query}, timeout=3)
            data = r.json()
            val = data['data']['result'][0]['value'][1]
            results[key] = float(val)
        except Exception:
            results[key] = None
    return {
        'cpuPercent': round(results['cpu'], 1) if results['cpu'] is not None else None,
        'memPercent': round(results['mem'], 1) if results['mem'] is not None else None,
        'diskUsedTB': round(results['disk_used'] / 1e12, 1) if results['disk_used'] is not None else None,
        'diskTotalTB': round(results['disk_total'] / 1e12, 1) if results['disk_total'] is not None else None,
        'gpuTempC': round(results['gpu_temp']) if results['gpu_temp'] is not None else None,
        'gpuUtilPercent': round(results['gpu_util'], 1) if results['gpu_util'] is not None else None,
    }

@app.route('/api/system-stats', methods=['GET'])
def system_stats():
    """CPU, memory, disk usage from Prometheus."""
    try:
        data = cached('system_stats', 15, _fetch_system_stats)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Health ---

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
