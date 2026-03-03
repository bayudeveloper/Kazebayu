from http.server import BaseHTTPRequestHandler
import json
import random
import string

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {
            "success": True,
            "message": "API is running!",
            "endpoints": ["/api/test", "/api/generate"]
        }
        
        self.wfile.write(json.dumps(response).encode())
        return
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data)
        except:
            data = {}
        
        prefix = data.get('email', '')
        
        if prefix:
            clean = ''.join(c for c in prefix if c.isalnum())[:10]
            email = f"{clean}@himmel.com" if clean else f"user{random.randint(100,999)}@himmel.com"
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
            "message": f"✅ Email {email} created!"
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