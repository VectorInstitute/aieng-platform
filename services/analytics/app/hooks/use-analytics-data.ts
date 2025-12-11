import { useState, useEffect, useCallback } from 'react';
import type { AnalyticsSnapshot } from '@/lib/types';

interface UseAnalyticsDataResult {
  data: AnalyticsSnapshot | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refetch: () => void;
}

const REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes

export function useAnalyticsData(): UseAnalyticsDataResult {
  const [data, setData] = useState<AnalyticsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const response = await fetch('/analytics/api/snapshot');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const json = await response.json();
      setData(json);
      // Use the timestamp from the snapshot data (when it was collected)
      setLastUpdated(json.timestamp ? new Date(json.timestamp) : null);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch analytics data:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();

    const interval = setInterval(fetchData, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchData]);

  return {
    data,
    loading,
    error,
    lastUpdated,
    refetch: fetchData,
  };
}
