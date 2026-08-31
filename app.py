import streamlit as st
import pandas as pd

# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="WorkBridge AI",
    page_icon="🏢",
    layout="wide"
)

st.title("🏢 WorkBridge AI")
st.caption("설계 엔지니어링 업무의 단계 간 지식 인수인계 지원 시스템")

# =========================================================
# Excel 불러오기
# =========================================================

FILE_NAME = "handover_data.xlsx"


@st.cache_data
def load_data():

    sheets = pd.read_excel(
        FILE_NAME,
        sheet_name=None
    )

    return sheets


try:
    data = load_data()

except Exception as e:

    st.error("❌ Excel 파일을 불러오지 못했습니다.")

    st.info(
        "GitHub 저장소에 handover_data.xlsx 파일이 있는지 확인해주세요."
    )

    st.stop()


# =========================================================
# 데이터 준비
# =========================================================

knowledge = data.get("02_단계별지식", pd.DataFrame())
handover = data.get("03_인수인계연결", pd.DataFrame())
missing = data.get("04_누락탐지", pd.DataFrame())
terms = data.get("05_용어_전공지식", pd.DataFrame())
checklist = data.get("09_인수인계체크리스트", pd.DataFrame())
scenarios = data.get("10_대회시연시나리오", pd.DataFrame())
project = data.get("00_프로젝트개요", pd.DataFrame())


# =========================================================
# 프로젝트 정보
# =========================================================

st.sidebar.header("📁 프로젝트")

project_name = "2026 그린리모델링 가상 프로젝트"

if not project.empty:

    try:
        project_dict = dict(
            zip(
                project.iloc[:, 0],
                project.iloc[:, 1]
            )
        )

        project_name = project_dict.get(
            "프로젝트명",
            project_name
        )

    except Exception:
        pass


st.sidebar.success(project_name)

# =========================================================
# 메뉴
# =========================================================

menu = st.sidebar.radio(
    "메뉴",
    [
        "🏠 대시보드",
        "🔎 업무 지식 검색",
        "🔗 단계 연결",
        "⚠️ 누락정보 탐지",
        "📋 인수인계 체크리스트",
        "📖 용어/전공지식",
        "🎬 대회 시연"
    ]
)


# =========================================================
# 공통 함수
# =========================================================

def safe_text(value):

    if pd.isna(value):
        return ""

    return str(value)


def find_knowledge(keyword):

    if knowledge.empty:
        return pd.DataFrame()

    keyword = keyword.lower()

    mask = knowledge.apply(
        lambda row:
        keyword in " ".join(
            safe_text(x).lower()
            for x in row
        ),
        axis=1
    )

    return knowledge[mask]


# =========================================================
# 1. 대시보드
# =========================================================

if menu == "🏠 대시보드":

    st.header("📊 인수인계 대시보드")

    st.write(
        "그린리모델링 프로젝트의 업무 지식과 "
        "단계 간 인수인계 상태를 한 화면에서 확인합니다."
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "업무 지식",
            f"{len(knowledge)}건"
        )

    with col2:
        st.metric(
            "인수인계 연결",
            f"{len(handover)}건"
        )

    with col3:
        st.metric(
            "누락 정보",
            f"{len(missing)}건"
        )

    with col4:
        st.metric(
            "체크리스트",
            f"{len(checklist)}건"
        )

    st.divider()

    st.subheader("🔄 업무 지식 흐름")

    st.info(
        "현황·노후진단  →  개선안·설계  →  시공·검증  →  인수인계"
    )

    st.divider()

    st.subheader("💡 시스템 핵심 기능")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            """
            ### 🔎 지식 검색

            업무명이나 설비명을 검색하여
            관련 업무 지식을 확인합니다.
            """
        )

    with c2:
        st.markdown(
            """
            ### 🔗 단계 연결

            이전 단계의 판단이
            다음 단계에서 어떻게 이어지는지 확인합니다.
            """
        )

    with c3:
        st.markdown(
            """
            ### ⚠️ 누락 탐지

            인수인계 과정에서 빠진 정보를
            자동으로 확인합니다.
            """
        )


# =========================================================
# 2. 업무 지식 검색
# =========================================================

elif menu == "🔎 업무 지식 검색":

    st.header("🔎 업무 지식 검색")

    keyword = st.text_input(
        "업무, 설비, 용어 등을 입력하세요",
        placeholder="예: 냉난방 / 환기 / 냉동기 / 창호"
    )

    if keyword:

        result = find_knowledge(keyword)

        st.write(
            f"검색 결과: **{len(result)}건**"
        )

        if result.empty:

            st.warning(
                "관련 업무 지식을 찾지 못했습니다."
            )

        else:

            for _, row in result.iterrows():

                knowledge_id = safe_text(
                    row.get("Knowledge_ID", "")
                )

                title = safe_text(
                    row.get("업무", "")
                )

                with st.expander(
                    f"📌 {knowledge_id} | {title}"
                ):

                    st.markdown("### 📋 현재 상황")

                    st.write(
                        safe_text(
                            row.get("입력/현황(가상)", "")
                        )
                    )

                    st.markdown("### 💡 판단 / 결정")

                    st.write(
                        safe_text(
                            row.get("판단/결정(가상)", "")
                        )
                    )

                    st.markdown("### 🧠 판단근거")

                    st.info(
                        safe_text(
                            row.get("판단근거(가상)", "")
                        )
                    )

                    st.markdown("### ➡️ 다음 단계에 전달할 지식")

                    st.write(
                        safe_text(
                            row.get(
                                "다음 단계에 전달할 지식",
                                ""
                            )
                        )
                    )

                    st.markdown("### ⚠️ 인수인계 누락정보")

                    missing_text = safe_text(
                        row.get(
                            "인수인계 누락정보(가상)",
                            ""
                        )
                    )

                    if missing_text:
                        st.warning(missing_text)
                    else:
                        st.success(
                            "현재 기록된 누락정보가 없습니다."
                        )


# =========================================================
# 3. 단계 연결
# =========================================================

elif menu == "🔗 단계 연결":

    st.header("🔗 단계 간 지식 연결")

    st.write(
        "선행 업무의 판단이 다음 업무로 어떻게 전달되는지 확인합니다."
    )

    if not handover.empty:

        for _, row in handover.iterrows():

            from_id = safe_text(
                row.get("From_Knowledge_ID", "")
            )

            to_id = safe_text(
                row.get("To_Knowledge_ID", "")
            )

            section = safe_text(
                row.get("인수인계 구간", "")
            )

            with st.expander(
                f"🔗 {from_id} → {to_id} | {section}"
            ):

                st.markdown("### 이전 단계의 핵심 판단")

                st.write(
                    safe_text(
                        row.get(
                            "이전 단계의 핵심 판단",
                            ""
                        )
                    )
                )

                st.markdown("### 다음 단계에 전달할 핵심 지식")

                st.info(
                    safe_text(
                        row.get(
                            "다음 단계에 전달할 핵심 지식",
                            ""
                        )
                    )
                )

                st.markdown("### 필요한 자료")

                st.write(
                    safe_text(
                        row.get("필요 자료", "")
                    )
                )

                st.markdown("### 🤖 AI 활용 예")

                st.success(
                    safe_text(
                        row.get("AI 활용 예", "")
                    )
                )


# =========================================================
# 4. 누락정보 탐지
# =========================================================

elif menu == "⚠️ 누락정보 탐지":

    st.header("⚠️ 인수인계 누락정보 탐지")

    st.write(
        "후임자가 업무를 이어받기 전에 "
        "추가로 확인해야 할 정보를 보여줍니다."
    )

    if not missing.empty:

        priority = st.selectbox(
            "우선도",
            ["전체", "높음", "중간", "낮음"]
        )

        result = missing.copy()

        if priority != "전체":

            result = result[
                result["우선도"].astype(str) == priority
            ]

        st.metric(
            "확인 필요 항목",
            f"{len(result)}건"
        )

        for _, row in result.iterrows():

            p = safe_text(
                row.get("우선도", "")
            )

            if p == "높음":
                st.error(
                    f"🔴 높은 우선도 | "
                    f"{safe_text(row.get('Knowledge_ID', ''))}"
                )

            elif p == "중간":
                st.warning(
                    f"🟡 중간 우선도 | "
                    f"{safe_text(row.get('Knowledge_ID', ''))}"
                )

            else:
                st.info(
                    f"🟢 낮은 우선도 | "
                    f"{safe_text(row.get('Knowledge_ID', ''))}"
                )

            st.write(
                safe_text(
                    row.get(
                        "AI가 발견한 문제(가상)",
                        ""
                    )
                )
            )

            st.caption(
                "추가 기록 필요: "
                + safe_text(
                    row.get(
                        "추가로 기록할 정보",
                        ""
                    )
                )
            )

            st.divider()


# =========================================================
# 5. 체크리스트
# =========================================================

elif menu == "📋 인수인계 체크리스트":

    st.header("📋 인수인계 체크리스트")

    st.write(
        "후임자가 업무를 넘겨받기 전에 확인해야 할 항목입니다."
    )

    if not checklist.empty:

        for _, row in checklist.iterrows():

            item = safe_text(
                row.get("체크 항목", "")
            )

            status = safe_text(
                row.get("현재 상태(가상)", "")
            )

            required = safe_text(
                row.get("필수 여부", "")
            )

            st.markdown(
                f"### 📌 {item}"
            )

            c1, c2 = st.columns(2)

            with c1:

                if status == "미입력":
                    st.error("❌ 미입력")
                else:
                    st.success("✅ 입력됨")

            with c2:

                st.write(
                    f"필수 여부: **{required}**"
                )

            st.caption(
                safe_text(
                    row.get(
                        "AI 판정 예시",
                        ""
                    )
                )

            st.divider()


# =========================================================
# 6. 용어 / 전공지식
# =========================================================

elif menu == "📖 용어/전공지식":

    st.header("📖 표준 용어 / 전공지식 검색")

    keyword = st.text_input(
        "용어를 검색하세요",
        placeholder="예: U-value / 냉난방 / 환기"
    )

    if keyword and not terms.empty:

        keyword = keyword.lower()

        result = terms[
            terms.apply(
                lambda row:
                keyword in " ".join(
                    safe_text(x).lower()
                    for x in row
                ),
                axis=1
            )
        ]

        if result.empty:

            st.warning(
                "관련 용어를 찾지 못했습니다."
            )

        else:

            for _, row in result.iterrows():

                st.subheader(
                    safe_text(
                        row.get(
                            "표준 용어",
                            ""
                        )
                    )
                )

                st.write(
                    safe_text(
                        row.get(
                            "설명(프로토타입용)",
                            ""
                        )
                    )
                )

                st.caption(
                    "관련 분야: "
                    + safe_text(
                        row.get(
                            "관련 분야",
                            ""
                        )
                    )
                )


# =========================================================
# 7. 대회 시연
# =========================================================

elif menu == "🎬 대회 시연":

    st.header("🎬 대회 시연 모드")

    st.write(
        "실제 발표 상황에서 사용할 수 있는 대표 시나리오입니다."
    )

    if not scenarios.empty:

        for _, row in scenarios.iterrows():

            scenario = safe_text(
                row.get("Scenario", "")
            )

            situation = safe_text(
                row.get("상황", "")
            )

            question = safe_text(
                row.get("사용자 질문", "")
            )

            ai_action = safe_text(
                row.get("AI가 해야 할 일", "")
            )

            evaluation = safe_text(
                row.get("평가 포인트", "")
            )

            with st.expander(
                f"🎯 {scenario} | {question}"
            ):

                st.markdown("### 상황")

                st.write(situation)

                st.markdown("### 👤 사용자 질문")

                st.info(question)

                st.markdown("### 🤖 시스템이 해야 할 일")

                st.write(ai_action)

                st.markdown("### 🏆 평가 포인트")

                st.success(evaluation)


# =========================================================
# Footer
# =========================================================

st.divider()

st.caption(
    "WorkBridge AI | Green Remodeling Knowledge Handover Prototype"
)

st.caption(
    "※ 본 시스템의 프로젝트 및 업무 데이터는 프로토타입용 가상 데이터입니다."
)
