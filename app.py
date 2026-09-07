import streamlit as st

st.set_page_config(
    page_title="훈련과정 통합 대시보드",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


def check_password() -> bool:
    """secrets.toml에 APP_PASSWORD가 설정되어 있으면 비밀번호 입력을 요구한다."""
    try:
        app_password = st.secrets.get("APP_PASSWORD")
    except Exception:
        app_password = None

    if not app_password:
        # 비밀번호가 설정되지 않은 경우(로컬 개발 등) 그대로 통과시킨다.
        return True

    if st.session_state.get("authenticated"):
        return True

    def on_submit():
        if st.session_state.get("password_input") == app_password:
            st.session_state["authenticated"] = True
        else:
            st.session_state["authenticated"] = False
        st.session_state["password_input"] = ""

    st.markdown("## 🔒 접속 비밀번호를 입력하세요")
    st.text_input("비밀번호", type="password", key="password_input", on_change=on_submit)
    if st.session_state.get("authenticated") is False:
        st.error("비밀번호가 올바르지 않습니다.")
    return False


if not check_password():
    st.stop()

pg = st.navigation([
    st.Page("pages/01_hrdnet.py",  title="HRD-Net 대시보드",   icon="🎓"),
    st.Page("pages/02_worknet.py", title="고용24 키워드 검색", icon="🔍"),
])
pg.run()