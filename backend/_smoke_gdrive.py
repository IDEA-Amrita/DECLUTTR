"""Ad-hoc smoke test for Phase 2 Drive cleanup pure logic. Not part of the suite."""
import os, tempfile
os.environ.setdefault("GOOGLE_CLIENT_ID", "x")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "y")

from datetime import datetime, timezone, timedelta
from sqlmodel import Session, SQLModel, create_engine, select
from app.models.gdrive_schemas import DriveToken, DriveScanJob, DriveFileRecord
from app.services.drive_scanner import DriveScanner

engine = create_engine(f"sqlite:///{tempfile.mktemp(suffix='.db')}")
SQLModel.metadata.create_all(engine)

now = datetime.now(timezone.utc)
old = now - timedelta(days=800)

# Build a scanner WITHOUT touching Google
scanner = object.__new__(DriveScanner)
with Session(engine) as db:
    tok = DriveToken(email="t@e.com", access_token="a", refresh_token="r")
    db.add(tok); db.commit(); db.refresh(tok)
    scanner.db = db
    scanner.token = tok
    scanner._folder_cache = {}

    # 1. exact-duplicate clustering by md5
    files = [
        {"id": "a1", "name": "photo.jpg",  "mimeType": "image/jpeg", "size": "5000000", "md5Checksum": "H1", "modifiedTime": now.isoformat()},
        {"id": "a2", "name": "photo (1).jpg", "mimeType": "image/jpeg", "size": "5000000", "md5Checksum": "H1", "modifiedTime": (now - timedelta(days=2)).isoformat()},
        {"id": "a3", "name": "unique.pdf", "mimeType": "application/pdf", "size": "200000000", "md5Checksum": "H2", "modifiedTime": old.isoformat()},
        {"id": "a4", "name": "old.docx", "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "size": "30000", "md5Checksum": "H3", "modifiedTime": old.isoformat()},
    ]
    clusters = scanner._build_exact_clusters(files)
    originals, dupes = scanner._resolve_cluster_roles(clusters)
    assert clusters["a1"] == clusters["a2"], "H1 files should share a group"
    assert "a3" not in clusters, "unique file should not be clustered"
    assert len(dupes) == 1 and len(originals) == 1, f"expected 1 dupe/1 original, got {dupes}/{originals}"
    print("[1] clustering OK  group=", clusters["a1"], "orig=", originals, "dupe=", dupes)

    # 2. classification + confidence + bucket
    cat, conf, bucket = scanner._classify(files[1], 5000000, now - timedelta(days=2), None, is_dupe=True)
    assert bucket == "exact_duplicate" and conf >= 50, (cat, conf, bucket)
    catL, confL, bucketL = scanner._classify(files[2], 200000000, old, None, is_dupe=False)
    assert bucketL in ("large_file", "old_file"), (catL, confL, bucketL)
    print("[2] classify OK  dupe=", (cat, conf, bucket), " large/old=", (catL, confL, bucketL))

    # persist records so organize/keep can run
    for f in files:
        gid = clusters.get(f["id"])
        is_dupe = f["id"] in dupes
        is_orig = f["id"] in originals
        modified = datetime.fromisoformat(f["modifiedTime"])
        c, cf, bk = scanner._classify(f, int(f["size"]), modified, None, is_dupe)
        db.add(DriveFileRecord(
            scan_id="scan1", account_id=tok.id, drive_id=f["id"], name=f["name"],
            mime_type=f["mimeType"], size_bytes=int(f["size"]), md5_checksum=f["md5Checksum"],
            modified_at=modified, duplicate_group_id=gid, is_cluster_original=is_orig,
            category=c, confidence=cf, deletion_bucket=bk,
            in_deletion_list=(bk is not None and cf >= 50 and not is_orig),
        ))
    db.add(DriveScanJob(id="scan1", account_id=tok.id, status="done"))
    db.commit()

    # 3. organize plan (type + time paradigms)
    plan = scanner.plan_organization("scan1", ["type", "time"])
    assert plan["files_planned"] > 0 and len(plan["folders"]) > 0, plan
    print("[3] organize OK  folders=", [f["path"] for f in plan["folders"]])

    # 4. keep_file protects and removes from deletion list
    dupe_rec = db.exec(select(DriveFileRecord).where(DriveFileRecord.drive_id == "a2")).one()
    res = scanner.keep_file(dupe_rec.id, "family vacation photo", "important", None)
    db.refresh(dupe_rec)
    assert dupe_rec.is_protected and not dupe_rec.in_deletion_list, (dupe_rec.is_protected, dupe_rec.in_deletion_list)
    print("[4] keep_file OK  ->", res)

    # 5. deletion-list buckets present
    in_del = db.exec(select(DriveFileRecord).where(DriveFileRecord.in_deletion_list == True)).all()  # noqa: E712
    print("[5] deletion-list count=", len(in_del), "buckets=", {r.deletion_bucket for r in in_del})

print("\nSMOKE_OK")
