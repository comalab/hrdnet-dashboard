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
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="bi-header">📊 훈련과정 경영 전략 대시보드 <span class="beta-badge">BETA</span></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="bi-subheader">실제 등록 인원수 중심의 시장 규모, 직종별 수요 볼륨, 개강 완료 실적 및 예상 매출 분석</div>',
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────
# 데이터 정제 및 파생변수 생성 함수
# (오늘 포함 과거 실적 & 절대 인원수 중심)
# ─────────────────────────────────────────────
def prepare_bi_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    """실제 등록인원수와 매출 중심의 지표 계산"""
    df = raw_df.copy()

    # 구버전 컬럼명 호환
    if "수강신청인원" in df.columns and "등록인원" not in df.columns:
        df["등록인원"] = df["수강신청인원"]

    # 필수 컬럼 기본값 처리
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

    # 수치형 변환
    df["등록인원"] = pd.to_numeric(df["등록인원"], errors="coerce").fillna(0).astype(int)
    df["실제훈련비"] = pd.to_numeric(df["실제훈련비"], errors="coerce").fillna(0)
    df["수강비"] = pd.to_numeric(df["수강비"], errors="coerce").fillna(0)
    df["만족도점수"] = pd.to_numeric(df["만족도점수"], errors="coerce").fillna(0.0)

    # 1. 예상 매출 (실제 등록인원 × 1인당 실제훈련비)
    df["예상매출"] = df["등록인원"] * df["실제훈련비"]

    # 2. 날짜 및 개강월 계산
    today = date.today()
    df["시작일_dt"] = pd.to_datetime(df["훈련시작일"], errors="coerce")
    df["개강월"] = df["시작일_dt"].dt.strftime("%Y-%m")

    def calc_dday(dt):
        if pd.isna(dt):
            return None
        return (dt.date() - today).days

    df["D-Day"] = df["시작일_dt"].apply(calc_dday)

    # 3. 절대 인원수 기반 개강 실적 구분
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
# 사이드바: 1) 검색 조건 (오늘 포함 과거 데이터 전용)
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

            # 날짜 컬럼 정리
            for col in ["훈련시작일", "훈련종료일"]:
                if col in new_df.columns:
                    new_df[col] = pd.to_datetime(new_df[col], errors="coerce").dt.strftime("%Y-%m-%d")

            # ★ 오늘 포함 과거 데이터만 엄격하게 필터링 (미래 미개강 과정 제외) ★
            new_df["_start_date_obj"] = pd.to_datetime(new_df["훈련시작일"], errors="coerce").dt.date
            new_df = new_df[new_df["_start_date_obj"] <= end_date_input].drop(columns=["_start_date_obj"])

            # 숫자 컬럼 변환
            for col in ["수강비", "실제훈련비", "정원", "등록인원"]:
                if col in new_df.columns:
                    new_df[col] = pd.to_numeric(new_df[col], errors="coerce")

            # NCS코드 -> 직종명 매핑
            if "NCS코드" in new_df.columns:
                new_df["직종명"] = new_df["NCS코드"].apply(map_ncs_code)

            # 세션 공유 (01_hrdnet.py와 양방향 공유)
            st.session_state.df = new_df
            st.session_state.bi_df = prepare_bi_data(new_df)
            st.session_state.current_source = "searched"
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
        st.success(
            f"🔗 **[HRD-Net 대시보드]** 에서 조회된 **{len(active_df):,}건**의 데이터와 연동 중입니다."
        )
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
                st.toast("업로드된 엑셀 적용 완료!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"파싱 실패: {e}")

# 데이터가 아직 없는 경우 기본 저장 파일 자동 로드 시도
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
# 사이드바 하단: 세부 필터 (0명 제외 및 과거 필터 추가)
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🎯 인원 분석 필터")

    # 1. 모집인원 0명 제외 선택 옵션
    exclude_zero = st.toggle(
        "🚫 모집인원 0명 과정 제외",
        value=True,
        help="등록인원이 0명인 과정(미개설/폐강 등)을 제외하고 실제 인원이 모집된 과정만 분석합니다.",
    )

    # 2. 오늘 포함 과거 데이터만 보기 토글 (업로드/샘플 데이터 대비)
    past_only = st.toggle(
        "📅 오늘 이전 개강 과정만 보기",
        value=True,
        help="개강일이 오늘 이전인 실제 개강 과정만 필터링합니다.",
    )

    all_organs = sorted(df["훈련기관명"].dropna().unique().tolist())
    is_mito_present = any("미토" in o for o in all_organs)

    # 3. 미토 집중 분석 토글
    focus_mito = st.toggle("🏫 미토직업전문학교만 집중 분석", value=False) if is_mito_present else False

    filtered_df = df.copy()

    # 필터 적용 1: 과거 개강 과정
    if past_only:
        filtered_df = filtered_df[filtered_df["시작일_dt"].dt.date <= date.today()]

    # 필터 적용 2: 모집인원 0명 제외
    if exclude_zero:
        filtered_df = filtered_df[filtered_df["등록인원"] > 0]

    # 필터 적용 3: 기관 선택
    if focus_mito:
        filtered_df = filtered_df[filtered_df["훈련기관명"].str.contains("미토", na=False)]
    else:
        selected_organs = st.multiselect(
            "훈련기관 필터",
            options=all_organs,
            default=[],
            placeholder="전체 기관",
        )
        if selected_organs:
            filtered_df = filtered_df[filtered_df["훈련기관명"].isin(selected_organs)]

    # 필터 적용 4: 직종(NCS)
    all_jobs = sorted([j for j in filtered_df["직종명"].dropna().unique() if j])
    selected_jobs = st.multiselect(
        "직종(NCS) 필터",
        options=all_jobs,
        default=[],
        placeholder="전체 직종",
    )
    if selected_jobs:
        filtered_df = filtered_df[filtered_df["직종명"].isin(selected_jobs)]

    # 필터 적용 5: 인원수 구간
    all_statuses = sorted(filtered_df["인원구분"].dropna().unique().tolist())
    selected_statuses = st.multiselect(
        "등록 인원수 구간",
        options=all_statuses,
        default=[],
        placeholder="전체 구간",
    )
    if selected_statuses:
        filtered_df = filtered_df[filtered_df["인원구분"].isin(selected_statuses)]

    st.caption(f"분석 대상: **{len(filtered_df):,}건** / 원본 {len(df):,}건")

# 필터링 후 데이터가 없는 경우 처리
if filtered_df.empty:
    st.warning("⚠️ 선택하신 조건에 부합하는 과정이 없습니다. '모집인원 0명 제외' 토글이나 세부 필터를 조정해보세요.")
    st.stop()

# ─────────────────────────────────────────────
# 1. 상단 핵심 경영 KPI 요약 (실제 인원수 기준)
# ─────────────────────────────────────────────
total_courses = len(filtered_df)
total_registered = filtered_df["등록인원"].sum()
avg_registered_per_course = (total_registered / total_courses) if total_courses > 0 else 0.0
total_revenue = filtered_df["예상매출"].sum()

low_enroll_courses = len(
    filtered_df[(filtered_df["등록인원"] > 0) & (filtered_df["등록인원"] <= 5)]
)

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric(
        label="👥 총 등록 인원수 (Total)",
        value=f"{total_registered:,}명",
        delta=f"개설 과정 {total_courses:,}개",
        help="선택된 범위 내에서 실제로 모집/등록된 수강생의 총합입니다.",
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
tab_job_volume, tab_timing, tab_revenue, tab_institution, tab_data = st.tabs(
    [
        "🏆 [직종 규모] 직종별 실제 등록인원수",
        "🗓️ [개강 실적] 월별 개강 추이 & 현황",
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
    st.caption("정원과 무관하게, 실제로 가장 많은 수강생이 등록한 시장 수요 중심 직종을 파악합니다.")

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
            st.caption("조건에 부합하는 직종이 없습니다.")

    st.divider()

    st.markdown("#### 📌 직종별 수강생 유입 규모 요약")
    if not job_agg.empty:
        c_top1 = job_agg.iloc[0]
        st.info(
            f"현재 가장 수강생이 많은 1위 직종은 **`{c_top1['직종명']}`** (총 **{c_top1['총등록인원']:,}명**, 과정 {c_top1['개설과정수']}개)이며, "
            f"과정당 평균 **{c_top1['과정당평균인원']}명**이 등록되었습니다."
        )

# ─────────────────────────────────────────────
# TAB 2: 개강 실적 및 월별 추이 모니터링
# ─────────────────────────────────────────────
with tab_timing:
    st.subheader("🗓️ 월별 개강 추이 & 실제 개강 과정 현황")
    st.caption("월별 개강된 과정 수 및 실제 등록 인원수 규모를 비교 분석합니다.")

    valid_dates_df = filtered_df.dropna(subset=["시작일_dt"]).copy()
    if not valid_dates_df.empty:
        monthly_df = (
            valid_dates_df.groupby("개강월")
            .agg(총등록인원=("등록인원", "sum"), 개설과정수=("과정명", "count"))
            .reset_index()
            .sort_values("개강월")
        )
        fig_month = px.bar(
            monthly_df,
            x="개강월",
            y="총등록인원",
            text="총등록인원",
            color="총등록인원",
            color_continuous_scale="Purples",
            title="월별 실제 등록 훈련생 합계 (명)",
            height=340,
        )
        fig_month.update_traces(texttemplate="%{text:,}명", textposition="outside")
        fig_month.update_layout(template="plotly_white")
        st.plotly_chart(fig_month, use_container_width=True)

    st.subheader("📋 최근 개강 과정 실적 현황 (최신순)")
    recent_opened_df = (
        filtered_df.sort_values("훈련시작일", ascending=False)
        .copy()
    )

    if not recent_opened_df.empty:
        st.dataframe(
            recent_opened_df[
                [
                    "훈련기관명",
                    "과정명",
                    "직종명",
                    "훈련시작일",
                    "등록인원",
                    "인원구분",
                    "실제훈련비",
                    "예상매출",
                ]
            ],
            use_container_width=True,
            height=380,
            column_config={
                "등록인원": st.column_config.NumberColumn("실제 등록인원", format="%d 명"),
                "실제훈련비": st.column_config.NumberColumn("1인 훈련비", format="%,d 원"),
                "예상매출": st.column_config.NumberColumn("예상 매출", format="%,d 원"),
            },
        )

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
    st.caption("정원이 아닌 '실제 등록 인원수' 총합과 '과정당 평균 인원'으로 각 학원의 실제 모집 체급을 비교합니다.")

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
        top_avg_orgs = org_agg[org_agg["개설과정수"] >= 2].sort_values("과정당평균인원", ascending=False).head(10)
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
