"""daily-report-service — 内部日报服务

Flask + MySQL + Redis，由 Nginx 反向代理对外提供服务。
"""

import json
import logging
import os
import time
from datetime import datetime

import pymysql
import pymysql.cursors
import redis
from flask import Flask, jsonify, request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("daily-report")

MYSQL_HOST = os.environ.get("MYSQL_HOST", "mysql")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "report")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DB = os.environ.get("MYSQL_DB", "daily_report")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD") or None

CACHE_TTL_REPORTS = int(os.environ.get("CACHE_TTL_REPORTS", "60"))
CACHE_TTL_SUMMARY = int(os.environ.get("CACHE_TTL_SUMMARY", "300"))

VALID_DEPARTMENTS = {"研发部", "产品部", "运营部", "市场部", "客服部"}

app = Flask(__name__)
app.json.ensure_ascii = False


def get_db():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor,
    )


_redis = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    socket_connect_timeout=2,
    socket_timeout=2,
    decode_responses=True,
)


def cache_get(key):
    try:
        return _redis.get(key)
    except Exception as exc:  # 缓存故障不阻塞主流程，降级读库
        log.warning("redis unavailable (%s), falling back to mysql", exc)
        return None


def cache_set(key, value, ttl):
    try:
        _redis.setex(key, ttl, value)
    except Exception as exc:
        log.warning("redis unavailable (%s), skip cache write", exc)


def cache_delete(*keys):
    try:
        _redis.delete(*keys)
    except Exception as exc:
        log.warning("redis unavailable (%s), skip cache invalidation", exc)


@app.get("/health")
def health():
    checks = {}
    status = "ok"
    status_code = 200

    try:
        conn = get_db()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            conn.close()
        checks["mysql"] = "ok"
    except Exception as exc:
        checks["mysql"] = f"error: {exc}"
        status = "unhealthy"
        status_code = 503

    try:
        _redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        # 缓存故障可降级，不直接判定服务不可用
        checks["redis"] = f"error: {exc}"
        if status == "ok":
            status = "degraded"

    return jsonify({
        "service": "daily-report-service",
        "status": status,
        "checks": checks,
        "time": datetime.now().isoformat(timespec="seconds"),
    }), status_code


@app.get("/api/reports")
def list_reports():
    date_str = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "invalid date, expected YYYY-MM-DD"}), 400

    department = (request.args.get("department") or "").strip()
    if department and department not in VALID_DEPARTMENTS:
        return jsonify({
            "error": f"unknown department, expected one of {sorted(VALID_DEPARTMENTS)}"
        }), 400

    cache_key = f"reports:{date_str}:{department or 'all'}"
    started = time.monotonic()

    cached = cache_get(cache_key)
    if cached is not None:
        payload = json.loads(cached)
        payload["source"] = "cache"
        payload["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
        return jsonify(payload)

    sql = (
        "SELECT id, report_date, department, author, title, created_at "
        "FROM reports WHERE report_date = %s"
    )
    params = [date_str]
    if department:
        sql += " AND department = %s"
        params.append(department)
    sql += " ORDER BY created_at DESC LIMIT 20"

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    items = [
        {**row, "report_date": str(row["report_date"]),
         "created_at": str(row["created_at"])}
        for row in rows
    ]
    payload = {
        "date": date_str,
        "department": department or "all",
        "count": len(items),
        "items": items,
    }
    cache_set(cache_key, json.dumps(payload, ensure_ascii=False), CACHE_TTL_REPORTS)

    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    payload["source"] = "mysql"
    payload["elapsed_ms"] = elapsed_ms
    log.info("GET /api/reports date=%s dept=%s source=mysql elapsed_ms=%s",
             date_str, department or "all", elapsed_ms)
    return jsonify(payload)


@app.get("/api/summary")
def summary():
    days_raw = request.args.get("days", "7")
    try:
        days = int(days_raw)
    except ValueError:
        return jsonify({"error": "days must be an integer"}), 400
    if not 1 <= days <= 90:
        return jsonify({"error": "days must be between 1 and 90"}), 400

    cache_key = f"summary:{days}"
    started = time.monotonic()

    cached = cache_get(cache_key)
    if cached is not None:
        payload = json.loads(cached)
        payload["source"] = "cache"
        payload["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
        return jsonify(payload)

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT department, COUNT(*) AS report_count, "
                "COUNT(DISTINCT author) AS author_count "
                "FROM reports "
                "WHERE report_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
                "GROUP BY department ORDER BY report_count DESC",
                (days,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    payload = {"days": days, "departments": rows}
    cache_set(cache_key, json.dumps(payload, ensure_ascii=False), CACHE_TTL_SUMMARY)

    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    payload["source"] = "mysql"
    payload["elapsed_ms"] = elapsed_ms
    log.info("GET /api/summary days=%s source=mysql elapsed_ms=%s", days, elapsed_ms)
    return jsonify(payload)


@app.post("/api/reports")
def create_report():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400

    department = (body.get("department") or "").strip()
    author = (body.get("author") or "").strip()
    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()

    if not department or not author or not title:
        return jsonify({"error": "department, author, title are required"}), 400
    if department not in VALID_DEPARTMENTS:
        return jsonify({
            "error": f"unknown department, expected one of {sorted(VALID_DEPARTMENTS)}"
        }), 400

    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO reports (report_date, department, author, title, content) "
                "VALUES (%s, %s, %s, %s, %s)",
                (today, department, author, title, content),
            )
            report_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    cache_delete(f"reports:{today}:all", f"reports:{today}:{department}")
    return jsonify({"id": report_id, "report_date": today}), 201


# 启动时先确认 MySQL 可用：数据库连不上时快速失败，避免带病提供服务
def check_mysql_on_boot():
    conn = get_db()
    conn.close()
    log.info("MySQL connection OK (%s:%s/%s)", MYSQL_HOST, MYSQL_PORT, MYSQL_DB)


check_mysql_on_boot()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
