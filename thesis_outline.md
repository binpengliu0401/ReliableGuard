# ReliableGuard 论文大纲

## 拟定题目

**ReliableGuard: Claim-level Runtime Auditing for Tool-using LLM Agents**

中文题目可写为：

**ReliableGuard：面向工具调用型大语言模型智能体的声明级运行时审计框架**

## 摘要

摘要应围绕“问题、方法、实验、发现、贡献”展开。

- **研究背景**：工具调用型 LLM agents 不仅会产生文本幻觉，还可能在自然语言输出、工具调用轨迹和外部环境状态之间产生不一致。
- **研究问题**：现有 factuality evaluation、agent benchmarks 和 observability tools 难以同时完成失败量化、失败标准化和失败追踪。
- **方法**：提出 ReliableGuard，一个 claim-level runtime auditing harness，通过 claim extraction、verifiability classification、domain verification、risk scoring、intervention policy 和 trace reporting 对 agent 行为进行审计。正文中进一步解释其 post-hoc runtime verification 与 neuro-symbolic 架构属性。
- **实验设计**：在 ecommerce 和 academic reference 两个领域评估，比较 baseline、audit-only 和 enforced-intervention 三种设置，并补充计算开销与 claim extraction 质量分析。
- **核心发现**：state-grounded ecommerce 任务中，trace/state-augmented auditing 显著提升检测能力；reference 任务中，claim extraction coverage 和 verifier calibration 是主要瓶颈。
- **贡献**：提出 externally verifiable agent failures 的 taxonomy、claim-level audit pipeline、domain verifier adapter contract，以及跨领域消融评估。

## 1. Introduction

### 1.1 Background

- 说明 LLM agents 从单纯文本生成扩展到工具调用、数据库操作、文档检索、外部 API 交互等任务。
- 强调工具调用场景下的可靠性问题不同于普通 hallucination：错误可能存在于 tool trace、database state、PDF reference list、DOI metadata 或 state transition 中。
- 引出本文关注的核心对象：**externally verifiable failures in tool-using LLM agents**。

### 1.2 Problem Statement

围绕三个系统性问题展开：

- **难以量化**：agent 的最终回答可能是正确、部分正确、unsupported、unsafe 或 unverifiable，缺少统一度量。
- **难以标准化**：不同领域的失败形态不同，例如 ecommerce 中的 false-success database mutation 与 reference 中的 fabricated DOI。
- **难以追踪**：final-answer-level evaluation 无法覆盖工具执行轨迹和外部状态中的关键证据。

### 1.3 Research Scope

- 明确本文只研究具有可观察 grounding artifacts 的 externally verifiable failures。
- 包括 database state、tool execution traces、bibliographic metadata、PDF reference lists。
- 排除 subjective quality、style preference、open-ended opinions、unverifiable claims 和模型训练优化。

### 1.4 Research Questions

- **RQ1: Claim-level Audit Accuracy and Coverage**  
  claim-level post-hoc auditing 对不同 failure categories 的检测准确性与覆盖上限如何？

- **RQ2: Cross-domain Framework Generalizability**  
  统一的 evidence-state 分类体系和风险打分框架，能否在结构差异显著的两个域（ecommerce state-grounded vs reference evidence-grounded）上产生一致且可解释的可靠性度量？

- **RQ3: Final-answer-only versus Trace/State-augmented Auditing**  
  相比只审计最终回答，引入 tool traces 和 environment state 能带来多少增益？

### 1.5 Contributions

- 提出一个用于 externally verifiable failures 的 F0-F5 failure taxonomy。
- 提出 claim-level neuro-symbolic audit pipeline。
- 定义 domain verifier adapter interface contract。
- 在 ecommerce 和 academic reference 两个领域完成 baseline、audit-only、intervention 三组消融评估。

## 2. Background and Related Work

该章建议从四条原始文献线索中收敛为三个主要方向。Neuro-symbolic AI 不再作为平行 related work 大节，而是移到第 4 章作为 ReliableGuard 的 architecture motivation；这样 Related Work 更聚焦于直接理论祖先、最近方法邻居和工程背景。

### 2.1 Runtime Verification

- 介绍 classical runtime verification：对程序执行 trace 进行监控，并根据 temporal logic、state machines 或 rule systems 判断行为是否满足 specification。
- 可讨论 Java PathExplorer、EAGLE、Introduction to Runtime Verification。
- 再连接到 AgentSpec 和 AGrail 等 LLM agent runtime enforcement / guardrail 工作。
- 差异点：ReliableGuard 不只检查 action-level safety constraints，而是审计 agent final answer、tool trace 和 external evidence 之间的 claim-level factual consistency。

### 2.2 Factuality and Hallucination Detection

- 介绍 hallucination detection、claim decomposition、atomic factuality evaluation。
- 重点连接 FActScore 与 SelfCheckGPT。
- 差异点：FActScore 面向 static generated text；ReliableGuard 面向 tool-using agents，正确性可能依赖 tool execution、database mutation 和 external metadata。

### 2.3 LLM Agent Evaluation and Observability

- 介绍 AgentBench、tau-bench、ToolSandbox 等 agent benchmarks。
- 介绍 LangSmith、Langfuse、DeepEval 等 observability / evaluation frameworks。
- 差异点：benchmarks 主要回答 agent 是否完成任务，observability tools 主要记录发生了什么；ReliableGuard 进一步解释为什么某次运行应被 PASS、WARN 或 BLOCK。

### 2.4 Positioning Summary

- 用一张 comparison matrix 总结不同方向的 evaluation object、verification method、intervention support、domain-specificity 和 runtime mode。
- 明确本文定位：ReliableGuard is not primarily a contribution to any single direction. Its contribution is the integration point: applying runtime verification's monitor-and-trace paradigm to agent behavior, using neuro-symbolic architecture to audit factual claims, and generating the observability signals that agent benchmarks measure but do not explain.

## 3. Formal Problem Definition

该章应从 `formal_definitions.md` 中抽象出论文的数学定义，建议放在方法之前。

### 3.1 Tool-using Agent Execution

- 定义一次 agent run 包括 user query、agent answer、tool calls、tool responses、environment state snapshots 和 domain evidence sources。
- 说明 ReliableGuard 不修改 agent policy，而是在 execution 后或 execution 过程中进行 post-hoc runtime audit。

### 3.2 Claim and Evidence State

- 定义 agent answer \(A\) 被抽取为 claim set：

  \[
  C = \{c_1, c_2, \ldots, c_n\} = Extract(A)
  \]

- 定义 evidence state：

  \[
  e_i \in E = \{supported, contradicted, unsupported, not\_found, unverifiable\}
  \]

- 解释五类 evidence state 在两个领域中的含义。

### 3.3 Intervention Verdict

- 定义 task-level verdict：

  \[
  v_t \in \{PASS, WARN, BLOCK\}
  \]

- 说明 PASS 表示接受，WARN/BLOCK 表示风险检测动作。

### 3.4 Core Metrics

正式定义并解释：

- **False Acceptance Rate (FAR)**：risky tasks 被错误 PASS 的比例。
- **False Alarm Rate**：safe tasks 被错误 WARN/BLOCK 的比例。
- **Risk Detection Rate (RDR)**：risky tasks 被 WARN/BLOCK 检测到的比例。
- **Task Claim Coverage Rate (TCCR)**：至少产生一个 grounded 非 unverifiable claim 的任务比例。
- **Evidence-state distribution**：supported、contradicted、unsupported、unverifiable、not_found 的任务级分布。
- **Runtime and token cost**：阶段 latency mean/p95、total audit latency 和 token count。

### 3.5 Domain Verifier Adapter Contract

- 定义 verifier adapter 的输入：claim、claim_type、domain_context。
- 定义输出：evidence_state、confidence、evidence_source、raw_evidence。
- 说明 adapter constraints：
  - determinism
  - offline by default
  - single-claim independence
  - evidence transparency
  - no hidden policy decisions

### 3.6 Claim-level Traceability Chain

- 定义审计链：

  \[
  c_i \rightarrow l_i \rightarrow e_i \rightarrow s_i \rightarrow a_i
  \]

- 定义 aggregate policy：

  \[
  V_{agg} = AggregatePolicy(\{a_i\}_{i=1}^{n}, \{s_i\}_{i=1}^{n}, S)
  \]

- 说明 \(S\) 代表 structural audit signals，例如 high-value order violation 或 database state-transition anomaly。

## 4. ReliableGuard Framework

### 4.1 System Overview

- 给出整体架构图：agent execution layer、audit pipeline、domain verifier adapters、policy intervention layer、trace reporting layer。
- 强调 ReliableGuard 是 reliability harness，而不是 model optimization method。

### 4.2 Claim-level Audit Pipeline

按六阶段描述：

1. Extract factual claims from agent final answer.
2. Classify each claim by verifiability and relevance.
3. Verify claims using domain-specific verifier adapters.
4. Score claim-level and aggregate reliability risks.
5. Intervene with PASS/WARN/BLOCK when enforcement is enabled.
6. Trace every claim-to-evidence audit path.

### 4.3 Architecture Motivation: Neuro-symbolic Auditing

- 介绍 ReliableGuard 为什么采用 neuro-symbolic architecture。
- neural components 负责理解非结构化 agent output，例如 claim extraction 和 verifiability classification。
- symbolic components 负责可复现的 evidence checking、risk scoring、policy aggregation 和 trace reporting。
- 可简要连接 Neural Theorem Provers、DeepProbLog、Logic-LM、CRITIC、LLM-Modulo，但强调差异：这些工作多用于提升 reasoning 或 task solving；ReliableGuard 将神经符号结构用于 runtime monitoring 和 reliability auditing。

### 4.4 Neural Components

- claim extraction：将非结构化 final answer 转换为 claim-level audit units。
- verifiability classification：判断 claim 是否 fully verifiable、partially verifiable 或 unverifiable。
- 说明 neural components 的风险：coverage ceiling、aggregate claims、ambiguous extraction。

### 4.5 Symbolic Components

- domain verifier adapters：基于结构化证据进行 deterministic checking。
- risk scorer：将 evidence state、confidence 和 claim type 映射为 risk score。
- policy engine：将 claim-level risk 与 structural signals 聚合为 PASS/WARN/BLOCK。

### 4.6 Trace Reporting

- 说明 trace report schema 中的 run-level fields 与 claim-level traces。
- 展示每条 trace 如何保存 claim、verifiability、verification、risk 和 intervention。
- 解释 traceability 对 reproducibility、debugging 和 error analysis 的作用。

## 5. Domain Instantiations

### 5.1 Domain Selection Rationale

- 本文选择 ecommerce 和 academic reference，不只是因为二者使用不同 grounding mechanism，而是因为它们代表两类有现实意义的 agent 部署场景。
- **Ecommerce 代表工业级部署场景**：事务型数据库、状态变更、库存和订单查询、高价值操作风险，以及 false-success database mutation 等最终回答不可见的执行失败。
- **Academic reference 代表学术生产场景**：文献生成与验证、DOI 元数据、PDF reference list、bibliographic metadata 和知识可信度。
- 两个领域在 grounding mechanism、evidence 结构和 failure pattern 上互补，共同覆盖“结构化状态驱动”和“异构证据驱动”这两种主流 agent 部署模式。
- 该选择也为 external validity 提供边界说明：本文不是声称覆盖所有领域，而是选择两个具有代表性的部署模式作为概念验证。

### 5.2 Ecommerce: Industrial State-grounded Agent Tasks

- 任务环境：SQLite-backed order database 与 ecommerce domain tools。
- grounding artifacts：database records、tool calls、tool responses、state snapshots。
- 典型失败：
  - incorrect order information
  - unsafe high-value order creation
  - false-success where tool reports success but database state is unchanged
- 说明该领域用于检验 trace/state-augmented auditing 的价值。

### 5.3 Academic Reference: Evidence-grounded Scholarly Production Tasks

- 任务环境：DOI、authors、titles、publication years、PDF reference lists、bibliographic metadata。
- grounding artifacts：local fixtures、PDF extraction output、metadata sources。
- 典型失败：
  - fabricated references
  - invalid DOI metadata
  - author-title mismatch
  - unsupported bibliographic claims
- 说明该领域用于检验 heterogenous evidence 与 claim extraction coverage 的限制。

### 5.4 Cross-domain Comparison

- ecommerce 是 state-grounded：证据结构化、状态变化明确。
- reference 是 evidence-grounded：证据异构、claim extraction 与 metadata matching 更脆弱。
- 引出后续实验中的 domain-dependent calibration 问题。

## 6. Experimental Design

### 6.1 Evaluation Goals

- 回答 RQ1：检测准确性、failure category coverage、claim extraction ceiling；V2/V3 enforcement 权衡作为 RQ1 子分析。
- 回答 RQ2：统一框架跨域一致性——ecommerce 与 reference 的 evidence-state 分布差异是否由框架本身解释，而非框架失效。
- 回答 RQ3：final-answer-only 与 trace/state-augmented auditing 的增益，重点区分 F2（pre-execution 策略违规）与 F4（post-hoc claim verification 已能覆盖）的检测来源差异。

### 6.2 Datasets and Scenarios

- Set A：controlled known-failure benchmark，覆盖 F0-F5 failure taxonomy。
- Set B：generalization stress test，覆盖 expected PASS、WARN、BLOCK。
- 按 domain、failure category、difficulty、anticipated failure type 和 verifiable facts 描述数据。

### 6.3 Ablation Settings

- **V1 Baseline**：无 verifier，无 intervention。
- **V2 AuditOnly**：启用 verifier，但不强制干预。
- **V3 Intervention**：启用 verifier，并执行 PASS/WARN/BLOCK。
- **V3_NoStructural**：RQ3 专用 ecommerce 消融，保持 verifier 和 intervention 开启，但关闭 structural audit。
- 说明 V1/V2/V3 是主消融，目标是隔离 verification 和 intervention 对可靠性指标的影响；V3_NoStructural 只用于 RQ3 的 trace/state 边界分析。

### 6.4 Evaluation Conditions

- final-answer-only auditing：只基于 agent final answer。
- trace/state-augmented auditing：引入 tool execution traces、database state snapshots 和 structural audit signals。
- offline deterministic verification：默认使用本地 fixtures、database state 和 cached metadata。

### 6.5 Comparator Scope and External Baselines

- 主实验以 V1/V2/V3 为核心，因为本文目标是验证 ReliableGuard 内部机制的增量贡献，而不是把通用 observability platform 当作同类系统比较。
- 可加入一个 limited baseline：将 FActScore-style claim decomposition / factuality checking 直接应用于 final answer，作为 final-answer-only factuality baseline。
- 对 LangSmith、Langfuse、DeepEval 等系统应采用 qualitative comparison，而非直接数值比较，因为它们主要提供 tracing、evaluation workflow 或 LLM-as-judge metrics，不提供本文所定义的 domain verifier adapter、evidence state 和 PASS/WARN/BLOCK intervention contract。
- 若不实现外部 baseline，应在 Discussion 或 Threats to Validity 中明确说明：comparison with alternative baselines is left for future work, because their evaluation objects and intervention semantics differ from ReliableGuard.

### 6.6 Metrics

- False Acceptance Rate (FAR)
- False Alarm Rate
- Risk Detection Rate (RDR)
- Task Claim Coverage Rate (TCCR)
- evidence-state distribution：supported、contradicted、unsupported、unverifiable、not_found 的任务均值与 coverage
- per-failure-type detection rate
- reliability score distribution
- stage latency mean/p95：extract_claims、classify_verifiability、verify_claims、score_risks、decide_interventions、generate_report、total_pipeline
- average and total positive token counts
- bootstrap confidence intervals

### 6.7 Claim Extraction Quality Check

- 对一小部分 ecommerce 和 reference 样本进行人工标注，建立 gold atomic claims。
- 计算自动 claim extraction 的 precision、recall 和 F1。
- 将 missed claims 与 unverifiable aggregate claims 单独统计，用于解释 TCCR 上限和 reference domain 的 false alarm 问题。
- 该小节不需要大规模标注，但应证明 pipeline 的第一步不是未经检查的黑箱。

### 6.8 Runtime and Cost Measurement

- 报告每次 audit 的平均 latency、p95 latency、LLM token cost 或 approximate token count。
- 与 agent execution time 分开报告，说明 ReliableGuard 作为 production reliability layer 的部署代价。
- 当前代码已从 `ReliabilityReport.stage_latencies` 聚合阶段 mean/p95，并从 result row 或 `state["total_tokens"]` 聚合正 token counts。
- 建议增加一张表：claim extraction time、verification time、risk/policy time、report generation time、total audit time 和 token count。

### 6.9 Implementation Details

- Python 3.12。
- LangGraph-based agent execution。
- OpenRouter-compatible LLM calls。
- SQLite ecommerce database。
- local reference fixtures and optional external verifier sources disabled by default。
- trace artifacts written under logs，benchmark results written under results。

## 7. Results

### 7.1 Overall Performance Across Ablation Settings

- 对比 V1、V2、V3 在两个领域和两个 evaluation sets 上的 FAR、False Alarm Rate、RDR 和 TCCR。
- 重点回答 intervention 是否降低 risky task 的 false acceptance。
- 若加入 FActScore-style final-answer-only baseline，则在此处报告其与 ReliableGuard final-answer-only / trace-state augmented variants 的差异。

### 7.2 RQ1: Claim-level Audit Accuracy and Coverage

- 按 F0-F5 failure categories 报告检测率。
- 区分 verifier error 与 claim extraction miss。
- 报告 claim coverage ceiling，尤其是 reference domain 中 aggregate / unverifiable claims 的影响。
- 补充人工标注子集上的 claim extraction precision、recall 和 F1。

### 7.3 RQ2: Cross-domain Framework Generalizability

- 并排对比 ecommerce 与 reference 两个域在同一套指标（FAR、RDR、TCCR、reliability_score 分布）上的结果。
- 展示 evidence_state 分布差异：ecommerce 以 supported/contradicted 为主（DB 查询精确）；reference 以 unverifiable 为主（agent 倾向于聚合陈述）。
- 论证：这种域间差异本身由 unverifiable_count 和 TCCR 在框架内部解释，而不是框架失效的表现——这是标准化贡献的核心证据。
- V2 vs V3 的 enforcement 权衡（FAR/false alarm 权衡）作为本节子分析报告，说明 intervention 开关在两个域上的不同效果。

### 7.4 RQ3: Final-answer-only versus Trace/State-augmented Auditing

- 对比同一代码版本、同一 seeds、同一 Set A ecommerce 场景下的 V3_Intervention 与 V3_NoStructural。
- 旧批次数据已归档到 `results/_archive/rq3_ablation_20260514/`；后续完整批次快照已保存为 `results/_archive/full_experiment_snapshot_20260522.tar.gz`。这些只作为 preservation / preliminary evidence；最终论文数字必须来自当前修复后代码重跑生成的 timestamped `results/rq3_ablation/` 输出。
- 关键分析：差距是否主要来自 F2 检测（pre-execution policy）而非 F4（post-hoc claim verification 已能覆盖）。
- 结论：structural audit 对 ecommerce 的独特贡献是 pre-execution 策略违规检测，而非 post-hoc 状态不一致检测。
- 将 high-value order policy violation（F2）作为 structural audit 贡献的代表性案例，将 false-success database mutation（F4）作为 claim pipeline 已能覆盖的对照案例。

### 7.5 Domain-level Analysis

- ecommerce：说明 trace/state evidence 更稳定，因此 structural audit 有较高增益。
- reference：说明 evidence heterogeneity、claim granularity 和 unverifiable aggregate claims 导致 false alarm 与 coverage 问题。

### 7.6 Case Studies

建议选择三个案例：

- **Case 1: False-success ecommerce mutation**  
  final answer 声称订单创建成功，但 database state unchanged。

- **Case 2: High-value order policy violation**  
  tool call 触发 amount threshold，structural signal 导致 BLOCK。

- **Case 3: Reference metadata mismatch**  
  DOI、title、author 或 publication year 与 metadata 不一致，展示 claim-to-evidence trace。

### 7.7 Expected or Observed Findings

若实验结果已固定，可写为 observed findings；若仍在整理，应写为 expected findings 或 preliminary findings。

- ecommerce 中 trace/state-augmented auditing 预计会显著提升 detection rate；最终数值以冻结代码后的 Set A 和 RQ3 同批结果为准。
- reference 中 enforced intervention 可能产生高 false alarm rate，主要原因预计是 claim extraction 产生大量 unverifiable aggregate claims；最终用 evidence-state 表和 TCCR 解释。

### 7.8 Runtime and Cost Results

- 报告平均 audit latency、p95 latency 与 token cost。
- 区分 neural stages 和 symbolic stages 的开销。
- 使用 `stage_latency_mean_ms`、`stage_latency_p95_ms`、`avg_tokens` 和 `total_tokens_sum` 填表。
- 记录对应的 timestamped results 目录和 commit hash，避免混用归档旧批次与修复后新批次。
- 讨论该开销对 offline benchmark、interactive agent 和 production monitoring 三种使用方式的影响。

## 8. Discussion

### 8.1 Why Trace/State-augmented Auditing Matters—and Where It Does Not

ReliableGuard 的受控消融实验（V3 vs V3_NoStructural）用于揭示 trace/state augmentation 的价值边界，而非只是一个总体检测增益数字。最终论证应使用修复后冻结代码重跑的同批 RQ3 数据；`results/_archive/full_experiment_snapshot_20260522.tar.gz` 和更早旧批次只作为设计验证与复现实验参考。这个边界在架构层面有明确的解释。

**Claim pipeline 在没有 trace/state 的情况下能覆盖的：**

- **F3（虚构数据）**：agent 声称一个 DB 里不存在的实体 → claim pipeline 查询 DB → not_found → BLOCK。不需要任何 trace。
- **F4（false-success）**：agent 说"order confirmed"，但工具实际上没有改变 DB 状态。Claim pipeline 提取声明"order status is confirmed"，查询 DB → status = pending → contradicted → BLOCK。Claim pipeline 本质上是一个 post-hoc 事实一致性检查器——它把最终回答里的声明拿去和当前 domain state 对比。工具调用是否"成功报告了"并不重要，重要的是最终状态。

**Structural audit 独立负责的：**

- **F2（策略违规）**：agent 创建了 amount = 8000 的订单。Claim pipeline 提取声明"order amount is 8000"，查询 DB → amount = 8000 ✓ → supported → PASS。DB 状态是正确的，事实全部对应。问题在于：这个操作在执行前违反了 amount > 5000 需要审批的业务策略。策略违规发生在状态变化之前，而不是状态之中。任何事后验证都无法发现它，因为执行结果里没有任何"错误"可供核实。只有 pre-execution check 在工具调用前检查 `amount=8000 > 5000` 才能拦截。

**原则性的边界描述：**

这不是"trace/state 提供了更多信息"那么简单。边界在于：**失败是否在 post-execution domain state 里留下可观测的矛盾**。

- 如果是（F3、F4）：claim pipeline 覆盖，structural audit 不带来额外增益。
- 如果不是（F2）：domain state 在执行后是正确的，claim pipeline 天然盲区，只有 pre-execution structural audit 能检测。

**架构意义：**

这解释了为什么 ReliableGuard 的双层设计是必要的，而不只是"ecommerce 比 reference 多了一个组件"：

- Neural claim pipeline：language understanding + post-hoc factual consistency checking
- Symbolic structural audit：business rule encoding + pre-execution enforcement

两层的覆盖域不重叠，任何一层都不能替代另一层。这一设计原则对新领域的扩展同样成立：如果新领域存在"操作结果正确但操作决策不合规"的失败场景（医疗审批、财务合规、权限控制），structural audit 是必须的；如果失败都表现为最终状态的事实不一致，claim pipeline 就已足够。

### 8.2 Domain-dependent Reliability

- state-grounded domain 的 verifier 更容易确定 supported / contradicted。
- evidence-grounded citation domain 更依赖 claim extraction quality 和 metadata availability。

### 8.3 Audit versus Enforcement

- audit-only 更适合作为 diagnostic layer。
- enforced intervention 更适合高风险场景，但需要 calibration，避免 excessive false alarm。

### 8.4 Claim Extraction as a Bottleneck

- 分析 claim extraction miss 如何限制 audit coverage。
- 讨论 aggregate claims、implicit claims、ambiguous claims 和 overly broad claims。

### 8.5 Practical Implications

- ReliableGuard 可作为 agent reliability layer，而不是替代模型训练、RLHF 或 universal hallucination detector。
- 对 production agent system 的意义：可审计、可追踪、可复现、可配置干预。

### 8.6 External Baseline Interpretation

- 主动说明本文的核心证据来自 controlled ablation，而不是广泛 external benchmark competition。
- 解释为什么 FActScore、LangSmith、Langfuse、DeepEval 与 ReliableGuard 的评估对象不同：它们可以评估文本事实性或记录 agent traces，但通常不定义 domain-specific evidence state、verifier adapter contract 和 intervention semantics。
- 若没有实现外部 baseline，应明确写为限制，并放入 Future Work。

## 9. Limitations

ReliableGuard 有三个需要正面陈述的限制：

- **Latency and token cost**：audit pipeline 每次运行都会增加 LLM 调用、verification 和 trace logging 开销，因此不适合所有低延迟场景。
- **Claim extraction coverage**：系统上限受 LLM extractor 将 agent answer 分解为 atomic verifiable claims 的能力约束；未被抽取的事实无法被 verifier 检测。
- **Domain adapter development**：每个新领域都需要合适的 grounding artifacts、claim types 和 verifier adapter；当前实现不是无需配置即可泛化到任意 agent 系统的通用检测器。

这些限制不是附带问题，而是 ReliableGuard 部署边界的一部分，也为后续通用化工作提供直接动机。

## 10. Threats to Validity

### 10.1 Internal Validity

- LLM 输出随机性可能影响 claim extraction 和 agent behavior。
- prompt design、policy threshold 和 verifier implementation 可能影响结果。

### 10.2 Construct Validity

- PASS/WARN/BLOCK 是否充分代表真实可靠性需要讨论。
- evidence_state 到 risk_score 的映射可能引入人为设计偏差。

### 10.3 External Validity

- 当前只覆盖 ecommerce 和 academic reference 两个领域。
- 这两个领域分别代表工业事务型 agent 和学术证据型 agent，覆盖结构化状态驱动与异构证据驱动两类部署模式，但仍不能代表所有 real-world agent domains。
- 新领域需要新的 grounding artifacts、verifier adapters 和 benchmark scenarios。

### 10.4 Benchmark Validity

- Set A 可能偏向已知 F0-F5 failure patterns。
- Set B 虽用于泛化压力测试，但仍不能代表所有 real-world agent failures。

### 10.5 Reproducibility

- 外部 API、模型版本、OpenRouter routing 和 live metadata sources 可能导致结果波动。
- 因此默认 benchmark verification 应 offline by default。

### 10.6 Baseline Validity

- 当前主实验是 internal ablation，而不是与所有 alternative factuality / observability tools 的完整 benchmark 对比。
- 若只加入 FActScore-style final-answer-only baseline，应说明它主要用于验证 final-answer-only factuality checking 的边界，而不是代表完整 agent reliability tooling。
- 更系统的 external baseline comparison 应放入 Future Work。

## 11. Future Work

### 11.1 Plug-and-play Verifier Adapter Scaffolding

- 当前实现需要 domain-specific verifier adapters。
- 一个自然扩展是提供 configuration-driven adapter scaffolding，让用户通过 declarative config file 或 lightweight script 指定 grounding artifacts、claim types 和 verification rules，而不必编写完整 custom verifier code。
- 这会把 ReliableGuard 从 two-domain research prototype 推向可复用的 reliability layer，适配更多 arbitrary tool-using agent systems。

### 11.2 Broader Domain and Baseline Evaluation

- 扩展到更多高风险 agent 场景，例如 healthcare workflow、finance operations、legal document review、enterprise database agents。
- 与 FActScore-style factuality checking、LLM-as-judge evaluators、observability platforms 和 agent benchmark metrics 建立更系统的对比。

### 11.3 Better Claim Extraction and Calibration

- 改进 claim extraction granularity，减少 aggregate unverifiable claims。
- 研究 adaptive calibration for intervention policies，降低 reference domain 中的 false alarm。
- 探索 human-in-the-loop review，用于修正 high-risk 或 low-confidence verdict。

## 12. Conclusion

- 重申 thesis claim：externally verifiable failures in tool-using LLM agents can be quantified, standardized, and traced through a claim-level runtime auditing harness。
- 总结 ReliableGuard 的方法：claim-level extraction、domain verification、risk scoring、policy intervention、trace reporting。
- 总结实验结论：state-grounded ecommerce 中 trace/state augmentation 显著有效；evidence-grounded reference 中 coverage 和 calibration 是主要限制。
- 收束到本文贡献边界：ReliableGuard 不声称解决所有 hallucination，也不优化底层模型，而是为有可观察 grounding artifacts 的 tool-using agents 提供可审计、可解释、可干预的可靠性层。

## Appendix 建议

- Appendix A: F0-F5 failure taxonomy details
- Appendix B: Prompt templates for claim extraction and classification
- Appendix C: Domain verifier adapter typed interface
- Appendix D: Trace report JSON schema
- Appendix E: Benchmark scenario construction
- Appendix F: Additional ablation tables
- Appendix G: Case-study trace reports
- Appendix H: Source-backed reference verification diagnostics

## 推荐图表

- **Figure 1**: Set A 主消融对比，V1/V2/V3 × ecommerce/reference 的 RDR、False Alarm 和 Safe Pass。
- **Figure 2**: Set A ecommerce 按 F1-F5 failure mode 的检测率。
- **Figure 3**: RQ3 structural audit 对比，V3_Intervention vs V3_NoStructural 的 F2/F4 检测率。
- **Figure 4**: Set B 泛化压力测试，V1/V2/V3 × ecommerce/reference 的 FAR 和 false alarm。
- **Table 1**: 主消融数值表，V1/V2/V3 × 两域的 FAR、RDR、False Alarm、Safe Pass、Pass Rate。
- **Table 2**: Evidence-state 分布表，supported、contradicted、unsupported、unverifiable、not_found 和 coverage。
- **Table 3**: Runtime latency 表，阶段 mean/p95 与 token cost。
- **Supplementary Table**: Claim extraction precision / recall on manually annotated subset。
- **Supplementary Table**: Related work comparison matrix。

## 建议写作主线

整篇论文应避免把 ReliableGuard 写成一个“万能 hallucination detector”。更稳妥的主线是：

ReliableGuard 针对的是工具调用型 LLM agents 中**可被外部证据验证的失败**。它的价值不是提升模型本身，而是把 agent 的输出、工具轨迹和环境状态转换为可量化、可标准化、可追踪的可靠性证据。

领域选择的叙事应从现实部署场景出发：ecommerce 代表工业级事务型 agent，academic reference 代表学术生产型 agent。二者分别覆盖结构化状态驱动与异构证据驱动两种主流部署模式。实验应突出两个结论：第一，在 state-grounded 任务中，仅看 final answer 对 pre-execution policy violation 不够，trace/state auditing 能补足该类盲区；第二，在 evidence-grounded 任务中，claim extraction coverage、evidence-state distribution 和 verifier calibration 决定了系统上限。
