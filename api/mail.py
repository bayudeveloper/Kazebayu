from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
import time
import uuid
import random
import string
import re
import traceback
from typing import Optional, List, Dict, Any

app = FastAPI()

# CORS - lebih lengkap
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# API Mail.tm
MAIL_API = "https://api.mail.tm"
TIMEOUT = 30

# ==================== MODELS ====================
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

# ==================== ERROR HANDLER GLOBAL ====================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle semua error biar selalu balikin JSON"""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": str(exc),
            "error_type": type(exc).__name__
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exception"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail
        }
    )

# ==================== ROOT ====================
@app.get("/")
async def root():
    return JSONResponse(content={
        "name": "Himmel Temp Mail",
        "developer": "Bayu Official",
        "domain": "@himmel.com",
        "status": "online",
        "powered_by": "Mail.tm API",
        "version": "1.5.5"
    })

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(content={
        "status": "healthy",
        "api": "connected",
        "timestamp": time.time()
    })

# ==================== DOMAINS ====================
@app.get("/api/domains")
async def get_domains():
    """Ambil domain yang tersedia dari Mail.tm"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{MAIL_API}/domains")
            
            if resp.status_code == 200:
                data = resp.json()
                domains = data.get('member', [])
                
                # Format domains
                formatted_domains = []
                for d in domains:
                    formatted_domains.append({
                        "domain": d.get('domain'),
                        "id": d.get('id')
                    })
                
                # Inject himmel.com kalo gak ada
                if not any(d['domain'] == 'himmel.com' for d in formatted_domains):
                    formatted_domains.append({
                        "domain": "himmel.com",
                        "id": "himmel.com"
                    })
                
                return JSONResponse(content={
                    "success": True,
                    "domains": formatted_domains,
                    "count": len(formatted_domains)
                })
            
            # Fallback
            return JSONResponse(content={
                "success": True,
                "domains": [{"domain": "himmel.com", "id": "himmel.com"}],
                "count": 1
            })
            
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "message": "Timeout connecting to Mail.tm"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Domain error: {str(e)}"
            }
        )

# ==================== GENERATE EMAIL ====================
@app.post("/api/generate")
async def generate_email(request: EmailRequest):
    """Bikin email real di Mail.tm"""
    
    try:
        # ===== GENERATE EMAIL =====
        if request.email and request.email.strip():
            # Pake custom prefix
            prefix = re.sub(r'[^a-zA-Z0-9]', '', request.email.lower())
            if not prefix or len(prefix) < 3:
                prefix = ''.join(random.choices(string.ascii_lowercase, k=8))
            # Potong kalo kepanjangan
            prefix = prefix[:20]
        else:
            # Random generate
            prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
        
        email = f"{prefix}@himmel.com"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        
        # ===== PANGGIL MAIL.TM API =====
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            
            # 1. Cek domain dulu
            try:
                domains_resp = await client.get(f"{MAIL_API}/domains")
                domains_data = domains_resp.json() if domains_resp.status_code == 200 else {"member": []}
                domains = domains_data.get('member', [])
                
                # Cari domain yang available
                domain_id = None
                for domain in domains:
                    domain_name = domain.get('domain', '')
                    # Cari domain yang cocok atau pake yang pertama
                    if 'himmel' in domain_name or domain_name.endswith('.com'):
                        domain_id = domain.get('id')
                        if domain_name != 'himmel.com':
                            # Update email pake domain real
                            email = f"{prefix}@{domain_name}"
                        break
                
                # Fallback kalo gak ada domain
                if not domain_id and domains:
                    domain_id = domains[0].get('id')
                    domain_name = domains[0].get('domain', 'himmel.com')
                    email = f"{prefix}@{domain_name}"
                    
            except Exception as e:
                print(f"Domain fetch error: {e}")
                domain_id = None
            
            # 2. Create account
            account_data = {
                "address": email,
                "password": password
            }
            
            if domain_id:
                account_data["domain"] = domain_id
            
            create_resp = await client.post(
                f"{MAIL_API}/accounts",
                json=account_data
            )
            
            # Handle response
            if create_resp.status_code in [200, 201]:
                # Success - langsung login
                token_resp = await client.post(
                    f"{MAIL_API}/token",
                    json={
                        "address": email,
                        "password": password
                    }
                )
                
                if token_resp.status_code == 200:
                    token_data = token_resp.json()
                    account_id = token_data.get('id')
                    token = token_data.get('token')
                    
                    return JSONResponse(content={
                        "success": True,
                        "email": email,
                        "password": password,
                        "token": token,
                        "id": account_id,
                        "message": f"✨ Email {email} berhasil dibuat!"
                    })
                else:
                    # Gagal login tapi account mungkin udah jadi
                    return JSONResponse(content={
                        "success": True,
                        "email": email,
                        "password": password,
                        "token": None,
                        "id": None,
                        "message": f"📧 Email dibuat, tapi gagal login. Coba manual."
                    })
            
            elif create_resp.status_code == 422:
                # Validation error - mungkin email udah ada
                error_data = create_resp.json()
                if "already exists" in str(error_data):
                    # Email udah ada, generate ulang
                    return await generate_email(EmailRequest(email=prefix + random.choice(string.digits)))
                
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "message": f"Validation error: {error_data}"
                    }
                )
            
            else:
                # Error lain
                try:
                    error_detail = create_resp.json()
                except:
                    error_detail = create_resp.text
                
                return JSONResponse(
                    status_code=create_resp.status_code,
                    content={
                        "success": False,
                        "message": f"Mail.tm error: {error_detail}"
                    }
                )
                
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "message": "Timeout connecting to Mail.tm"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error: {str(e)}"
            }
        )

# ==================== GET INBOX ====================
@app.get("/api/inbox/{email}")
async def get_inbox(email: str, token: Optional[str] = None, password: Optional[str] = None):
    """Ambil inbox dari Mail.tm"""
    
    try:
        # Validasi email
        if '@' not in email:
            email = f"{email}@himmel.com"
        
        # Kalo pake password, login dulu
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif password:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                token_resp = await client.post(
                    f"{MAIL_API}/token",
                    json={
                        "address": email,
                        "password": password
                    }
                )
                
                if token_resp.status_code == 200:
                    token_data = token_resp.json()
                    token = token_data.get('token')
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
        
        # Kalo gak ada auth, return kosong
        if not headers:
            return JSONResponse(content={
                "success": True,
                "email": email,
                "messages": [],
                "count": 0,
                "note": "Need token or password"
            })
        
        # Ambil messages
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
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
                        "created_at": msg.get('createdAt'),
                        "has_attachments": msg.get('hasAttachments', False)
                    })
                
                return JSONResponse(content={
                    "success": True,
                    "email": email,
                    "messages": messages,
                    "count": len(messages),
                    "total": msgs_data.get('total', 0)
                })
            
            elif msgs_resp.status_code == 401:
                return JSONResponse(
                    status_code=401,
                    content={
                        "success": False,
                        "message": "Invalid token"
                    }
                )
            else:
                return JSONResponse(
                    status_code=msgs_resp.status_code,
                    content={
                        "success": False,
                        "message": f"Failed to get messages: {msgs_resp.text}"
                    }
                )
                
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "message": "Timeout"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error: {str(e)}"
            }
        )

# ==================== GET SINGLE MESSAGE ====================
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
                        "created_at": msg.get('createdAt'),
                        "attachments": msg.get('attachments', [])
                    }
                })
            
            elif msg_resp.status_code == 404:
                return JSONResponse(
                    status_code=404,
                    content={
                        "success": False,
                        "message": "Message not found"
                    }
                )
            else:
                return JSONResponse(
                    status_code=msg_resp.status_code,
                    content={
                        "success": False,
                        "message": f"Error: {msg_resp.text}"
                    }
                )
                
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "message": "Timeout"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error: {str(e)}"
            }
        )

# ==================== DELETE EMAIL ====================
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
                else:
                    return JSONResponse(
                        status_code=del_resp.status_code,
                        content={
                            "success": False,
                            "message": f"Failed to delete: {del_resp.text}"
                        }
                    )
            else:
                return JSONResponse(
                    status_code=me_resp.status_code,
                    content={
                        "success": False,
                        "message": f"Failed to get account: {me_resp.text}"
                    }
                )
                
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "message": "Timeout"
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error: {str(e)}"
            }
        )

# ==================== TEST ENDPOINT ====================
@app.get("/api/test")
async def test_api():
    """Test endpoint buat ngecek koneksi"""
    return JSONResponse(content={
        "success": True,
        "message": "API is working!",
        "timestamp": time.time()
    })

# Handler untuk Vercel
handler = app