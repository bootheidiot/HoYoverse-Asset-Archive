import os
import re
import uuid
import json
import mimetypes
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
from botocore.client import Config
from PIL import Image
import io

app = Flask(__name__)
CORS(app)

# ── CONFIG ────────────────────────────────────────────────────────────────────
R2_ACCOUNT_ID      = os.environ.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY      = os.environ.get('R2_ACCESS_KEY')
R2_SECRET_KEY      = os.environ.get('R2_SECRET_KEY')
R2_BUCKET_NAME     = os.environ.get('R2_BUCKET_NAME')
DISCORD_WEBHOOK    = os.environ.get('DISCORD_WEBHOOK')
ARCHIVE_ACCESS_KEY = os.environ.get('ARCHIVE_ACCESS_KEY')
ARCHIVE_SECRET_KEY = os.environ.get('ARCHIVE_SECRET_KEY')
ARCHIVE_USERNAME   = os.environ.get('ARCHIVE_USERNAME', 'bootheidiot')
# ─────────────────────────────────────────────────────────────────────────────

DB_FILE = 'submissions.json'

GAME_LABELS = {
    'zzz': 'Zenless Zone Zero',
    # Add more as you expand the form
}

# ── DATABASE ──────────────────────────────────────────────────────────────────

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ── R2 ────────────────────────────────────────────────────────────────────────

def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )

# ── RESOLUTION ────────────────────────────────────────────────────────────────

def get_resolution(file_bytes, filename):
    try:
        if any(filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.avif']):
            img = Image.open(io.BytesIO(file_bytes))
            return f'{img.width}×{img.height}'
    except Exception:
        pass
    return None

# ── DISCORD ───────────────────────────────────────────────────────────────────

def notify_discord(submission):
    if not DISCORD_WEBHOOK:
        return
    game       = GAME_LABELS.get(submission['game'], submission['game'])
    event      = submission.get('eventTitle', '')
    event_type = submission.get('eventType', '')
    content    = submission.get('contentType', '')
    file_count = len(submission.get('files', []))
    payload = {
        "embeds": [{
            "title": "📥 New Submission Pending Review",
            "color": 0x9966CC,
            "fields": [
                {"name": "Game",         "value": game,         "inline": True},
                {"name": "Event",        "value": event,        "inline": True},
                {"name": "Type",         "value": event_type,   "inline": True},
                {"name": "Content",      "value": content,      "inline": True},
                {"name": "Files",        "value": str(file_count), "inline": True},
                {"name": "Submission ID","value": submission['id'], "inline": True},
            ],
            "footer": {"text": "HoYoverse Asset Archive"},
            "timestamp": submission['submittedAt']
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=5)
    except Exception:
        pass

# ── ARCHIVE.ORG — CREATE NEW ITEM ─────────────────────────────────────────────

def upload_new_ia_item(submission, meta, file_overrides):
    """
    Creates a brand new Archive.org item for this submission.
    meta: { title, identifier, description, tags, creator }
    file_overrides: list of new filenames in same order as submission['files']
    """
    results = []
    r2 = get_r2_client()
    identifier = meta['identifier']

    # Build tag list for x-archive-meta-subject
    tags = [t.strip() for t in meta.get('tags', '').split(',') if t.strip()]

    for i, file_info in enumerate(submission.get('files', [])):
        try:
            # Download from R2
            obj = r2.get_object(Bucket=R2_BUCKET_NAME, Key=file_info['r2Key'])
            file_bytes = obj['Body'].read()

            # Use overridden filename if provided
            dest_name = file_overrides[i] if i < len(file_overrides) else file_info['name']
            ia_url = f'https://s3.us.archive.org/{identifier}/{dest_name}'

            headers = {
                'Authorization':              f'LOW {ARCHIVE_ACCESS_KEY}:{ARCHIVE_SECRET_KEY}',
                'Content-Type':               file_info.get('mimeType', 'application/octet-stream'),
                'x-archive-auto-make-bucket': '1',
                'x-archive-meta-title':       meta.get('title', ''),
                'x-archive-meta-description': meta.get('description', ''),
                'x-archive-meta-creator':     meta.get('creator', 'HoYoverse'),
                'x-archive-meta-mediatype':   'movies',
                'x-archive-meta-noindex':     '0',
            }

            # Add subject tags
            for j, tag in enumerate(tags):
                key = 'x-archive-meta-subject' if j == 0 else f'x-archive-meta0{j+1}-subject'
                headers[key] = tag

            resp = requests.put(ia_url, data=file_bytes, headers=headers, timeout=300)
            results.append({'file': dest_name, 'status': resp.status_code})

        except Exception as e:
            results.append({'file': file_info.get('name', '?'), 'error': str(e)})

    return results

# ── ARCHIVE.ORG — ADD TO EXISTING ITEM ───────────────────────────────────────

def upload_to_existing_ia_item(identifier, files_data):
    """
    Adds files to an existing Archive.org item.
    files_data: list of { name, bytes, mime }
    """
    results = []
    for f in files_data:
        try:
            ia_url = f'https://s3.us.archive.org/{identifier}/{f["name"]}'
            headers = {
                'Authorization': f'LOW {ARCHIVE_ACCESS_KEY}:{ARCHIVE_SECRET_KEY}',
                'Content-Type':  f.get('mime', 'application/octet-stream'),
                'x-archive-auto-make-bucket': '0',
            }
            resp = requests.put(ia_url, data=f['bytes'], headers=headers, timeout=300)
            results.append({'file': f['name'], 'status': resp.status_code})
        except Exception as e:
            results.append({'file': f.get('name', '?'), 'error': str(e)})
    return results

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/submit', methods=['POST'])
def submit():
    game         = request.form.get('game')
    event_title  = request.form.get('eventTitle', '').strip()
    event_type   = request.form.get('eventType', '').strip()
    content_type = request.form.get('contentType', '').strip()
    files        = request.files.getlist('files')

    if not game or not event_title or not event_type or not content_type:
        return jsonify({'error': 'Missing required fields'}), 400
    if not files:
        return jsonify({'error': 'No files provided'}), 400

    submission_id  = str(uuid.uuid4())[:8].upper()
    uploaded_files = []
    r2 = get_r2_client()

    for f in files:
        file_bytes = f.read()
        safe_name  = f.filename.replace(' ', '_')
        r2_key     = f'submissions/{submission_id}/{safe_name}'
        mime       = mimetypes.guess_type(f.filename)[0] or 'application/octet-stream'
        resolution = get_resolution(file_bytes, f.filename)

        r2.put_object(
            Bucket=R2_BUCKET_NAME, Key=r2_key,
            Body=file_bytes, ContentType=mime,
        )

        url = r2.generate_presigned_url(
            'get_object',
            Params={'Bucket': R2_BUCKET_NAME, 'Key': r2_key},
            ExpiresIn=604800
        )

        uploaded_files.append({
            'name': safe_name, 'size': len(file_bytes),
            'mimeType': mime, 'resolution': resolution,
            'r2Key': r2_key, 'url': url,
        })

    submission = {
        'id':          submission_id,
        'game':        game,
        'eventTitle':  event_title,
        'eventType':   event_type,
        'contentType': content_type,
        'status':      'pending',
        'submittedAt': datetime.utcnow().isoformat() + 'Z',
        'reviewedAt':  None,
        'r2Deleted':   False,
        'files':       uploaded_files,
    }

    db = load_db()
    db.append(submission)
    save_db(db)
    notify_discord(submission)

    return jsonify({'success': True, 'id': submission_id}), 201


@app.route('/submissions', methods=['GET'])
def get_submissions():
    db = load_db()
    return jsonify(list(reversed(db)))


@app.route('/review/<submission_id>', methods=['POST'])
def review(submission_id):
    body   = request.get_json()
    action = body.get('action')

    if action not in ('approved', 'rejected'):
        return jsonify({'error': 'Invalid action'}), 400

    db  = load_db()
    sub = next((s for s in db if s['id'] == submission_id), None)

    if not sub:
        return jsonify({'error': 'Submission not found'}), 404
    if sub['status'] != 'pending':
        return jsonify({'error': 'Already reviewed'}), 409

    sub['status']     = action
    sub['reviewedAt'] = datetime.utcnow().isoformat() + 'Z'

    if action == 'approved':
        meta = {
            'title':       body.get('title', ''),
            'identifier':  body.get('identifier', ''),
            'description': body.get('description', ''),
            'tags':        body.get('tags', ''),
            'creator':     body.get('creator', 'HoYoverse'),
        }
        file_names     = body.get('fileNames', [])
        upload_results = upload_new_ia_item(sub, meta, file_names)
        sub['archiveUpload']  = upload_results
        sub['archiveMeta']    = meta
        sub['archiveFileNames'] = file_names

    save_db(db)

    # Discord notification
    if DISCORD_WEBHOOK:
        game  = GAME_LABELS.get(sub['game'], sub['game'])
        emoji = '✅' if action == 'approved' else '❌'
        ia_url = f"https://archive.org/details/{sub.get('archiveMeta', {}).get('identifier', '')}" if action == 'approved' else ''
        payload = {
            "embeds": [{
                "title": f"{emoji} Submission {action.capitalize()}",
                "color": 0x6bffb8 if action == 'approved' else 0xff6b6b,
                "fields": [
                    {"name": "ID",    "value": submission_id, "inline": True},
                    {"name": "Game",  "value": game,          "inline": True},
                    {"name": "Event", "value": sub.get('eventTitle', ''), "inline": True},
                ] + ([{"name": "Archive.org", "value": ia_url, "inline": False}] if ia_url else []),
                "footer": {"text": "HoYoverse Asset Archive"},
            }]
        }
        try:
            requests.post(DISCORD_WEBHOOK, json=payload, timeout=5)
        except Exception:
            pass

    return jsonify({'success': True, 'status': action})


@app.route('/delete-r2/<submission_id>', methods=['POST'])
def delete_r2(submission_id):
    db  = load_db()
    sub = next((s for s in db if s['id'] == submission_id), None)

    if not sub:
        return jsonify({'error': 'Submission not found'}), 404
    if sub.get('r2Deleted'):
        return jsonify({'error': 'Already deleted'}), 409

    r2 = get_r2_client()
    for file_info in sub.get('files', []):
        try:
            r2.delete_object(Bucket=R2_BUCKET_NAME, Key=file_info['r2Key'])
        except Exception:
            pass

    sub['r2Deleted'] = True
    save_db(db)
    return jsonify({'success': True})


@app.route('/ia-debug', methods=['GET'])
def ia_debug():
    """Debug endpoint to see raw Archive.org API response."""
    headers = {
        'Authorization': f'LOW {ARCHIVE_ACCESS_KEY}:{ARCHIVE_SECRET_KEY}',
    }
    results = {}

    # Test several different query approaches
    queries = {
        'uploader':        f'uploader:{ARCHIVE_USERNAME}',
        'creator':         f'creator:{ARCHIVE_USERNAME}',
        'subject_zzz':     'subject:ZZZ',
        'title_wallpaper': 'title:wallpaper AND subject:ZZZ',
        'identifier_prefix': f'identifier:{ARCHIVE_USERNAME}',
    }

    for label, q in queries.items():
        try:
            resp = requests.get(
                'https://archive.org/services/search/v1/scrape',
                params={'q': q, 'fields': 'identifier,title', 'count': 100},
                headers=headers,
                timeout=10
            )
            data = resp.json()
            results[label] = {
                'query': q,
                'status': resp.status_code,
                'total': data.get('total', 0),
                'sample': [d.get('identifier') for d in data.get('items', [])[:3]],
            }
        except Exception as e:
            results[label] = {'error': str(e)}

    return jsonify(results)


@app.route('/ia-search', methods=['GET'])
def ia_search():
    """Search the user's Archive.org uploads using authenticated API."""
    q = request.args.get('q', '').strip().lower()
    try:
        headers = {
            'Authorization': f'LOW {ARCHIVE_ACCESS_KEY}:{ARCHIVE_SECRET_KEY}',
        }

        params = {
            'q':      'subject:ZZZ AND subject:HoYoverse',
            'fields': 'identifier,title',
            'count':  100,
        }

        resp = requests.get(
            'https://archive.org/services/search/v1/scrape',
            params=params,
            headers=headers,
            timeout=15
        )
        resp.raise_for_status()
        items_raw = resp.json().get('items', [])

        items = []
        for d in items_raw:
            ident = d.get('identifier', '')
            title = d.get('title', ident)
            if not ident:
                continue
            # Filter by search query client-side
            if q and q not in title.lower() and q not in ident.lower():
                continue
            items.append({
                'identifier': ident,
                'title':      title,
                'thumb':      f'https://archive.org/services/img/{ident}',
            })
        return jsonify(items)
    except Exception as e:
        # Always return 200 with empty list to avoid CORS issues on 500
        app.logger.error(f'ia-search error: {e}')
        return jsonify([]), 200


@app.route('/ia-add', methods=['POST'])
def ia_add():
    """Upload files directly to an existing Archive.org item."""
    identifier = request.form.get('identifier')
    files      = request.files.getlist('files')

    if not identifier or not files:
        return jsonify({'error': 'Missing identifier or files'}), 400

    files_data = []
    for f in files:
        file_bytes = f.read()
        mime = mimetypes.guess_type(f.filename)[0] or 'application/octet-stream'
        files_data.append({'name': f.filename, 'bytes': file_bytes, 'mime': mime})

    results = upload_to_existing_ia_item(identifier, files_data)
    return jsonify({'success': True, 'results': results})


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
