TAIWAN_RULES = (
    "使用臺灣繁體中文常用標準字，不用簡體字與罕用異體字。"
    "按上下文辨別在／再、的／地／得；只選現有候選，沒把握保留原首選。"
)

PROMPTS = {
    "baseline": "依前文語意，選擇最合理且通順的臺灣繁體中文續文。所有候選均由注音輸入法產生。",
    "concise": "哪個續文最符合前文語意？選擇自然的臺灣繁體中文說法。",
    "repair": "以下句子版本只有同音候選詞不同。根據前文，哪一句最能表達使用者想說的意思？",
    "fluency": "閱讀整段前文，選出語意連貫、文法自然的中文續文。",
    "common_usage": "依完整前文選擇語意正確、通順且符合臺灣常用詞的續文，避免不成詞的組合。",
    "english": "Based on the preceding Chinese text, which continuation is semantically correct and natural in Traditional Chinese as used in Taiwan? All candidates have the same pronunciation.",
}
