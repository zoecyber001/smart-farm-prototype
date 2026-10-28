"""Watering advice, as a swappable strategy (implements the AdviceStrategy port).

The default strategy reads soil type (what the soil can hold), crop + growth stage
(what the plant needs now), temperature (heat raises water use) and the ML drying
forecast (when to water, not just whether) — and answers in crop terms:
"Water Bed A (Tomato) for 22 min now", with the reason in the detail line.

To try a different policy (e.g. cost-aware, sensor-fusion, agronomist rules),
implement advise(context) and inject it; the engine, decisions and dashboard
follow automatically.
"""
import math

from . import units
from .ports import AdviceContext

# Faults that make automatic watering dangerous or pointless; the decision service
# halts on these. Faults whose data cannot be trusted live in UNRELIABLE.
BLOCKING = ('PUMP_NO_CURRENT', 'PUMP_JAMMED', 'LINE_BLOCKED', 'LEAK')
UNRELIABLE = ('SENSOR_FAULT', 'SENSOR_STUCK', 'NODE_OFFLINE')


def _litres_for(aw, stage, soil, node):
    """Litres needed to refill from current available water to the stage target."""
    deficit_pts = max(0.0, stage['target_aw'] - aw) * (soil['fc'] - soil['wp'])
    return deficit_pts / 100.0 * stage['root_mm'] * node['area_m2']          # 1 mm over 1 m2 = 1 L


class ThresholdAdvisor:
    """Soil-agnostic trigger points per growth stage, split cycles on slow soils."""

    def advise(self, ctx):
        node, soil, crop, stage, days = ctx.node, ctx.soil, ctx.crop, ctx.stage, ctx.days
        latest, history, forecast_h = ctx.latest, ctx.history, ctx.forecast_h
        bed = node['bed']
        vwc = latest['vwc']
        aw = units.aw_from_vwc(vwc, soil)
        hot = latest.get('temp', 25) >= 32
        trigger = stage['trigger_aw'] + (0.05 if hot else 0.0)
        litres = _litres_for(aw, stage, soil, node)
        total_min = litres / node['design_flow_lpm']
        run_min = int(min(math.ceil(total_min), soil['max_run_min']))
        leftover_min = int(math.ceil(total_min - run_min)) if total_min - run_min > 1 else 0
        ctx_text = "{} at {} stage (day {}). {}".format(crop['label'], stage['name'], days, stage['needs'])
        pct = int(round(aw * 100))

        out = {'node': node['id'], 'bed': bed, 'crop': crop['label'], 'stage': stage['name'], 'day': days,
               'soil': soil['label'], 'aw_pct': pct, 'trigger_pct': int(round(trigger * 100)),
               'target_pct': int(round(stage['target_aw'] * 100)), 'minutes': 0, 'litres': 0,
               'status': 'ok', 'urgency': 'none', 'headline': '', 'detail': ''}

        recent = history[-5:] if history else []
        rise = (vwc - min(r['vwc'] for r in recent)) if recent else 0
        recent_irr = sum(r.get('irr_s', 0) for r in recent)
        rain_note = (' Moisture jumped without irrigation, so this was probably rain.' if rise >= 4 and recent_irr == 0 else '')

        blocking = ctx.blocking
        if aw > 1.05:
            out.update(status='too_wet', headline='{}: do not water, soil is saturated'.format(bed),
                       detail='{}% of usable water, above the {}% soil can hold. Check drainage.{} {}'.format(pct, 100, rain_note, ctx_text))
        elif aw <= trigger:
            urgent = aw < 0.30
            out.update(status='water_now', urgency='urgent' if urgent else 'today', minutes=run_min, litres=int(round(litres)))
            detail = ('{} soil is at {}% of usable water; this stage needs it above {}%{}. {}'
                      .format(soil['label'].capitalize(), pct, int(round(trigger * 100)),
                              ' (raised because it is hot)' if hot else '', ctx_text))
            if leftover_min:
                detail += ' {} soil takes water slowly: water {} min now, then repeat in {} min for the remaining {} min.'.format(
                    soil['label'].capitalize(), run_min, soil['soak_min'], leftover_min)
            out['headline'] = '{}Water {} ({}) for {} min now'.format('URGENT: ' if urgent else '', bed, crop['label'], run_min)
            out['detail'] = detail + rain_note
            if blocking:
                hand = int(round(litres))
                out.update(status='check_hardware', urgency='urgent',
                           headline='{}: water by hand, about {} litres. Automatic watering is stopped.'.format(bed, hand),
                           detail='The soil needs water now ({}% left, needs >{}%) but the hardware has a fault: {}. {}'.format(
                               pct, int(round(trigger * 100)), blocking[0]['title'].lower(), ctx_text))
        elif forecast_h is not None and forecast_h <= 12:
            out.update(status='water_soon', urgency='soon',
                       headline='{}: will need water in about {} h'.format(bed, max(1, int(round(forecast_h)))),
                       detail='{}% of usable water now; the forecast says it reaches the {}% trigger in about {} h. '
                              'Best to water in the cool of early morning or evening to cut evaporation. {}'.format(
                                  pct, int(round(trigger * 100)), max(1, int(round(forecast_h))), ctx_text))
        else:
            eta = '' if forecast_h is None else ' Next watering expected in about {} h.'.format(int(round(min(forecast_h, 99))))
            out.update(headline='{}: no action needed'.format(bed),
                       detail='{}% of usable water left ({} soil). Needs to stay above {}%.{}{} {}'.format(
                           pct, soil['label'], int(round(trigger * 100)), eta, rain_note, ctx_text))
        return out
