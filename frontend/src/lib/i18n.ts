export type Locale = "zh" | "en";

const dict = {
  // ─── Navigation ───────────────────────────────────────
  "nav.workspace": { zh: "工作区", en: "WORKSPACE" },
  "nav.project": { zh: "项目", en: "PROJECT" },
  "nav.system": { zh: "系统", en: "SYSTEM" },
  "nav.projects": { zh: "项目", en: "Projects" },
  "nav.settings": { zh: "设置", en: "Settings" },
  "nav.overview": { zh: "概览", en: "Overview" },
  "nav.blackboard": { zh: "黑板", en: "Blackboard" },
  "nav.messages": { zh: "消息", en: "Messages" },
  "nav.knowledge": { zh: "知识库", en: "Knowledge" },
  "nav.paper": { zh: "论文", en: "Paper" },
  "nav.expandSidebar": { zh: "展开侧边栏", en: "Expand sidebar" },
  "nav.collapseSidebar": { zh: "收起侧边栏", en: "Collapse sidebar" },

  // ─── Phases ───────────────────────────────────────────
  "phase.explore": { zh: "探索", en: "Explore" },
  "phase.hypothesize": { zh: "假设", en: "Hypothesize" },
  "phase.evidence": { zh: "求证", en: "Evidence" },
  "phase.compose": { zh: "撰写", en: "Compose" },
  "phase.synthesize": { zh: "综合", en: "Synthesize" },
  "phase.complete": { zh: "完成", en: "Complete" },

  // ─── Artifact Types ───────────────────────────────────
  "artifact.directions": { zh: "研究方向", en: "Research Direction" },
  "artifact.trend_signals": { zh: "趋势信号", en: "Trend Signal" },
  "artifact.hypotheses": { zh: "假设", en: "Hypothesis" },
  "artifact.evidence_findings": { zh: "证据发现", en: "Evidence" },
  "artifact.evidence_gaps": { zh: "证据缺口", en: "Evidence Gap" },
  "artifact.experiment_guide": { zh: "实验指南", en: "Experiment Guide" },
  "artifact.outline": { zh: "大纲", en: "Outline" },
  "artifact.draft": { zh: "草稿", en: "Draft" },
  "artifact.review": { zh: "评审", en: "Review" },
  "artifact.items": { zh: "项产出", en: "artifacts" },

  // ─── Artifact Sections (Blackboard) ───────────────────
  "artifactSection.directions": { zh: "研究方向", en: "Research Directions" },
  "artifactSection.hypotheses": { zh: "假设", en: "Hypotheses" },
  "artifactSection.evidence_findings": { zh: "证据", en: "Evidence" },
  "artifactSection.outline": { zh: "大纲", en: "Outline" },
  "artifactSection.draft": { zh: "草稿", en: "Draft" },
  "artifactSection.review": { zh: "评审", en: "Review" },
  "artifactSection.trend_signals": { zh: "趋势信号", en: "Trend Signals" },

  // ─── Actions ──────────────────────────────────────────
  "action.create": { zh: "创建", en: "Create" },
  "action.cancel": { zh: "取消", en: "Cancel" },
  "action.delete": { zh: "删除", en: "Delete" },
  "action.save": { zh: "保存", en: "Save" },
  "action.edit": { zh: "编辑", en: "Edit" },
  "action.start": { zh: "开始", en: "Start" },
  "action.pause": { zh: "暂停", en: "Pause" },
  "action.resume": { zh: "恢复", en: "Resume" },
  "action.confirm": { zh: "确认", en: "Confirm" },
  "action.download": { zh: "下载", en: "Download" },
  "action.collapse": { zh: "收起", en: "Collapse" },
  "action.showMore": { zh: "展开更多", en: "Show more" },
  "action.expandAll": { zh: "展开详情", en: "Expand" },
  "action.collapseUp": { zh: "收起 ↑", en: "Collapse ↑" },
  "action.showAllN": { zh: "显示全部 {n} 条", en: "Show all {n}" },
  "action.showFirstN": { zh: "收起 (显示前 {n} 条)", en: "Collapse (first {n})" },
  "action.newProject": { zh: "新建项目", en: "New Project" },
  "action.saveSettings": { zh: "保存设置", en: "Save Settings" },
  "action.backToDashboard": { zh: "返回仪表盘", en: "Back to Dashboard" },
  "action.deleteProject": { zh: "删除项目", en: "Delete project" },
  "action.loadCitationGraph": { zh: "加载引用图谱", en: "Load Citation Graph" },

  // ─── Status ───────────────────────────────────────────
  "status.running": { zh: "运行中", en: "Running" },
  "status.paused": { zh: "已暂停", en: "Paused" },
  "status.completed": { zh: "已完成", en: "Completed" },
  "status.failed": { zh: "失败", en: "Failed" },
  "status.idle": { zh: "空闲", en: "Idle" },
  "status.live": { zh: "实时", en: "Live" },
  "status.offline": { zh: "离线", en: "Offline" },
  "status.saved": { zh: "已保存", en: "Saved" },
  "status.researchRunning": { zh: "研究进行中", en: "Research Running" },
  "status.researchComplete": { zh: "研究完成", en: "Research Complete" },
  "status.researchPaused": { zh: "研究已暂停", en: "Research Paused" },
  "status.synthesizing": { zh: "综合中…", en: "Synthesizing…" },
  "status.loading": { zh: "加载中…", en: "Loading…" },

  // ─── Section Headings ─────────────────────────────────
  "section.researchPipeline": { zh: "研究流水线", en: "Research Pipeline" },
  "section.recentActivity": { zh: "最近活动", en: "Recent Activity" },
  "section.time": { zh: "时间", en: "Time" },
  "section.tokenUsage": { zh: "Token 用量", en: "Token Usage" },
  "section.researchPaper": { zh: "研究论文", en: "Research Paper" },
  "section.messageStream": { zh: "消息流", en: "Message Stream" },
  "section.challenges": { zh: "挑战", en: "Challenges" },
  "section.citationGraph": { zh: "引用图谱", en: "Citation Graph" },
  "section.blackboard": { zh: "黑板", en: "Blackboard" },
  "section.researchProjects": { zh: "研究项目", en: "Research Projects" },
  "section.newResearchProject": { zh: "新建研究项目", en: "New Research Project" },
  "section.settings": { zh: "设置", en: "Settings" },
  "section.apiKeys": { zh: "API 密钥", en: "API Keys" },
  "section.modelPreferences": { zh: "模型偏好", en: "Model Preferences" },
  "section.perAgentModel": { zh: "按 Agent 模型配置", en: "Per-Agent Model Configuration" },
  "section.topicDriftWarning": { zh: "偏题警告", en: "Topic Drift Warning" },
  "section.checkpointReview": { zh: "检查点审核", en: "Checkpoint Review" },
  "section.deleteProject": { zh: "删除项目", en: "Delete Project" },

  // ─── Empty States ─────────────────────────────────────
  "empty.noProjects": { zh: "暂无项目", en: "No projects yet" },
  "empty.noProjectsHint": { zh: "创建您的第一个研究项目以开始", en: "Create your first research project to get started" },
  "empty.projectNotFound": { zh: "项目未找到", en: "Project not found" },
  "empty.noActivity": { zh: "暂无活动", en: "No activity yet" },
  "empty.noArtifacts": { zh: "暂无{type}", en: "No {type} yet" },
  "empty.noArtifactsPhase": { zh: "此阶段暂无独立产出", en: "No artifacts for this phase" },
  "empty.waitingMessages": { zh: "等待消息中…", en: "Waiting for messages…" },
  "empty.noChallenges": { zh: "暂无挑战", en: "No challenges" },
  "empty.noCitations": { zh: "暂无引用数据", en: "No citation data yet" },
  "empty.citationsHint": { zh: "当 Librarian 检索论文后，引用将在此显示", en: "Citations will appear as the Librarian retrieves papers" },
  "empty.researchInProgress": { zh: "研究进行中", en: "Research in progress" },
  "empty.paperWhenComplete": { zh: "研究完成后论文将可用", en: "The paper will be available once the research is complete" },

  // ─── Settings Labels ─────────────────────────────────
  "settings.deepseekApiKey": { zh: "DeepSeek API 密钥", en: "DeepSeek API Key" },
  "settings.openrouterApiKey": { zh: "OpenRouter API 密钥", en: "OpenRouter API Key" },
  "settings.anthropicApiKey": { zh: "Anthropic API 密钥", en: "Anthropic API Key" },
  "settings.anthropicBaseUrl": { zh: "Anthropic 接口地址", en: "Anthropic Base URL" },
  "settings.s2ApiKey": { zh: "Semantic Scholar API 密钥", en: "Semantic Scholar API Key" },
  "settings.enableWebRetrieval": { zh: "启用网络检索", en: "Enable Web Retrieval" },
  "settings.enableWebRetrievalDesc": { zh: "允许 Librarian 从 arXiv/Semantic Scholar 检索论文", en: "Allow Librarian to retrieve papers from arXiv/Semantic Scholar" },

  // ─── Agent Role Labels ──────────────────────────────
  "agent.director": { zh: "总监", en: "Director" },
  "agent.scientist": { zh: "科学家", en: "Scientist" },
  "agent.librarian": { zh: "文献员", en: "Librarian" },
  "agent.writer": { zh: "撰稿人", en: "Writer" },
  "agent.critic": { zh: "评审员", en: "Critic" },
  "agent.synthesizer": { zh: "综合员", en: "Synthesizer" },

  // ─── Model Presets ──────────────────────────────────
  "preset.label": { zh: "快捷预设", en: "Quick Presets" },
  "preset.free": { zh: "免费", en: "Free" },
  "preset.freeDesc": { zh: "零成本体验", en: "Zero cost" },
  "preset.economy": { zh: "经济", en: "Economy" },
  "preset.economyDesc": { zh: "DeepSeek ~0.3元/次", en: "DeepSeek ~$0.04/run" },
  "preset.balanced": { zh: "均衡", en: "Balanced" },
  "preset.balancedDesc": { zh: "多厂商 ~1元/次", en: "Multi-vendor ~$0.15/run" },
  "preset.quality": { zh: "质量", en: "Quality" },
  "preset.qualityDesc": { zh: "中文最强 ~5元/次", en: "Best Chinese ~$0.60/run" },
  "preset.premium": { zh: "旗舰", en: "Premium" },
  "preset.premiumDesc": { zh: "全球最强 ~45元/次", en: "Global best ~$6/run" },
  "preset.custom": { zh: "自定义配置", en: "Custom configuration" },
  "preset.noModels": { zh: "请先在上方配置至少一个 API 密钥", en: "Please configure at least one API key above" },
  "preset.costUnit": { zh: "元/次", en: "RMB/run" },
  "preset.showDetail": { zh: "查看详情", en: "Details" },
  "preset.hideDetail": { zh: "收起详情", en: "Hide" },
  "preset.detailCost": { zh: "单次成本:", en: "Cost/run:" },
  "preset.detailAgents": { zh: "模型配置:", en: "Models:" },
  "preset.detailTraits": { zh: "特点:", en: "Traits:" },
  "preset.selectForProject": { zh: "模型预设", en: "Model Preset" },
  "preset.perLane": { zh: "通道 {lane} 预设", en: "Lane {lane} Preset" },
  "preset.saveCustom": { zh: "保存为自定义预设", en: "Save as Custom Preset" },
  "preset.customName": { zh: "预设名称", en: "Preset Name" },
  "preset.customNamePlaceholder": { zh: "例如：我的研究预设", en: "e.g. My Research Preset" },
  "preset.deleteCustom": { zh: "删除自定义预设", en: "Delete custom preset" },
  "preset.customPresets": { zh: "自定义预设", en: "Custom Presets" },

  // ─── Model Tags ─────────────────────────────────────
  "tag.free": { zh: "免费", en: "Free" },
  "tag.economy": { zh: "经济", en: "Economy" },
  "tag.value": { zh: "性价比", en: "Value" },
  "tag.flagship": { zh: "旗舰", en: "Flagship" },
  "tag.premium": { zh: "高端", en: "Premium" },
  "tag.priceWarning": { zh: "此模型费用较高（约 ${price}/百万 token），确定使用吗？", en: "This model is expensive (~${price}/M tokens). Continue?" },
  "tag.priceWarningTitle": { zh: "高价模型提醒", en: "Expensive Model Warning" },

  // ─── Form Labels & Placeholders ───────────────────────
  "form.searchProjects": { zh: "搜索项目…", en: "Search projects…" },
  "form.projectName": { zh: "项目名称", en: "Project Name" },
  "form.projectNamePlaceholder": { zh: "例如：蛋白质折叠研究", en: "e.g. Protein Folding Study" },
  "form.researchTopic": { zh: "研究课题", en: "Research Topic" },
  "form.researchTopicPlaceholder": { zh: "描述您想要研究的内容…", en: "Describe what you want to research…" },
  "form.parallelLanes": { zh: "并行通道", en: "Parallel Lanes" },
  "form.embeddingModel": { zh: "向量模型", en: "Embedding" },
  "form.useDefault": { zh: "使用默认", en: "Use default" },

  // ─── Confirm/Modal ────────────────────────────────────
  "modal.newProject": { zh: "新建研究项目", en: "New Research Project" },
  "modal.deleteProject": { zh: "删除项目", en: "Delete Project" },
  "modal.deleteConfirm": { zh: "确定要删除 {name} ？", en: "Are you sure you want to delete {name}?" },
  "modal.deleteWarning": { zh: "此操作无法撤销。所有研究产出和数据将被永久删除。", en: "This action cannot be undone. All research artifacts and data will be permanently deleted." },
  "modal.checkpointReview": { zh: "检查点审核", en: "Checkpoint Review" },

  // ─── Form extras ───────────────────────────────────────
  "form.sequential": { zh: "1（顺序执行）", en: "1 (sequential)" },
  "form.maxParallel": { zh: "5（最大并行）", en: "5 (max parallel)" },

  // ─── Time / Misc ──────────────────────────────────────
  "time.created": { zh: "创建于", en: "Created" },
  "time.runningFor": { zh: "已运行", en: "Running for" },
  "time.completedAt": { zh: "完成于", en: "Completed" },
  "time.justNow": { zh: "刚刚", en: "just now" },
  "time.mAgo": { zh: "分钟前", en: "m ago" },
  "time.hAgo": { zh: "小时前", en: "h ago" },
  "time.dAgo": { zh: "天前", en: "d ago" },
  "misc.tokens": { zh: "Tokens", en: "Tokens" },
  "misc.calls": { zh: "调用次数", en: "Calls" },
  "misc.iter": { zh: "迭代", en: "Iter" },
  "misc.parallelLanes": { zh: "并行通道", en: "Parallel Lanes" },
  "misc.lane": { zh: "通道", en: "Lane" },
  "lane.tab": { zh: "通道 {n}", en: "Lane {n}" },
  "lane.synthesis": { zh: "综合", en: "Synthesis" },
  "misc.allRoles": { zh: "全部角色", en: "All roles" },
  "misc.all": { zh: "全部", en: "All" },
  "misc.open": { zh: "未解决", en: "Open" },
  "misc.resolved": { zh: "已解决", en: "Resolved" },
  "misc.papers": { zh: "篇论文", en: "papers" },
  "misc.citations": { zh: "条引用", en: "citations" },
  "misc.strengths": { zh: "优点", en: "Strengths" },
  "misc.weaknesses": { zh: "缺点", en: "Weaknesses" },
  "misc.noContent": { zh: "（无内容）", en: "(no content)" },
  "misc.methodology": { zh: "方法", en: "Methodology" },
  "misc.rationale": { zh: "依据", en: "Rationale" },
  "misc.expected": { zh: "预期", en: "Expected outcome" },
  "misc.confidence": { zh: "置信度", en: "Confidence" },
  "misc.manageDesc": { zh: "管理和监控您的 AI 辅助研究流程", en: "Manage and monitor your AI-assisted research workflows" },
  "misc.settingsDesc": { zh: "配置 API 密钥、模型偏好和研究默认值", en: "Configure API keys, model preferences, and research defaults" },
  "misc.switchToLight": { zh: "切换到浅色模式", en: "Switch to light mode" },
  "misc.switchToDark": { zh: "切换到深色模式", en: "Switch to dark mode" },
} as const;

export type I18nKey = keyof typeof dict;

export function t(key: I18nKey, locale: Locale, params?: Record<string, string | number>): string {
  const entry = dict[key];
  let text: string = entry?.[locale] ?? key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(`{${k}}`, String(v));
    }
  }
  return text;
}

export function getLocaleFromStorage(): Locale {
  if (typeof window === "undefined") return "zh";
  return (localStorage.getItem("aide-locale") as Locale) || "zh";
}

export function setLocaleToStorage(locale: Locale) {
  if (typeof window !== "undefined") {
    localStorage.setItem("aide-locale", locale);
  }
}
