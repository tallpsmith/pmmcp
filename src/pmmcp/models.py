from __future__ import annotations

import re
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class Host(BaseModel):
    source: str
    hostnames: list[str]
    labels: dict[str, str] = {}


class Metric(BaseModel):
    name: str
    pmid: str
    type: str
    semantics: str
    units: str
    indom: str | None = None
    series: str = ""
    source: str = ""
    labels: dict[str, str] = {}
    oneline: str = ""
    helptext: str = ""

    @field_validator("name")
    @classmethod
    def name_must_be_dot_separated(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", v):
            raise ValueError(f"Metric name must be dot-separated namespace: {v!r}")
        return v


class Instance(BaseModel):
    instance: int
    name: str
    series: str = ""
    source: str = ""
    labels: dict[str, str] = {}


class MetricValue(BaseModel):
    series: str
    timestamp: int
    value: str | float | int
    instance: str | None = None


class TimeWindow(BaseModel):
    start: str = "-1hour"
    end: str = "now"
    interval: str = "auto"


class WindowStats(BaseModel):
    mean: float
    min: float
    max: float
    p95: float
    stddev: float
    sample_count: int


class DeltaStats(BaseModel):
    mean_change: float
    mean_change_pct: float
    stddev_change: float
    significant: bool


class WindowComparison(BaseModel):
    metric: str
    instance: str | None = None
    window_a: WindowStats
    window_b: WindowStats
    delta: DeltaStats


class SearchResult(BaseModel):
    name: str
    type: str
    oneline: str = ""
    helptext: str = ""
    score: float = 0.0


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int = -1
    limit: int = Field(ge=1, le=1000)
    offset: int = Field(ge=0)
    has_more: bool
