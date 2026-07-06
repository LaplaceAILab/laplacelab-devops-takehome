-- 生成历史日报测试数据（约 20 万条，覆盖最近 180 天）
USE daily_report;

SET SESSION cte_max_recursion_depth = 200001;

INSERT INTO reports (report_date, department, author, title, content, created_at)
WITH RECURSIVE seq AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1 FROM seq WHERE n < 200000
)
SELECT
    DATE_SUB(CURDATE(), INTERVAL MOD(n, 180) DAY),
    ELT(MOD(n, 5) + 1, '研发部', '产品部', '运营部', '市场部', '客服部'),
    CONCAT('user_', LPAD(MOD(n, 60), 2, '0')),
    CONCAT('工作日报 ', DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL MOD(n, 180) DAY), '%Y-%m-%d'), ' #', n),
    REPEAT(CONCAT('今日完成事项、进展与风险记录 ', n, '；'), 12),
    DATE_SUB(NOW(), INTERVAL MOD(n, 259200) MINUTE)
FROM seq;

ANALYZE TABLE reports;
