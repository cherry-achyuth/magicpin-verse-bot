# Data models for the Vera bot.
# This defines Pydantic schemas for the 4 context types (Category, Merchant,
# Customer, Trigger) and all request/response objects for the HTTP API.

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# Context Models


class OfferTemplate(BaseModel):
    id: Optional[str] = None
    title: str
    value: Optional[str] = None
    audience: Optional[str] = None
    type: Optional[str] = None


class VoiceProfile(BaseModel):
    tone: Optional[str] = None
    vocab_allowed: Optional[List[str]] = None
    vocab_taboo: Optional[List[str]] = None
    taboos: Optional[List[str]] = None


class PeerStats(BaseModel):
    avg_rating: Optional[float] = None
    avg_reviews: Optional[int] = None
    avg_ctr: Optional[float] = None
    scope: Optional[str] = None


class DigestItem(BaseModel):
    id: str
    kind: Optional[str] = None
    title: str
    source: Optional[str] = None
    trial_n: Optional[int] = None
    patient_segment: Optional[str] = None
    summary: Optional[str] = None


class ContentItem(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    channel: Optional[str] = None
    body: Optional[str] = None


class SeasonalBeat(BaseModel):
    month: Optional[str] = None
    month_range: Optional[str] = None
    note: Optional[str] = None


class TrendSignal(BaseModel):
    query: Optional[str] = None
    delta_yoy: Optional[float] = None
    segment_age: Optional[str] = None


class CategoryContext(BaseModel):
    slug: str
    offer_catalog: List[OfferTemplate] = Field(default_factory=list)
    voice: VoiceProfile = Field(default_factory=VoiceProfile)
    peer_stats: PeerStats = Field(default_factory=PeerStats)
    digest: List[DigestItem] = Field(default_factory=list)
    patient_content_library: List[ContentItem] = Field(default_factory=list)
    seasonal_beats: List[SeasonalBeat] = Field(default_factory=list)
    trend_signals: List[TrendSignal] = Field(default_factory=list)


class Identity(BaseModel):
    name: str
    city: Optional[str] = None
    locality: Optional[str] = None
    place_id: Optional[str] = None
    verified: Optional[bool] = None
    languages: List[str] = Field(default_factory=list)
    owner_first_name: Optional[str] = None
    established_year: Optional[int] = None


class Subscription(BaseModel):
    status: str
    plan: Optional[str] = None
    days_remaining: Optional[int] = None
    days_since_expiry: Optional[int] = None


class Delta7d(BaseModel):
    views_pct: Optional[float] = None
    calls_pct: Optional[float] = None


class PerformanceSnapshot(BaseModel):
    window_days: Optional[int] = None
    views: Optional[int] = None
    calls: Optional[int] = None
    directions: Optional[int] = None
    ctr: Optional[float] = None
    leads: Optional[int] = None
    delta_7d: Optional[Delta7d] = None


class MerchantOffer(BaseModel):
    id: Optional[str] = None
    title: str
    status: Optional[str] = None
    value: Optional[str] = None


class CustomerAggregate(BaseModel):
    total_unique_ytd: Optional[int] = None
    lapsed_180d_plus: Optional[int] = None
    retention_6mo_pct: Optional[float] = None
    high_risk_adult_count: Optional[int] = None


class MerchantContext(BaseModel):
    merchant_id: str
    category_slug: str
    identity: Identity
    subscription: Subscription
    performance: PerformanceSnapshot = Field(default_factory=PerformanceSnapshot)
    offers: List[MerchantOffer] = Field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    customer_aggregate: CustomerAggregate = Field(default_factory=CustomerAggregate)
    signals: List[Any] = Field(default_factory=list)
    review_themes: List[Any] = Field(default_factory=list)


class CustomerIdentity(BaseModel):
    name: str
    phone_redacted: Optional[str] = None
    language_pref: Optional[str] = None
    age_band: Optional[str] = None


class Relationship(BaseModel):
    first_visit: Optional[str] = None
    last_visit: Optional[str] = None
    visits_total: Optional[int] = None
    services_received: List[str] = Field(default_factory=list)
    lifetime_value: Optional[float] = None


class Preferences(BaseModel):
    preferred_slots: Optional[str] = None
    channel: Optional[str] = None
    reminder_opt_in: Optional[bool] = None


class Consent(BaseModel):
    opted_in_at: Optional[str] = None
    scope: List[str] = Field(default_factory=list)


class CustomerContext(BaseModel):
    customer_id: str
    merchant_id: str
    identity: CustomerIdentity
    relationship: Relationship = Field(default_factory=Relationship)
    state: str
    preferences: Preferences = Field(default_factory=Preferences)
    consent: Consent = Field(default_factory=Consent)


class TriggerContext(BaseModel):
    id: str
    scope: str
    kind: str
    source: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    urgency: int = 1
    suppression_key: str = ""
    expires_at: Optional[str] = None


# HTTP Wire API Models


class ContextPushRequest(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: Optional[str] = None


class ContextPushResponse(BaseModel):
    accepted: bool
    ack_id: Optional[str] = None
    stored_at: Optional[str] = None
    reason: Optional[str] = None
    current_version: Optional[int] = None
    details: Optional[str] = None


class TickRequest(BaseModel):
    now: str
    available_triggers: List[str] = Field(default_factory=list)


class Action(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: str
    trigger_id: str
    template_name: Optional[str] = None
    template_params: Optional[List[str]] = None
    body: str
    cta: str
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: List[Action] = Field(default_factory=list)


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: Optional[str] = None
    turn_number: int


class ReplyResponse(BaseModel):
    action: str
    body: Optional[str] = None
    cta: Optional[str] = None
    wait_seconds: Optional[int] = None
    rationale: str


class HealthzResponse(BaseModel):
    status: str
    uptime_seconds: int
    contexts_loaded: Dict[str, int]


class MetadataResponse(BaseModel):
    team_name: str
    team_members: List[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str
