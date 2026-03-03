import json
import random
import string
import time
import urllib.request
import urllib.error
import ssl
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

ssl._create_default_https_context = ssl._create_unverified_context

MAIL_API = "https://api.mail.tm"


def send_json(h, status, data):
    body = json.dumps(data, ensure_ascii=False).encode()
    h.send_response(status)
    h.send_header('Content-Type', 'application/json; charset=utf-8')
    h.send_header('Content-Length', str(len(body)))
    h.send_header('Access-Control-Allow-Origin', '*')
    h.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    h.send_header('Access-Control-Allow-Headers', 'Content-Type')
    h.end_headers()
    h.wfile.write(body)


def api_request(url, method='GET', payload=None, token=None, timeout=15):
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0'
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'

    data = json.dumps(payload).encode() if payload else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=method)

    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def get_domain():
    """Ambil domain pertama dari Mail.tm."""
    data    = api_request(f"{MAIL_API}/domains")
    members = data.get('hydra:member', data.get('member', []))
    if not members:
        raise Exception("Tidak ada domain tersedia di Mail.tm")
    return members[0]['domain']


class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        query  = parse_qs(parsed.query)

        # ===== TEST =====
        if path == "/api/test":
            try:
                domain = get_domain()
                send_json(self, 200, {
                    "success":   True,
                    "message":   "API is working!",
                    "domain":    domain,
                    "timestamp": time.time()
                })
            except Exception as e:
                send_json(self, 500, {"success": False, "message": str(e)})

        # ===== INBOX =====
        elif path.startswith("/api/inbox/"):
            parts = path.strip('/').split('/')
            if len(parts) < 3:
                send_json(self, 400, {"success": False, "message": "Invalid URL"})
                return

            email = parts[2]
            token = query.get('token', [''])[0]

            if not token:
                send_json(self, 400, {"success": False, "message": "Token required"})
                return

            try:
                data = api_request(f"{MAIL_API}/messages", token=token)
                members = data.get('hydra:member', data.get('member', []))
                messages = [
                    {
                        "id":         msg.get('id'),
                        "from":       msg.get('from', {}).get('address', 'Unknown'),
                        "subject":    msg.get('subject', 'No Subject'),
                        "intro":      msg.get('intro', ''),
                        "created_at": msg.get('createdAt')
                    }
                    for msg in members
                ]
                send_json(self, 200, {
                    "success":  True,
                    "email":    email,
                    "messages": messages,
                    "count":    len(messages)
                })
            except urllib.error.HTTPError as e:
                body = e.read().decode() if hasattr(e, 'read') else ''
                send_json(self, e.code, {"success": False, "message": f"Mail.tm error {e.code}: {body}"})
            except Exception as e:
                send_json(self, 500, {"success": False, "message": str(e)})

        # ===== SINGLE MESSAGE =====
        elif path.startswith("/api/message/"):
            parts = path.strip('/').split('/')
            if len(parts) < 4:
                send_json(self, 400, {"success": False, "message": "Invalid URL"})
                return

            message_id = parts[3]
            token      = query.get('token', [''])[0]

            if not token:
                send_json(self, 400, {"success": False, "message": "Token required"})
                return

            try:
                data = api_request(f"{MAIL_API}/messages/{message_id}", token=token)
                send_json(self, 200, {
                    "success": True,
                    "message": {
                        "id":         data.get('id'),
                        "from":       data.get('from', {}).get('address'),
                        "to":         data.get('to', [{}])[0].get('address') if data.get('to') else None,
                        "subject":    data.get('subject', 'No Subject'),
                        "text":       data.get('text', ''),
                        "html":       data.get('html', ''),
                        "created_at": data.get('createdAt')
                    }
                })
            except urllib.error.HTTPError as e:
                body = e.read().decode() if hasattr(e, 'read') else ''
                send_json(self, e.code, {"success": False, "message": f"Mail.tm error {e.code}: {body}"})
            except Exception as e:
                send_json(self, 500, {"success": False, "message": str(e)})

        else:
            send_json(self, 404, {"success": False, "message": "Endpoint not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        # ===== GENERATE EMAIL =====
        if path == "/api/generate":
            try:
                length = int(self.headers.get('Content-Length', 0))
                raw    = self.rfile.read(length) if length else b'{}'
                body   = json.loads(raw)
                custom = body.get('email', '').strip()
            except Exception:
                custom = ''

            # Bersihkan prefix
            if custom:
                prefix = ''.join(c for c in custom if c.isalnum() or c in '-_.')[:30]
            if not custom or not prefix:
                prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

            password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

            try:
                # 1. Ambil domain
                domain = get_domain()
                email  = f"{prefix}@{domain}"

                # 2. Buat akun
                api_request(f"{MAIL_API}/accounts", method='POST', payload={
                    "address":  email,
                    "password": password
                })

                # 3. Ambil token
                tok = api_request(f"{MAIL_API}/token", method='POST', payload={
                    "address":  email,
                    "password": password
                })

                send_json(self, 200, {
                    "success":  True,
                    "email":    email,
                    "password": password,
                    "token":    tok.get('token'),
                    "id":       tok.get('id'),
                    "message":  f"✅ Email {email} berhasil dibuat!"
                })

            except urllib.error.HTTPError as e:
                try:
                    err_body = json.loads(e.read().decode())
                    detail   = err_body.get('detail') or err_body.get('message') or str(err_body)
                except Exception:
                    detail = f"HTTP {e.code}"
                send_json(self, 500, {"success": False, "message": f"Gagal membuat email: {detail}"})

            except Exception as e:
                send_json(self, 500, {"success": False, "message": f"Error: {str(e)}"})

        else:
            send_json(self, 404, {"success": False, "message": "Endpoint not found"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
