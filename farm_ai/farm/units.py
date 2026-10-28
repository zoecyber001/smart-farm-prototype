"""Pure unit conversions, shared by every layer.

Raw sensor counts -> volumetric soil water (% VWC) -> plant-available water (0-1),
plus battery percentage and clock formatting. No imports from the rest of the
package: these functions are trivially testable in isolation.
"""
from datetime import datetime, timezone


def local_hour(ts, tz_hours=1):
    """Hour of day (0-24) at the farm. Nigeria = UTC+1."""
    return ((ts + tz_hours * 3600) % 86400) / 3600.0


def raw_to_vwc(raw, node, soil):
    """Capacitive soil sensor: high raw = dry. Two-point calibration:
    reading in air -> 0 %, reading in water -> saturation."""
    f = (node['dry_raw'] - raw) / float(node['dry_raw'] - node['wet_raw'])
    return f * soil['sat']


def vwc_to_raw(vwc, node, soil):
    """Inverse of raw_to_vwc; lets tests and the simulator speak in physical units."""
    return node['dry_raw'] - (vwc / float(soil['sat'])) * (node['dry_raw'] - node['wet_raw'])


def aw_from_vwc(vwc, soil):
    """Volumetric water -> fraction of plant-available water (wp = 0, fc = 1)."""
    return (vwc - soil['wp']) / float(soil['fc'] - soil['wp'])


def vwc_from_aw(aw, soil):
    """Inverse of aw_from_vwc."""
    return soil['wp'] + aw * (soil['fc'] - soil['wp'])


def batt_pct(v):
    """Battery voltage (18650/LiFePO4-ish 3.3-4.15 V range) -> 0-100 %."""
    return max(0, min(100, (v - 3.3) / (4.15 - 3.3) * 100))


def fmt_time(ts):
    """Compact human timestamp for the dashboard and evidence strings."""
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%d %b %H:%M')
