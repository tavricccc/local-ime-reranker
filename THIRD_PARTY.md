# 第三方元件與授權

自行撰寫程式碼採 MIT License。安裝腳本下載的輸入法、模型、詞庫依各自授權使用，MIT 不會覆蓋這些元件的條款。

| 元件 | 來源 | 授權／條款 |
| --- | --- | --- |
| Julia 1 權重及 runtime | [SupersonicLabs/Julia-1](https://huggingface.co/SupersonicLabs/Julia-1) | Apache-2.0；底層模型來源見其 model card |
| Weasel 小狼毫 | [rime/weasel](https://github.com/rime/weasel) | GPL-3.0 |
| librime | [rime/librime](https://github.com/rime/librime) | BSD-3-Clause；套件所含依賴另依其授權 |
| librime-lua | [hchunhui/librime-lua](https://github.com/hchunhui/librime-lua) | BSD-3-Clause |
| 洋蔥注音 Plus | [oniondelta/Onion_Rime_Files](https://github.com/oniondelta/Onion_Rime_Files) | 上游明訂不得用於商業營利相關行為；詞庫各來源另有授權標註 |
| Rime 地球拼音詞庫 | [rime/rime-terra-pinyin](https://github.com/rime/rime-terra-pinyin) | 字典內標註 CC BY-SA 3.0 與 CC-CEDICT 來源 |
| Jev 官方 API（選用） | [Typesafe](https://typesafe.ai/) | 雲端服務，依提供方條款與帳號方案使用 |

模型、第三方執行檔及完整洋蔥詞庫不隨 Git 儲存庫散布，安裝時從上游取得。固定版本記錄在 `assets.lock.json` 與 `config/onion-plus.lock.json`。

本儲存庫不表示整套安裝內容可商用。更換詞庫時應重新檢查新來源授權；本專案的 MIT 授權只適用於自行撰寫的部分。
