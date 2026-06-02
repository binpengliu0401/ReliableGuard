# Related Work Skeleton for ReliableGuard

ReliableGuard is positioned as a neuro-symbolic post-hoc runtime verification harness for tool-using LLM agents. For the final thesis, the related-work chapter should foreground three direct comparison lines: runtime verification, factuality and hallucination detection, and LLM agent evaluation/observability. Neuro-symbolic AI remains in this skeleton as architecture motivation, but it should be used to explain the framework design rather than treated as the primary empirical comparison group.

The current empirical framing should remain bounded: the strongest evidence is in state-grounded ecommerce with trace/state structural audit; academic reference and Set B stress-test results show claim grounding and generalization limits. Related work comparisons should therefore avoid presenting ReliableGuard as a universal hallucination detector or a drop-in replacement for broad observability platforms.

## 1. Runtime Verification

Runtime Verification (RV) is the main theoretical anchor for ReliableGuard. Classical RV monitors execution traces and checks whether observed behavior satisfies a formal specification, often written in temporal logic, state machines, or rule systems.

### Key Papers

- **Havelund and Rosu, 2004, "An Overview of the Runtime Verification Tool Java PathExplorer."**  
  Presents Java PathExplorer as an RV tool that monitors Java execution traces against temporal-logic specifications and concurrency-error patterns.  
  Source: https://dblp.org/rec/journals/fmsd/HavelundR04a

- **Barringer, Goldberg, Havelund, and Sen, 2004, "Rule-Based Runtime Verification."**  
  Introduces EAGLE, a rule-based framework for finite-trace monitoring across temporal logic, regular expressions, real-time logics, and quantified properties.  
  Sources: https://doi.org/10.1007/978-3-540-24622-0_5 and https://research.manchester.ac.uk/en/publications/rule-based-runtime-verification/

- **Bartocci, Falcone, Francalanza, and Reger, 2018, "Introduction to Runtime Verification."**  
  Provides a modern primer on RV terminology, specification languages, instrumentation, monitoring, and monitorability.  
  Source: https://doi.org/10.1007/978-3-319-75632-5_1

- **Wang, Poskitt, and Sun, 2025, "AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents."**  
  Proposes a domain-specific language for specifying and enforcing runtime constraints on LLM agents. At the time of writing, this should be cited as an arXiv preprint rather than as a published conference paper.  
  Source: https://arxiv.org/abs/2503.18666

- **Luo et al., 2025, "AGrail: A Lifelong Agent Guardrail with Effective and Adaptive Safety Detection."**  
  Introduces an adaptive agent guardrail that generates and optimizes safety checks for LLM agents across tasks.  
  Source: https://aclanthology.org/2025.acl-long.399/

### Difference from ReliableGuard

Traditional RV primarily checks formally specified temporal or event-based properties over program traces. AgentSpec and AGrail move closer to LLM agents, but they focus mainly on action-level safety constraints or adaptive guardrails. ReliableGuard instead focuses on post-hoc reliability auditing of domain-grounded factual properties: whether claims made by a tool-using agent are supported by database state, bibliographic metadata, tool execution traces, or other external evidence.

### Positioning Draft

ReliableGuard inherits the RV view that system behavior should be checked against explicit specifications at runtime or after execution. However, the monitored properties in ReliableGuard are not limited to LTL/CTL-style temporal properties or pre-action safety constraints. They are claim-level, domain-grounded factual properties over agent outputs, execution traces, and external environment state.

## 2. Neuro-symbolic AI

Neuro-symbolic AI provides the architectural explanation for ReliableGuard. The key idea is to combine neural components for perception, language understanding, or pattern recognition with symbolic components for structured reasoning, verification, or rule-based inference.

### Key Papers

- **Rocktaschel and Riedel, 2017, "End-to-End Differentiable Proving."**  
  Introduces Neural Theorem Provers, combining neural representations with differentiable logical rule application.  
  Source: https://arxiv.org/abs/1705.11040

- **Manhaeve et al., 2018, "DeepProbLog: Neural Probabilistic Logic Programming."**  
  Integrates neural predicates into probabilistic logic programming, enabling hybrid symbolic and subsymbolic reasoning.  
  Source: https://arxiv.org/abs/1805.10872

- **Pan et al., 2023, "Logic-LM: Empowering Large Language Models with Symbolic Solvers for Faithful Logical Reasoning."**  
  Uses LLMs to translate natural language problems into symbolic formulations, then applies deterministic symbolic solvers.  
  Source: https://aclanthology.org/2023.findings-emnlp.248/

- **Gou et al., 2024, "CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing."**  
  Uses external tools to critique and revise LLM outputs, showing the value of tool-grounded feedback loops.  
  Sources: https://arxiv.org/abs/2305.11738 and https://www.microsoft.com/en-us/research/publication/critic-large-language-models-can-self-correct-with-tool-interactive-critiquing/

- **Gundawar et al., 2024, "Robust Planning with Compound LLM Architectures: An LLM-Modulo Approach."**  
  Pairs LLMs with sound external verifiers for planning and scheduling, using verifier feedback to reject or repair invalid outputs.  
  Source: https://arxiv.org/abs/2411.14484

### Difference from ReliableGuard

Most neuro-symbolic work focuses on improving reasoning, planning, or learning performance. The symbolic component is often used to solve a task more accurately, produce a better answer, or guide refinement. ReliableGuard uses a neuro-symbolic architecture for a different purpose: runtime monitoring and reliability auditing. Neural components extract and classify claims, while symbolic components verify them against domain evidence and produce traceable intervention decisions.

### Positioning Draft

ReliableGuard can be understood as a neuro-symbolic monitoring architecture. Unlike neuro-symbolic systems that use symbolic solvers to improve task completion, ReliableGuard uses symbolic verifiers as an audit layer over agent behavior. This shifts the role of neuro-symbolic integration from solving tasks to supervising externally verifiable claims and state transitions.

## 3. LLM Factuality and Hallucination Detection

Factuality and hallucination detection are directly related to ReliableGuard's claim verification component. This literature studies how to decompose, verify, score, and mitigate factual errors in generated text.

### Key Papers

- **Ji et al., 2023, "Survey of Hallucination in Natural Language Generation."**  
  Provides a broad survey of hallucination definitions, metrics, mitigation methods, and task-specific hallucination research in NLG.  
  Source: https://doi.org/10.1145/3571730

- **Min et al., 2023, "FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation."**  
  Breaks long-form text into atomic facts and computes the proportion supported by reliable knowledge sources.  
  Source: https://aclanthology.org/2023.emnlp-main.741/

- **Manakul, Liusie, and Gales, 2023, "SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models."**  
  Detects hallucination by checking consistency across multiple sampled generations from the same black-box model.  
  Source: https://aclanthology.org/2023.emnlp-main.557/

- **Huang et al., 2023, "A Survey on Hallucination in Large Language Models: Principles, Taxonomy, Challenges, and Open Questions."**  
  Surveys LLM hallucination taxonomies, causes, detection methods, mitigation techniques, and open challenges.  
  Source: https://arxiv.org/abs/2311.05232

### Difference from ReliableGuard

Existing factuality and hallucination work mostly evaluates static natural-language outputs. FActScore is especially close to ReliableGuard because both use claim-level decomposition and external evidence. ReliableGuard extends this idea from static text to tool-using agents, where correctness may depend on tool calls, database mutations, state transitions, and domain-specific verifier adapters.

### Positioning Draft

ReliableGuard builds on claim-level factuality evaluation but changes the evaluation target from generated text alone to agent behavior. In tool-using agents, a final answer may be linguistically plausible and factually grounded in isolation while still masking action-state inconsistencies or unsafe tool execution. ReliableGuard therefore combines factual claim verification with trace- and state-aware auditing.

## 4. LLM Agent Evaluation and Observability

LLM agent evaluation and observability frameworks provide the engineering context for ReliableGuard. Benchmarks evaluate whether agents can solve interactive tasks, while observability tools record traces, logs, latency, costs, and evaluation scores for debugging and production monitoring.

### Key Papers and Tools

- **Liu et al., 2024, "AgentBench: Evaluating LLMs as Agents."**  
  Provides a multi-environment benchmark for evaluating LLMs as agents across interactive tasks requiring reasoning and decision-making.  
  Sources: https://openreview.net/forum?id=zAdUB0aCTQ and https://proceedings.iclr.cc/paper_files/paper/2024/hash/e9df36b21ff4ee211a8b71ee8b7e9f57-Abstract-Conference.html

- **Yao et al., 2024, "tau-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains."**  
  Evaluates tool-using conversational agents in realistic domains with simulated users, domain policies, APIs, and final database-state comparison.  
  Source: https://arxiv.org/abs/2406.12045

- **Lu et al., 2025, "ToolSandbox: A Stateful, Conversational, Interactive Evaluation Benchmark for LLM Tool Use Capabilities."**  
  Evaluates LLM tool-use capabilities through stateful execution, implicit state dependencies, user simulation, and dynamic milestone checking.  
  Source: https://aclanthology.org/2025.findings-naacl.65/

- **LangSmith, 2024-2026, LLM application observability and evaluation platform.**  
  Supports offline and online evaluation, production traces, datasets, evaluators, experiments, and monitoring workflows.  
  Source: https://docs.langchain.com/langsmith/evaluation

- **Langfuse and DeepEval, 2024-2026, LLM observability and evaluation frameworks.**  
  Langfuse provides open-source tracing, prompt management, and evaluation workflows; DeepEval provides pytest-style LLM evaluation with agent, tool-use, RAG, and safety metrics.  
  Sources: https://langfuse.com/docs/ and https://deepeval.com/docs/introduction

### Difference from ReliableGuard

AgentBench, tau-bench, and ToolSandbox focus on benchmarking agent capability and task success. LangSmith, Langfuse, Phoenix, and DeepEval provide observability and evaluation infrastructure, but they are general platforms rather than a domain-grounded reliability monitor with a formal claim-verification pipeline. ReliableGuard occupies the middle ground: it is not only a benchmark and not only a tracing tool, but a harness that converts traces and outputs into claim-level reliability evidence and PASS/WARN/BLOCK decisions.

### Positioning Draft

ReliableGuard complements existing agent benchmarks and observability tools by adding a domain-grounded audit layer. Whereas benchmarks report whether an agent completed a task and observability platforms expose what happened during a run, ReliableGuard explains why a run should be trusted, warned, or blocked. Its contribution is a standardized claim-level pipeline that connects agent outputs, execution traces, environment state, evidence states, risk scores, and intervention verdicts.

## Comparison Matrix

| Work / Direction | Evaluation Object | Verification Method | Intervention Support | Domain-specific | Runtime Mode |
| --- | --- | --- | --- | --- | --- |
| Java PathExplorer / classical RV | Program traces, events, concurrency patterns | Symbolic temporal logic and rule-based monitoring | Usually detection; enforcement depends on monitor design | Usually program/system-specific | Online or offline trace monitoring |
| AgentSpec | LLM agent actions and runtime constraints | Symbolic DSL with trigger-predicate-enforcement rules | Yes | Yes, through user-defined rules | Runtime |
| AGrail | LLM agent actions and safety risks | Hybrid LLM-generated and optimized safety checks | Yes | Adaptive across tasks, but safety-policy dependent | Runtime |
| Logic-LM / LLM-Modulo | Reasoning outputs, plans, symbolic formulations | Hybrid LLM translation plus symbolic solver/verifier | Indirect, through rejection or repair | Domain/problem dependent | Mostly offline or iterative inference-time |
| CRITIC | LLM-generated text/code/toxicity outputs | Hybrid LLM plus external tool feedback | Indirect, through self-correction | Task/tool dependent | Inference-time |
| FActScore | Long-form generated text and atomic facts | Hybrid claim decomposition plus retrieval/LLM verification | No | Primarily knowledge-source dependent | Offline evaluation |
| SelfCheckGPT | Generated passages and sampled consistency | LLM-based sampling consistency | No | No external domain verifier | Offline evaluation |
| AgentBench | Agent trajectories across interactive environments | Benchmark scoring and environment-specific success metrics | No | Yes, via benchmark environments | Offline benchmark |
| tau-bench | Agent-user-tool conversations and final database state | Symbolic database-state comparison plus task success metrics | No | Yes, retail/airline domains | Offline benchmark with simulated interaction |
| ToolSandbox | Stateful conversational tool-use trajectories | Environment-state and milestone-based evaluation | No | Yes, through sandbox tasks and tools | Offline benchmark with interactive execution |
| LangSmith / Langfuse / Phoenix | LLM app traces, runs, spans, scores | LLM-based, rule-based, human, and custom evaluators | Limited; mainly monitoring and alerting workflows | Application-specific configuration | Online and offline |
| DeepEval | LLM app outputs, traces, agents, RAG systems | LLM-as-judge, DAG/rule metrics, built-in metrics | Test failure in CI; not domain intervention by default | Configurable | Offline and CI-oriented, with platform monitoring |
| **ReliableGuard** | Agent final answer, claim traces, tool execution traces, database state, bibliographic metadata | **Hybrid neuro-symbolic claim extraction plus symbolic domain verifiers** | **Yes: PASS/WARN/BLOCK** | **Yes, via verifier adapters and domain contexts** | **Post-hoc runtime audit; offline benchmark-compatible** |

## Draft Synthesis Paragraph

Taken together, prior work provides three foundations for ReliableGuard: runtime verification supplies the monitor-and-trace paradigm, neuro-symbolic AI supplies the neural-symbolic decomposition pattern, and factuality evaluation supplies claim-level evidence checking. Agent benchmarks and observability tools further establish the need to evaluate and debug agents through traces and environment interaction. ReliableGuard differs by integrating these strands into a single reliability harness for tool-using LLM agents: it extracts factual claims from agent outputs, verifies them against domain-grounded artifacts, scores risk, applies intervention policies, and records traceable audit reports.

ReliableGuard additionally addresses a standardization gap that prior work does not resolve. Existing factuality evaluation works such as FActScore operate on a single domain or knowledge source and do not define a domain-portable verification contract. Agent benchmarks such as tau-bench use domain-specific success metrics that cannot be compared across tasks or domains. ReliableGuard instead defines a unified evidence-state taxonomy, claim-type weight matrix, and reliability score formula that apply identically across structurally different domains. This allows domain-dependent differences in agent behavior—such as the high unverifiable claim rate in academic reference tasks versus the precise state-grounded failures in ecommerce tasks—to be expressed and compared within the same measurement framework, rather than requiring separate evaluation protocols per domain.

## Citation Verification Notes

The following checks were performed before using this skeleton as thesis material.

| Entry | Verification status | Stable source to use |
| --- | --- | --- |
| AgentSpec | Verified on arXiv. Cite as an arXiv preprint unless and until the final ICSE 2026 proceedings citation is used. | https://arxiv.org/abs/2503.18666 |
| AGrail | Verified on ACL Anthology as `2025.acl-long.399`, with DOI `10.18653/v1/2025.acl-long.399`. | https://aclanthology.org/2025.acl-long.399/ |
| AgentBench | Verified on both OpenReview and ICLR Proceedings. OpenReview is the safest citation source for ICLR metadata. | https://openreview.net/forum?id=zAdUB0aCTQ |
| CRITIC | Verified on both arXiv and Microsoft Research. arXiv is the safer citation source; the Microsoft page is useful for affiliation/context. | https://arxiv.org/abs/2305.11738 |
| Rule-Based Runtime Verification | Verified via Manchester Research Explorer and DOI references in Springer-linked bibliographies. | https://doi.org/10.1007/978-3-540-24622-0_5 |
| Java PathExplorer | Verified via DBLP with DOI metadata. | https://dblp.org/rec/journals/fmsd/HavelundR04a |
| Introduction to Runtime Verification | Verified via Manchester Research Explorer with DOI `10.1007/978-3-319-75632-5_1`. | https://research.manchester.ac.uk/en/publications/introduction-to-runtime-verification/ |
| Neural Theorem Provers | Verified on arXiv as `1705.11040`. | https://arxiv.org/abs/1705.11040 |
| DeepProbLog | Verified on arXiv as `1805.10872`; extended journal version exists in Artificial Intelligence. | https://arxiv.org/abs/1805.10872 |
| Logic-LM | Verified on ACL Anthology as Findings of EMNLP 2023. | https://aclanthology.org/2023.findings-emnlp.248/ |
| FActScore | Verified on ACL Anthology as EMNLP 2023. | https://aclanthology.org/2023.emnlp-main.741/ |
| SelfCheckGPT | Verified on ACL Anthology as EMNLP 2023. | https://aclanthology.org/2023.emnlp-main.557/ |
| ToolSandbox | Verified on ACL Anthology as Findings of NAACL 2025, with DOI `10.18653/v1/2025.findings-naacl.65`. | https://aclanthology.org/2025.findings-naacl.65/ |
| tau-bench | Verified on arXiv as `2406.12045`. | https://arxiv.org/abs/2406.12045 |
| LangSmith / Langfuse / DeepEval | Verified against official documentation pages. Treat these as engineering tools rather than peer-reviewed literature. | https://docs.langchain.com/langsmith/evaluation, https://langfuse.com/docs, https://deepeval.com/docs/introduction |

For the final thesis bibliography, prefer publisher, ACL Anthology, OpenReview, arXiv, DBLP, or DOI links over secondary blog posts and AI paper-indexing websites.
