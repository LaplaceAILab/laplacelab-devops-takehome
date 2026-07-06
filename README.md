# daily-report-service · 运维工程师 Take-Home 环境

这是 Laplace AI Lab 运维工程师 Take-Home 测试**任务一**使用的环境仓库。完整题目见 [ASSIGNMENT.md](ASSIGNMENT.md)。

## 背景

「日报服务」是一个内部小服务，同事们用它提交和查看每日工作日报。技术栈：

```
客户端 ──> Nginx (host:8080) ──> Flask 应用 (:5000) ──┬──> MySQL 8.0 (:3306)
                                                      └──> Redis 7 (:6379)
```

产品同事反馈：**“服务时好时坏，有时候打不开，有时候很慢。”** 你的任务是把它排查清楚并修好。

## 快速开始

需要本机安装 Docker 与 docker-compose（或兼容工具如 podman compose）。

```bash
docker-compose up -d --build
```

> 首次启动 MySQL 需要初始化约 20 万条测试数据，可能需要 1~3 分钟，请耐心等待。
> 如果 pip 安装依赖较慢，可自行修改 `app/Dockerfile` 使用国内镜像源。

服务入口：`http://localhost:8080`

## 接口说明

| 方法 | 路径 | 说明 | 示例 |
|---|---|---|---|
| GET | `/health` | 健康检查（含依赖状态） | `curl http://localhost:8080/health` |
| GET | `/api/reports` | 查询某天的日报列表 | `curl 'http://localhost:8080/api/reports?date=2026-07-01&department=研发部'` |
| GET | `/api/summary` | 最近 N 天各部门日报统计 | `curl 'http://localhost:8080/api/summary?days=7'` |
| POST | `/api/reports` | 提交一条日报 | 见下方 |

> 测试数据覆盖「你首次启动环境那天」往前 180 天，`date` 参数取这个范围内的日期即可查到数据（示例里的日期请自行替换）。

```bash
curl -X POST http://localhost:8080/api/reports \
  -H 'Content-Type: application/json' \
  -d '{"department": "研发部", "author": "张三", "title": "今日工作", "content": "完成了……"}'
```

## 你需要做什么

按照 [ASSIGNMENT.md](ASSIGNMENT.md) 任务一的要求：

1. 启动环境，访问 `/health` 和业务接口，观察现象；
2. 排查并修复环境中存在的问题（**不止一个**）；
3. 提交修改后的文件和一份排查报告。

仓库里的任何文件（配置、代码、compose 文件）都允许修改。

## 提交方式

Fork 或复制本仓库到你自己的仓库（公开/私有均可，私有请邀请我们查看），或打包为压缩包发送。建议的目录结构：

```
├── (你修改过的环境文件)
├── REPORT.md            # 任务一排查报告
├── scripts/             # 任务二脚本 + 测试说明
└── answers.md           # 任务三 / 任务四书面回答
```

## 说明

- 本仓库中的所有账号密码均为本地练习用的样例凭据，与任何真实系统无关。
- 数据为脚本生成的合成数据。
- 欢迎使用 AI 工具，但请按题目要求在报告中说明使用与验证情况。
