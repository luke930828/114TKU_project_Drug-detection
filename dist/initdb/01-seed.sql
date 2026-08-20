-- 展示用種子資料。資料庫「第一次建立」時自動執行一次。
--
-- ⚠️ 這個檔案會跟著壓縮檔一起公開下載，
--    絕對不要放真實爬取到的可疑網址、蒐證內容或任何個資。

-- 預設管理員帳號（密碼請在系統內第一次登入後立刻修改）
-- password_hash 請填你們 auth.py 使用的雜湊格式，不要放明文
-- INSERT INTO users (user_id, account, password_hash, role, department)
-- VALUES ('admin', 'admin', '<hash>', 'admin', '示範單位');

-- 白名單範例（公開、無爭議的網站）
-- INSERT INTO whitelist_websites (url, title, reason, added_by)
-- VALUES ('https://www.moe.gov.tw', '教育部', '政府機關', 'system');
