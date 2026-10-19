import re
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ============================================================
# 1. ИНСТРУМЕНТЫ АГЕНТА
# ============================================================

def calculator(expression: str) -> str:
	"""Вычисляет математическое выражение. Вводи как '15*23'."""
	clean = re.sub(r'[^0-9+\-*/().]', '', expression)
	try:
		result = eval(clean)
		return f"Результат: {result}"
	except Exception:
		return "Ошибка: неверное выражение."

def save_to_file(text: str) -> str:
	"""Сохраняет текст в файл result.txt."""
	try:
		with open("result.txt", "w", encoding="utf-8") as f:
			f.write(text)
		return "Сохранено в файл result.txt"
	except Exception as e:
		return f"Ошибка: {e}"

# ============================================================
# 2. ПОДКЛЮЧАЕМ МОДЕЛЬ (Gemma-4-E4B-Uncensored)
# ============================================================

llm = ChatOllama(
	model="hf.co/HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive:Q4_K_M",
	temperature=0.1,
    base_url="http://127.0.0.1:11434"
)

# ============================================================
# 3. ПРОМПТ ДЛЯ АГЕНТА
# ============================================================

prompt = ChatPromptTemplate.from_messages([
	("system", """Ты — умный помощник. У тебя есть два инструмента:

1. calculator — для вычислений.
2. save_to_file — для сохранения текста в файл.

Если пользователь просит вычислить — используй calculator.
Если просит сохранить текст — используй save_to_file.

Чтобы вызвать инструмент, верни ответ строго в формате:
ACTION: имя_инструмента
INPUT: данные для инструмента

Например:
ACTION: calculator
INPUT: 15*23

Если инструмент не нужен, просто ответь текстом."""),
	("user", "{input}")
])

chain = prompt | llm | StrOutputParser()

# ============================================================
# 4. ФУНКЦИЯ-ДИСПЕТЧЕР (обрабатывает ответ модели)
# ============================================================

def agent_process(question: str) -> str:
	response = chain.invoke({"input": question})

	if "ACTION:" in response and "INPUT:" in response:
		action_match = re.search(r"ACTION:\s*(.+)", response)
		input_match = re.search(r"INPUT:\s*(.+)", response)

		if action_match and input_match:
			action = action_match.group(1).strip()
			inp = input_match.group(1).strip()

			if action == "calculator":
				result = calculator(inp)
			elif action == "save_to_file":
				result = save_to_file(inp)
			else:
				result = "Неизвестное действие."

			final_prompt = ChatPromptTemplate.from_messages([
				("system", "Вот результат действия: {result}. Кратко ответь пользователю."),
				("user", "{input}")
			])
			final_chain = final_prompt | llm | StrOutputParser()
			return final_chain.invoke({"input": question, "result": result})

	return response

# ============================================================
# 5. ЗАПУСК
# ============================================================

if __name__ == "__main__":
	print("🤖 Агент запущен!")
	print("-" * 40)

	question1 = "Сколько будет 15 умножить на 23?"
	print(f"Q: {question1}")
	print(f"A: {agent_process(question1)}")

	print("-" * 40)

	question2 = "Сохрани фразу 'Привет, мир!' в файл"
	print(f"Q: {question2}")
	print(f"A: {agent_process(question2)}")
