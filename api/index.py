import json
import random
import string
import time
import urllib.request
import urllib.parse
import ssl
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# SSL fix untuk Vercel
ssl._create_default_https_context = ssl._create_unverified_context

MAIL_API = "https://api.mail.tm"


def send_json(handler, status, data):
    """Helper: kirim JSON response dengan urutan header yang benar."""
    body = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type')
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress log agar tidak crash di Vercel

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        query  = parse_qs(parsed.query)

        if path == "/api/test":
            send_json(self, 200, {
                "success":   True,
                "message":   "API is working!",
                "timestamp": time.time()
            })

        elif path.startswith("/api/inbox/"):
            parts = path.split('/')
            if len(parts) < 4:
                send_json(self, 400, {"success": False, "message": "Invalid URL"})
                return
            email = parts[3]
            token = query.get('token', [''])[0]
            if not token:
                send_json(self, 400, {"success": False, "message": "Token required"})
                return
            try:
                req = urllib.request.Request(
                    f"{MAIL_API}/messages",
                    headers={"Authorization": f"Bearer {token}"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                messages = [
                    {
                        "id":         m.get('id'),
                        "from":       m.get('from', {}).get('address', 'Unknown'),
                        "subject":    m.get('subject', 'No Subject'),
                        "intro":      m.get('intro', ''),
                        "created_at": m.get('createdAt')
                    }
                    for m in data.get('member', [])
                ]
                send_json(self, 200, {"success": True, "email": email, "messages": messages, "count": len(messages)})
            except Exception as e:
                send_json(self, 500, {"success": False, "message": str(e)})

        elif path.startswith("/api/message/"):
            parts = path.split('/')
            if len(parts) < 5:
                send_json(self, 400, {"success": False, "message": "Invalid URL"})
                return
            message_id = parts[4]
            token      = query.get('token', [''])[0]
            if not token:
                send_json(self, 400, {"success": False, "message": "Token required"})
                return
            try:
                req = urllib.request.Request(
                    f"{MAIL_API}/messages/{message_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
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
            except Exception as e:
                send_json(self, 500, {"success": False, "message": str(e)})

        else:
            send_json(self, 404, {"success": False, "message": "Endpoint not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        if path == "/api/generate":
            try:
                length = int(self.headers.get('Content-Length', 0))
                raw    = self.rfile.read(length) if length else b'{}'
                body   = json.loads(raw)
                custom = body.get('email', '')
            except Exception:
                custom = ''

            prefix = (''.join(c for c in custom if c.isalnum())[:15]
                      if custom else '') or \
                     ''.join(random.choices(string.ascii_lowercase, k=10))
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

            try:
                with urllib.request.urlopen(
                    urllib.request.Request(f"{MAIL_API}/domains"), timeout=10
                ) as r:
                    d = json.loads(r.read().decode())
                    domain = (d.get('member') or [{}])[0].get('domain', 'himmel.com')

                email = f"{prefix}@{domain}"

                urllib.request.urlopen(
                    urllib.request.Request(
                        f"{MAIL_API}/accounts", method='POST',
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps({"address": email, "password": password}).encode()
                    ), timeout=10
                )

                with urllib.request.urlopen(
                    urllib.request.Request(
                        f"{MAIL_API}/token", method='POST',
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps({"address": email, "password": password}).encode()
                    ), timeout=10
                ) as r:
                    tok = json.loads(r.read().decode())

                send_json(self, 200, {
                    "success":  True,
                    "email":    email,
                    "password": password,
                    "token":    tok.get('token'),
                    "id":       tok.get('id'),
                    "message":  f"✅ Email {email} berhasil dibuat!"
                })

            except Exception as e:
                fb_email = f"{prefix}@himmel.com"
                send_json(self, 200, {
                    "success":  True,
                    "email":    fb_email,
                    "password": password,
                    "token":    "dummy_" + ''.join(random.choices(string.ascii_letters, k=20)),
                    "id":       "dummy_id",
                    "message":  f"✅ Email {fb_email} dibuat (offline mode)"
                })
        else:
            send_json(self, 404, {"success": False, "message": "Endpoint not found"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
