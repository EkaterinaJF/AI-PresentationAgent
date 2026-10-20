from ddgs import DDGS

with DDGS() as ddgs:
    results = ddgs.images("схема солнечной системы", max_results=5)
    for r in results:
        print(r.get('image'))