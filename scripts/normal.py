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
NORMAL_USERS_COUNT = 50  # Increased to 50 normal users

# API Key for authentication
API_KEY = ""

# ============ IP POOL ============
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
]

# ============ USER AGENTS ============
USER_AGENTS = [
    # Windows Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
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

# ============ NORMAL USER BEHAVIOR ============
class NormalUserConfig:
    # Realistic human browsing behavior
    DELAY_MIN = 2.0      # Minimum seconds between requests
    DELAY_MAX = 8.0      # Maximum seconds between requests
    SESSION_LENGTH = 3   # Number of requests per session
    SESSION_BREAK_MIN = 30  # Seconds between sessions
    SESSION_BREAK_MAX = 120  # Seconds between sessions
    PAGE_VIEWS_PER_SESSION = (2, 5)  # Random page views per session
    BROWSE_DEPTH = 0.7   # Probability of clicking related links
    SEARCH_PROBABILITY = 0.3  # Probability of using search
    ERROR_PROBABILITY = 0.01  # 1% error rate (404s, etc.)
    IP_CHANGE_INTERVAL = (3600, 7200)  # Change IP every 1-2 hours (like real users)

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

class CookieManager:
    def __init__(self):
        self.user_cookies: Dict[int, str] = {}
    
    def get_or_create_cookie(self, user_id: int) -> str:
        if user_id not in self.user_cookies:
            cookie_val = f"user_{user_id}_{uuid.uuid4().hex[:12]}"
            self.user_cookies[user_id] = cookie_val
        return self.user_cookies[user_id]

ip_manager = IPManager()
cookie_manager = CookieManager()

def get_user_agent() -> str:
    return random.choice(USER_AGENTS)

def random_headers(user_id: int) -> dict:
    ip = ip_manager.get_ip_for_user(user_id)
    user_agent = get_user_agent()
    
    headers = {
        "X-API-KEY": API_KEY,
        "User-Agent": user_agent,
        "Accept": random.choice(["application/json", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"]),
        "Accept-Language": random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.9", "en-US,en;q=0.8,fr;q=0.6"]),
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "Sec-Ch-Ua": '"Chromium";v="120", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": random.choice(['"Windows"', '"macOS"', '"Android"']),
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "X-Forwarded-For": ip,
        "X-Real-IP": ip,
    }
    
    cookie_val = cookie_manager.get_or_create_cookie(user_id)
    headers["Cookie"] = f"X-TrianSec-User-ID={cookie_val}"
    
    return headers

async def normal_user_behavior(user_id: int, stop_event: asyncio.Event):
    """
    Simulates a totally normal user with human-like browsing behavior.
    """
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        session_count = 0
        total_requests = 0
        
        print(f"\n👤 Normal User {user_id} started")
        
        while not stop_event.is_set():
            try:
                # Start a new browsing session
                session_count += 1
                page_views = random.randint(*NormalUserConfig.PAGE_VIEWS_PER_SESSION)
                
                # Randomly decide what to do in this session
                session_type = random.choices(
                    ["browse", "search", "profile", "mixed"],
                    weights=[0.4, 0.2, 0.15, 0.25]
                )[0]
                
                # Build session endpoints
                endpoints = []
                
                if session_type == "browse":
                    # Browse products/feed like a normal user
                    endpoints.append(random.choice(["/api/products", "/api/feed"]))
                    # Add some related navigation
                    for _ in range(page_views - 1):
                        if random.random() < NormalUserConfig.BROWSE_DEPTH:
                            endpoints.append(random.choice(["/api/products", "/api/feed"]))
                        else:
                            endpoints.append(random.choice(NORMAL_ENDPOINTS))
                
                elif session_type == "search":
                    # Search for things
                    search_terms = [
                        "laptop", "phone", "tablet", "book", "mouse", "keyboard",
                        "monitor", "headphones", "speaker", "camera", "drone",
                        "watch", "fitness", "gaming", "office", "home"
                    ]
                    for _ in range(page_views):
                        q = random.choice(search_terms)
                        endpoints.append(f"/api/search?q={q}")
                
                elif session_type == "profile":
                    # Profile-related activities
                    endpoints.append("/api/profile")
                    endpoints.append("/api/users/me")
                    if page_views > 2:
                        endpoints.append(random.choice(["/api/products", "/api/feed"]))
                
                else:  # mixed
                    # Mix of different endpoints
                    for _ in range(page_views):
                        endpoints.append(random.choice(NORMAL_ENDPOINTS))
                
                # Simulate reading/thinking time between page views
                for i, endpoint in enumerate(endpoints):
                    if stop_event.is_set():
                        break
                    
                    headers = random_headers(user_id)
                    
                    # Add some random delays to simulate human reading/thinking
                    # Users spend more time on content pages vs search pages
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
                        
                        # Simulate occasional errors (like clicking a broken link)
                        if random.random() < NormalUserConfig.ERROR_PROBABILITY:
                            # Hit a non-existent endpoint
                            error_endpoint = f"/api/missing_{random.randint(1000,9999)}"
                            await client.get(error_endpoint, headers=headers, timeout=3)
                            total_requests += 1
                        
                        # Log occasional activity
                        if total_requests % 10 == 0:
                            print(f"\n📊 User {user_id}: {total_requests} requests made")
                        
                    except httpx.TimeoutException:
                        print(f"\n⏱️ User {user_id}: timeout on {endpoint}")
                    except Exception as e:
                        # Normal users occasionally experience errors
                        pass
                
                # Session break - user goes idle (like checking email, getting coffee)
                session_break = random.uniform(NormalUserConfig.SESSION_BREAK_MIN, NormalUserConfig.SESSION_BREAK_MAX)
                if session_count % 3 == 0:
                    # Longer break every few sessions (like lunch or meeting)
                    session_break *= 2
                    print(f"\n☕ User {user_id}: taking a long break ({session_break:.0f}s)")
                
                await asyncio.sleep(session_break)
                
            except Exception as e:
                print(f"\n❌ User {user_id} error: {e}")
                await asyncio.sleep(random.uniform(2.0, 5.0))
        
        print(f"\n✅ Normal User {user_id} completed: {total_requests} requests, {session_count} sessions")

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
                  f"Users: {len(self.tasks)} | "
                  f"IPs: {unique_ips} | "
                  f"IP Changes: {total_ip_changes} | "
                  f"Cookies: {total_cookies}", end="", flush=True)
            
            await asyncio.sleep(5)
    
    async def run(self):
        print("=" * 80)
        print("👤 NORMAL USER SIMULATION")
        print("=" * 80)
        print(f"⏱️  Duration: {DURATION_MINUTES} minutes")
        print(f"👥 Users: {NORMAL_USERS_COUNT}")
        print(f"🌐 IP Pool: {len(IP_POOL)} unique IPs")
        print(f"🔑 API Key: {API_KEY[:20]}...")
        print("=" * 80)
        print("\n📋 User Behavior:")
        print("   • 2-8 seconds between requests (human reading time)")
        print("   • 2-5 page views per session")
        print("   • 30-120 second breaks between sessions")
        print("   • 1% error rate (broken links)")
        print("   • 1-2 hour IP change intervals")
        print("   • Persistent cookies")
        print("   • Realistic user agents (Chrome, Firefox, Safari)")
        print("   • Mixed browsing, searching, and profile views")
        print("=" * 80)
        print("\n🚀 Starting simulation... Press Ctrl+C to stop early\n")
        
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.start_time = time.time()
        
        # Start all normal users
        for i in range(NORMAL_USERS_COUNT):
            self.tasks.append(asyncio.create_task(normal_user_behavior(i, self.stop_event)))
        
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
        print("=" * 80)

if __name__ == "__main__":
    simulation = Simulation()
    asyncio.run(simulation.run())