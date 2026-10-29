# 产品使用与安全问答 RAG 设计

- 日期：2026-10-26
- 状态：已确认，待实施计划
- 项目目录：`D:\1\项目汇总\rag重构`

## 1. 目标

建设一个面向电子产品用户的使用与安全问答助手。用户可以先用自然语言说出产品型号，或从产品目录中选择型号，然后进行多轮问答。

系统以产品手册为主要依据，返回带文档、版本、页码和章节引用的回答。手册证据不足时，允许提供明确标注的通用说明；涉及安全、维修、拆机和危险操作时，只能使用手册证据。

项目必须覆盖从需求、数据导入、检索、回答、评测、部署到故障处理的完整闭环，并能解释关键技术和参数的选择依据。

## 2. 产品范围

### 2.1 第一版支持的产品

第一版固定支持三类产品、每类两款，共六款：

| 类别 | 产品 | 文档 |
| --- | --- | --- |
| 平板 | 华为平板 C7 | `华为平板 C7 用户指南-(DBY-W09,HarmonyOS 2_01,ZH-CN).pdf` |
| 平板 | 华为擎云 C5 第 4 代 | `华为擎云 C5 (第4代) 用户指南-(BYD5-W10&AL10,HarmonyOS 4.3_01,zh-cn).pdf` |
| 笔记本 | HUAWEI MateBook B5-440 | `HUAWEI MateBook B5-440 用户指南-(KLVFZ,Windows11_02,zh-cn).pdf` |
| 笔记本 | 华为擎云 HM740 | `华为擎云 HM740 用户指南-(HM740-001&031,HarmonyOS 6.0_01,zh-cn).pdf` |
| 显示器 | 华为显示器 B5-341W | `华为显示器 B5-341W 用户指南-(ZQE-CBA,04,zh-cn).pdf` |
| 显示器 | 华为擎云 M272Q | `华为擎云 M272Q 用户指南-(XSN-27QBZ,02,zh-cn).pdf` |

源文档目录为 `D:\1\项目汇总\Rag项目\PythonProject16\doc`。

### 2.2 主要用户

- 主要用户：正在使用或已经购买产品的普通用户。
- 次要用户：需要快速查阅产品资料、但不需要销售推荐的销售人员。
- 管理员：负责上传文档、处理元数据冲突、验证和发布新版本。

### 2.3 第一版明确不做

- 价格、库存、促销、购买链接、竞品比较和购买建议。
- 普通用户文档上传。
- 用户注册、第三方登录和跨设备偏好同步。
- 跨会话自由文本长期记忆或用户画像。
- 多智能体自由协作。
- 长期运行、自主规划、无停止条件的 Agent。
- 知识图谱和联网搜索。
- 图片生成或基于设备照片的故障诊断。
- 公开互联网生产环境的高可用部署。

## 3. 回答策略

每次回答只有一个主要模式。

### 3.1 `manual_grounded`

- 结论必须来自当前产品当前活动版本的文档。
- 每个具体结论必须引用真实 Chunk。
- 引用展示文档名、版本、页码和章节路径。
- 不得补充检索上下文之外的具体参数、步骤或型号。

### 3.2 `general_explanation`

- 只允许解释低风险基础概念、术语，或建议联系官方支持。
- 必须显著标注“非手册内容”。
- 不得回答具体型号兼容性、具体设置步骤、故障原因、维修方案、保修承诺或安全处置。
- 不得与手册回答混合成无法区分的单一文本。

### 3.3 `refused`

- 型号未确定。
- 手册证据不足。
- 安全风险问题没有手册依据。
- verifier 两次均未通过。
- 检索或模型服务不可用。

### 3.4 安全优先规则

以下类型优先按安全风险处理：

- 冒烟、起火、爆炸、异常发热。
- 漏液、进水、触电、损坏电源线。
- 电池膨胀、异味、异常声音。
- 拆机、维修、改装、短接或绕过保护装置。

安全风险问题优先检索独立安全文档和 `safety` 章节。找不到依据时直接拒答并建议停止使用、断开电源并联系官方支持。不得使用通用知识生成具体处置步骤。

## 4. 总体架构

采用前后端分离和模块化单体。

运行边界：

```text
Browser
  -> Next.js web
  -> FastAPI api
       -> MySQL
       -> Qdrant
       -> LLM Provider
       -> Embedding Provider
       -> Reranker Provider
       -> Langfuse

FastAPI worker
  -> PDF 解析
  -> 章节和 Chunk 构建
  -> 远程 Dense 向量化
  -> 本地 Sparse 编码
  -> Qdrant 索引
  -> MySQL 状态更新
```

部署约束：

- `web`、`api`、`worker`、MySQL 和 Qdrant 在本地运行。
- Embedding、Reranker 和 LLM 使用远程 Provider。
- Langfuse 使用 Langfuse Cloud。
- 第一版不使用 Redis、Celery、MinIO 和微服务拆分。
- `api` 与 `worker` 共享同一后端代码库，使用不同启动入口。

## 5. 模块边界

### 5.1 `domain`

保存与框架无关的业务对象、值对象、错误和端口。

核心对象：

- Product
- ProductAlias
- DocumentFamily
- DocumentVersion
- DocumentType
- Section
- Chunk
- RetrievalCandidate
- RerankResult
- Conversation
- Message
- AnswerMode
- AnswerRun
- Citation
- IngestionBatch
- IngestionItem
- IndexVersion

### 5.2 `application`

负责用例编排：

- `answer_turn`：执行有限 retrieve-verify loop。
- `resolve_product`：解析用户输入中的产品型号。
- `rewrite_query`：将依赖上下文的追问改写为独立问题。
- `retrieve`：执行 Dense、Sparse、RRF 和精排。
- `generate_answer`：根据回答模式生成结果。
- `verify_answer`：检查引用和事实依据。
- `ingest_document`：协调导入、解析、切分、向量化和发布。
- `switch_active_version`：原子切换产品的活动文档版本。

### 5.3 `infrastructure`

实现领域端口：

- MySQL repositories 和 Alembic migrations。
- Qdrant vector index。
- 远程 Dense Embedding 客户端。
- 本地 BM25 Sparse 编码器。
- 远程 Reranker 客户端。
- LLM 客户端。
- MinerU 和 PyMuPDF PDF 解析适配器。
- Langfuse tracing adapter。
- 本地文件存储。

### 5.4 `api`

- FastAPI 路由。
- 请求和响应校验。
- 管理员登录和会话。
- 匿名 `visitor_id` Cookie。
- SSE 编码与断线取消。
- 统一错误响应。

### 5.5 `worker`

- 从 MySQL 任务表领取导入任务。
- 每个 worker 同时只处理一个 PDF。
- 保存阶段状态，支持幂等重试和断点恢复。

### 5.6 `harness`

- 直接调用 application 层。
- 执行 dev 和 locked test。
- 计算阶段指标和端到端指标。
- 输出 JSON 报告。
- 把 Trace 和分数写入 Langfuse。

## 6. 数据模型

### 6.1 产品和别名

`products`：

- `id`
- `name`
- `category`
- `brand`
- `status`
- `created_at`
- `updated_at`

`product_aliases`：

- `id`
- `product_id`
- `alias`
- `normalized_alias`
- `alias_type`

产品识别先经过规范化别名匹配，不经过 RAG。别名必须显式存在于产品目录中。

### 6.2 文档族和版本

`documents` 表示逻辑文档族：

- `id`
- `canonical_name`
- `manufacturer`
- `status`
- `created_at`
- `updated_at`

`document_versions` 表示具体文件版本：

- `id`
- `document_id`
- `file_blob_id`
- `version_label`
- `version_key`
- `version_source`
- `version_confidence`
- `sha256`
- `received_at`
- `effective_from`
- `effective_to`
- `published_at`
- `superseded_at`
- `status`
- `metadata_confidence`
- `metadata_evidence`
- `created_at`

版本状态：

```text
draft -> processing -> validated -> active -> superseded
                         \-> failed
```

`file_blobs`：

- `id`
- `sha256`
- `storage_uri`
- `size_bytes`
- `original_filename`
- `content_type`
- `created_at`

`product_document_bindings`：

- `id`
- `product_id`
- `document_id`
- `active_version_id`
- `created_at`
- `updated_at`

同一物理文件可以关联多个产品。每个产品分别维护自己的活动版本指针。

### 6.3 文档类型和章节

`document_types`：

- `id`
- `code`
- `name`

`document_version_types` 是文档版本和类型的多对多关系。管理员界面第一版最多选择两个文档类型，但数据库不限制为两个。

`document_sections`：

- `id`
- `document_version_id`
- `parent_section_id`
- `section_path`
- `title`
- `page_start`
- `page_end`
- `section_types`
- `order_index`

`section_types` 支持多值，例如 `safety`、`usage`、`specification`、`installation`、`troubleshooting`、`maintenance`。

### 6.4 Chunk 和索引

`chunks`：

- `id`
- `document_version_id`
- `section_id`
- `content`
- `content_hash`
- `page_start`
- `page_end`
- `section_path`
- `section_types`
- `block_ids`
- `order_index`

`index_versions`：

- `id`
- `chunker_version`
- `dense_provider`
- `dense_model`
- `dense_model_revision`
- `dense_dimension`
- `sparse_method`
- `sparse_tokenizer`
- `created_at`

`document_indexes`：

- `id`
- `document_version_id`
- `index_version_id`
- `status`
- `chunk_count`
- `indexed_at`
- `error_code`
- `error_message`

### 6.5 导入批次

`ingestion_batches`：

- `id`
- `source_type`
- `status`
- `created_by`
- `created_at`
- `completed_at`

`ingestion_items`：

- `id`
- `batch_id`
- `relative_path`
- `original_filename`
- `sha256`
- `detected_product_ids`
- `selected_product_ids`
- `detected_version_label`
- `version_source`
- `document_type_codes`
- `confidence`
- `conflict_type`
- `status`
- `error_code`
- `error_message`

### 6.6 会话与偏好

`conversations`：

- `id`
- `visitor_id`
- `product_id`
- `status`
- `created_at`
- `updated_at`

`messages`：

- `id`
- `conversation_id`
- `role`
- `content`
- `rewritten_query`
- `created_at`

`conversation_summaries`：

- `id`
- `conversation_id`
- `summary`
- `covered_message_id`
- `token_estimate`
- `created_at`

`visitor_preferences`：

- `visitor_id`
- `language`
- `answer_detail`
- `show_citations`
- `created_at`
- `updated_at`

偏好只保存用户明确设置的低敏感配置，不保存推断画像。

### 6.7 回答与反馈

`answer_runs`：

- `id`
- `conversation_id`
- `user_message_id`
- `assistant_message_id`
- `mode`
- `trace_id`
- `index_version_id`
- `retrieved_document_version_ids`
- `citations_snapshot`
- `verification_result`
- `retry_count`
- `latency_ms`
- `token_usage`
- `estimated_cost`
- `status`
- `created_at`

`feedback`：

- `id`
- `answer_run_id`
- `rating`
- `reason`
- `created_at`

引用快照以结构化 JSON 保存，至少包含文档版本、页码、章节、Chunk ID 和引用原文。

## 7. Qdrant 数据契约

每个 Qdrant point 包含：

- Dense vector。
- Sparse vector。
- `chunk_id`
- `document_version_id`
- `index_version_id`
- `product_ids`
- `document_type_codes`
- `section_types`
- `page_start`
- `page_end`
- `section_path`
- `content`
- `content_hash`

MySQL 是事实来源。Qdrant 索引必须可以从 MySQL、原始 PDF 和索引配置重建。

检索时先读取当前产品绑定的活动文档版本，然后按 `document_version_id` 和 `index_version_id` 过滤 Qdrant。不得只按时间或文件名过滤版本。

## 8. 管理员导入

### 8.1 上传方式

管理员登录后可以使用：

- 单文件上传。
- 目录上传。

两种方式共用同一个批次接口。目录上传时，每个文件独立处理，一个文件失败不导致整个批次回滚。

### 8.2 SHA-256 去重

服务器在接收文件后计算 SHA-256。

- SHA-256 相同：不重复保存和解析。
- 如果已有文件尚未关联当前产品，管理员可以把现有文件关联到当前产品。
- 如果已经关联当前产品，提示内容已存在并跳过。

物理文件按内容寻址保存，数据库保存稳定身份和业务关系。

### 8.3 同名文件冲突

同名判断限定在产品或当前导入上下文中，比较规范化文件名。

内容相同：提示文件已存在。

内容不同：暂停该文件并返回：

- `replace_as_new_version`
- `rename_and_continue`
- `cancel`

`replace_as_new_version` 在内部创建新文档版本，旧版本转为 `superseded`，不删除旧文件。只有从未发布的 `draft` 允许真正替换。

`rename_and_continue` 创建独立文档记录，不覆盖旧文件。

### 8.4 元数据自动识别

版本识别优先级：

1. 修订记录、版本号、文件编号和发布日期。
2. 封面、页眉、页脚和版权页。
3. PDF 元数据。
4. 文件名和目录提示。
5. 上传时间仅作为低置信度兜底。

上传时间字段为 `received_at`，不得当作真实业务版本。

如果无法提取版本，可以使用临时 `version_key`，例如 `received-20261025-001`，但界面和引用必须显示“版本未知”。

### 8.5 置信度规则

高置信度：

- 产品 ID 通过产品目录校验。
- 从文档内容提取到明确版本号或发布日期。
- 没有版本冲突。
- 自动通过元数据审核。

中置信度：

- 产品 ID 明确，但版本无法提取。
- 使用临时版本键。
- 管理员一键确认后才能进入发布流程。

低置信度：

- 产品或版本均未识别，或产品不在目录中。
- 必须人工填写 `product_id`。
- 版本可以保持未知。

所有文件都必须通过解析、Chunk、索引和完整性验证。高置信度只跳过元数据人工审核，不跳过质量验证。

安全手册在切换活动版本之前必须人工确认一次。

### 8.6 预览表

目录上传后自动生成预览表：

- 原始文件名
- 相对路径
- SHA-256
- 上传时间
- 产品识别结果
- 文档类型
- 版本号
- 版本提取来源
- 发布日期
- 是否重复
- 同名冲突
- 置信度
- 建议状态

预览表主要由确定性程序生成。只有非结构化字段无法提取时，才调用一次结构化 LLM 提取。LLM 输出必须经过 JSON Schema 和产品目录校验。

manifest 为可选项，用于批量覆盖或特殊目录。正常导入不要求人工逐份填写。

## 9. PDF 解析与 Chunk

### 9.1 解析器

主要解析器：MinerU。

备用解析器：PyMuPDF。

解析输出统一为文档、章节、标题、段落、列表、表格、警告和图片 OCR 的内部结构。每块内容保留页码、章节路径、块类型和原文位置。

扫描页或文本覆盖率不足的页面进入 OCR。纯图片不能生成空 Chunk。

### 9.2 文档类型和章节类型

文档层允许同时关联多个来源类型，例如 `user_guide` 和 `safety_guide`。混合文档使用 `mixed_manual`。

章节层使用内容类型：

- `safety`
- `usage`
- `specification`
- `installation`
- `troubleshooting`
- `maintenance`
- `legal`

### 9.3 Chunk 规则

- 目标长度：300 到 600 个中文字符。
- 最大长度：800 个中文字符。
- Chunk 正文前缀包含标题路径。
- 只对长段落使用 80 到 120 字重叠。
- 不跨章节重叠。
- 安全警告保持完整。
- 操作步骤按步骤组保持完整。
- 表格保留表头；大表按行组切分并重复表头。
- 相邻 Chunk 只在同一章节、同一操作步骤或同一表格内允许合并。

### 9.4 阶段状态

导入任务状态：

```text
uploaded -> parsed -> chunked -> embedded -> indexed -> validated
```

失败状态必须保存失败阶段、错误码和可恢复信息。

每个阶段必须幂等。重复执行不能生成重复 Chunk 或重复 Qdrant point。

### 9.5 发布条件

- 所有页面已解析或明确标记为图片页。
- 空 Chunk、超长 Chunk 和重复 Chunk 在允许范围内。
- Qdrant 写入数量与有效 Chunk 数量一致。
- 当前活动版本没有混入新版本 Chunk。
- `index_version` 和模型版本已记录。
- 安全文档已完成人工确认。

发布时在 MySQL 事务中切换活动版本。新版本失败时，旧版本继续提供服务。

## 10. 检索

### 10.1 基线参数

```text
Dense 粗排：30 条
Sparse 粗排：30 条
RRF 后精排候选：前 20 条
最终进入回答上下文：前 6 条
最大检索循环次数：2
```

这些值是基线，不是固定真理。通过 dev 集比较粗排 K、精排 K 和最终 K，再确定生产参数。

### 10.2 Dense

生产环境使用远程 Dense Embedding Provider，目标模型为 BGE-M3 或经 dev 评测证明更优的替代模型。

以下配置必须固定并记录：

- Provider
- 模型名称
- 模型 revision
- 向量维度
- 相似度度量

### 10.3 Sparse

如果远程 Provider 不返回 BGE-M3 Sparse 向量，则使用本地 BM25 与中文分词生成 Sparse 向量。

分词必须保留：

- 产品型号。
- 英文缩写。
- 数字和单位。
- 接口名称。
- 文档中的错误码。

### 10.4 RRF

Dense 和 Sparse 各自按排名融合：

```text
RRF(d) = sum(1 / (60 + rank_i(d)))
```

`60` 是 RRF 平滑常数，不是候选数或最终上下文数。

### 10.5 精排

默认使用远程 BGE-reranker-v2-m3 或经评测确认的替代 cross-encoder。精排只处理 RRF 后前 20 条候选，最终保留前 6 条。

### 10.6 检索过滤

必须过滤：

- 当前产品。
- 当前活动文档版本。
- 当前索引版本。

不得出现以下情况：

- 跨产品检索。
- 新旧版本混合。
- 使用旧索引回答新活动版本。
- 把同一 Chunk 多次加入同一上下文。

### 10.7 HyDE

HyDE 不进入第一版基线。

只有 dev 集证明模糊问题的召回不足时，才允许进行 HyDE 实验。HyDE 不得用于：

- 安全风险问题。
- 精确参数和型号问题。
- 没有证据时必须拒答的问题。

## 11. 多轮对话

保存当前会话原文，超过 Token 阈值后将较早消息压缩为滚动摘要。

新会话不跨会话继承设备上下文。偏好可以保存，但不保存自由文本长期记忆。

追问改写示例：

```text
上一轮：C7 支持蓝牙吗？
本轮：那怎么连接？
改写：华为平板 C7 如何连接蓝牙设备？
```

改写不得增加用户没有提及的型号或参数。改写失败时使用原问题并记录失败原因。

用户在会话中切换产品时，必须建立新的话题边界。上一产品的检索结果和事实不能参与新产品的回答。

## 12. 有限问答循环

每次提问执行：

1. 校验会话、产品和用户偏好。
2. 识别安全风险。
3. 加载最近消息和滚动摘要。
4. 必要时改写追问。
5. 解析产品；无法唯一确定时停止并询问。
6. 读取活动文档版本和索引版本。
7. Dense 和 Sparse 各召回 30 条。
8. RRF 合并并截取前 20 条。
9. 精排并选择前 6 条。
10. 按回答模式生成回答。
11. 执行 verifier。
12. 通过则返回；失败则最多重试一次。

### 12.1 第二次尝试

第二次尝试只允许：

- 改写遗漏上下文的查询。
- 补充同章节父级内容。
- 向用户提出澄清问题。

第二次仍失败则返回 `refused`，不进行第三次模型调用。

### 12.2 停止条件

- verifier 通过。
- 形成明确安全拒答。
- 完成第二次尝试仍失败。
- 用户取消或 SSE 断开。
- 不可恢复的 Provider、数据库或索引错误。

## 13. Verifier

### 13.1 确定性检查

- 引用编号存在。
- Chunk ID 存在。
- 文档版本和页码匹配。
- 引用属于当前产品和当前活动版本。
- 引用没有使用旧索引或未发布版本。
- 同一 Chunk 没有重复进入上下文。

### 13.2 语义检查

- 每个具体事实都能在引用 Chunk 中找到依据。
- 回答没有新增手册外的型号、参数和操作步骤。
- 安全回答没有使用通用知识补充。
- 通用说明包含明确的“非手册内容”标记。

验证失败原因必须写入 `answer_runs` 和 Langfuse Trace。

## 14. API 与 SSE

### 14.1 公开 API

```text
GET    /api/products
POST   /api/conversations
GET    /api/conversations/{id}
POST   /api/conversations/{id}/resolve-product
POST   /api/conversations/{id}/messages/stream
POST   /api/conversations/{id}/messages/{message_id}/feedback
GET    /api/preferences
PATCH  /api/preferences
```

### 14.2 SSE 事件

```text
run_started
product_resolved
status
answer_delta
citations
done
error
```

状态阶段：

- `retrieving`
- `reranking`
- `generating`
- `verifying`
- `retrying`

只发送用户需要的状态和最终回答增量。不得发送检索分数、内部 Prompt、模型思考或完整候选列表。

安全问答不能把未经 verifier 检查的模型文本直接流给用户。LLM 先完成生成，服务端完成引用和语义验证，再把已经批准的回答按文本片段通过 `answer_delta` 发送。SSE 仍然是流式体验，但不会暴露未经核验的内容。

事件顺序固定为：

```text
run_started
product_resolved
status(retrieving)
status(reranking)
status(generating)
status(verifying)
answer_delta
citations
done
```

发生重试时发送 `status(retrying)`，最终只能以 `done` 或 `error` 结束，不得同时发送两者。

SSE 必须包含心跳。连接断开时停止后续模型调用，保存已完成阶段和失败状态。

### 14.3 管理员 API

```text
POST   /api/admin/login
POST   /api/admin/logout
POST   /api/admin/imports
GET    /api/admin/imports
GET    /api/admin/imports/{id}
POST   /api/admin/imports/{id}/conflicts/{item_id}/resolve
POST   /api/admin/document-versions/{id}/publish
GET    /api/admin/documents
```

目录上传使用批次接口，manifest 可选。冲突处理返回三个明确动作：

- `replace_as_new_version`
- `rename_and_continue`
- `cancel`

## 15. 前端

### 15.1 公开问答工作台

- 产品类别和型号选择器。
- 自动型号识别和候选确认。
- 多轮聊天。
- 当前产品卡片。
- SSE 流式回答。
- 手册依据或通用说明标签。
- 引用侧栏。
- 用户偏好设置。
- 有帮助和无帮助反馈。

### 15.2 管理员工作台

- 单文件上传。
- 目录上传。
- 预览表。
- 同名冲突处理。
- 解析和索引状态。
- 文档版本列表。
- 活动版本查看和切换。

## 16. 安全和隐私

- 管理员接口必须登录，普通用户不能导入文档。
- 第一版只提供一个管理员账号，凭据由环境变量提供 Argon2 密码哈希，会话使用服务端签名 Cookie。
- 上传只接受 PDF，校验文件头、扩展名、大小和文件名。
- 禁止路径穿越和不可信相对路径。
- 匿名用户按 IP 和 `visitor_id` 限流。
- 限制消息长度和并发请求。
- Cookie 使用 `HttpOnly` 和 `SameSite=Lax`。
- 修改请求校验来源。
- 回答渲染前进行 HTML 清理。
- 检索到的文档内容视为不可信数据，不能覆盖系统指令。
- Langfuse 默认不记录完整 Prompt 和 Chunk 原文。
- 远程 Embedding、Reranker 和 LLM 会接收到必要的用户问题和 Chunk，隐私说明必须明确。

## 17. 本地部署

```text
Docker Compose
├── web
├── api
├── worker
├── mysql
└── qdrant

远程服务
├── Embedding Provider
├── Reranker Provider
├── LLM Provider
└── Langfuse Cloud
```

持久化：

- MySQL Volume。
- Qdrant Volume。
- 原始 PDF 文件目录。

配置通过环境变量注入。`.env` 不提交 Git。

健康检查：

- `/health/live`：进程存活。
- `/health/ready`：MySQL 和 Qdrant 可用。

## 18. 可观测性

应用日志使用 JSON 输出到容器标准输出。

Langfuse 记录：

- 产品和会话 ID 的不可逆标识。
- 每个阶段的 span。
- 模型、Token、耗时和错误。
- 检索和精排配置。
- verifier 结果。
- 评测分数。

MySQL 记录：

- 导入状态。
- 回答运行状态。
- 回答模式。
- 引用快照。
- 用户反馈。

Langfuse 故障不能阻止问答，但必须写本地错误日志。

## 19. 评测 harness

### 19.1 数据集

至少 72 个 case：

- 36 个 dev。
- 36 个 locked test。

每个 case 只归入一个主要分组，覆盖：

- 48 个手册可答问题，六款产品每款 8 个。
- 12 个通用说明、无答案和安全问题。
- 12 个多轮追问 case。

dev 和 test 都要按产品类别、回答模式和安全类型分层。test 在流程冻结前不得用于调参。

### 19.2 Case 契约

每个 case 至少包含：

- `case_id`
- `split`
- `product_id`
- `category`
- `messages`
- `expected_mode`
- `must_cite`
- `required_facts`
- `forbidden_claims`
- `reference_answer`
- `tags`

`must_cite` 使用稳定证据位置：

- `document_sha256`
- `page`
- `section_path`
- `evidence_quote`

不得直接标注 Chunk ID，因为 Chunk 会随切分实验变化。

### 19.3 阶段指标

- 产品识别准确率。
- 歧义处理正确率。
- Query Rewrite 正确率。
- 回答模式分类正确率。
- `Recall@20` 和 `Recall@30`。
- RRF 中正确证据的排名。
- 精排后正确证据是否进入前 6。
- `nDCG@6`。
- 必要事实覆盖率。
- 引用精确率。
- 无依据陈述率。
- 安全错误回答数。
- 正确拒答率。
- 平均延迟、P95 延迟和单次成本。

### 19.4 发布门槛

- 关键安全问题的错误回答数必须为 0。
- 无效引用数必须为 0。
- 引用必须可追溯到活动文档版本和真实页码。
- 同一回答不得包含重复 Chunk。
- 其余阈值在基线测试后确定，不允许预先伪造准确率。

### 19.5 Harness 输出

- 每个 case 的阶段结果。
- JSON 机器可读报告。
- 可视化摘要。
- 与上一版索引和 Prompt 的对比。
- Langfuse Trace 关联 ID。

harness 不依赖 Langfuse 才能运行。

## 20. 故障处理

- Embedding 或 Reranker 超时：有限重试后返回明确错误，不用通用知识伪造回答。
- LLM 超时：回答失败，不返回半截伪造答案。
- Qdrant 不可用：返回服务不可用。
- Langfuse 不可用：继续回答，并写本地错误日志。
- 索引中断：任务保持可恢复状态，不切换活动版本。
- 新版本验证失败：旧活动版本继续服务。
- SSE 断开：取消后续模型调用，记录 `aborted`。
- 产品识别失败：停止检索，要求用户选择。

## 21. 测试策略

### 21.1 单元测试

- 产品别名规范化。
- 版本提取和版本比较。
- SHA-256 去重和同名冲突。
- 结构化 Chunk 边界。
- 安全和步骤连续性。
- RRF 排序。
- Loop 停止条件。
- Verifier 确定性规则。

### 21.2 集成测试

- MySQL repository 和 Alembic migration。
- Qdrant 写入、过滤和版本隔离。
- 导入任务恢复和幂等性。
- 活动版本原子切换。
- SSE 事件顺序和断线取消。

### 21.3 前端端到端测试

- 选择产品。
- 对话中自动识别产品。
- 多轮追问。
- 引用侧栏。
- 通用说明标签。
- 管理员单文件上传。
- 管理员目录上传和冲突处理。

### 21.4 安全测试

- 伪造 PDF。
- 路径穿越。
- 超长消息。
- Prompt 注入。
- 跨型号检索。
- 旧版本泄漏。
- 未授权管理员接口。

## 22. 验收标准

### 22.1 功能

- 六款产品可以完成单轮和多轮问答。
- 支持自然语言型号识别和手动选择。
- 返回真实可追溯引用。
- 安全高风险问题没有证据时拒答。
- 管理员可以单文件和目录上传。
- 同名冲突提供三个处理动作。
- 新版本验证后才切换活动版本。

### 22.2 质量

- 关键安全问题错误回答数为 0。
- 无效引用数为 0。
- locked test 结果由 harness 生成并保存。
- 能解释 Chunk、K、Embedding、RRF 和 Reranker 的选型依据。

### 22.3 工程

- Docker Compose 一键启动。
- 单元、集成、API 和关键前端流程有自动测试。
- 日志、Trace、健康检查和错误状态可用。
- 能从 MySQL、PDF 和索引配置重建 Qdrant。
- README、架构、数据模型、API、评测和故障处理文档完整。

## 23. 关键 ADR

实施过程中至少记录以下决策：

- 为什么使用前后端分离和模块化单体。
- 为什么使用 MySQL 作为事实来源。
- 为什么使用 Qdrant。
- 为什么 Dense 使用远程 Provider。
- 为什么 Sparse 使用 BM25 或远程 Sparse。
- 为什么使用 RRF。
- 为什么初始精排 20 条、最终 6 条。
- 为什么 HyDE 延后。
- 为什么使用有限 retrieve-verify loop 而不是 LangGraph。
- 为什么文档版本和索引版本分离。
- 为什么使用稳定证据标注而不是 Chunk ID。

## 24. 已知风险

- 远程 Embedding 和 Reranker 的模型版本可能变化，必须固定 revision 并支持重新索引。
- 不同 Provider 的 Dense 和 Sparse 质量需要评测，不能只看模型名称。
- PDF 表格、跨页步骤和图片信息可能解析不完整。
- 六款产品与 72 个 case 的规模较小，结论不能直接外推到所有电子产品。
- Langfuse Cloud 和远程模型涉及数据离开本机，必须限制 Trace 内容并告知用户。
- 本地部署不适合公开互联网长期服务，第一版定位为本地演示和工程验证。

## 25. 后续版本

以下内容明确延后，不进入第一版实施：

- HyDE 和 query expansion 实验。
- 自动管理网页。
- 用户账号和跨设备同步。
- 结构化长期记忆。
- 多 Provider 自动路由。
- 图片理解和设备照片诊断。
- 知识图谱和联网搜索。
- 公开互联网高可用部署。
