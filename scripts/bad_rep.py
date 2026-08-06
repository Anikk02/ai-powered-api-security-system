import asyncio
import random
import httpx
import time
import uuid
import hashlib
from datetime import datetime
from typing import List, Tuple, Dict, Optional
import signal
import sys

# ============ CONFIGURATION ============
BASE_URL = "http://localhost:8000"

DURATION_MINUTES = 30
NORMAL_USERS_COUNT = 30
SUSPICIOUS_USERS_COUNT = 15
ATTACK_USERS_COUNT = 15
BAD_REPUTATION_USERS_COUNT = 10  # 🔥 NEW: Users with very bad reputation

# API Key for authentication
API_KEY = ""

# ============ ENHANCED IP POOL (100+ realistic IPs) ============
IP_POOL = [
    # US IPs (New York)
    "192.168.1.101", "192.168.1.102", "192.168.1.103", "192.168.1.104", "192.168.1.105",
    "192.168.1.106", "192.168.1.107", "192.168.1.108", "192.168.1.109", "192.168.1.110",
    "192.168.1.111", "192.168.1.112", "192.168.1.113", "192.168.1.114", "192.168.1.115",
    # US IPs (California)
    "10.0.0.101", "10.0.0.102", "10.0.0.103", "10.0.0.104", "10.0.0.105",
    "10.0.0.106", "10.0.0.107", "10.0.0.108", "10.0.0.109", "10.0.0.110",
    "10.0.0.111", "10.0.0.112", "10.0.0.113", "10.0.0.114", "10.0.0.115",
    # Europe IPs (UK, Germany, France)
    "172.16.0.101", "172.16.0.102", "172.16.0.103", "172.16.0.104", "172.16.0.105",
    "172.16.0.106", "172.16.0.107", "172.16.0.108", "172.16.0.109", "172.16.0.110",
    "172.16.1.101", "172.16.1.102", "172.16.1.103", "172.16.1.104", "172.16.1.105",
    "172.16.1.106", "172.16.1.107", "172.16.1.108", "172.16.1.109", "172.16.1.110",
    # Asia IPs (Japan, Singapore, India)
    "192.168.2.101", "192.168.2.102", "192.168.2.103", "192.168.2.104", "192.168.2.105",
    "192.168.2.106", "192.168.2.107", "192.168.2.108", "192.168.2.109", "192.168.2.110",
    "192.168.2.111", "192.168.2.112", "192.168.2.113", "192.168.2.114", "192.168.2.115",
    "192.168.3.101", "192.168.3.102", "192.168.3.103", "192.168.3.104", "192.168.3.105",
    # South America IPs (Brazil, Argentina)
    "10.1.0.101", "10.1.0.102", "10.1.0.103", "10.1.0.104", "10.1.0.105",
    "10.1.0.106", "10.1.0.107", "10.1.0.108", "10.1.0.109", "10.1.0.110",
    "10.1.0.111", "10.1.0.112", "10.1.0.113", "10.1.0.114", "10.1.0.115",
    # Australia IPs
    "172.17.0.101", "172.17.0.102", "172.17.0.103", "172.17.0.104", "172.17.0.105",
    "172.17.0.106", "172.17.0.107", "172.17.0.108", "172.17.0.109", "172.17.0.110",
    # Mobile Network IPs (different ranges)
    "192.168.100.101", "192.168.100.102", "192.168.100.103", "192.168.100.104", "192.168.100.105",
    "192.168.100.106", "192.168.100.107", "192.168.100.108", "192.168.100.109", "192.168.100.110",
    "10.10.0.101", "10.10.0.102", "10.10.0.103", "10.10.0.104", "10.10.0.105",
    "10.10.0.106", "10.10.0.107", "10.10.0.108", "10.10.0.109", "10.10.0.110",
    # Corporate IPs (different subnets)
    "172.18.0.101", "172.18.0.102", "172.18.0.103", "172.18.0.104", "172.18.0.105",
    "172.18.0.106", "172.18.0.107", "172.18.0.108", "172.18.0.109", "172.18.0.110",
    "192.168.200.101", "192.168.200.102", "192.168.200.103", "192.168.200.104", "192.168.200.105",
    "192.168.200.106", "192.168.200.107", "192.168.200.108", "192.168.200.109", "192.168.200.110",
    # Additional random IPs
    "10.2.0.101", "10.2.0.102", "10.2.0.103", "10.2.0.104", "10.2.0.105",
    "172.19.0.101", "172.19.0.102", "172.19.0.103", "172.19.0.104", "172.19.0.105",
]

# ============ ENHANCED USER AGENT POOL ============
USER_AGENTS = {
    "browser": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    ],
    "mobile": [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    ],
    "bot": [
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)",
        "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",
    ]
}

# ============ ENDPOINTS ============
NORMAL_ENDPOINTS = [
    "/health",
    "/api/profile",
    "/api/users/me",
    "/api/products",
    "/api/search",
    "/api/feed",
]

SUSPICIOUS_ENDPOINTS = [
    "/api/data",
    "/api/products", 
    "/api/search",
]

ATTACK_ENDPOINTS = [
    "/login",
    "/admin",
    "/config", 
    "/.env",
    "/debug",
    "/api/private",
    "/wp-admin",
    "/phpmyadmin",
]

# ============ USER BEHAVIOR CONFIGURATION ============
USER_BEHAVIORS = {
    "normal": {
        "delay_range": (1.0, 5.0),
        "ip_rotation": False,
        "session_endpoints": 3,
        "error_rate": 0.02,
        "user_agent_types": ["browser", "mobile"],
        "cookie_persistence": True,
        "ip_change_probability": 0.3,
        "ip_change_interval": (300, 1800)
    },
    "suspicious": {
        "delay_range": (0.5, 3.0),
        "ip_rotation": False,
        "session_endpoints": 2,
        "error_rate": 0.05,
        "user_agent_types": ["browser"],
        "cookie_persistence": True,
        "ip_change_probability": 0.1,
        "ip_change_interval": (600, 3600)
    },
    "attack": {
        "delay_range": (0.1, 1.5),
        "ip_rotation": True,
        "session_endpoints": 1,
        "error_rate": 0.10,
        "user_agent_types": ["browser", "bot"],
        "cookie_persistence": False,
        "ip_change_probability": 1.0,
        "ip_change_interval": (1, 5)
    },
    "bad_reputation": {  # 🔥 NEW: Users who will build very bad reputation
        "delay_range": (0.1, 0.5),  # Very fast requests
        "ip_rotation": True,  # Rotate IPs constantly
        "session_endpoints": 1,
        "error_rate": 0.30,  # High error rate
        "user_agent_types": ["bot", "browser"],  # Mixed agents
        "cookie_persistence": False,  # No cookies
        "ip_change_probability": 1.0,
        "ip_change_interval": (1, 3)  # Change IP every 1-3 seconds
    }
}

# ============ IP MANAGER ============
class IPManager:
    def __init__(self):
        self.used_ips: Dict[int, str] = {}
        self.ip_pool = IP_POOL.copy()
        random.shuffle(self.ip_pool)
        self.ip_index = 0
        self.ip_history: Dict[int, List[str]] = {}
        self.ip_change_timers: Dict[int, float] = {}
    
    def get_ip_for_user(self, user_id: int, behavior_type: str = "normal") -> str:
        if behavior_type == "attack" or behavior_type == "bad_reputation":
            return self.get_rotating_ip()
        
        if user_id not in self.used_ips:
            ip = self.ip_pool[self.ip_index % len(self.ip_pool)]
            self.used_ips[user_id] = ip
            self.ip_history[user_id] = [ip]
            behavior = USER_BEHAVIORS.get(behavior_type, USER_BEHAVIORS["normal"])
            min_interval, max_interval = behavior["ip_change_interval"]
            self.ip_change_timers[user_id] = time.time() + random.uniform(min_interval, max_interval)
            self.ip_index += 1
        else:
            current_time = time.time()
            behavior = USER_BEHAVIORS.get(behavior_type, USER_BEHAVIORS["normal"])
            
            if current_time > self.ip_change_timers.get(user_id, 0):
                if random.random() < behavior["ip_change_probability"]:
                    old_ip = self.used_ips[user_id]
                    attempts = 0
                    while attempts < 10:
                        new_ip = self.ip_pool[random.randint(0, len(self.ip_pool) - 1)]
                        if new_ip != old_ip:
                            self.used_ips[user_id] = new_ip
                            self.ip_history[user_id].append(new_ip)
                            min_interval, max_interval = behavior["ip_change_interval"]
                            self.ip_change_timers[user_id] = time.time() + random.uniform(min_interval, max_interval)
                            break
                        attempts += 1
        
        return self.used_ips.get(user_id, self.ip_pool[0])
    
    def get_rotating_ip(self) -> str:
        return random.choice(self.ip_pool)
    
    def get_ip_history(self, user_id: int) -> List[str]:
        return self.ip_history.get(user_id, [])

ip_manager = IPManager()

# ============ COOKIE MANAGER ============
class CookieManager:
    def __init__(self):
        self.user_cookies: Dict[int, str] = {}
        self.cookie_history: Dict[int, List[str]] = {}
    
    def get_or_create_cookie(self, user_id: int, behavior_type: str = "normal") -> Optional[str]:
        behavior = USER_BEHAVIORS.get(behavior_type, USER_BEHAVIORS["normal"])
        
        if not behavior["cookie_persistence"]:
            return None
        
        if user_id not in self.user_cookies:
            cookie_val = f"user_{user_id}_{uuid.uuid4().hex[:12]}"
            self.user_cookies[user_id] = cookie_val
            self.cookie_history[user_id] = [cookie_val]
        
        return self.user_cookies[user_id]
    
    def refresh_cookie(self, user_id: int) -> str:
        new_cookie = f"user_{user_id}_{uuid.uuid4().hex[:12]}"
        self.user_cookies[user_id] = new_cookie
        if user_id in self.cookie_history:
            self.cookie_history[user_id].append(new_cookie)
        else:
            self.cookie_history[user_id] = [new_cookie]
        return new_cookie

cookie_manager = CookieManager()

# ============ HELPER FUNCTIONS ============
def get_user_agent(user_type: str) -> str:
    behavior = USER_BEHAVIORS.get(user_type, USER_BEHAVIORS["normal"])
    agent_types = behavior["user_agent_types"]
    
    all_agents = []
    for agent_type in agent_types:
        all_agents.extend(USER_AGENTS.get(agent_type, []))
    
    return random.choice(all_agents) if all_agents else USER_AGENTS["browser"][0]

def generate_fingerprint(ip: str, user_agent: str) -> str:
    raw = f"{ip}:{user_agent}:{int(time.time())}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def random_headers(
    user_type: str, 
    user_id: int, 
    rotate_ip: bool = False, 
    include_cookie: bool = True,
    existing_cookie: Optional[str] = None
) -> dict:
    if rotate_ip:
        ip = ip_manager.get_rotating_ip()
    else:
        ip = ip_manager.get_ip_for_user(user_id, user_type)
    
    user_agent = get_user_agent(user_type)
    
    headers = {
        "X-API-KEY": API_KEY,
        "User-Agent": user_agent,
        "Accept": random.choice(["application/json", "text/html", "*/*"]),
        "Accept-Language": random.choice(["en-US,en;q=0.9", "fr-FR,fr;q=0.9", "de-DE,de;q=0.9"]),
        "Accept-Encoding": random.choice(["gzip, deflate, br", "gzip, deflate"]),
        "Connection": random.choice(["keep-alive", "close"]),
        "X-Forwarded-For": ip,
        "X-Real-IP": ip,
        "X-Simulated-User-Type": user_type,
        "X-Simulated-User-ID": str(user_id),
        "X-Simulated-Fingerprint": generate_fingerprint(ip, user_agent),
    }
    
    if include_cookie and user_type not in ["attack", "bad_reputation"]:
        if existing_cookie:
            cookie_val = existing_cookie
        else:
            cookie_val = cookie_manager.get_or_create_cookie(user_id, user_type)
        
        if cookie_val:
            headers["Cookie"] = f"X-TrianSec-User-ID={cookie_val}"
    
    if user_type in ["attack", "bad_reputation"]:
        headers["X-Simulated-Label"] = "attack"
    
    return headers

# ============ USER BEHAVIORS ============

async def normal_user_behavior(user_id: int, stop_event: asyncio.Event):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        session_endpoints = []
        user_cookie = None
        
        while not stop_event.is_set():
            try:
                if len(session_endpoints) < 3 or random.random() < 0.3:
                    session_endpoints = random.sample(NORMAL_ENDPOINTS, min(3, len(NORMAL_ENDPOINTS)))
                
                endpoint = random.choice(session_endpoints)
                
                if endpoint == "/api/search" and random.random() < 0.4:
                    search_terms = ["laptop", "phone", "tablet", "book", "mouse", "keyboard"]
                    q = random.choice(search_terms)
                    endpoint = f"/api/search?q={q}"
                
                headers = random_headers("normal", user_id, rotate_ip=False, include_cookie=True, existing_cookie=user_cookie)
                
                if not user_cookie and "Cookie" in headers:
                    cookie_parts = headers["Cookie"].split("=")
                    if len(cookie_parts) > 1:
                        user_cookie = cookie_parts[1]
                
                response = await client.get(endpoint, headers=headers, timeout=5)
                
                if response.status_code == 429:
                    print(f"\n⚠️  Rate limited: Normal User {user_id} at {endpoint}")
                
                await asyncio.sleep(random.uniform(*USER_BEHAVIORS["normal"]["delay_range"]))
                
            except Exception as e:
                await asyncio.sleep(random.uniform(1.0, 3.0))

async def suspicious_user_behavior(user_id: int, stop_event: asyncio.Event):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        user_cookie = None
        
        while not stop_event.is_set():
            try:
                if random.random() < 0.7:
                    endpoint = random.choice(NORMAL_ENDPOINTS)
                else:
                    endpoint = random.choice(SUSPICIOUS_ENDPOINTS)
                
                headers = random_headers("suspicious", user_id, rotate_ip=False, include_cookie=True, existing_cookie=user_cookie)
                
                if not user_cookie and "Cookie" in headers:
                    cookie_parts = headers["Cookie"].split("=")
                    if len(cookie_parts) > 1:
                        user_cookie = cookie_parts[1]
                
                response = await client.get(endpoint, headers=headers, timeout=5)
                
                if response.status_code == 429:
                    print(f"\n⚠️  Suspicious user {user_id} rate limited at {endpoint}")
                
                await asyncio.sleep(random.uniform(*USER_BEHAVIORS["suspicious"]["delay_range"]))
                
            except Exception as e:
                await asyncio.sleep(random.uniform(0.5, 1.5))

async def attack_user_behavior(user_id: int, stop_event: asyncio.Event):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        attack_count = 0
        max_attacks = random.randint(5, 15)
        
        while not stop_event.is_set() and attack_count < max_attacks:
            try:
                attack_type = random.choice(["brute_force", "scanning", "injection"])
                
                if attack_type == "brute_force":
                    passwords = ["admin123", "password123", "123456", "admin", "root"]
                    for pwd in random.sample(passwords, min(2, len(passwords))):
                        headers = random_headers("attack", user_id, rotate_ip=True, include_cookie=False)
                        response = await client.post(
                            "/login",
                            json={"username": "admin", "password": pwd},
                            headers=headers,
                            timeout=3
                        )
                        attack_count += 1
                        if attack_count % 2 == 0:
                            print(f"\n🔴 Attack {attack_count}/{max_attacks}: Brute force attempt")
                        await asyncio.sleep(random.uniform(0.3, 0.8))
                
                elif attack_type == "scanning":
                    for endpoint in random.sample(ATTACK_ENDPOINTS, min(2, len(ATTACK_ENDPOINTS))):
                        headers = random_headers("attack", user_id, rotate_ip=True, include_cookie=False)
                        response = await client.get(endpoint, headers=headers, timeout=3)
                        attack_count += 1
                        if attack_count % 2 == 0:
                            print(f"\n🔴 Attack {attack_count}/{max_attacks}: Scanning {endpoint}")
                        await asyncio.sleep(random.uniform(0.2, 0.5))
                
                elif attack_type == "injection":
                    payloads = ["' OR '1'='1", "admin'--", "1' AND 1=1--"]
                    payload = random.choice(payloads)
                    headers = random_headers("attack", user_id, rotate_ip=True, include_cookie=False)
                    response = await client.get(
                        f"/api/search?q={payload}",
                        headers=headers,
                        timeout=3
                    )
                    attack_count += 1
                    if attack_count % 2 == 0:
                        print(f"\n🔴 Attack {attack_count}/{max_attacks}: SQL injection attempt")
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                
                await asyncio.sleep(random.uniform(1.0, 3.0))
                
            except Exception as e:
                await asyncio.sleep(random.uniform(1.0, 2.0))
        
        if attack_count >= max_attacks:
            print(f"\n✅ Attack user {user_id} completed {attack_count} attacks")

# 🔥 NEW: Bad reputation user - designed to build terrible reputation rapidly
async def bad_reputation_user_behavior(user_id: int, stop_event: asyncio.Event):
    """
    User designed to build very bad reputation rapidly through:
    - Very fast requests (0.1-0.5s delays)
    - High error rate (30%)
    - Constant IP rotation
    - No cookies
    - Hitting sensitive endpoints
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
        attack_count = 0
        max_attacks = random.randint(20, 40)  # Many attacks
        print(f"\n🔥 Bad reputation user {user_id} starting ({max_attacks} attacks)")
        
        while not stop_event.is_set() and attack_count < max_attacks:
            try:
                # Mix of different bad behaviors
                behavior = random.choice([
                    "brute_force", 
                    "scanning", 
                    "injection", 
                    "rapid_requests", 
                    "error_spike",
                    "sensitive_endpoint"
                ])
                
                if behavior == "brute_force":
                    passwords = ["admin123", "password123", "123456", "admin", "root", "letmein", "welcome"]
                    for pwd in random.sample(passwords, min(3, len(passwords))):
                        headers = random_headers("bad_reputation", user_id, rotate_ip=True, include_cookie=False)
                        response = await client.post(
                            "/login",
                            json={"username": "admin", "password": pwd},
                            headers=headers,
                            timeout=3
                        )
                        attack_count += 1
                        print(f"\n🔴 BadRep {user_id}: Brute force {attack_count}/{max_attacks}")
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                
                elif behavior == "scanning":
                    endpoints = random.sample(ATTACK_ENDPOINTS, min(4, len(ATTACK_ENDPOINTS)))
                    for endpoint in endpoints:
                        headers = random_headers("bad_reputation", user_id, rotate_ip=True, include_cookie=False)
                        response = await client.get(endpoint, headers=headers, timeout=3)
                        attack_count += 1
                        print(f"\n🔴 BadRep {user_id}: Scanning {endpoint} {attack_count}/{max_attacks}")
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                
                elif behavior == "injection":
                    payloads = [
                        "' OR '1'='1", 
                        "admin'--", 
                        "1' AND 1=1--", 
                        "' UNION SELECT NULL--",
                        "'; DROP TABLE users--",
                        "' OR 1=1--"
                    ]
                    for payload in random.sample(payloads, min(2, len(payloads))):
                        headers = random_headers("bad_reputation", user_id, rotate_ip=True, include_cookie=False)
                        response = await client.get(
                            f"/api/search?q={payload}",
                            headers=headers,
                            timeout=3
                        )
                        attack_count += 1
                        print(f"\n🔴 BadRep {user_id}: Injection {attack_count}/{max_attacks}")
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                
                elif behavior == "rapid_requests":
                    # Rapid fire requests to trigger rate limiting
                    for _ in range(random.randint(3, 5)):
                        endpoint = random.choice(NORMAL_ENDPOINTS + ["/api/data", "/api/products"])
                        headers = random_headers("bad_reputation", user_id, rotate_ip=True, include_cookie=False)
                        response = await client.get(endpoint, headers=headers, timeout=2)
                        attack_count += 1
                        print(f"\n🔴 BadRep {user_id}: Rapid request {attack_count}/{max_attacks}")
                        await asyncio.sleep(random.uniform(0.05, 0.15))
                
                elif behavior == "error_spike":
                    # Cause many errors (404s, 500s)
                    endpoints = ["/api/missing", "/api/error", "/invalid", "/test", "/fake"]
                    for endpoint in random.sample(endpoints, min(2, len(endpoints))):
                        headers = random_headers("bad_reputation", user_id, rotate_ip=True, include_cookie=False)
                        response = await client.get(endpoint, headers=headers, timeout=3)
                        attack_count += 1
                        print(f"\n🔴 BadRep {user_id}: Error spike {attack_count}/{max_attacks}")
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                
                elif behavior == "sensitive_endpoint":
                    # Hit sensitive endpoints repeatedly
                    sensitive = ["/api/data", "/api/private", "/config", "/api/users/me"]
                    endpoint = random.choice(sensitive)
                    headers = random_headers("bad_reputation", user_id, rotate_ip=True, include_cookie=False)
                    response = await client.get(endpoint, headers=headers, timeout=3)
                    attack_count += 1
                    print(f"\n🔴 BadRep {user_id}: Sensitive endpoint {endpoint} {attack_count}/{max_attacks}")
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                
                # Small delay between attack cycles
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
            except Exception as e:
                print(f"\n❌ BadRep user {user_id} error: {e}")
                await asyncio.sleep(random.uniform(0.5, 1.0))
        
        print(f"\n🔥 Bad reputation user {user_id} completed {attack_count} attacks!")

# ============ MAIN SIMULATION ============

class Simulation:
    def __init__(self):
        self.tasks = []
        self.stop_event = asyncio.Event()
        self.start_time = None
    
    def signal_handler(self, sig, frame):
        print("\n\n🛑 Stopping simulation gracefully...")
        self.stop_event.set()
    
    async def monitor_stats(self):
        while not self.stop_event.is_set():
            elapsed = time.time() - self.start_time
            minutes_remaining = max(0, DURATION_MINUTES - (elapsed / 60))
            
            unique_ips = len(ip_manager.used_ips)
            total_ip_changes = sum(len(history) - 1 for history in ip_manager.ip_history.values() if len(history) > 1)
            total_cookies = len(cookie_manager.user_cookies)
            
            print(f"\r📊 Running: {elapsed/60:.1f}/{DURATION_MINUTES} min | "
                  f"Remaining: {minutes_remaining:.1f} min | "
                  f"Unique IPs: {unique_ips} | "
                  f"IP Changes: {total_ip_changes} | "
                  f"Cookies: {total_cookies} | "
                  f"Tasks: {len(self.tasks)}", end="", flush=True)
            
            await asyncio.sleep(5)
    
    async def run(self):
        print("=" * 80)
        print("🔥 TRIANSEC - BAD REPUTATION SIMULATION")
        print("=" * 80)
        print(f"⏱️  Duration: {DURATION_MINUTES} minutes")
        print(f"🔑 API Key: {API_KEY[:20]}...")
        print(f"🌐 IP Pool Size: {len(IP_POOL)} unique IPs")
        print("👥 User Mix:")
        print(f"   ✅ Normal users: {NORMAL_USERS_COUNT} (consistent IP, cookies)")
        print(f"   ⚠️  Suspicious users: {SUSPICIOUS_USERS_COUNT} (consistent IP, faster)")
        print(f"   🔴 Attack users: {ATTACK_USERS_COUNT} (rotating IPs)")
        print(f"   🔥 BAD REPUTATION users: {BAD_REPUTATION_USERS_COUNT} (VERY aggressive!)")
        print("=" * 80)
        print("\n🔥 Bad Reputation User Behavior:")
        print("   • 20-40 attacks per user")
        print("   • Brute force, scanning, SQL injection")
        print("   • Rapid requests (0.1-0.5s delays)")
        print("   • 30% error rate")
        print("   • Constant IP rotation (every 1-3 seconds)")
        print("   • No cookies (anonymous)")
        print("   • Hitting sensitive endpoints")
        print("=" * 80)
        print("\n🚀 Starting simulation... Press Ctrl+C to stop early\n")
        
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.start_time = time.time()
        
        user_id = 0
        
        # Normal users
        for i in range(NORMAL_USERS_COUNT):
            self.tasks.append(asyncio.create_task(normal_user_behavior(user_id + i, self.stop_event)))
        user_id += NORMAL_USERS_COUNT
        
        # Suspicious users
        for i in range(SUSPICIOUS_USERS_COUNT):
            self.tasks.append(asyncio.create_task(suspicious_user_behavior(user_id + i, self.stop_event)))
        user_id += SUSPICIOUS_USERS_COUNT
        
        # Attack users
        for i in range(ATTACK_USERS_COUNT):
            self.tasks.append(asyncio.create_task(attack_user_behavior(user_id + i, self.stop_event)))
        user_id += ATTACK_USERS_COUNT
        
        # 🔥 Bad reputation users
        for i in range(BAD_REPUTATION_USERS_COUNT):
            self.tasks.append(asyncio.create_task(bad_reputation_user_behavior(user_id + i, self.stop_event)))
        
        monitor_task = asyncio.create_task(self.monitor_stats())
        
        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=DURATION_MINUTES * 60)
        except asyncio.TimeoutError:
            print("\n\n✅ Simulation completed successfully!")
            self.stop_event.set()
        
        monitor_task.cancel()
        for task in self.tasks:
            task.cancel()
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        elapsed = time.time() - self.start_time
        print("\n" + "=" * 80)
        print("📊 SIMULATION COMPLETE")
        print("=" * 80)
        print(f"⏱️  Runtime: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print(f"🌐 Unique IPs used: {len(ip_manager.used_ips)}")
        print(f"🔄 Total IP changes: {sum(len(h) - 1 for h in ip_manager.ip_history.values() if len(h) > 1)}")
        print(f"🍪 Cookies created: {len(cookie_manager.user_cookies)}")
        print(f"👥 Total simulated users: {len(self.tasks)}")
        print("=" * 80)
        print("\n💡 Check your dashboard at http://localhost:3000")
        print("📋 Look for:")
        print("   🔥 Bad reputation users should have:")
        print("      • Very high violation counts (50+)")
        print("      • High risk scores (70%+)")
        print("      • Should be throttled or blocked")
        print("   • Attack users should show high risk")
        print("   • Normal users should show low risk")
        print("=" * 80)


if __name__ == "__main__":
    simulation = Simulation()
    asyncio.run(simulation.run())