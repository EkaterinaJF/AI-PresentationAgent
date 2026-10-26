import streamlit as st
import os
from presentation_agent import coordinator

st.set_page_config(page_title="AI Presentation Generator", page_icon="🤖", layout="wide")

# Инициализация состояния (чтобы поле очищалось)
if "user_request" not in st.session_state:
    st.session_state.user_request = ""

st.title("🤖 AI Генератор Презентаций")
st.markdown("Опишите, какую презентацию вы хотите, и нажмите «Сгенерировать».")

# Поле для ввода (привязано к сессии)
user_request = st.text_area(
    "Ваш запрос:", 
    value=st.session_state.user_request,
    height=200,
    placeholder="Например: Сделай презентацию про космос, 5 слайдов..."
)

col1, col2 = st.columns([1, 4])
with col1:
    generate_btn = st.button("🚀 Сгенерировать", type="primary")
with col2:
    if st.button("Очистить"):
        st.session_state.user_request = ""
        st.rerun()

if generate_btn:
    if not user_request.strip():
        st.warning("Пожалуйста, введите запрос.")
    else:
        st.session_state.user_request = user_request
        filename = "web_presentation.pptx"
        
        with st.spinner("Агенты работают... Это может занять несколько минут (генерация картинок)."):
            try:
                result = coordinator(user_request, filename=filename)
                st.success(f"✅ {result}")
                
                # Показываем файл для скачивания
                with open(filename, "rb") as file:
                    st.download_button(
                        label="📥 Скачать презентацию (.pptx)",
                        data=file,
                        file_name="presentation.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
                    
            except Exception as e:
                st.error(f"❌ Произошла ошибка: {e}")
