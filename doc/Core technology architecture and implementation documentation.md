这份技术架构文档（Tech Spec）将把我们之前讨论的所有业务逻辑、Agent 编排、低成本 RAG 和风控模型整合在一起，作为研发团队的第一阶段落地蓝图。

作为产品经理，我的要求是：**技术必须为业务逻辑服务，拒绝为了 AI 而 AI。金融系统的底线是“确定性（Determinism）”。**

# ---

**核心技术架构与实施文档 (Tech Spec)**

**项目名称：** AI 增强型价值投资辅助系统 (A/H 股专版)

**文档版本：** V1.0 \- MVP 阶段

## **1\. 系统总体架构设计**

系统采用 **分离式架构 (Decoupled Architecture)**，将“大模型的语言理解能力”与“传统程序的精确计算能力”严格分开。

Code snippet

graph TD  
    subgraph "1. Data Ingestion & RAG (数据处理层)"  
        A1\[Tushare/AKShare API\] \--\> B\[结构化数据库 PostgreSQL\]  
        A2\[公告 PDF/网页\] \--\> C\[Markdown 转换器 Unstructured\]  
        C \--\> D\[Hybrid RAG: Qdrant \+ pgvector\]  
    end

    subgraph "2. Agentic Workflow (LangGraph 编排层)"  
        E\[主控 Agent: 意图识别\] \--\> F1\[排雷 Agent: 查附注/算分\]  
        E \--\> F2\[估值 Agent: 跑 DCF/PB 模型\]  
        E \--\> F3\[利差 Agent: 调取存款利率比对\]  
    end

    subgraph "3. Deterministic Tools (确定性工具层)"  
        F1 \--\> G1\[Python REPL: M-Score 计算\]  
        F2 \--\> G2\[Python REPL: DCF 公式\]  
        F3 \--\> G3\[API: 实时抓取国债/存单利率\]  
    end

    subgraph "4. Application Layer (前端展示层)"  
        G1 & G2 & G3 \--\> H\[Next.js \+ Tailwind CSS UI\]  
        H \--\> I\[Dashboard: 机会成本 / 安全边际 / 风险雷达\]  
    end

## ---

**2\. 核心模块技术实现方案**

### **2.1 混合检索 RAG 引擎 (Hybrid RAG)**

解决 A/H 股几百页财报带来的信息过载和幻觉问题。

* **文档预处理：** 使用开源的 Marker 或 Unstructured.io 将 PDF 转换为含有表格结构的 Markdown。  
* **分块策略 (Chunking)：** 采用 **Parent-Document Retrieval**（父子文档检索）。子块设为 500 tokens 用于高精度向量比对，命中后返回 2000 tokens 的父块上下文给 LLM。  
* **双路召回存储：**  
  * **向量库 (Vector Store)：** 使用本地 Docker 部署 Qdrant。  
  * **嵌入模型 (Embedding)：** 采用国产开源 bge-m3（对中文财务专有名词理解好）。  
  * **元数据库 (Metadata)：** 使用 PostgreSQL \+ pgvector 存储年份、行业、公司代码等结构化标签，查询时先按条件过滤，再做向量相似度搜索。

### **2.2 LangGraph 多智能体编排**

采用基于状态机（State Machine）的有环图架构，确保分析逻辑可回溯、可中断。

* **核心状态定义 (State Schema)：**  
  系统在流转中始终维护一个全局状态字典，包含原始数据、风险评分和计算结果。  
* **循环验证逻辑：** 如果“估值 Agent”发现自由现金流数据缺失，框架允许状态流转回“数据提取 Agent”重新查阅财报附注，而不是直接报错。

### **2.3 机会成本利差引擎 (Yield Gap Engine)**

这是系统的核心业务亮点，必须保证计算绝对精确。

* **数据源：** 每日定时任务 (Cron Job) 拉取中国 10 年期国债收益率、各大行 3 年期大额存单基准利率，以及香港金管局基准利率。  
* **税后股息计算公式：**  
  使用 Python 工具执行计算，严禁 LLM 直接相减。  
  $$DY\_{net} \= \\frac{Dividend \\times (1 \- TaxRate)}{Price}$$  
  *(注：针对港股通，系统自动将 $TaxRate$ 设为 20%)*  
* **利差判断逻辑：**  
  $$YG \= DY\_{net} \- \\max(R\_{f\\\_bond}, R\_{f\\\_deposit})$$  
  若 $YG \< 0$，触发前端红色预警，中断估值推荐。

## ---

**3\. 风险控制与排雷模块设计 (Risk Shield)**

### **3.1 财务欺诈识别 (Beneish M-Score)**

将法务会计逻辑代码化。Agent 提取过去两年的财报关键科目（应收账款、销售收入、固定资产等），调用 Python 脚本计算 M-Score。

核心逻辑公式（由系统在沙盒中执行）：

$$M \= \-4.84 \+ 0.92 \\times DSRI \+ 0.528 \\times GMI \+ 0.404 \\times AQI \+ 0.892 \\times SGI \+ \\dots$$

* **阈值判定：** 当 $M \> \-1.78$ 时，强制将该股票打上“造假高危”标签。

### **3.2 语义矛盾检测 (Semantic Conflict Check)**

* **机制：** 让 LLM 并行阅读“管理层讨论与分析 (MD\&A)”和“审计师意见”。  
* **Prompt 约束：** 强制提取“关联交易”、“会计估计变更”、“存货减值”三大敏感词汇，若出现异常变动，强制在前端高亮展示。

## ---

**4\. 接口与数据交互协议 (API Design)**

为前端 Dashboard 提供的数据接口规范建议。

| 接口端点 (Endpoint) | 请求参数 (Payload) | 核心返回字段 (Response) | 说明 |
| :---- | :---- | :---- | :---- |
| /api/v1/analyze/risk | {"ticker": "600519.SH"} | m\_score, risk\_level, red\_flags (List) | 返回排雷诊断结果及具体风险点 |
| /api/v1/analyze/yield | {"ticker": "0700.HK", "cost\_basis": 300} | current\_dy, rf\_rate, yield\_gap, recommendation | 机会成本对标对比 |
| /api/v1/analyze/dcf | {"ticker": "000002.SZ", "growth\_rate": 0.05} | intrinsic\_value, margin\_of\_safety, assumptions | 动态 DCF 估值，支持前端滑块动态传参重算 |

## ---

**5\. 部署与工程化建议**

* **模型选型：**  
  * 推理核心：接入 Claude 3.5 Sonnet 或 DeepSeek-V3 API（代码逻辑与指令遵循能力强）。  
  * 辅助处理（如表格总结）：使用低成本模型如 GPT-4o-mini 或本地 Qwen-2.5。  
* **计算沙盒 (Security)：** Python 代码的执行必须放在隔离的 Docker 容器中执行，防止 Agent 生成的恶意代码破坏宿主机系统。  
* **缓存机制 (Caching)：** 使用 Redis 缓存热门股票的计算结果。如果无重大公告且股价波动小于 1%，直接返回昨日缓存数据，大幅降低 Token 消耗。

### ---

**PM 的最终落地建议 (Execution Plan)**

不要试图在 V1.0 就把这些全部做完。**马斯克式的执行力在于快速验证核心假设。**

**我建议的前两周 Sprint 目标：**

只做 A 股沪深 300 的成分股。只上线两个功能：**“自动计算 M-Score 排雷分”和“股息率 vs 大额存单利差图”**。连大模型对话框都不需要，先用跑批的方式生成静态报告，看看你的目标用户愿不愿意为这 300 份报告买单。



