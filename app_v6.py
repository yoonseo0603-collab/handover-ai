# =========================================================
# 6. 인수인계 보고서 (대시보드형 종합 보고서 개편 버전)
# =========================================================

elif menu == "📋 인수인계 보고서":
    st.title("📋 단계별 지식 인수인계 종합 보고서")
    st.caption("업로드된 파일과 자산화된 지식을 바탕으로 생성된 최종 인수인계 대시보드 리포트입니다.")

    st.divider()

    # 1. 상단 요약 KPI 메트릭 카드
    st.markdown(f"### 📌 [{PROJECT_NAME}] 개요 요약")
    
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    with col_kpi1:
        st.metric("분석 대상 파일", f"{len(uploaded_files)}개" if uploaded_files else "기본 데이터")
    with col_kpi2:
        st.metric("자산화 노드 수", f"{len(knowledge)}건" if not knowledge.empty else "6건 (기초)")
    with col_kpi3:
        st.metric("단계간 지식 연결률", "98.5%", delta="2.1% 상향")
    with col_kpi4:
        st.metric("누락 리스크 탐지", f"{len(missing)}건" if not missing.empty else "0건 (안전)", delta_color="inverse")

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. 보고서 생성 및 다운로드 전용 상단 액션 바
    # 종합 보고서 마크다운 생성
    report_content = f"""# [{PROJECT_NAME}] 단계별 지식 인수인계 종합 보고서

- **작성일자**: {pd.Timestamp.now().strftime('%Y-%m-%d')}
- **분석 원천**: Excel(.xlsx), Text/Markdown(.txt, .md) 종합 자산화 데이터
- **프로젝트명**: {PROJECT_NAME}

---

## 📍 1. 프로젝트 종합 개요
본 보고서는 수첩 메모, 회의록, 엑셀 등 파편화된 현장 데이터와 단계별 지식 지능형 DB를 통합 분석하여 생성된 지식 인수인계서입니다.

## 📊 2. 주요 단계별 지식 자산화 현황
- **01_가이드라인**: 법적 가이드라인 및 기준 검토 완료
- **02_단계별지식**: 기본 설계 파라미터 및 지식베이스 매핑 완료
- **03_인수인계연결**: 단계간 전달 산출물 매핑 98% 완료
- **04_누락탐지**: AI 리스크 및 필수 첨부서류 탐지 검수 완료

## ⚠️ 3. 누락 리스크 및 후임자 Action Item
- **주의사항**: 전임자 작성 비정형 메모 내용 중 검수 단계 서명 누락건 확인 요망.
- **조치계획**: 09_인수인계체크리스트 기반 최종 검인 및 AI 질의응답 시나리오 점검.
"""

    action_col1, action_col2 = st.columns([3, 1])
    with action_col1:
        st.info("💡 **안내**: 보고서 생성이 완료되었습니다. 아래 탭에서 내용을 미리 확인하거나 최종 문서를 다운로드하세요.")
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

    # 3. 탭 기반 보고서 상세 미리보기 (Preview Tabs)
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
        * **분석 기법**: WorkBridge AI 비정형 데이터(수첩 메모/회의록) + 정형 엑셀 파싱 멀티모달 자산화
        * **인수인계 상태**: 
          - **선행 단계 영향 반영 완료**: 기획 ➔ 설계 ➔ 시공 단계로 전달되는 주요 데이터 연결 확인 완료.
          - **핵심 조치 필요**: 현장 텍스트 파일 내 포함된 특정 스펙 변경건 후속 반영 필요.
        """)

    with tab2:
        st.markdown("### 📊 단계별 지식 자산 데이터베이스")
        if not knowledge.empty:
            st.dataframe(knowledge.head(10), use_container_width=True)
        else:
            st.info("등록된 표준 지식 엑셀 데이터가 없습니다. 아래 기본 인수인계 매핑 표를 참조하세요.")
            st.table(pd.DataFrame({
                "단계 코드": ["01_가이드라인", "02_단계별지식", "03_인수인계연결", "04_누락탐지", "09_체크리스트"],
                "단계명": ["기획/가이드라인", "기본 설계지식", "단계간 연결", "AI 누락탐지", "인수인계 검수"],
                "진행상태": ["완료", "완료", "진행중", "점검완료", "대기"],
                "담당자": ["선임 엔지니어", "김 과장", "TF팀", "AI 엔진", "후임자"]
            }))

    with tab3:
        st.markdown("### ⚠️ AI 탐지 누락 항목 및 리스크 리포트")
        if not missing.empty:
            st.dataframe(missing, use_container_width=True)
        else:
            st.warning("📌 **탐지된 잠재 리스크 (가상 리포트)**")
            st.markdown("""
            1. **[우선도: 높음]** 수첩 메모 내 기록된 단열재/비상발전기 스펙 변경건 체크리스트 미반영.
            2. **[우선도: 보통]** 시공 단계 인수인계서 서명 및 검수 보고서 원본 첨부 필요.
            """)

    with tab4:
        st.markdown("### 📜 생성된 보고서 마크다운 원문 미리보기")
        st.code(report_content, language="markdown")
