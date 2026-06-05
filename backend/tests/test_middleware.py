def test_csp_includes_kakao_postcode_domains(client):
    response = client.get("/api/health")
    csp = response.headers.get("content-security-policy", "")
    assert "https://t1.daumcdn.net" in csp
    assert "https://postcode.map.kakao.com" in csp
    assert "script-src" in csp
    assert "frame-src" in csp


def test_csp_allows_pretendard_cdn_for_style_and_font(client):
    response = client.get("/api/health")
    csp = response.headers.get("content-security-policy", "")
    style_directive = next(part for part in csp.split(";") if part.strip().startswith("style-src"))
    font_directive = next(part for part in csp.split(";") if part.strip().startswith("font-src"))
    assert "https://cdn.jsdelivr.net" in style_directive
    assert "https://cdn.jsdelivr.net" in font_directive
