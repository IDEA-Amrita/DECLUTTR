from sqlmodel import Session
from app.models.schemas import Suggestion


def _create_suggestion(session: Session, path: str) -> Suggestion:
    s = Suggestion(
        scan_id="test-scan",
        type="large_file",
        path=path,
        size_bytes=1024,
        last_accessed=0,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def test_consent_false_does_not_delete(client, session, tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    s = _create_suggestion(session, str(f))

    resp = client.post("/api/consent/confirm", json={
        "suggestion_id": s.id,
        "module": "storage",
        "action": "delete",
        "confirmed": False,
    })
    assert resp.status_code == 200
    assert resp.json()["executed"] is False
    assert f.exists()


def test_consent_true_moves_to_trash(client, session, tmp_path):
    f = tmp_path / "trash_me.txt"
    f.write_text("delete me")
    s = _create_suggestion(session, str(f))

    resp = client.post("/api/consent/confirm", json={
        "suggestion_id": s.id,
        "module": "storage",
        "action": "delete",
        "confirmed": True,
    })
    assert resp.status_code == 200
    assert resp.json()["executed"] is True
    assert not f.exists()

    session.refresh(s)
    assert s.consent_given == 1


def test_consent_true_logs_to_consent_log(client, session, tmp_path):
    from sqlmodel import select
    from app.models.schemas import ConsentLog
    f = tmp_path / "log_me.txt"
    f.write_text("x")
    s = _create_suggestion(session, str(f))

    client.post("/api/consent/confirm", json={
        "suggestion_id": s.id,
        "module": "storage",
        "action": "delete",
        "confirmed": True,
    })

    logs = session.exec(select(ConsentLog).where(ConsentLog.suggestion_id == s.id)).all()
    assert len(logs) == 1
    assert logs[0].success == 1
