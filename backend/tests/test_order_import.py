import io

import pytest
from openpyxl import Workbook


def _make_xlsx(rows: list[list]) -> bytes:
    return _make_xlsx_with_headers(
        [
            "group_key",
            "customer_name",
            "customer_phone",
            "customer_address",
            "scheduled_date",
            "service_name",
            "total_amount",
        ],
        rows,
    )


def _make_xlsx_with_headers(headers: list[str], rows: list[list]) -> bytes:
    wb = Workbook()
    try:
        ws = wb.active
        ws.append(headers)
        for row in rows:
            ws.append(row)
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
    finally:
        wb.close()


def test_order_import_single_group_with_two_lines(client, seed_admin_token):
    data = _make_xlsx(
        [
            ["G1", "Test Customer", "010-1111-2222", "Seoul 1", "2026-06-01", "Aircon", 100000],
            ["G1", "Test Customer", "010-1111-2222", "Seoul 1", "2026-06-01", "Living", 80000],
        ]
    )
    res = client.post(
        "/api/admin/orders/import",
        files={
            "file": (
                "orders.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["succeeded_groups"] == 1
    assert body["succeeded_lines"] == 2
    assert body["failed"] == []


def test_order_import_two_groups(client, seed_admin_token):
    data = _make_xlsx(
        [
            ["G1", "Customer A", "010-1111-2222", "Gangnam", "2026-06-01", "Aircon", 100000],
            ["G2", "Customer B", "010-3333-4444", "Gangbuk", "2026-06-02", "Move", 250000],
        ]
    )
    res = client.post(
        "/api/admin/orders/import",
        files={
            "file": (
                "orders.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    body = res.json()
    assert res.status_code == 200
    assert body["succeeded_groups"] == 2
    assert body["succeeded_lines"] == 2


def test_order_import_accepts_multiple_visit_dates(client, seed_admin_token):
    headers = [
        "group_key",
        "customer_name",
        "customer_phone",
        "customer_address",
        "scheduled_date",
        "visit_dates",
        "service_name",
        "total_amount",
    ]
    data = _make_xlsx_with_headers(
        headers,
        [[
            "MULTI",
            "Multi Visit Import",
            "010-1212-3434",
            "Seoul Multi",
            "2026-09-02",
            "2026-09-02, 2026-09-03, 2026-09-07",
            "Multi-day Cleaning",
            300000,
        ]],
    )
    response = client.post(
        "/api/admin/orders/import",
        files={
            "file": (
                "orders.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["succeeded_lines"] == 1

    orders = client.get(
        "/api/admin/orders?include_past_paid=true",
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert orders.status_code == 200, orders.text
    imported = next(
        order for order in orders.json() if order["service_name"] == "Multi-day Cleaning"
    )
    assert imported["visit_dates"] == ["2026-09-02", "2026-09-03", "2026-09-07"]


def test_order_import_reports_invalid_rows(client, seed_admin_token):
    data = _make_xlsx(
        [
            ["", "", "010-1111-2222", "Gangnam", "2026-06-01", "Aircon", 100000],
            ["G2", "Customer B", "abc", "Gangnam", "2026-06-02", "Aircon", 100000],
            ["G3", "Customer C", "010-9999-8888", "Gangnam", "2026-06-03", "Aircon", 100000],
        ]
    )
    res = client.post(
        "/api/admin/orders/import",
        files={
            "file": (
                "orders.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    body = res.json()
    assert res.status_code == 200
    assert body["succeeded_groups"] == 1
    assert body["succeeded_lines"] == 1
    assert {failure["row_index"] for failure in body["failed"]} == {1, 2}


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity"])
def test_order_import_reports_non_finite_amounts(
    client,
    seed_admin_token,
    amount: str,
):
    data = _make_xlsx(
        [["G1", "Customer", "010-1111-2222", "Seoul", "2026-06-01", "Aircon", amount]]
    )
    response = client.post(
        "/api/admin/orders/import",
        files={
            "file": (
                "orders.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["succeeded_groups"] == 0
    assert body["succeeded_lines"] == 0
    assert body["failed"] == [
        {"row_index": 1, "reason": f"invalid_total_amount:{amount}"}
    ]


def test_order_import_group_rollback_when_one_line_invalid(client, seed_admin_token):
    data = _make_xlsx(
        [
            ["G1", "Customer A", "010-1111-2222", "Gangnam", "2026-06-01", "Aircon", 100000],
            ["G1", "Customer A", "abc", "Gangnam", "2026-06-01", "Living", 80000],
        ]
    )
    res = client.post(
        "/api/admin/orders/import",
        files={
            "file": (
                "orders.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    body = res.json()
    assert res.status_code == 200
    assert body["succeeded_groups"] == 0
    assert body["succeeded_lines"] == 0
    reasons = {failure["reason"] for failure in body["failed"]}
    assert any("invalid_phone" in reason for reason in reasons)
    assert "group_skipped_due_to_sibling_error" in reasons


def test_order_import_rejects_inconsistent_group_customer(client, seed_admin_token):
    data = _make_xlsx(
        [
            ["G1", "Customer A", "010-1111-2222", "Gangnam", "2026-06-01", "Aircon", 100000],
            ["G1", "Other Name", "010-1111-2222", "Gangnam", "2026-06-02", "Living", 80000],
        ]
    )
    res = client.post(
        "/api/admin/orders/import",
        files={
            "file": (
                "orders.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    body = res.json()
    assert res.status_code == 200
    assert body["succeeded_groups"] == 0
    reasons = {failure["reason"] for failure in body["failed"]}
    assert "inconsistent_group_customer" in reasons


def test_order_import_rejects_invalid_file_type(client, seed_admin_token):
    res = client.post(
        "/api/admin/orders/import",
        files={"file": ("orders.txt", b"not xlsx", "text/plain")},
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code in {400, 415}


def test_order_import_trims_header_names(client, seed_admin_token):
    data = _make_xlsx_with_headers(
        [
            "group_key ",
            " customer_name",
            "customer_phone",
            "customer_address",
            "scheduled_date",
            "service_name",
            "total_amount",
        ],
        [["G1", "Customer A", "010-1111-2222", "Gangnam", "2026-06-01", "Aircon", 100000]],
    )
    res = client.post(
        "/api/admin/orders/import",
        files={
            "file": (
                "orders.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    body = res.json()
    assert res.status_code == 200
    assert body["succeeded_groups"] == 1
    assert body["failed"] == []


def test_order_import_requires_admin(client, seed_partner_token):
    data = _make_xlsx([["G1", "X", "010-0000-0000", "X", "2026-06-01", "X", 1000]])
    res = client.post(
        "/api/admin/orders/import",
        files={
            "file": (
                "orders.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers={"Authorization": f"Bearer {seed_partner_token}"},
    )
    assert res.status_code in {401, 403}
