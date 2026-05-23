from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models.schemas import ProtectedRule, ProtectedRuleCreate

router = APIRouter()


@router.get("/protected/rules")
def list_rules(session: Session = Depends(get_session)):
    return session.exec(select(ProtectedRule)).all()


@router.post("/protected/rules")
def create_rule(body: ProtectedRuleCreate, session: Session = Depends(get_session)):
    rule = ProtectedRule(type=body.type, value=body.value, label=body.label)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.delete("/protected/rules/{rule_id}")
def delete_rule(rule_id: str, session: Session = Depends(get_session)):
    rule = session.get(ProtectedRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()
    return {"deleted": True}
