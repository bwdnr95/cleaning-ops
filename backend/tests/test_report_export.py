def test_revenue_export_csv(client, seed_admin_token):
    res = client.get(
        "/api/admin/reports/revenue/export",
        params={
            "granularity": "month",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "format": "csv",
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    content_disposition = res.headers.get("content-disposition", "")
    assert "attachment" in content_disposition
    assert 'filename="revenue.csv"' in content_disposition
    assert res.content.startswith(b"\xef\xbb\xbf")
    text = res.content.decode("utf-8-sig")
    header_line = text.splitlines()[0]
    assert "period" in header_line
    assert "revenue" in header_line


def test_revenue_export_xlsx(client, seed_admin_token):
    res = client.get(
        "/api/admin/reports/revenue/export",
        params={
            "granularity": "month",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "format": "xlsx",
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(res.content) > 100


def test_export_unsupported_format_returns_400(client, seed_admin_token):
    res = client.get(
        "/api/admin/reports/revenue/export",
        params={
            "granularity": "month",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "format": "pdf",
        },
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code in {400, 422}


def test_export_requires_admin(client):
    res = client.get(
        "/api/admin/reports/revenue/export",
        params={
            "granularity": "month",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "format": "csv",
        },
    )
    assert res.status_code in {401, 403}


def test_partners_export_csv(client, seed_admin_token):
    res = client.get(
        "/api/admin/reports/partners/export",
        params={"start_date": "2026-01-01", "end_date": "2026-12-31", "format": "csv"},
        headers={"Authorization": f"Bearer {seed_admin_token}"},
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
