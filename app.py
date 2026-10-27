import streamlit as st
import os
from presentation_agent import coordinator

st.set_page_config(page_title="AI Presentation Generator", page_icon="🤖", layout="wide")

# Инициализация состояния
if "user_request" not in st.session_state:
    st.session_state.user_request = ""

st.title("🤖 AI Генератор Презентаций")
st.markdown("Опишите, какую презентацию вы хотите, и нажмите «Сгенерировать».")

# Функция для очистки поля
def clear_text():
    st.session_state.user_request = ""
    st.session_state.text_area_key = "" # Сбрасываем ключ виджета

# Поле для ввода (добавляем key)
user_request = st.text_area(
    "Ваш запрос:", 
    value=st.session_state.user_request,
    key="text_area_key", # <-- ВАЖНО: добавляем уникальный ключ
    height=200,
    placeholder="Например: Сделай презентацию про космос, 5 слайдов..."
)

col1, col2 = st.columns([1, 4])
with col1:
    generate_btn = st.button("🚀 Сгенерировать", type="primary")
with col2:
    # При нажатии вызываем функцию очистки
    if st.button("Очистить"):
        clear_text()
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
                
                # --- ПРЕВЬЮ СЛАЙДОВ ---
                import json
                try:
                    with open("presentation_data.json", "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    st.markdown("### 📸 Предпросмотр слайдов")
                    
                    for i, slide in enumerate(data.get("slides", [])):
                        st.markdown(f"**Слайд {i+1}: {slide.get('title', 'Без заголовка')}**")
                        
                        # Показываем картинку, если она есть
                        img_path = f"images/slide_{i+1}.png"
                        if os.path.exists(img_path):
                            st.image(img_path, width=300)
                        
                        # Показываем текст
                        st.info(slide.get("content", "Нет текста"))
                        st.divider()
                        
                except FileNotFoundError:
                    st.warning("Файл с данными для превью не найден.")
                # ----------------------
                
                # Кнопка скачивания
                with open(filename, "rb") as file:
                    st.download_button(
                        label="📥 Скачать презентацию (.pptx)",
                        data=file,
                        file_name="presentation.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
                    
            except Exception as e:
                st.error(f"❌ Произошла ошибка: {e}")
