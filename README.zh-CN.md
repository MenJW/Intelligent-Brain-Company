# TOBECEO
<div align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Framework-Flask-green.svg" alt="Framework">
  <img src="https://img.shields.io/badge/Agent-MultiAgent-orange.svg" alt="MultiAgent">
  <img src="https://img.shields.io/github/stars/MenJW/TO-BE-CEO?style=social" alt="GitHub Stars">
  <img src="https://img.shields.io/github/license/MenJW/TO-BE-CEO" alt="License">
  <img src="https://img.shields.io/github/last-commit/MenJW/TO-BE-CEO" alt="Last Commit">
</div>
把创业想法先丢进一家 AI 公司，再决定要不要真做。

这不是一个“给你建议”的聊天机器人，而是一套可追踪、可回放、可干预的公司式决策流程：

- 先研究，再兴奋
- 先辩论，再投入
- 先董事会结论，再执行
- 发现问题后，支持干预并重规划

[English Version](./README.md)

---

## 为什么更有用

很多项目不是输在执行慢，而是输在前期判断太乐观。

TOBECEO 把想法评估拆成 5 个阶段：

1. 研究
2. 部门方案
3. 跨部门圆桌
4. 综合汇总
5. 董事会决策与评分卡

你还可以在任意阶段和 agent 对话，把关键聊天结论升级为正式干预，再继续推进流程。

---

## 当前能力

![Hero Demo](./assets/hero-demo.gif)

- 内置 Web Console（浏览器直接体验）
- Flask API（项目、规划、时间线、版本 diff、对话）
- CLI 一键生成草案
- SQLite 持久化项目与任务状态
- 中英文对话切换
- 阶段回放 + 员工级讨论留痕

适合：

- 创业者做早期 idea 压测
- 产品团队做机会评估
- 加速器/训练营做结构化评审
- 不想听“套话鼓励”，想听“组织化反驳”的团队

---

## 快速开始

### 1. 安装

```bash
python -m pip install -e .[dev]
```

### 2. 启动 API + 控制台

```bash
tobeceo-api
```

打开：

- http://127.0.0.1:8000
- http://127.0.0.1:8000/health

### 3. 使用 CLI

```bash
tobeceo-plan "面向独立健身房的 AI 增长助手" \
  --summary "帮助老板自动化留存、复购与私域运营。" \
  --constraint "控制获客成本" \
  --metric "月留存率 > 90%"
```

---

## 60 秒体验 API

### 创建项目

```bash
curl -X POST http://127.0.0.1:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "title": "面向校招的 AI 面试官",
    "summary": "按岗位能力模型自动完成初筛。",
    "constraints": ["避免评分偏见"],
    "metrics": ["面试完成率 > 70%"],
    "language": "zh-CN"
  }'
```

### 推进到下一阶段

```bash
curl -X POST http://127.0.0.1:8000/api/planning/generate \
  -H "Content-Type: application/json" \
  -d '{"project_id":"<PROJECT_ID>"}'
```

重复调用即可依次推进 5 个阶段。

### 与 agent 对话

```bash
curl -X POST http://127.0.0.1:8000/api/projects/<PROJECT_ID>/chat \
  -H "Content-Type: application/json" \
  -d '{"agent":"research", "message":"这个项目最大的商业风险是什么？"}'
```

### 比较两个版本差异

```bash
curl "http://127.0.0.1:8000/api/projects/<PROJECT_ID>/plans/diff?from=<V1>&to=<V2>"
```

---

## 阶段流程

1. `research`
2. `department_design`
3. `roundtable`
4. `synthesis`
5. `board`

评分卡与最终建议在 `board` 阶段生成。

---

## 截图

![Screenshot 1](./assets/screenshot-1.png)
![Screenshot 2](./assets/screenshot-2.png)
![Screenshot 3](./assets/screenshot-3.png)

---

## 配置项

可选环境变量：

- `IBC_HOST` 默认 `127.0.0.1`
- `IBC_PORT` 默认 `8000`
- `IBC_DATA_DIR` 默认 `.data`
- `IBC_LLM_API_KEY`
- `IBC_LLM_BASE_URL`
- `IBC_LLM_MODEL`
- `IBC_LLM_TIMEOUT_SECONDS` 默认 `45`

不配置 LLM 也可运行，系统会使用可复现的 demo 模式。

---

## 部署

仓库已包含 Render 部署配置：`render.yaml`。

---

## Roadmap

- 强化董事会辩论机制
- 支持按依赖关系做选择性重算
- 增加多用户鉴权与工作空间隔离
- 提供生产级数据库方案
- 建立自动化质量回归评估

---

## 贡献

欢迎提 issue 和 PR。

如果想快速参与，建议从这些方向入手：

- 新行业测试用例
- 干预策略优化
- 评分卡维度增强
- diff 与时间线交互体验优化

---

## License

Apache-2.0
