// useActivity.js
import { activityService } from "../../services/client/activityService";
import { useEffect, useState, useRef } from "react";

const normalizeActivityData = (result) => ({
  timeline: result.timeline || [],
  endpoints: result.endpoints || [],
  trend: result.trend || [],
  insights: result.insights || null,
  metrics: result.metrics || null,
  peak: result.peak || null,
  patterns: result.patterns || [],
  correlations: result.correlations || [],
  topEndpoint: result.topEndpoint || null,
  healthScore: typeof result.healthScore === 'number' ? result.healthScore : null,
  isMock: !!result.isMock,
});

const EMPTY_DATA = {
  timeline: [], endpoints: [], trend: [], insights: null, metrics: null,
  peak: null, patterns: [], correlations: [], topEndpoint: null,
  healthScore: null, isMock: false,
};

export const useActivity = () => {
  // 🔹 Read once at mount: if we already have real data cached (this tab
  // session or a previous visit via localStorage), paint it immediately —
  // no skeleton, no mock flash.
  const cachedOnMount = activityService.getCachedActivity();

  const [data, setData] = useState(
    cachedOnMount ? normalizeActivityData(cachedOnMount) : EMPTY_DATA
  );
  // loading = true only when we truly have nothing to show yet.
  const [loading, setLoading] = useState(!cachedOnMount);
  // refreshing = true while re-fetching in the background behind
  // already-visible (possibly stale) data.
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const isFetching = useRef(false);
  const initialLoadDone = useRef(!!cachedOnMount);

  useEffect(() => {
    let active = true;

    const fetchData = async (background) => {
      if (background) setRefreshing(true);
      else setLoading(true);

      try {
        const result = await activityService.getActivity();
        if (result && active) {
          setData(normalizeActivityData(result));
          setError(null);
          initialLoadDone.current = true;
        }
      } catch (err) {
        if (active) setError(err);
      } finally {
        if (active) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    };

    // Always fetch fresh data on mount: foreground (skeleton) if nothing
    // cached, background (silent) if we're already showing stale real data.
    fetchData(!!cachedOnMount);

    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 🔄 Background refresh every 30s
  useEffect(() => {
    let active = true;
    const refreshInterval = setInterval(async () => {
      if (isFetching.current || !initialLoadDone.current) return;
      try {
        isFetching.current = true;
        setRefreshing(true);
        const result = await activityService.getActivity();
        if (result && active) {
          setData(normalizeActivityData(result));
        }
      } catch (err) {
        console.error('Background refresh failed:', err);
      } finally {
        isFetching.current = false;
        if (active) setRefreshing(false);
      }
    }, 30000);

    return () => {
      active = false;
      clearInterval(refreshInterval);
    };
  }, []);

  return { data, loading, refreshing, error };
};