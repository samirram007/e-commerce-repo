"""The file library: folders, access rules, versions, shares, trash and the
storefront customer-upload inbox.

Folders are a tree over `StoredFile`. Restricted folders (a permission and/or
role names) hide their contents from everyone else, deleting is soft until a
purge, replacing contents keeps the previous bytes as a version, and a share
link is the only way a file leaves the ERP without a bearer token.
"""
import uuid

API = "/api/v1"
SHOP = f"{API}/storefront/shop"

PAYLOAD = {"file": ("notes.txt", b"hello library", "text/plain")}


def _token(client, admin_headers, company_id, *, roles=("other_user",), is_company_admin=False) -> dict:
    """A second user in `company_id` with the given roles, plus their headers."""
    email = f"lib-{uuid.uuid4().hex[:10]}@test.io"
    resp = client.post(
        f"{API}/users",
        headers=admin_headers,
        json={
            "email": email,
            "password": "SuperSecret!123",
            "full_name": "Library User",
            "company_id": company_id,
            "role_names": list(roles),
            "is_company_admin": is_company_admin,
        },
    )
    assert resp.status_code == 201, resp.text
    login = client.post(f"{API}/auth/login", json={"email": email, "password": "SuperSecret!123"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}", "X-Company-Id": company_id}


def _folders(client, headers) -> dict:
    resp = client.get(f"{API}/files/folders", headers=headers)
    assert resp.status_code == 200, resp.text
    return {row["name"]: row for row in resp.json()["items"]}


def _new_folder(client, headers, name, **extra) -> dict:
    resp = client.post(f"{API}/files/folders", headers=headers, json={"name": name, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _upload(client, headers, *, name="notes.txt", body=b"hello library", content_type="text/plain", **form):
    resp = client.post(
        f"{API}/files/upload",
        headers=headers,
        files={"file": (name, body, content_type)},
        data=form,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_upload_list_download_rename_and_move(client, auth_headers):
    folder = _new_folder(client, auth_headers, "Contracts")
    nested = _new_folder(client, auth_headers, "2026", parent_id=folder["id"])
    assert nested["path"] == f"/Contracts/2026"

    record = _upload(client, auth_headers, folder_id=nested["id"])
    assert record["folder_id"] == nested["id"]
    assert record["folder_path"] == "/Contracts/2026"
    assert record["version_count"] == 0

    listing = client.get(f"{API}/files", headers=auth_headers, params={"folder_id": nested["id"]})
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert [row["id"] for row in body["items"]] == [record["id"]]
    assert [crumb["name"] for crumb in body["breadcrumbs"]] == ["Contracts", "2026"]

    # the parent folder lists only its own files, and subfolders on request
    parent = client.get(
        f"{API}/files",
        headers=auth_headers,
        params={"folder_id": folder["id"], "include_subfolders": True},
    ).json()
    assert [row["id"] for row in parent["items"]] == [record["id"]]
    assert [row["name"] for row in parent["subfolders"]] == ["2026"]

    download = client.get(f"{API}/files/{record['id']}/download", headers=auth_headers)
    assert download.status_code == 200, download.text
    assert download.content == b"hello library"
    assert download.headers["content-type"].startswith("text/plain")

    renamed = client.patch(
        f"{API}/files/{record['id']}", headers=auth_headers, json={"name": "agreement.txt"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "agreement.txt"

    moved = client.patch(
        f"{API}/files/{record['id']}",
        headers=auth_headers,
        json={"folder_id": folder["id"], "move": True},
    )
    assert moved.json()["folder_path"] == "/Contracts"


def test_folder_rules_reject_duplicates_and_bad_moves(client, auth_headers):
    parent = _new_folder(client, auth_headers, "Projects")
    child = _new_folder(client, auth_headers, "Alpha", parent_id=parent["id"])
    grandchild = _new_folder(client, auth_headers, "Deep", parent_id=child["id"])

    duplicate = client.post(
        f"{API}/files/folders", headers=auth_headers, json={"name": "alpha", "parent_id": parent["id"]}
    )
    assert duplicate.status_code == 409, duplicate.text

    into_itself = client.patch(
        f"{API}/files/folders/{parent['id']}",
        headers=auth_headers,
        json={"parent_id": grandchild["id"], "move": True},
    )
    assert into_itself.status_code == 400, into_itself.text

    renamed = client.patch(
        f"{API}/files/folders/{parent['id']}", headers=auth_headers, json={"name": "Programs"}
    )
    assert renamed.json()["path"] == "/Programs"
    # descendants follow the rename
    assert client.get(f"{API}/files/folders/{grandchild['id']}", headers=auth_headers).json()["path"] == (
        "/Programs/Alpha/Deep"
    )


def test_restricted_folder_hides_contents_from_other_roles(client, admin_headers, company_id, auth_headers):
    hr = _new_folder(
        client, auth_headers, "Board minutes", required_permission="company.members.manage"
    )
    record = _upload(client, auth_headers, folder_id=hr["id"], name="minutes.txt")

    other = _token(client, admin_headers, company_id, roles=("other_user",))
    tree = _folders(client, other)
    assert "Board minutes" not in tree

    listing = client.get(f"{API}/files", headers=other)
    assert listing.status_code == 200, listing.text
    assert [row["id"] for row in listing.json()["items"]] == []

    # hidden from the tree and the listing, and refused when addressed directly
    assert client.get(f"{API}/files/{record['id']}", headers=other).status_code == 403
    assert client.get(f"{API}/files/{record['id']}/download", headers=other).status_code == 403

    # the admin still sees it
    assert client.get(f"{API}/files/{record['id']}", headers=auth_headers).status_code == 200


def test_role_scoped_folder_grants_access_to_that_role(client, admin_headers, company_id, auth_headers):
    payroll = _new_folder(client, auth_headers, "Payroll", role_names=["accountant"])
    record = _upload(client, auth_headers, folder_id=payroll["id"], name="payslip.txt")

    accountant = _token(client, admin_headers, company_id, roles=("accountant",))
    assert "Payroll" in _folders(client, accountant)
    assert client.get(f"{API}/files/{record['id']}/download", headers=accountant).status_code == 200

    other = _token(client, admin_headers, company_id, roles=("other_user",))
    assert client.get(f"{API}/files/{record['id']}", headers=other).status_code == 403


def test_replace_contents_keeps_a_downloadable_version(client, auth_headers):
    folder = _new_folder(client, auth_headers, "Designs")
    record = _upload(client, auth_headers, folder_id=folder["id"], name="logo.txt", body=b"v1")

    resp = client.post(
        f"{API}/files/{record['id']}/contents",
        headers=auth_headers,
        files={"file": ("logo.txt", b"v2", "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["size_bytes"] == 2

    versions = client.get(f"{API}/files/{record['id']}/versions", headers=auth_headers).json()["items"]
    assert [row["version"] for row in versions] == [1]
    assert versions[0]["size_bytes"] == 2  # the superseded bytes were b"v1"

    assert client.get(f"{API}/files/{record['id']}/download", headers=auth_headers).content == b"v2"
    old = client.get(
        f"{API}/files/{record['id']}/versions/{versions[0]['id']}/download", headers=auth_headers
    )
    assert old.status_code == 200, old.text
    assert old.content == b"v1"

    detail = client.get(f"{API}/files/{record['id']}", headers=auth_headers).json()
    assert detail["version_count"] == 1
    assert [row["version"] for row in detail["versions"]] == [1]


def test_trash_restore_and_purge(client, admin_headers, company_id, auth_headers):
    folder = _new_folder(client, auth_headers, "Archive")
    record = _upload(client, auth_headers, folder_id=folder["id"], name="old.txt")
    other = _token(client, admin_headers, company_id, roles=("other_user",))

    trashed = client.delete(f"{API}/files/{record['id']}", headers=auth_headers)
    assert trashed.status_code == 200, trashed.text
    assert client.get(f"{API}/files/{record['id']}", headers=auth_headers).status_code == 404
    assert [row["id"] for row in client.get(f"{API}/files/trash", headers=auth_headers).json()["items"]] == [
        record["id"]
    ]

    # only an admin may purge, and only out of the trash
    assert client.delete(f"{API}/files/{record['id']}/purge", headers=other).status_code == 403
    restored = client.post(f"{API}/files/{record['id']}/restore", headers=auth_headers)
    assert restored.status_code == 200, restored.text
    assert client.get(f"{API}/files/{record['id']}", headers=auth_headers).status_code == 200

    client.delete(f"{API}/files/{record['id']}", headers=auth_headers)
    purged = client.delete(f"{API}/files/{record['id']}/purge", headers=auth_headers)
    assert purged.status_code == 200, purged.text
    assert client.get(
        f"{API}/files/{record['id']}", headers=auth_headers, params={"include_trashed": True}
    ).status_code == 404


def test_trash_and_restore_a_whole_folder(client, auth_headers):
    folder = _new_folder(client, auth_headers, "Bulk")
    sub = _new_folder(client, auth_headers, "Inner", parent_id=folder["id"])
    first = _upload(client, auth_headers, folder_id=folder["id"], name="a.txt")
    second = _upload(client, auth_headers, folder_id=sub["id"], name="b.txt")

    result = client.delete(f"{API}/files/folders/{folder['id']}", headers=auth_headers)
    assert result.status_code == 200, result.text
    assert result.json()["files_trashed"] == 2
    assert client.get(f"{API}/files/{first['id']}", headers=auth_headers).status_code == 404
    assert client.get(f"{API}/files/{second['id']}", headers=auth_headers).status_code == 404

    assert client.post(f"{API}/files/folders/{folder['id']}/restore", headers=auth_headers).status_code == 200
    assert client.get(f"{API}/files/{first['id']}", headers=auth_headers).status_code == 200
    assert client.get(f"{API}/files/{second['id']}", headers=auth_headers).status_code == 200


def test_bulk_actions_move_and_trash_a_selection(client, auth_headers):
    source = _new_folder(client, auth_headers, "Inbox")
    target = _new_folder(client, auth_headers, "Filed")
    ids = [
        _upload(client, auth_headers, folder_id=source["id"], name=f"doc-{index}.txt")["id"]
        for index in range(3)
    ]

    moved = client.post(
        f"{API}/files/bulk",
        headers=auth_headers,
        json={"ids": ids, "action": "move", "folder_id": target["id"]},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["changed"] == 3
    filed = client.get(f"{API}/files", headers=auth_headers, params={"folder_id": target["id"]}).json()
    assert len(filed["items"]) == 3

    trashed = client.post(
        f"{API}/files/bulk", headers=auth_headers, json={"ids": ids, "action": "trash"}
    )
    assert trashed.json()["changed"] == 3
    assert client.get(f"{API}/files", headers=auth_headers, params={"folder_id": target["id"]}).json()[
        "items"
    ] == []

    bad = client.post(
        f"{API}/files/bulk", headers=auth_headers, json={"ids": ids, "action": "explode"}
    )
    assert bad.status_code == 400, bad.text


def test_share_link_serves_a_file_without_a_token(client, auth_headers):
    record = _upload(client, auth_headers, name="price-list.txt")

    created = client.post(f"{API}/files/shares", headers=auth_headers, json={"file_id": record["id"]})
    assert created.status_code == 201, created.text
    share = created.json()
    assert share["url"] == f"{API}/files/shared/{share['token']}"

    opened = client.get(f"{API}/files/shared/{share['token']}")  # no headers at all
    assert opened.status_code == 200, opened.text
    assert [row["name"] for row in opened.json()["files"]] == ["price-list.txt"]

    download = client.get(f"{API}/files/shared/{share['token']}/download/{record['id']}")
    assert download.status_code == 200, download.text
    assert download.content == b"hello library"

    shares = client.get(f"{API}/files/shares", headers=auth_headers).json()["items"]
    assert [row["downloads"] for row in shares if row["id"] == share["id"]] == [1]

    assert client.delete(f"{API}/files/shares/{share['id']}", headers=auth_headers).status_code == 200
    assert client.get(f"{API}/files/shared/{share['token']}").status_code == 404


def test_share_link_expiry_and_folder_shares(client, auth_headers):
    folder = _new_folder(client, auth_headers, "Media kit")
    _upload(client, auth_headers, folder_id=folder["id"], name="one.txt")
    _upload(client, auth_headers, folder_id=folder["id"], name="two.txt")

    expired = client.post(
        f"{API}/files/shares",
        headers=auth_headers,
        json={"folder_id": folder["id"], "expires_in_days": 0},
    ).json()
    assert client.get(f"{API}/files/shared/{expired['token']}").status_code == 404

    live = client.post(f"{API}/files/shares", headers=auth_headers, json={"folder_id": folder["id"]}).json()
    opened = client.get(f"{API}/files/shared/{live['token']}").json()
    assert opened["folder"]["name"] == "Media kit"
    assert sorted(row["name"] for row in opened["files"]) == ["one.txt", "two.txt"]

    both = client.post(
        f"{API}/files/shares",
        headers=auth_headers,
        json={"folder_id": folder["id"], "file_id": "whatever"},
    )
    assert both.status_code == 400, both.text


def test_other_screens_uploads_are_filed_into_system_folders(client, auth_headers):
    """An image uploaded for a product lands in the library, already organised."""
    product = client.post(
        f"{API}/catalog/products",
        headers=auth_headers,
        json={
            "sku": f"LIB-{uuid.uuid4().hex[:6]}",
            "name": "Library Lamp",
            "hsn_sac": "9405",
            "base_price": "10",
            "base_cost": "4",
            "stock_type": "stock",
        },
    ).json()
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    resp = client.post(
        f"{API}/catalog/products/{product['id']}/image",
        headers=auth_headers,
        files={"file": ("lamp.png", png, "image/png")},
    )
    assert resp.status_code == 200, resp.text

    folders = _folders(client, auth_headers)
    assert "Product images" in folders
    listing = client.get(
        f"{API}/files", headers=auth_headers, params={"folder_id": folders["Product images"]["id"]}
    ).json()
    assert [row["name"] for row in listing["items"]] == ["lamp.png"]


def test_file_usage_reports_where_a_file_is_referenced(client, auth_headers):
    product = client.post(
        f"{API}/catalog/products",
        headers=auth_headers,
        json={
            "sku": f"USE-{uuid.uuid4().hex[:6]}",
            "name": "Usage Widget",
            "hsn_sac": "8473",
            "base_price": "5",
            "base_cost": "2",
            "stock_type": "stock",
        },
    ).json()
    png = b"\x89PNG\r\n\x1a\n" + b"1" * 16
    assert (
        client.post(
            f"{API}/catalog/products/{product['id']}/image",
            headers=auth_headers,
            files={"file": ("widget.png", png, "image/png")},
        ).status_code
        == 200
    )
    listing = client.get(f"{API}/files", headers=auth_headers, params={"search": "widget"}).json()
    file_id = listing["items"][0]["id"]

    usage = client.get(f"{API}/files/{file_id}/usage", headers=auth_headers)
    assert usage.status_code == 200, usage.text
    assert [row["kind"] for row in usage.json()["used"]] == ["product"]


def test_shopper_uploads_go_to_the_moderated_inbox(client, auth_headers):
    folders = _folders(client, auth_headers)
    inbox = folders["Customer uploads"]
    assert inbox["accepts_shopper_uploads"] is True

    shopper = {"X-Company-Id": auth_headers["X-Company-Id"], "X-Anon-Id": "guest-1"}
    resp = client.post(
        f"{SHOP}/uploads",
        headers=shopper,
        files={"file": ("proof.png", b"\x89PNG\r\n\x1a\n" + b"7" * 8, "image/png")},
    )
    assert resp.status_code == 201, resp.text
    record = resp.json()

    mine = client.get(f"{SHOP}/uploads", headers=shopper)
    assert mine.status_code == 200, mine.text
    assert mine.json()["enabled"] is True
    assert [row["id"] for row in mine.json()["items"]] == [record["id"]]

    # it shows up in the library inbox, private to the company
    listing = client.get(f"{API}/files", headers=auth_headers, params={"folder_id": inbox["id"]}).json()
    assert [row["id"] for row in listing["items"]] == [record["id"]]
    assert listing["items"][0]["uploaded_via"] == "storefront"

    # the store can read it back, another shopper cannot
    assert client.get(f"{SHOP}/uploads/{record['id']}", headers=shopper).status_code == 200
    other = {"X-Company-Id": auth_headers["X-Company-Id"], "X-Anon-Id": "guest-2"}
    assert client.get(f"{SHOP}/uploads/{record['id']}", headers=other).status_code == 404

    # turning the inbox off closes the feature
    off = client.patch(
        f"{API}/files/folders/{inbox['id']}", headers=auth_headers, json={"accepts_shopper_uploads": False}
    )
    assert off.status_code == 200, off.text
    blocked = client.post(
        f"{SHOP}/uploads",
        headers=shopper,
        files={"file": ("proof.png", b"\x89PNG\r\n\x1a\n" + b"8" * 8, "image/png")},
    )
    assert blocked.status_code == 400, blocked.text
    assert client.get(f"{SHOP}/uploads", headers=shopper).json()["enabled"] is False


def test_search_and_trash_listing(client, auth_headers):
    _upload(client, auth_headers, name="invoice-scan.txt")
    keep = _upload(client, auth_headers, name="keep-me.txt")

    found = client.get(f"{API}/files", headers=auth_headers, params={"search": "invoice"}).json()
    assert [row["name"] for row in found["items"]] == ["invoice-scan.txt"]

    client.delete(f"{API}/files/{keep['id']}", headers=auth_headers)
    trash = client.get(f"{API}/files/trash", headers=auth_headers, params={"search": "keep"}).json()
    assert [row["id"] for row in trash["items"]] == [keep["id"]]
