import streamlit as st
import os
from presentation_agent import coordinator  # Импортируем нашего координатора

# Настройка страницы
st.set_page_config(page_title="AI Presentation Generator", page_icon="🤖", layout="wide")

st.title("🤖 AI Генератор Презентаций")
st.markdown("Опишите, какую презентацию вы хотите, и нажмите «Сгенерировать».")

# Поле для ввода промпта
user_request = st.text_area(
    "Ваш запрос:", 
    height=200,
    placeholder="Например: Сделай презентацию про космос, 5 слайдов. На титульном листе укажи автора 'Иван' и город 'Москва'. 1. Звезды. 2. Планеты..."
)

# Кнопка запуска
if st.button("🚀 Сгенерировать презентацию", type="primary"):
    if not user_request.strip():
        st.warning("Пожалуйста, введите запрос.")
    else:
        with st.spinner("Агенты работают... Это может занять несколько минут (генерация картинок)."):
            try:
                # Запускаем координатора (он вернет имя файла)
                # Внимание: в coordinator мы передаем filename="presentation.pptx"
                result = coordinator(user_request, filename="web_presentation.pptx")
                
                st.success("✅ Презентация успешно создана!")
                
                # Кнопка для скачивания файла
                with open("web_presentation.pptx", "rb") as file:
                    st.download_button(
                        label="📥 Скачать презентацию (.pptx)",
                        data=file,
                        file_name="presentation.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
                    
            except Exception as e:
                st.error(f"❌ Произошла ошибка: {e}")
                st.info("Проверьте логи в терминале для получения подробностей.")
