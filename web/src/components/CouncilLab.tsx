import { useEffect, useMemo, useRef, useState } from "react";

type CouncilOpinion = {
  agent_id: string;
  display_name: string;
  agent_type: string;
  weight: number;
  score: number;
  metrics: string;
  reason: string;
};

type AgentPreferences = {
  theme_weight: number;
  efficiency_weight: number;
  budget_weight: number;
  price_cap_usd: number | null;
};

type AgentContextBudget = {
  max_deck_cards: number;
  max_candidates: number;
  max_commander_text_chars: number;
  max_candidate_oracle_chars: number;
};

type AgentContextFilters = {
  include_commander_text: boolean;
  include_deck_cards: boolean;
  include_candidate_oracle: boolean;
  include_candidate_type_line: boolean;
  include_candidate_cmc: boolean;
  include_candidate_price: boolean;
};

type AgentContext = {
  budget: AgentContextBudget;
  filters: AgentContextFilters;
};

export type CouncilAgentConfig = {
  id: string;
  display_name: string | null;
  type: string;
  weight: number;
  model: string | null;
  temperature: number;
  system_prompt?: string | null;
  user_prompt_template?: string | null;
  preferences: AgentPreferences;
  context?: AgentContext;
};

type CouncilAnalysisResponse = {
  session_id: number;
  commander_name: string;
  card_name: string;
  opinions: CouncilOpinion[];
};

type CouncilConsultResponse = {
  session_id: number;
  commander_name: string;
  card_name: string;
  opinions: CouncilOpinion[];
  verdict: string;
};

type PanelState = {
  panelId: string;
  agent: CouncilAgentConfig;
  selectedKey: string;
  loading: boolean;
  error: string | null;
  opinions: CouncilOpinion[];
  includeInCouncil: boolean;
  lastSessionId?: number;
  lastCardId?: number;
};

type CouncilLabProps = {
  sessionId: number;
  cardId: number;
  apiBase: string;
};

const SAVED_AGENTS_KEY = "councilAgentLibrary";

const createEmptyAgent = (): CouncilAgentConfig => ({
  id: "custom-agent",
  display_name: "Custom Agent",
  type: "heuristic",
  weight: 1.0,
  model: null,
  temperature: 0.3,
  system_prompt: null,
  user_prompt_template: null,
  preferences: {
    theme_weight: 0.5,
    efficiency_weight: 0.25,
    budget_weight: 0.25,
    price_cap_usd: null,
  },
  context: {
    budget: {
      max_deck_cards: 40,
      max_candidates: 60,
      max_commander_text_chars: 1200,
      max_candidate_oracle_chars: 600,
    },
    filters: {
      include_commander_text: true,
      include_deck_cards: true,
      include_candidate_oracle: true,
      include_candidate_type_line: true,
      include_candidate_cmc: true,
      include_candidate_price: true,
    },
  },
});

const DEFAULT_SYSTEM_PROMPT =
  "You are a council agent for Commander synergy training. " +
  "Explain why the card is synergistic or not for the commander and if it would be " +
  "a no or if it has potential. " +
  "Keep it short (1-2 sentences) and plain language.";

const DEFAULT_USER_PROMPT =
  "Explain in 1-2 sentences whether this card has synergy with the commander. " +
  "Use the data provided and return only the reason text.";

const normalizeAgent = (agent: CouncilAgentConfig): CouncilAgentConfig => ({
  ...agent,
  system_prompt: agent.system_prompt ?? DEFAULT_SYSTEM_PROMPT,
  user_prompt_template: agent.user_prompt_template ?? DEFAULT_USER_PROMPT,
});

const cloneAgent = (agent: CouncilAgentConfig): CouncilAgentConfig =>
  normalizeAgent(JSON.parse(JSON.stringify(agent)) as CouncilAgentConfig);

const buildApiUrl = (apiBase: string, path: string) => {
  if (!apiBase) return path;
  if (apiBase.endsWith("/") && path.startsWith("/")) {
    return `${apiBase.slice(0, -1)}${path}`;
  }
  if (!apiBase.endsWith("/") && !path.startsWith("/")) {
    return `${apiBase}/${path}`;
  }
  return `${apiBase}${path}`;
};

const formatPercent = (value: number, total: number) => {
  if (!Number.isFinite(total) || total <= 0) return "—";
  const percent = (value / total) * 100;
  return `${percent.toFixed(1)}%`;
};

export function CouncilLab({ sessionId, cardId, apiBase }: CouncilLabProps) {
  const [defaultAgents, setDefaultAgents] = useState<CouncilAgentConfig[]>([]);
  const [savedAgents, setSavedAgents] = useState<CouncilAgentConfig[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      const raw = window.localStorage.getItem(SAVED_AGENTS_KEY);
      const parsed = raw ? (JSON.parse(raw) as CouncilAgentConfig[]) : [];
      if (!Array.isArray(parsed)) return [];
      return parsed.map((agent) => {
        const legacy = agent as CouncilAgentConfig & { agent_id?: string };
        const id = legacy.id || legacy.agent_id || "custom-agent";
        return normalizeAgent({ ...legacy, id });
      });
    } catch {
      return [];
    }
  });
  const [panels, setPanels] = useState<PanelState[]>([]);
  const [agentError, setAgentError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [importTargetPanel, setImportTargetPanel] = useState<string | null>(null);
  const [sharedApiKey, setSharedApiKey] = useState("");
  const [consultLoading, setConsultLoading] = useState(false);
  const [consultError, setConsultError] = useState<string | null>(null);
  const [consultResult, setConsultResult] = useState<CouncilConsultResponse | null>(null);
  const [synthesizerAgent, setSynthesizerAgent] = useState<CouncilAgentConfig>(() =>
    normalizeAgent({
      ...createEmptyAgent(),
      id: "synthesizer",
      display_name: "Council Synthesizer",
      type: "llm",
      weight: 1.0,
      model: "gpt-4o-mini",
      preferences: {
        theme_weight: 0.5,
        efficiency_weight: 0.25,
        budget_weight: 0.25,
        price_cap_usd: null,
      },
      system_prompt:
        "You are a council synthesizer. You are a messenger who reports the council's outcome. "
        + "Do not form a new opinion. Decide No or Potential based only on the provided opinions and weights.",
      user_prompt_template:
        "Return a short verdict of No or Potential with a 1-2 sentence rationale. "
        + "Summarize the council's reasoning without adding new arguments.",
    }),
  );
  const totalAgentWeight = useMemo(
    () =>
      panels
        .filter((panel) => panel.includeInCouncil)
        .reduce(
          (sum, panel) =>
            sum + (Number.isFinite(panel.agent.weight) ? panel.agent.weight : 0),
          0,
        ),
    [panels],
  );

  const libraryOptions = useMemo(() => {
    const defaults = defaultAgents.map((agent) => ({
      key: `default:${agent.id}`,
      label: agent.display_name || agent.id,
      agent,
    }));
    const saved = savedAgents.map((agent) => ({
      key: `saved:${agent.id}`,
      label: agent.display_name || agent.id,
      agent,
    }));
    const combined = [...defaults, ...saved];
    if (combined.length === 0) {
      combined.push({
        key: "custom",
        label: "Custom agent",
        agent: normalizeAgent(createEmptyAgent()),
      });
    }
    return combined;
  }, [defaultAgents, savedAgents]);

  const syncSavedAgents = (next: CouncilAgentConfig[]) => {
    setSavedAgents(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SAVED_AGENTS_KEY, JSON.stringify(next));
    }
  };

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const response = await fetch(buildApiUrl(apiBase, "/api/council/agents"));
        if (!response.ok) {
          throw new Error(`Failed to load agents (${response.status}).`);
        }
        const data = (await response.json()) as CouncilAgentConfig[];
        setDefaultAgents(data.map((agent) => normalizeAgent(agent)));
        setAgentError(null);
      } catch (err) {
        setAgentError(err instanceof Error ? err.message : "Failed to load agents.");
      }
    };
    fetchAgents();
  }, [apiBase]);

  useEffect(() => {
    if (panels.length > 0 || defaultAgents.length === 0) return;
    const primary = defaultAgents[0] ?? normalizeAgent(createEmptyAgent());
    const secondary = defaultAgents[1] ?? primary;
    setPanels([
      {
        panelId: `panel-${crypto.randomUUID()}`,
        agent: cloneAgent(primary),
        selectedKey: `default:${primary.id}`,
        loading: false,
        error: null,
        opinions: [],
        includeInCouncil: true,
        lastSessionId: undefined,
        lastCardId: undefined,
      },
      {
        panelId: `panel-${crypto.randomUUID()}`,
        agent: cloneAgent(secondary),
        selectedKey: `default:${secondary.id}`,
        loading: false,
        error: null,
        opinions: [],
        includeInCouncil: true,
        lastSessionId: undefined,
        lastCardId: undefined,
      },
    ]);
  }, [defaultAgents, panels.length]);

  const updatePanel = (panelId: string, updater: (panel: PanelState) => PanelState) => {
    setPanels((current) => current.map((panel) => (panel.panelId === panelId ? updater(panel) : panel)));
  };

  const handleSelectAgent = (panelId: string, selectedKey: string) => {
    const selected = libraryOptions.find((option) => option.key === selectedKey);
    updatePanel(panelId, (panel) => ({
      ...panel,
      selectedKey,
      agent: selected ? cloneAgent(selected.agent) : panel.agent,
      opinions: [],
      error: null,
    }));
  };

  const handleSaveAgent = (panelId: string) => {
    const panel = panels.find((entry) => entry.panelId === panelId);
    if (!panel) return;
    const next = [
      ...savedAgents.filter((agent) => agent.id !== panel.agent.id),
      normalizeAgent(panel.agent),
    ];
    syncSavedAgents(next);
  };

  const handleDeleteAgent = (panelId: string) => {
    const panel = panels.find((entry) => entry.panelId === panelId);
    if (!panel) return;
    const next = savedAgents.filter((agent) => agent.id !== panel.agent.id);
    syncSavedAgents(next);
    if (panel.selectedKey.startsWith("saved:")) {
      const fallback = defaultAgents[0] ?? createEmptyAgent();
      updatePanel(panelId, (current) => ({
        ...current,
        agent: cloneAgent(fallback),
        selectedKey: defaultAgents.length ? `default:${fallback.id}` : current.selectedKey,
      }));
    }
  };

  const handleImportClick = (panelId: string) => {
    setImportTargetPanel(panelId);
    fileInputRef.current?.click();
  };

  const handleImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !importTargetPanel) return;
    const text = await file.text();
    try {
      const response = await fetch(buildApiUrl(apiBase, "/api/council/agent/import"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ yaml: text }),
      });
      if (!response.ok) {
        let detail = "Import failed.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // Ignore parse errors.
        }
        throw new Error(detail);
      }
      const agent = normalizeAgent((await response.json()) as CouncilAgentConfig);
      syncSavedAgents([...savedAgents.filter((entry) => entry.id !== agent.id), agent]);
      updatePanel(importTargetPanel, (panel) => ({
        ...panel,
        agent: cloneAgent(agent),
        selectedKey: `saved:${agent.id}`,
        opinions: [],
        error: null,
      }));
    } catch (err) {
      updatePanel(importTargetPanel, (panel) => ({
        ...panel,
        error: err instanceof Error ? err.message : "Failed to import agent.",
      }));
    } finally {
      event.target.value = "";
      setImportTargetPanel(null);
    }
  };

  const handleExport = async (panelId: string) => {
    const panel = panels.find((entry) => entry.panelId === panelId);
    if (!panel) return;
    try {
      const response = await fetch(buildApiUrl(apiBase, "/api/council/agent/export"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(panel.agent),
      });
      if (!response.ok) {
        throw new Error("Export failed.");
      }
      const payload = (await response.json()) as { yaml: string };
      const blob = new Blob([payload.yaml], { type: "text/yaml" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${panel.agent.id || "council-agent"}.yaml`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      updatePanel(panelId, (current) => ({
        ...current,
        error: err instanceof Error ? err.message : "Export failed.",
      }));
    }
  };

  const handleAnalyze = async (panelId: string) => {
    const panel = panels.find((entry) => entry.panelId === panelId);
    if (!panel) return;
    updatePanel(panelId, (current) => ({
      ...current,
      loading: true,
      error: null,
      opinions: [],
    }));
    try {
      const response = await fetch(buildApiUrl(apiBase, "/api/training/council/analyze"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          card_id: cardId,
          api_key: sharedApiKey.trim() || undefined,
          council_overrides: {
            agents: [
              {
                id: panel.agent.id,
                display_name: panel.agent.display_name,
                type: panel.agent.type,
                weight: panel.agent.weight,
                model: panel.agent.model,
                temperature: panel.agent.temperature,
                system_prompt: panel.agent.system_prompt ?? DEFAULT_SYSTEM_PROMPT,
                user_prompt_template: panel.agent.user_prompt_template ?? DEFAULT_USER_PROMPT,
                preferences: panel.agent.preferences,
                context: panel.agent.context,
              },
            ],
          },
        }),
      });
      if (!response.ok) {
        let detail = "Council analysis failed.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // Ignore parse errors.
        }
        throw new Error(detail);
      }
      const data = (await response.json()) as CouncilAnalysisResponse;
      updatePanel(panelId, (current) => ({
        ...current,
        opinions: data.opinions,
        loading: false,
        lastSessionId: sessionId,
        lastCardId: cardId,
      }));
    } catch (err) {
      updatePanel(panelId, (current) => ({
        ...current,
        error: err instanceof Error ? err.message : "Council analysis failed.",
        loading: false,
      }));
    }
  };

  const handleConsult = async () => {
    const activePanels = panels.filter((panel) => panel.includeInCouncil);
    if (!activePanels.length) {
      setConsultError("Select at least one agent to consult.");
      return;
    }
    setConsultLoading(true);
    setConsultError(null);
    setConsultResult(null);
    try {
      const cachedOpinions: CouncilOpinion[] = [];
      const agentsToRun = activePanels.filter((panel) => {
        const matchesCard =
          panel.lastSessionId === sessionId && panel.lastCardId === cardId;
        const hasOpinion =
          panel.opinions.length > 0 &&
          panel.opinions.some((opinion) => opinion.agent_id === panel.agent.id);
        if (matchesCard && hasOpinion) {
          cachedOpinions.push(...panel.opinions);
          return false;
        }
        return true;
      });
      const response = await fetch(buildApiUrl(apiBase, "/api/training/council/consult"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          card_id: cardId,
          api_key: sharedApiKey.trim() || undefined,
          cached_opinions: cachedOpinions,
          agents: agentsToRun.map((panel) => ({
            id: panel.agent.id,
            display_name: panel.agent.display_name,
            type: panel.agent.type,
            weight: panel.agent.weight,
            model: panel.agent.model,
            temperature: panel.agent.temperature,
            system_prompt: panel.agent.system_prompt,
            user_prompt_template: panel.agent.user_prompt_template,
            preferences: panel.agent.preferences,
            context: panel.agent.context,
          })),
          synthesizer: {
            id: synthesizerAgent.id,
            display_name: synthesizerAgent.display_name,
            type: synthesizerAgent.type,
            weight: synthesizerAgent.weight,
            model: synthesizerAgent.model,
            temperature: synthesizerAgent.temperature,
            system_prompt: synthesizerAgent.system_prompt,
            user_prompt_template: synthesizerAgent.user_prompt_template,
            preferences: synthesizerAgent.preferences,
            context: synthesizerAgent.context,
          },
        }),
      });
      if (!response.ok) {
        let detail = "Council consult failed.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // Ignore parse errors.
        }
        throw new Error(detail);
      }
      const data = (await response.json()) as CouncilConsultResponse;
      setConsultResult(data);
    } catch (err) {
      setConsultError(err instanceof Error ? err.message : "Council consult failed.");
    } finally {
      setConsultLoading(false);
    }
  };

  const handleAddPanel = () => {
    const fallback = defaultAgents[0] ?? normalizeAgent(createEmptyAgent());
    setPanels((current) => [
      ...current,
      {
        panelId: `panel-${crypto.randomUUID()}`,
        agent: cloneAgent(fallback),
        selectedKey: defaultAgents.length ? `default:${fallback.id}` : "custom",
        loading: false,
        error: null,
        opinions: [],
        includeInCouncil: true,
        lastSessionId: undefined,
        lastCardId: undefined,
      },
    ]);
  };

  const handleRemovePanel = (panelId: string) => {
    setPanels((current) => current.filter((panel) => panel.panelId !== panelId));
  };

  if (!sessionId || !cardId) {
    return null;
  }

  return (
    <div className="council-lab">
      <div className="council-lab-header">
        <div>
          <h3>Council Lab</h3>
          <p>Load an agent, tweak weights, and compare outputs side by side.</p>
        </div>
      </div>
      <label className="field">
        <span>
          OpenAI API key (optional)
          <span
            className="help"
            data-tooltip="Shared API key for all panels and the council consult."
          >
            ?
          </span>
        </span>
        <input
          type="password"
          value={sharedApiKey}
          onChange={(event) => setSharedApiKey(event.target.value)}
          placeholder="sk-..."
        />
      </label>
      {agentError && <div className="notice error">{agentError}</div>}
      <div className="council-consult">
        <div className="council-consult-header">
          <div>
            <h4>Consult the Council</h4>
            <p>Run all included agents and synthesize a verdict.</p>
          </div>
          <button className="primary" type="button" onClick={handleConsult} disabled={consultLoading}>
            {consultLoading ? (
              <>
                <span className="spinner" aria-hidden="true" />
                Consulting...
              </>
            ) : (
              "Consult the Council"
            )}
          </button>
        </div>
        {consultError && <div className="notice error">{consultError}</div>}
        {consultResult && (
          <div className="council-consult-result">
            <strong>Verdict</strong>
            <p>{consultResult.verdict}</p>
          </div>
        )}
        <div className="council-consult-synth">
          <div className="council-panel-header">
            <div>
              <h4>Synthesizer Agent</h4>
              <p>Messenger only. Summarizes council opinions into a verdict.</p>
            </div>
          </div>
          <div className="council-agent-form">
            <label className="field">
              <span>
                Model
                <span className="help" data-tooltip="LLM model used for synthesis.">
                  ?
                </span>
              </span>
              <input type="text" value={synthesizerAgent.model ?? ""} readOnly />
            </label>
            <label className="field">
              <span>
                Temperature
                <span className="help" data-tooltip="Randomness for synthesis (0–1).">
                  ?
                </span>
              </span>
              <input
                className="short-input"
                type="number"
                step="0.05"
                min={0}
                max={1}
                value={synthesizerAgent.temperature}
                readOnly
              />
            </label>
          </div>
          <label className="field">
            <span>
              System prompt
              <span className="help" data-tooltip="Defines the messenger role for synthesis.">
                ?
              </span>
            </span>
            <textarea
              rows={3}
              value={synthesizerAgent.system_prompt ?? DEFAULT_SYSTEM_PROMPT}
              readOnly
            />
          </label>
          <label className="field">
            <span>
              User prompt template
              <span className="help" data-tooltip="Task instructions for the messenger.">
                ?
              </span>
            </span>
            <textarea
              rows={4}
              value={synthesizerAgent.user_prompt_template ?? DEFAULT_USER_PROMPT}
              readOnly
            />
          </label>
        </div>
      </div>
      <div className="council-add-panel">
        <button className="secondary" type="button" onClick={handleAddPanel}>
          Add panel
        </button>
      </div>

      <div className="council-lab-panels">
        {panels.map((panel, index) => {
          const isSaved = savedAgents.some((agent) => agent.id === panel.agent.id);
          const isHeuristic = panel.agent.type === "heuristic";
          const weightTotal =
            panel.agent.preferences.theme_weight +
            panel.agent.preferences.efficiency_weight +
            panel.agent.preferences.budget_weight;
          const showVoteWeight = panels.length > 1;
          return (
            <article key={panel.panelId} className="council-lab-panel">
              <div className="council-panel-header">
                <div>
                  <h4>Panel {index + 1}</h4>
                  <p>Single agent run for this card.</p>
                </div>
              <div className="council-panel-actions">
                  <label className="toggle inline-toggle">
                    <input
                      type="checkbox"
                      checked={panel.includeInCouncil}
                      onChange={(event) =>
                        updatePanel(panel.panelId, (current) => ({
                          ...current,
                          includeInCouncil: event.target.checked,
                        }))
                      }
                    />
                    <span>Include</span>
                  </label>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => handleAnalyze(panel.panelId)}
                    disabled={panel.loading}
                  >
                    {panel.loading ? (
                      <>
                        <span className="spinner" aria-hidden="true" />
                        Analyzing...
                      </>
                    ) : (
                      "Analyze"
                    )}
                  </button>
                  {panels.length > 1 && (
                    <button
                      className="secondary"
                      type="button"
                      onClick={() => handleRemovePanel(panel.panelId)}
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>

              <label className="field">
                <span>
                  Load agent
                  <span
                    className="help"
                    data-tooltip="Choose a default agent from council.yaml or a saved agent from your browser."
                  >
                    ?
                  </span>
                  {isHeuristic && (
                    <span className="muted inline-note">
                      Heuristic agents skip LLM prompts.
                    </span>
                  )}
                </span>
                <select
                  value={panel.selectedKey}
                  onChange={(event) => handleSelectAgent(panel.panelId, event.target.value)}
                >
                  {libraryOptions.map((option) => (
                    <option key={option.key} value={option.key}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <div className="council-agent-form">
                <label className="field">
                  <span>
                    Agent ID
                    <span
                      className="help"
                      data-tooltip="Stable identifier used in logs, exports, and routing. Keep it unique."
                    >
                      ?
                    </span>
                  </span>
                  <input
                    type="text"
                    value={panel.agent.id}
                    onChange={(event) =>
                      updatePanel(panel.panelId, (current) => ({
                        ...current,
                        agent: { ...current.agent, id: event.target.value },
                      }))
                    }
                  />
                </label>
                <label className="field">
                  <span>
                    Display name
                    <span
                      className="help"
                      data-tooltip="UI label shown in panels and exports. Leave blank to use Agent ID."
                    >
                      ?
                    </span>
                  </span>
                  <input
                    type="text"
                    value={panel.agent.display_name ?? ""}
                    onChange={(event) =>
                      updatePanel(panel.panelId, (current) => ({
                        ...current,
                        agent: { ...current.agent, display_name: event.target.value || null },
                      }))
                    }
                  />
                </label>
                <label className="field">
                  <span>
                    Type
                    <span
                      className="help"
                      data-tooltip="Heuristic = scores only. LLM = scores + generated reason using prompts."
                    >
                      ?
                    </span>
                  </span>
                  <select
                    value={panel.agent.type}
                    onChange={(event) =>
                      updatePanel(panel.panelId, (current) => ({
                        ...current,
                        agent: { ...current.agent, type: event.target.value },
                      }))
                    }
                  >
                    <option value="heuristic">heuristic</option>
                    <option value="llm">llm</option>
                  </select>
                </label>
                <label className="field">
                  <span>
                    Model
                    <span
                      className="help"
                      data-tooltip="LLM model name (used only when Type = LLM). Example: gpt-4o-mini."
                    >
                      ?
                    </span>
                  </span>
                  <input
                    type="text"
                    value={panel.agent.model ?? ""}
                    onChange={(event) =>
                      updatePanel(panel.panelId, (current) => ({
                        ...current,
                        agent: { ...current.agent, model: event.target.value || null },
                      }))
                    }
                    placeholder="gpt-4o-mini"
                    disabled={isHeuristic}
                  />
                </label>
                <label className="field">
                  <span>
                    Temperature
                    <span
                      className="help"
                      data-tooltip="LLM randomness (0–1). Lower = more consistent, higher = more creative."
                    >
                      ?
                    </span>
                  </span>
                  <input
                    className="short-input"
                    type="number"
                    step="0.05"
                    min={0}
                    max={1}
                    value={panel.agent.temperature}
                    onChange={(event) =>
                      updatePanel(panel.panelId, (current) => ({
                        ...current,
                        agent: { ...current.agent, temperature: Number(event.target.value) },
                      }))
                    }
                    disabled={isHeuristic}
                  />
                </label>
                <label className="field">
                  <span>
                    Weight
                    <span
                      className="help"
                      data-tooltip="Voting weight used if multiple agents are combined into a council."
                    >
                      ?
                    </span>
                    {showVoteWeight && (
                      <span className="muted inline-note">
                        {formatPercent(panel.agent.weight, totalAgentWeight)}
                      </span>
                    )}
                  </span>
                  <input
                    className="short-input"
                    type="number"
                    step="0.1"
                    min={0}
                    value={panel.agent.weight}
                    placeholder={
                      showVoteWeight
                        ? formatPercent(panel.agent.weight, totalAgentWeight)
                        : undefined
                    }
                    onChange={(event) =>
                      updatePanel(panel.panelId, (current) => ({
                        ...current,
                        agent: { ...current.agent, weight: Number(event.target.value) },
                      }))
                    }
                  />
                </label>
              </div>

              <div className="council-agent-weights">
                <label className="field">
                  <span>
                    Theme weight
                    <span
                      className="help"
                      data-tooltip="Bias toward commander identity/theme match in the heuristic score."
                    >
                      ?
                    </span>
                    <span className="muted inline-note">
                      {formatPercent(panel.agent.preferences.theme_weight, weightTotal)}
                    </span>
                  </span>
                  <input
                    className="short-input"
                    type="number"
                    step="0.05"
                    value={panel.agent.preferences.theme_weight}
                    placeholder={formatPercent(panel.agent.preferences.theme_weight, weightTotal)}
                    onChange={(event) =>
                      updatePanel(panel.panelId, (current) => ({
                        ...current,
                        agent: {
                          ...current.agent,
                          preferences: {
                            ...current.agent.preferences,
                            theme_weight: Number(event.target.value),
                          },
                        },
                      }))
                    }
                  />
                </label>
                <label className="field">
                  <span>
                    Efficiency weight
                    <span
                      className="help"
                      data-tooltip="Bias toward lower mana cost in the heuristic score."
                    >
                      ?
                    </span>
                    <span className="muted inline-note">
                      {formatPercent(panel.agent.preferences.efficiency_weight, weightTotal)}
                    </span>
                  </span>
                  <input
                    className="short-input"
                    type="number"
                    step="0.05"
                    value={panel.agent.preferences.efficiency_weight}
                    placeholder={formatPercent(panel.agent.preferences.efficiency_weight, weightTotal)}
                    onChange={(event) =>
                      updatePanel(panel.panelId, (current) => ({
                        ...current,
                        agent: {
                          ...current.agent,
                          preferences: {
                            ...current.agent.preferences,
                            efficiency_weight: Number(event.target.value),
                          },
                        },
                      }))
                    }
                  />
                </label>
                <label className="field">
                  <span>
                    Budget weight
                    <span
                      className="help"
                      data-tooltip="Bias toward cheaper cards when price data exists."
                    >
                      ?
                    </span>
                    <span className="muted inline-note">
                      {formatPercent(panel.agent.preferences.budget_weight, weightTotal)}
                    </span>
                  </span>
                  <input
                    className="short-input"
                    type="number"
                    step="0.05"
                    value={panel.agent.preferences.budget_weight}
                    placeholder={formatPercent(panel.agent.preferences.budget_weight, weightTotal)}
                    onChange={(event) =>
                      updatePanel(panel.panelId, (current) => ({
                        ...current,
                        agent: {
                          ...current.agent,
                          preferences: {
                            ...current.agent.preferences,
                            budget_weight: Number(event.target.value),
                          },
                        },
                      }))
                    }
                  />
                </label>
                <label className="field">
                  <span>
                    Card price cap (USD)
                    <span
                      className="help"
                      data-tooltip="Optional budget reference for the heuristic (blank = no cap)."
                    >
                      ?
                    </span>
                  </span>
                  <input
                    className="short-input"
                    type="number"
                    step="0.5"
                    value={panel.agent.preferences.price_cap_usd ?? ""}
                    onChange={(event) =>
                      updatePanel(panel.panelId, (current) => ({
                        ...current,
                        agent: {
                          ...current.agent,
                          preferences: {
                            ...current.agent.preferences,
                            price_cap_usd: event.target.value
                              ? Number(event.target.value)
                              : null,
                          },
                        },
                      }))
                    }
                  />
                </label>
              </div>

              <label className="field">
                  <span>
                    System prompt
                    <span
                      className="help"
                      data-tooltip="Sets the agent’s role/behavior. Used only for LLM agents."
                    >
                      ?
                    </span>
                  </span>
                <textarea
                  rows={3}
                  value={panel.agent.system_prompt ?? DEFAULT_SYSTEM_PROMPT}
                  onChange={(event) =>
                    updatePanel(panel.panelId, (current) => ({
                      ...current,
                      agent: { ...current.agent, system_prompt: event.target.value },
                    }))
                  }
                  disabled={isHeuristic}
                />
              </label>
              <label className="field">
                  <span>
                    User prompt template
                    <span
                      className="help"
                      data-tooltip="Natural-language task. Card/commander data and weights are appended automatically."
                    >
                      ?
                    </span>
                  </span>
                <textarea
                  rows={6}
                  value={panel.agent.user_prompt_template ?? DEFAULT_USER_PROMPT}
                  onChange={(event) =>
                    updatePanel(panel.panelId, (current) => ({
                      ...current,
                      agent: { ...current.agent, user_prompt_template: event.target.value },
                    }))
                  }
                  disabled={isHeuristic}
                />
              </label>


              <div className="council-lab-buttons">
                <button className="secondary" type="button" onClick={() => handleSaveAgent(panel.panelId)}>
                  {isSaved ? "Overwrite saved" : "Save agent"}
                </button>
                <button className="secondary" type="button" onClick={() => handleExport(panel.panelId)}>
                  Export YAML
                </button>
                <button className="secondary" type="button" onClick={() => handleImportClick(panel.panelId)}>
                  Import YAML
                </button>
                {isSaved && (
                  <button className="secondary" type="button" onClick={() => handleDeleteAgent(panel.panelId)}>
                    Delete saved
                  </button>
                )}
              </div>
              {panel.error && <div className="notice error">{panel.error}</div>}
              {!panel.error && panel.opinions.length === 0 && !panel.loading && (
                <p className="muted">Run analysis to see this agent's opinion.</p>
              )}
              {panel.opinions.length > 0 && (
                <div className="council-opinions">
                  {panel.opinions.map((opinion) => (
                    <article key={opinion.agent_id} className="council-opinion">
                      <div className="council-opinion-header">
                        <strong>{opinion.display_name}</strong>
                        <span className="pill subtle">{opinion.agent_type}</span>
                        <span className="pill">score {opinion.score.toFixed(2)}</span>
                      </div>
                      <p className="meta">{opinion.metrics}</p>
                      {opinion.reason && <p className="reason">{opinion.reason}</p>}
                    </article>
                  ))}
                </div>
              )}
            </article>
          );
        })}
      </div>
      <input
        ref={fileInputRef}
        className="visually-hidden"
        type="file"
        accept=".yaml,.yml"
        onChange={handleImportFile}
      />
    </div>
  );
}
