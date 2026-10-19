import os
import requests

# User-Agent — обязателен для Wikimedia API
HEADERS = {
    "User-Agent": "PresentationAgent/1.0 (https://github.com/EkaterinaJF; contact: ekaterina.basilisk@gmail.com)"
}

def stock_agent(query: str, filename: str) -> str:
    """Ищет изображение на Wikimedia Commons и скачивает его."""
    
    api_url = "https://commons.wikimedia.org/w/api.php"
    
    # Шаг 1: поиск файлов
    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": 6,  # File namespace
        "srlimit": 5,      # первые 5 результатов
        "format": "json"
    }
    
    try:
        response = requests.get(api_url, params=search_params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"   ⚠️ Ошибка поиска Wikimedia: {e}")
        return None
    
    results = data.get("query", {}).get("search", [])
    if not results:
        print(f"   ⚠️ Ничего не найдено на Wikimedia по запросу: {query}")
        return None
    
    # Берём первый результат
    title = results[0]["title"]  # например "File:Solar system.jpg"
    
    # Шаг 2: получаем URL картинки
    info_params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "format": "json"
    }
    
    try:
        response = requests.get(api_url, params=info_params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        info_data = response.json()
    except Exception as e:
        print(f"   ⚠️ Ошибка получения URL: {e}")
        return None
    
    pages = info_data.get("query", {}).get("pages", {})
    for page in pages.values():
        imageinfo = page.get("imageinfo", [])
        if not imageinfo:
            continue
        
        info = imageinfo[0]
        mime = info.get("mime", "")
        url = info.get("url")
        
        # Пропускаем не-картинки (аудио, видео, pdf)
        if not mime.startswith("image/"):
            print(f"   ⚠️ Первый результат не картинка ({mime}), пропускаю")
            continue
        
        # Скачиваем
        try:
            img_response = requests.get(url, headers=HEADERS, timeout=30)
            img_response.raise_for_status()
            with open(filename, "wb") as f:
                f.write(img_response.content)
            print(f"   ✅ Скачано с Wikimedia: {title}")
            return filename
        except Exception as e:
            print(f"   ⚠️ Ошибка скачивания: {e}")
            return None
    
    return None
if __name__ == "__main__":
    stock_agent("solar system diagram", "test_wikimedia.png")
