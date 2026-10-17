"""Batch & serial tracking for stock items.

Covers: products declare `track_batches` / `track_serials`; goods receipts
enforce the declaration, register serials as `in_stock`, reject duplicates;
outbound movements release serials and mark them `issued`; the serial view
exposes the records.
"""


def _create_product(client, auth_headers, *, sku: str, track_batches: bool, track_serials: bool) -> str:
    resp = client.post(
        "/api/v1/catalog/products",
        headers=auth_headers,
        json={
            "sku": sku,
            "name": f"Product {sku}",
            "base_price": "20",
            "base_cost": "10",
            "stock_type": "stock",
            "track_batches": track_batches,
            "track_serials": track_serials,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_bin(client, auth_headers, code: str) -> str:
    wh = client.post(
        "/api/v1/storage/locations",
        headers=auth_headers,
        json={"code": f"WH-{code}", "name": "Warehouse", "location_type": "warehouse"},
    )
    assert wh.status_code == 201, wh.text
    resp = client.post(
        "/api/v1/storage/locations",
        headers=auth_headers,
        json={"code": code, "name": "Bin", "location_type": "bin", "parent_id": wh.json()["id"]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _approved_po(client, auth_headers, vendor_id: str, product_id: str, qty: str = "3"):
    po = client.post(
        "/api/v1/purchasing/orders",
        headers=auth_headers,
        json={
            "vendor_id": vendor_id,
            "order_date": "2026-03-01",
            "currency": "USD",
            "lines": [{"product_id": product_id, "ordered_qty": qty, "unit_cost": "10.00"}],
        },
    ).json()
    client.post(f"/api/v1/purchasing/orders/{po['id']}/submit", headers=auth_headers)
    client.post(f"/api/v1/purchasing/orders/{po['id']}/approve", headers=auth_headers)
    lines = client.get(f"/api/v1/purchasing/orders/{po['id']}/lines", headers=auth_headers).json()
    return po, lines[0]["id"]


def _receive(client, auth_headers, po_id: str, line_id: str, bin_id: str, **line):
    return client.post(
        f"/api/v1/purchasing/orders/{po_id}/receive",
        headers=auth_headers,
        json={"lines": [{"order_line_id": line_id, "location_id": bin_id, **line}]},
    )


def test_batch_and_serial_receipt_is_enforced_and_registers_serials(client, auth_headers, master_data):
    vendor_id = master_data["vendor_id"]
    product_id = _create_product(client, auth_headers, sku="SN-1", track_batches=True, track_serials=True)
    bin_id = _create_bin(client, auth_headers, "BIN-SN1")
    po, line_id = _approved_po(client, auth_headers, vendor_id, product_id, qty="3")

    # missing batch -> rejected
    missing_batch = _receive(client, auth_headers, po["id"], line_id, bin_id, qty_received="3", serials=["S1", "S2", "S3"])
    assert missing_batch.status_code == 400, missing_batch.text
    assert missing_batch.json()["error"]["code"] == "BATCH_REQUIRED"

    # missing serials -> rejected
    missing_serials = _receive(client, auth_headers, po["id"], line_id, bin_id, qty_received="3", batch_ref="B1")
    assert missing_serials.status_code == 400, missing_serials.text
    assert missing_serials.json()["error"]["code"] == "SERIALS_REQUIRED"

    # serial count mismatch -> rejected
    mismatch = _receive(
        client, auth_headers, po["id"], line_id, bin_id, qty_received="3", batch_ref="B1", serials=["S1", "S2"]
    )
    assert mismatch.status_code == 400, mismatch.text
    assert mismatch.json()["error"]["code"] == "SERIALS_QTY_MISMATCH"

    # correct receipt registers the serials
    ok = _receive(
        client, auth_headers, po["id"], line_id, bin_id, qty_received="3", batch_ref="B1", serials=["S1", "S2", "S3"]
    )
    assert ok.status_code == 201, ok.text

    serials = client.get("/api/v1/inventory/serials", headers=auth_headers).json()
    by_number = {s["serial_number"]: s for s in serials}
    assert {"S1", "S2", "S3"} <= set(by_number)
    assert all(by_number[n]["status"] == "in_stock" for n in ("S1", "S2", "S3"))
    assert all(by_number[n]["batch_ref"] == "B1" for n in ("S1", "S2", "S3"))


def test_duplicate_serial_number_is_rejected(client, auth_headers, master_data):
    vendor_id = master_data["vendor_id"]
    product_id = _create_product(client, auth_headers, sku="SN-2", track_batches=False, track_serials=True)
    bin_id = _create_bin(client, auth_headers, "BIN-SN2")

    po1, line1 = _approved_po(client, auth_headers, vendor_id, product_id, qty="1")
    first = _receive(client, auth_headers, po1["id"], line1, bin_id, qty_received="1", serials=["DUP-1"])
    assert first.status_code == 201, first.text

    po2, line2 = _approved_po(client, auth_headers, vendor_id, product_id, qty="1")
    second = _receive(client, auth_headers, po2["id"], line2, bin_id, qty_received="1", serials=["DUP-1"])
    assert second.status_code == 400, second.text
    assert second.json()["error"]["code"] == "SERIAL_DUPLICATE"


def test_outbound_movement_releases_serials(client, auth_headers, master_data):
    vendor_id = master_data["vendor_id"]
    product_id = _create_product(client, auth_headers, sku="SN-3", track_batches=False, track_serials=True)
    bin_id = _create_bin(client, auth_headers, "BIN-SN3")

    po, line_id = _approved_po(client, auth_headers, vendor_id, product_id, qty="2")
    ok = _receive(client, auth_headers, po["id"], line_id, bin_id, qty_received="2", serials=["OUT-1", "OUT-2"])
    assert ok.status_code == 201, ok.text

    fy = client.post(
        "/api/v1/fiscal-years",
        headers=auth_headers,
        json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    assert fy.status_code == 201, fy.text

    resp = client.post(
        "/api/v1/inventory/adjustments",
        headers=auth_headers,
        json={
            "product_id": product_id,
            "location_id": bin_id,
            "quantity": "1",
            "direction": "decrease",
            "reason": "sold",
        },
    )
    assert resp.status_code == 201, resp.text

    issued = client.get("/api/v1/inventory/serials?status=issued", headers=auth_headers).json()
    assert [s["serial_number"] for s in issued] == ["OUT-1"]  # FIFO releases the oldest

    in_stock = client.get("/api/v1/inventory/serials?status=in_stock", headers=auth_headers).json()
    assert [s["serial_number"] for s in in_stock] == ["OUT-2"]
