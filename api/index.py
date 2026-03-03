from http.server import BaseHTTPRequestHandler
import json
import time
import random
import string
import urllib.request
import urllib.parse
import ssl

# SSL fix untuk Vercel
ssl._create_default_https_context = ssl._create_unverified_context

MAIL_API = "https://api.mail.tm"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Set CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        
        # API Test
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
        
        # Health check
        elif self.path == "/api/health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {"status": "healthy", "api": "connected"}
            self.wfile.write(json.dumps(response).encode())
            return
        
        # Get domains
        elif self.path == "/api/domains":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                req = urllib.request.Request(f"{MAIL_API}/domains")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    domains = [d.get('domain') for d in data.get('member', [])]
                    
                    response = {
                        "success": True,
                        "domains": domains
                    }
            except Exception as e:
                response = {
                    "success": False,
                    "message": str(e)
                }
            
            self.wfile.write(json.dumps(response).encode())
            return
        
        # Get inbox messages
        elif self.path.startswith("/api/inbox/"):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                # Parse path: /api/inbox/email?token=xxx
                parts = self.path.split('/')
                email = parts[3] if len(parts) > 3 else ''
                
                from urllib.parse import urlparse, parse_qs
                query = parse_qs(urlparse(self.path).query)
                token = query.get('token', [''])[0]
                
                if not token:
                    response = {"success": False, "message": "Token required"}
                    self.wfile.write(json.dumps(response).encode())
                    return
                
                # Get messages from Mail.tm
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
        
        # Get single message
        elif self.path.startswith("/api/message/"):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                # Parse path: /api/message/email/message_id?token=xxx
                parts = self.path.split('/')
                email = parts[3] if len(parts) > 3 else ''
                message_id = parts[4] if len(parts) > 4 else ''
                
                from urllib.parse import urlparse, parse_qs
                query = parse_qs(urlparse(self.path).query)
                token = query.get('token', [''])[0]
                
                if not token:
                    response = {"success": False, "message": "Token required"}
                    self.wfile.write(json.dumps(response).encode())
                    return
                
                # Get message from Mail.tm
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
            response = {"success": False, "message": "Not found"}
            self.wfile.write(json.dumps(response).encode())
            return
    
    def do_POST(self):
        # Set CORS
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        
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
                # 1. Get domains from Mail.tm
                domains_req = urllib.request.Request(f"{MAIL_API}/domains")
                with urllib.request.urlopen(domains_req, timeout=10) as resp:
                    domains_data = json.loads(resp.read().decode())
                    domains = domains_data.get('member', [])
                    
                    if not domains:
                        raise Exception("No domains available")
                    
                    domain = domains[0].get('domain')
                    email = f"{prefix}@{domain}"
                    
                    # 2. Create account
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
                        if acc_resp.getcode() in [200, 201]:
                            # 3. Get token
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
                
                # Fallback
                raise Exception("Failed to create account")
                
            except Exception as e:
                # Return error
                response = {
                    "success": False,
                    "message": f"Error: {str(e)}"
                }
                
                self.send_response(500)
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