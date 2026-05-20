def test_csp_includes_kakao_postcode_domains(client):
    response = client.get("/api/health")
    csp = response.headers.get("content-security-policy", "")
    assert "https://t1.daumcdn.net" in csp
    assert "https://postcode.map.kakao.com" in csp
    assert "script-src" in csp
    assert "frame-src" in csp
