from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import time
import random
import string
import re
import traceback
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Mail.tm
MAIL_API = "https://api.mail.tm"
TIMEOUT = 30

@app.get("/")
async def root():
    return JSONResponse(content={
        "name": "Himmel Temp Mail",
        "developer": "Bayu Official",
        "domain": "@himmel.com",
        "status": "online",
        "message": "API is running!"
    })

@app.get("/api/test")
async def test_api():
    """TEST - Pastiin API jalan"""
    return JSONResponse(content={
        "success": True,
        "message": "API is working!",
        "timestamp": time.time()
    })

@app.get("/api/health")
async def health_check():
    return JSONResponse(content={
        "status": "healthy",
        "api": "connected"
    })

@app.get("/api/domains")
async def get_domains():
    """Ambil domain dari Mail.tm"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{MAIL_API}/domains")
            
            if resp.status_code == 200:
                data = resp.json()
                domains = data.get('member', [])
                
                formatted_domains = []
                for d in domains:
                    formatted_domains.append({
                        "domain": d.get('domain'),
                        "id": d.get('id')
                    })
                
                return JSONResponse(content={
                    "success": True,
                    "domains": formatted_domains
                })
            
            return JSONResponse(content={
                "success": False,
                "message": "Failed to fetch domains"
            })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(e)
            }
        )

@app.post("/api/generate")
async def generate_email(request: Request):
    """Bikin email real di Mail.tm"""
    try:
        # Parse JSON
        try:
            data = await request.json()
        except:
            data = {}
        
        # Generate prefix
        custom_prefix = data.get('email', '')
        if custom_prefix and custom_prefix.strip():
            prefix = re.sub(r'[^a-zA-Z0-9]', '', custom_prefix.lower())
            if not prefix or len(prefix) < 3:
                prefix = ''.join(random.choices(string.ascii_lowercase, k=8))
            prefix = prefix[:20]
        else:
            prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        
        # Generate random password
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # 1. Dapetin domain dulu
            domains_resp = await client.get(f"{MAIL_API}/domains")
            
            if domains_resp.status_code != 200:
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": "Gagal ambil domain dari Mail.tm"
                    }
                )
            
            domains_data = domains_resp.json()
            domains = domains_data.get('member', [])
            
            if not domains:
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": "Tidak ada domain tersedia"
                    }
                )
            
            # Pake domain pertama yang available
            domain = domains[0].get('domain')
            email = f"{prefix}@{domain}"
            
            # 2. Create account
            account_data = {
                "address": email,
                "password": password
            }
            
            create_resp = await client.post(
                f"{MAIL_API}/accounts",
                json=account_data
            )
            
            if create_resp.status_code in [200, 201]:
                # 3. Login dapet token
                token_resp = await client.post(
                    f"{MAIL_API}/token",
                    json={
                        "address": email,
                        "password": password
                    }
                )
                
                if token_resp.status_code == 200:
                    token_data = token_resp.json()
                    
                    return JSONResponse(content={
                        "success": True,
                        "email": email,
                        "password": password,
                        "token": token_data.get('token'),
                        "id": token_data.get('id'),
                        "message": f"✨ Email {email} berhasil dibuat!"
                    })
            
            # Handle error
            error_text = create_resp.text if hasattr(create_resp, 'text') else "Unknown error"
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Gagal bikin email: {error_text}"
                }
            )
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(e)
            }
        )

@app.get("/api/inbox/{email}")
async def get_inbox(email: str, token: str):
    """Ambil inbox dari Mail.tm"""
    try:
        if not token:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "Token required"
                }
            )
        
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Ambil messages
            msgs_resp = await client.get(
                f"{MAIL_API}/messages",
                headers=headers
            )
            
            if msgs_resp.status_code == 200:
                msgs_data = msgs_resp.json()
                
                messages = []
                for msg in msgs_data.get('member', []):
                    messages.append({
                        "id": msg.get('id'),
                        "from": msg.get('from', {}).get('address', 'Unknown'),
                        "subject": msg.get('subject', 'No Subject'),
                        "intro": msg.get('intro', ''),
                        "created_at": msg.get('createdAt')
                    })
                
                return JSONResponse(content={
                    "success": True,
                    "email": email,
                    "messages": messages,
                    "count": len(messages)
                })
            
            return JSONResponse(
                status_code=msgs_resp.status_code,
                content={
                    "success": False,
                    "message": f"Gagal ambil inbox: {msgs_resp.text}"
                }
            )
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(e)
            }
        )

@app.get("/api/message/{email}/{message_id}")
async def get_message(email: str, message_id: str, token: str):
    """Ambil detail pesan"""
    try:
        if not token:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "Token required"
                }
            )
        
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            msg_resp = await client.get(
                f"{MAIL_API}/messages/{message_id}",
                headers=headers
            )
            
            if msg_resp.status_code == 200:
                msg = msg_resp.json()
                
                return JSONResponse(content={
                    "success": True,
                    "message": {
                        "id": msg.get('id'),
                        "from": msg.get('from', {}).get('address'),
                        "to": msg.get('to', [{}])[0].get('address') if msg.get('to') else None,
                        "subject": msg.get('subject', 'No Subject'),
                        "text": msg.get('text', ''),
                        "html": msg.get('html', ''),
                        "created_at": msg.get('createdAt')
                    }
                })
            
            return JSONResponse(
                status_code=msg_resp.status_code,
                content={
                    "success": False,
                    "message": f"Gagal ambil pesan: {msg_resp.text}"
                }
            )
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(e)
            }
        )

@app.delete("/api/delete/{email}")
async def delete_email(email: str, token: str):
    """Hapus account email"""
    try:
        if not token:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "Token required"
                }
            )
        
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Dapetin account ID
            me_resp = await client.get(
                f"{MAIL_API}/me",
                headers=headers
            )
            
            if me_resp.status_code == 200:
                account_id = me_resp.json().get('id')
                
                if not account_id:
                    return JSONResponse(
                        status_code=404,
                        content={
                            "success": False,
                            "message": "Account ID not found"
                        }
                    )
                
                # Delete account
                del_resp = await client.delete(
                    f"{MAIL_API}/accounts/{account_id}",
                    headers=headers
                )
                
                if del_resp.status_code == 204:
                    return JSONResponse(content={
                        "success": True,
                        "message": "Email berhasil dihapus"
                    })
            
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Gagal hapus email"
                }
            )
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": str(e)
            }
        )

# Handler untuk Vercel
handler = app