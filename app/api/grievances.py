"""Kotlin Android Frontend REST API for IGM Grievances and Ratings.

Provides:
  - Grievance ticket lifecycle (create, list, get, escalate L1->L2->L3, resolve)
  - Settlement pause/unpause tracking
  - SLA timer automated checks
  - Buyer ratings and seller reputation scores
"""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import SessionDep
from app.ondc.igm import IgmService
from app.ondc.rating import RatingService

router = APIRouter(prefix="/grievances", tags=["grievances"])
ratings_router = APIRouter(prefix="/ratings", tags=["ratings"])


class CreateGrievanceRequest(BaseModel):
    transaction_id: str
    category: str = "QUALITY"
    sub_category: str = "MOISTURE_EXCESS"
    description: str
    complainant_info: dict[str, Any] = Field(default_factory=dict)
    respondent_info: dict[str, Any] = Field(default_factory=dict)


class EscalateGrievanceRequest(BaseModel):
    reason: str | None = None


class ResolveGrievanceRequest(BaseModel):
    resolution_notes: str
    refund_amount_inr: int = 0


class SubmitRatingRequest(BaseModel):
    transaction_id: str
    target_id: str
    score: int = Field(ge=1, le=5)
    rating_category: str = "seller"
    feedback: str | None = None


# ---------------------------------------------------------------------------
# Grievance Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_grievance(payload: CreateGrievanceRequest, session: SessionDep) -> dict[str, Any]:
    service = IgmService(session)
    ticket = await service.create_ticket(
        transaction_id=payload.transaction_id,
        category=payload.category,
        sub_category=payload.sub_category,
        description=payload.description,
        complainant_info=payload.complainant_info,
        respondent_info=payload.respondent_info,
    )
    return {
        "status": "success",
        "ticket": {
            "id": ticket.ticket_id,
            "transaction_id": ticket.transaction_id,
            "category": ticket.category,
            "sub_category": ticket.sub_category,
            "description": ticket.description,
            "status": ticket.status,
            "escalation_level": ticket.escalation_level,
            "expected_response_time": ticket.expected_response_time,
            "settlement_paused": ticket.settlement_paused,
            "sla_expires_at": ticket.sla_expires_at.isoformat() if ticket.sla_expires_at else None,
            "created_at": ticket.created_at.isoformat(),
        },
    }


@router.get("")
async def list_grievances(
    session: SessionDep,
    transaction_id: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    service = IgmService(session)
    tickets = await service.list_tickets(transaction_id)
    return {
        "count": len(tickets),
        "tickets": [
            {
                "id": t.ticket_id,
                "transaction_id": t.transaction_id,
                "category": t.category,
                "sub_category": t.sub_category,
                "description": t.description,
                "status": t.status,
                "escalation_level": t.escalation_level,
                "settlement_paused": t.settlement_paused,
                "expected_response_time": t.expected_response_time,
                "sla_expires_at": t.sla_expires_at.isoformat() if t.sla_expires_at else None,
                "created_at": t.created_at.isoformat(),
            }
            for t in tickets
        ],
    }


@router.get("/{ticket_id}")
async def get_grievance(ticket_id: str, session: SessionDep) -> dict[str, Any]:
    service = IgmService(session)
    ticket = await service.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grievance ticket not found")
    return {
        "id": ticket.ticket_id,
        "transaction_id": ticket.transaction_id,
        "category": ticket.category,
        "sub_category": ticket.sub_category,
        "description": ticket.description,
        "status": ticket.status,
        "escalation_level": ticket.escalation_level,
        "expected_response_time": ticket.expected_response_time,
        "settlement_paused": ticket.settlement_paused,
        "resolution_notes": ticket.resolution_notes,
        "refund_amount_inr": ticket.refund_amount_inr,
        "sla_expires_at": ticket.sla_expires_at.isoformat() if ticket.sla_expires_at else None,
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
    }


@router.post("/{ticket_id}/escalate")
async def escalate_grievance(
    ticket_id: str,
    payload: EscalateGrievanceRequest,
    session: SessionDep,
) -> dict[str, Any]:
    service = IgmService(session)
    ticket = await service.escalate_ticket(ticket_id, reason=payload.reason)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket not found or cannot be escalated (already resolved or at max escalation)",
        )
    return {
        "status": "escalated",
        "ticket_id": ticket.ticket_id,
        "escalation_level": ticket.escalation_level,
        "status_code": ticket.status,
        "expected_response_time": ticket.expected_response_time,
        "sla_expires_at": ticket.sla_expires_at.isoformat() if ticket.sla_expires_at else None,
    }


@router.post("/{ticket_id}/resolve")
async def resolve_grievance(
    ticket_id: str,
    payload: ResolveGrievanceRequest,
    session: SessionDep,
) -> dict[str, Any]:
    service = IgmService(session)
    ticket = await service.resolve_ticket(
        ticket_id,
        resolution_notes=payload.resolution_notes,
        refund_amount_inr=payload.refund_amount_inr,
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grievance ticket not found")
    return {
        "status": "resolved",
        "ticket_id": ticket.ticket_id,
        "settlement_paused": ticket.settlement_paused,
        "refund_amount_inr": ticket.refund_amount_inr,
        "resolution_notes": ticket.resolution_notes,
    }


@router.post("/sla/check")
async def run_sla_check(session: SessionDep) -> dict[str, Any]:
    service = IgmService(session)
    escalated = await service.check_sla_timers()
    return {
        "status": "completed",
        "escalated_count": len(escalated),
        "escalated_ticket_ids": [t.ticket_id for t in escalated],
    }


# ---------------------------------------------------------------------------
# Rating Endpoints
# ---------------------------------------------------------------------------


@ratings_router.post("", status_code=status.HTTP_201_CREATED)
async def submit_rating(payload: SubmitRatingRequest, session: SessionDep) -> dict[str, Any]:
    service = RatingService(session)
    record = await service.submit_rating(
        transaction_id=payload.transaction_id,
        target_id=payload.target_id,
        score=payload.score,
        rating_category=payload.rating_category,
        feedback=payload.feedback,
    )
    score = await service.get_seller_score(payload.target_id)
    return {
        "status": "success",
        "rating_id": str(record.id),
        "target_id": payload.target_id,
        "score": record.score,
        "updated_seller_score": score,
    }


@ratings_router.get("/{target_id}")
async def get_seller_ratings(target_id: str, session: SessionDep) -> dict[str, Any]:
    service = RatingService(session)
    score = await service.get_seller_score(target_id)
    ratings = await service.list_ratings(target_id)
    return {
        "target_id": target_id,
        "seller_score": score,
        "rating_count": len(ratings),
        "ratings": [
            {
                "id": str(r.id),
                "transaction_id": r.transaction_id,
                "score": r.score,
                "category": r.rating_category,
                "feedback": r.feedback,
                "created_at": r.created_at.isoformat(),
            }
            for r in ratings
        ],
    }
