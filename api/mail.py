from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import time
import uuid
from typing import Optional, List
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Mail.tm (FREE, REAL EMAIL SERVICE)
MAIL_API = "https://api.mail.tm"
TIMEOUT = 30

class EmailRequest(BaseModel):
    email: Optional[str] = None

class EmailResponse(BaseModel):
    success: bool
    email: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    id: Optional[str] = None
    messages: List[dict] = []
    message: Optional[str] = None

@app.get("/")
async def root():
    return {
        "name": "Himmel Temp Mail",
        "developer": "Bayu Official",
        "domain": "@himmel.com",
        "status": "online",
        "powered_by": "Mail.tm API"
    }

@app.get("/api/domains")
async def get_domains():
    """Ambil domain yang tersedia dari Mail.tm"""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{MAIL_API}/domains", timeout=TIMEOUT)
            if resp.status_code == 200:
                domains = resp.json()
                # Filter cuma yang @himmel.com (kalo ada)
                himmel_domains = [d for d in domains.get('ld', []) if 'himmel' in d.get('domain', '')]
                if himmel_domains:
                    return {"domains": himmel_domains}
            
            # Fallback: inject domain himmel.com
            return {
                "domains": [
                    {
                        "domain": "himmel.com",
                        "id": "himmel-com"
                    }
                ]
            }
        except Exception as e:
            return {"domains": [{"domain": "himmel.com"}], "error": str(e)}

@app.post("/api/generate", response_model=EmailResponse)
async def generate_email(request: EmailRequest):
    """Bikin email real di Mail.tm"""
    
    # Generate random email
    if request.email and request.email.strip():
        # Pake custom prefix
        prefix = re.sub(r'[^a-zA-Z0-9]', '', request.email.lower())
        if not prefix:
            import random, string
            prefix = ''.join(random.choices(string.ascii_lowercase, k=8))
        email = f"{prefix}@himmel.com"
    else:
        # Random generate
        import random, string
        prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{prefix}@himmel.com"
    
    # Generate random password
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Dapetin domain ID dari Mail.tm
            domains_resp = await client.get(f"{MAIL_API}/domains", timeout=TIMEOUT)
            domain_id = None
            
            if domains_resp.status_code == 200:
                domains = domains_resp.json()
                # Cari domain yang available
                for domain in domains.get('member', []):
                    if domain.get('domain') == 'himmel.com' or True:  # Force pake himmel.com
                        domain_id = domain.get('id', '@himmel.com')
                        break
            
            # 2. Create account di Mail.tm
            account_data = {
                "address": email,
                "password": password
            }
            
            # Kalo ada domain_id, tambahin
            if domain_id:
                account_data["domain"] = domain_id
            
            create_resp = await client.post(
                f"{MAIL_API}/accounts",
                json=account_data,
                timeout=TIMEOUT
            )
            
            if create_resp.status_code in [200, 201]:
                # 3. Login dapet token
                token_resp = await client.post(
                    f"{MAIL_API}/token",
                    json={
                        "address": email,
                        "password": password
                    },
                    timeout=TIMEOUT
                )
                
                if token_resp.status_code == 200:
                    token_data = token_resp.json()
                    account_id = token_data.get('id')
                    token = token_data.get('token')
                    
                    return EmailResponse(
                        success=True,
                        email=email,
                        password=password,
                        token=token,
                        id=account_id,
                        message="✨ Email berhasil dibuat! Bisa langsung dipake."
                    )
            
            # Kalo gagal, return error
            error_detail = create_resp.text if hasattr(create_resp, 'text') else "Unknown error"
            return EmailResponse(
                success=False,
                message=f"Gagal bikin email: {error_detail}"
            )
            
        except Exception as e:
            return EmailResponse(
                success=False,
                message=f"Error: {str(e)}"
            )

@app.get("/api/inbox/{email}")
async def get_inbox(email: str, password: Optional[str] = None, token: Optional[str] = None):
    """Ambil inbox dari Mail.tm"""
    
    if not email.endswith("@himmel.com"):
        return {"success": False, "message": "Domain harus @himmel.com"}
    
    async with httpx.AsyncClient() as client:
        try:
            headers = {}
            
            # Kalo ada token, pake token
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            # Kalo ada password, login dulu
            elif password:
                token_resp = await client.post(
                    f"{MAIL_API}/token",
                    json={
                        "address": email,
                        "password": password
                    },
                    timeout=TIMEOUT
                )
                
                if token_resp.status_code == 200:
                    token_data = token_resp.json()
                    token = token_data.get('token')
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
            
            # Ambil messages
            if headers:
                msgs_resp = await client.get(
                    f"{MAIL_API}/messages",
                    headers=headers,
                    timeout=TIMEOUT
                )
                
                if msgs_resp.status_code == 200:
                    msgs_data = msgs_resp.json()
                    
                    # Format messages
                    messages = []
                    for msg in msgs_data.get('member', []):
                        messages.append({
                            "id": msg.get('id'),
                            "from": msg.get('from', {}).get('address', 'Unknown'),
                            "subject": msg.get('subject', 'No Subject'),
                            "intro": msg.get('intro', ''),
                            "created_at": msg.get('createdAt'),
                            "has_attachments": msg.get('hasAttachments', False)
                        })
                    
                    return {
                        "success": True,
                        "email": email,
                        "messages": messages,
                        "count": len(messages)
                    }
            
            return {
                "success": True,
                "email": email,
                "messages": [],
                "count": 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

@app.get("/api/message/{email}/{message_id}")
async def get_message(email: str, message_id: str, token: str):
    """Ambil detail pesan"""
    
    async with httpx.AsyncClient() as client:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            
            msg_resp = await client.get(
                f"{MAIL_API}/messages/{message_id}",
                headers=headers,
                timeout=TIMEOUT
            )
            
            if msg_resp.status_code == 200:
                msg = msg_resp.json()
                
                return {
                    "success": True,
                    "message": {
                        "id": msg.get('id'),
                        "from": msg.get('from', {}).get('address'),
                        "to": msg.get('to', [{}])[0].get('address') if msg.get('to') else None,
                        "subject": msg.get('subject'),
                        "text": msg.get('text'),
                        "html": msg.get('html'),
                        "created_at": msg.get('createdAt')
                    }
                }
            
            return {
                "success": False,
                "message": "Pesan tidak ditemukan"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

@app.delete("/api/delete/{email}")
async def delete_email(email: str, token: str):
    """Hapus account email"""
    
    async with httpx.AsyncClient() as client:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            
            # Cari account ID dulu
            me_resp = await client.get(
                f"{MAIL_API}/me",
                headers=headers,
                timeout=TIMEOUT
            )
            
            if me_resp.status_code == 200:
                account_id = me_resp.json().get('id')
                
                # Delete account
                del_resp = await client.delete(
                    f"{MAIL_API}/accounts/{account_id}",
                    headers=headers,
                    timeout=TIMEOUT
                )
                
                if del_resp.status_code == 204:
                    return {
                        "success": True,
                        "message": "Email berhasil dihapus"
                    }
            
            return {
                "success": False,
                "message": "Gagal hapus email"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

# Handler untuk Vercel
handler = app