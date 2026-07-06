-- 生成历史日报测试数据（约 20 万条，覆盖最近 180 天）
USE daily_report;

SET SESSION cte_max_recursion_depth = 200001;

-- 每个日期约 1100 条；用 FLOOR(n/180) 派生部门/作者，
-- 避免与 MOD(n,180) 的日期取模相关联（5、60 都整除 180，直接 MOD(n,5) 会导致每天只有一个部门）
INSERT INTO reports (report_date, department, author, title, content, created_at)
WITH RECURSIVE seq AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1 FROM seq WHERE n < 200000
)
SELECT
    DATE_SUB(CURDATE(), INTERVAL MOD(n, 180) DAY),
    ELT(MOD(FLOOR(n / 180), 5) + 1, '研发部', '产品部', '运营部', '市场部', '客服部'),
    CONCAT('user_', LPAD(MOD(FLOOR(n / 180), 60), 2, '0')),
    CONCAT('工作日报 ', DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL MOD(n, 180) DAY), '%Y-%m-%d'), ' #', n),
    REPEAT(CONCAT('今日完成事项、进展与风险记录 ', n, '；'), 12),
    TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL MOD(n, 180) DAY),
              SEC_TO_TIME(9 * 3600 + MOD(n * 37, 9 * 3600)))
FROM seq;

ANALYZE TABLE reports;
