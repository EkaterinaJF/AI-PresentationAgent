import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import json
import re
import torch
from diffusers import StableDiffusionPipeline, AutoencoderKL
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

# ============================================================
# 1. МОДЕЛЬ (LLM)
# ============================================================

llm = ChatOllama(
    model="hf.co/HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive:Q4_K_M",
    base_url="http://127.0.0.1:11434",
    temperature=0.3
)

# ============================================================
# 2. ГЕНЕРАТОР КАРТИНОК (загружается один раз)
# ============================================================

from PIL import Image, ImageDraw, ImageFont

# Проверяем, доступна ли CUDA (видеокарта NVIDIA)
USE_CUDA = torch.cuda.is_available()
pipe = None

if USE_CUDA:
    print("🎨 CUDA доступна. Загрузка VAE и модели Stable Diffusion...")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    VAE_PATH = os.path.join(BASE_DIR, "vae", "vae-ft-mse-840000-ema-pruned.safetensors")
    
    vae = AutoencoderKL.from_single_file(
        VAE_PATH,
        torch_dtype=torch.float16
    )
    
    pipe = StableDiffusionPipeline.from_pretrained(
        "SG161222/Realistic_Vision_V5.1_noVAE",
        vae=vae,
        torch_dtype=torch.float16,
        safety_checker=None
    )
    pipe.enable_model_cpu_offload()
    pipe.enable_attention_slicing()
else:
    print("⚠️ CUDA недоступна. Картинки будут заменены на заглушки.")

NEGATIVE_PROMPT = (
    "(deformed iris, deformed pupils, semi-realistic, cgi, 3d, render, sketch, "
    "cartoon, drawing, anime:1.4), text, close up, cropped, out of frame, "
    "worst quality, low quality, jpeg artifacts, ugly, duplicate, morbid, "
    "mutilated, (extra fingers:1.5), (mutated hands:1.5), (poorly drawn hands:1.5), "
    "(poorly drawn face:1.5), (fused fingers:1.5), (too many fingers:1.5), "
    "mutation, deformed, blurry, dehydrated, bad anatomy, bad proportions, "
    "extra limbs, cloned face, disfigured, gross proportions, malformed limbs, "
    "missing arms, missing legs, extra arms, extra legs, long neck"
)

def image_agent(prompt: str, filename: str, seed: int = 42, color: str = "#1a2a6c", font_name: str = "arial.ttf") -> str:
    """Генерирует картинку (через SD) или рисует заглушку."""
    if USE_CUDA:
        image = pipe(prompt=prompt, negative_prompt=NEGATIVE_PROMPT, num_inference_steps=25, guidance_scale=7.0, height=512, width=512, generator=torch.Generator(device="cuda").manual_seed(seed)).images[0]
        image.save(filename)
        return filename
    width, height = 800, 600
    img = Image.new("RGB", (width, height), color=color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_name, 40)
    except Exception:
        font = ImageFont.load_default()
    label = prompt[:30] + "..." if len(prompt) > 30 else prompt
    bbox = draw.textbbox((0, 0), label, font=font)
    x = (width - (bbox[2] - bbox[0])) // 2
    y = (height - (bbox[3] - bbox[1])) // 2
    draw.text((x, y), label, fill="white", font=font)
    img.save(filename)
    return filename

from ddgs import DDGS
import requests
import io

def stock_agent(query: str, filename: str) -> str:
    """Ищет изображение через ddgs и скачивает его, конвертируя в PNG."""
    print(f"   🔍 [STOCK] Ищу: {query}")
    try:
        with DDGS() as ddgs:
            results = ddgs.images(query, max_results=5)
            if not results:
                print(f"   ⚠️ [STOCK] Ничего не найдено: {query}")
                return None
            print(f"   ✅ [STOCK] Найдено {len(results)} результатов")
            for r in results:
                url = r.get('image')
                if not url:
                    continue
                try:
                    img_response = requests.get(url, timeout=30)
                    img_response.raise_for_status()
                    content_type = img_response.headers.get("Content-Type", "")
                    if not content_type.startswith("image/"):
                        continue
                    
                    # Конвертируем в PNG через Pillow
                    img = Image.open(io.BytesIO(img_response.content))
                    img = img.convert("RGB")
                    img.save(filename, "PNG")
                    
                    print(f"   ✅ [STOCK] Скачано и конвертировано: {url[:60]}...")
                    return filename
                except Exception as e:
                    print(f"   ⚠️ [STOCK] Ошибка с ссылкой: {e}")
                    continue
            print(f"   ⚠️ [STOCK] Не удалось скачать картинку: {query}")
            return None
    except Exception as e:
        print(f"   ⚠️ [STOCK] Ошибка поиска: {e}")
        return None
import matplotlib.pyplot as plt

def diagram_agent(description: str, filename: str, bg_color: str = "#ffffff", text_color: str = "#000000", font_name: str = "arial.ttf") -> str:
    """Рисует график на основе текстового описания."""
    print(f"   📊 [DIAGRAM] Рисую график: {description[:50]}...")
    
    # Настройка шрифта и цветов под стиль презентации
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['text.color'] = text_color
    plt.rcParams['axes.labelcolor'] = text_color
    plt.rcParams['xtick.color'] = text_color
    plt.rcParams['ytick.color'] = text_color
    plt.rcParams['axes.edgecolor'] = text_color

    # Создаём фигуру
    fig, ax = plt.subplots(figsize=(8, 6), facecolor=bg_color)
    ax.set_facecolor(bg_color)

    # Простой парсинг: если в описании есть "bar chart" или "diameters" — рисуем столбцы
    # В будущем здесь можно сделать более умный парсинг данных
    if "bar" in description.lower() or "diameters" in description.lower() or "размер" in description.lower():
        planets = ["Меркурий", "Венера", "Земля", "Марс", "Юпитер", "Сатурн", "Уран", "Нептун"]
        # Примерные диаметры в км (для наглядности)
        diameters = [4879, 12104, 12742, 6779, 139820, 116460, 50724, 49244]
        
        bars = ax.bar(planets, diameters, color="#4A90E2")
        ax.set_title("Сравнение диаметров планет (км)", fontsize=16, color=text_color)
        ax.set_ylabel("Диаметр (км)", fontsize=12)
        
        # Добавляем подписи значений над столбцами
        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, yval + 1000, int(yval), ha='center', va='bottom', fontsize=10, color=text_color)
    else:
        # Если описание не распознано, рисуем простой график-заглушку
        ax.text(0.5, 0.5, "График\n(нет данных)", ha='center', va='center', fontsize=20, color=text_color, transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])

    # Сохраняем картинку
    plt.tight_layout()
    plt.savefig(filename, dpi=100, facecolor=bg_color)
    plt.close(fig)
    
    print(f"   ✅ [DIAGRAM] Сохранено: {filename}")
    return filename
# ============================================================
# 3. АГЕНТ-СТИЛИСТ
# ============================================================

def stylist_agent(user_request: str) -> dict:
    """Анализирует промпт и подбирает оформление презентации."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Ты — креативный дизайнер презентаций. Пользователь опишет, 
        какую презентацию он хочет. Ты должен подобрать оформление и вернуть JSON.

        Формат ответа (строго JSON, без пояснений):
        {{
            "background_color": "#rrggbb",
            "text_color": "#rrggbb",
            "placeholder_color": "#rrggbb",
            "font_name": "arial.ttf",
            "font_size_title": 32,
            "font_size_body": 18
        }}

        ПРАВИЛА:
        1. Если пользователь указал что-то явно — учти это.
        2. Если что-то не указал — подбери самостоятельно.
        3. НЕ используй одни и те же цвета для разных тем.
        4. Думай о теме, аудитории, настроении презентации.

        КРИТИЧЕСКОЕ ПРАВИЛО КОНТРАСТА:
        - Если фон тёмный — текст должен быть светлым.
        - Если фон светлый — текст должен быть тёмным.

        Для шрифта используй ТОЛЬКО один из этих вариантов:
        - "arial.ttf"
        - "calibri.ttf"
        - "times.ttf"
        - "georgia.ttf"
        - "verdana.ttf"

        Размеры шрифтов: title — от 28 до 36, body — от 16 до 20.

        Никаких пояснений до или после JSON. Только валидный JSON."""),
        ("user", "{input}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"input": user_request})
    
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if not json_match:
        raise ValueError(f"Стилист не вернул JSON. Ответ: {response}")
    
    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        raise ValueError(f"Ошибка парсинга JSON стилиста: {e}. Ответ: {response}")
    
    return data

# ============================================================
# 4. АГЕНТ-ТЕКСТОВИК
# ============================================================

def text_agent(user_request: str) -> dict:
    """Генерирует структуру презентации с английскими промптами для картинок."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Ты — генератор презентаций. Пользователь опишет, 
        какую презентацию он хочет. Ты должен вернуть JSON.

        Формат ответа (строго JSON, без пояснений):
        {{
            "title_mode": "default" | "none" | "standard",
            "first_slide_is_title": true | false,
            "presentation_title": "Название презентации",
            "slides": [
                {{
                    "title": "Заголовок", 
                    "content": "Содержание", 
                    "visual_type": "generated" | "stock" | "diagram" | "none",
                    "visual_data": "данные для выбранного типа"
                }},
                ...
            ]
        }}

        ЛОГИКА title_mode и first_slide_is_title:
        Случай 1: Первая тема в списке — «титульный».
        → title_mode: "none", first_slide_is_title: true
        Случай 2: Темы + ОТДЕЛЬНО просят титульный.
        → title_mode: "standard", first_slide_is_title: false
        Случай 3: Про титульный ничего не сказано.
        → title_mode: "default", first_slide_is_title: false
        Случай 4: Сказано «без титульного».
        → title_mode: "none", first_slide_is_title: false
        КРИТИЧЕСКОЕ ПРАВИЛО:
        - first_slide_is_title=true и title_mode="standard" НЕ МОГУТ быть одновременно.

        ЛОГИКА visual_type:
        - "generated" — ХУДОЖЕСТВЕННАЯ картинка (космос, природа, абстракция, фантазия, настроение). 
        - "stock" — ТОЧНАЯ схема или изображение (анатомия, устройство механизмов, портреты реальных людей, карты, исторические фото, схемы с подписями).
        - "diagram" — график, таблица, диаграмма данных.
        - "none" — картинка не нужна (только текст).

        ПРАВИЛА для visual_data:
        - Для "generated" — КОРОТКИЙ английский промпт для Stable Diffusion. 
          СТРОГО не более 10-12 слов. Пиши только ключевые теги через запятую, 
          без длинных описаний и предлогов. 
          Хорошо: "vibrant nebula, planets, deep space, cosmic dust".
          Плохо: "Epic view of the solar system from deep space, dramatic lighting, sense of awe".
        - Для "stock" — поисковый запрос на РУССКОМ (например, "схема солнечной системы", "портрет Эйнштейна").
        - Для "diagram" — описание графика на английском.
        - Для "none" — пустая строка "".

        ПРАВИЛА для slides:
        - Ровно столько слайдов, сколько просит пользователь.
        - Заголовок — короткий (до 60 символов).
        - Содержание — 2–4 предложения.
        - В поле "title" титульного слайда ВСЕГДА пиши название презентации.

        Никаких пояснений до или после JSON. Только валидный JSON."""),
        ("user", "{input}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"input": user_request})
    
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if not json_match:
        raise ValueError(f"Текстовик не вернул JSON. Ответ: {response}")
    
    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        raise ValueError(f"Ошибка парсинга JSON текстовика: {e}. Ответ: {response}")
    
    return data

def controller_agent(data: dict) -> dict:
    """Контроллер: проверяет данные от текстовика и исправляет ошибки."""
    print("   🛡️ Контроллер проверяет данные...")
    
    for i, slide in enumerate(data.get("slides", [])):
        visual_type = slide.get("visual_type")
        visual_data = slide.get("visual_data", "")
        
        # Проверяем только промпты для Stable Diffusion
        if visual_type == "generated":
            words = visual_data.split()
            if len(words) > 15:
                print(f"   ⚠️ Контроллер: Слайд {i+1}. Промпт слишком длинный ({len(words)} слов). Прошу текстовика исправить...")
                
                # Формируем промпт для исправления
                fix_prompt = f"""Твой предыдущий промпт для Stable Diffusion был слишком длинным: "{visual_data}".
                Модель понимает максимум 77 токенов (около 15 слов). 
                Перепиши его КОРОЧЕ (не более 10-12 слов), оставив только ключевые теги через запятую.
                Верни ТОЛЬКО новый промпт, без кавычек и пояснений."""
                
                # Отправляем запрос текстовику
                new_prompt_response = llm.invoke(fix_prompt)
                new_prompt = new_prompt_response.content.strip()
                
                # Обновляем данные
                slide["visual_data"] = new_prompt
                print(f"   ✅ Контроллер: Промпт исправлен -> {new_prompt}")
    
    return data

# ============================================================
# 5. АГЕНТ-СБОРЩИК
# ============================================================

def hex_to_rgb(hex_color: str) -> tuple:
    """Преобразует HEX в RGB."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def builder_agent(data: dict, style: dict, filename: str = "presentation.pptx") -> str:
    """Создаёт .pptx с текстом и сгенерированными картинками."""
    
    title_mode = data.get("title_mode", "default")
    first_slide_is_title = data.get("first_slide_is_title", False)
    presentation_title = data.get("presentation_title", "Презентация")
    slides = data.get("slides", [])
    
    # Защита от двойного титульного
    if first_slide_is_title and title_mode == "standard":
        print("   ⚠️ Конфликт флагов. Исправляю: title_mode='none'")
        title_mode = "none"
    
    bg_color = style.get("background_color", "#ffffff")
    text_color = style.get("text_color", "#000000")
    placeholder_color = style.get("placeholder_color", "#cccccc")
    font_name = style.get("font_name", "arial.ttf")
    font_size_body = style.get("font_size_body", 18)
    
    img_dir = "images"
    os.makedirs(img_dir, exist_ok=True)
    
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)
    
    def apply_background(slide):
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(*hex_to_rgb(bg_color))
    
    def apply_text_color(shape):
        if not shape.has_text_frame:
            return
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.color.rgb = RGBColor(*hex_to_rgb(text_color))
    
    slide_counter = 0
    
    if title_mode == "standard":
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        apply_background(slide)
        slide.shapes.title.text = presentation_title
        apply_text_color(slide.shapes.title)
        if len(slide.placeholders) > 1:
            slide.placeholders[1].text = ""
        slide_counter += 1
    
    for i, slide_data in enumerate(slides):
        
        # 1. Титульный слайд (если он первый в списке)
        if first_slide_is_title and i == 0:
            title_text = slide_data.get("title", presentation_title).strip()
            
            slide = prs.slides.add_slide(prs.slide_layouts[0])
            apply_background(slide)
            slide.shapes.title.text = title_text
            apply_text_color(slide.shapes.title)
            
            slide_counter += 1
            continue
        
        # 2. Обычный тематический слайд
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        apply_background(slide)
        title = slide.shapes.title
        
        if title_mode == "default" and i == 0:
            title.text = f"{presentation_title}\n{slide_data.get('title', '')}"
        else:
            title.text = slide_data.get("title", f"Слайд {i+1}")
        
        apply_text_color(title)
        
        # 3. Выбор визуала
        visual_type = slide_data.get("visual_type", "none")
        visual_data = slide_data.get("visual_data", "")
        img_filename = os.path.join(img_dir, f"slide_{i+1}.png") # <-- Привязка к номеру слайда в списке
        
        image_added = False
        
        if visual_type == "generated":
            print(f"   🎨 [SD] Слайд {i+1}: {visual_data}")
            image_agent(visual_data, img_filename, seed=42 + i, color=placeholder_color, font_name=font_name)
            image_added = True
            
        elif visual_type == "stock":
            print(f"   🖼️ [STOCK] Слайд {i+1}: {visual_data}")
            result = stock_agent(visual_data, img_filename)
            if result:
                image_added = True
                
        elif visual_type == "diagram":
            print(f"   📊 [DIAGRAM] Слайд {i+1}: {visual_data}")
            diagram_agent(visual_data, img_filename, bg_color=bg_color, text_color=text_color, font_name=font_name)
            image_added = True
        
        # 4. Вставляем картинку
        if image_added and os.path.exists(img_filename):
            slide.shapes.add_picture(
                img_filename,
                left=Inches(0.5),
                top=Inches(2),
                width=Inches(5)
            )
        
        # 5. Вставляем текст (всегда)
        content = slide_data.get("content", "")
        if content:
            textbox = slide.shapes.add_textbox(
                left=Inches(6),
                top=Inches(2),
                width=Inches(6.5),
                height=Inches(4)
            )
            tf = textbox.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.text = content
            for run in p.runs:
                run.font.size = Pt(font_size_body)
            
            apply_text_color(textbox)
        
        slide_counter += 1
    
    prs.save(filename)
    return f"Презентация сохранена: {filename} ({slide_counter} слайдов, режим: {title_mode})"

# ============================================================
# 6. КООРДИНАТОР
# ============================================================

def coordinator(user_request: str, filename: str = "presentation.pptx") -> str:
    """Координирует работу всех агентов."""
    
    print("🎨 Агент-стилист подбирает оформление...")
    style = stylist_agent(user_request)
    print(f"   ✅ Фон: {style.get('background_color')}")
    print(f"   ✅ Текст: {style.get('text_color')}")
    print(f"   ✅ Шрифт: {style.get('font_name')}")
    
    print("📝 Агент-текстовик генерирует структуру...")
    data = text_agent(user_request)
    
    # ОТЛАДКА: смотрим, что вернул текстовик
    print("\n--- ОТЛАДКА СТРУКТУРЫ СЛАЙДОВ ---")
    for idx, slide in enumerate(data.get("slides", [])):
        print(f"Слайд {idx+1}:")
        print(f"  title: {slide.get('title')}")
        print(f"  content: {slide.get('content', '')[:50]}...")
        print(f"  visual_type: {slide.get('visual_type')}")
        print(f"  visual_data: {slide.get('visual_data')}")
    print("--- КОНЕЦ ОТЛАДКИ ---\n")
    
    print(f"   ✅ title_mode: {data.get('title_mode')}")
    print(f"   ✅ first_slide_is_title: {data.get('first_slide_is_title')}")
    print(f"   ✅ Слайдов в списке: {len(data.get('slides', []))}")
    
    # ВЫЗОВ КОНТРОЛЛЕРА
    data = controller_agent(data)
    
    print("📦 Агент-сборщик собирает .pptx...")
    result = builder_agent(data, style, filename)
    print(f"   ✅ {result}")
    
    return result

# ============================================================
# 7. ЗАПРОС ПОЛЬЗОВАТЕЛЯ
# ============================================================

if __name__ == "__main__":
    user_request = """
    Сделай презентацию для взрослых по сексологии. Титульный лист не нужен. Первый слайд введение что это за область науки. Второй слайд с примером ведущего сексолога и его достижением. Третий слайд с графиком или диаграммой по росту проблем в этой сфере с годами (количество обращений от года к году). Четвертый слайд - строение женских и мужских половых органов с текстом о принципиальном отличии биологическом. Пятый слайд что-то о пользе науки и прогнозе ее развития. На всех слайдах текст ориентированный на взрослого, 6-7 предложений. Фон и цвет подобрать максимально концентрирующий внимание на презентации
    """
        
    print("🤖 Мультиагент презентаций запущен!")
    print("=" * 50)
        
    # Вот этой строки не хватало!
    result = coordinator(user_request, filename="space_presentation.pptx")
        
    print("=" * 50)
    print(f"🎉 Готово! {result}")
