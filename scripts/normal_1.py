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
TOTAL_USERS = 50  # Total unique users that will ever exist
MAX_CONCURRENT_USERS = 30  # Max active at any time
USER_LIFETIME_MIN = 5  # Minimum minutes a user stays active
USER_LIFETIME_MAX = 15  # Maximum minutes a user stays active
USER_SLEEP_MIN = 10  # Minimum minutes a user stays inactive before re-joining
USER_SLEEP_MAX = 30  # Maximum minutes a user stays inactive before re-joining

# API Key for authentication
API_KEY = ""

# ============ COMPLETELY DIFFERENT IP POOL (200+ unique IPs) ============
IP_POOL = [
    # Residential IPs (US - East Coast)
    "24.0.0.1", "24.0.0.2", "24.0.0.3", "24.0.0.4", "24.0.0.5",
    "24.0.0.6", "24.0.0.7", "24.0.0.8", "24.0.0.9", "24.0.0.10",
    "24.0.1.1", "24.0.1.2", "24.0.1.3", "24.0.1.4", "24.0.1.5",
    
    # Residential IPs (US - West Coast)
    "67.0.0.1", "67.0.0.2", "67.0.0.3", "67.0.0.4", "67.0.0.5",
    "67.0.0.6", "67.0.0.7", "67.0.0.8", "67.0.0.9", "67.0.0.10",
    "67.0.1.1", "67.0.1.2", "67.0.1.3", "67.0.1.4", "67.0.1.5",
    
    # Residential IPs (Europe - UK)
    "82.0.0.1", "82.0.0.2", "82.0.0.3", "82.0.0.4", "82.0.0.5",
    "82.0.0.6", "82.0.0.7", "82.0.0.8", "82.0.0.9", "82.0.0.10",
    "82.0.1.1", "82.0.1.2", "82.0.1.3", "82.0.1.4", "82.0.1.5",
    
    # Residential IPs (Europe - Germany/France)
    "87.0.0.1", "87.0.0.2", "87.0.0.3", "87.0.0.4", "87.0.0.5",
    "87.0.0.6", "87.0.0.7", "87.0.0.8", "87.0.0.9", "87.0.0.10",
    "87.0.1.1", "87.0.1.2", "87.0.1.3", "87.0.1.4", "87.0.1.5",
    
    # Residential IPs (Asia - Japan)
    "133.0.0.1", "133.0.0.2", "133.0.0.3", "133.0.0.4", "133.0.0.5",
    "133.0.0.6", "133.0.0.7", "133.0.0.8", "133.0.0.9", "133.0.0.10",
    "133.0.1.1", "133.0.1.2", "133.0.1.3", "133.0.1.4", "133.0.1.5",
    
    # Residential IPs (Asia - Singapore/India)
    "139.0.0.1", "139.0.0.2", "139.0.0.3", "139.0.0.4", "139.0.0.5",
    "139.0.0.6", "139.0.0.7", "139.0.0.8", "139.0.0.9", "139.0.0.10",
    "139.0.1.1", "139.0.1.2", "139.0.1.3", "139.0.1.4", "139.0.1.5",
    
    # Residential IPs (Australia)
    "143.0.0.1", "143.0.0.2", "143.0.0.3", "143.0.0.4", "143.0.0.5",
    "143.0.0.6", "143.0.0.7", "143.0.0.8", "143.0.0.9", "143.0.0.10",
    "143.0.1.1", "143.0.1.2", "143.0.1.3", "143.0.1.4", "143.0.1.5",
    
    # Mobile Networks (US - AT&T, Verizon, T-Mobile)
    "166.0.0.1", "166.0.0.2", "166.0.0.3", "166.0.0.4", "166.0.0.5",
    "166.0.0.6", "166.0.0.7", "166.0.0.8", "166.0.0.9", "166.0.0.10",
    "166.0.1.1", "166.0.1.2", "166.0.1.3", "166.0.1.4", "166.0.1.5",
    
    # Mobile Networks (Europe - Vodafone, O2)
    "188.0.0.1", "188.0.0.2", "188.0.0.3", "188.0.0.4", "188.0.0.5",
    "188.0.0.6", "188.0.0.7", "188.0.0.8", "188.0.0.9", "188.0.0.10",
    "188.0.1.1", "188.0.1.2", "188.0.1.3", "188.0.1.4", "188.0.1.5",
    
    # Corporate IPs (Various companies)
    "204.0.0.1", "204.0.0.2", "204.0.0.3", "204.0.0.4", "204.0.0.5",
    "204.0.0.6", "204.0.0.7", "204.0.0.8", "204.0.0.9", "204.0.0.10",
    "204.0.1.1", "204.0.1.2", "204.0.1.3", "204.0.1.4", "204.0.1.5",
    
    # Cloud/Data Center IPs (AWS, Azure, GCP)
    "54.0.0.1", "54.0.0.2", "54.0.0.3", "54.0.0.4", "54.0.0.5",
    "54.0.0.6", "54.0.0.7", "54.0.0.8", "54.0.0.9", "54.0.0.10",
    "54.0.1.1", "54.0.1.2", "54.0.1.3", "54.0.1.4", "54.0.1.5",
    "54.0.2.1", "54.0.2.2", "54.0.2.3", "54.0.2.4", "54.0.2.5",
    
    # Educational Institutions (Universities)
    "128.0.0.1", "128.0.0.2", "128.0.0.3", "128.0.0.4", "128.0.0.5",
    "128.0.0.6", "128.0.0.7", "128.0.0.8", "128.0.0.9", "128.0.0.10",
    "128.0.1.1", "128.0.1.2", "128.0.1.3", "128.0.1.4", "128.0.1.5",
    
    # Government/Military IPs
    "148.0.0.1", "148.0.0.2", "148.0.0.3", "148.0.0.4", "148.0.0.5",
    "148.0.0.6", "148.0.0.7", "148.0.0.8", "148.0.0.9", "148.0.0.10",
    "148.0.1.1", "148.0.1.2", "148.0.1.3", "148.0.1.4", "148.0.1.5",
    
    # ISP Networks (Comcast, Spectrum, Cox)
    "76.0.0.1", "76.0.0.2", "76.0.0.3", "76.0.0.4", "76.0.0.5",
    "76.0.0.6", "76.0.0.7", "76.0.0.8", "76.0.0.9", "76.0.0.10",
    "76.0.1.1", "76.0.1.2", "76.0.1.3", "76.0.1.4", "76.0.1.5",
    "76.0.2.1", "76.0.2.2", "76.0.2.3", "76.0.2.4", "76.0.2.5",
    
    # Residential IPs (Canada, Mexico)
    "64.0.0.1", "64.0.0.2", "64.0.0.3", "64.0.0.4", "64.0.0.5",
    "64.0.0.6", "64.0.0.7", "64.0.0.8", "64.0.0.9", "64.0.0.10",
    "64.0.1.1", "64.0.1.2", "64.0.1.3", "64.0.1.4", "64.0.1.5",
    
    # Residential IPs (South America - Brazil, Argentina)
    "177.0.0.1", "177.0.0.2", "177.0.0.3", "177.0.0.4", "177.0.0.5",
    "177.0.0.6", "177.0.0.7", "177.0.0.8", "177.0.0.9", "177.0.0.10",
    "177.0.1.1", "177.0.1.2", "177.0.1.3", "177.0.1.4", "177.0.1.5",
    
    # Residential IPs (Africa - South Africa, Nigeria)
    "164.0.0.1", "164.0.0.2", "164.0.0.3", "164.0.0.4", "164.0.0.5",
    "164.0.0.6", "164.0.0.7", "164.0.0.8", "164.0.0.9", "164.0.0.10",
    "164.0.1.1", "164.0.1.2", "164.0.1.3", "164.0.1.4", "164.0.1.5",
    
    # Middle East IPs (UAE, Saudi Arabia)
    "94.0.0.1", "94.0.0.2", "94.0.0.3", "94.0.0.4", "94.0.0.5",
    "94.0.0.6", "94.0.0.7", "94.0.0.8", "94.0.0.9", "94.0.0.10",
    "94.0.1.1", "94.0.1.2", "94.0.1.3", "94.0.1.4", "94.0.1.5",
]

# ============ USER AGENTS WITH DIFFERENT VERSIONS ============
USER_AGENTS = [
    # Windows Chrome (different versions)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    # Windows Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
    # Mac Chrome
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Mac Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    # iPhone
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    # Android
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
]

# ============ NORMAL ENDPOINTS ============
NORMAL_ENDPOINTS = [
    "/api/products",
    "/api/search", 
    "/api/feed",
    "/api/profile",
    "/api/users/me",
    "/health",
]

# ============ CLIENT HINTS PLATFORMS ============
PLATFORMS = ['"Windows"', '"macOS"', '"Android"', '"Linux"', '"iOS"', '"Chrome OS"']


# ============ NORMAL USER BEHAVIOR ============
class NormalUserConfig:
    DELAY_MIN = 2.0
    DELAY_MAX = 8.0
    SESSION_LENGTH = 3
    SESSION_BREAK_MIN = 30
    SESSION_BREAK_MAX = 120
    PAGE_VIEWS_PER_SESSION = (2, 5)
    BROWSE_DEPTH = 0.7
    SEARCH_PROBABILITY = 0.3
    ERROR_PROBABILITY = 0.01
    IP_CHANGE_INTERVAL = (3600, 7200)


class IPManager:
    def __init__(self):
        self.used_ips: Dict[int, str] = {}
        self.ip_pool = IP_POOL.copy()
        random.shuffle(self.ip_pool)
        self.ip_index = 0
        self.ip_history: Dict[int, List[str]] = {}
        self.ip_change_timers: Dict[int, float] = {}
    
    def get_ip_for_user(self, user_id: int) -> str:
        if user_id not in self.used_ips:
            ip = self.ip_pool[self.ip_index % len(self.ip_pool)]
            self.used_ips[user_id] = ip
            self.ip_history[user_id] = [ip]
            min_interval, max_interval = NormalUserConfig.IP_CHANGE_INTERVAL
            self.ip_change_timers[user_id] = time.time() + random.uniform(min_interval, max_interval)
            self.ip_index += 1
        else:
            current_time = time.time()
            if current_time > self.ip_change_timers.get(user_id, 0):
                old_ip = self.used_ips[user_id]
                attempts = 0
                while attempts < 10:
                    new_ip = self.ip_pool[random.randint(0, len(self.ip_pool) - 1)]
                    if new_ip != old_ip:
                        self.used_ips[user_id] = new_ip
                        self.ip_history[user_id].append(new_ip)
                        min_interval, max_interval = NormalUserConfig.IP_CHANGE_INTERVAL
                        self.ip_change_timers[user_id] = time.time() + random.uniform(min_interval, max_interval)
                        break
                    attempts += 1
        
        return self.used_ips.get(user_id, self.ip_pool[0])
    
    def get_ip_history(self, user_id: int) -> List[str]:
        return self.ip_history.get(user_id, [])


class CookieManager:
    def __init__(self):
        self.user_cookies: Dict[int, str] = {}
    
    def get_or_create_cookie(self, user_id: int) -> str:
        if user_id not in self.user_cookies:
            cookie_val = f"user_{user_id}_{uuid.uuid4().hex[:12]}"
            self.user_cookies[user_id] = cookie_val
        return self.user_cookies[user_id]
    
    def get_cookie_history(self, user_id: int) -> List[str]:
        return [self.user_cookies.get(user_id)] if user_id in self.user_cookies else []


ip_manager = IPManager()
cookie_manager = CookieManager()


def get_user_agent() -> str:
    return random.choice(USER_AGENTS)


def random_headers(user_id: int) -> dict:
    ip = ip_manager.get_ip_for_user(user_id)
    user_agent = get_user_agent()
    
    # Extract browser and platform from user-agent for consistency
    if "Chrome" in user_agent and "Android" in user_agent:
        platform = '"Android"'
        ua_brand = '"Chromium";v="120", "Not_A Brand";v="24"'
    elif "Chrome" in user_agent and "Macintosh" in user_agent:
        platform = '"macOS"'
        ua_brand = '"Chromium";v="120", "Not_A Brand";v="24"'
    elif "Chrome" in user_agent and "Windows" in user_agent:
        platform = '"Windows"'
        ua_brand = '"Chromium";v="120", "Not_A Brand";v="24"'
    elif "Firefox" in user_agent:
        platform = random.choice(['"Windows"', '"macOS"'])
        ua_brand = '"Firefox";v="121", "Not_A Brand";v="24"'
    elif "Safari" in user_agent and "iPhone" in user_agent:
        platform = '"iOS"'
        ua_brand = '"Safari";v="17", "Not_A Brand";v="24"'
    elif "Safari" in user_agent:
        platform = '"macOS"'
        ua_brand = '"Safari";v="17", "Not_A Brand";v="24"'
    else:
        platform = random.choice(PLATFORMS)
        ua_brand = '"Chromium";v="120", "Not_A Brand";v="24"'
    
    headers = {
        "X-API-KEY": API_KEY,
        "User-Agent": user_agent,
        "Accept": random.choice([
            "application/json",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "application/json, text/plain, */*"
        ]),
        "Accept-Language": random.choice([
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-US,en;q=0.8,fr;q=0.6",
            "en-US,en;q=0.7,de;q=0.3",
            "en-IN,en;q=0.9"
        ]),
        "Accept-Encoding": random.choice([
            "gzip, deflate, br",
            "gzip, deflate",
            "gzip, deflate, br, zstd"
        ]),
        "Connection": random.choice(["keep-alive", "close"]),
        "Cache-Control": random.choice(["max-age=0", "no-cache", "no-store"]),
        # 🔥 Client Hints (for enhanced fingerprint)
        "Sec-Ch-Ua": ua_brand,
        "Sec-Ch-Ua-Mobile": "?0" if "Mobile" not in user_agent and "iPhone" not in user_agent else "?1",
        "Sec-Ch-Ua-Platform": platform,
        "Sec-Ch-Ua-Platform-Version": random.choice([
            '"10.0.19045"', '"10.0.22621"', '"10.0.22000"',
            '"13.0.0"', '"14.0.0"', '"15.0.0"',
            '"12.0.0"'
        ]),
        "Sec-Ch-Ua-Arch": random.choice(['"x86"', '"arm64"', '"x86_64"']),
        "Sec-Ch-Ua-Bitness": random.choice(['"64"', '"32"']),
        "Sec-Ch-Ua-Full-Version": random.choice([
            '"120.0.6099.216"', '"120.0.6099.217"', '"119.0.6045.199"',
            '"118.0.5993.120"', '"117.0.5938.132"'
        ]),
        # 🔥 Sec-Fetch Headers (modern browser signals)
        "Sec-Fetch-Dest": random.choice(["document", "empty", "iframe", "script", "style", "image"]),
        "Sec-Fetch-Mode": random.choice(["navigate", "cors", "no-cors", "same-origin"]),
        "Sec-Fetch-Site": random.choice(["same-origin", "same-site", "cross-site", "none"]),
        "DNT": random.choice(["1", "0"]),
        "Upgrade-Insecure-Requests": "1",
        "X-Forwarded-For": ip,
        "X-Real-IP": ip,
        # 🔥 Custom headers for enhanced fingerprinting
        "X-TimeZone": random.choice([
            "America/New_York", "America/Los_Angeles", "Europe/London",
            "Europe/Berlin", "Asia/Tokyo", "Asia/Singapore",
            "Australia/Sydney", "America/Sao_Paulo", "Asia/Dubai"
        ]),
    }
    
    cookie_val = cookie_manager.get_or_create_cookie(user_id)
    headers["Cookie"] = f"X-TrianSec-User-ID={cookie_val}"
    
    return headers


async def normal_user_behavior(user_id: int, stop_event: asyncio.Event):
    """Simulates a single user that can be active or inactive"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        session_count = 0
        total_requests = 0
        user_active = False
        
        print(f"\n👤 User {user_id} created")
        
        while not stop_event.is_set():
            try:
                # Decide if user should be active or inactive
                if not user_active:
                    # User is inactive - take a long break before becoming active again
                    sleep_duration = random.uniform(USER_SLEEP_MIN * 60, USER_SLEEP_MAX * 60)
                    print(f"\n💤 User {user_id} sleeping for {sleep_duration/60:.1f} minutes")
                    await asyncio.sleep(min(sleep_duration, 60))  # Sleep in chunks to check stop_event
                    user_active = True
                    print(f"\n🔄 User {user_id} waking up")
                    continue
                
                # User is active - run a session
                session_count += 1
                page_views = random.randint(*NormalUserConfig.PAGE_VIEWS_PER_SESSION)
                
                session_type = random.choices(
                    ["browse", "search", "profile", "mixed"],
                    weights=[0.4, 0.2, 0.15, 0.25]
                )[0]
                
                endpoints = []
                
                if session_type == "browse":
                    endpoints.append(random.choice(["/api/products", "/api/feed"]))
                    for _ in range(page_views - 1):
                        if random.random() < NormalUserConfig.BROWSE_DEPTH:
                            endpoints.append(random.choice(["/api/products", "/api/feed"]))
                        else:
                            endpoints.append(random.choice(NORMAL_ENDPOINTS))
                
                elif session_type == "search":
                    search_terms = [
                        "laptop", "phone", "tablet", "book", "mouse", "keyboard",
                        "monitor", "headphones", "speaker", "camera", "drone",
                        "watch", "fitness", "gaming", "office", "home"
                    ]
                    for _ in range(page_views):
                        q = random.choice(search_terms)
                        endpoints.append(f"/api/search?q={q}")
                
                elif session_type == "profile":
                    endpoints.append("/api/profile")
                    endpoints.append("/api/users/me")
                    if page_views > 2:
                        endpoints.append(random.choice(["/api/products", "/api/feed"]))
                
                else:
                    for _ in range(page_views):
                        endpoints.append(random.choice(NORMAL_ENDPOINTS))
                
                for endpoint in endpoints:
                    if stop_event.is_set():
                        break
                    
                    headers = random_headers(user_id)
                    
                    if "search" in endpoint:
                        think_time = random.uniform(1.0, 3.0)
                    elif endpoint in ["/api/products", "/api/feed"]:
                        think_time = random.uniform(3.0, 8.0)
                    else:
                        think_time = random.uniform(1.0, 5.0)
                    
                    await asyncio.sleep(think_time)
                    
                    try:
                        response = await client.get(endpoint, headers=headers, timeout=5)
                        total_requests += 1
                        
                        if random.random() < NormalUserConfig.ERROR_PROBABILITY:
                            error_endpoint = f"/api/missing_{random.randint(1000,9999)}"
                            await client.get(error_endpoint, headers=headers, timeout=3)
                            total_requests += 1
                        
                        if total_requests % 10 == 0:
                            print(f"\n📊 User {user_id}: {total_requests} requests made")
                        
                    except httpx.TimeoutException:
                        print(f"\n⏱️ User {user_id}: timeout on {endpoint}")
                    except Exception as e:
                        pass
                
                # After session, decide if user should stay active or go inactive
                session_break = random.uniform(NormalUserConfig.SESSION_BREAK_MIN, NormalUserConfig.SESSION_BREAK_MAX)
                
                # Randomly decide to go inactive (20% chance after each session)
                if random.random() < 0.2:
                    user_active = False
                    print(f"\n😴 User {user_id} going inactive")
                    # Take a long break (will be handled at the start of the loop)
                else:
                    # Short break between sessions
                    await asyncio.sleep(session_break)
                
            except Exception as e:
                print(f"\n❌ User {user_id} error: {e}")
                await asyncio.sleep(random.uniform(2.0, 5.0))
        
        print(f"\n✅ User {user_id} completed: {total_requests} requests, {session_count} sessions")


# ============ MAIN SIMULATION ============

class Simulation:
    def __init__(self):
        self.tasks = []
        self.stop_event = asyncio.Event()
        self.start_time = None
        self.active_users = set()
        self.user_tasks = {}  # Track which user IDs are running
    
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
            
            active_count = sum(1 for task in self.tasks if not task.done())
            
            print(f"\r📊 Running: {elapsed/60:.1f}/{DURATION_MINUTES} min | "
                  f"Remaining: {minutes_remaining:.1f} min | "
                  f"Active Users: {active_count}/{len(self.tasks)} | "
                  f"Unique IPs: {unique_ips} | "
                  f"IP Changes: {total_ip_changes} | "
                  f"Cookies: {total_cookies}", end="", flush=True)
            
            await asyncio.sleep(5)
    
    async def run(self):
        print("=" * 80)
        print("👤 NORMAL USER SIMULATION (WITH USER CHURN)")
        print("=" * 80)
        print(f"⏱️  Duration: {DURATION_MINUTES} minutes")
        print(f"👥 Total Users: {TOTAL_USERS}")
        print(f"📊 Max Concurrent Users: {MAX_CONCURRENT_USERS}")
        print(f"⏳ User Active Time: {USER_LIFETIME_MIN}-{USER_LIFETIME_MAX} minutes")
        print(f"💤 User Inactive Time: {USER_SLEEP_MIN}-{USER_SLEEP_MAX} minutes")
        print(f"🌐 IP Pool Size: {len(IP_POOL)} unique IPs")
        print("=" * 80)
        print("\n📋 User Behavior:")
        print("   • Users come and go (churn)")
        print("   • 2-8 seconds between requests (human reading time)")
        print("   • 2-5 page views per session")
        print("   • 30-120 second breaks between sessions")
        print("   • Users go inactive for 10-30 minutes")
        print("   • 1% error rate (broken links)")
        print("   • 1-2 hour IP change intervals")
        print("=" * 80)
        print("\n🚀 Starting simulation... Press Ctrl+C to stop early\n")
        
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.start_time = time.time()
        
        # Start users with staggered delays
        for i in range(TOTAL_USERS):
            # Stagger user starts (30 seconds between each)
            initial_delay = random.uniform(0, 30) * (i / TOTAL_USERS) * 0.5
            print(f"\n⏰ User {i} starting in {initial_delay:.1f} seconds")
            await asyncio.sleep(initial_delay)
            
            if not self.stop_event.is_set():
                task = asyncio.create_task(normal_user_behavior(i, self.stop_event))
                self.tasks.append(task)
                
                # Don't exceed max concurrent users
                while len([t for t in self.tasks if not t.done()]) >= MAX_CONCURRENT_USERS:
                    await asyncio.sleep(1)
        
        monitor_task = asyncio.create_task(self.monitor_stats())
        
        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=DURATION_MINUTES * 60)
        except asyncio.TimeoutError:
            print("\n\n✅ Simulation completed successfully!")
            self.stop_event.set()
        
        monitor_task.cancel()
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        elapsed = time.time() - self.start_time
        print("\n" + "=" * 80)
        print("📊 SIMULATION COMPLETE")
        print("=" * 80)
        print(f"⏱️  Runtime: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        print(f"👥 Total users: {len(self.tasks)}")
        print(f"🌐 Unique IPs used: {len(ip_manager.used_ips)}")
        print(f"🔄 Total IP changes: {sum(len(h) - 1 for h in ip_manager.ip_history.values() if len(h) > 1)}")
        print(f"🍪 Cookies created: {len(cookie_manager.user_cookies)}")
        print("=" * 80)
        
        print("\n💡 Check your dashboard at http://localhost:3000")
        print("📋 Normal users should show:")
        print("   • Low risk scores (< 0.30)")
        print("   • 0 violations")
        print("   • Allowed status")
        print("   • Unique fingerprints per user")
        print("   • Varying active user counts over time")
        print("=" * 80)


if __name__ == "__main__":
    simulation = Simulation()
    asyncio.run(simulation.run())