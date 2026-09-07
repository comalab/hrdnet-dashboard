from datetime import datetime, timedelta
from urllib.parse import quote
from io import BytesIO
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st

# ── 날짜 설정 ──
_today = datetime.now()
_wn_start = _today.strftime("%Y%m%d")
_wn_start_dp = _today.strftime("%Y-%m-%d")
_wn_end = (_today + timedelta(days=365)).strftime("%Y%m%d")
_wn_end_dp = (_today + timedelta(days=365)).strftime("%Y-%m-%d")
_report_date = _today.strftime("%y%m%d")


def create_url(keyword: str) -> str:
    kw = quote(keyword)
    return (
        f"https://www.work24.go.kr/hr/a/a/1100/trnnCrsInf.do?"
        f"dghtSe=A&traingMthCd=A&endDate={_wn_end}&trng_prd=A&pageSize=10"
        f"&startDate_datepicker={_wn_start_dp}&topMenuYn=&tracseId=AIG20240000470957"
        f"&totamtSuptYn=A&crseTracseSeNum=&keyword={kw}"
        f"&area=26230%7C%EB%B6%80%EC%82%B0+%EB%B6%80%EC%82%B0%EC%A7%84%EA%B5%AC"
        f"&orderKey=2&kdgLinkYn=&srchType=all_type"
        f"&crseTracseSe=A%7C%ED%9B%88%EB%A0%A8%EC%9C%A0%ED%98%95+%EC%A0%84%EC%B2%B4"
        f"&tranRegister=&trng_type=A&mberId=&pageId=2&noTrngPay=Y"
        f"&endDate_datepicker={_wn_end_dp}&monthGubun=&pageOrder=2ASC"
        f"&startTrngPay=&startDate={_wn_start}&endTrngPay=&tracseTme=5"
        f"&keyword1=&keyword2=&orderBy=ASC&currentTab=2&pop=&pageRow=10"
        f"&ncsSearchKeyword=&keywordTrngNm=&keywordType=1&gb=&kDgtlYn=&mberSe="
        f"&max_trng=&totTraingTime=A&i2=A&areaSearchKeyword="
        f"&programMenuIdentification=EBG020000000310&min_trng=&pageIndex=1"
        f"&chkNoTrngPay=Y&bgrlInstYn=&crseTracseSeKDT=&ncs=&gvrnInstt="
        f"&selectNCSKeyword=&compareArgArr=&action=trnnCrsInfPost.do"
    )


COURSE_TYPE_TAGS = {
    "산업구조변화대응": "산대특",
    "국가기간전략직종": "국기",
    "과정평가형": "과평",
}


def crawl_courses(keyword: str) -> list:
    url = create_url(keyword)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    data = []
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")
        for c in soup.select("div.list[data-tracseid]"):
            inst = c.select_one("div.company_title a")
            title = c.select_one("h3.t3_sb a")
            price = c.select_one("div.coin span.item")
            period = c.select_one("div.info span.time")
            period_text = period.get_text().strip() if period else "정보없음"

            start_md = ""
            if period_text != "정보없음":
                try:
                    raw = period_text.split()[0].strip().replace("-", ".")
                    d = datetime.strptime(raw, "%Y.%m.%d")
                    start_md = f"{d.month}/{d.day}"
                except Exception:
                    start_md = period_text.split()[0] if period_text.split() else ""

            total_time = c.select("div.info a")
            location = c.select_one("div.site p.s1_r")
            emp = c.select_one("div.member span.item em.txt") or c.select_one(
                "div.member span.line em.txt"
            )
            pay = c.select_one("div.right_btn_area div.mb8")
            pay_text = pay.get_text(strip=True).split("\n")[0] if pay else "정보없음"
            if "원" in pay_text:
                pay_text = pay_text.split("원")[0] + "원"
            status = c.select_one("div.right_btn_area span.t3_sb")

            badge_texts = [
                b.get_text(strip=True) for b in c.select("span.clr_blue.fw600")
            ]
            course_type = ""
            for label, tag in COURSE_TYPE_TAGS.items():
                if any(label in b for b in badge_texts):
                    course_type = tag
                    break

            data.append(
                {
                    "검색키워드": keyword,
                    "훈련기관": inst.get_text(strip=True) if inst else "정보없음",
                    "과정명": title.get_text(strip=True) if title else "정보없음",
                    "훈련비용": price.get_text(strip=True) if price else "정보없음",
                    "훈련기간": period_text,
                    "시작일자": start_md,
                    "과정구분": course_type,
                    "총시간": (
                        total_time[0].get_text(strip=True) if total_time else "정보없음"
                    ),
                    "지역": location.get_text(strip=True) if location else "정보없음",
                    "취업률": emp.get_text(strip=True) if emp else "정보없음",
                    "본인부담금": pay_text,
                    "모집상태": status.get_text(strip=True) if status else "정보없음",
                }
            )
    except Exception as e:
        st.warning(f"'{keyword}' 오류: {e}")
    return data


# ── 기관명 변환 매핑 ──
inst_map = {
    "양정인력개발센터": "양정",
    "미토직업전문학교": "미토",
    "부산예일직업전문학교": "예일",
    "미래창조평생교육원": "미창",
    "정연화의료서비스아카데미전문학원": "정연화",
    "그린컴퓨터아카데미 부산": "그린",
    "엠비씨(MBC)아카데미 컴퓨터교육센터 화곡점" : "엠비씨",
    "엠아카데미컴퓨터아트학원" : "엠아",
    "동성인재개발교육원" : "동성",
    "성심미용예술직업전문학교" : "성심"
}

MITO_INST_NAME = "미토직업전문학교"
MITO_TOP_RANK = 5  # 부정훈련 신고 대비: 1~5등 내 미토 과정이 3개 이상이면 조정 필요
MITO_MAX_COUNT = 2  # 이 개수를 초과하면(=3개 이상) 조정 필요


def check_mito_top_rank(df: pd.DataFrame, keywords: list, top_n: int = MITO_TOP_RANK) -> list:
    """직종(키워드)별 상위 top_n 순위 내에 미토직업전문학교 과정이 2개 이상인 키워드 목록 반환"""
    flagged = []
    for kw in keywords:
        kw_df = df[df["검색키워드"] == kw].head(top_n)
        if (kw_df["훈련기관"] == MITO_INST_NAME).sum() > MITO_MAX_COUNT:
            flagged.append(kw)
    return flagged


def generate_report(df: pd.DataFrame, keywords: list) -> str:

    flagged_keywords = check_mito_top_rank(df, keywords)

    lines = []
    if flagged_keywords:
        lines.append(
            f"⚠️ [조정 필요] {MITO_INST_NAME} 과정이 상위 {MITO_TOP_RANK}등 이내에 {MITO_MAX_COUNT + 1}개 이상 있는 직종: "
            + ", ".join(flagged_keywords)
            + "\n"
        )
    lines.append(f"[{_report_date} 예비반 순위]\n\n해당 데이터를 바탕으로 {_report_date} 예비반 순위 보고드립니다.\n")
    for kw in keywords:
        kw_df = df[df["검색키워드"] == kw].head(10)
        lines.append(f"\n{kw} 1p 순위\n")




        if not kw_df.empty:
            for i, row in enumerate(kw_df.itertuples(), 1):
                s = row.시작일자 if row.시작일자 else "날짜확인불가"
                inst_name = inst_map.get(row.훈련기관, row.훈련기관)  # 매핑 적용
                is_mito = row.훈련기관 == MITO_INST_NAME
                tag_suffix = (
                    f" ({row.과정구분})" if is_mito and getattr(row, "과정구분", "") else ""
                )
                mark = " ⚠️" if is_mito and i <= MITO_TOP_RANK and kw in flagged_keywords else ""
                lines.append(f"{i}. {inst_name} {s}{tag_suffix}{mark}")
        else:
            lines.append("검색된 훈련 과정이 없습니다.")
        lines.append("")
    return "\n".join(lines)


if hasattr(st, "dialog"):

    @st.dialog("⚠️ 조정 필요 알림")
    def show_mito_alert(flagged_keywords: list):
        st.warning(
            f"**{MITO_INST_NAME}** 과정이 상위 {MITO_TOP_RANK}등 이내에 {MITO_MAX_COUNT + 1}개 이상 있는 직종이 있습니다.\n\n"
            + "\n".join(f"- {kw}" for kw in flagged_keywords)
            + "\n\n부정훈련 신고 대비를 위해 예비반 순위를 확인하고 조정해 주세요."
        )
        if st.button("확인", use_container_width=True):
            st.session_state.mito_alert_dismissed = True
            st.rerun()

else:

    def show_mito_alert(flagged_keywords: list):
        st.toast(
            f"⚠️ 조정 필요: {MITO_INST_NAME} 상위 {MITO_TOP_RANK}등 이내 {MITO_MAX_COUNT + 1}개 이상 ({', '.join(flagged_keywords)})",
            icon="⚠️",
        )
        st.session_state.mito_alert_dismissed = True


def to_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="검색결과", index=False)
    return output.getvalue()


# ── UI ──────────────────────────────────────
st.title("🔍 고용24 키워드 검색")
st.caption("부산 부산진구 기준 · 수강신청인원 순 정렬 · 키워드당 최대 10건")
st.divider()

if "crawl_df" not in st.session_state:
    st.session_state.crawl_df = None

keyword_input = st.text_area(
    "검색 키워드 (한 줄에 하나씩 입력)",
    placeholder="예시:\n파이썬\n데이터분석\nUX/UI",
    height=160,
)

if st.button("🕷️ 크롤링 시작", type="primary", use_container_width=True):
    keywords = [k.strip() for k in keyword_input.strip().splitlines() if k.strip()]
    if not keywords:
        st.error("키워드를 입력해 주세요.")
    else:
        all_data = []
        prog = st.progress(0)
        for idx, kw in enumerate(keywords, 1):
            st.write(f"⏳ `{kw}` 검색 중...")
            result = crawl_courses(kw)
            all_data.extend(result)
            st.write(f"✅ **{kw}** → {len(result)}개 수집")
            prog.progress(idx / len(keywords))
            if idx < len(keywords):
                time.sleep(3)
        prog.empty()

        if all_data:
            st.session_state.crawl_df = pd.DataFrame(all_data)
            st.session_state.mito_alert_dismissed = False
            st.success(f"총 **{len(all_data):,}건** 수집 완료!")
        else:
            st.warning("수집된 데이터가 없습니다.")

crawl_df = st.session_state.get("crawl_df")
if crawl_df is not None and not crawl_df.empty:
    st.divider()

    flagged_keywords = check_mito_top_rank(
        crawl_df, crawl_df["검색키워드"].unique().tolist()
    )
    if flagged_keywords:
        st.error(
            f"⚠️ **[조정 필요]** {MITO_INST_NAME} 과정이 상위 {MITO_TOP_RANK}등 이내에 {MITO_MAX_COUNT + 1}개 이상 있는 직종: "
            + ", ".join(flagged_keywords)
        )
        if not st.session_state.get("mito_alert_dismissed", False):
            show_mito_alert(flagged_keywords)

    st.caption(f"수집 결과: **{len(crawl_df):,}건**")

    st.dataframe(
        crawl_df.drop(columns=["시작일자"]),
        use_container_width=True,
        height=420,
    )

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="📄 엑셀 다운로드",
            data=to_excel(crawl_df.drop(columns=["시작일자"])),
            file_name=f"고용24_검색결과_{_wn_start}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with col2:
        report_text = generate_report(
            crawl_df, crawl_df["검색키워드"].unique().tolist()
        )
        st.download_button(
            label="📝 순위 보고서 다운로드",
            data=report_text.encode("utf-8"),
            file_name=f"순위보고서_{_report_date}.txt",
            mime="text/plain; charset=utf-8",
            use_container_width=True,
        )

    with st.expander("📋 순위 보고서 미리보기"):
        st.text(report_text)
else:
    st.info("위에서 키워드를 입력하고 [크롤링 시작] 버튼을 클릭하세요.")