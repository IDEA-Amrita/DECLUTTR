def test_add_and_list_rules(client):
    resp = client.post("/api/protected/rules", json={"type": "folder", "value": "/home/user/important", "label": "Important"})
    assert resp.status_code == 200
    rule_id = resp.json()["id"]

    resp = client.get("/api/protected/rules")
    assert resp.status_code == 200
    rules = resp.json()
    assert any(r["id"] == rule_id for r in rules)


def test_delete_rule(client):
    resp = client.post("/api/protected/rules", json={"type": "path", "value": "/keep/this.txt", "label": "Keep"})
    rule_id = resp.json()["id"]
    del_resp = client.delete(f"/api/protected/rules/{rule_id}")
    assert del_resp.status_code == 200
    rules = client.get("/api/protected/rules").json()
    assert not any(r["id"] == rule_id for r in rules)


def test_is_protected_folder_rule():
    from app.services.protected_service import is_protected
    rules = [{"type": "folder", "value": "/home/user/important"}]
    assert is_protected("/home/user/important/file.txt", rules) is True
    assert is_protected("/home/user/other/file.txt", rules) is False


def test_is_protected_path_rule():
    from app.services.protected_service import is_protected
    rules = [{"type": "path", "value": "/keep/this.txt"}]
    assert is_protected("/keep/this.txt", rules) is True
    assert is_protected("/keep/other.txt", rules) is False
