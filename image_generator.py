import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import torch
from diffusers import StableDiffusionPipeline, AutoencoderKL

# Загружаем VAE из локального файла
print("Загрузка VAE...")
vae = AutoencoderKL.from_single_file(
    "F:/workspace/AI/PresentationAgent/vae/vae-ft-mse-840000-ema-pruned.safetensors",
    torch_dtype=torch.float16
)

# Загружаем модель Realistic Vision
print("Загрузка модели Realistic Vision V5.1...")
pipe = StableDiffusionPipeline.from_pretrained(
    "SG161222/Realistic_Vision_V5.1_noVAE",
    vae=vae,
    torch_dtype=torch.float16,
    safety_checker=None
)

# Оптимизация для 6 ГБ VRAM
pipe.enable_model_cpu_offload()
pipe.enable_attention_slicing()

# Рекомендованный негативный промпт из карточки модели
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

def generate_image(prompt: str, filename: str, seed: int = 42):
    """Генерирует картинку по промпту и сохраняет в файл."""
    
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
    print(f"   ✅ Сохранено: {filename}")
    return filename

if __name__ == "__main__":
    print("Генерация тестовых картинок...")
    
    generate_image(
        "two happy children playing in a sunny park, photorealistic, detailed faces, sharp focus, natural lighting, 8k",
        "test_children_rv.png",
        seed=42
    )
    
    generate_image(
    "two workers in orange vests, standing on a road, portrait, photorealistic, detailed faces, sharp focus, natural lighting, 8k",
    "test_workers_rv.png",
    seed=123
    )
    
    generate_image(
        "portrait of a young woman, photorealistic, detailed face, sharp focus, natural lighting, 8k",
        "test_portrait_rv.png",
        seed=456
    )
    
    print("Готово!")
