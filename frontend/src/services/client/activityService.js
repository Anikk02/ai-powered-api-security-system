// activityService.js
import axios from "axios";
import mockActivityData from "../../utils/client/mockActivityData";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const DEBUG = import.meta.env.DEV;

const CACHE_KEY = "trianSec_activity_cache";

// 🔹 In-memory mirrors of localStorage, hydrated synchronously at module
// init so the very first render (even after a hard refresh) can paint
// last-known REAL data instead of blocking or falling back to mock.
let cachedData = null;
let cacheTimestamp = null;
let pendingRequest = null;

try {
  const raw = localStorage.getItem(CACHE_KEY);
  if (raw) {
    const parsed = JSON.parse(raw);
    if (parsed?.data) {
      cachedData = parsed.data;
      cacheTimestamp = parsed.timestamp;
    }
  }
} catch (e) {
  if (DEBUG) console.warn("Failed to hydrate activity cache", e);
}

const persistRealData = (data, timestamp) => {
  cachedData = data;
  cacheTimestamp = timestamp;
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ data, timestamp }));
  } catch (e) {
    if (DEBUG) console.warn("Failed to persist activity cache", e);
  }
};

export const activityService = {
  // 🔹 Synchronous read of whatever real data we already have, so the hook
  // can paint it on first render with zero network wait.
  getCachedActivity: () => cachedData,

  getActivity: async (window = 600) => {
    if (USE_MOCK) {
      if (DEBUG) console.log("🧪 MOCK MODE ACTIVE");
      return { ...mockActivityData, isMock: true };
    }

    // 🔹 Dedupe concurrent in-flight calls (Strict Mode, interval overlap, etc.)
    if (pendingRequest) {
      return pendingRequest;
    }

    pendingRequest = (async () => {
      try {
        const token = localStorage.getItem("access_token");
        const response = await axios.get("/api/dashboard/activity", {
          params: { window },
          headers: { Authorization: `Bearer ${token}` },
        });

        const hasData = response.data?.trend?.length > 0 ||
                        response.data?.endpoints?.length > 0 ||
                        response.data?.timeline?.length > 0;

        if (!hasData) {
          // Real API answered but has nothing yet (cold query, etc).
          // Prefer stale-but-real cache over mock — never regress a
          // visible real dashboard back to demo data.
          if (cachedData) {
            if (DEBUG) console.warn("⚠️ API empty — keeping last known real data");
            return cachedData;
          }
          if (DEBUG) console.warn("⚠️ API empty, no cache yet — using mock placeholder");
          return { ...mockActivityData, isMock: true };
        }

        const realData = { ...response.data, isMock: false };
        persistRealData(realData, Date.now());

        if (DEBUG) {
          console.log("✅ Activity data loaded", {
            trend: response.data?.trend?.length || 0,
            endpoints: response.data?.endpoints?.length || 0,
            timeline: response.data?.timeline?.length || 0,
          });
        }

        return realData;
      } catch (error) {
        if (DEBUG) console.error("❌ API FAILED:", error?.response?.data || error.message);
        // Same rule on hard failure: stale real > mock.
        return cachedData || { ...mockActivityData, isMock: true };
      } finally {
        pendingRequest = null;
      }
    })();

    return pendingRequest;
  },

  clearCache: () => {
    if (DEBUG) console.log("🧹 Clearing activity cache");
    cachedData = null;
    cacheTimestamp = null;
    pendingRequest = null;
    try {
      localStorage.removeItem(CACHE_KEY);
    } catch (e) {}
  },
};