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

# ── Provider configs ──────────────────────────────────────────────────────────
MAILTM_API    = "https://api.mail.tm"
GUERRILLA_API = "https://api.guerrillamail.com/ajax.php"
MAILDROP_API  = "https://maildrop.cc/v2/mailbox"

PREFER_DOMAIN = "dollicons.com"   # domain Mail.tm favorit


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

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


def http_get(url, headers=None, timeout=12):
    req = urllib.request.Request(url, headers={
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0',
        **(headers or {})
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def http_post(url, payload, headers=None, timeout=12):
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data, headers={
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'Mozilla/5.0',
        **(headers or {})
    }, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def random_prefix(n=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER 1 — Mail.tm
# ══════════════════════════════════════════════════════════════════════════════

def mailtm_get_domain():
    data    = http_get(f"{MAILTM_API}/domains")
    members = data if isinstance(data, list) else data.get('hydra:member', data.get('member', []))
    if not members:
        raise Exception("No domains on Mail.tm")
    domains = [(m['domain'] if isinstance(m, dict) else m) for m in members]
    return PREFER_DOMAIN if PREFER_DOMAIN in domains else domains[0]


def mailtm_generate(prefix):
    domain   = mailtm_get_domain()
    email    = f"{prefix}@{domain}"
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    http_post(f"{MAILTM_API}/accounts", {"address": email, "password": password})
    tok = http_post(f"{MAILTM_API}/token",    {"address": email, "password": password})
    return {
        "provider": "mailtm",
        "email":    email,
        "token":    tok.get('token'),
        "id":       tok.get('id'),
        "password": password,
    }


def mailtm_inbox(token):
    data    = http_get(f"{MAILTM_API}/messages", headers={"Authorization": f"Bearer {token}"})
    members = data if isinstance(data, list) else data.get('hydra:member', data.get('member', []))
    return [
        {
            "id":         m.get('id'),
            "from":       m.get('from', {}).get('address', 'Unknown'),
            "subject":    m.get('subject', 'No Subject'),
            "intro":      m.get('intro', ''),
            "created_at": m.get('createdAt'),
        }
        for m in members
    ]


def mailtm_message(message_id, token):
    d = http_get(f"{MAILTM_API}/messages/{message_id}", headers={"Authorization": f"Bearer {token}"})
    return {
        "id":         d.get('id'),
        "from":       d.get('from', {}).get('address'),
        "to":         d.get('to', [{}])[0].get('address') if d.get('to') else None,
        "subject":    d.get('subject', 'No Subject'),
        "text":       d.get('text', ''),
        "html":       d.get('html', ''),
        "created_at": d.get('createdAt'),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER 2 — Guerrilla Mail (no token needed, session-based)
# ══════════════════════════════════════════════════════════════════════════════

def guerrilla_generate(prefix):
    # set_email_user pakai prefix kita
    data = http_get(
        f"{GUERRILLA_API}?f=set_email_user&email_user={prefix}&lang=en"
    )
    email = data.get('email_addr', f"{prefix}@guerrillamailblock.com")
    sid   = data.get('sid_token', '')
    return {
        "provider": "guerrilla",
        "email":    email,
        "token":    sid,      # sid_token dipakai sebagai "token" kita
        "id":       prefix,
        "password": None,
    }


def guerrilla_inbox(token, seq=0):
    data = http_get(
        f"{GUERRILLA_API}?f=get_email_list&offset=0&seq={seq}&sid_token={token}"
    )
    msgs = data.get('list', [])
    return [
        {
            "id":         m.get('mail_id'),
            "from":       m.get('mail_from', 'Unknown'),
            "subject":    m.get('mail_subject', 'No Subject'),
            "intro":      m.get('mail_excerpt', ''),
            "created_at": m.get('mail_timestamp'),
        }
        for m in msgs
    ]


def guerrilla_message(message_id, token):
    data = http_get(
        f"{GUERRILLA_API}?f=fetch_email&email_id={message_id}&sid_token={token}"
    )
    return {
        "id":         data.get('mail_id'),
        "from":       data.get('mail_from'),
        "to":         data.get('mail_recipient'),
        "subject":    data.get('mail_subject', 'No Subject'),
        "text":       data.get('mail_body', ''),
        "html":       data.get('mail_body', ''),
        "created_at": data.get('mail_timestamp'),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER 3 — Maildrop (no auth, inbox public by mailbox name)
# ══════════════════════════════════════════════════════════════════════════════

def maildrop_generate(prefix):
    email = f"{prefix}@maildrop.cc"
    # Maildrop tidak perlu registrasi sama sekali
    return {
        "provider": "maildrop",
        "email":    email,
        "token":    prefix,   # nama mailbox = "token"
        "id":       prefix,
        "password": None,
    }


def maildrop_inbox(mailbox):
    data = http_get(f"{MAILDROP_API}/{mailbox}")
    msgs = data if isinstance(data, list) else data.get('messages', [])
    return [
        {
            "id":         m.get('id'),
            "from":       m.get('from', 'Unknown'),
            "subject":    m.get('subject', 'No Subject'),
            "intro":      m.get('intro', ''),
            "created_at": m.get('date'),
        }
        for m in msgs
    ]


def maildrop_message(mailbox, message_id):
    data = http_get(f"{MAILDROP_API}/{mailbox}/{message_id}")
    return {
        "id":         data.get('id'),
        "from":       data.get('from'),
        "to":         data.get('to'),
        "subject":    data.get('subject', 'No Subject'),
        "text":       data.get('body', ''),
        "html":       data.get('html', data.get('body', '')),
        "created_at": data.get('date'),
    }


# ══════════════════════════════════════════════════════════════════════════════
# GENERATE — fallback chain Mail.tm → Guerrilla → Maildrop
# ══════════════════════════════════════════════════════════════════════════════

def generate_email(custom_prefix=''):
    if custom_prefix:
        prefix = ''.join(c for c in custom_prefix if c.isalnum() or c in '-_.')[:30]
    else:
        prefix = ''
    if not prefix:
        prefix = random_prefix()

    errors = []

    # 1. Mail.tm
    try:
        result = mailtm_generate(prefix)
        result['message'] = f"✅ Email {result['email']} berhasil dibuat!"
        return result
    except Exception as e:
        errors.append(f"Mail.tm: {e}")

    # 2. Guerrilla Mail
    try:
        result = guerrilla_generate(prefix)
        result['message'] = f"✅ Email {result['email']} berhasil dibuat! (via Guerrilla)"
        return result
    except Exception as e:
        errors.append(f"Guerrilla: {e}")

    # 3. Maildrop
    try:
        result = maildrop_generate(prefix)
        result['message'] = f"✅ Email {result['email']} berhasil dibuat! (via Maildrop)"
        return result
    except Exception as e:
        errors.append(f"Maildrop: {e}")

    raise Exception("Semua provider gagal: " + " | ".join(errors))


# ══════════════════════════════════════════════════════════════════════════════
# HANDLER
# ══════════════════════════════════════════════════════════════════════════════

class handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        query  = parse_qs(parsed.query)

        # ===== TEST =====
        if path == "/api/test":
            results = {}
            try:
                results['mailtm_domain'] = mailtm_get_domain()
                results['mailtm'] = 'ok'
            except Exception as e:
                results['mailtm'] = str(e)
            try:
                http_get(f"{GUERRILLA_API}?f=get_email_address&lang=en", timeout=5)
                results['guerrilla'] = 'ok'
            except Exception as e:
                results['guerrilla'] = str(e)
            results['maildrop'] = 'ok (no-auth)'
            send_json(self, 200, {"success": True, "providers": results, "timestamp": time.time()})

        # ===== INBOX =====
        elif path.startswith("/api/inbox/"):
            parts    = path.strip('/').split('/')
            email    = parts[2] if len(parts) > 2 else ''
            token    = query.get('token', [''])[0]
            provider = query.get('provider', ['mailtm'])[0]

            if not token:
                send_json(self, 400, {"success": False, "message": "Token required"})
                return

            try:
                if provider == 'guerrilla':
                    messages = guerrilla_inbox(token)
                elif provider == 'maildrop':
                    messages = maildrop_inbox(token)  # token = mailbox name
                else:
                    messages = mailtm_inbox(token)

                send_json(self, 200, {
                    "success":  True,
                    "email":    email,
                    "messages": messages,
                    "count":    len(messages),
                    "provider": provider,
                })
            except urllib.error.HTTPError as e:
                body = e.read().decode() if hasattr(e, 'read') else ''
                send_json(self, e.code, {"success": False, "message": f"Error {e.code}: {body}"})
            except Exception as e:
                send_json(self, 500, {"success": False, "message": str(e)})

        # ===== SINGLE MESSAGE =====
        elif path.startswith("/api/message/"):
            parts      = path.strip('/').split('/')
            message_id = parts[3] if len(parts) > 3 else ''
            token      = query.get('token', [''])[0]
            provider   = query.get('provider', ['mailtm'])[0]
            mailbox    = parts[2] if len(parts) > 2 else ''

            if not token:
                send_json(self, 400, {"success": False, "message": "Token required"})
                return

            try:
                if provider == 'guerrilla':
                    msg = guerrilla_message(message_id, token)
                elif provider == 'maildrop':
                    msg = maildrop_message(mailbox.split('@')[0], message_id)
                else:
                    msg = mailtm_message(message_id, token)

                send_json(self, 200, {"success": True, "message": msg})
            except urllib.error.HTTPError as e:
                body = e.read().decode() if hasattr(e, 'read') else ''
                send_json(self, e.code, {"success": False, "message": f"Error {e.code}: {body}"})
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
                custom = body.get('email', '').strip()
            except Exception:
                custom = ''

            try:
                result = generate_email(custom)
                send_json(self, 200, {"success": True, **result})
            except Exception as e:
                send_json(self, 500, {"success": False, "message": str(e)})
        else:
            send_json(self, 404, {"success": False, "message": "Endpoint not found"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
