-- 202606270001_scan_eligibility_index.sql
--
-- Phase 2 (tech debt overhaul): scanner and public surface filter devices
-- by (scan_enabled = true AND scan_eligibility = 'active_scan' AND
-- manifest_code IS NOT NULL). The supabase repository was post-filtering
-- this in Python after pulling pages of rows; now the predicate is pushed
-- to SQL and this partial index makes the active-scan slice O(matches)
-- instead of O(catalog_size).
--
-- The index is partial so it stays small even as the catalog grows: only
-- rows that are scan-eligible at all are indexed. The supporting
-- expression on manifest_code keeps the planner happy when callers also
-- ask for "must have a manifest" (which is required for the worker to
-- issue a meaningful OTA query).

CREATE INDEX IF NOT EXISTS devices_active_scan_partial_idx
ON devices (name)
WHERE scan_enabled = true
  AND scan_eligibility = 'active_scan'
  AND manifest_code IS NOT NULL;

-- A second index keyed on the scan_group_key is used by the scanner
-- sharding step (stable_group_scan_shard reads the group key per device).
-- Without an index the cycle-day shard scan over a large active set is a
-- sequential scan of the partial set; this brings it down to a btree seek.
CREATE INDEX IF NOT EXISTS devices_active_scan_group_partial_idx
ON devices (scan_group_key)
WHERE scan_enabled = true
  AND scan_eligibility = 'active_scan'
  AND manifest_code IS NOT NULL;
