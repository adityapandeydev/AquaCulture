"""Request contract and conversion to model input."""
from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from ml.models.history import CHANNELS, HISTORY, HORIZONS, Samples

MINIMUM_COVERAGE, MINIMUM_HOURS, RECENT_HOURS = 0.75, 20, 3
HOUR = timedelta(hours=1)
Number = Annotated[float, Field(allow_inf_nan=False)]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=False)


class HourValue(Strict):
    start: AwareDatetime
    coverage: Annotated[Number, Field(ge=0, le=1)]
    do_mgL: Optional[Annotated[Number, Field(ge=0, le=40)]] = None
    ph: Optional[Annotated[Number, Field(gt=0, le=14)]] = None
    temperature_c: Optional[Annotated[Number, Field(gt=0, le=50)]] = None


class ForecastRequest(Strict):
    species: Annotated[str, Field(min_length=1, max_length=64)]
    timezone: Annotated[str, Field(min_length=1, max_length=64)]
    issue_time: AwareDatetime
    history: Annotated[List[HourValue], Field(min_length=1, max_length=HISTORY)]


class RequestError(Exception):
    def __init__(self, status, code, message, reasons=()):
        super().__init__(message)
        self.status, self.code, self.message, self.reasons = status, code, message, list(reasons)


def invalid(reason):
    return RequestError(400, 'invalid_request', 'The request is not valid.', [reason])


def local_zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise invalid('unknown_timezone')


def to_samples(request):
    """Place hourly values on the 24-hour grid that ends at the issue time."""
    zone = local_zone(request.timezone)
    issue = request.issue_time.astimezone(timezone.utc)
    local = issue.astimezone(zone)
    if local.minute or local.second or local.microsecond:
        raise invalid('issue_time_not_on_local_hour')
    x, previous = np.full((1, HISTORY, len(CHANNELS)), np.nan), None
    for item in request.history:
        start = item.start.astimezone(timezone.utc)
        if previous is not None and start <= previous:
            raise invalid('history_not_in_order')
        previous = start
        age = issue - start
        if age % HOUR:
            raise invalid('history_not_on_hour_grid')
        steps = age // HOUR
        if steps < 1:
            raise invalid('history_after_issue_time')
        if steps > HISTORY:
            raise invalid('history_too_old')
        if item.coverage >= MINIMUM_COVERAGE and item.do_mgL is not None:
            x[0, HISTORY - steps] = [np.nan if v is None else v for v in (item.do_mgL, item.ph, item.temperature_c)]
    present, reasons = np.isfinite(x[0]), []
    if present[:, 0].sum() < MINIMUM_HOURS:
        reasons.append('insufficient_do_history')
    if not present[-RECENT_HOURS:, 0].all():
        reasons.append('recent_do_gap')
    for column, name in ((1, 'ph'), (2, 'temperature')):
        if present[:, column].sum() < MINIMUM_HOURS:
            reasons.append(f'insufficient_{name}_history')
    if reasons:
        raise RequestError(422, 'history_unavailable', 'The history does not support a forecast.', reasons)
    hour = (issue - HOUR).astimezone(zone).hour
    return Samples(x, np.full((1, len(HORIZONS)), np.nan), np.array([hour]), np.array(['']), np.array([0]))


def utc_text(value: datetime):
    return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
