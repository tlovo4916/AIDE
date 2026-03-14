/**
 * Shared preset definitions used by both Settings page and Project creation modal.
 */

export const AGENT_ROLE_KEYS = [
  "director",
  "scientist",
  "librarian",
  "writer",
  "critic",
  "synthesizer",
] as const;

export type AgentRoleKey = (typeof AGENT_ROLE_KEYS)[number];

/** Roles that benefit from reasoning-capable models */
export const REASONING_ROLES = new Set<string>(["director", "scientist", "critic"]);

export type PresetKey = "free" | "economy" | "balanced" | "quality" | "premium" | "custom";
export type BuiltinPresetKey = Exclude<PresetKey, "custom">;
export type PresetConfig = Record<string, string>;

export const PRESET_OVERRIDES: Record<BuiltinPresetKey, PresetConfig> = {
  free: {
    director: "step-3.5-flash",
    scientist: "step-3.5-flash",
    critic: "step-3.5-flash",
    librarian: "step-3.5-flash",
    writer: "step-3.5-flash",
    synthesizer: "step-3.5-flash",
    embedding: "nvidia/llama-nemotron-embed-vl-1b-v2:free",
  },
  economy: {
    director: "deepseek-reasoner",
    scientist: "deepseek-reasoner",
    critic: "deepseek-reasoner",
    librarian: "deepseek-chat",
    writer: "deepseek-chat",
    synthesizer: "deepseek-reasoner",
    embedding: "qwen/qwen3-embedding-4b",
  },
  balanced: {
    director: "deepseek-reasoner",
    scientist: "deepseek-reasoner",
    critic: "qwen3.5-plus",
    librarian: "step-3.5-flash",
    writer: "qwen3.5-plus",
    synthesizer: "minimax-m2.5",
    embedding: "qwen/qwen3-embedding-8b",
  },
  quality: {
    director: "glm-5",
    scientist: "deepseek-v3.2-speciale",
    critic: "glm-5",
    librarian: "qwen3.5-plus",
    writer: "qwen3.5-plus",
    synthesizer: "minimax-m2.5",
    embedding: "openai/text-embedding-3-small",
  },
  premium: {
    director: "claude-opus-4-6",
    scientist: "gemini-3.1-pro",
    critic: "claude-opus-4-6",
    librarian: "qwen3.5-plus",
    writer: "claude-sonnet-4-6",
    synthesizer: "gemini-3.1-pro",
    embedding: "openai/text-embedding-3-large",
  },
};

export type PresetDetail = {
  cost: { zh: string; en: string };
  agents: { zh: string; en: string };
  traits: { zh: string; en: string };
  scene: { zh: string; en: string };
};

export const PRESET_DETAILS: Record<BuiltinPresetKey, PresetDetail> = {
  free: {
    cost: { zh: "0 元/次", en: "$0/run" },
    agents: {
      zh: "全部 6 个 Agent 使用 Step 3.5 Flash（阶跃星辰，256K 上下文，147t/s 最快速度）· Embedding: Nemotron V2（免费）",
      en: "All 6 agents use Step 3.5 Flash (256K ctx, 147t/s fastest) · Embedding: Nemotron V2 (free)",
    },
    traits: {
      zh: "速率限制 20 次/分钟、200 次/天 · 中文可用（Step 是中国公司） · AIME 97.3% 数学推理 · 推理深度中等",
      en: "Rate limited 20 req/min, 200 req/day · Chinese OK · AIME 97.3% · Medium reasoning",
    },
    scene: {
      zh: "适合初次体验、教学演示、预算为零的探索性研究",
      en: "Good for first-time use, demos, zero-budget exploration",
    },
  },
  economy: {
    cost: { zh: "~0.3 元/次 ($0.04)", en: "~$0.04/run (¥0.3)" },
    agents: {
      zh: "总监/科学家/评审/综合 → DeepSeek Reasoner · 文献/撰稿 → DeepSeek Chat · Embedding: Qwen3 4B（$0.02/M）",
      en: "Director/Scientist/Critic/Synth → DeepSeek Reasoner · Librarian/Writer → DeepSeek Chat · Embedding: Qwen3 4B ($0.02/M)",
    },
    traits: {
      zh: "V3.2 底座 128K 上下文 · 缓存命中省 90%（0.2 元/M）· 中文质量优秀 · 推理深度强",
      en: "V3.2 base 128K ctx · Cache hit saves 90% · Excellent Chinese · Strong reasoning",
    },
    scene: {
      zh: "适合日常研究、高频使用、个人开发者、批量跑实验",
      en: "Good for daily research, frequent use, batch experiments",
    },
  },
  balanced: {
    cost: { zh: "~0.7-1.5 元/次 ($0.10-0.20)", en: "~$0.10-0.20/run (¥0.7-1.5)" },
    agents: {
      zh: "总监/科学家 → DeepSeek Reasoner · 评审/撰稿 → Qwen 3.5 Plus · 文献 → Step Flash · 综合 → MiniMax M2.5 · Embedding: Qwen3 8B（$0.01/M）",
      en: "Director/Scientist → DeepSeek Reasoner · Critic/Writer → Qwen 3.5 Plus · Librarian → Step Flash · Synth → MiniMax M2.5 · Embedding: Qwen3 8B ($0.01/M)",
    },
    traits: {
      zh: "4 厂商混搭，单一故障不影响整体 · 最长 1M 上下文 · 中文质量优秀 · 推理深度强",
      en: "4-vendor mix, fault-tolerant · Up to 1M ctx · Excellent Chinese · Strong reasoning",
    },
    scene: {
      zh: "⭐ 通用推荐方案 — 适合正式研究项目、追求质量与成本平衡",
      en: "⭐ Recommended — formal research, best quality/cost balance",
    },
  },
  quality: {
    cost: { zh: "~3-6 元/次 ($0.40-0.80)", en: "~$0.40-0.80/run (¥3-6)" },
    agents: {
      zh: "总监/评审 → GLM-5 · 科学家 → DeepSeek V3.2 Speciale · 文献/撰稿 → Qwen 3.5 Plus · 综合 → MiniMax M2.5 · Embedding: OpenAI Small（$0.02/M）",
      en: "Director/Critic → GLM-5 · Scientist → V3.2 Speciale · Librarian/Writer → Qwen 3.5 Plus · Synth → MiniMax M2.5 · Embedding: OpenAI Small ($0.02/M)",
    },
    traits: {
      zh: "5 厂商混搭 · 中文质量顶级（GLM-5 Arena 冠军 + Qwen 写作）· 推理深度顶级（Speciale 超 GPT-5）· 无速率限制",
      en: "5-vendor mix · Top-tier Chinese (GLM-5 Arena champ + Qwen writing) · Top reasoning · No rate limit",
    },
    scene: {
      zh: "适合严肃学术研究、论文产出、企业报告",
      en: "Good for serious academic research, papers, enterprise reports",
    },
  },
  premium: {
    cost: { zh: "~30-60 元/次 ($4-8)", en: "~$4-8/run (¥30-60)" },
    agents: {
      zh: "总监/评审 → Claude Opus 4.6 · 科学家/综合 → Gemini 3.1 Pro · 撰稿 → Claude Sonnet 4.6 · 文献 → Qwen 3.5 Plus · Embedding: OpenAI Large（$0.13/M）",
      en: "Director/Critic → Claude Opus · Scientist/Synth → Gemini 3.1 Pro · Writer → Claude Sonnet · Librarian → Qwen 3.5 Plus · Embedding: OpenAI Large ($0.13/M)",
    },
    traits: {
      zh: "全球最强推理 + 全球最强写作 · 1M 上下文 · 中文质量优秀 · 速度较慢",
      en: "World's best reasoning + writing · 1M ctx · Excellent Chinese · Slower speed",
    },
    scene: {
      zh: "适合不计成本追求极致、顶会论文、关键研究",
      en: "For no-budget-limit research, top-conference papers, critical demos",
    },
  },
};

/** Detect which built-in preset matches the current agent_model_overrides + embedding */
export function detectPreset(
  overrides: Record<string, string>,
  embeddingModel?: string,
): PresetKey {
  for (const [key, preset] of Object.entries(PRESET_OVERRIDES)) {
    const agentsMatch = AGENT_ROLE_KEYS.every((role) => overrides[role] === preset[role]);
    const embeddingMatch = !embeddingModel || embeddingModel === preset.embedding;
    if (agentsMatch && embeddingMatch) return key as PresetKey;
  }
  return "custom";
}

/** A user-defined custom preset with model overrides and optional description */
export type CustomPresetData = {
  overrides: Record<string, string>;
  description?: string;
};

/** Resolve a preset key (builtin or custom) to its agent_model_overrides config */
export function resolvePresetConfig(
  key: string,
  customPresets?: Record<string, CustomPresetData>,
): PresetConfig | null {
  if (key in PRESET_OVERRIDES) {
    return PRESET_OVERRIDES[key as BuiltinPresetKey];
  }
  if (customPresets && key in customPresets) {
    return customPresets[key].overrides;
  }
  return null;
}
