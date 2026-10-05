SYMBOLS = "ㄅㄆㄇㄈㄉㄊㄋㄌㄍㄎㄏㄐㄑㄒㄓㄔㄕㄖㄗㄘㄙㄧㄨㄩㄚㄛㄜㄝㄞㄟㄠㄡㄢㄣㄤㄥㄦˉˊˇˋ˙"
KEYS = "1qaz2wsxedcrfv5tgbyhnujm8ik,9ol.0p;/- 6347"
MAPPING = dict(zip(SYMBOLS, KEYS, strict=True))


def bopomofo_keys(reading: str) -> str:
    return "".join(MAPPING[ch] for ch in reading if ch != " ")
