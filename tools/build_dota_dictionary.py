import json
import re
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

URLS = {
    "ru": (
        "https://raw.githubusercontent.com/"
        "muk-as/DOTA2_CLIENT/master/"
        "game/dota/pak01_dir/resource/localization/"
        "dota_russian.txt"
    ),
    "heroes": (
        "https://raw.githubusercontent.com/"
        "odota/dotaconstants/master/build/heroes.json"
    ),
    "items": (
        "https://raw.githubusercontent.com/"
        "odota/dotaconstants/master/build/items.json"
    ),
    "abilities": (
        "https://raw.githubusercontent.com/"
        "odota/dotaconstants/master/build/hero_abilities.json"
    ),
}


WORD_RE = re.compile(
    r"[A-Za-zА-Яа-яЁё]+(?:[-'][A-Za-zА-Яа-яЁё]+)*"
)


def download(url: str) -> bytes:
    print(f"Скачиваю: {url}")
    with urllib.request.urlopen(url) as response:
        return response.read()


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass

    return data.decode("utf-8", errors="ignore")


def extract_words(text: str):
    return {
        word.strip("-'").lower()
        for word in WORD_RE.findall(text)
        if len(word.strip("-'")) >= 2
    }


full_lexicon = set()
dota_terms = set()


# ============================================================
# Русская локализация клиента
# ============================================================

ru_text = decode_text(
    download(URLS["ru"])
)

pairs = re.findall(
    r'^\s*"([^"]+)"\s+"((?:\\.|[^"])*)"',
    ru_text,
    flags=re.MULTILINE,
)

interesting_keys = (
    "hero",
    "item",
    "ability",
    "facet",
    "rune",
    "ward",
    "roshan",
    "courier",
    "neutral",
    "aegis",
    "tormentor",
    "lotus",
)

for key, value in pairs:
    value = (
        value
        .replace("\\n", " ")
        .replace('\\"', '"')
    )

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = re.sub(
        r"\{[^}]+\}",
        " ",
        value,
    )

    words = extract_words(value)

    full_lexicon.update(words)

    if (
        any(part in key.lower() for part in interesting_keys)
        and len(value) <= 100
        and len(words) <= 10
    ):
        dota_terms.update(words)


# ============================================================
# OpenDota structured data
# ============================================================

heroes = json.loads(
    download(URLS["heroes"])
)

items = json.loads(
    download(URLS["items"])
)

abilities = json.loads(
    download(URLS["abilities"])
)


def add_name(value):
    if not isinstance(value, str):
        return

    cleaned = (
        value
        .replace("npc_dota_hero_", "")
        .replace("item_", "")
        .replace("_", " ")
    )

    words = extract_words(cleaned)

    full_lexicon.update(words)
    dota_terms.update(words)


for hero in heroes.values():
    add_name(hero.get("localized_name"))
    add_name(hero.get("name"))


for item in items.values():
    if not isinstance(item, dict):
        continue

    add_name(item.get("dname"))
    add_name(item.get("name"))


def walk(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in (
                "name",
                "title",
                "localized_name",
                "dname",
            ):
                add_name(value)

            walk(value)

    elif isinstance(obj, list):
        for value in obj:
            walk(value)


walk(abilities)


# ============================================================
# Русскоязычный Dota-сленг
# ============================================================

slang = {
    "вард",
    "варды",
    "сентри",
    "обсервер",
    "обс",
    "смок",
    "смоки",
    "байбек",
    "бкб",
    "тп",
    "мид",
    "топ",
    "бот",
    "хард",
    "оффлейн",
    "саппорт",
    "сап",
    "керри",
    "ганг",
    "ганк",
    "пуш",
    "депуш",
    "фарм",
    "фармить",
    "крип",
    "крипы",
    "ластхит",
    "денай",
    "роша",
    "рошан",
    "аегис",
    "шард",
    "лотус",
    "торментор",
    "терзатель",
    "глиф",
    "блинк",
    "даггер",
    "аганим",
    "аганимс",
    "рефрешер",
    "ульта",
    "ульт",
    "мана",
    "хп",
    "инвиз",
    "стан",
    "сайленс",
    "рут",
    "дизарм",
    "бара",
    "пудж",
    "сф",
    "цмка",
    "ам",
    "па",
    "войд",
    "инвокер",
    "тинкер",
    "морф",
    "джагер",
    "джаггер",
    "акс",
    "скай",
    "лина",
    "лион",
    "шейкер",
    "рубик",
    "снайпер",
    "течис",
}

full_lexicon.update(slang)
dota_terms.update(slang)


aliases = {
    "ворд": "вард",
    "ворды": "варды",
    "вордов": "вардов",

    "байбэк": "байбек",
    "бай бэк": "байбек",
    "бай бек": "байбек",

    "бэкэбэ": "БКБ",
    "бкб": "БКБ",

    "тэ пэ": "ТП",
    "тп": "ТП",

    "рошан": "Рошан",
    "роша": "Роша",

    "аганимс": "Аганим",
    "аганим": "Аганим",

    "дагер": "даггер",

    "сапорт": "саппорт",
    "саппорт": "саппорт",

    "кери": "керри",
    "керри": "керри",

    "ласт хит": "ластхит",
    "ластхит": "ластхит",

    "торментор": "Торментор",
    "терзатель": "Терзатель",
}


(DATA / "dota_lexicon.txt").write_text(
    "\n".join(sorted(full_lexicon)),
    encoding="utf-8",
)

(DATA / "dota_terms.txt").write_text(
    "\n".join(sorted(dota_terms)),
    encoding="utf-8",
)

(DATA / "dota_aliases.json").write_text(
    json.dumps(
        aliases,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


print()
print(f"Полный словарь: {len(full_lexicon)} слов")
print(f"Dota-термины: {len(dota_terms)} слов")
print(f"Aliases: {len(aliases)}")
