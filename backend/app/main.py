import logging
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid

from app.core.config import settings
from app.core.logging import setup_logging
from app.middleware.request_middleware import RequestMiddleware
from app.db.base import Base
from app.db.session import engine
from app.websocket.manager import websocket_manager
from app.websocket.developer_manager import developer_websocket_manager
from app.authentication import routes as auth_routes

# Import all models
from app.db.models import (
    clients, api_key, request_log, decision_log, 
    feature_log, ml_prediction, feedback, refresh_token, password_reset_token
)

# Import API routes
from app.api.routes import dashboard
from app.api.routes.activity import router as activity_router
from app.api.routes.settings import router as settings_router
from app.api.routes.api_keys import router as api_router
from app.api.routes.developer import router as developer_router   
from app.authentication import admin_routes

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# ============ LIFESPAN ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('Starting API Security System...')

    # Create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info('Database initialized')

    yield

    logger.info("Shutting down API Security System...")

# ============ CREATE APP ============

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Include API routes
app.include_router(auth_routes.router)
app.include_router(dashboard.router)
app.include_router(activity_router)
app.include_router(api_router)
app.include_router(settings_router)
app.include_router(developer_router)   
app.include_router(admin_routes.router)

# Add middleware
app.add_middleware(RequestMiddleware)

# ============ WEBSOCKET ENDPOINTS ============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Client WebSocket endpoint for real-time client updates."""
    await websocket_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)

@app.websocket("/api/developer/ws")
async def developer_websocket_endpoint(websocket: WebSocket):
    """Developer Panel WebSocket endpoint for real-time updates."""
    await developer_websocket_manager.connect(websocket)
    try:
        await websocket.send_json({
            "type": "connection_established",
            "message": "Connected to Developer Panel WebSocket",
            "connection_id": developer_websocket_manager.connection_counter
        })
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
    except WebSocketDisconnect:
        developer_websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Developer WebSocket error: {e}")
        developer_websocket_manager.disconnect(websocket)

# ====================================================================
# ALL REQUEST MODELS & API ENDPOINTS (Below WebSocket endpoints)
# ====================================================================

# ============ REQUEST MODELS ============

class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: Optional[bool] = False

class CartAddRequest(BaseModel):
    product_id: int
    quantity: int = 1
    price: Optional[float] = None
    currency: Optional[str] = "USD"

class CouponRequest(BaseModel):
    coupon_code: str

class CheckoutRequest(BaseModel):
    payment_method: str
    shipping_address: str
    total: float

class ProfileUpdateRequest(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None

class ResetPasswordRequest(BaseModel):
    email: str

class OrderRequest(BaseModel):
    product_id: int
    quantity: int = 1
    payment_method: Optional[str] = "card"

class SearchRequest(BaseModel):
    q: str
    page: Optional[int] = 1
    limit: Optional[int] = 20

# ============ HEALTH & TEST ============

@app.get('/api/test')
async def test():
    return {'message': 'working'}

@app.get('/health')
async def health():
    return {'status': 'ok'}

@app.get('/api/health')
async def api_health():
    return {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()}

@app.get('/api/ping')
async def ping():
    return {'pong': True, 'timestamp': datetime.utcnow().isoformat()}

@app.get('/api/status')
async def status():
    return {'status': 'operational', 'version': settings.APP_VERSION}

@app.get('/api/version')
async def version():
    return {'version': settings.APP_VERSION, 'name': settings.APP_NAME}

# ============ AUTHENTICATION ENDPOINTS ============

@app.post("/login")
async def login(request: LoginRequest):
    """Login endpoint - Primary target for credential stuffing attacks"""
    # Valid credentials for testing
    valid_users = {
        "admin": "admin123",
        "test": "password123",
        "user": "user123",
        "guest": "guest123",
        "john.doe": "john123",
        "jane.smith": "jane123",
        "support": "support123",
        "sales": "sales123",
        "marketing": "marketing123",
        "developer": "dev123"
    }
    
    if request.username in valid_users and request.password == valid_users[request.username]:
        token = f"jwt_{uuid.uuid4().hex[:16]}"
        return {
            "status": "success",
            "token": token,
            "user": {
                "id": hash(request.username) % 1000,
                "username": request.username,
                "role": "admin" if request.username == "admin" else "user"
            },
            "expires_in": 3600
        }
    
    return {"status": "failed", "message": "Invalid credentials"}

@app.post("/auth")
async def auth(request: LoginRequest):
    """Alternative auth endpoint - Also targeted"""
    return await login(request)

@app.post("/api/auth")
async def api_auth(request: LoginRequest):
    """API auth endpoint - Targeted by API abuse"""
    return await login(request)

@app.post("/token")
async def token(request: LoginRequest):
    """Token endpoint - OAuth-style"""
    return await login(request)

@app.post("/oauth/token")
async def oauth_token(request: LoginRequest):
    """OAuth token endpoint - Targeted by automated tools"""
    return await login(request)

# ============ USER PROFILE ENDPOINTS ============

@app.get("/api/profile")
async def get_profile():
    """Get user profile - Targeted by session hijacking"""
    return {
        "user_id": 123,
        "name": "Test User",
        "email": "test@example.com",
        "phone": "+1-555-123-4567",
        "role": "user",
        "preferences": {
            "theme": "dark",
            "notifications": True,
            "language": "en"
        },
        "created_at": "2024-01-01T00:00:00Z",
        "last_login": datetime.utcnow().isoformat()
    }

@app.post("/api/profile/update")
async def update_profile(request: ProfileUpdateRequest):
    """Update profile - Targeted by session hijacking"""
    return {
        "status": "success",
        "message": "Profile updated",
        "data": request.dict()
    }

@app.get("/api/users/me")
async def users_me():
    """Get current user - Normal endpoint"""
    return {
        "id": 123,
        "username": "testuser",
        "email": "test@example.com",
        "role": "user",
        "avatar": "https://example.com/avatar.png"
    }

@app.get("/api/users")
async def list_users():
    """List users - Admin endpoint targeted by API abuse"""
    return {
        "users": [
            {"id": 1, "username": "admin", "role": "admin", "status": "active"},
            {"id": 2, "username": "user1", "role": "user", "status": "active"},
            {"id": 3, "username": "user2", "role": "user", "status": "inactive"},
        ],
        "total": 3,
        "page": 1,
        "limit": 10
    }

@app.get("/api/v2/users")
async def api_v2_users():
    """V2 API users endpoint - Targeted by API scanners"""
    return {
        "version": "v2",
        "data": [
            {"id": 1, "username": "admin", "email": "admin@example.com"},
            {"id": 2, "username": "user1", "email": "user1@example.com"},
        ],
        "meta": {"total": 2}
    }

@app.get("/api/admin/users")
async def api_admin_users():
    """Admin users endpoint - Sensitive endpoint"""
    return {
        "users": [
            {"id": 1, "username": "admin", "role": "admin", "permissions": ["all"]},
            {"id": 2, "username": "user1", "role": "user", "permissions": ["read"]}
        ],
        "total": 2
    }

@app.get("/admin/dashboard")
async def admin_dashboard():
    """Admin dashboard - Sensitive endpoint"""
    return {
        "status": "admin_dashboard",
        "stats": {
            "users": 1234,
            "requests": 56789,
            "errors": 123,
            "uptime": "99.9%"
        },
        "recent_activity": [
            {"action": "user_login", "timestamp": datetime.utcnow().isoformat()},
            {"action": "api_call", "timestamp": datetime.utcnow().isoformat()}
        ]
    }

# ============ PRODUCT / SHOPPING ENDPOINTS ============

@app.get("/api/products")
async def list_products():
    """List products - Normal endpoint, scraping target"""
    return {
        "products": [
            {"id": 1, "name": "Laptop Pro", "price": 1299.99, "category": "electronics", "stock": 50},
            {"id": 2, "name": "Smartphone X", "price": 799.99, "category": "electronics", "stock": 100},
            {"id": 3, "name": "Wireless Headphones", "price": 199.99, "category": "accessories", "stock": 75},
            {"id": 4, "name": "Tablet Pro", "price": 499.99, "category": "electronics", "stock": 30},
            {"id": 5, "name": "Book: Python Programming", "price": 39.99, "category": "books", "stock": 200},
            {"id": 6, "name": "Book: Data Science", "price": 49.99, "category": "books", "stock": 150},
            {"id": 7, "name": "Gaming Mouse", "price": 89.99, "category": "accessories", "stock": 120},
            {"id": 8, "name": "Mechanical Keyboard", "price": 149.99, "category": "accessories", "stock": 80},
            {"id": 9, "name": "4K Monitor", "price": 399.99, "category": "electronics", "stock": 25},
            {"id": 10, "name": "USB-C Hub", "price": 59.99, "category": "accessories", "stock": 150}
        ],
        "total": 10,
        "page": 1,
        "limit": 20
    }

@app.get("/api/products/category/{category}")
async def products_by_category(category: str):
    """Products by category - Scraping target"""
    categories = {
        "electronics": [{"id": 1, "name": "Laptop Pro", "price": 1299.99}],
        "books": [{"id": 5, "name": "Python Programming", "price": 39.99}],
        "accessories": [{"id": 3, "name": "Wireless Headphones", "price": 199.99}]
    }
    return {"category": category, "products": categories.get(category, [])}

@app.get("/api/products/featured")
async def featured_products():
    """Featured products - Scraping target"""
    return {
        "featured": [
            {"id": 1, "name": "Laptop Pro", "price": 1299.99, "featured": True},
            {"id": 2, "name": "Smartphone X", "price": 799.99, "featured": True}
        ]
    }

@app.post("/api/cart/add")
async def cart_add(request: CartAddRequest):
    """Add to cart - Business logic abuse target"""
    # Validate price manipulation
    if request.price and request.price < 1:
        return {"status": "failed", "message": "Invalid price"}
    
    # Validate inventory hoarding
    if request.quantity > 100:
        return {"status": "failed", "message": "Quantity exceeds limit"}
    
    return {
        "status": "success",
        "cart": {
            "items": [{
                "product_id": request.product_id,
                "quantity": request.quantity,
                "price": request.price or 99.99,
                "total": (request.price or 99.99) * request.quantity
            }],
            "total": (request.price or 99.99) * request.quantity
        }
    }

@app.post("/api/cart/apply-coupon")
async def apply_coupon(request: CouponRequest):
    """Apply coupon - Business logic abuse target"""
    valid_coupons = ["DISCOUNT10", "SAVE20", "WELCOME", "FREE99"]
    
    if request.coupon_code in valid_coupons:
        return {
            "status": "success",
            "discount": 20,
            "message": f"Coupon {request.coupon_code} applied"
        }
    return {"status": "failed", "message": "Invalid coupon code"}

@app.post("/api/checkout/confirm")
async def checkout_confirm(request: CheckoutRequest):
    """Checkout confirmation - Business logic abuse target"""
    # Validate total manipulation
    if request.total < 0:
        return {"status": "failed", "message": "Invalid total amount"}
    
    # Validate payment method
    if request.payment_method in ["null", "invalid", "bypass"]:
        return {"status": "failed", "message": "Invalid payment method"}
    
    return {
        "status": "success",
        "order_id": f"ORD_{uuid.uuid4().hex[:8].upper()}",
        "total": request.total,
        "payment_method": request.payment_method,
        "shipping_address": request.shipping_address
    }

# ============ ORDERS ENDPOINTS ============

@app.get("/api/orders")
async def list_orders():
    """List orders - Targeted by session hijacking"""
    return {
        "orders": [
            {"id": 1, "product": "Laptop Pro", "amount": 1299.99, "status": "delivered"},
            {"id": 2, "product": "Smartphone X", "amount": 799.99, "status": "shipped"},
            {"id": 3, "product": "Wireless Headphones", "amount": 199.99, "status": "pending"}
        ],
        "total": 3
    }

@app.post("/api/orders")
async def create_order(request: OrderRequest):
    """Create order - Targeted by session hijacking"""
    return {
        "status": "success",
        "order": {
            "id": 999,
            "product_id": request.product_id,
            "quantity": request.quantity,
            "payment_method": request.payment_method,
            "total": request.quantity * 99.99,
            "status": "confirmed"
        }
    }

@app.get("/api/payment/methods")
async def payment_methods():
    """Get payment methods - Targeted by session hijacking"""
    return {
        "methods": [
            {"id": 1, "type": "credit_card", "last4": "4242", "expiry": "12/25"},
            {"id": 2, "type": "paypal", "email": "user@example.com"}
        ]
    }

# ============ SEARCH ENDPOINTS ============

@app.get("/api/search")
async def search(q: str = "", page: int = 1, limit: int = 20):
    """Search endpoint - Normal endpoint"""
    return {
        "query": q,
        "page": page,
        "limit": limit,
        "results": [
            {"id": 1, "name": f"Result for {q}", "score": 0.95},
            {"id": 2, "name": f"Another result for {q}", "score": 0.85}
        ] if q else [],
        "total": 0 if not q else 2
    }

@app.post("/api/search")
async def search_post(request: SearchRequest):
    """Search endpoint - POST version"""
    return await search(request.q, request.page, request.limit)

# ============ FEED ENDPOINTS ============

@app.get("/api/feed")
async def get_feed():
    """Get feed - Normal endpoint"""
    return {
        "feed": [
            {"id": 1, "type": "post", "content": "Hello world!", "timestamp": datetime.utcnow().isoformat()},
            {"id": 2, "type": "update", "content": "System updated", "timestamp": datetime.utcnow().isoformat()}
        ]
    }

# ============ DATA / ANALYTICS ENDPOINTS ============

@app.get("/api/data")
async def get_data():
    """Get data - Sensitive endpoint, scraping target"""
    return {
        "data": [
            {"id": i, "value": i * 10, "timestamp": datetime.utcnow().isoformat()}
            for i in range(10)
        ],
        "message": "sample data"
    }

@app.get("/api/secure")
async def get_secure():
    """Secure data - Sensitive endpoint, API abuse target"""
    return {
        "secure_data": {
            "api_key": "sk_test_secure_12345",
            "secret": "sensitive_encrypted_data",
            "access_level": "restricted"
        }
    }

@app.get("/api/analytics")
async def analytics():
    """Analytics endpoint - API abuse target"""
    return {
        "metrics": {
            "requests": {"total": 12345, "unique": 678},
            "errors": {"4xx": 123, "5xx": 45},
            "performance": {"avg_latency": 0.5, "p95": 1.2}
        }
    }

@app.get("/api/reports")
async def reports():
    """Reports endpoint - API abuse target"""
    return {
        "reports": [
            {"name": "Traffic Report", "date": "2024-01-01", "data": "..."},
            {"name": "Error Report", "date": "2024-01-02", "data": "..."}
        ]
    }

@app.get("/api/export")
async def export_data():
    """Export endpoint - API abuse target"""
    return {
        "export_id": f"exp_{uuid.uuid4().hex[:8]}",
        "status": "processing",
        "download_url": "/downloads/export.csv"
    }

@app.get("/api/backup")
async def backup():
    """Backup endpoint - API abuse target"""
    return {
        "backup_id": f"bak_{uuid.uuid4().hex[:8]}",
        "size": "15MB",
        "created_at": datetime.utcnow().isoformat(),
        "status": "completed"
    }

@app.get("/api/internal/metrics")
async def internal_metrics():
    """Internal metrics - Sensitive endpoint"""
    return {
        "cpu_usage": 45.2,
        "memory_usage": 1024,
        "requests_per_second": 150,
        "error_rate": 0.02,
        "active_connections": 42,
        "uptime_seconds": 86400
    }

# ============ ADMIN / SYSTEM ENDPOINTS ============

@app.get("/admin")
async def admin():
    """Admin panel - Sensitive endpoint"""
    return {
        "status": "admin_panel",
        "version": "1.0.0",
        "environment": "development",
        "features": {
            "auth": True,
            "logging": True,
            "monitoring": True
        }
    }

@app.get("/config")
async def config():
    """Config endpoint - Scanner target"""
    return {
        "debug": False,
        "version": "1.0.0",
        "api_keys": ["sk_test_123", "sk_test_456"],
        "allowed_origins": ["http://localhost:3000"],
        "rate_limits": {"default": 100, "admin": 1000}
    }

@app.get("/debug")
async def debug():
    """Debug endpoint - Scanner target"""
    return {
        "debug": True,
        "info": "Debug mode enabled",
        "trace": "detailed_info",
        "stack": "full_trace_back"
    }

@app.get("/api/private")
async def private():
    """Private API - High risk endpoint"""
    return {
        "secret": "sensitive_data_123",
        "api_key": "private_key_xyz_789",
        "internal_config": {
            "database_url": "postgresql://internal:secret@db:5432/prod",
            "redis_host": "redis.internal:6379"
        }
    }

@app.get("/api/internal")
async def internal():
    """Internal endpoint - High risk endpoint"""
    return {
        "internal": True,
        "data": "internal_system_data",
        "services": {
            "auth": {"status": "healthy", "port": 8001},
            "db": {"status": "healthy", "connection": "pooled"}
        }
    }

# ============ FILE / ASSET ENDPOINTS ============

@app.get("/.env")
async def env_file():
    """Environment file - Scanner target"""
    return {
        "DB_PASSWORD": "secret123",
        "API_KEY": "sk_test_123456",
        "JWT_SECRET": "super_secret_key_123",
        "REDIS_PASSWORD": "redis_secret",
        "AWS_ACCESS_KEY": "AKIAIOSFODNN7EXAMPLE",
        "AWS_SECRET_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    }

@app.get("/.git/config")
async def git_config():
    """Git config - Scanner target"""
    return {
        "[core]": "repositoryformatversion = 0",
        "[remote 'origin']": "url = https://github.com/example/repo.git",
        "[user]": "name = Developer, email = dev@example.com"
    }

@app.get("/.aws/credentials")
async def aws_credentials():
    """AWS credentials - Scanner target"""
    return {
        "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
        "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "region": "us-east-1"
    }

@app.get("/.ssh/id_rsa")
async def ssh_key():
    """SSH private key - Scanner target"""
    return {
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----",
        "permissions": "600"
    }

@app.get("/backup/db.sql")
async def backup_db():
    """Database backup - Scanner target"""
    return {
        "file": "database_backup.sql",
        "size": "15MB",
        "timestamp": datetime.utcnow().isoformat(),
        "data": "CREATE TABLE users (id INT, username VARCHAR); INSERT INTO users VALUES (1, 'admin');"
    }

@app.get("/backup.zip")
async def backup_zip():
    """Backup archive - Scanner target"""
    return {
        "file": "backup.zip",
        "size": "15MB",
        "download": "backup.zip",
        "contains": ["database.sql", "config.yaml", "secrets.txt"]
    }

@app.get("/database.sql")
async def database_sql():
    """Database SQL dump - Scanner target"""
    return {
        "file": "database.sql",
        "content": "CREATE TABLE users (id INT PRIMARY KEY, username VARCHAR(255), password VARCHAR(255));",
        "tables": ["users", "products", "orders", "payments"]
    }

@app.get("/password.txt")
async def password_file():
    """Password file - Scanner target"""
    return {
        "passwords": [
            "admin123", "password123", "qwerty", "abc123",
            "admin", "root", "123456", "welcome"
        ]
    }

@app.get("/credentials.txt")
async def credentials_file():
    """Credentials file - Scanner target"""
    return {
        "credentials": [
            {"user": "admin", "pass": "admin123"},
            {"user": "root", "pass": "root123"},
            {"user": "user", "pass": "user123"},
            {"user": "test", "pass": "test123"}
        ]
    }

@app.get("/dump")
async def dump():
    """System dump - Scanner target"""
    return {
        "dump": "system_dump_data",
        "memory": {"used": "2GB", "total": "8GB", "free": "6GB"},
        "processes": [
            {"pid": 1, "name": "api", "cpu": 5},
            {"pid": 2, "name": "worker", "cpu": 10}
        ]
    }

@app.get("/trace")
async def trace():
    """Trace endpoint - Scanner target"""
    return {
        "traces": [
            {"id": 1, "duration": 100, "path": "/api/data", "method": "GET"},
            {"id": 2, "duration": 200, "path": "/login", "method": "POST"},
            {"id": 3, "duration": 50, "path": "/health", "method": "GET"}
        ]
    }

# ============ API SPEC / SWAGGER ENDPOINTS ============

@app.get("/swagger.json")
async def swagger_json():
    """Swagger spec - Scanner target"""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "API",
            "version": "1.0.0",
            "description": "API Documentation"
        },
        "paths": {
            "/api/data": {"get": {"summary": "Get data"}},
            "/login": {"post": {"summary": "Login"}},
            "/api/products": {"get": {"summary": "List products"}}
        }
    }

@app.get("/openapi.json")
async def openapi_json():
    """OpenAPI spec - Scanner target"""
    return await swagger_json()

@app.get("/api/docs")
async def api_docs():
    """API documentation - Scanner target"""
    return {
        "docs": {
            "endpoints": [
                {"path": "/api/data", "method": "GET", "description": "Get data"},
                {"path": "/login", "method": "POST", "description": "Login"},
                {"path": "/api/products", "method": "GET", "description": "List products"}
            ]
        }
    }

# ============ GRAPHQL ENDPOINTS ============

@app.get("/graphql")
async def graphql_endpoint():
    """GraphQL endpoint - Scanner target"""
    return {
        "message": "GraphQL endpoint",
        "schema": "type Query { hello: String, users: [User] }",
        "introspection": True
    }

@app.post("/graphql")
async def graphql_post(request: Request):
    """GraphQL POST endpoint - Scanner target"""
    try:
        body = await request.json()
        return {
            "data": {
                "hello": "world",
                "query": body.get("query", ""),
                "variables": body.get("variables", {})
            }
        }
    except:
        return {"error": "Invalid GraphQL query"}

# ============ MONITORING / ACTUATOR ENDPOINTS ============

@app.get("/actuator/health")
async def actuator_health():
    """Actuator health - Scanner target"""
    return {
        "status": "UP",
        "components": {
            "db": {"status": "UP", "details": {"database": "postgresql"}},
            "cache": {"status": "UP", "details": {"redis": "connected"}},
            "queue": {"status": "UP", "details": {"rabbitmq": "connected"}}
        }
    }

@app.get("/actuator/env")
async def actuator_env():
    """Actuator environment - Scanner target"""
    return {
        "activeProfiles": ["prod", "api"],
        "propertySources": [
            {"name": "application.properties", "properties": {
                "server.port": {"value": 8080},
                "db.host": {"value": "localhost"},
                "db.password": {"value": "secret123"}
            }}
        ]
    }

@app.get("/metrics")
async def metrics():
    """Metrics endpoint - Scanner target"""
    return {
        "requests": 1000,
        "errors": 10,
        "latency": 0.5,
        "cpu": 45.2,
        "memory": 1024,
        "gauge": {
            "active_sessions": 42,
            "queue_size": 10,
            "cache_hit_ratio": 0.85
        },
        "counter": {
            "login_attempts": 5678,
            "api_calls": 12345,
            "errors_total": 123
        }
    }

# ============ RESET PASSWORD ============

@app.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """Reset password endpoint - Attack surface"""
    return {
        "status": "success",
        "message": "Password reset link sent",
        "email": request.email,
        "reset_token": f"reset_{uuid.uuid4().hex[:16]}"
    }

@app.post("/api/reset-password")
async def api_reset_password(request: ResetPasswordRequest):
    """API reset password - Attack surface"""
    return await reset_password(request)

# ============ MISCELLANEOUS ATTACK TARGETS ============

@app.get("/phpmyadmin")
async def phpmyadmin():
    """phpMyAdmin - Scanner target"""
    return {
        "status": "phpMyAdmin",
        "version": "4.9.7",
        "database": "mysql",
        "host": "localhost",
        "user": "root"
    }

@app.get("/wp-admin")
async def wp_admin():
    """WordPress admin - Scanner target"""
    return {"status": "WordPress Admin", "version": "5.8.1"}

@app.get("/api/admin/config")
async def api_admin_config():
    """Admin config - API abuse target"""
    return {
        "config": {
            "debug": True,
            "secret_key": "admin_secret_123",
            "api_keys": ["admin_key_1", "admin_key_2"],
            "allowed_ips": ["192.168.1.0/24", "10.0.0.0/8"]
        }
    }

@app.get("/api/admin/dashboard")
async def api_admin_dashboard():
    """Admin dashboard - API abuse target"""
    return {
        "dashboard": {
            "users": {"total": 1234, "active": 567, "new": 89},
            "revenue": {"total": 123456, "monthly": 10234, "growth": 15.5},
            "requests": {"total": 56789, "avg": 789, "peak": 1234}
        }
    }

# ============ Test endpoint already exists above ============
# ============ All endpoints below are for attack simulation ============

@app.get("/api/internal/status")
async def internal_status():
    """Internal status - Sensitive endpoint"""
    return {
        "status": "operational",
        "services": {
            "api": {"status": "up", "version": "1.0.0"},
            "db": {"status": "up", "connections": 10},
            "cache": {"status": "up", "hit_ratio": 0.95}
        }
    }

@app.get("/api/debug/trace")
async def debug_trace():
    """Debug trace - Sensitive endpoint"""
    return {
        "trace_id": uuid.uuid4().hex[:16],
        "span_id": uuid.uuid4().hex[:8],
        "parent_id": None,
        "name": "api_request",
        "start_time": datetime.utcnow().isoformat(),
        "duration": 123.45
    }

@app.get("/api/health/ready")
async def health_ready():
    """Readiness probe - Normal endpoint"""
    return {"ready": True, "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/health/live")
async def health_live():
    """Liveness probe - Normal endpoint"""
    return {"alive": True, "timestamp": datetime.utcnow().isoformat()}