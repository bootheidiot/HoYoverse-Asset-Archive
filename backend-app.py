import os
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
CORS(app)  # Allow requests from your GitHub Pages site

# ── CONFIG (set these as environment variables) ────────────────────────────────
R2_ACCOUNT_ID      = os.environ.get('R2_ACCOUNT_ID')
R2_ACCESS_KEY      = os.environ.get('R2_ACCESS_KEY')
R2_SECRET_KEY      = os.environ.get('R2_SECRET_KEY')
R2_BUCKET_NAME     = os.environ.get('R2_BUCKET_NAME')
DISCORD_WEBHOOK    = os.environ.get('DISCORD_WEBHOOK')
ARCHIVE_ACCESS_KEY = os.environ.get('ARCHIVE_ACCESS_KEY')
ARCHIVE_SECRET_KEY = os.environ.get('ARCHIVE_SECRET_KEY')
ARCHIVE_IDENTIFIER = os.environ.get('ARCHIVE_IDENTIFIER')  # your archive.org item identifier
# ──────────────────────────────────────────────────────────────────────────────

DB_FILE = 'submissions.json'

GAME_LABELS = {
    'zzz': 'Zenless Zone Zero',
    # Add more as you expand the form
}

TYPE_LABELS = {
    'limited-time-events': 'Limited Time Events',
    'misc-marketing-material': 'Misc Marketing Material',
    # Add more as you expand the form
}

# ── DATABASE HELPERS ──────────────────────────────────────────────────────────

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ── R2 CLIENT ─────────────────────────────────────────────────────────────────

def get_r2_client():
    return boto3.client(
        's3',
        endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )

def get_public_url(key):
    # If you set a public domain on your R2 bucket, replace this with your domain
    return f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com/{R2_BUCKET_NAME}/{key}'

# ── IMAGE RESOLUTION ──────────────────────────────────────────────────────────

def get_resolution(file_bytes, filename):
    try:
        if any(filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.avif']):
            img = Image.open(io.BytesIO(file_bytes))
            return f'{img.width}×{img.height}'
    except Exception:
        pass
    return None

# ── DISCORD NOTIFICATION ──────────────────────────────────────────────────────

def notify_discord(submission):
    if not DISCORD_WEBHOOK:
        return
    game  = GAME_LABELS.get(submission['game'], submission['game'])
    ctype = TYPE_LABELS.get(submission['contentType'], submission['contentType'])
    file_count = len(submission.get('files', []))
    payload = {
        "embeds": [{
            "title": "📥 New Submission Pending Review",
            "color": 0x2c4a6e,
            "fields": [
                {"name": "Game",         "value": game,              "inline": True},
                {"name": "Content Type", "value": ctype,             "inline": True},
                {"name": "Files",        "value": str(file_count),   "inline": True},
                {"name": "Submission ID","value": submission['id'],   "inline": False},
            ],
            "footer": {"text": "HoYoverse Asset Archive"},
            "timestamp": submission['submittedAt']
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK, json=payload, timeout=5)
    except Exception:
        pass

# ── ARCHIVE.ORG UPLOAD ────────────────────────────────────────────────────────

def upload_to_archive(submission):
    """Upload approved files to archive.org via their S3-like API."""
    results = []
    for file_info in submission.get('files', []):
        try:
            # Download from R2
            r2 = get_r2_client()
            obj = r2.get_object(Bucket=R2_BUCKET_NAME, Key=file_info['r2Key'])
            file_bytes = obj['Body'].read()

            # Upload to Archive.org
            game  = submission['game']
            ctype = submission['contentType']
            dest_key = f"{game}/{ctype}/{file_info['name']}"

            ia_url = f'https://s3.us.archive.org/{ARCHIVE_IDENTIFIER}/{dest_key}'
            headers = {
                'Authorization': f'LOW {ARCHIVE_ACCESS_KEY}:{ARCHIVE_SECRET_KEY}',
                'Content-Type': file_info.get('mimeType', 'application/octet-stream'),
                'x-archive-auto-make-bucket': '1',
                'x-archive-meta-mediatype': 'image',
                'x-archive-meta-subject': f'HoYoverse;{GAME_LABELS.get(game, game)};{TYPE_LABELS.get(ctype, ctype)}',
            }
            resp = requests.put(ia_url, data=file_bytes, headers=headers, timeout=120)
            results.append({'file': file_info['name'], 'status': resp.status_code})
        except Exception as e:
            results.append({'file': file_info.get('name', '?'), 'error': str(e)})
    return results

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/submit', methods=['POST'])
def submit():
    game         = request.form.get('game')
    content_type = request.form.get('contentType')
    files        = request.files.getlist('files')

    if not game or not content_type:
        return jsonify({'error': 'Missing game or contentType'}), 400
    if not files:
        return jsonify({'error': 'No files provided'}), 400

    submission_id = str(uuid.uuid4())[:8].upper()
    uploaded_files = []
    r2 = get_r2_client()

    for f in files:
        file_bytes = f.read()
        safe_name  = f.filename.replace(' ', '_')
        r2_key     = f'submissions/{submission_id}/{safe_name}'
        mime       = mimetypes.guess_type(f.filename)[0] or 'application/octet-stream'
        resolution = get_resolution(file_bytes, f.filename)

        # Upload to Cloudflare R2
        r2.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=r2_key,
            Body=file_bytes,
            ContentType=mime,
        )

        # Generate a pre-signed URL valid for 7 days for dashboard preview
        url = r2.generate_presigned_url(
            'get_object',
            Params={'Bucket': R2_BUCKET_NAME, 'Key': r2_key},
            ExpiresIn=604800
        )

        uploaded_files.append({
            'name':       safe_name,
            'size':       len(file_bytes),
            'mimeType':   mime,
            'resolution': resolution,
            'r2Key':      r2_key,
            'url':        url,
        })

    submission = {
        'id':          submission_id,
        'game':        game,
        'contentType': content_type,
        'status':      'pending',
        'submittedAt': datetime.utcnow().isoformat() + 'Z',
        'reviewedAt':  None,
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
    # Return newest first
    return jsonify(list(reversed(db)))


@app.route('/review/<submission_id>', methods=['POST'])
def review(submission_id):
    body   = request.get_json()
    action = body.get('action')  # 'approved' or 'rejected'

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
        upload_results = upload_to_archive(sub)
        sub['archiveUpload'] = upload_results

    save_db(db)

    # Notify Discord of outcome
    if DISCORD_WEBHOOK:
        game  = GAME_LABELS.get(sub['game'], sub['game'])
        emoji = '✅' if action == 'approved' else '❌'
        payload = {
            "embeds": [{
                "title": f"{emoji} Submission {action.capitalize()}",
                "color": 0x2d6a4f if action == 'approved' else 0xc0392b,
                "fields": [
                    {"name": "ID",   "value": submission_id, "inline": True},
                    {"name": "Game", "value": game,          "inline": True},
                ],
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
        return jsonify({'error': 'Already deleted from R2'}), 409

    r2 = get_r2_client()
    errors = []
    for file_info in sub.get('files', []):
        try:
            r2.delete_object(Bucket=R2_BUCKET_NAME, Key=file_info['r2Key'])
        except Exception as e:
            errors.append({'file': file_info.get('name', '?'), 'error': str(e)})

    if errors:
        return jsonify({'error': 'Some files could not be deleted', 'details': errors}), 500

    sub['r2Deleted'] = True
    save_db(db)
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
