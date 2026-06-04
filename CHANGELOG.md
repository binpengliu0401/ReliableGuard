# Changelog

所有显著变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

每次向 GitHub push 前，Codex 必须在 `## [Unreleased]` 下添加本次变更条目，
并将 CHANGELOG.md 与代码变更包含在同一个 commit 中。

---

## [Unreleased]

### Changed
- **论文 RQ 重新编号**（确认 2026-06-04，按逻辑依赖顺序）：
  - RQ1 = Claim-level audit accuracy + coverage ceiling（电商，成功案例）
  - RQ2 = Final-answer-only vs. trace/state-augmented auditing（电商，原 RQ3 的 structural 内容）
  - RQ3 = Cross-domain generalizability，定位为诊断/边界案例（reference，自我诊断）
  - `docs/thesis_scope.md` 三个 RQ 全部重写，含 RQ3 可证伪性辩护与 RQ 间逻辑关系
- **代码与论文编号解耦**（编号只活在论文，代码用语义名）：
  - `scripts/run_rq3_ablation.sh` → `scripts/run_structural_ablation.sh`
  - `generate_figures.py`：`generate_fig3_rq3_structural` → `generate_fig3_structural`，`_latest_rq3_dir` → `_latest_structural_ablation_dir`，图标题去掉 `RQ3:` 前缀
  - 产物图改名 `figures/fig3_rq3_structural.pdf` → `figures/fig3_structural.pdf`
  - 权威目录 `results/rq3_ablation/` 保持不变（历史命名 = 结构消融 = 论文 RQ2）
- **论文文档重构**：`thesis_scope.md` / `formal_definitions.md` / `related_work_skeleton.md` 由仓库根目录迁移至 `docs/`；`README.md` 刷新项目结构与实验快照引用

### Added
- 零 claim 透明度指标（`eval/metrics.py`）：`zero_claim_rate`、`zero_claim_pass_rate`、`pass_with_claim_rate`、`pass_without_claim_rate`，并在逐行 CSV 增加 `claim_count`
- `scripts/threshold_sensitivity.py`：对 score-based WARN 阈值 {0.5, 0.6, 0.7} 做事后敏感性分析，输出 FAR/RDR
- `CHANGELOG.md` 与 Git pre-push hook（`hooks/pre-push`、`scripts/install-hooks.sh`）：push 前强制校验 CHANGELOG 更新

### Fixed
- `eval/fact_scorer.py`：对齐 reference 工具实际写入的 `doi_status` 取值（`valid`→`verified`、`not_found`→`failed`），修正 Set B reference 辅助 fact 指标（不影响主 FAR/RDR）

### Removed
- 删除根目录 `thesis_outline.md`（论文结构重构，不再使用）
- 删除孤儿图产物 `figures/fig3_rq3_structural.pdf`（已由 `fig3_structural.pdf` 取代）

---

## [0.6.0] - 2026-06-02 — Docs & Thesis Materials

### Changed
- 更新论文文档和实验产物（thesis materials and experiment artifacts）

---

## [0.5.0] - 2026-05-26 — Experiment Freeze & Benchmark Stability

### Fixed
- Benchmark 运行时错误快速失败（fail fast on runtime failures）——防止静默跳过基础设施错误
- 优化 audit policy 和实验输出格式

### Changed
- 追踪实验输入文件并刷新 reference fixture
- 冻结论文 metrics，锁定 `scripts/` 实验脚本状态
- 刷新 README 概览以反映当前实验批次

> 本版本对应权威实验批次 commit `3759744`：
> - Set A full ablation: `results/set_a_full/20260526/173346/`
> - Set B full ablation: `results/set_b_full/20260531/045635/`
> - RQ3 structural ablation: `results/rq3_ablation/20260531/073500/`

---

## [0.4.0] - 2026-05-13 — Structural Audit Ablation (RQ3)

### Added
- `structural_audit.py`：ecommerce 结构审计组件
  - Pre-execution policy check：`create_order` 且 `amount > 5000` 时直接 BLOCK（对应 F2）
  - Post-execution state check：tool 报 success 但 DB 状态未变时 BLOCK（对应 F4）
- `use_structural_audit` 消融开关：支持 `V3_NoStructural` vs `V3_Intervention` 受控对比（RQ3）
- Ecommerce-only ablation 控制和 TCCR metric
- Reference verifier sources：CrossRef、Semantic Scholar、URL 适配器（默认关闭）

### Changed
- 整合运行时报告更新，清理未使用的 registry 注册项

---

## [0.3.0] - 2026-04-27 — Ablation Framework & V1/V2/V3 Standardization

### Added
- Multi-seed bootstrap 置信区间（Task 5）：跨 seed 运行并导出 pass rate / FAR 的 CI 列
- Audit-only ablation 指标修正（Task 1）：新增 `reliability_verdict_audit`，与 effective verdict 并列导出
- Set A 汇总 metrics 和完整运行脚本（`run_set_a_full.sh` 等）
- Ablation metrics 精化和 CSV 诊断导出

### Changed
- 统一 ablation 版本命名为 `V1_Baseline` / `V2_AuditOnly` / `V3_Intervention`（移除所有旧别名）
- 删除 legacy version aliases

### Fixed
- Ablation keys 对齐和 pipeline 注入修正

---

## [0.2.0] - 2026-04-07 — Reference Domain & Unified Benchmark

### Added
- Reference domain 完整实现：DOI/PDF fixture、SchemaValidator、gate validation、reference scenario datasets
- Reference domain DB-aware policy layer
- Real-PDF fixture workflow 和 Semantic DOI recovery
- 统一 benchmark 导出（ecommerce + reference 双 domain）

### Changed
- 重构：归档 legacy ReAct 路径，统一 ablation 运行时为 LangGraph
- 将硬编码 TOOL_CONFIG 替换为 registry + yaml config
- 整理 runtime 模块结构，scenario generators 移入 `scripts/`

### Fixed
- SchemaValidator 规则结构重建，float 精度 bug
- list type 支持、reference scenarios benchmark 集成、F4B 重命名为 F4

---

## [0.1.0] - 2026-03-27 — Benchmark Core & F0-F5 Scenarios

### Added
- `eval/benchmark.py`、`ablation_runner.py`、`metrics.py`：benchmark 框架核心
- F0-F5 failure taxonomy scenario coverage（`tasks/scenario_v1.py`）
- `confirm_order` / `refund_order` 工具，支持 multi-turn loop，F5 smoke test 通过
- Multi-backend 支持（ablation_config.py）

### Fixed
- Metrics 计算、float 精度、scenario label 错误

---

## [0.0.2] - 2026-03-16 — LangGraph Migration

### Added
- Recovery v0：failure classifier、recovery controller、agent 集成
- 迁移 LLM backend 到 Qwen-plus / OpenRouter

### Changed
- Agent 控制流重构为 LangGraph `StateGraph`（替代原有自定义循环）

### Fixed
- `final_answer` 生成，`tool_calls` 过滤

---

## [0.0.1] - 2026-03-02 — Project Bootstrap

### Added
- 项目初始化：Mistral API + SQLite ecommerce tools
- State Tracker 和 Verifier，FALSE_SUCCESS 检测可用
- Gate v1：schema、policy、dependency checks 全部通过
- `reset_env`：可复现的 order_id 从 1 开始的运行环境
- Baseline agent 完成，对比数据就绪
- RG-OBS-001 发现，multi-run test，distribution plot
