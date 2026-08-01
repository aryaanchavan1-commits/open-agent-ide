from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import events
from ..database import get_db
from ..models import CommandApproval, PlanChange
from ..schemas import ApprovalResponse

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/{approval_id}/respond")
async def respond_approval(approval_id: int, data: ApprovalResponse, db: Session = Depends(get_db)):
    approval = db.get(CommandApproval, approval_id)
    if approval:
        if approval.status != "pending":
            raise HTTPException(400, "Approval already responded")
        approval.status = "approved" if data.decision == "approve" else "rejected"
        from datetime import datetime, timezone

        approval.responded_at = datetime.now(timezone.utc)
        db.commit()
        events.resolve_approval(approval.id)
        await events.emit(
            approval.project_id,
            "permission.response",
            {"approval_id": approval.id, "decision": approval.status},
        )
        return {"ok": True, "status": approval.status}

    plan = db.get(PlanChange, approval_id)
    if plan:
        if plan.status != "proposed":
            raise HTTPException(400, "Plan already responded")
        plan.status = "approved" if data.decision == "approve" else "rejected"
        db.commit()
        events.resolve_approval(plan.id)
        await events.emit(
            plan.project_id,
            "changes.response",
            {"plan_id": plan.id, "decision": plan.status},
        )
        return {"ok": True, "status": plan.status}

    raise HTTPException(404, "Approval not found")
