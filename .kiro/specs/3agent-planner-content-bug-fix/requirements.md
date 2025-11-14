# 3Agent Planner内容误保存Bug修复需求文档

## Introduction

3Agent对话模式在生成章节时，存在将Planner Agent的分析内容误保存为章节正文的严重Bug。本文档定义修复该Bug的需求。

## Glossary

- **3Agent对话模式**: 使用Planner、Writer、Reviewer、Summarizer四个Agent协作生成章节的模式
- **Planner Agent**: 负责分析大纲、规划内容、查询历史信息的Agent
- **Writer Agent**: 负责撰写章节正文的Agent
- **Chapter Content**: 章节正文内容，应该是小说故事文本
- **Planner Output**: Planner Agent的输出，包含analysis、plan、queries_summary、notes_for_writer等字段
- **ChapterVersion**: 数据库中存储章节版本的表，包含content字段

## Requirements

### Requirement 1: 防止Planner输出被误保存为章节内容

**User Story:** 作为系统管理员，我希望确保只有Writer Agent生成的章节正文被保存到数据库，这样用户才能看到正确的小说内容而不是AI的内部分析。

#### Acceptance Criteria

1. WHEN Planner Agent返回包含full_content字段的错误JSON格式，THEN System SHALL拒绝该响应并记录错误日志
2. WHEN Planner Agent的输出被传递给Writer Agent，THEN System SHALL确保只提取analysis、plan等文本建议字段，不传递任何full_content字段
3. WHEN Writer Agent返回的full_content包含Planner格式的关键词（analysis、plan等），THEN System SHALL在清理Markdown之前进行检测并拒绝保存
4. WHEN 检测到Planner格式内容，THEN System SHALL触发重试机制（第一轮）或抛出异常（第二轮）
5. WHEN 章节内容保存到ChapterVersion表，THEN System SHALL验证content字段不包含Planner格式的结构化内容

### Requirement 2: 增强Planner格式检测准确性

**User Story:** 作为开发人员，我希望系统能准确检测各种形式的Planner格式内容，这样才能有效防止错误内容被保存。

#### Acceptance Criteria

1. WHEN 检测Planner格式，THEN System SHALL在Markdown清理之前进行检测，避免清理后关键词丢失
2. WHEN 检测Planner关键词，THEN System SHALL支持多种格式检测，包括"analysis:"、"**analysis**"、"## analysis"等Markdown包裹的形式
3. WHEN 检测到2个或以上Planner关键词，THEN System SHALL判定为Planner格式内容
4. WHEN full_content是JSON字符串且包含Planner字段，THEN System SHALL解析JSON并检测内部结构
5. WHEN full_content开头1000字符内包含Planner关键词，THEN System SHALL触发检测逻辑

### Requirement 3: 完善错误处理和日志记录

**User Story:** 作为运维人员，我希望系统在检测到Planner格式内容时提供详细的错误信息和日志，这样我才能快速定位和解决问题。

#### Acceptance Criteria

1. WHEN 检测到Planner格式内容，THEN System SHALL记录包含章节号、版本号、检测到的关键词、内容预览的详细日志
2. WHEN Planner Agent返回错误格式，THEN System SHALL记录完整的响应内容（前1000字符）到错误日志
3. WHEN Writer Agent两轮都返回Planner格式，THEN System SHALL抛出包含具体错误原因的ValueError异常
4. WHEN 保存章节内容前，THEN System SHALL记录内容类型、字数、前200字预览到info日志
5. WHEN 检测逻辑触发，THEN System SHALL记录检测结果（通过/失败、suspicious_count、匹配的关键词）到日志

### Requirement 4: 确保数据流完整性

**User Story:** 作为系统架构师，我希望从Planner到Writer到保存的整个数据流都有明确的验证点，这样才能确保数据完整性和正确性。

#### Acceptance Criteria

1. WHEN Planner Agent返回结果，THEN System SHALL验证返回格式只包含analysis、plan、queries_summary、notes_for_writer字段，不包含full_content字段
2. WHEN 构建Writer上下文，THEN System SHALL只提取Planner的文本建议，不传递完整的JSON结构
3. WHEN Writer Agent返回结果，THEN System SHALL验证必须包含full_content字段且为非空字符串
4. WHEN 提取full_content保存，THEN System SHALL在auto_generator_service中再次验证内容格式
5. WHEN 保存到数据库，THEN System SHALL确保ChapterVersion.content字段只包含章节正文，不包含任何结构化的Agent输出

### Requirement 5: 支持调试和问题追踪

**User Story:** 作为开发人员，我希望系统提供足够的调试信息，这样当出现问题时我能快速追踪数据流并定位Bug。

#### Acceptance Criteria

1. WHEN 3Agent模式生成章节，THEN System SHALL在metadata中记录每个Agent的输出摘要
2. WHEN Planner格式检测触发，THEN System SHALL在日志中输出检测到的具体关键词和位置
3. WHEN Writer Agent重试，THEN System SHALL记录重试原因和上一轮的问题
4. WHEN 章节保存成功，THEN System SHALL记录最终保存的内容类型和验证结果
5. WHEN 生成失败，THEN System SHALL在异常消息中包含失败的Agent、轮次、具体原因

## Notes

本需求文档关注的核心问题是：**防止Planner Agent的分析内容被误保存为章节正文**。

关键修复点：
1. 在Markdown清理之前进行Planner格式检测
2. 增强关键词检测，支持Markdown包裹的格式
3. 在多个验证点检查内容格式
4. 完善错误处理和日志记录

预期效果：
- 100%阻止Planner格式内容被保存
- 提供清晰的错误信息帮助调试
- 确保用户只看到正确的小说内容
