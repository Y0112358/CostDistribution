# 更新按鈕的 Cloudflare Worker

網頁上的「更新資料」按鈕透過此 Worker 呼叫 GitHub workflow_dispatch，
觸發 `.github/workflows/dashboard.yml` 重算資料並重新部署 Pages。
GitHub token 只存在 Worker 的 secrets，**不會進前端 JS**。

## 部署步驟（一次性）

1. `npm install`
2. `npx wrangler login`
3. 建立 **fine-grained PAT**：僅授權此 repo 的 `Actions: Read and write`
4. 設定 secrets（`npx wrangler secret put <名稱>`，逐個輸入值）：
   - `GH_TOKEN` = 上面的 PAT
   - `OWNER` = GitHub 帳號
   - `REPO` = repo 名稱
   - `WORKFLOW` = `dashboard.yml`
5. `npm run deploy` → 得到 worker URL（形如 `https://theme-rotation-update.你的子域.workers.dev`）
6. 在 repo 的 **Settings → Secrets and variables → Actions** 新增：
   - `VITE_UPDATE_URL` = `<worker URL>/update`
   - `VITE_ACTIONS_URL` = `https://github.com/<OWNER>/<REPO>/actions/workflows/dashboard.yml`

設定完成後，網頁上的「更新資料」即為真正的頁內一鍵更新。
未設定時按鈕自動退化為連結到 Actions 頁面手動觸發。
