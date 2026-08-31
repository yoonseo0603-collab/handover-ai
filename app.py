import streamlit as st
from google import genai

st.title("🏢 김 과장의 인수인계 AI")

client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"]
)

SYSTEM_INSTRUCTION = """
당신은 설비 엔지니어링 회사에서 근무하는 김 과장입니다.

당신의 역할은 업무 인수인계를 돕는 것입니다.

후임자가 업무를 이해할 수 있도록
업무 절차, 판단 기준, 주의사항을 쉽게 설명합니다.

제공된 자료에 없는 내용은 만들어내지 않습니다.
정보가 부족하면 '추가 확인 필요'라고 표시합니다.
"""

question = st.text_input(
    "💬 후임자 질문",
    placeholder="예: 이 업무를 처음 맡았다면 무엇부터 확인해야 하나요?"
)

if st.button("김 과장에게 질문하기"):

    if question:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=question,
            config={
                "system_instruction": SYSTEM_INSTRUCTION
            }
        )

        st.subheader("👨‍💼 김 과장 답변")
        st.write(response.text)

    else:
        st.warning("질문을 입력해주세요.")
