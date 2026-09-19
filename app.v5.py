import streamlit as st
import pandas as pd
from pathlib import Path
from io import BytesIO

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
# 다중 포맷 파일 업로드 (엑셀, 텍스트, 마크다운 등 모두 지원)
# =========================================================

st.sidebar.header("📁 프로젝트 및 현장 자료 업로드")
st.sidebar.caption("엑셀(.xlsx)뿐만 아니라 수첩 메모, 회의록 등 텍스트(.txt, .md) 파일도 자유롭게 업로드하세요.")

uploaded_files = st.sidebar.file_uploader(
    "참조 파일 업로드 (복수 선택 가능)",
    type=["xlsx", "txt", "md"],
    accept_multiple_files=True,
    help="정형 엑셀 및 비정형 텍스트/메모 파일을 모두 지원합니다."
)

# 데이터 컨테이너 초기화
data = {}
raw_text_corpus = []

if uploaded_files:
    for file in uploaded_files:
        file_extension = file.name.split(".")[-1].lower()
        
        if file_extension == "xlsx":
            try:
                xls_data = pd.read_excel(BytesIO(file.getvalue()), sheet_name=None)
                data.update(xls_data)
                st.sidebar.success(f"📊 엑셀 로드 완료: {file.name}")
            except Exception as e:
                st.sidebar.error(f"❌ 엑셀 읽기 실패 ({file.name})")
                
        elif file_extension in ["txt", "md"]:
            try:
                text_content = file.getvalue().decode("utf-8", errors="ignore")
                raw_text_corpus.append(f"--- 파일명: {file.name} ---\n{text_content}")
                st.sidebar.success(f"📝 텍스트/메모 로드 완료: {file.name}")
            except Exception as e:
                st.sidebar.error(f"❌ 텍스트 읽기 실패 ({file.name})")

# 데이터프레임 추출 (없으면 빈 DataFrame)
project = data.get("00_프로젝트개요", pd.DataFrame())
knowledge = data.get("02_단계별지식", pd.DataFrame())
handover = data.get("03_인수인계연결", pd.DataFrame())
missing = data.get("04_누락탐지", pd.DataFrame())
checklist = data.get("09_인수인계체크리스트", pd.DataFrame())
stage_map = data.get("08_단계연결맵", pd.DataFrame())


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
    if not project.empty:
        try:
            for _, row in project.iterrows():
                key = safe_text(row.iloc[0])
                value = safe_text(row.iloc[1])
                if key == "프로젝트명":
                    return value
        except Exception:
            pass
    return "2026 그린리모델링 가상 프로젝트 (종합 인수인계)"


PROJECT_NAME = get_project_name()


def row_to_text(row):
    result = []
    for column in row.index:
        value = safe_text(row[column])
        if value:
            result.append(f"{column}: {value}")
    return " | ".join(result)


# =========================================================
# 지식 검색 및 컨텍스트 빌더
# =========================================================

def search_knowledge(question, top_n=6):
    if knowledge.empty:
        return pd.DataFrame()

    question = safe_text(question).lower()
    keywords = [w.strip(".,!?/()[]") for w in question.split() if len(w.strip(".,!?/()[]")) >= 2]

    scores = []
    for _, row in knowledge.iterrows():
        text = row_to_text(row).lower()
        score = sum(1 for kw in keywords if kw in text)
        scores.append(score)

    result = knowledge.copy()
    result["_score"] = scores
    result = result.sort_values("_score", ascending=False)

    if result["_score"].max() == 0:
        result = result.head(top_n)
    else:
        result = result[result["_score"] > 0].head(top_n)

    return result.drop(columns=["_score"], errors="ignore")


def build_context(question):
    selected = search_knowledge(question, top_n=6)
    context = []

    context.append("===== 업로드된 비정형 메모 및 텍스트 자료 =====")
    if raw_text_corpus:
        context.extend(raw_text_corpus)
    else:
        context.append("추가 업로드된 텍스트/메모 파일 없음")

    context.append("\n===== 프로젝트 개요 (엑셀) =====")
    if not project.empty:
        for _, row in project.iterrows():
            context.append(row_to_text(row))

    context.append("\n===== 관련 단계별 지식 (엑셀 DB) =====")
    if selected.empty:
        context.append("등록된 표준 지식 없음")
    else:
        for _, row in selected.iterrows():
            context.append(row_to_text(row))

    return "\n".join(context)


# =========================================================
# Gemini 설정 (단계별 지식 인수인계 특화 페르소나)
# =========================================================

SYSTEM_INSTRUCTION = """
당신은 설계 엔지니어링 프로젝트의 '단계별 지식 인수인계' 전문 AI '김 과장'입니다.
현업 엔지니어들은 바쁘기 때문에 정형화된 틀이나 템플릿 없이, 엑셀뿐만 아니라 수첩 메모(.txt), 회의록(.md), 거친 날림 메모 등 다양한 포맷으로 업무 기록을 남깁니다.

[핵심 임무]
1. 사용자가 업로드한 파일(엑셀, 텍스트, 메모 등)이나 입력한 비정형 텍스트를 종합하여, 프로젝트의 '단계별 지식 체계(Stage Knowledge)'에 맞추어 완벽하게 파싱·매핑하십시오.
2. 엔지니어링 프로젝트 생애주기 관점에서 앞 단계의 결정이 다음 단계에 미치는 영향(지식 연결성)을 명확히 분석하십시오.
3. 전임자가 놓치기 쉬운 리스크나 누락 요소를 찾아내어 후임자에게 강력한 리스크 경고를 제공하십시오.

[출력 양식]
### 📍 1. 파악된 프로젝트 단계 및 현황
- 업로드된 자료(엑셀/텍스트)를 기반으로 한 엔지니어링 단계 및 핵심 상황 요약

### 🔍 2. 선임자의 판단 및 엔지니어링 근거
- 선임자가 왜 그런 실무적 판단을 내렸는지에 대한 배경 (행간 추론)

### 🔗 3. 단계별 지식 연결 (앞 ➔ 다음 단계 영향)
- 이 내용이 전 단계에서 어떻게 넘어왔으며, 후속 단계(설계/시공/인허가 등)에 어떤 영향을미치는지 연결

### ⚠️ 4. 누락 리스크 및 주의사항
- 자료에서 포착된 잠재적 위험 요소나 후임자가 반드시 확인해야 할 사항

### ➡️ 5. 후임자 Action Item
- 다음 담당자가 즉시 수행해야 할 구체적인 실무 조치
"""


def ask_gemini(question, context, is_raw_input=False, target_stage=""):
    # 1) google-genai 라이브러리 확인
    if genai is None:
        st.error("❌ google-genai 라이브러리를 불러오지 못했습니다.")
        st.error("requirements.txt에 google-genai가 포함되어 있는지 확인해주세요.")
        return None

    # 2) Streamlit Secrets에서 API Key 확인
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        if not api_key:
            st.error("❌ GEMINI_API_KEY가 비어 있습니다.")
            return None
    except Exception as e:
        st.error(f"❌ Streamlit Secrets 오류: {e}")
        st.info('Secrets에는 다음 형식으로 입력해야 합니다: GEMINI_API_KEY = "YOUR_API_KEY"')
        return None

    # 3) Gemini API 호출
    try:
        client = genai.Client(api_key=api_key)

        if is_raw_input:
            prompt = f"""
[업로드된 파일 및 현장 비정형 메모 전체 내용]
{context}

[추가 입력된 질문/메모]
(목표 단계: {target_stage if target_stage else "자동 분류"})
{question}

위 자료들을 종합하여 시스템의 '단계별 지식 인수인계' 구조에 맞춰 완벽한 브리핑 보고서로 자동 자산화하여 답변하세요.
"""
        else:
            prompt = f"""
[프로젝트 데이터 및 업로드된 파일 컨텍스트]
{context}

[후임자의 질문]
{question}

위 데이터를 기반으로 단계별 지식 인수인계 관점에서 명확하게 답변하세요.
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "system_instruction": SYSTEM_INSTRUCTION
            }
        )

        return response.text

    except Exception as e:
        st.error(f"❌ Gemini API 호출 오류: {type(e).__name__}")
        st.error(str(e))
        return None


# =========================================================
# 사이드바 메뉴
# =========================================================

st.sidebar.title("🏢 WorkBridge AI")
st.sidebar.caption("단계별 지식 인수인계 플랫폼")
st.sidebar.success(PROJECT_NAME)

menu = st.sidebar.radio(
    "메뉴",
    [
        "📊 프로젝트 대시보드",
        "💬 파일·메모 ➔ 단계별 지식 자동 자산화",
        "🤖 AI 인수인계 챗봇",
        "🔗 단계별 지식 연결",
        "⚠️ 누락정보 확인",
        "📋 인수인계 보고서"
    ]
)


# =========================================================
# 1. 프로젝트 대시보드
# =========================================================

if menu == "📊 프로젝트 대시보드":
    st.title("🏢 WorkBridge AI")
    st.subheader("단계별 지식 인수인계 대시보드")
    st.caption("엑셀, 텍스트, 메모 등 어떤 포맷이든 AI가 알아서 단계별 지식으로 자산화하는 시스템")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("프로젝트", PROJECT_NAME)
    with col2:
        st.metric("업로드된 파일 수", f"{len(uploaded_files)}개" if uploaded_files else "기본 가상 모드")
    with col3:
        st.metric("지식 노드 DB", f"{len(knowledge)}건" if not knowledge.empty else "비정형 모드")

    st.divider()

    st.info(
        "💡 **핵심 설계 철학**: "
        "정형화된 엑셀 템플릿뿐만 아니라 수첩 메모(`.txt`), 회의록(`.md`) 등 **어떤 형태의 파일이나 텍스트든 자유롭게 업로드**할 수 있습니다. "
        "시스템이 알아서 내용을 파싱하여 **단계별 지식 구조(Stage Knowledge)**로 자산화합니다."
    )

    if st.button("👉 파일 및 메모를 단계별 지식으로 변환해보기", type="primary"):
        st.session_state["jump"] = True
        st.rerun()


# =========================================================
# 2. 파일·메모 ➔ 단계별 지식 자동 자산화
# =========================================================

elif menu == "💬 파일·메모 ➔ 단계별 지식 자동 자산화":
    st.title("💬 파일 및 메모 ➔ 단계별 지식 자동 자산화")
    st.caption(
        "좌측 사이드바에서 엑셀(.xlsx)뿐만 아니라 텍스트(.txt, .md) 파일을 업로드하거나, "
        "아래에 직접 현장 메모를 입력하여 AI 분석을 실행할 수 있습니다."
    )

    stage_options = [
        "자동 판별",
        "01_통합설계 및 기본계획",
        "02_전기통신설비 검토",
        "03_소방방재연구 및 인허가",
        "04_친환경 컨설팅 및 시공 연계"
    ]
    selected_stage = st.selectbox("📌 관련 엔지니어링 단계 선택", stage_options)

    # 샘플 버튼
    st.markdown("##### ⚡ 현장 메모/텍스트 샘플 예시")
    c1, c2 = st.columns(2)
    
    sample_1 = "통합설계 단계: 구청 외벽 단열 기준 강화로 인해 단열재 두께 상향 조정 검토 필요. 예산 한도 내에서 스펙 조율 요망."
    sample_2 = "소방방재 인허가: 스프링클러 말단 압력시험 데이터 누락 확인. 시공사 협조 거부 중이므로 후임자가 긴급 조치 필요."

    raw_text_input = ""
    if c1.button("📌 [샘플 A] 단열재 기준 강화 이슈 (텍스트 메모)"):
        raw_text_input = sample_1
    if c2.button("📌 [샘플 B] 소방 인허가 누락 이슈 (텍스트 메모)"):
        raw_text_input = sample_2

    user_raw_memo = st.text_area(
        "✍️ 현장 텍스트 및 추가 메모 입력 (자유 양식)",
        value=raw_text_input,
        height=120,
        placeholder="업로드된 파일 내용과 함께 분석할 추가 메모나 질문을 입력하세요..."
    )

    if st.button("🚀 업로드된 파일 및 메모 ➔ 단계별 지식 자동 자산화", type="primary"):
        with st.spinner("AI가 업로드된 파일(.xlsx, .txt 등)과 메모를 종합 분석하여 단계별 지식으로 매핑 중입니다..."):
            combined_context = build_context(user_raw_memo)
            result_text = ask_gemini(user_raw_memo, combined_context, is_raw_input=True, target_stage=selected_stage)
            
            if result_text:
                st.success("✅ 파일 및 비정형 메모가 성공적으로 '단계별 지식 인수인계서'로 자산화되었습니다!")
                st.markdown("---")
                st.markdown(result_text)
            else:
                st.warning("⚠️ Gemini 분석에 실패했습니다. 위에 표시된 상세 오류 메시지를 확인해주세요.")


# =========================================================
# 3. AI 인수인계 챗봇
# =========================================================

elif menu == "🤖 AI 인수인계 챗봇":
    st.title("🤖 단계별 지식 연계 인수인계 챗봇")
    st.caption("업로드된 파일들과 Excel DB를 종합하여 후임자의 질문에 답변합니다.")

    question = st.text_area(
        "💬 후임자 질문 입력",
        value="업로드된 자료와 전임자 기록을 바탕으로 다음 단계에서 가장 주의해야 할 점은 무엇인가요?",
        height=80
    )

    if st.button("🤖 인수인계 지식 조회", type="primary"):
        with st.spinner("종합 데이터베이스를 검색 및 분석 중입니다..."):
            context = build_context(question)
            answer = ask_gemini(question, context, is_raw_input=False)

            if not answer:
                answer = "### 📍 현황\n- 데이터 또는 API 설정을 확인해주세요."
            
            st.markdown("---")
            st.markdown(answer)


# =========================================================
# 4. 단계별 지식 연결
# =========================================================

elif menu == "🔗 단계별 지식 연결":
    st.title("🔗 단계별 지식 연결 구조")
    st.caption("엔지니어링 프로젝트 생애주기 동안 선행 단계의 결정이 후속 단계로 어떻게 전파되는지 보여줍니다.")
    
    if stage_map.empty:
        st.info("등록된 단계 연결 맵 데이터가 없습니다. (기본 예시 노드 표시)")
        st.markdown("""
        * **[통합설계]** ➔ 설계 변경 사항 ➔ **[전기통신설비]** 연계
        * **[소방방재연구]** ➔ 인허가 조건 충족 ➔ **[친환경 컨설팅]** 연계
        """)
    else:
        for _, row in stage_map.iterrows():
            st.markdown(f"### 📌 {safe_text(row.get('출발 단계', ''))} ➔ {safe_text(row.get('도착 단계', ''))}")
            st.write(f"**지식 연결 내용**: {safe_text(row.get('연결 설명', ''))}")
            st.divider()


# =========================================================
# 5. 누락정보 확인
# =========================================================

elif menu == "⚠️ 누락정보 확인":
    st.title("⚠️ 누락정보 및 리스크 탐지")
    st.caption("업로드된 자료와 단계별 지식 전파 과정에서 포착된 잠재적 리스크 항목입니다.")
    
    if missing.empty:
        st.success("현재 탐지된 치명적 누락 정보가 없습니다. (파일을 업로드하면 실시간 리스크가 분석됩니다)")
    else:
        for _, row in missing.iterrows():
            st.warning(f"**[우선도: {safe_text(row.get('우선도', ''))}]** {safe_text(row.get('AI가 발견한 문제(가상)', ''))}")


# =========================================================
# 6. 인수인계 보고서
# =========================================================

elif menu == "📋 인수인계 보고서":
    st.title("📋 단계별 지식 인수인계 보고서")
    st.caption("업로드된 파일과 자산화된 지식을 바탕으로 최종 인수인계 보고서를 생성합니다.")
    
    report_md = f"# [{PROJECT_NAME}] 단계별 지식 인수인계 종합 보고서\n\n- 파일 지원: Excel(.xlsx), Text/Markdown(.txt, .md)\n- 특징: 정형 양식 강제 없는 비정형 데이터 자동 자산화"
    st.markdown(report_md)
    st.download_button("📥 인수인계 보고서 다운로드", data=report_md, file_name="MultiFormat_Handover_Report.md")


# =========================================================
# 하단 카피라이트
# =========================================================
st.divider()
st.caption("※ WorkBridge AI — 엑셀, 텍스트, 메모 등 어떤 자료든 완벽하게 흡수하여 단계별 지식을 연결하는 인수인계 솔루션")
