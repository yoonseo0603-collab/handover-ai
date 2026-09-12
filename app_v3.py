import streamlit as st
import pandas as pd
from pathlib import Path

# Gemini
try:
    from google import genai
except Exception:
    genai = None


# =========================================================
# 기본 설정
# =========================================================

st.set_page_config(
    page_title="WorkBridge AI",
    page_icon="🏢",
    layout="wide"
)

# =========================================================
# Excel 프로젝트 파일 업로드
# =========================================================

st.sidebar.header("📁 프로젝트 파일")

uploaded_file = st.sidebar.file_uploader(
    "프로젝트 Excel 파일 업로드",
    type=["xlsx"],
    help="WorkBridge AI 형식의 프로젝트 Excel 파일을 업로드하세요."
)

if uploaded_file is None:
    st.info("👈 왼쪽 사이드바에서 프로젝트 Excel 파일을 업로드해주세요.")
    st.caption("예: 2026_그린리모델링_가상프로젝트_단계간_지식인수인계_V2_대회용.xlsx")
    st.stop()

@st.cache_data
def load_uploaded_data(file_bytes):
    from io import BytesIO
    return pd.read_excel(BytesIO(file_bytes), sheet_name=None)

try:
    data = load_uploaded_data(uploaded_file.getvalue())
except Exception as e:
    st.error("❌ Excel 파일을 읽지 못했습니다.")
    st.code(str(e))
    st.stop()


# =========================================================
# Excel 시트 연결
# =========================================================

project = data.get(
    "00_프로젝트개요",
    pd.DataFrame()
)

knowledge = data.get(
    "02_단계별지식",
    pd.DataFrame()
)

handover = data.get(
    "03_인수인계연결",
    pd.DataFrame()
)

missing = data.get(
    "04_누락탐지",
    pd.DataFrame()
)

checklist = data.get(
    "09_인수인계체크리스트",
    pd.DataFrame()
)

stage_map = data.get(
    "08_단계연결맵",
    pd.DataFrame()
)


# =========================================================
# 공통 함수
# =========================================================

def safe_text(value):

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value)


def get_project_name():

    if project.empty:
        return "○○시 중앙도서관 그린리모델링(가상)"

    try:

        for _, row in project.iterrows():

            key = safe_text(row.iloc[0])

            value = safe_text(row.iloc[1])

            if key == "프로젝트명":
                return value

    except Exception:
        pass

    return "○○시 중앙도서관 그린리모델링(가상)"


PROJECT_NAME = get_project_name()


def row_to_text(row):

    result = []

    for column in row.index:

        value = safe_text(row[column])

        if value:

            result.append(
                f"{column}: {value}"
            )

    return " | ".join(result)


# =========================================================
# 질문과 관련된 Knowledge 찾기
# =========================================================

def search_knowledge(question, top_n=6):

    if knowledge.empty:
        return pd.DataFrame()

    question = safe_text(question).lower()

    # 질문에서 간단한 키워드 추출
    keywords = []

    for word in question.split():

        word = word.strip(
            ".,!?/()[]"
        )

        if len(word) >= 2:
            keywords.append(word)

    scores = []

    for _, row in knowledge.iterrows():

        text = row_to_text(row).lower()

        score = 0

        for keyword in keywords:

            if keyword in text:
                score += 1

        # 냉난방 관련 질문
        if any(
            word in question
            for word in [
                "냉방",
                "냉난방",
                "냉동기",
                "장비"
            ]
        ):

            if any(
                word in text
                for word in [
                    "냉난방",
                    "냉동",
                    "장비"
                ]
            ):

                score += 3

        # 환기 관련 질문
        if "환기" in question:

            if "환기" in text:
                score += 3

        # 외벽/창호/단열 관련 질문
        if any(
            word in question
            for word in [
                "외벽",
                "창호",
                "단열",
                "외피"
            ]
        ):

            if any(
                word in text
                for word in [
                    "외벽",
                    "창호",
                    "단열",
                    "외피"
                ]
            ):

                score += 3

        scores.append(score)

    result = knowledge.copy()

    result["_score"] = scores

    result = result.sort_values(
        "_score",
        ascending=False
    )

    # 관련 자료가 하나도 없으면 앞쪽 핵심 자료 사용
    if result["_score"].max() == 0:

        result = result.head(top_n)

    else:

        result = result[
            result["_score"] > 0
        ].head(top_n)

    return result.drop(
        columns=["_score"],
        errors="ignore"
    )


# =========================================================
# Gemini에게 전달할 프로젝트 정보 만들기
# =========================================================

def build_context(question):

    selected = search_knowledge(
        question,
        top_n=6
    )

    context = []

    # 프로젝트
    context.append(
        "===== 프로젝트 개요 ====="
    )

    if not project.empty:

        for _, row in project.iterrows():

            context.append(
                row_to_text(row)
            )

    # 단계별 지식
    context.append(
        "\n===== 관련 단계별 지식 ====="
    )

    if selected.empty:

        context.append(
            "관련 지식 없음"
        )

    else:

        for _, row in selected.iterrows():

            context.append(
                row_to_text(row)
            )

    # 인수인계 연결
    context.append(
        "\n===== 인수인계 연결 ====="
    )

    if not handover.empty:

        selected_ids = set()

        if "Knowledge_ID" in selected.columns:

            selected_ids = set(
                selected["Knowledge_ID"]
                .astype(str)
            )

        for _, row in handover.iterrows():

            from_id = safe_text(
                row.get(
                    "From_Knowledge_ID",
                    ""
                )
            )

            to_id = safe_text(
                row.get(
                    "To_Knowledge_ID",
                    ""
                )
            )

            if (
                not selected_ids
                or from_id in selected_ids
                or to_id in selected_ids
            ):

                context.append(
                    row_to_text(row)
                )

    # 누락 정보
    context.append(
        "\n===== 누락 정보 ====="
    )

    if not missing.empty:

        for _, row in missing.iterrows():

            context.append(
                row_to_text(row)
            )

    # 체크리스트
    context.append(
        "\n===== 인수인계 체크리스트 ====="
    )

    if not checklist.empty:

        for _, row in checklist.iterrows():

            context.append(
                row_to_text(row)
            )

    return "\n".join(context)


# =========================================================
# Gemini 설정
# =========================================================

SYSTEM_INSTRUCTION = """
당신은 설계 엔지니어링 프로젝트의
'지식 인수인계 AI'입니다.

사용자가 프로젝트를 처음 맡은 후임 엔지니어라고 생각하고
이전 담당자의 판단과 업무 정보를 이해하기 쉽게 설명하세요.

반드시 제공된 프로젝트 데이터만 근거로 답하세요.

데이터에 없는 내용을 임의로 만들어내지 마세요.

확인할 수 없는 내용은
'확인 필요'라고 표시하세요.

특히 다음 5가지를 중요하게 설명하세요.

1. 현재 상황
2. 선임자의 판단
3. 판단 근거
4. 아직 확인하지 않은 정보
5. 다음 담당자가 해야 할 일

가능하면 Knowledge_ID와 이전/다음 단계의 연결도 설명하세요.

단순한 전공지식 설명보다
'이 프로젝트에서 후임자가 무엇을 확인하고
어떤 업무를 이어서 해야 하는가'
를 중심으로 답변하세요.

답변 형식:

### ① 현재 상황

### ② 선임자의 판단

### ③ 판단 근거

### ④ ⚠️ 아직 확인할 정보

### ⑤ ➡️ 다음 담당자가 할 일

### ⑥ 🔗 이전 단계와의 연결
"""


def ask_gemini(question, context):

    if genai is None:

        return None

    try:

        api_key = st.secrets[
            "GEMINI_API_KEY"
        ]

    except Exception:

        return None

    try:

        client = genai.Client(
            api_key=api_key
        )

        prompt = f"""
[프로젝트 인수인계 데이터]

{context}


[후임자의 질문]

{question}


위 프로젝트 데이터만 근거로
인수인계 관점에서 답변하세요.
"""

        response = client.models.generate_content(

            model="gemini-3.6-flash",

            contents=prompt,

            config={
                "system_instruction":
                    SYSTEM_INSTRUCTION
            }
        )

        return response.text

    except Exception:

        return None


# =========================================================
# Gemini가 없어도 작동하는 기본 답변
# =========================================================

def local_answer(question):

    selected = search_knowledge(
        question,
        top_n=5
    )

    if selected.empty:

        return """
### ① 현재 상황

관련 프로젝트 데이터를 찾지 못했습니다.

### ② 선임자의 판단

확인 필요

### ③ 판단 근거

확인 필요

### ④ ⚠️ 아직 확인할 정보

업무명이나 설비명을 조금 더 구체적으로 입력해주세요.

### ⑤ ➡️ 다음 담당자가 할 일

프로젝트의 단계별 지식과 누락정보를 확인하세요.
"""


    answer = []


    # 현재 상황
    answer.append(
        "### ① 현재 상황"
    )

    items = []

    for _, row in selected.iterrows():

        value = safe_text(
            row.get(
                "입력/현황(가상)",
                ""
            )
        )

        if value:
            items.append(
                f"- {value}"
            )

    answer.append(
        "\n".join(items[:5])
        if items
        else "- 확인 필요"
    )


    # 판단
    answer.append(
        "\n### ② 선임자의 판단"
    )

    items = []

    for _, row in selected.iterrows():

        value = safe_text(
            row.get(
                "판단/결정(가상)",
                ""
            )
        )

        if value:
            items.append(
                f"- {value}"
            )

    answer.append(
        "\n".join(items[:5])
        if items
        else "- 확인 필요"
    )


    # 판단 근거
    answer.append(
        "\n### ③ 판단 근거"
    )

    items = []

    for _, row in selected.iterrows():

        value = safe_text(
            row.get(
                "판단근거(가상)",
                ""
            )
        )

        if value:
            items.append(
                f"- {value}"
            )

    answer.append(
        "\n".join(items[:5])
        if items
        else "- 확인 필요"
    )


    # 누락정보
    answer.append(
        "\n### ④ ⚠️ 아직 확인할 정보"
    )

    items = []

    for _, row in selected.iterrows():

        value = safe_text(
            row.get(
                "인수인계 누락정보(가상)",
                ""
            )
        )

        if value:
            items.append(
                f"- {value}"
            )

    if not items and not missing.empty:

        for _, row in missing.head(5).iterrows():

            value = safe_text(
                row.get(
                    "추가로 기록할 정보",
                    ""
                )
            )

            if value:
                items.append(
                    f"- {value}"
                )

    answer.append(
        "\n".join(items[:5])
        if items
        else "- 현재 데이터에서 추가 누락정보를 찾지 못했습니다."
    )


    # 다음 업무
    answer.append(
        "\n### ⑤ ➡️ 다음 담당자가 할 일"
    )

    items = []

    for _, row in selected.iterrows():

        value = safe_text(
            row.get(
                "다음 단계에 전달할 지식",
                ""
            )
        )

        if value:
            items.append(
                f"- {value}"
            )

    answer.append(
        "\n".join(items[:5])
        if items
        else "- 누락정보를 먼저 확인하세요."
    )


    # 단계 연결
    answer.append(
        "\n### ⑥ 🔗 이전 단계와의 연결"
    )

    items = []

    for _, row in selected.iterrows():

        kid = safe_text(
            row.get(
                "Knowledge_ID",
                ""
            )
        )

        link = safe_text(
            row.get(
                "단계연결_ID",
                ""
            )
        )

        next_id = safe_text(
            row.get(
                "연결 Knowledge_ID",
                ""
            )
        )

        if kid:

            items.append(
                f"- {kid}: {link} → {next_id}"
            )

    answer.append(
        "\n".join(items[:5])
        if items
        else "- 연결정보 확인 필요"
    )

    return "\n".join(answer)


# =========================================================
# 사이드바
# =========================================================

st.sidebar.title(
    "🏢 WorkBridge AI"
)

st.sidebar.caption(
    "설계 엔지니어링 지식 인수인계"
)

st.sidebar.success(
    PROJECT_NAME
)


menu = st.sidebar.radio(

    "메뉴",

    [
        "📊 프로젝트 대시보드",
        "🤖 AI 인수인계",
        "🔗 단계별 지식 연결",
        "⚠️ 누락정보 확인",
        "📋 인수인계 보고서"
    ]
)


# =========================================================
# 1. 프로젝트 대시보드
# =========================================================

if menu == "📊 프로젝트 대시보드":

    st.title(
        "🏢 WorkBridge AI"
    )

    st.subheader(
        "프로젝트 지식 인수인계 대시보드"
    )

    st.caption(
        "이전 담당자의 판단과 근거를 "
        "다음 담당자의 업무로 연결합니다."
    )


    # 프로젝트 카드
    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "프로젝트",
            PROJECT_NAME
        )

    with col2:

        st.metric(
            "현재 단계",
            "개선안·설계"
        )

    with col3:

        st.metric(
            "누락 정보",
            f"{len(missing)}건"
        )


    st.divider()


    # 업무 흐름
    st.subheader(
        "🔄 프로젝트 지식 흐름"
    )

    st.info(
        "현황·노후진단  →  "
        "개선안·설계  →  "
        "시공·검증  →  "
        "인수인계·성과"
    )


    st.divider()


    # 핵심 인수인계
    st.subheader(
        "📨 현재 단계에서 이어받을 핵심 정보"
    )

    if not knowledge.empty:

        design_data = knowledge[
            knowledge[
                "프로젝트 단계"
            ].astype(str).str.contains(
                "개선안",
                na=False
            )
        ]

        if design_data.empty:
            design_data = knowledge.head(3)

        for _, row in design_data.head(3).iterrows():

            st.markdown(
                f"""
                **{safe_text(row.get("Knowledge_ID", ""))}**
                · {safe_text(row.get("업무", ""))}
                """
            )

            st.write(
                safe_text(
                    row.get(
                        "다음 단계에 전달할 지식",
                        ""
                    )
                )
            )


    st.divider()


    # 누락정보
    st.subheader(
        "⚠️ 후임자가 먼저 확인해야 할 정보"
    )

    if missing.empty:

        st.success(
            "등록된 누락정보가 없습니다."
        )

    else:

        for _, row in missing.head(4).iterrows():

            st.warning(
                f"""
                **{safe_text(row.get("우선도", ""))}**
                
                {safe_text(row.get("AI가 발견한 문제(가상)", ""))}
                
                → 추가 확인:
                {safe_text(row.get("추가로 기록할 정보", ""))}
                """
            )


    st.divider()


    # AI 질문
    st.subheader(
        "🤖 바로 AI에게 질문하기"
    )

    question = st.selectbox(

        "시연 질문",

        [
            "이 프로젝트를 처음 맡았는데 무엇부터 확인해야 하나요?",
            "왜 냉난방장치를 개선하려고 했나요?",
            "왜 이 장비를 선정했나요?",
            "설계에서 아직 확인되지 않은 정보는 무엇인가요?",
            "다음 담당자에게 무엇을 인수인계해야 하나요?"
        ]
    )


    if st.button(
        "🤖 AI 인수인계 분석하기",
        type="primary"
    ):

        st.session_state[
            "question"
        ] = question

        st.session_state[
            "run_ai"
        ] = True

        st.session_state[
            "menu_target"
        ] = "🤖 AI 인수인계"

        st.rerun()


# =========================================================
# 2. AI 인수인계
# =========================================================

elif menu == "🤖 AI 인수인계":

    st.title(
        "🤖 AI 인수인계"
    )

    st.caption(
        "프로젝트 Excel의 업무 지식과 "
        "단계 연결정보를 바탕으로 "
        "후임자의 질문에 답합니다."
    )


    question = st.text_area(

        "💬 후임자의 질문",

        value=st.session_state.get(
            "question",
            "이 프로젝트를 처음 맡았는데 무엇부터 확인해야 하나요?"
        ),

        height=100,

        placeholder=
        "예: 왜 냉난방장치를 개선하려고 했나요?"
    )


    if st.button(
        "🤖 인수인계 분석",
        type="primary"
    ):

        with st.spinner(
            "프로젝트 정보를 분석하고 있습니다..."
        ):

            context = build_context(
                question
            )

            ai_answer = ask_gemini(
                question,
                context
            )

            if ai_answer:

                answer = ai_answer

                st.success(
                    "Gemini가 프로젝트 데이터를 기반으로 분석했습니다."
                )

            else:

                answer = local_answer(
                    question
                )

                st.info(
                    "Gemini 연결이 확인되지 않아 "
                    "Excel 기반 분석 결과를 표시합니다."
                )


        st.divider()

        st.subheader(
            "📨 인수인계 분석 결과"
        )

        st.markdown(
            answer
        )


        # AI가 어떤 데이터를 봤는지 확인
        with st.expander(
            "🔎 AI가 참고한 프로젝트 데이터 보기"
        ):

            st.text(
                context
            )


# =========================================================
# 3. 단계별 지식 연결
# =========================================================

elif menu == "🔗 단계별 지식 연결":

    st.title(
        "🔗 단계별 지식 연결"
    )

    st.caption(
        "한 단계의 판단이 다음 단계의 업무로 "
        "어떻게 이어지는지 보여줍니다."
    )


    if stage_map.empty:

        st.warning(
            "08_단계연결맵 데이터를 찾을 수 없습니다."
        )

    else:

        for _, row in stage_map.iterrows():

            from_stage = safe_text(
                row.get(
                    "출발 단계",
                    ""
                )
            )

            from_id = safe_text(
                row.get(
                    "출발 Knowledge",
                    ""
                )
            )

            relation = safe_text(
                row.get(
                    "연결 관계",
                    ""
                )
            )

            to_stage = safe_text(
                row.get(
                    "도착 단계",
                    ""
                )
            )

            to_id = safe_text(
                row.get(
                    "도착 Knowledge",
                    ""
                )
            )

            description = safe_text(
                row.get(
                    "연결 설명",
                    ""
                )
            )


            st.markdown(
                f"""
                ### {from_stage}

                **{from_id}**
                
                ↓ `{relation}` ↓
                
                **{to_stage}**
                
                **{to_id}**
                
                {description}
                """
            )

            st.divider()


# =========================================================
# 4. 누락정보
# =========================================================

elif menu == "⚠️ 누락정보 확인":

    st.title(
        "⚠️ 누락정보 확인"
    )

    st.caption(
        "후임자가 업무를 이어가기 위해 "
        "추가로 확인해야 하는 정보를 보여줍니다."
    )


    if missing.empty:

        st.success(
            "등록된 누락정보가 없습니다."
        )

    else:

        priority = st.selectbox(
            "우선도",
            [
                "전체",
                "높음",
                "중간"
            ]
        )


        view = missing.copy()


        if (
            priority != "전체"
            and "우선도" in view.columns
        ):

            view = view[
                view["우선도"].astype(str)
                == priority
            ]


        for _, row in view.iterrows():

            problem = safe_text(
                row.get(
                    "AI가 발견한 문제(가상)",
                    ""
                )
            )

            need = safe_text(
                row.get(
                    "추가로 기록할 정보",
                    ""
                )
            )

            kid = safe_text(
                row.get(
                    "Knowledge_ID",
                    ""
                )
            )

            p = safe_text(
                row.get(
                    "우선도",
                    ""
                )
            )


            with st.expander(
                f"⚠️ {p} | {kid}"
            ):

                st.write(
                    "**AI가 발견한 문제**"
                )

                st.write(
                    problem
                )

                st.write(
                    "**추가로 기록해야 할 정보**"
                )

                st.write(
                    need
                )


# =========================================================
# 5. 인수인계 보고서
# =========================================================

elif menu == "📋 인수인계 보고서":

    st.title(
        "📋 프로젝트 인수인계 보고서"
    )

    st.caption(
        "프로젝트의 판단·근거·누락정보를 "
        "한 번에 정리합니다."
    )


    report = []

    report.append(
        f"# {PROJECT_NAME}"
    )

    report.append("")

    report.append(
        "## 1. 프로젝트 개요"
    )

    report.append(
        "노후 공공건축물의 에너지 성능 개선과 "
        "단계 간 설계·판단 정보의 인수인계를 "
        "지원하는 가상 프로젝트입니다."
    )


    report.append("")

    report.append(
        "## 2. 주요 업무 지식"
    )


    if not knowledge.empty:

        for _, row in knowledge.iterrows():

            kid = safe_text(
                row.get(
                    "Knowledge_ID",
                    ""
                )
            )

            stage = safe_text(
                row.get(
                    "프로젝트 단계",
                    ""
                )
            )

            work = safe_text(
                row.get(
                    "업무",
                    ""
                )
            )

            decision = safe_text(
                row.get(
                    "판단/결정(가상)",
                    ""
                )
            )

            reason = safe_text(
                row.get(
                    "판단근거(가상)",
                    ""
                )
            )

            next_info = safe_text(
                row.get(
                    "다음 단계에 전달할 지식",
                    ""
                )
            )


            report.append(
                f"### {kid} | {stage} | {work}"
            )

            if decision:
                report.append(
                    f"- 판단: {decision}"
                )

            if reason:
                report.append(
                    f"- 근거: {reason}"
                )

            if next_info:
                report.append(
                    f"- 다음 단계 전달: {next_info}"
                )


    report.append("")

    report.append(
        "## 3. 누락정보"
    )


    if not missing.empty:

        for _, row in missing.iterrows():

            report.append(
                f"- [{safe_text(row.get('우선도', ''))}] "
                f"{safe_text(row.get('AI가 발견한 문제(가상)', ''))} "
                f"→ {safe_text(row.get('추가로 기록할 정보', ''))}"
            )


    report_text = "\n".join(
        report
    )


    st.markdown(
        report_text
    )


    st.download_button(

        "📥 인수인계 보고서 저장",

        data=report_text,

        file_name=
        "WorkBridge_AI_인수인계보고서.md",

        mime="text/markdown"
    )


# =========================================================
# 하단
# =========================================================

st.divider()

st.caption(
    "※ 본 프로젝트의 건물명·수치·설계판단·시공결과는 "
    "대회용 가상 데이터입니다."
)
