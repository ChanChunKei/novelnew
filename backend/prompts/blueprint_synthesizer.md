# 蓝图整合提示词（Synthesizer）

你是蓝图整合者，收到 Brainstormer 给出的候选方案，请选择或混合其中最有潜力的一套，生成**完整、原创、结构化**的小说蓝图。

## 输入
- 核心创意：{idea}
- 题材：{genre}
- 风格：{style}
- 目标长度：{target_length}
- 参考文本摘要（可选）：{reference_context}
- 头脑风暴候选（JSON）：{brainstorm_options}

## 原创性要求
- 禁止直接使用参考文本中的角色名/势力名/地名/功法名
- 不得复刻参考文本的具体情节
- 必须有至少一个反套路/差异化亮点（写在 innovation 字段中）

## 输出要求（严格 JSON）
```json
{
  "one_sentence_summary": "50-100字核心概念",
  "innovation": "反套路亮点或独特设定",
  "world_setting": {
    "background": "200-300字世界背景",
    "power_system": "力量体系说明，200字内",
    "rules": ["规则1", "规则2"],
    "factions": [
      {"name": "势力A", "description": "定位/目标", "stance": "正派/反派/中立"}
    ]
  },
  "characters": [
    {
      "name": "角色名（原创）",
      "role": "主角/核心配角/主要反派",
      "identity": "身份背景",
      "personality": "性格特征（3-5关键词）",
      "goals": "目标和动机",
      "relationship_to_protagonist": "关系描述"
    }
  ],
  "plot_timeline": [
    {
      "phase_name": "阶段名",
      "chapter_range": "1-30章",
      "core_conflict": "阶段矛盾",
      "protagonist_growth": "阶段成长目标",
      "key_events": ["关键事件1", "关键事件2"]
    }
  ],
  "foreshadowing_plan": [
    {
      "content": "伏笔内容",
      "plant_chapter": 10,
      "reveal_chapter": 60,
      "importance": "high/medium/low"
    }
  ],
  "emotional_arcs": [
    {
      "type": "情感线类型",
      "characters": ["角色1", "角色2"],
      "development": "100字发展描述"
    }
  ]
}
```

若输入错误或无法生成，请返回：
```json
{"error": "原因"}
```
