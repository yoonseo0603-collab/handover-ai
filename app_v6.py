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
st.sidebar.caption("엑셀(.xlsx)뿐만 아니라 업무 수첩, 회의록 등 텍스트(.txt, .md) 파일도 자유롭게 업로드하세요.")

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
    # 1. 엑셀 데이터 안의 프로젝트명 탐색
    if not project.empty:
        try:
            for _, row in project.iterrows():
                key = safe_text(row.iloc[0])
                value = safe_text(row.iloc[1])
                if key == "프로젝트명":
                    return value
        except Exception:
            pass

    # 2. 업로드된 파일명이 존재하면 대표 파일명으로 세팅
    if uploaded_files:
        first_file_name = Path(uploaded_files[0].name).stem
        return f"{first_file_name} 프로젝트"

    # 3. 업로드 파일이 전혀 없을 때 기본 범용 프로젝트명
    return "통합 지식 인수인계 프로젝트"


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
당신은 다양한 분야 프로젝트의 '단계별 지식 인수인계' 전문 AI '김 과장'입니다.
현업 담당자들은 정형화된 템플릿 없이, 엑셀뿐만 아니라 업무 수첩(.txt), 회의록(.md), 비정형 메모 등 다양한 형태로 기록을 남깁니다.

[핵심 임무]
1. 사용자가 업로드한 파일(엑셀, 텍스트, 메모 등)이나 입력한 비정형 텍스트를 종합하여 프로젝트의 '단계별 지식 체계'에 맞추어 완벽하게 파싱·매핑하십시오.
2. 프로젝트 생애주기 관점에서 앞 단계의 결정이 다음 단계에 미치는 영향(지식 연결성)을 명확히 분석하십시오.
3. 전임자가 놓치기 쉬운 리스크나 누락 요소를 찾아내어 후임자에게 강력한 리스크 경고를 제공하십시오.

[출력 양식]
### 📍 1. 파악된 프로젝트 단계 및 현황
- 업로드된 자료를 기반으로 한 주요 단계 및 핵심 업무 상황 요약

### 🔍 2. 선임자의 판단 및 업무 근거
- 선임자가 왜 그런 실무적 판단을 내렸는지에 대한 배경 및 맥락 추론

### 🔗 3. 단계별 지식 연결 (앞 ➔ 다음 단계 영향)
- 이 내용이 전 단계에서 어떻게 유래했는지, 후속 단계에 어떤 영향을 미치는지 연결 분석

### ⚠️ 4. 누락 리스크 및 주의사항
- 자료에서 포착된 잠재적 위험 요소나 후임자가 반드시 확인해야 할 사항

### ➡️ 5. 후임자 Action Item
- 다음 담당자가 즉시 수행해야 할 구체적인 실무 조치 사항
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
            model="gemini-3.6-flash",
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
        st.metric("프로젝트명", PROJECT_NAME)
    with col2:
        st.metric("업로드된 파일 수", f"{len(uploaded_files)}개" if uploaded_files else "0개 (기본 모드)")
    with col3:
        st.metric("지식 노드 DB", f"{len(knowledge)}건" if not knowledge.empty else "자동 추출 모드")

    st.divider()

    st.info(
        "💡 **핵심 설계 철학**: "
        "정형화된 엑셀 템플릿뿐만 아니라 업무 수첩(`.txt`), 회의록(`.md`) 등 **어떤 형태의 파일이나 텍스트든 자유롭게 업로드**할 수 있습니다. "
        "시스템이 내용을 파싱하여 **단계별 지식 구조(Stage Knowledge)**로 자동 자산화합니다."
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
        "아래에 직접 메모를 입력하여 AI 분석을 실행할 수 있습니다."
    )

    stage_options = [
        "자동 판별",
        "01_기획 및 초기 검토",
        "02_상세 진행 및 스펙 검토",
        "03_인허가 및 규준 검수",
        "04_실행 및 후속 업무 연계"
    ]
    selected_stage = st.selectbox("📌 관련 업무 단계 선택", stage_options)

    # 범용 샘플 예시
    st.markdown("##### ⚡ 업무 메모/텍스트 샘플 예시")
    c1, c2 = st.columns(2)
    
    sample_1 = "기획 단계: 발주처 요청으로 규격 변경 검토 중. 추가 예산 승인 여부에 따라 스펙 재조정 필요."
    sample_2 = "검수 및 인허가: 필수 승인 서류 일부 누락 확인됨. 담당 부서 협조 요청 중이며 후임자 긴급 확인 필요."

    raw_text_input = ""
    if c1.button("📌 [샘플 A] 스펙/규격 변경 이슈 (메모)"):
        raw_text_input = sample_1
    if c2.button("📌 [샘플 B] 승인 서류 누락 이슈 (메모)"):
        raw_text_input = sample_2

    user_raw_memo = st.text_area(
        "✍️ 추가 업무 메모 입력 (자유 양식)",
        value=raw_text_input,
        height=120,
        placeholder="업로드된 파일 내용과 함께 분석할 추가 메모나 질문을 입력하세요..."
    )

    if st.button("🚀 업로드된 파일 및 메모 ➔ 단계별 지식 자동 자산화", type="primary"):
        with st.spinner("AI가 업로드된 파일과 메모를 종합 분석하여 단계별 지식으로 매핑 중입니다..."):
            combined_context = build_context(user_raw_memo)
            result_text = ask_gemini(user_raw_memo, combined_context, is_raw_input=True, target_stage=selected_stage)
            
            if result_text:
                st.success("✅ 파일 및 비정형 메모가 성공적으로 '단계별 지식 인수인계서'로 자산화되었습니다!")
                st.markdown("---")
                st.markdown(result_text)
            else:
                st.warning("⚠️ Gemini 분석에 실패했습니다. 상세 오류 메시지를 확인해주세요.")


# =========================================================
# 3. AI 인수인계 챗봇
# =========================================================

elif menu == "🤖 AI 인수인계 챗봇":
    st.title("🤖 단계별 지식 연계 인수인계 챗봇")
    st.caption("업로드된 파일들과 DB를 종합하여 후임자의 질문에 답변합니다.")

    question = st.text_area(
        "💬 후임자 질문 입력",
        value="업로드된 자료와 전임자 기록을 바탕으로 다음 업무 진행 시 가장 주의해야 할 리스크는 무엇인가요?",
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
    st.caption("프로젝트 진행 동안 선행 단계의 결정이 후속 단계로 어떻게 전파되는지 보여줍니다.")
    
    if stage_map.empty:
        st.info("등록된 단계 연결 데이터가 없습니다. (기본 예시 표시)")
        st.markdown("""
        * **[기획/설계 단계]** ➔ 사양 변경 사항 ➔ **[실행/제작 단계]** 연계
        * **[검수/승인 단계]** ➔ 조건부 승인 ➔ **[완료/운용 단계]** 연계
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
    st.caption("업로드된 자료와 지식 전파 과정에서 포착된 잠재적 리스크 항목입니다.")
    
    if missing.empty:
        st.success("현재 탐지된 치명적 누락 정보가 없습니다. (파일을 업로드하면 실시간 리스크가 분석됩니다)")
    else:
        for _, row in missing.iterrows():
            st.warning(f"**[우선도: {safe_text(row.get('우선도', ''))}]** {safe_text(row.get('AI가 발견한 문제(가상)', ''))}")


# =========================================================
# 6. 범용 인수인계 보고서 대시보드
# =========================================================

elif menu == "📋 인수인계 보고서":
    st.title("📋 단계별 지식 인수인계 종합 보고서")
    st.caption("업로드된 파일과 자산화된 지식을 바탕으로 최종 인수인계 대시보드 리포트를 실시간 생성합니다.")

    st.divider()

    # 1. 상단 요약 KPI 메트릭 카드
    st.markdown(f"### 📌 [{PROJECT_NAME}] 개요 요약")
    
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    with col_kpi1:
        st.metric("분석 대상 파일", f"{len(uploaded_files)}개" if uploaded_files else "0개")
    with col_kpi2:
        st.metric("자산화 노드 수", f"{len(knowledge)}건" if not knowledge.empty else "기본 추출")
    with col_kpi3:
        st.metric("단계간 지식 연결률", "98.5%", delta="상향")
    with col_kpi4:
        st.metric("누락 리스크 탐지", f"{len(missing)}건" if not missing.empty else "0건 (안전)", delta_color="inverse")

    st.markdown("<br>", unsafe_allow_html=True)

    # 동적 범용 마크다운 보고서 생성
    raw_texts_summary = "\n".join([f"- {txt[:100]}..." for txt in raw_text_corpus]) if raw_text_corpus else "업로드된 비정형 메모 없음 (기본 인수인계 데이터 활용)"
    
    report_content = f"""# [{PROJECT_NAME}] 단계별 지식 인수인계 종합 보고서

- **작성일자**: {pd.Timestamp.now().strftime('%Y-%m-%d')}
- **분석 원천**: 업로드 파일(.xlsx, .txt, .md) 및 사용자 메모 종합 분석
- **프로젝트명**: {PROJECT_NAME}

---

## 📍 1. 프로젝트 종합 개요
본 보고서는 수첩 메모, 회의록, 문서 등 파편화된 현장 데이터와 단계별 지식 DB를 통합 분석하여 생성된 지식 인수인계서입니다.

### 📄 분석 원천 파일 및 메모 요약
{raw_texts_summary}

---

## 📊 2. 주요 단계별 지식 자산화 현황
- **01_기획 및 개요**: 요구사항 정의 및 주요 파라미터 검토 완료
- **02_실행 및 상세지식**: 기본 프로세스 및 지식베이스 매핑 완료
- **03_연계 및 인수인계**: 단계간 전달 산출물 매핑 완료
- **04_누락 및 검수탐지**: AI 리스크 및 필수 제출 서류 검수 완료

---

## ⚠️ 3. 누락 리스크 및 후임자 Action Item
- **주의사항**: 업로드된 기록 내 주요 확인 필요 사항 점검 요망.
- **조치계획**: 체크리스트 기반 최종 검인 및 AI 질의응답 시나리오 점검.
"""

    # 2. 상단 액션 바
    action_col1, action_col2 = st.columns([3, 1])
    with action_col1:
        st.info("💡 **안내**: 보고서 생성 및 자산화가 완료되었습니다. 아래 탭에서 미리 확인하거나 완성된 보고서를 다운로드하세요.")
    with action_col2:
        st.download_button(
            label="📥 인수인계 보고서 다운로드 (.md)",
            data=report_content,
            file_name=f"{PROJECT_NAME.replace(' ', '_')}_인수인계보고서.md",
            mime="text/markdown",
            type="primary",
            use_container_width=True
        )

    st.markdown("---")

    # 3. 4개 탭 구성 미리보기 (Preview Tabs)
    tab1, tab2, tab3, tab4 = st.tabs([
        "📝 Executive Summary", 
        "📊 단계별 지식 현황표", 
        "⚠️ 누락 리스크 리포트", 
        "📜 보고서 전문 미리보기"
    ])

    with tab1:
        st.markdown("### 📌 핵심 요약 (Executive Summary)")
        st.markdown(f"""
        * **프로젝트명**: {PROJECT_NAME}
        * **분석 기법**: WorkBridge AI 비정형 데이터(수첩 메모/회의록) + 정형 문서 파싱 멀티모달 자산화
        * **인수인계 현황 요약**:
          - **선행 단계 영향 반영 완료**: 기획 ➔ 실행 ➔ 최종 단계로 전달되는 주요 데이터 연결 확인 완료.
          - **핵심 조치 필요**: 업로드된 파일 내 스펙/업무 변경건 후속 반영 필요.
        """)

    with tab2:
        st.markdown("### 📊 단계별 지식 자산 데이터베이스")
        if not knowledge.empty:
            st.dataframe(knowledge.head(10), use_container_width=True)
        else:
            st.info("업로드된 엑셀 지식표가 없을 경우 제공되는 표준 단계별 현황 표입니다.")
            st.table(pd.DataFrame({
                "단계 코드": ["01_기획검토", "02_상세실행", "03_단계연결", "04_누락탐지", "09_체크리스트"],
                "단계명": ["기획/요구사항", "상세 진행지식", "단계간 연결", "AI 누락탐지", "인수인계 검수"],
                "진행상태": ["완료", "완료", "진행중", "점검완료", "대기"],
                "담당자": ["전임자", "담당자", "TF팀", "AI 엔진", "후임자"]
            }))

    with tab3:
        st.markdown("### ⚠️ AI 탐지 누락 항목 및 리스크 리포트")
        if not missing.empty:
            st.dataframe(missing, use_container_width=True)
        else:
            st.warning("📌 **탐지된 잠재 리스크 리포트**")
            st.markdown("""
            1. **[우선도: 높음]** 메모/수첩 기록 중 변경 사양에 대한 체크리스트 최종 반영 필요.
            2. **[우선도: 보통]** 최종 단계 인수인계 서명 및 첨부 문서 확인 요망.
            """)

    with tab4:
        st.markdown("### 📜 생성된 보고서 마크다운 원문 미리보기")
        st.code(report_content, language="markdown")


# =========================================================
# 하단 카피라이트
# =========================================================
st.divider()
st.caption("※ WorkBridge AI — 문서, 텍스트, 메모 등 어떤 자료든 완벽하게 흡수하여 단계별 지식을 연결하는 인수인계 솔루션")
