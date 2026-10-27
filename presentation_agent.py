import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import json
import re
import io
import requests
import torch
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from diffusers import StableDiffusionPipeline, AutoencoderKL
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from ddgs import DDGS

# ============================================================
# 1. НАСТРОЙКА МОДЕЛИ (LLM)
# ============================================================

llm = ChatOllama(
    model="hf.co/HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive:Q4_K_M",
    base_url="http://127.0.0.1:11434",
    temperature=0.3
)

# ============================================================
# 2. ГЕНЕРАТОР КАРТИНОК (Stable Diffusion)
# ============================================================

USE_CUDA = torch.cuda.is_available()
pipe = None

USE_CUDA = torch.cuda.is_available()
_pipe = None

def get_pipe():
    """Ленивая загрузка модели Stable Diffusion (только при первом использовании)."""
    global _pipe
    if _pipe is not None:
        return _pipe
    
    if not USE_CUDA:
        return None
        
    print("🎨 CUDA доступна. Загрузка VAE и модели Stable Diffusion...")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    VAE_PATH = os.path.join(BASE_DIR, "vae", "vae-ft-mse-840000-ema-pruned.safetensors")
    
    vae = AutoencoderKL.from_single_file(VAE_PATH, torch_dtype=torch.float16)
    _pipe = StableDiffusionPipeline.from_pretrained(
        "SG161222/Realistic_Vision_V5.1_noVAE",
        vae=vae,
        torch_dtype=torch.float16,
        safety_checker=None
    )
    _pipe.enable_model_cpu_offload()
    _pipe.enable_attention_slicing()
    return _pipe

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
    """Генерирует картинку через SD или рисует цветную заглушку, если GPU нет."""
    pipe = get_pipe()
    if pipe:
        # генерация...
        image = pipe(
            prompt=prompt,
            negative_prompt=NEGATIVE_PROMPT,
            num_inference_steps=25,
            guidance_scale=7.0,
            height=512,
            width=512,
            generator=torch.Generator(device="cuda").manual_seed(seed)
        ).images[0]
        image.save(filename)
        return filename
    
    # Fallback: заглушка
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

# ============================================================
# 3. ПОИСК КАРТИНОК (Stock)
# ============================================================

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
				# --- ФИЛЬТР МАГАЗИНОВ ---
                blocked_domains = ["ozon.ru", "wildberries.ru", "avito.ru", "market.yandex.ru", "aliexpress.ru"]
                if any(domain in url for domain in blocked_domains):
                    print(f"   ⚠️ [STOCK] Пропускаю магазин: {url[:50]}...")
                    continue
                # -------------------------
                try:
                    img_response = requests.get(url, timeout=30)
                    img_response.raise_for_status()
                    content_type = img_response.headers.get("Content-Type", "")
                    if not content_type.startswith("image/"):
                        continue
                    
                    img = Image.open(io.BytesIO(img_response.content))
                    img = img.convert("RGB")
                    img.save(filename, "PNG")
                    
                    print(f"   ✅ [STOCK] Скачано: {url[:60]}...")
                    return filename
                except Exception as e:
                    print(f"   ⚠️ [STOCK] Ошибка с ссылкой: {e}")
                    continue
            print(f"   ⚠️ [STOCK] Не удалось скачать картинку: {query}")
            return None
    except Exception as e:
        print(f"   ⚠️ [STOCK] Ошибка поиска: {e}")
        return None

# ============================================================
# 4. ПОСТРОЕНИЕ ГРАФИКОВ (Diagram)
# ============================================================

def _clean_numeric_data(data_list: list) -> list:
    """Вспомогательная функция: очищает данные от процентов и строк."""
    clean_list = []
    for val in data_list:
        if isinstance(val, str):
            val = val.replace("%", "").replace(" ", "").strip()
            try:
                val = float(val)
            except ValueError:
                val = 0
        clean_list.append(val)
    return clean_list

def diagram_agent(data: dict, filename: str, bg_color: str = "#ffffff", text_color: str = "#000000", font_name: str = "arial.ttf"):
    """Рисует график. Для line/bar возвращает PNG, для pie — возвращает данные для pptx."""
    
    chart_type = data.get("chart_type", "bar")
    title = data.get("title", "График")
    print(f"   📊 [DIAGRAM] Обработка графика: {title} ({chart_type})")

    # Если это круговая диаграмма, отдаем данные для нативного pptx
    if chart_type == "pie":
        return data

    # Для line и bar рисуем через matplotlib
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['text.color'] = text_color
    plt.rcParams['axes.labelcolor'] = text_color
    plt.rcParams['xtick.color'] = text_color
    plt.rcParams['ytick.color'] = text_color
    plt.rcParams['axes.edgecolor'] = text_color

    fig, ax = plt.subplots(figsize=(8, 6), facecolor=bg_color)
    ax.set_facecolor(bg_color)

    x_label = data.get("x_label", "")
    y_label = data.get("y_label", "")
    categories = data.get("categories", [])
    series = data.get("series", [])
    
    # Обратная совместимость
    if not series and "x_data" in data and "y_data" in data:
        categories = data["x_data"]
        series = [{"name": "Данные", "data": data["y_data"]}]

    if not categories or not series:
        ax.text(0.5, 0.5, "Нет данных для графика", ha='center', va='center', fontsize=20, color=text_color, transform=ax.transAxes)
    else:
        clean_series = []
        for s in series:
            clean_series.append({
                "name": s.get("name", "Серия"), 
                "data": _clean_numeric_data(s.get("data", []))
            })

        if chart_type == "line":
            for s in clean_series:
                ax.plot(categories, s["data"], marker='o', label=s["name"], linewidth=2)
            ax.legend(facecolor=bg_color, edgecolor=text_color, labelcolor=text_color)
        else: # bar
            x = np.arange(len(categories))
            width = 0.8 / len(clean_series)
            for i, s in enumerate(clean_series):
                offset = (i - len(clean_series)/2 + 0.5) * width
                bars = ax.bar(x + offset, s["data"], width, label=s["name"])
                for bar in bars:
                    yval = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2, yval, str(int(yval)) if yval.is_integer() else str(yval), ha='center', va='bottom', fontsize=9, color=text_color)
            ax.set_xticks(x)
            ax.set_xticklabels(categories)
            ax.legend(facecolor=bg_color, edgecolor=text_color, labelcolor=text_color)

        ax.set_title(title, fontsize=14, color=text_color)
        ax.set_xlabel(x_label, fontsize=10)
        ax.set_ylabel(y_label, fontsize=10)

    plt.tight_layout()
    plt.savefig(filename, dpi=100, facecolor=bg_color)
    plt.close(fig)
    print(f"   ✅ [DIAGRAM] Сохранено как картинка: {filename}")
    return filename

# ============================================================
# 5. АГЕНТ-СТИЛИСТ
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
            "font_size_body": 18,
            "style_prompt": "общий стиль для картинок (на английском)"
        }}

        ПРАВИЛО для style_prompt:
        - Опиши общий визуальный стиль презентации на английском (например, "photorealistic, cinematic, dark cosmic", "flat vector, bright colors, cartoon", "minimalist, clean, corporate").

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
# 6. АГЕНТ-ТЕКСТОВИК
# ============================================================

def text_agent(user_request: str) -> dict:
    """Генерирует структуру презентации с английскими промптами для картинок."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Ты — генератор презентаций. Твоя задача — вернуть JSON.

        Формат ответа:
        {{
            "title_mode": "default" | "none" | "standard",
            "first_slide_is_title": true | false,
            "presentation_title": "Название презентации",
            "title_slide_content": "Автор, город, дата (если указаны)",
            "slides": [
                {{"title": "Заголовок", "content": "Текст", "visual_type": "generated|stock|diagram|none", "visual_data": "данные"}}
            ]
        }}

        ПРАВИЛА ДЛЯ ТИТУЛЬНОГО ЛИСТА:
        1. Если пользователь НЕ говорил про титульный лист:
           → title_mode: "default", first_slide_is_title: false
           (Если указан автор/город, запиши их в title_slide_content. Если НЕ указан — оставь пустую строку "").

        2. Если пользователь перечислил слайды и ПЕРВЫЙ из них — «титульный»:
           → title_mode: "none", first_slide_is_title: true
           (Если указан автор/город, запиши их в title_slide_content. Если НЕ указан — оставь пустую строку "").

        3. Если пользователь ОТДЕЛЬНО просит титульный, а темы идут с 1-го:
           → title_mode: "standard", first_slide_is_title: false
           (Если указан автор/город, запиши их в title_slide_content. Если НЕ указан — оставь пустую строку "").

        4. Если пользователь сказал «без титульного»:
           → title_mode: "none", first_slide_is_title: false
           (title_slide_content оставь пустым).

        ПРАВИЛА ДЛЯ СЛАЙДОВ:
        - Заголовки: до 9 слов, без точек и двоеточий.
        - content: Если пользователь указал количество предложений на слайд (например, "по 2-4 предложения"), СТРОГО следуй этому. Если не указал — пиши 6-7 предложений.
        - visual_type: 
          - "generated" — художественная картинка (промпт на английском, до 10 слов).
          - "stock" — точная схема/портрет (запрос на русском).
          - "diagram" — график (объект с chart_type, title, categories, series).
          - "none" — без картинки.

        ВАЖНОЕ ПРАВИЛО ДЛЯ ДЕТЕЙ:
        - Если аудитория — дети (малыши, школьники), НЕ ИСПОЛЬЗУЙ visual_type: "diagram". 

          Вместо графиков используй "generated" (картинки) или "none" (только текст).
        Верни ТОЛЬКО валидный JSON, без пояснений."""),
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

# ============================================================
# 7. КОНТРОЛЛЕР (Проверка данных)
# ============================================================

def controller_agent(data: dict, user_request: str = "") -> dict:
    """Контроллер: проверяет данные от текстовика и исправляет ошибки."""
    print("   🛡️ Контроллер проверяет данные...")
    
    # --- ПРОВЕРКА ЛОГИЧЕСКОГО КОНФЛИКТА ТИТУЛЬНОГО ---
    title_mode = data.get("title_mode")
    first_slide_is_title = data.get("first_slide_is_title")
    
    if title_mode == "standard" and first_slide_is_title:
        print("   ⚠️ Контроллер: Конфликт! title_mode='standard' и first_slide_is_title=True одновременно.")
        print("   🔧 Исправляю: отключаю first_slide_is_title и удаляю дублирующий слайд.")
        data["first_slide_is_title"] = False
        if data.get("slides"):
            data["slides"].pop(0)
    # ---------------------------------------------------

    # --- ОПРЕДЕЛЯЕМ, ДЕТСКАЯ ЛИ ЭТО ПРЕЗЕНТАЦИЯ ---
    is_kids_presentation = any(word in user_request.lower() for word in ["малыш", "ребен", "дет", "школьник"])
    
    for i, slide in enumerate(data.get("slides", [])):
        visual_type = slide.get("visual_type")
        visual_data = slide.get("visual_data", "")
        
        # --- ЗАПРЕТ ГРАФИКОВ ДЛЯ ДЕТЕЙ ---
        if is_kids_presentation and visual_type == "diagram":
            print(f"   ⚠️ Контроллер: Слайд {i+1}. Детская презентация не должна содержать графиков. Меняю на картинку.")
            slide["visual_type"] = "generated"
            slide["visual_data"] = "cute cartoon illustration, bright colors, for kids"
        # ---------------------------------
        
        # Проверяем только промпты для Stable Diffusion
        if slide["visual_type"] == "generated":
            words = visual_data.split()
            if len(words) > 15:
                print(f"   ⚠️ Контроллер: Слайд {i+1}. Промпт слишком длинный ({len(words)} слов). Прошу текстовика исправить...")
                fix_prompt = f"""Твой предыдущий промпт для Stable Diffusion был слишком длинным: "{visual_data}".
                Модель понимает максимум 77 токенов (около 15 слов). 
                Перепиши его КОРОЧЕ (не более 10-12 слов), оставив только ключевые теги через запятую.
                Верни ТОЛЬКО новый промпт, без кавычек и пояснений."""
                new_prompt_response = llm.invoke(fix_prompt)
                new_prompt = new_prompt_response.content.strip()
                slide["visual_data"] = new_prompt
                print(f"   ✅ Контроллер: Промпт исправлен -> {new_prompt}")
    
    return data

# ============================================================
# 8. АГЕНТ-СБОРЩИК
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
    
    bg_color = style.get("background_color", "#ffffff")
    text_color = style.get("text_color", "#000000")
    placeholder_color = style.get("placeholder_color", "#cccccc")
    font_name = style.get("font_name", "arial.ttf")
    
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
    
    # ========================================================
    # 1. ПРОВЕРКА НАЛИЧИЯ ТИТУЛЬНОГО ЛИСТА
    # ========================================================
    
    title_slide_content = data.get("title_slide_content", "")
    
    # 1.1. Титульный лист по умолчанию (default) или отдельный (standard)
    if title_mode in ["default", "standard"]:
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        apply_background(slide)
        slide.shapes.title.text = presentation_title
        apply_text_color(slide.shapes.title)
        
        if len(slide.placeholders) > 1:
            slide.placeholders[1].text = title_slide_content
            apply_text_color(slide.placeholders[1])
                
        slide_counter += 1

    # 1.2. Титульный лист уже включен в список слайдов пользователем (first_slide_is_title)
    elif first_slide_is_title and slides:
        slide_data = slides.pop(0)
        title_text = slide_data.get("title", presentation_title).strip()
        
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        apply_background(slide)
        slide.shapes.title.text = title_text
        apply_text_color(slide.shapes.title)
        
        if len(slide.placeholders) > 1:
            slide.placeholders[1].text = title_slide_content
            apply_text_color(slide.placeholders[1])
            
        slide_counter += 1
    
    # ========================================================
    # 2. ОСНОВНОЙ ЦИКЛ ПО СЛАЙДАМ (только контент)
    # ========================================================
    
    for i, slide_data in enumerate(slides):
        
        # 2.1. Создание обычного тематического слайда
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        apply_background(slide)
        title = slide.shapes.title
        
        title.left = Inches(0.5)
        title.top = Inches(0.2)
        title.width = Inches(12.33)
        title.height = Inches(1.2)
        
        title.text = slide_data.get("title", f"Слайд {i+1}")
        apply_text_color(title)
        
        # 2.1.1. Динамический шрифт заголовка
        title_text_len = len(slide_data.get("title", ""))
        title_font_size = 36
        if title_text_len > 45:
            title_font_size = 28
        elif title_text_len > 35:
            title_font_size = 32
            
        for paragraph in title.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(title_font_size)
        
        # 2.2. Выбор визуала
        visual_type = slide_data.get("visual_type", "none")
        visual_data = slide_data.get("visual_data", "")
        img_filename = os.path.join(img_dir, f"slide_{i+1}.png")
        image_added = False
        
        if visual_type == "generated":
            style_prompt = style.get("style_prompt", "")
            full_prompt = f"{visual_data}, {style_prompt}" if style_prompt else visual_data
            
            print(f"   🎨 [SD] Слайд {i+1}: {full_prompt[:60]}...")
            image_agent(full_prompt, img_filename, seed=42 + i, color=placeholder_color, font_name=font_name)
            image_added = True
            
        elif visual_type == "stock":
            print(f"   🖼️ [STOCK] Слайд {i+1}: {visual_data}")
            result = stock_agent(visual_data, img_filename)
            if result:
                image_added = True
                
        elif visual_type == "diagram":
            print(f"   📊 [DIAGRAM] Слайд {i+1}: {visual_data.get('title', 'График')}")
            result = diagram_agent(visual_data, img_filename, bg_color=bg_color, text_color=text_color, font_name=font_name)
            
            if isinstance(result, dict): # Нативная круговая диаграмма
                chart_data = CategoryChartData()
                chart_data.categories = result["categories"]
                clean_data = _clean_numeric_data(result["series"][0]["data"])
                chart_data.add_series(result["series"][0]["name"], clean_data)
                
                x, y, cx, cy = Inches(0.5), Inches(1.5), Inches(5), Inches(5)
                graphic_frame = slide.shapes.add_chart(XL_CHART_TYPE.PIE, x, y, cx, cy, chart_data)
                chart = graphic_frame.chart
                chart.has_title = True
                chart.chart_title.text_frame.text = result["title"]
                
                plot = chart.plots[0]
                plot.has_data_labels = True
                data_labels = plot.data_labels
                data_labels.show_percentage = True
                data_labels.show_category_name = True
                data_labels.show_value = False
                image_added = False
            else:
                image_added = True
        
        # 2.3. Вставка картинки (с сохранением пропорций)
        if image_added and os.path.exists(img_filename):
            try:
                img = Image.open(img_filename)
                img_w, img_h = img.size
                max_size = 5.0
                
                if img_w > img_h:
                    final_width = max_size
                    final_height = max_size * (img_h / img_w)
                else:
                    final_height = max_size
                    final_width = max_size * (img_w / img_h)
                
                slide.shapes.add_picture(
                    img_filename,
                    left=Inches(0.5),
                    top=Inches(1.5),
                    width=Inches(final_width),
                    height=Inches(final_height)
                )
            except Exception as e:
                print(f"   ⚠️ Не удалось обработать картинку: {e}")
        
        # 2.4. Вставка текста (всегда)
        content = slide_data.get("content", "")
        if content:
            base_size = 24 
            actual_font_size = base_size
            
            if len(content) > 400:
                actual_font_size = max(18, base_size - 4)
            elif len(content) > 250:
                actual_font_size = max(20, base_size - 2)
            
            textbox = slide.shapes.add_textbox(
                left=Inches(6),
                top=Inches(1.5),
                width=Inches(6.5),
                height=Inches(5.5)
            )
            tf = textbox.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = 3
            
            p = tf.paragraphs[0]
            p.text = content
            for run in p.runs:
                run.font.size = Pt(actual_font_size)
            
            apply_text_color(textbox)
        
        slide_counter += 1
    
    prs.save(filename)
    return f"Презентация сохранена: {filename} ({slide_counter} слайдов, режим: {title_mode})"

# ============================================================
# 9. КООРДИНАТОР
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
    
    print(f"   ✅ title_mode: {data.get('title_mode')}")
    print(f"   ✅ first_slide_is_title: {data.get('first_slide_is_title')}")
    print(f"   ✅ title_slide_content: {data.get('title_slide_content')}") # <-- ВОТ ЭТА СТРОКА
    print(f"   ✅ Слайдов в списке: {len(data.get('slides', []))}")
    
    data = controller_agent(data, user_request)
    
    print("📦 Агент-сборщик собирает .pptx...")
    result = builder_agent(data, style, filename)
    print(f"   ✅ {result}")
    
	    # Сохраняем данные для превью в Streamlit
    import json
    with open("presentation_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
		
    return result


