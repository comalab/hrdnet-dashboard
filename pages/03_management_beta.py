import calendar
from datetime import date, datetime, timedelta
from io import BytesIO
import os
import sys

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# 루트 디렉터리를 sys.path에 추가하여 공용 모듈 로드 지원
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hrdnet_crawler import HRDNetCrawler
from ncs_helper import map_ncs_code

# ─────────────────────────────────────────────
# 페이지 기본 설정 및 스타일
# ─────────────────────────────────────────────
st.markdown(
    """
    <style>
    .bi-header {
        font-size: 2rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.2rem;
    }
    .bi-subheader {
        font-size: 1rem;
        color: #64748b;
        margin-bottom: 1.5rem;
    }
    .beta-badge {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        vertical-align: middle;
        margin-left: 0.5rem;
    }
    /* 달력 그리드 스타일 */
    .cal-container {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        overflow: hidden;
        background: #ffffff;
        margin-top: 1rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
    }
    .cal-header-row {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        background: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
        text-align: center;
        font-weight: 700;
        font-size: 0.88rem;
        color: #475569;
    }
    .cal-header-cell {
        padding: 10px 0;
    }
    .cal-header-sun { color: #ef4444; }
    .cal-header-sat { color: #3b82f6; }
    .cal-grid-row {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        border-bottom: 1px solid #f1f5f9;
    }
    .cal-cell {
        min-height: 125px;
        max-height: 175px;
        overflow-y: auto;
        padding: 6px;
        border-right: 1px solid #f1f5f9;
        background: #ffffff;
        transition: background 0.15s ease;
    }
    .cal-cell:last-child {
        border-right: none;
    }
    .cal-cell-empty {
        background: #fcfdfe;
        min-height: 125px;
        border-right: 1px solid #f1f5f9;
    }
    .cal-cell-today {
        background: #f0fdf4 !important;
        border: 2px solid #22c55e !important;
    }
    .cal-day-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
        padding-bottom: 2px;
        border-bottom: 1px solid #f1f5f9;
    }
    .cal-day-num {
        font-weight: 700;
        font-size: 0.85rem;
        color: #334155;
    }
    .cal-day-badge-cnt {
        font-size: 0.72rem;
        font-weight: 700;
        background: #e2e8f0;
        color: #475569;
        padding: 1px 5px;
        border-radius: 9999px;
    }
    .cal-pill {
        border-radius: 4px;
        padding: 2px 5px;
        font-size: 0.72rem;
        line-height: 1.35;
        margin-bottom: 3px;
        display: block;
        text-overflow: ellipsis;
        white-space: nowrap;
        overflow: hidden;
        border-left: 3px solid;
    }
    .cal-pill-conflict {
        background: #fef2f2;
        color: #b91c1c;
        border: 1px dashed #f87171;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 2px 4px;
        border-radius: 4px;
        margin-bottom: 3px;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="bi-header">📊 훈련과정 경영 전략 대시보드 <span class="beta-badge">BETA</span></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="bi-subheader">실제 등록 인원수 중심의 시장 규모, 학원별 복수 선택 비교, 개강일정 캘린더 및 빈집털이 전략 분석</div>',
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────
# 기관명 단축 및 캘린더 뱃지 색상 매핑
# ─────────────────────────────────────────────
INST_MAP = {
    "미토직업전문학교": "미토",
    "양정인력개발센터": "양정",
    "부산예일직업전문학교": "예일",
    "미래창조평생교육원": "미창",
    "정연화의료서비스아카데미전문학원": "정연화",
    "그린컴퓨터아카데미 부산": "그린",
    "동성인재개발교육원": "동성",
    "성심미용예술직업전문학교": "성심",
    "엠아카데미컴퓨터아트학원": "엠아",
}


def get_short_inst_name(full_name: str) -> str:
    if not full_name:
        return ""
    for k, v in INST_MAP.items():
        if k in full_name:
            return v
    clean = (
        full_name.replace("직업전문학교", "")
        .replace("아카데미", "")
        .replace("인재개발원", "")
        .replace("교육원", "")
        .strip()
    )
    return clean[:4] if clean else full_name[:4]


def get_organ_badge_style(organ_name: str) -> dict:
    tag = get_short_inst_name(organ_name)
    if "미토" in organ_name:
        return {"bg": "#dcfce7", "text": "#166534", "border": "#22c55e", "tag": tag}
    elif "양정" in organ_name:
        return {"bg": "#dbeafe", "text": "#1e40af", "border": "#3b82f6", "tag": tag}
    elif "예일" in organ_name:
        return {"bg": "#f3e8ff", "text": "#6b21a8", "border": "#a855f7", "tag": tag}
    elif "그린" in organ_name:
        return {"bg": "#ffedd5", "text": "#9a3412", "border": "#f97316", "tag": tag}
    elif "동성" in organ_name:
        return {"bg": "#fce7f3", "text": "#9d174d", "border": "#ec4899", "tag": tag}
    elif "미래" in organ_name or "미창" in organ_name:
        return {"bg": "#ccfbf1", "text": "#115e59", "border": "#14b8a6", "tag": tag}
    elif "정연화" in organ_name:
        return {"bg": "#fef9c3", "text": "#854d0e", "border": "#eab308", "tag": tag}
    else:
        return {"bg": "#f1f5f9", "text": "#334155", "border": "#64748b", "tag": tag}


# ─────────────────────────────────────────────
# 데이터 정제 및 파생변수 생성 함수
# ─────────────────────────────────────────────
def prepare_bi_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()

    if "수강신청인원" in df.columns and "등록인원" not in df.columns:
        df["등록인원"] = df["수강신청인원"]

    if "등록인원" not in df.columns:
        df["등록인원"] = 0
    if "실제훈련비" not in df.columns:
        df["실제훈련비"] = 0
    if "수강비" not in df.columns:
        df["수강비"] = 0
    if "만족도점수" not in df.columns:
        df["만족도점수"] = 0.0
    if "직종명" not in df.columns:
        df["직종명"] = "기타직종"

    df["등록인원"] = pd.to_numeric(df["등록인원"], errors="coerce").fillna(0).astype(int)
    df["실제훈련비"] = pd.to_numeric(df["실제훈련비"], errors="coerce").fillna(0)
    df["수강비"] = pd.to_numeric(df["수강비"], errors="coerce").fillna(0)
    df["만족도점수"] = pd.to_numeric(df["만족도점수"], errors="coerce").fillna(0.0)

    df["예상매출"] = df["등록인원"] * df["실제훈련비"]

    today = date.today()
    df["시작일_dt"] = pd.to_datetime(df["훈련시작일"], errors="coerce")
    df["종료일_dt"] = pd.to_datetime(df["훈련종료일"], errors="coerce")
    df["개강월"] = df["시작일_dt"].dt.strftime("%Y-%m")
    df["개강일자"] = df["시작일_dt"].dt.strftime("%Y-%m-%d")

    def calc_dday(dt):
        if pd.isna(dt):
            return None
        return (dt.date() - today).days

    df["D-Day"] = df["시작일_dt"].apply(calc_dday)

    def classify_headcount_status(reg_count):
        if reg_count >= 12:
            return "🟢 안정권 (12명 이상)"
        elif reg_count >= 6:
            return "🟡 보통 (6~11명)"
        elif reg_count > 0:
            return "🔴 인원저조 (1~5명)"
        else:
            return "⚪ 미등록 (0명)"

    df["인원구분"] = [classify_headcount_status(r) for r in df["등록인원"]]
    df["기관약칭"] = [get_short_inst_name(o) for o in df["훈련기관명"]]

    return df


def to_excel_bi(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="경영인원분석", index=False)
    return output.getvalue()


# ─────────────────────────────────────────────
# 세션 상태 초기화
# ─────────────────────────────────────────────
sample_file_path = "미토직업전문학교훈련과정.xlsx"

if "bi_df" not in st.session_state:
    st.session_state.bi_df = None

# ─────────────────────────────────────────────
# 사이드바: 1) 과거 실적 검색 조건
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 HRD-Net 과거 실적 검색")
    st.caption("개강 확정된 실제 데이터를 위해 **오늘 포함 과거 개강 과정**만 추출합니다.")

    try:
        default_auth_key = st.secrets.get("HRDNET_API_KEY", "")
    except Exception:
        default_auth_key = ""

    auth_key = st.text_input(
        "API 인증키 *",
        value=default_auth_key,
        type="password",
        help="HRD-Net 오픈API 인증키 (.streamlit/secrets.toml 자동연동)",
    )

    st.subheader("조회 기간 설정")
    today = date.today()
    preset = st.radio(
        "기간 프리셋",
        ["최근 3개월", "최근 6개월", "최근 1년", "직접 설정"],
        index=1,
        horizontal=True,
    )
    if preset == "최근 3개월":
        calc_start = today - timedelta(days=90)
    elif preset == "최근 6개월":
        calc_start = today - timedelta(days=180)
    elif preset == "최근 1년":
        calc_start = today - timedelta(days=365)
    else:
        calc_start = today - timedelta(days=180)

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date_input = st.date_input(
            "시작일 (From)",
            value=calc_start,
            max_value=today,
            format="YYYY/MM/DD",
            key="bi_start_date",
        )
    with col_d2:
        end_date_input = st.date_input(
            "종료일 (To, 오늘까지)",
            value=today,
            max_value=today,
            format="YYYY/MM/DD",
            help="오늘 이전(과거) 개강 과정만 추출하도록 오늘 날짜로 제한됩니다.",
            key="bi_end_date",
        )

    st.subheader("훈련기관 / 과정명")
    train_organ_name = st.text_input("훈련기관명", placeholder="예: 미토직업전문학교 (전체: 빈칸)", key="bi_organ_input")
    course_name = st.text_input("훈련과정명", placeholder="예: 자바, 회계 (전체: 빈칸)", key="bi_course_input")

    st.subheader("지역")
    area_options = {
        "부산광역시": "26",
        "서울특별시": "11",
        "인천광역시": "28",
        "대구광역시": "27",
        "광주광역시": "29",
        "대전광역시": "30",
        "울산광역시": "31",
        "세종특별자치시": "36",
        "경기도": "41",
        "강원도": "42",
        "충청북도": "43",
        "충청남도": "44",
        "전라북도": "45",
        "전라남도": "46",
        "경상북도": "47",
        "경상남도": "48",
        "제주특별자치도": "50",
    }
    selected_area = st.selectbox("지역 선택", list(area_options.keys()), index=0, key="bi_area_select")
    area_code = area_options[selected_area]

    search_btn = st.button("🔎 과거 실적 검색 시작", type="primary", use_container_width=True)

    st.divider()

# ─────────────────────────────────────────────
# 검색 버튼 클릭 시 API 호출 및 과거 데이터 필터링
# ─────────────────────────────────────────────
if search_btn:
    if not auth_key:
        st.error("❌ API 인증키를 입력해주세요.")
        st.stop()

    start_date_str = start_date_input.strftime("%Y%m%d")
    end_date_str = end_date_input.strftime("%Y%m%d")

    crawler = HRDNetCrawler(auth_key)

    status_box = st.empty()
    progress_bar = st.progress(0)
    log_box = st.empty()

    status_box.info(f"⏳ 과거 개강 실적을 조회하는 중입니다... ({start_date_str} ~ {end_date_str})")

    def progress_callback(collected, total, page):
        pct = min(int(collected / total * 100), 100) if total > 0 else 0
        progress_bar.progress(pct)
        log_box.caption(f"페이지 {page} 완료 | 수집: {collected}/{total}건")

    try:
        courses, total_count = crawler.get_training_courses(
            train_organ_name=train_organ_name,
            course_name=course_name,
            area_code=area_code,
            start_date=start_date_str,
            end_date=end_date_str,
            progress_callback=progress_callback,
        )

        progress_bar.progress(100)
        log_box.empty()

        if courses:
            new_df = pd.DataFrame(courses)

            for col in ["훈련시작일", "훈련종료일"]:
                if col in new_df.columns:
                    new_df[col] = pd.to_datetime(new_df[col], errors="coerce").dt.strftime("%Y-%m-%d")

            new_df["_start_date_obj"] = pd.to_datetime(new_df["훈련시작일"], errors="coerce").dt.date
            new_df = new_df[new_df["_start_date_obj"] <= end_date_input].drop(columns=["_start_date_obj"])

            for col in ["수강비", "실제훈련비", "정원", "등록인원"]:
                if col in new_df.columns:
                    new_df[col] = pd.to_numeric(new_df[col], errors="coerce")

            if "NCS코드" in new_df.columns:
                new_df["직종명"] = new_df["NCS코드"].apply(map_ncs_code)

            st.session_state.df = new_df
            st.session_state.bi_df = prepare_bi_data(new_df)
            st.session_state.current_source = "searched"
            # 세션 변경 시 선택 학원 초기화
            if "selected_organs" in st.session_state:
                del st.session_state["selected_organs"]
            status_box.success(
                f"✅ 검색 완료! 오늘 이전 개강 과정 총 **{len(new_df):,}건**이 수집되어 분석에 반영되었습니다."
            )
        else:
            st.session_state.bi_df = None
            status_box.warning("⚠️ 조회된 훈련과정이 없습니다. 기간 및 검색 조건을 확인해주세요.")

    except Exception as e:
        status_box.error(f"❌ 오류 발생: {e}")
        progress_bar.empty()
        log_box.empty()


# ─────────────────────────────────────────────
# 상단 데이터 소스 안내바 및 불러오기 제어
# ─────────────────────────────────────────────
source_col1, source_col2 = st.columns([3, 1])

with source_col1:
    active_df = st.session_state.get("df")
    current_src = st.session_state.get("current_source")
    if current_src == "searched":
        st.success(f"🔍 **[과거 실적 검색 완료]** 조회된 **{len(st.session_state.bi_df):,}건**의 개강 실적을 분석 중입니다.")
    elif active_df is not None and not active_df.empty:
        st.success(f"🔗 **[HRD-Net 대시보드]** 에서 조회된 **{len(active_df):,}건**의 데이터와 연동 중입니다.")
        if st.session_state.bi_df is None or st.session_state.get("current_source") != "session":
            st.session_state.bi_df = prepare_bi_data(active_df)
            st.session_state.current_source = "session"
    else:
        st.info("💡 좌측 사이드바에서 [🔎 과거 실적 검색 시작]을 누르거나, 저장된 데이터를 불러와 바로 분석할 수 있습니다.")

with source_col2:
    with st.popover("📂 다른 데이터 불러오기"):
        st.markdown("**데이터 소스 선택:**")
        if active_df is not None and not active_df.empty:
            if st.button("🔄 HRD 조회 데이터 불러오기", use_container_width=True):
                st.session_state.bi_df = prepare_bi_data(active_df)
                st.session_state.current_source = "session"
                st.rerun()

        if os.path.exists(sample_file_path):
            if st.button("📁 기본 저장 데이터 (미토 106건)", use_container_width=True):
                try:
                    loaded = pd.read_excel(sample_file_path)
                    st.session_state.bi_df = prepare_bi_data(loaded)
                    st.session_state.current_source = "sample_file"
                    if "selected_organs" in st.session_state:
                        del st.session_state["selected_organs"]
                    st.toast("기본 데이터가 로드되었습니다!", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"로드 실패: {e}")

        uploaded_file = st.file_uploader("📤 엑셀 파일 직접 업로드", type=["xlsx", "xls"])
        if uploaded_file is not None:
            try:
                uploaded_df = pd.read_excel(uploaded_file)
                st.session_state.bi_df = prepare_bi_data(uploaded_df)
                st.session_state.current_source = "uploaded"
                if "selected_organs" in st.session_state:
                    del st.session_state["selected_organs"]
                st.toast("업로드된 엑셀 적용 완료!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"파싱 실패: {e}")

if st.session_state.bi_df is None and os.path.exists(sample_file_path):
    try:
        loaded = pd.read_excel(sample_file_path)
        st.session_state.bi_df = prepare_bi_data(loaded)
        st.session_state.current_source = "sample_file"
    except Exception:
        pass

df = st.session_state.bi_df

if df is None or df.empty:
    st.info(
        """
        👈 **좌측 사이드바에서 검색 조건을 설정하고 [🔎 과거 실적 검색 시작] 버튼을 클릭하세요.**

        - API 인증키를 입력하면 오늘 포함 과거에 개강한 실제 데이터를 즉시 수집하여 경영 분석을 수행합니다.
        - 또는 상단의 [📂 다른 데이터 불러오기]를 통해 엑셀 파일을 불러올 수 있습니다.
        """
    )
    st.stop()

# ─────────────────────────────────────────────
# 사이드바 하단: 학원 복수 선택 필터 및 세부 옵션
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🎯 인원 분석 및 학원 필터")

    exclude_zero = st.toggle(
        "🚫 모집인원 0명 과정 제외",
        value=True,
        help="등록인원이 0명인 과정(미개설/폐강 등)을 제외하고 실제 인원이 모집된 과정만 분석합니다.",
    )

    past_only = st.toggle(
        "📅 오늘 이전 개강 과정만 보기",
        value=True,
        help="개강일이 오늘 이전인 실제 개강 과정만 필터링합니다.",
    )

    all_organs = sorted(df["훈련기관명"].dropna().unique().tolist())
    is_mito_present = any("미토" in o for o in all_organs)

    # ── 학원 복수 선택 필터 섹션 ──
    st.subheader("🏫 훈련기관 선택 (복수 선택)")

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("전체 학원 선택", use_container_width=True):
            st.session_state.selected_organs = all_organs
            st.rerun()
    with col_b2:
        if is_mito_present:
            if st.button("미토만 선택", use_container_width=True):
                st.session_state.selected_organs = [o for o in all_organs if "미토" in o]
                st.rerun()

    # 기본 선택값 결정
    if "selected_organs" not in st.session_state:
        st.session_state.selected_organs = all_organs

    # 유효한 학원 목록 유지
    current_defaults = [o for o in st.session_state.selected_organs if o in all_organs]
    if not current_defaults:
        current_defaults = all_organs

    selected_organs = st.multiselect(
        "비교 분석할 학원들을 선택하세요",
        options=all_organs,
        default=current_defaults,
        placeholder="학원을 1개 이상 선택하세요",
        help="학원을 여러 개 선택하여 개강일정 및 등록 인원을 교차 비교할 수 있습니다.",
    )
    st.session_state.selected_organs = selected_organs

    # ── 직종 필터 ──
    all_jobs = sorted([j for j in df["직종명"].dropna().unique() if j])
    selected_jobs = st.multiselect(
        "직종(NCS) 필터",
        options=all_jobs,
        default=[],
        placeholder="전체 직종",
    )

    # ── 인원수 구간 필터 ──
    all_statuses = sorted(df["인원구분"].dropna().unique().tolist())
    selected_statuses = st.multiselect(
        "등록 인원수 구간",
        options=all_statuses,
        default=[],
        placeholder="전체 구간",
    )

# ─────────────────────────────────────────────
# 필터 적용 데이터프레임 생성
# ─────────────────────────────────────────────
filtered_df = df.copy()

if past_only:
    filtered_df = filtered_df[filtered_df["시작일_dt"].dt.date <= date.today()]

if exclude_zero:
    filtered_df = filtered_df[filtered_df["등록인원"] > 0]

if selected_organs:
    filtered_df = filtered_df[filtered_df["훈련기관명"].isin(selected_organs)]
else:
    st.warning("⚠️ 선택된 학원이 없습니다. 좌측 사이드바에서 학원을 1개 이상 선택해 주세요.")
    st.stop()

if selected_jobs:
    filtered_df = filtered_df[filtered_df["직종명"].isin(selected_jobs)]

if selected_statuses:
    filtered_df = filtered_df[filtered_df["인원구분"].isin(selected_statuses)]

with st.sidebar:
    st.caption(f"분석 대상: **{len(filtered_df):,}건** / 원본 {len(df):,}건")

if filtered_df.empty:
    st.warning("⚠️ 선택하신 조건에 부합하는 과정이 없습니다. '모집인원 0명 제외' 토글이나 학원/직종 필터를 조정해보세요.")
    st.stop()

# ─────────────────────────────────────────────
# 1. 상단 핵심 경영 KPI 요약 (실제 인원수 기준)
# ─────────────────────────────────────────────
total_courses = len(filtered_df)
total_registered = filtered_df["등록인원"].sum()
avg_registered_per_course = (total_registered / total_courses) if total_courses > 0 else 0.0
total_revenue = filtered_df["예상매출"].sum()
selected_org_count = filtered_df["훈련기관명"].nunique()

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric(
        label="👥 총 등록 인원수 (Total)",
        value=f"{total_registered:,}명",
        delta=f"선택 학원 {selected_org_count}개 / 과정 {total_courses:,}개",
        help="선택된 학원들에서 실제로 모집/등록된 수강생의 총합입니다.",
    )

with kpi2:
    st.metric(
        label="📊 과정당 평균 모집 인원",
        value=f"{avg_registered_per_course:.1f}명",
        help="과정 1개당 실제로 몇 명을 모았는지 보여주는 실제 모집 체급 지표입니다.",
    )

with kpi3:
    st.metric(
        label="💰 확보된 예상 총 매출",
        value=f"{total_revenue / 1e8:.2f} 억원" if total_revenue >= 1e8 else f"{total_revenue / 1e4:,.0f} 만원",
        delta=f"1인 평균 훈련비 {filtered_df['실제훈련비'].mean():,.0f}원",
        help="실제 등록 인원 × 1인당 정부지원 실제훈련비 기준 총액입니다.",
    )

with kpi4:
    low_enroll_courses = len(
        filtered_df[(filtered_df["등록인원"] > 0) & (filtered_df["등록인원"] <= 5)]
    )
    st.metric(
        label="⚠️ 5명 이하 소규모 과정",
        value=f"{low_enroll_courses:,}개",
        delta="소수 인원 개강군",
        delta_color="inverse" if low_enroll_courses > 0 else "off",
        help="등록인원이 1~5명 수준인 소규모 과정 수입니다.",
    )

st.divider()

# ─────────────────────────────────────────────
# 2. 경영 전략 분석 탭
# ─────────────────────────────────────────────
tab_job_volume, tab_calendar_view, tab_revenue, tab_institution, tab_data = st.tabs(
    [
        "🏆 [직종 규모] 직종별 실제 등록인원수",
        "🗓️ [개강 캘린더] 학원별 개강 일정 & 타임라인",
        "💵 [매출 실적] 인원수 기반 매출 분석",
        "🏫 [기관 체급] 학원별 실제 모집력 비교",
        "📋 [데이터] 상세 통합 분석표",
    ]
)

# ─────────────────────────────────────────────
# TAB 1: 직종(NCS)별 실제 등록인원수 랭킹
# ─────────────────────────────────────────────
with tab_job_volume:
    st.subheader("💡 직종(NCS)별 실제 수강생 볼륨 (어디에 사람이 몰렸는가?)")
    st.caption("선택된 학원들 중에서 실제로 가장 많은 수강생이 등록한 시장 수요 중심 직종을 파악합니다.")

    job_agg = (
        filtered_df.groupby("직종명")
        .agg(
            총등록인원=("등록인원", "sum"),
            개설과정수=("과정명", "count"),
            총예상매출=("예상매출", "sum"),
            평균훈련비=("실제훈련비", "mean"),
        )
        .reset_index()
    )
    job_agg["과정당평균인원"] = (job_agg["총등록인원"] / job_agg["개설과정수"]).round(1)
    job_agg = job_agg.sort_values("총등록인원", ascending=False)

    col_j1, col_j2 = st.columns([3, 2])

    with col_j1:
        st.markdown("#### 🥇 직종별 총 등록인원수 TOP 15")
        top_jobs = job_agg.head(15)
        fig_job_bar = px.bar(
            top_jobs.sort_values("총등록인원", ascending=True),
            x="총등록인원",
            y="직종명",
            orientation="h",
            text="총등록인원",
            color="총등록인원",
            color_continuous_scale="Blues",
            labels={"총등록인원": "실제 등록 인원수 (명)"},
            height=480,
        )
        fig_job_bar.update_traces(texttemplate="%{text:,}명", textposition="outside")
        fig_job_bar.update_layout(template="plotly_white", showlegend=False)
        st.plotly_chart(fig_job_bar, use_container_width=True)

    with col_j2:
        st.markdown("#### ⚡ 과정당 평균 모집 인원 TOP 10")
        st.caption("과정 1개 열었을 때 가장 사람이 많이 모인 알짜 직종 (과정 수 2개 이상)")
        efficient_jobs = (
            job_agg[job_agg["개설과정수"] >= 2]
            .sort_values("과정당평균인원", ascending=False)
            .head(10)
        )
        if not efficient_jobs.empty:
            fig_eff = px.bar(
                efficient_jobs,
                x="직종명",
                y="과정당평균인원",
                text="과정당평균인원",
                color="과정당평균인원",
                color_continuous_scale="Teal",
                labels={"과정당평균인원": "평균 인원(명/과정)"},
                height=420,
            )
            fig_eff.update_traces(texttemplate="%{text:.1f}명", textposition="outside")
            fig_eff.update_layout(template="plotly_white", showlegend=False)
            st.plotly_chart(fig_eff, use_container_width=True)
        else:
            st.caption("과정 수 2개 이상인 직종이 없습니다.")

    st.divider()

    st.markdown("#### 📌 직종별 수강생 유입 규모 요약")
    if not job_agg.empty:
        c_top1 = job_agg.iloc[0]
        st.info(
            f"현재 선택된 범위에서 가장 수강생이 많은 1위 직종은 **`{c_top1['직종명']}`** (총 **{c_top1['총등록인원']:,}명**, 과정 {c_top1['개설과정수']}개)이며, "
            f"과정당 평균 **{c_top1['과정당평균인원']}명**이 등록되었습니다."
        )

# ─────────────────────────────────────────────
# TAB 2: 개강일정 캘린더 (핵심 기능)
# ─────────────────────────────────────────────
with tab_calendar_view:
    st.subheader("🗓️ 학원별 개강 일정 캘린더 & 개강 타이밍 분석")
    st.caption("선택한 학원들의 개강 시작일을 달력과 타임라인으로 비교하여 경쟁사 개강 충돌일과 빈집(블루오션) 타이밍을 포착합니다.")

    cal_base_df = filtered_df.dropna(subset=["시작일_dt"]).copy()
    available_months = sorted(cal_base_df["개강월"].dropna().unique().tolist())

    if not available_months:
        st.warning("분석 가능한 개강일 데이터가 없습니다.")
    else:
        # 상단 컨트롤 바
        ctrl_c1, ctrl_c2, ctrl_c3 = st.columns([2, 2, 2])

        with ctrl_c1:
            cur_month_str = date.today().strftime("%Y-%m")
            default_m_idx = available_months.index(cur_month_str) if cur_month_str in available_months else (len(available_months) - 1)
            selected_month = st.selectbox(
                "📅 개강 연월 선택",
                options=available_months,
                index=default_m_idx,
                help="달력으로 확인할 개강 연월을 선택하세요.",
            )

        with ctrl_c2:
            view_mode = st.radio(
                "보기 방식",
                ["📅 월간 달력 그리드 뷰", "📊 간트 타임라인 (Gantt) 뷰"],
                index=0,
                horizontal=True,
            )

        with ctrl_c3:
            # 캘린더 내 추가 직종 필터
            cal_jobs = sorted([j for j in cal_base_df["직종명"].dropna().unique() if j])
            selected_cal_job = st.selectbox(
                "직종별 일정 필터",
                options=["전체 직종"] + cal_jobs,
                index=0,
            )

        # 캘린더 표시 대상 필터링
        cal_display_df = cal_base_df[cal_base_df["개강월"] == selected_month].copy()
        if selected_cal_job != "전체 직종":
            cal_display_df = cal_display_df[cal_display_df["직종명"] == selected_cal_job]

        # 학원별 색상 범례 (Legend) 표시
        st.markdown("##### 🏫 학원별 색상 범례")
        legend_cols = st.columns(min(len(selected_organs), 6))
        for idx, org in enumerate(selected_organs[:6]):
            st_style = get_organ_badge_style(org)
            with legend_cols[idx]:
                st.markdown(
                    f'<div style="background:{st_style["bg"]}; color:{st_style["text"]}; border:1px solid {st_style["border"]}; border-radius:6px; padding:4px 8px; font-size:0.75rem; font-weight:700; text-align:center; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="{org}">[{st_style["tag"]}] {org[:6]}</div>',
                    unsafe_allow_html=True,
                )

        if len(selected_organs) > 6:
            st.caption(f"외 {len(selected_organs) - 6}개 기관 추가 선택됨")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── 1. 월간 달력 그리드 뷰 ──
        if view_mode == "📅 월간 달력 그리드 뷰":
            y_str, m_str = selected_month.split("-")
            year_val, month_val = int(y_str), int(m_str)

            # 일자별 그룹화
            day_courses_map = {}
            for row in cal_display_df.itertuples():
                d_num = row.시작일_dt.day
                if d_num not in day_courses_map:
                    day_courses_map[d_num] = []
                day_courses_map[d_num].append(row)

            cal_obj = calendar.Calendar(firstweekday=6)  # 일요일 시작
            weeks = cal_obj.monthdayscalendar(year_val, month_val)

            cal_html = ['<div class="cal-container">']

            # 요일 헤더
            cal_html.append('<div class="cal-header-row">')
            days_header = [("일", "cal-header-sun"), ("월", ""), ("화", ""), ("수", ""), ("목", ""), ("금", ""), ("토", "cal-header-sat")]
            for dh, dh_cls in days_header:
                cal_html.append(f'<div class="cal-header-cell {dh_cls}">{dh}</div>')
            cal_html.append('</div>')

            # 주별 그리드 렌더링
            for week in weeks:
                cal_html.append('<div class="cal-grid-row">')
                for d in week:
                    if d == 0:
                        cal_html.append('<div class="cal-cell-empty"></div>')
                    else:
                        is_today = (date.today().year == year_val and date.today().month == month_val and date.today().day == d)
                        today_cls = "cal-cell-today" if is_today else ""

                        courses_on_day = day_courses_map.get(d, [])
                        cnt = len(courses_on_day)

                        cal_html.append(f'<div class="cal-cell {today_cls}">')
                        cal_html.append(f'<div class="cal-day-header">')
                        cal_html.append(f'<span class="cal-day-num">{d}일</span>')
                        if cnt > 0:
                            cal_html.append(f'<span class="cal-day-badge-cnt">{cnt}개</span>')
                        cal_html.append('</div>')

                        if cnt > 0:
                            # 2개 이상 학원이 동시 개강하는 경우 충돌 뱃지
                            orgs_on_day = set(getattr(c, "훈련기관명") for c in courses_on_day)
                            if len(orgs_on_day) >= 2:
                                cal_html.append(f'<div class="cal-pill-conflict">⚡ 동시 개강 ({len(orgs_on_day)}개 학원)</div>')

                            # 최대 4개 과정 표시
                            for c in courses_on_day[:4]:
                                org_name = getattr(c, "훈련기관명", "")
                                crs_name = getattr(c, "과정명", "")
                                reg_cnt = getattr(c, "등록인원", 0)
                                b_style = get_organ_badge_style(org_name)

                                full_title = f"[{org_name}] {crs_name} (등록 {reg_cnt}명)"
                                cal_html.append(
                                    f'<div class="cal-pill" style="background:{b_style["bg"]}; color:{b_style["text"]}; border-left-color:{b_style["border"]};" title="{full_title}">'
                                    f'[{b_style["tag"]}] {crs_name[:9]} ({reg_cnt}명)'
                                    f'</div>'
                                )

                            if cnt > 4:
                                cal_html.append(f'<div style="font-size:0.68rem; color:#64748b; font-weight:600; text-align:right;">+{cnt - 4}개 과정 더보기</div>')

                        cal_html.append('</div>')
                cal_html.append('</div>')

            cal_html.append('</div>')
            st.markdown("".join(cal_html), unsafe_allow_html=True)

            # ── 캘린더 아래 상세 일자 조회 ──
            st.markdown("#### 📌 일자별 개강 과정 상세 조회")
            days_with_courses = sorted(day_courses_map.keys())
            if days_with_courses:
                sel_day_c1, sel_day_c2 = st.columns([2, 4])
                with sel_day_c1:
                    chosen_day = st.selectbox(
                        "확인할 날짜 선택",
                        options=days_with_courses,
                        format_func=lambda d: f"{selected_month}-{d:02d} ({len(day_courses_map[d])}개 개강)",
                    )
                with sel_day_c2:
                    day_courses_list = day_courses_map[chosen_day]
                    orgs_that_day = list(set(getattr(c, "훈련기관명") for c in day_courses_list))
                    st.info(f"**{selected_month}-{chosen_day:02d}** 개강: 총 **{len(day_courses_list)}개** 과정 ({', '.join(get_short_inst_name(o) for o in orgs_that_day)})")

                day_detail_df = pd.DataFrame([
                    {
                        "훈련기관": getattr(c, "훈련기관명"),
                        "과정명": getattr(c, "과정명"),
                        "직종명": getattr(c, "직종명"),
                        "등록인원": getattr(c, "등록인원"),
                        "훈련시작일": getattr(c, "훈련시작일"),
                        "훈련종료일": getattr(c, "훈련종료일"),
                        "1인훈련비": getattr(c, "실제훈련비"),
                        "예상매출": getattr(c, "예상매출"),
                    }
                    for c in day_courses_map[chosen_day]
                ]).sort_values("등록인원", ascending=False)

                st.dataframe(
                    day_detail_df,
                    use_container_width=True,
                    height=260,
                    column_config={
                        "등록인원": st.column_config.NumberColumn("등록인원", format="%d 명"),
                        "1인훈련비": st.column_config.NumberColumn("1인 훈련비", format="%,d 원"),
                        "예상매출": st.column_config.NumberColumn("예상 매출", format="%,d 원"),
                    },
                )
            else:
                st.info("선택된 월에는 개강 과정이 없습니다.")

            st.divider()

            # ── 동시 개강 격전일 및 블루오션(빈집) 타이밍 분석 ──
            st.markdown("#### ⚡ 동시 개강 경쟁일 & 블루오션 타이밍 분석")
            conflict_days = [d for d in days_with_courses if len(set(getattr(c, "훈련기관명") for c in day_courses_map[d])) >= 2]

            ana_col1, ana_col2 = st.columns(2)
            with ana_col1:
                st.markdown("##### ⚔️ 경쟁사 동시 개강 격전일 (같은 날 개강 충돌)")
                if conflict_days:
                    for cd in conflict_days[:5]:
                        c_list = day_courses_map[cd]
                        c_orgs = list(set(getattr(c, "훈련기관명") for c in c_list))
                        org_tags = [f"`{get_short_inst_name(o)}`" for o in c_orgs]
                        st.warning(f"**{selected_month}-{cd:02d}** : 총 **{len(c_list)}개** 과정 동시 개강 ({', '.join(org_tags)})")
                else:
                    st.success("해당 월에는 선택한 학원 간의 동일 날짜 개강 충돌이 없습니다.")

            with ana_col2:
                st.markdown("##### 🌟 개강 빈집 타이밍 (경쟁사 개강이 적은 주차)")
                # 월 전체 날짜 중 개강이 0건인 평일(월~금) 탐색
                empty_weekdays = []
                for d in range(1, calendar.monthrange(year_val, month_val)[1] + 1):
                    dt_check = date(year_val, month_val, d)
                    if dt_check.weekday() < 5 and d not in day_courses_map:
                        empty_weekdays.append(d)

                if empty_weekdays:
                    sample_days = [f"{d}일" for d in empty_weekdays[:8]]
                    st.success(f"**경쟁사 개강 없는 평일**: {', '.join(sample_days)} 등 총 {len(empty_weekdays)}일\n\n💡 해당 시점에 미토 과정을 배치하면 경쟁사와의 직접적인 수강생 유치 충돌을 피할 수 있습니다.")
                else:
                    st.info("해당 월에는 대부분의 평일에 개강 일정이 잡혀 있습니다.")

        # ── 2. 간트 타임라인 (Gantt) 뷰 ──
        else:
            st.markdown("#### 📊 학원별 개강 일정 타임라인 (Gantt 차트)")
            timeline_df = cal_display_df.copy()
            timeline_df["종료일_dt"] = timeline_df["종료일_dt"].fillna(timeline_df["시작일_dt"] + pd.Timedelta(days=30))
            timeline_df["표시명"] = timeline_df["기관약칭"] + " - " + timeline_df["과정명"].str[:22]

            fig_timeline = px.timeline(
                timeline_df.sort_values(["시작일_dt", "훈련기관명"]),
                x_start="시작일_dt",
                x_end="종료일_dt",
                y="표시명",
                color="훈련기관명",
                text="등록인원",
                hover_name="과정명",
                hover_data={
                    "훈련기관명": True,
                    "직종명": True,
                    "등록인원": True,
                    "훈련시작일": True,
                    "훈련종료일": True,
                },
                labels={"표시명": "훈련과정", "훈련시작일": "시작일"},
                height=max(450, len(timeline_df) * 28),
            )
            fig_timeline.update_yaxes(autorange="reversed")
            fig_timeline.update_traces(texttemplate="%{text}명", textposition="inside")
            fig_timeline.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_timeline, use_container_width=True)

# ─────────────────────────────────────────────
# TAB 3: 인원수 기반 매출 분석 및 시뮬레이션
# ─────────────────────────────────────────────
with tab_revenue:
    st.subheader("💰 등록 인원수 기반 실제 매출 기여도 및 시뮬레이터")
    st.caption("실제 모은 인원수에 정부지원 훈련비를 곱한 정밀 실적입니다.")

    sim_col1, sim_col2 = st.columns([1, 1])

    with sim_col1:
        st.markdown("#### 🎛️ 수강생 인원 추가 시뮬레이터")
        add_per_course = st.slider(
            "과정당 추가 모집 인원 (명)",
            min_value=1,
            max_value=10,
            value=2,
            step=1,
            help="각 과정별로 수강생을 N명 더 모집했을 때 추가로 발생하는 정부지원 매출액을 산출합니다.",
        )

        sim_added_revenue = (filtered_df["실제훈련비"] * add_per_course).sum()

        st.metric(
            label=f"🚀 전 과정 평균 +{add_per_course}명 추가 모집 시 추가 매출",
            value=f"{sim_added_revenue / 1e8:.2f} 억원" if sim_added_revenue >= 1e8 else f"{sim_added_revenue / 1e4:,.0f} 만원",
            delta=f"현재 매출 대비 +{(sim_added_revenue / total_revenue * 100):.1f}% 상승" if total_revenue > 0 else None,
        )
        st.info(
            f"💡 현재 분석 중인 **{len(filtered_df):,}개 과정**에서 1개 과정당 단 **{add_per_course}명**만 더 모았을 경우 총 **{sim_added_revenue / 1e4:,.0f}만 원**의 매출이 추가 발생합니다."
        )

    with sim_col2:
        st.markdown("#### 🏆 등록인원 기준 매출 기여 TOP 10 과정")
        top_rev = filtered_df.sort_values("예상매출", ascending=False).head(10)
        if not top_rev.empty:
            fig_rev = px.bar(
                top_rev.sort_values("예상매출", ascending=True),
                x="예상매출",
                y="과정명",
                orientation="h",
                text="등록인원",
                color="예상매출",
                color_continuous_scale="Sunset",
                height=380,
            )
            fig_rev.update_traces(
                texttemplate="%{text}명 등록",
                textposition="outside",
            )
            fig_rev.update_layout(template="plotly_white", showlegend=False)
            st.plotly_chart(fig_rev, use_container_width=True)

# ─────────────────────────────────────────────
# TAB 4: 기관별 실제 모집력 비교 (누가 진짜 많이 모으나?)
# ─────────────────────────────────────────────
with tab_institution:
    st.subheader("🏫 훈련기관별 실제 수강생 모집력 랭킹")
    st.caption("선택한 학원들의 '실제 등록 인원수' 총합과 '과정당 평균 인원'으로 실제 모집 체급을 비교합니다.")

    org_agg = (
        filtered_df.groupby("훈련기관명")
        .agg(
            총등록인원=("등록인원", "sum"),
            개설과정수=("과정명", "count"),
            총예상매출=("예상매출", "sum"),
            평균만족도=("만족도점수", lambda x: x[x > 0].mean() if len(x[x > 0]) > 0 else 0.0),
        )
        .reset_index()
    )
    org_agg["과정당평균인원"] = (org_agg["총등록인원"] / org_agg["개설과정수"]).round(1)
    org_agg = org_agg.sort_values("총등록인원", ascending=False)

    col_org1, col_org2 = st.columns([1, 1])

    with col_org1:
        st.markdown("#### 🥧 훈련생 총 등록 점유율")
        top_orgs_pie = org_agg.head(8).copy()
        other_sum = org_agg.iloc[8:]["총등록인원"].sum() if len(org_agg) > 8 else 0
        if other_sum > 0:
            top_orgs_pie = pd.concat(
                [
                    top_orgs_pie,
                    pd.DataFrame([{"훈련기관명": "기타 기관 합계", "총등록인원": other_sum}]),
                ],
                ignore_index=True,
            )
        fig_pie = px.pie(
            top_orgs_pie,
            names="훈련기관명",
            values="총등록인원",
            hole=0.4,
            height=380,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_org2:
        st.markdown("#### ⚡ 기관별 과정당 평균 모집 인원 비교")
        top_avg_orgs = org_agg.sort_values("과정당평균인원", ascending=False).head(10)
        fig_avg = px.bar(
            top_avg_orgs,
            x="훈련기관명",
            y="과정당평균인원",
            text="과정당평균인원",
            color="과정당평균인원",
            color_continuous_scale="Purples",
            height=380,
        )
        fig_avg.update_traces(texttemplate="%{text:.1f}명", textposition="outside")
        fig_avg.update_layout(template="plotly_white")
        st.plotly_chart(fig_avg, use_container_width=True)

    st.markdown("#### 📋 기관별 실제 모집 실적 비교표")
    st.dataframe(
        org_agg,
        use_container_width=True,
        height=320,
        column_config={
            "총등록인원": st.column_config.NumberColumn("총 등록인원", format="%d 명"),
            "과정당평균인원": st.column_config.NumberColumn("과정당 평균 모집", format="%.1f 명"),
            "총예상매출": st.column_config.NumberColumn("총 예상 매출", format="%,d 원"),
            "평균만족도": st.column_config.NumberColumn("평균 만족도", format="%.2f 점"),
        },
    )

# ─────────────────────────────────────────────
# TAB 5: 상세 통합 데이터 및 엑셀 다운로드
# ─────────────────────────────────────────────
with tab_data:
    st.subheader("📋 전체 과정 상세 실적표 (등록인원 순)")

    st.dataframe(
        filtered_df.sort_values("등록인원", ascending=False)[
            [
                "훈련기관명",
                "과정명",
                "직종명",
                "등록인원",
                "인원구분",
                "훈련시작일",
                "훈련종료일",
                "실제훈련비",
                "예상매출",
                "만족도점수",
            ]
        ],
        use_container_width=True,
        height=450,
        column_config={
            "등록인원": st.column_config.NumberColumn("실제 등록인원", format="%d 명"),
            "실제훈련비": st.column_config.NumberColumn("실제훈련비", format="%,d 원"),
            "예상매출": st.column_config.NumberColumn("예상매출", format="%,d 원"),
        },
    )

    st.divider()

    col_down1, col_down2 = st.columns([2, 1])
    with col_down1:
        st.write("📊 분석된 전체 데이터를 엑셀로 다운로드하여 내부 보고 및 기획 자료로 활용하세요.")
    with col_down2:
        bi_excel = to_excel_bi(filtered_df)
        st.download_button(
            label="📥 인원 중심 분석 엑셀 다운로드",
            data=bi_excel,
            file_name=f"과거훈련실적_경영분석_{date.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
