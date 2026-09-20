from src.text.translator import EnglishTranslator

TESTS = [
    "Поставьте варды на миду.",
    "У них нет байбека.",
    "Идем на Рошана.",
    "У Пуджа нет ульты.",
    "Керри фармит бот.",
    "Дайте смок и пойдем мид.",
    "Не деритесь без меня.",
    "У меня нет БКБ.",
    "Дефайте базу.",
    "Используйте глиф.",
    "Пудж, купи сентри.",
    "Алло, блять, Пудж.",
    "О, боже мой, долбаеб.",
]

translator = EnglishTranslator()

print()
print("=" * 90)
print("Dota2voice2text translation quality test")
print("=" * 90)

worst = 0.0

for source in TESTS:
    translated, elapsed = translator.translate(source)
    worst = max(worst, elapsed)
    print(f"\nRU: {source}")
    print(f"EN: {translated}")
    print(f"TIME: {elapsed:.3f}s")

print()
print("=" * 90)
print(f"WORST: {worst:.3f}s")
print("=" * 90)
