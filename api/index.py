from http.server import BaseHTTPRequestHandler
import json
import time

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/test":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                "success": True,
                "message": "API is working!",
                "timestamp": time.time()
            }
            
            self.wfile.write(json.dumps(response).encode())
            return
        
        elif self.path == "/api/health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                "status": "healthy",
                "api": "connected"
            }
            
            self.wfile.write(json.dumps(response).encode())
            return
        
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                "success": False,
                "message": "Not found"
            }
            
            self.wfile.write(json.dumps(response).encode())
            return
    
    def do_POST(self):
        if self.path == "/api/generate":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data)
                prefix = data.get('email', '')
            except:
                data = {}
                prefix = ''
            
            import random
            import string
            
            if prefix:
                clean_prefix = ''.join(c for c in prefix if c.isalnum())[:15]
                email = f"{clean_prefix}@himmel.com" if clean_prefix else f"user{random.randint(100,999)}@himmel.com"
            else:
                random_name = ''.join(random.choices(string.ascii_lowercase, k=8))
                email = f"{random_name}@himmel.com"
            
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=30))
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                "success": True,
                "email": email,
                "password": password,
                "token": token,
                "id": "acc_" + ''.join(random.choices(string.digits, k=10)),
                "message": f"✅ Email {email} berhasil dibuat!"
            }
            
            self.wfile.write(json.dumps(response).encode())
            return
        
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                "success": False,
                "message": "Endpoint not found"
            }
            
            self.wfile.write(json.dumps(response).encode())
            return
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        return