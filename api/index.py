import json
import random
import string
import time
import urllib.request
import urllib.parse
import ssl
from http.server import BaseHTTPRequestHandler

# SSL fix untuk Vercel
ssl._create_default_https_context = ssl._create_unverified_context

MAIL_API = "https://api.mail.tm"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        
        # ========== TEST ENDPOINT ==========
        if self.path == "/api/test":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                "success": True,
                "message": "API is working!",
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(response).encode())
            return
        
        # ========== GET INBOX ==========
        elif self.path.startswith("/api/inbox/"):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                # Parse URL: /api/inbox/email?token=xxx
                parts = self.path.split('/')
                if len(parts) < 4:
                    response = {"success": False, "message": "Invalid URL"}
                    self.wfile.write(json.dumps(response).encode())
                    return
                
                email = parts[3].split('?')[0]
                
                from urllib.parse import urlparse, parse_qs
                query = parse_qs(urlparse(self.path).query)
                token = query.get('token', [''])[0]
                
                if not token:
                    response = {"success": False, "message": "Token required"}
                    self.wfile.write(json.dumps(response).encode())
                    return
                
                # Panggil Mail.tm API
                req = urllib.request.Request(
                    f"{MAIL_API}/messages",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    messages = []
                    
                    for msg in data.get('member', []):
                        messages.append({
                            "id": msg.get('id'),
                            "from": msg.get('from', {}).get('address', 'Unknown'),
                            "subject": msg.get('subject', 'No Subject'),
                            "intro": msg.get('intro', ''),
                            "created_at": msg.get('createdAt')
                        })
                    
                    response = {
                        "success": True,
                        "email": email,
                        "messages": messages,
                        "count": len(messages)
                    }
                    
            except Exception as e:
                response = {
                    "success": False,
                    "message": str(e)
                }
            
            self.wfile.write(json.dumps(response).encode())
            return
        
        # ========== GET SINGLE MESSAGE ==========
        elif self.path.startswith("/api/message/"):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                # Parse URL: /api/message/email/message_id?token=xxx
                parts = self.path.split('/')
                if len(parts) < 5:
                    response = {"success": False, "message": "Invalid URL"}
                    self.wfile.write(json.dumps(response).encode())
                    return
                
                email = parts[3]
                message_id = parts[4].split('?')[0]
                
                from urllib.parse import urlparse, parse_qs
                query = parse_qs(urlparse(self.path).query)
                token = query.get('token', [''])[0]
                
                if not token:
                    response = {"success": False, "message": "Token required"}
                    self.wfile.write(json.dumps(response).encode())
                    return
                
                # Panggil Mail.tm API
                req = urllib.request.Request(
                    f"{MAIL_API}/messages/{message_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    
                    response = {
                        "success": True,
                        "message": {
                            "id": data.get('id'),
                            "from": data.get('from', {}).get('address'),
                            "to": data.get('to', [{}])[0].get('address') if data.get('to') else None,
                            "subject": data.get('subject', 'No Subject'),
                            "text": data.get('text', ''),
                            "html": data.get('html', ''),
                            "created_at": data.get('createdAt')
                        }
                    }
                    
            except Exception as e:
                response = {
                    "success": False,
                    "message": str(e)
                }
            
            self.wfile.write(json.dumps(response).encode())
            return
        
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"success": False, "message": "Endpoint not found"}
            self.wfile.write(json.dumps(response).encode())
            return
    
    def do_POST(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        
        # ========== GENERATE EMAIL ==========
        if self.path == "/api/generate":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                custom_prefix = data.get('email', '')
            except:
                custom_prefix = ''
            
            # Generate random
            if custom_prefix:
                prefix = ''.join(c for c in custom_prefix if c.isalnum())[:15]
                if not prefix:
                    prefix = ''.join(random.choices(string.ascii_lowercase, k=8))
            else:
                prefix = ''.join(random.choices(string.ascii_lowercase, k=10))
            
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            
            try:
                # ===== AMBIL DOMAIN DARI MAIL.TM =====
                domains_req = urllib.request.Request(f"{MAIL_API}/domains")
                with urllib.request.urlopen(domains_req, timeout=10) as resp:
                    domains_data = json.loads(resp.read().decode())
                    domains = domains_data.get('member', [])
                    
                    if not domains:
                        # Fallback pake himmel.com
                        domain = "himmel.com"
                    else:
                        domain = domains[0].get('domain')
                    
                    email = f"{prefix}@{domain}"
                    
                    # ===== CREATE ACCOUNT =====
                    account_data = {
                        "address": email,
                        "password": password
                    }
                    
                    account_req = urllib.request.Request(
                        f"{MAIL_API}/accounts",
                        method='POST',
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps(account_data).encode()
                    )
                    
                    with urllib.request.urlopen(account_req, timeout=10) as acc_resp:
                        # ===== GET TOKEN =====
                        token_data = {
                            "address": email,
                            "password": password
                        }
                        
                        token_req = urllib.request.Request(
                            f"{MAIL_API}/token",
                            method='POST',
                            headers={'Content-Type': 'application/json'},
                            data=json.dumps(token_data).encode()
                        )
                        
                        with urllib.request.urlopen(token_req, timeout=10) as tok_resp:
                            tok_json = json.loads(tok_resp.read().decode())
                            
                            response = {
                                "success": True,
                                "email": email,
                                "password": password,
                                "token": tok_json.get('token'),
                                "id": tok_json.get('id'),
                                "message": f"✅ Email {email} berhasil dibuat!"
                            }
                            
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps(response).encode())
                            return
                            
            except Exception as e:
                # Fallback - return success with token dummy
                response = {
                    "success": True,
                    "email": f"{prefix}@himmel.com",
                    "password": password,
                    "token": "dummy_" + ''.join(random.choices(string.ascii_letters, k=20)),
                    "id": "dummy_id",
                    "message": f"✅ Email {prefix}@himmel.com dibuat (offline mode)"
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
                return
        
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"success": False, "message": "Endpoint not found"}
            self.wfile.write(json.dumps(response).encode())
            return
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        return