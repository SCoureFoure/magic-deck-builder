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
  preferences: AgentPreferences;
  context?: AgentContext;
};

type CouncilAnalysisResponse = {
  session_id: number;
  commander_name: string;
  card_name: string;
  opinions: CouncilOpinion[];
};

type PanelState = {
  panelId: string;
  agent: CouncilAgentConfig;
  selectedKey: string;
  apiKey: string;
  loading: boolean;
  error: string | null;
  opinions: CouncilOpinion[];
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

const cloneAgent = (agent: CouncilAgentConfig): CouncilAgentConfig =>
  JSON.parse(JSON.stringify(agent)) as CouncilAgentConfig;

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

export function CouncilLab({ sessionId, cardId, apiBase }: CouncilLabProps) {
  const [defaultAgents, setDefaultAgents] = useState<CouncilAgentConfig[]>([]);
  const [savedAgents, setSavedAgents] = useState<CouncilAgentConfig[]>(() => {
    if (typeof window === "undefined") return [];
    try {
      const raw = window.localStorage.getItem(SAVED_AGENTS_KEY);
      const parsed = raw ? (JSON.parse(raw) as CouncilAgentConfig[]) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });
  const [panels, setPanels] = useState<PanelState[]>([]);
  const [agentError, setAgentError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [importTargetPanel, setImportTargetPanel] = useState<string | null>(null);

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
        agent: createEmptyAgent(),
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
        setDefaultAgents(data);
        setAgentError(null);
      } catch (err) {
        setAgentError(err instanceof Error ? err.message : "Failed to load agents.");
      }
    };
    fetchAgents();
  }, [apiBase]);

  useEffect(() => {
    if (panels.length > 0 || defaultAgents.length === 0) return;
    const primary = defaultAgents[0] ?? createEmptyAgent();
    const secondary = defaultAgents[1] ?? primary;
    setPanels([
      {
        panelId: `panel-${crypto.randomUUID()}`,
        agent: cloneAgent(primary),
        selectedKey: `default:${primary.id}`,
        apiKey: "",
        loading: false,
        error: null,
        opinions: [],
      },
      {
        panelId: `panel-${crypto.randomUUID()}`,
        agent: cloneAgent(secondary),
        selectedKey: `default:${secondary.id}`,
        apiKey: "",
        loading: false,
        error: null,
        opinions: [],
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
    const next = [...savedAgents.filter((agent) => agent.id !== panel.agent.id), cloneAgent(panel.agent)];
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
      const agent = (await response.json()) as CouncilAgentConfig;
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
          api_key: panel.apiKey.trim() || undefined,
          council_overrides: {
            agents: [
              {
                id: panel.agent.id,
                display_name: panel.agent.display_name,
                type: panel.agent.type,
                weight: panel.agent.weight,
                model: panel.agent.model,
                temperature: panel.agent.temperature,
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
      }));
    } catch (err) {
      updatePanel(panelId, (current) => ({
        ...current,
        error: err instanceof Error ? err.message : "Council analysis failed.",
        loading: false,
      }));
    }
  };

  const handleAddPanel = () => {
    const fallback = defaultAgents[0] ?? createEmptyAgent();
    setPanels((current) => [
      ...current,
      {
        panelId: `panel-${crypto.randomUUID()}`,
        agent: cloneAgent(fallback),
        selectedKey: defaultAgents.length ? `default:${fallback.id}` : "custom",
        apiKey: "",
        loading: false,
        error: null,
        opinions: [],
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
        <button className="secondary" type="button" onClick={handleAddPanel}>
          Add panel
        </button>
      </div>
      {agentError && <div className="notice error">{agentError}</div>}
      <div className="council-lab-panels">
        {panels.map((panel, index) => {
          const isSaved = savedAgents.some((agent) => agent.id === panel.agent.id);
          return (
            <article key={panel.panelId} className="council-lab-panel">
              <div className="council-panel-header">
                <div>
                  <h4>Panel {index + 1}</h4>
                  <p>Single agent run for this card.</p>
                </div>
                <div className="council-panel-actions">
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => handleAnalyze(panel.panelId)}
                    disabled={panel.loading}
                  >
                    {panel.loading ? "Analyzing..." : "Analyze"}
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
                <span>Load agent</span>
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
                  <span>Agent ID</span>
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
                  <span>Display name</span>
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
                  <span>Type</span>
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
                  <span>Model</span>
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
                  />
                </label>
                <label className="field">
                  <span>Temperature</span>
                  <input
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
                  />
                </label>
                <label className="field">
                  <span>Weight</span>
                  <input
                    type="number"
                    step="0.1"
                    min={0}
                    value={panel.agent.weight}
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
                  <span>Theme weight</span>
                  <input
                    type="number"
                    step="0.05"
                    value={panel.agent.preferences.theme_weight}
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
                  <span>Efficiency weight</span>
                  <input
                    type="number"
                    step="0.05"
                    value={panel.agent.preferences.efficiency_weight}
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
                  <span>Budget weight</span>
                  <input
                    type="number"
                    step="0.05"
                    value={panel.agent.preferences.budget_weight}
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
                  <span>Price cap (USD)</span>
                  <input
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
                <span>OpenAI API key (optional)</span>
                <input
                  type="password"
                  value={panel.apiKey}
                  onChange={(event) =>
                    updatePanel(panel.panelId, (current) => ({
                      ...current,
                      apiKey: event.target.value,
                    }))
                  }
                  placeholder="sk-..."
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
