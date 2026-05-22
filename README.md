# Daily Global Trends Telegram Digest

這個 repo 會用 GitHub Actions 每天台灣時間早上 7:00 自動執行：

1. 從 Google News RSS 搜尋全球最新趨勢候選新聞。
2. 使用 OpenAI API 生成繁體中文深度摘要。
3. 透過 Telegram Bot API 傳送到指定聊天室。

## 你需要設定的 GitHub Secrets

到 GitHub repo 的 `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`，新增：

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

可選：

- `OPENAI_MODEL`，例如 `gpt-5.2`。如果不設定，腳本預設使用 `gpt-5.2`。

## 排程

`.github/workflows/daily-global-trends.yml` 使用 UTC `23:00` 執行，也就是台灣時間隔天早上 `07:00`。

你也可以到 GitHub Actions 頁面手動按 `Run workflow` 測試。
