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

print("🎨 Загрузка VAE...")
vae = AutoencoderKL.from_single_file(
    "F:/workspace/AI/PresentationAgent/vae/vae-ft-mse-840000-ema-pruned.safetensors",
    torch_dtype=torch.float16
)

print("🎨 Загрузка модели Realistic Vision V5.1...")
pipe = StableDiffusionPipeline.from_pretrained(
    "SG161222/Realistic_Vision_V5.1_noVAE",
    vae=vae,
    torch_dtype=torch.float16,
    safety_checker=None
)
pipe.enable_model_cpu_offload()
pipe.enable_attention_slicing()

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

def image_agent(prompt: str, filename: str, seed: int = 42) -> str:
    """Генерирует картинку по промпту."""
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
                    "image_prompt": "english prompt for image generation"
                }},
                ...
            ]
        }}
        ЛОГИКА (взаимоисключающая):

        Случай 1: Первая тема в списке — «титульный».
        → title_mode: "none", first_slide_is_title: true
        → Титульный УЖЕ в списке. Отдельный НЕ добавляй.

        Случай 2: Темы + ОТДЕЛЬНО просят титульный.
        → title_mode: "standard", first_slide_is_title: false
        → В списке ТОЛЬКО тематические слайды.

        Случай 3: Про титульный ничего не сказано.
        → title_mode: "default", first_slide_is_title: false

        Случай 4: Сказано «без титульного».
        → title_mode: "none", first_slide_is_title: false

        КРИТИЧЕСКОЕ ПРАВИЛО:
        - first_slide_is_title=true и title_mode="standard" НЕ МОГУТ быть одновременно.
        - Если first_slide_is_title=true, то title_mode ОБЯЗАН быть "none".

        ПРАВИЛА для slides:
        - Ровно столько слайдов, сколько просит пользователь.
        - Заголовок — короткий (до 60 символов).
        - Содержание — 2–4 предложения.
        - image_prompt — ВАЖНО: пиши на АНГЛИЙСКОМ, 5–10 слов, 
          описывающих визуальную сцену для Stable Diffusion.
          Например: "space, planets, stars, cosmic, digital art" 
          или "nature, forest, green, sunlight, realistic".

        ПРАВИЛО для титульного слайда:
        - В поле "title" титульного слайда ВСЕГДА пиши название презентации.
        - В поле "content" — только подпись (автор, город, дата), если пользователь её указал.
        - Если подписи нет — content = "". 

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
        
        # Титульный слайд из списка
        if first_slide_is_title and i == 0:
            title_text = slide_data.get("title", presentation_title).strip()
            content_text = slide_data.get("content", "").strip()
            
            # Если title пустой или общий, а content содержит название — меняем местами
            if (not title_text or title_text.lower() in ["титульный слайд", "титул", "title slide"]) and content_text:
                title_text = content_text
                content_text = ""
            
            slide = prs.slides.add_slide(prs.slide_layouts[0])
            apply_background(slide)
            slide.shapes.title.text = title_text
            apply_text_color(slide.shapes.title)
            
            if len(slide.placeholders) > 1:
                if content_text and content_text != title_text:
                    slide.placeholders[1].text = content_text
                    apply_text_color(slide.placeholders[1])
            
            slide_counter += 1
            continue
        
        # Обычный тематический слайд
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        apply_background(slide)
        title = slide.shapes.title
        
        if title_mode == "default" and i == 0:
            title.text = f"{presentation_title}\n{slide_data.get('title', '')}"
        else:
            title.text = slide_data.get("title", f"Слайд {i+1}")
        
        apply_text_color(title)
        
        # ГЕНЕРАЦИЯ КАРТИНКИ
        image_prompt = slide_data.get("image_prompt", "abstract background")
        img_filename = os.path.join(img_dir, f"slide_{slide_counter+1}.png")
        print(f"   🎨 Генерация картинки для слайда {slide_counter+1}: {image_prompt}")
        image_agent(image_prompt, img_filename, seed=42 + slide_counter)
        
        if os.path.exists(img_filename):
            slide.shapes.add_picture(
                img_filename,
                left=Inches(0.5),
                top=Inches(2),
                width=Inches(5)
            )
        
        # Текст
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
    print(f"   ✅ title_mode: {data.get('title_mode')}")
    print(f"   ✅ first_slide_is_title: {data.get('first_slide_is_title')}")
    print(f"   ✅ Слайдов в списке: {len(data.get('slides', []))}")
    
    print("📦 Агент-сборщик собирает .pptx...")
    result = builder_agent(data, style, filename)
    print(f"   ✅ {result}")
    
    return result

# ============================================================
# 7. ЗАПРОС ПОЛЬЗОВАТЕЛЯ
# ============================================================

if __name__ == "__main__":
    user_request = """
    Сделай презентацию про космос, 5 слайдов.
    Стиль: научно-популярный, для школьников.
    Темы слайдов:
    1. Титульный — "Космос: бесконечный мир"
    2. Что такое космос
    3. Планеты Солнечной системы
    4. Звёзды и галактики
    5. Заключение — почему космос важен
    """
    
    print("🤖 Мультиагент презентаций запущен!")
    print("=" * 50)
    
    result = coordinator(user_request, filename="space_presentation.pptx")
    
    print("=" * 50)
    print(f"🎉 Готово! {result}")
