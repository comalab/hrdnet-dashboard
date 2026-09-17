import socket
import time

import requests
import streamlit as st

st.title("🔧 고용24 연결 진단 (임시 페이지)")
st.caption("진단이 끝나면 이 페이지는 삭제해도 됩니다.")

TEST_URLS = [
    {"name": "고용24 메인", "url": "https://www.work24.go.kr"},
    {"name": "고용24 메인 페이지", "url": "https://www.work24.go.kr/cm/main.do"},
    {"name": "고용24 훈련과정 검색", "url": "https://www.work24.go.kr/hr/a/a/1100/trnnCrsInf.do"},
    {"name": "고용24 Open API", "url": "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"},
]


def test_dns():
    host = "www.work24.go.kr"
    try:
        ip = socket.gethostbyname(host)
        return True, f"[성공] {host} -> {ip}"
    except Exception as e:
        return False, f"[실패] DNS 조회 오류: {e}"


def test_tcp():
    host = "www.work24.go.kr"
    port = 443
    try:
        start = time.time()
        sock = socket.create_connection((host, port), timeout=10)
        elapsed = time.time() - start
        sock.close()
        return True, f"[성공] {host}:{port} / 연결시간 {elapsed:.2f}초"
    except Exception as e:
        return False, f"[실패] TCP 연결 오류: {e}"


def test_requests():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/152.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
    }
    session = requests.Session()
    session.headers.update(headers)

    results = []
    for item in TEST_URLS:
        name, url = item["name"], item["url"]
        try:
            start = time.time()
            response = session.get(url, timeout=(15, 30), allow_redirects=True)
            elapsed = time.time() - start
            results.append(
                {
                    "이름": name,
                    "url": url,
                    "상태": "성공",
                    "HTTP코드": response.status_code,
                    "응답시간(초)": round(elapsed, 2),
                    "응답크기(bytes)": len(response.content),
                    "최종URL": response.url,
                    "에러": "",
                }
            )
        except requests.exceptions.ConnectTimeout as e:
            results.append({"이름": name, "url": url, "상태": "ConnectTimeout", "HTTP코드": "", "응답시간(초)": "", "응답크기(bytes)": "", "최종URL": "", "에러": str(e)})
        except requests.exceptions.ReadTimeout as e:
            results.append({"이름": name, "url": url, "상태": "ReadTimeout", "HTTP코드": "", "응답시간(초)": "", "응답크기(bytes)": "", "최종URL": "", "에러": str(e)})
        except requests.exceptions.SSLError as e:
            results.append({"이름": name, "url": url, "상태": "SSL 오류", "HTTP코드": "", "응답시간(초)": "", "응답크기(bytes)": "", "최종URL": "", "에러": str(e)})
        except requests.exceptions.ConnectionError as e:
            results.append({"이름": name, "url": url, "상태": "ConnectionError", "HTTP코드": "", "응답시간(초)": "", "응답크기(bytes)": "", "최종URL": "", "에러": str(e)})
        except Exception as e:
            results.append({"이름": name, "url": url, "상태": type(e).__name__, "HTTP코드": "", "응답시간(초)": "", "응답크기(bytes)": "", "최종URL": "", "에러": str(e)})

    return results


st.divider()
st.subheader("🔎 비교 테스트 — Google / Naver / 고용24")
st.caption("고용24만 막혀 있는지, 이 서버 자체의 아웃바운드 연결이 막혀 있는지 구분합니다.")

if st.button("비교 테스트 시작"):
    compare_hosts = [
        ("www.google.com", 443),
        ("www.naver.com", 443),
        ("www.work24.go.kr", 443),
    ]
    for host, port in compare_hosts:
        try:
            start = time.time()
            s = socket.create_connection((host, port), timeout=10)
            elapsed = time.time() - start
            s.close()
            st.success(f"{host}:{port} → 성공 ({elapsed:.2f}초)")
        except Exception as e:
            st.error(f"{host}:{port} → 실패: {e}")

st.divider()

if st.button("🚀 진단 시작", type="primary"):
    st.subheader("1. DNS 확인")
    dns_ok, dns_msg = test_dns()
    st.write(dns_msg)

    st.subheader("2. HTTPS 포트(443) 연결 확인")
    tcp_ok, tcp_msg = test_tcp()
    st.write(tcp_msg)

    st.subheader("3. HTTP/HTTPS 요청 테스트")
    results = test_requests()
    for r in results:
        with st.expander(f"{r['이름']} — {r['상태']}" + (f" / HTTP {r['HTTP코드']}" if r["HTTP코드"] != "" else "")):
            st.json(r)

    st.subheader("4. 최종 요약")
    st.write(f"DNS 조회: {'정상' if dns_ok else '실패'}")
    st.write(f"443 포트: {'정상' if tcp_ok else '실패'}")
    for r in results:
        code = f" / HTTP {r['HTTP코드']}" if r["HTTP코드"] != "" else ""
        st.write(f"- {r['이름']}: {r['상태']}{code}")
else:
    st.info("버튼을 누르면 Streamlit Cloud 서버에서 직접 고용24 접속을 테스트합니다.")
