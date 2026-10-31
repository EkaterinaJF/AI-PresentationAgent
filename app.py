import streamlit as st
import os
import json
import copy
import shutil
from presentation_agent import coordinator, regenerate_text, regenerate_image, builder_agent

st.set_page_config(page_title="AI Presentation Editor", page_icon="🤖", layout="wide")

# --- ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ ---
if "user_request" not in st.session_state:
    st.session_state.user_request = ""
if "current_data" not in st.session_state:
    st.session_state.current_data = None
if "original_data" not in st.session_state:
    st.session_state.original_data = None

st.title("🤖 AI Генератор и Редактор Презентаций")

# --- ЭТАП 1: ВВОД ПРОМПТА ---
if st.session_state.current_data is None:
    st.markdown("Опишите, какую презентацию вы хотите, и нажмите «Сгенерировать».")
    user_request = st.text_area("Ваш запрос:", value=st.session_state.user_request, height=150)
    
    if st.button("🚀 Сгенерировать", type="primary"):
        if not user_request.strip():
            st.warning("Пожалуйста, введите запрос.")
        else:
            st.session_state.user_request = user_request
            with st.spinner("Агенты работают... (генерация картинок может занять время)"):
                try:
                    # Запускаем координатора
                    coordinator(user_request, filename="draft_presentation.pptx")
                    
                    # Загружаем JSON в память
                    with open("presentation_data.json", "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    st.session_state.current_data = data
                    st.session_state.original_data = copy.deepcopy(data)
                    
                    # --- СОЗДАЕМ БЭКАП КАРТИНОК ---
                    if os.path.exists("images"):
                        if os.path.exists("images_backup"):
                            shutil.rmtree("images_backup")
                        shutil.copytree("images", "images_backup")
                    # -------------------------------
                    
                    st.rerun()
                except Exception as e:
                        st.error(f"❌ Ошибка: {e}")
                        st.info("Проверьте логи в терминале.")

# --- ЭТАП 2: РЕДАКТОР СЛАЙДОВ ---
else:
    data = st.session_state.current_data
    
    st.success("✅ Презентация создана! Вы можете отредактировать слайды ниже.")
    st.markdown("### 📸 Редактор слайдов")
    
    for i, slide in enumerate(data.get("slides", [])):
        st.markdown(f"**Слайд {i+1}: {slide.get('title', 'Без заголовка')}**")
        
        col1, col2 = st.columns([1, 2])
        
        # --- ЛЕВАЯ КОЛОНКА (КАРТИНКА) ---
        with col1:
            img_path = f"images/slide_{i+1}.png"
            if os.path.exists(img_path):
                st.image(img_path, width=300)
            else:
                st.info("Нет картинки")
            
            img_prompt = st.text_input("Уточнить картинку:", key=f"img_prompt_{i}", placeholder="например: сделай ярче")
            
            col_img_1, col_img_2 = st.columns(2)
            with col_img_1:
                if st.button(f"🎨 Перегенерировать", key=f"btn_img_{i}"):
                    with st.spinner("Обновляю картинку..."):
                        try:
                            # Вызываем функцию перегенерации (она сама поймет тип визуала)
                            regenerate_image(slide, img_prompt, filename=img_path)
                            st.success("Обновлено!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка: {e}")
            with col_img_2:
                if st.button(f"🔄 Откатить", key=f"btn_revert_img_{i}"):
                    try:
                        backup_path = f"images_backup/slide_{i+1}.png"
                        if os.path.exists(backup_path):
                            shutil.copy(backup_path, img_path)
                            # Также восстанавливаем текстовые данные слайда из снимка
                            orig_slide = st.session_state.original_data["slides"][i]
                            slide["visual_data"] = orig_slide.get("visual_data", "")
                            slide["visual_type"] = orig_slide.get("visual_type", "none")
                            st.success("Картинка откачена!")
                            st.rerun()
                        else:
                            st.warning("Бэкап для этого слайда не найден.")
                    except Exception as e:
                        st.error(f"Ошибка отката: {e}")
        
        # --- ПРАВАЯ КОЛОНКА (ТЕКСТ) ---
        with col2:
            text_prompt = st.text_input("Уточнить текст:", key=f"text_prompt_{i}", placeholder="например: сделай проще")
            
            col_text_1, col_text_2 = st.columns(2)
            with col_text_1:
                if st.button(f"📝 Перегенерировать", key=f"btn_text_{i}"):
                    with st.spinner("Пишу текст..."):
                        try:
                            new_text = regenerate_text(slide, text_prompt)
                            slide["content"] = new_text
                            st.success("Обновлено!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Ошибка: {e}")
            with col_text_2:
                if st.button(f"🔄 Откатить", key=f"btn_revert_text_{i}"):
                    slide["content"] = st.session_state.original_data["slides"][i].get("content", "")
                    st.success("Текст откачен!")
                    st.rerun()
            
            st.info(slide.get("content", "Нет текста"))
        
        st.divider()
    
    # --- ОБЩАЯ КНОПКА СОХРАНЕНИЯ ---
    st.markdown("### 💾 Сохранить все изменения")
    if st.button("Собрать и скачать .pptx", type="primary"):
        with st.spinner("Собираю финальную презентацию..."):
            try:
                # Перезаписываем JSON с новыми данными
                with open("presentation_data.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                style = data.get("style", {"background_color": "#ffffff", "text_color": "#000000", "font_name": "arial.ttf"})
                result = builder_agent(data, style, filename="final_presentation.pptx")
                st.success("✅ Презентация собрана!")
                
                with open("final_presentation.pptx", "rb") as file:
                    st.download_button(
                        label="📥 Скачать финальную презентацию",
                        data=file,
                        file_name="presentation.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
            except Exception as e:
                st.error(f"Ошибка сборки: {e}")
    
    # Кнопка сброса (начать заново)
    if st.button("🔄 Начать заново"):
        st.session_state.current_data = None
        st.session_state.original_data = None
        st.rerun()
