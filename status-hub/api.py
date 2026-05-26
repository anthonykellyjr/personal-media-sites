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
HIDDEN_FULFILLED_FILE = '/app/hidden_fulfilled.json'
# Admin overrides for per-request state. Keyed by (tmdbId, type). Used when an
# admin wants to mark a Seerr-originated request as "searching" (hard to find)
# or override the auto-detected pending/uploaded state. Persisted across restarts.
REQUEST_OVERRIDES_FILE = '/app/request_overrides.json'
VALID_REQUEST_STATES = ('pending', 'searching', 'uploaded')
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

# --- Request-status version counter ---
# Bumped every time anything that affects /api/recently-fulfilled changes
# (new anon request, admin match/unmatch/state-change, Quick Request submit,
# fulfilled hide). Frontends poll the lightweight /api/recently-fulfilled/version
# endpoint and only do the full fetch when the version changes — gives near-
# real-time updates without persistent connections or frequent heavy fetches.
# Resets to 0 on container restart, which still triggers a refetch in any
# client that had a non-zero value (the inequality check fires either way).
_request_status_version = 0

def _invalidate_request_status():
    """Drop the recently-fulfilled cache AND bump the version counter so any
    polling client picks up the change on its next 30-second check."""
    global _request_status_version
    _cache.pop('recently_fulfilled', None)
    _request_status_version += 1

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
    _invalidate_request_status()

    print(f"Anonymous request received: {title}")
    admin_url = 'https://akplex.tv/requests-admin/'
    _send_ntfy('requests', 'Content Request', f"Someone requested: {title}\n\nMatch it: {admin_url}", 'movie_camera')
    _send_email(
        f"Content Request: {title}",
        f"Someone requested: {title}\n\nTime: {ts}\n\nMatch it to TMDB: {admin_url}",
        f"<h2>Content Request</h2>"
        f"<p><strong>Title:</strong> {title}</p>"
        f"<p><strong>Time:</strong> {ts}</p>"
        f"<p><a href=\"{admin_url}\" style=\"display:inline-block;padding:10px 18px;background:#9333ea;color:#fff;text-decoration:none;border-radius:6px;font-weight:600;\">Match to TMDB &rarr;</a></p>"
    )
    return jsonify({"success": True, "message": "Request received"})

# --- Text-request admin endpoints (used by /requests-admin/) ---
#
# Text-requests are anonymous content requests (free-form strings) that need
# to be matched to a TMDB id before they can flow into Seerr / the recently-
# fulfilled feed. Lifecycle:
#   anon_request() (POST /api/anon-request)  -> creates an UNMATCHED entry
#   match_text_request()                     -> attaches a tmdbId + mediaType
#   _fetch_recently_fulfilled() consumer     -> merges matched items into the
#                                                public Status Hub feed once
#                                                Seerr reports them available
# All admin endpoints below require the X-Admin-Key header.

def _require_admin():
    """Return a 401 response if the X-Admin-Key header is missing/wrong, else None."""
    if request.headers.get('X-Admin-Key', '') != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    return None

@app.route('/api/text-requests', methods=['GET'])
def list_text_requests():
    """List all persisted anonymous text requests (matched + unmatched), newest first."""
    err = _require_admin()
    if err: return err
    items = _load_text_requests()
    items.sort(key=lambda r: r.get('createdAt', 0), reverse=True)
    return jsonify({'requests': items})

@app.route('/api/text-requests', methods=['POST'])
def add_text_requests():
    """Manually seed one or more text requests (admin backfill).
    Body: {"text": "single string"} or {"texts": ["a", "b", ...]}.
    Seeded entries start UNMATCHED so they show up in the admin UI's Unmatched box.
    """
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
    _invalidate_request_status()
    return jsonify({'success': True, 'added': added})

@app.route('/api/text-requests/<int:req_id>/match', methods=['POST'])
def match_text_request(req_id):
    """Attach a TMDB id + media type to a text request.
    Body: {"tmdbId": int, "mediaType": "movie"|"tv", "title": str, "year": int}.
    Invalidates the recently-fulfilled cache so the public feed updates immediately.
    """
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
            _invalidate_request_status()
            return jsonify({'success': True, 'request': r})
    return jsonify({"error": "Not found"}), 404

@app.route('/api/text-requests/<int:req_id>/match', methods=['DELETE'])
def unmatch_text_request(req_id):
    """Clear the match on a text request (so it returns to the unmatched list).
    Useful if a match was made to the wrong title and you want to redo it.
    """
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
            _invalidate_request_status()
            return jsonify({'success': True})
    return jsonify({"error": "Not found"}), 404

@app.route('/api/text-requests/<int:req_id>', methods=['DELETE'])
def delete_text_request(req_id):
    """Remove a text request entirely (spam / duplicate / fulfilled-and-archived)."""
    err = _require_admin()
    if err: return err
    items = _load_text_requests()
    new_items = [r for r in items if r.get('id') != req_id]
    if len(new_items) == len(items):
        return jsonify({"error": "Not found"}), 404
    _save_text_requests(new_items)
    _invalidate_request_status()
    return jsonify({'success': True})

def _seerr_multi_search(query, limit=20):
    """Hit Seerr's multi-search and normalize to a slim list.
    Used by the admin matcher, the Quick Request modal, and the public
    /request and /issues pages. Results are sorted English-first then by
    popularity descending so the most-likely intended result is on top.
    """
    # Seerr rejects '+'-encoded spaces (requires %20). Build the URL with quote()
    # instead of passing params={'query': ...}, which uses '+' for spaces.
    url = f'{SEERR_URL}/api/v1/search?query={quote(query)}&page=1&language=en'
    resp = requests.get(url, headers={'X-Api-Key': SEERR_API_KEY}, timeout=8)
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
            'originalLanguage': item.get('originalLanguage') or '',
            'popularity': item.get('popularity') or 0,
        })
    out.sort(key=lambda x: (0 if x['originalLanguage'] == 'en' else 1, -x['popularity']))
    return out[:limit]

@app.route('/api/text-requests/search', methods=['GET'])
def text_request_search():
    """Admin-only Seerr search (used by /requests-admin/ matching UI)."""
    err = _require_admin()
    if err: return err
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'results': []})
    try:
        return jsonify({'results': _seerr_multi_search(query)})
    except Exception as e:
        return jsonify({'results': [], 'error': str(e)}), 500

@app.route('/api/seerr-search', methods=['GET'])
def seerr_search_public():
    """Public Seerr search proxy. Same trust level as the public /request page.
    Callers: Status Hub Quick Request modal, /request, /issues.
    """
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'results': []})
    try:
        return jsonify({'results': _seerr_multi_search(query, limit=10)})
    except Exception as e:
        return jsonify({'results': [], 'error': str(e)}), 500

@app.route('/api/seerr-status/<media_type>/<int:tmdb_id>', methods=['GET'])
def seerr_status_public(media_type, tmdb_id):
    """Public availability check for a TMDB id. Used by /issues to filter
    search results to media we actually have. Returns {status} where status
    matches Seerr's mediaInfo.status integer (4 = partially available, 5 = available).
    """
    if media_type not in ('movie', 'tv'):
        return jsonify({'error': 'media_type must be movie or tv'}), 400
    try:
        r = requests.get(
            f'{SEERR_URL}/api/v1/{media_type}/{tmdb_id}',
            headers={'X-Api-Key': SEERR_API_KEY},
            timeout=5
        )
        if r.status_code != 200:
            return jsonify({'status': None}), r.status_code
        info = r.json().get('mediaInfo') or {}
        return jsonify({'status': info.get('status')})
    except Exception as e:
        return jsonify({'status': None, 'error': str(e)}), 500

@app.route('/api/quick-request', methods=['POST'])
def quick_request():
    """Submit a Quick Request from the Status Hub modal.
    Body: {"tmdbId": int, "mediaType": "movie"|"tv", "title": str, "year": int?}.
    Side effects (POST to both, per user spec):
      1. Create a real Seerr request via POST /api/v1/request (TV defaults to all seasons).
      2. Persist a MATCHED text_request entry so it appears in /requests-admin/.
    Also fires the usual ntfy + email notifications and invalidates the
    recently-fulfilled cache so the public feed updates promptly.
    """
    data = request.get_json() or {}
    tmdb_id = data.get('tmdbId')
    media_type = data.get('mediaType')
    title = data.get('title') or 'Unknown'
    year = data.get('year')
    if not tmdb_id or media_type not in ('movie', 'tv'):
        return jsonify({"error": "tmdbId and mediaType (movie|tv) required"}), 400

    # 1. Submit to Seerr. We don't fail the whole request if Seerr is down —
    #    the admin can still see the matched entry and retry manually.
    seerr_ok = False
    seerr_err = None
    try:
        body = {'mediaType': media_type, 'mediaId': int(tmdb_id)}
        if media_type == 'tv':
            body['seasons'] = 'all'
        r = requests.post(
            f'{SEERR_URL}/api/v1/request',
            json=body,
            headers={'X-Api-Key': SEERR_API_KEY},
            timeout=10
        )
        # 201 = created, 409 = already requested (treat as success since the intent is met).
        seerr_ok = r.status_code in (200, 201, 409)
        if not seerr_ok:
            seerr_err = f"Seerr returned {r.status_code}: {r.text[:200]}"
    except Exception as e:
        seerr_err = str(e)

    # 2. Persist as a matched text_request so it shows up in /requests-admin/.
    ts_now = int(time.time())
    items = _load_text_requests()
    new_id = (max((r.get('id', 0) for r in items), default=0)) + 1
    items.append({
        'id': new_id,
        'text': title,
        'createdAt': ts_now,
        'tmdbId': int(tmdb_id),
        'mediaType': media_type,
        'matchedTitle': title,
        'matchedYear': year,
        'matchedAt': ts_now,
    })
    _save_text_requests(items)
    _invalidate_request_status()

    # 3. Notify admin (same channels as anon_request).
    label = f"{title}" + (f" ({year})" if year else "")
    admin_url = 'https://akplex.tv/requests-admin/'
    _send_ntfy('requests', 'Quick Request', f"Someone requested: {label}\n\nAdmin: {admin_url}", 'movie_camera')
    _send_email(
        f"Quick Request: {label}",
        f"Quick Request submitted: {label}\nTMDB id: {tmdb_id} ({media_type})\nSeerr: {'OK' if seerr_ok else 'FAILED — ' + (seerr_err or 'unknown')}\n\nAdmin: {admin_url}",
        f"<h2>Quick Request</h2>"
        f"<p><strong>Title:</strong> {label}</p>"
        f"<p><strong>TMDB:</strong> {tmdb_id} ({media_type})</p>"
        f"<p><strong>Seerr:</strong> {'OK' if seerr_ok else 'FAILED &mdash; ' + (seerr_err or 'unknown')}</p>"
        f"<p><a href=\"{admin_url}\" style=\"display:inline-block;padding:10px 18px;background:#9333ea;color:#fff;text-decoration:none;border-radius:6px;font-weight:600;\">Open Admin &rarr;</a></p>"
    )

    return jsonify({'success': True, 'seerr': seerr_ok, 'seerrError': seerr_err, 'requestId': new_id})

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
    # Ask Plex for a large window (500) so a recent dump of one show doesn't
    # crowd out every other series in the response.
    response = requests.get(
        f"{PLEX_URL}/library/sections/2/recentlyAdded",
        params={'X-Plex-Token': PLEX_TOKEN, 'X-Plex-Container-Start': 0, 'X-Plex-Container-Size': 500, 'type': 4},
        headers={'Accept': 'application/json'},
        timeout=15
    )
    items = response.json().get('MediaContainer', {}).get('Metadata', [])

    # Dedupe by series: keep one entry per show using the most-recently-added
    # episode for display, with `count` = how many of that show's episodes were
    # in the recent window. Avoids the "60 FMA cards, no other shows" problem.
    groups = {}
    for ep in items:
        key = ep.get('grandparentRatingKey') or ep.get('grandparentTitle', 'Unknown')
        groups.setdefault(key, []).append(ep)

    result = []
    for eps in groups.values():
        latest = max(eps, key=lambda e: e.get('addedAt', 0))
        # Link to the SEASON of the most-recent episode (parentRatingKey), not
        # the series — drops the user into the right season on click.
        parent_rk = latest.get('parentRatingKey')
        result.append({
            'id': latest.get('ratingKey'),
            'ratingKey': latest.get('ratingKey'),
            'seriesTitle': latest.get('grandparentTitle', 'Unknown'),
            'title': latest.get('title', ''),
            'seasonNumber': latest.get('parentIndex', 0),
            'episodeNumber': latest.get('index', 0),
            'addedAt': latest.get('addedAt'),
            'thumb': f"/api/plex-thumb?path={latest['grandparentThumb']}" if latest.get('grandparentThumb') else None,
            'url': f"https://app.plex.tv/desktop#!/server/{PLEX_MACHINE_ID}/details?key=%2Flibrary%2Fmetadata%2F{parent_rk}",
            'count': len(eps),
        })

    result.sort(key=lambda x: -(x.get('addedAt') or 0))
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
    """Fetch title/year/poster for a single Seerr request via its detail endpoint.
    Returns a dict with `state`: 'uploaded' if Plex has it (Seerr status >= 4),
    else 'pending' (queued/processing in Seerr).
    """
    media = req.get('media', {})
    tmdb_id = media.get('tmdbId')
    media_type = req.get('type', media.get('mediaType', 'movie'))
    rating_key = media.get('ratingKey') or media.get('ratingKey4k') or ''
    added_at_str = media.get('mediaAddedAt') or req.get('updatedAt', '')
    # Seerr media.status: 1=unknown, 2=pending, 3=processing, 4=partial, 5=available
    state = 'uploaded' if (media.get('status') or 0) >= 4 else 'pending'
    # Admin override (e.g. 'searching') takes precedence over Seerr's auto-detect.
    if tmdb_id and media_type in ('movie', 'tv'):
        ov = _load_request_overrides().get((int(tmdb_id), media_type))
        if ov and ov.get('state'):
            state = ov['state']

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
        'tmdbId': tmdb_id,
        'state': state,
    }

    if rating_key:
        result['plexUrl'] = f'https://app.plex.tv/desktop#!/server/{PLEX_MACHINE_ID}/details?key=%2Flibrary%2Fmetadata%2F{rating_key}'

    return result


# --- Recently-fulfilled hide list (admin curates which entries show on the feed) ---

def _load_hidden_fulfilled():
    """Returns a set of (tmdbId, type) tuples to exclude from /api/recently-fulfilled."""
    try:
        with open(HIDDEN_FULFILLED_FILE, 'r') as f:
            data = json.load(f)
        return {(int(item['tmdbId']), item['type']) for item in data if item.get('tmdbId')}
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def _save_hidden_fulfilled(hidden_set):
    items = [{'tmdbId': k[0], 'type': k[1]} for k in sorted(hidden_set)]
    with open(HIDDEN_FULFILLED_FILE, 'w') as f:
        json.dump(items, f, indent=2)

@app.route('/api/recently-fulfilled/hide', methods=['POST'])
def hide_fulfilled():
    """Admin-only: stop showing a given (tmdbId, type) on the public feed."""
    err = _require_admin()
    if err: return err
    body = request.get_json() or {}
    tmdb_id = body.get('tmdbId')
    mt = body.get('type') or body.get('mediaType')
    if not tmdb_id or mt not in ('movie', 'tv'):
        return jsonify({'error': 'tmdbId and type (movie|tv) required'}), 400
    hidden = _load_hidden_fulfilled()
    hidden.add((int(tmdb_id), mt))
    _save_hidden_fulfilled(hidden)
    # Invalidate the cached fulfilled response so the next GET reflects the hide.
    _invalidate_request_status()
    return jsonify({'success': True, 'hiddenCount': len(hidden)})


def _fetch_anon_detail(req):
    """Look up a matched anon request via Seerr; return a display item with `state`.
    Unlike _fetch_detail, this works from a text_request entry (tmdbId + mediaType
    set by the admin via /requests-admin/). Returns items in both 'pending' and
    'uploaded' states so the public feed shows the full lifecycle.
    """
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
    state = 'uploaded' if (media_info.get('status') or 0) >= 4 else 'pending'
    # Admin override takes precedence over Seerr's auto-detect.
    ov = _load_request_overrides().get((int(tmdb_id), media_type))
    if ov and ov.get('state'):
        state = ov['state']

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
        'state': state,
    }
    if rating_key:
        out['plexUrl'] = f'https://app.plex.tv/desktop#!/server/{PLEX_MACHINE_ID}/details?key=%2Flibrary%2Fmetadata%2F{rating_key}'
    return out


# --- Admin per-request state overrides --------------------------------------
# Stored as a list of {tmdbId, type, state, note, updatedAt} dicts. Admins set
# overrides via POST /api/admin/request-state to mark a request as 'searching'
# (hard to find but still working on it) or to force pending/uploaded. The
# request fetchers below merge these in so the override takes precedence over
# Seerr's auto-detected state.

def _load_request_overrides():
    """Return overrides as dict keyed by (tmdbId, type) -> {state, note, updatedAt}."""
    try:
        with open(REQUEST_OVERRIDES_FILE, 'r') as f:
            data = json.load(f)
        out = {}
        for item in data:
            tmdb = item.get('tmdbId')
            t = item.get('type')
            if tmdb and t in ('movie', 'tv'):
                out[(int(tmdb), t)] = {
                    'state': item.get('state'),
                    'note': item.get('note', ''),
                    'updatedAt': item.get('updatedAt'),
                }
        return out
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_request_overrides(overrides_dict):
    items = [
        {'tmdbId': k[0], 'type': k[1], 'state': v.get('state'), 'note': v.get('note', ''), 'updatedAt': v.get('updatedAt')}
        for k, v in sorted(overrides_dict.items())
    ]
    with open(REQUEST_OVERRIDES_FILE, 'w') as f:
        json.dump(items, f, indent=2)

@app.route('/api/admin/request-state', methods=['POST'])
def set_request_state():
    """Admin: set the displayed state for a (tmdbId, type) request.
    Body: {"tmdbId": int, "type": "movie"|"tv", "state": "pending"|"searching"|"uploaded", "note": str?}
    Pass state="" or null to clear the override (back to auto-detect from Seerr).
    """
    err = _require_admin()
    if err: return err
    body = request.get_json() or {}
    tmdb_id = body.get('tmdbId')
    mt = body.get('type')
    state = body.get('state')
    note = body.get('note', '') or ''
    if not tmdb_id or mt not in ('movie', 'tv'):
        return jsonify({'error': 'tmdbId and type (movie|tv) required'}), 400
    if state and state not in VALID_REQUEST_STATES:
        return jsonify({'error': f'state must be one of {VALID_REQUEST_STATES} or empty to clear'}), 400
    overrides = _load_request_overrides()
    key = (int(tmdb_id), mt)
    if not state:
        overrides.pop(key, None)
    else:
        overrides[key] = {'state': state, 'note': note, 'updatedAt': int(time.time())}
    _save_request_overrides(overrides)
    _invalidate_request_status()
    return jsonify({'success': True, 'overrideCount': len(overrides)})

def _fetch_tmdb_detail(key):
    """Fetch title/year/poster from Seerr for a (tmdb_id, media_type) tuple.
    Returns (key, dict-or-None). Used by admin_all_requests to enrich items
    in parallel so the admin page doesn't show 'TMDB 7345' / no posters.
    """
    tmdb_id, media_type = key
    endpoint = 'movie' if media_type == 'movie' else 'tv'
    try:
        r = requests.get(
            f'{SEERR_URL}/api/v1/{endpoint}/{tmdb_id}',
            headers={'X-Api-Key': SEERR_API_KEY},
            timeout=5
        )
        if r.status_code != 200:
            return key, None
        d = r.json()
        title = d.get('title') or d.get('name') or d.get('originalTitle') or 'Unknown'
        date_field = d.get('releaseDate') or d.get('firstAirDate') or ''
        year = None
        if len(date_field) >= 4:
            try: year = int(date_field[:4])
            except ValueError: pass
        poster_path = d.get('posterPath') or ''
        poster_url = f'https://image.tmdb.org/t/p/w185{poster_path}' if poster_path else None
        # Also pull mediaInfo.status — this is the authoritative "is it in Plex"
        # signal for matched items that may not appear in the recent /request
        # list (e.g. older Seerr requests outside the take=200 window, OR text
        # requests that were never in Seerr but the file is in Plex now).
        media_info = d.get('mediaInfo') or {}
        return key, {
            'title': title,
            'year': year,
            'posterUrl': poster_url,
            'mediaStatus': media_info.get('status', 0),
        }
    except Exception:
        return key, None


def _build_admin_all_requests():
    """Heavy work for /api/admin/all-requests. Cached so repeated admin-page
    loads don't refetch 80+ TMDB details every time. Cache is invalidated on
    any state-changing action via _invalidate_request_status()."""
    text_items = _load_text_requests()
    overrides = _load_request_overrides()

    # Pull Seerr's full request list (take=200 covers typical instances —
    # the old take=50 missed older items causing state miscalcs).
    seerr_results = []
    try:
        r = requests.get(
            f'{SEERR_URL}/api/v1/request',
            params={'take': 200, 'skip': 0, 'filter': 'all', 'sort': 'modified'},
            headers={'X-Api-Key': SEERR_API_KEY},
            timeout=15
        )
        if r.status_code == 200:
            seerr_results = r.json().get('results', [])
    except Exception as e:
        print(f'admin_all_requests: Seerr list fetch failed: {e}')

    # Index Seerr requests by (tmdbId, type) — keep the full request object
    # so we have access to media.status AND createdAt etc.
    seerr_by_key = {}
    for sr in seerr_results:
        media = sr.get('media') or {}
        tmdb = media.get('tmdbId')
        t = sr.get('type', media.get('mediaType'))
        if tmdb and t in ('movie', 'tv'):
            seerr_by_key[(int(tmdb), t)] = sr

    # text_keys: items already represented as text_requests — used to dedupe
    # Seerr-only entries so we don't show the same tmdbId twice.
    text_keys = set()
    for it in text_items:
        if it.get('tmdbId') and it.get('mediaType') in ('movie', 'tv'):
            text_keys.add((int(it['tmdbId']), it['mediaType']))

    # Build the set of keys that need TMDB detail enrichment (title + poster +
    # authoritative status). Every matched item gets enriched.
    detail_keys = set()
    for it in text_items:
        if it.get('tmdbId') and it.get('mediaType') in ('movie', 'tv'):
            detail_keys.add((int(it['tmdbId']), it['mediaType']))
    for key in seerr_by_key:
        if key not in text_keys:
            detail_keys.add(key)

    # Parallel fetch — typically ~30-100 calls, completes in <2s with workers=10.
    detail_map = {}
    if detail_keys:
        with ThreadPoolExecutor(max_workers=10) as ex:
            for key, info in ex.map(_fetch_tmdb_detail, detail_keys):
                if info:
                    detail_map[key] = info

    def derive_state(tmdb_id, media_type):
        """Override > TMDB detail status > Seerr-request status > 'pending'."""
        ov = overrides.get((int(tmdb_id), media_type))
        if ov and ov.get('state'):
            return ov['state'], ov.get('note', '')
        # Prefer the mediaInfo.status from the per-item detail call — it's the
        # most up-to-date "is the file in Plex" signal, and it covers items
        # not in the recent /request list.
        d = detail_map.get((int(tmdb_id), media_type))
        if d and d.get('mediaStatus'):
            return ('uploaded' if d['mediaStatus'] >= 4 else 'pending'), ''
        sr = seerr_by_key.get((int(tmdb_id), media_type))
        if sr:
            ms = (sr.get('media') or {}).get('status', 0)
            return ('uploaded' if ms >= 4 else 'pending'), ''
        return 'pending', ''

    def parse_iso_ts(s):
        if not s: return None
        try:
            return int(datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp())
        except Exception:
            return None

    out = []
    for it in text_items:
        matched = bool(it.get('tmdbId') and it.get('mediaType') in ('movie', 'tv'))
        if matched:
            key = (int(it['tmdbId']), it['mediaType'])
            state, note = derive_state(*key)
            d = detail_map.get(key) or {}
            title = d.get('title') or it.get('matchedTitle') or it.get('text') or 'Unknown'
            year = d.get('year') or it.get('matchedYear')
            poster = d.get('posterUrl')
        else:
            state, note = None, ''
            title = it.get('text') or 'Unknown'
            year = None
            poster = None
        out.append({
            'source': 'text_request',
            'id': it['id'],
            'text': it.get('text'),
            'tmdbId': it.get('tmdbId'),
            'type': it.get('mediaType'),
            'title': title,
            'year': year,
            'posterUrl': poster,
            'matchedAt': it.get('matchedAt'),
            'createdAt': it.get('createdAt'),
            'state': state,
            'note': note,
            'matched': matched,
        })

    # Seerr-only items (no corresponding text_request entry)
    for key, sr in seerr_by_key.items():
        if key in text_keys:
            continue
        tmdb_id, t = key
        state, note = derive_state(tmdb_id, t)
        d = detail_map.get(key) or {}
        created_unix = parse_iso_ts(sr.get('createdAt'))
        out.append({
            'source': 'seerr',
            'seerrRequestId': sr.get('id'),
            'tmdbId': tmdb_id,
            'type': t,
            'title': d.get('title'),
            'year': d.get('year'),
            'posterUrl': d.get('posterUrl'),
            'requestedBy': (sr.get('requestedBy') or {}).get('displayName'),
            'createdAt': created_unix,
            'state': state,
            'note': note,
            'matched': True,
        })

    return {'items': out}


@app.route('/api/admin/all-requests', methods=['GET'])
def admin_all_requests():
    """Admin: unified view of every known request — text_request entries
    (matched + unmatched) AND Seerr-originated requests not already covered by
    a text_request entry. Each item carries current displayed state (override
    > TMDB detail > Seerr request status) plus enriched title/year/poster.

    Cached 60s; invalidated on every state-changing action so the admin sees
    fresh data after their own clicks but the heavy detail fetch isn't redone
    on every page load.
    """
    err = _require_admin()
    if err: return err
    try:
        data = cached('admin_all_requests', 60, _build_admin_all_requests)
        return jsonify(data)
    except Exception as e:
        print(f'admin_all_requests failed: {e}')
        return jsonify({'items': [], 'error': str(e)}), 500

def _fetch_recently_fulfilled():
    """Fetch ALL recent Seerr requests + matched anon-requests + unmatched text requests.
    Each item carries a `state` field ('pending' or 'uploaded') so the frontend can
    render a colored footer indicating whether the request has been uploaded to Plex.
    """
    resp = requests.get(
        f'{SEERR_URL}/api/v1/request',
        # filter=all returns pending + processing + available; sort=modified surfaces
        # both newly-uploaded items and freshly-submitted requests near the top.
        # take=50 keeps the public feed reasonably sized but matches Seerr's own
        # queue length more accurately than the old take=25 (which was under-
        # counting pending items when there were many recent uploads).
        params={'take': 50, 'skip': 0, 'filter': 'all', 'sort': 'modified'},
        headers={'X-Api-Key': SEERR_API_KEY},
        timeout=10
    )
    if resp.status_code != 200:
        return {'requests': [], 'error': f'Seerr returned {resp.status_code}'}

    results_list = resp.json().get('results', [])
    all_text_requests = _load_text_requests()
    matched_anon = [r for r in all_text_requests if r.get('tmdbId') and r.get('mediaType')]
    unmatched_anon = [r for r in all_text_requests if not r.get('tmdbId')]

    with ThreadPoolExecutor(max_workers=5) as executor:
        seerr_items = list(executor.map(_fetch_detail, results_list))
        anon_items = [x for x in executor.map(_fetch_anon_detail, matched_anon) if x]

    # Unmatched anon requests have no TMDB id yet, so no poster/year. Render as
    # placeholder tiles with state='pending' so users see their text submission
    # was received even before an admin matches it.
    unmatched_items = [{
        'title': r.get('text', 'Unknown request'),
        'year': None,
        'type': 'request',  # frontend conditionals hide the Movie/TV badge for this value
        'addedAt': r.get('createdAt'),
        'posterUrl': None,
        'tmdbId': None,
        'state': 'pending',
    } for r in unmatched_anon]

    # Dedupe by (title, year, type) — prefer Seerr's record if both exist.
    seen = set()
    merged = []
    for it in seerr_items:
        soft_key = (it.get('title'), it.get('year'), it.get('type'))
        if soft_key in seen: continue
        seen.add(soft_key)
        merged.append(it)
    for it in anon_items:
        soft_key = (it.get('title'), it.get('year'), it.get('type'))
        if soft_key in seen: continue
        seen.add(soft_key)
        merged.append(it)
    for it in unmatched_items:
        soft_key = (it.get('title'), it.get('year'), it.get('type'))
        if soft_key in seen: continue
        seen.add(soft_key)
        merged.append(it)

    # Filter admin-hidden entries by (tmdbId, type). Unmatched items have no
    # tmdbId so they're never auto-hidden via this list.
    hidden = _load_hidden_fulfilled()
    if hidden:
        merged = [m for m in merged if (m.get('tmdbId'), m.get('type')) not in hidden]

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

@app.route('/api/recently-fulfilled/version', methods=['GET'])
def recently_fulfilled_version():
    """Lightweight poll endpoint — returns the version counter that bumps every
    time anything affecting /api/recently-fulfilled changes (new anon request,
    admin match/unmatch/state-change, Quick Request, hide). Clients poll this
    cheap endpoint and only do the full /api/recently-fulfilled fetch when the
    version differs from their last seen value. Near-real-time updates without
    persistent connections or chatty heavy fetches.
    """
    return jsonify({'version': _request_status_version})

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
