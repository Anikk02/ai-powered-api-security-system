import asyncio
import time
import statistics
from typing import List, Dict
import httpx

# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "http://localhost:8000"
TOTAL_USERS = 500
CONCURRENT_BATCH = 50  # Process 50 at a time
DEFAULT_PASSWORD = "TestPass123"


# ============================================================
# LOAD TEST FUNCTIONS
# ============================================================

async def login_user(
    client: httpx.AsyncClient,
    email: str,
    password: str,
) -> Dict:
    """Login a single user and return timing info."""
    start = time.perf_counter()
    try:
        response = await client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=30.0,
        )
        elapsed = (time.perf_counter() - start) * 1000  # ms
        
        return {
            "email": email,
            "status": response.status_code,
            "elapsed_ms": elapsed,
            "success": response.status_code == 200,
            "tokens": response.json() if response.status_code == 200 else None,
        }
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {
            "email": email,
            "status": 0,
            "elapsed_ms": elapsed,
            "success": False,
            "error": str(e),
        }


async def access_me(
    client: httpx.AsyncClient,
    access_token: str,
) -> Dict:
    """Access /me endpoint with token."""
    start = time.perf_counter()
    try:
        response = await client.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        elapsed = (time.perf_counter() - start) * 1000
        return {
            "status": response.status_code,
            "elapsed_ms": elapsed,
            "success": response.status_code == 200,
        }
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return {"status": 0, "elapsed_ms": elapsed, "success": False}


async def run_load_test():
    """Run the complete load test."""
    
    print("=" * 60)
    print(f"  LOAD TEST: {TOTAL_USERS} Users")
    print("=" * 60)
    print()
    
    # ─────────────────────────────────────────────────────────
    # Phase 1: Login all 500 users
    # ─────────────────────────────────────────────────────────
    print("[INFO] Phase 1: Login 500 users")
    print(f"   Batch size: {CONCURRENT_BATCH}")
    print()
    
    login_results: List[Dict] = []
    
    async with httpx.AsyncClient() as client:
        overall_start = time.perf_counter()
        
        for batch_start in range(0, TOTAL_USERS, CONCURRENT_BATCH):
            batch_end = min(batch_start + CONCURRENT_BATCH, TOTAL_USERS)
            
            tasks = []
            for i in range(batch_start + 1, batch_end + 1):
                email = f"testuser{i:04d}@triansec.dev"
                tasks.append(login_user(client, email, DEFAULT_PASSWORD))
            
            results = await asyncio.gather(*tasks)
            login_results.extend(results)
            
            success_count = sum(1 for r in results if r["success"])
            print(f"   Batch {batch_start+1}-{batch_end}: "
                  f"{success_count}/{len(results)} success")
        
        login_elapsed = (time.perf_counter() - overall_start) * 1000
    
    # Analyze login results
    successful_logins = [r for r in login_results if r["success"]]
    failed_logins = [r for r in login_results if not r["success"]]
    login_times = [r["elapsed_ms"] for r in successful_logins]
    
    print()
    print(f"   [OK] Successful: {len(successful_logins)}")
    print(f"   [FAIL] Failed: {len(failed_logins)}")
    if login_times:
        print(f"   Avg: {statistics.mean(login_times):.1f}ms")
        print(f"   P50: {statistics.median(login_times):.1f}ms")
        print(f"   P95: {sorted(login_times)[int(len(login_times)*0.95)]:.1f}ms")
        print(f"   P99: {sorted(login_times)[int(len(login_times)*0.99)]:.1f}ms")
        print(f"   Max: {max(login_times):.1f}ms")
    print(f"   Total Time: {login_elapsed:.0f}ms")
    
    # ─────────────────────────────────────────────────────────
    # Phase 2: Access /me with all tokens
    # ─────────────────────────────────────────────────────────
    print()
    print("[INFO] Phase 2: Access /me for all logged-in users")
    
    me_results: List[Dict] = []
    
    async with httpx.AsyncClient() as client:
        me_start = time.perf_counter()
        
        for batch_start in range(0, len(successful_logins), CONCURRENT_BATCH):
            batch = successful_logins[batch_start:batch_start + CONCURRENT_BATCH]
            
            tasks = [
                access_me(client, r["tokens"]["access_token"])
                for r in batch
            ]
            results = await asyncio.gather(*tasks)
            me_results.extend(results)
        
        me_elapsed = (time.perf_counter() - me_start) * 1000
    
    successful_me = [r for r in me_results if r["success"]]
    me_times = [r["elapsed_ms"] for r in successful_me]
    
    print(f"   [OK] Successful: {len(successful_me)}")
    if me_times:
        print(f"   Avg: {statistics.mean(me_times):.1f}ms")
        print(f"   P50: {statistics.median(me_times):.1f}ms")
        print(f"   P95: {sorted(me_times)[int(len(me_times)*0.95)]:.1f}ms")
    print(f"   Total Time: {me_elapsed:.0f}ms")
    
    # ─────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  LOAD TEST SUMMARY")
    print("=" * 60)
    print(f"  Total users:     {TOTAL_USERS}")
    print(f"  Login success:   {len(successful_logins)} ({len(successful_logins)/TOTAL_USERS*100:.1f}%)")
    print(f"  /me success:     {len(successful_me)} ({len(successful_me)/max(len(successful_logins),1)*100:.1f}%)")
    if login_times:
        print(f"  Login avg:       {statistics.mean(login_times):.1f}ms")
    if me_times:
        print(f"  /me avg:         {statistics.mean(me_times):.1f}ms")
    print()
    
    # Pass/Fail criteria
    all_pass = True
    if len(successful_logins) < TOTAL_USERS * 0.95:
        print("  [FAIL] Login success rate < 95%")
        all_pass = False
    if login_times and statistics.mean(login_times) > 5000:
        print("  [FAIL] Average login time > 5s")
        all_pass = False
    if me_times and statistics.mean(me_times) > 500:
        print("  [FAIL] Average /me time > 500ms")
        all_pass = False
    
    if all_pass:
        print("  [PASS] ALL CHECKS PASSED")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_load_test())
