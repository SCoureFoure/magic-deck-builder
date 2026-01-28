import { useEffect, useMemo, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import { CardDisplay, type CardFace } from "./components/CardDisplay";
import { CouncilLab } from "./components/CouncilLab";

type CommanderResult = {
  name: string;
  type_line: string;
  color_identity: string[];
  mana_cost: string | null;
  cmc: number;
  eligibility: string | null;
  commander_legal: string;
  image_url: string | null;
  card_faces?: CardFace[] | null;
};

type CommanderSearchResponse = {
  query: string;
  count: number;
  results: CommanderResult[];
};

type DeckCardResult = {
  name: string;
  quantity: number;
  role: string;
  type_line: string;
  mana_cost: string | null;
  cmc: number;
  image_url: string | null;
  identity_score: number;
  commander_score: number;
  deck_score: number;
};

type DeckGenerationResponse = {
  commander_name: string;
  total_cards: number;
  is_valid: boolean;
  validation_errors: string[];
  cards_by_role: Record<string, DeckCardResult[]>;
  metrics: DeckMetrics;
};

type DeckMetrics = {
  archetype_purity: number;
  identity_concentration: number;
  synergy_ratio: number;
  role_balance: Record<string, number>;
};

type TrainingCard = {
  id: number;
  name: string;
  type_line: string;
  color_identity: string[];
  mana_cost: string | null;
  cmc: number;
  oracle_text: string | null;
  image_url: string | null;
  card_faces?: CardFace[] | null;
};

type TrainingSessionResponse = {
  session_id: number;
  commander: TrainingCard;
};

type TrainingCardResponse = {
  session_id: number;
  card: TrainingCard;
};

type TrainingCommanderStat = {
  card_name: string;
  yes: number;
  no: number;
  ratio: number;
};

type TrainingStatsResponse = {
  total_votes: number;
  commanders: {
    commander_name: string;
    yes: number;
    no: number;
    ratio: number;
    cards: TrainingCommanderStat[];
  }[];
};

type SynergyCardResult = {
  card_name: string;
  type_line: string;
  mana_cost: string | null;
  cmc: number;
  image_url: string | null;
  card_faces?: CardFace[] | null;
  yes: number;
  no: number;
  ratio: number;
  total_votes: number;
  legal_for_commander: boolean;
};
const DEFAULT_LIMIT = 10;
const ROLE_ORDER = ["lands", "ramp", "draw", "removal", "synergy", "wincons", "flex"];
const STAGE_LABELS = {
  search: "Stage 1 — Search",
  wizard: "Stage 2 — Deck Wizard",
  training: "Training — Synergy Labels",
};
type Stage = keyof typeof STAGE_LABELS;
const API_BASE =
  (import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE?.trim() ?? "";

const apiUrl = (path: string) => {
  if (!API_BASE) return path;
  if (API_BASE.endsWith("/") && path.startsWith("/")) {
    return `${API_BASE.slice(0, -1)}${path}`;
  }
  if (!API_BASE.endsWith("/") && !path.startsWith("/")) {
    return `${API_BASE}/${path}`;
  }
  return `${API_BASE}${path}`;
};

function formatColors(colors: string[]): string {
  if (!colors.length) return "C";
  return colors.join("");
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function App() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(DEFAULT_LIMIT.toString());
  const [populate, setPopulate] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<CommanderResult[]>([]);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [stage, setStage] = useState<Stage>("search");
  const [selectedCommander, setSelectedCommander] = useState<CommanderResult | null>(null);
  const [deckLoading, setDeckLoading] = useState(false);
  const [deckError, setDeckError] = useState<string | null>(null);
  const [deckData, setDeckData] = useState<DeckGenerationResponse | null>(null);
  const [useCouncil, setUseCouncil] = useState(false);
  const [trainingLoading, setTrainingLoading] = useState(false);
  const [trainingError, setTrainingError] = useState<string | null>(null);
  const [trainingSession, setTrainingSession] = useState<TrainingSessionResponse | null>(null);
  const [trainingCard, setTrainingCard] = useState<TrainingCard | null>(null);
  const [trainingStats, setTrainingStats] = useState<TrainingStatsResponse | null>(null);
  const [synergyQuery, setSynergyQuery] = useState("");
  const [synergyResults, setSynergyResults] = useState<SynergyCardResult[]>([]);
  const [synergyLoading, setSynergyLoading] = useState(false);
  const [synergyError, setSynergyError] = useState<string | null>(null);
  const [topSynergies, setTopSynergies] = useState<SynergyCardResult[]>([]);
  const [topSynergyLoading, setTopSynergyLoading] = useState(false);
  const [topSynergyError, setTopSynergyError] = useState<string | null>(null);
  const [zoomedImage, setZoomedImage] = useState<{ url: string; alt: string } | null>(
    null
  );
  const normalizedLimit = useMemo(() => {
    const parsed = Number(limit);
    if (Number.isNaN(parsed) || parsed < 1) return DEFAULT_LIMIT;
    return Math.min(parsed, 50);
  }, [limit]);

  useEffect(() => {
    if (!selectedCommander) {
      setTopSynergies([]);
      setTopSynergyError(null);
      return;
    }
    fetchTopSynergies(selectedCommander.name);
  }, [selectedCommander]);

  const handleImageClick = (
    event: ReactMouseEvent<HTMLImageElement>,
    imageUrl: string | null,
    alt: string
  ) => {
    event.stopPropagation();
    if (!imageUrl) return;
    setZoomedImage({ url: imageUrl, alt });
  };

  const handleSearch = async () => {
    if (!query.trim()) {
      setError("Enter a commander name to search.");
      return;
    }

    setLoading(true);
    setError(null);
    setResults([]);
    setStage("search");
    setSelectedCommander(null);
    setDeckData(null);
    setDeckError(null);

    try {
      const params = new URLSearchParams({
        query: query.trim(),
        limit: normalizedLimit.toString(),
      });
      if (populate) {
        params.set("populate", "true");
      }

      const response = await fetch(apiUrl(`/api/commanders?${params.toString()}`));
      if (!response.ok) {
        let detail = "Search failed.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // Ignore JSON parse errors and use default message.
        }

        if (response.status === 404) {
          setResults([]);
          setLastQuery(query.trim());
          setError(detail);
          return;
        }
        throw new Error(`Search failed (${response.status}). ${detail}`);
      }

      const data = (await response.json()) as CommanderSearchResponse;
      setResults(data.results);
      setLastQuery(data.query);
    } catch (err) {
      if (err instanceof TypeError) {
        const hint = API_BASE || "http://localhost:8000";
        setError(`Could not reach API. Is the backend running at ${hint}?`);
      } else {
        setError(err instanceof Error ? err.message : "Unexpected error.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSelectCommander = (commander: CommanderResult) => {
    setSelectedCommander(commander);
    setStage("wizard");
    setDeckData(null);
    setDeckError(null);
    setSynergyResults([]);
    setSynergyQuery("");
    setSynergyError(null);
  };

  const handleGenerateDeck = async () => {
    if (!selectedCommander) return;
    setDeckLoading(true);
    setDeckError(null);
    setDeckData(null);

    try {
      const response = await fetch(apiUrl("/api/decks/generate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          commander_name: selectedCommander.name,
          use_llm_agent: true,
          use_council: useCouncil,
        }),
      });

      if (!response.ok) {
        let detail = "Deck generation failed.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // Ignore JSON parse errors and use default message.
        }
        throw new Error(`Deck generation failed (${response.status}). ${detail}`);
      }

      const data = (await response.json()) as DeckGenerationResponse;
      setDeckData(data);
    } catch (err) {
      if (err instanceof TypeError) {
        const hint = API_BASE || "http://localhost:8000";
        setDeckError(`Could not reach API. Is the backend running at ${hint}?`);
      } else {
        setDeckError(err instanceof Error ? err.message : "Unexpected error.");
      }
    } finally {
      setDeckLoading(false);
    }
  };

  const fetchTopSynergies = async (commanderName: string) => {
    setTopSynergyLoading(true);
    setTopSynergyError(null);
    try {
      const response = await fetch(
        apiUrl(
          `/api/commanders/${encodeURIComponent(
            commanderName,
          )}/synergy/top?limit=5&min_ratio=0.5`,
        ),
      );
      if (!response.ok) {
        let detail = "Top synergy lookup failed.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // Ignore JSON parse errors and use default message.
        }
        throw new Error(`Top synergy lookup failed (${response.status}). ${detail}`);
      }

      const data = (await response.json()) as SynergyCardResult[];
      setTopSynergies(data);
    } catch (err) {
      if (err instanceof TypeError) {
        const hint = API_BASE || "http://localhost:8000";
        setTopSynergyError(`Could not reach API. Is the backend running at ${hint}?`);
      } else {
        setTopSynergyError(err instanceof Error ? err.message : "Unexpected error.");
      }
    } finally {
      setTopSynergyLoading(false);
    }
  };

  const handleSynergySearch = async () => {
    if (!selectedCommander) return;
    if (!synergyQuery.trim()) {
      setSynergyError("Enter a card name to search.");
      return;
    }
    setSynergyLoading(true);
    setSynergyError(null);
    setSynergyResults([]);

    try {
      const params = new URLSearchParams({ query: synergyQuery.trim() });
      const response = await fetch(
        apiUrl(
          `/api/commanders/${encodeURIComponent(selectedCommander.name)}/synergy?${params.toString()}`,
        ),
      );
      if (!response.ok) {
        let detail = "Synergy search failed.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // Ignore JSON parse errors and use default message.
        }
        throw new Error(`Synergy search failed (${response.status}). ${detail}`);
      }
      const data = (await response.json()) as SynergyCardResult[];
      setSynergyResults(data);
    } catch (err) {
      if (err instanceof TypeError) {
        const hint = API_BASE || "http://localhost:8000";
        setSynergyError(`Could not reach API. Is the backend running at ${hint}?`);
      } else {
        setSynergyError(err instanceof Error ? err.message : "Unexpected error.");
      }
    } finally {
      setSynergyLoading(false);
    }
  };

  const handleStartTraining = async () => {
    setStage("training");
    setTrainingSession(null);
    setTrainingCard(null);
    await startTrainingSession();
  };

  const startTrainingSession = async () => {
    setTrainingLoading(true);
    setTrainingError(null);
    try {
      const response = await fetch(apiUrl("/api/training/session/start"), { method: "POST" });
      if (!response.ok) {
        let detail = "Training session failed.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // Ignore JSON parse errors and use default message.
        }
        throw new Error(`Training session failed (${response.status}). ${detail}`);
      }
      const data = (await response.json()) as TrainingSessionResponse;
      setTrainingSession(data);
      await fetchTrainingCard(data.session_id);
      await fetchTrainingStats();
    } catch (err) {
      if (err instanceof TypeError) {
        const hint = API_BASE || "http://localhost:8000";
        setTrainingError(`Could not reach API. Is the backend running at ${hint}?`);
      } else {
        setTrainingError(err instanceof Error ? err.message : "Unexpected error.");
      }
    } finally {
      setTrainingLoading(false);
    }
  };

  const fetchTrainingCard = async (sessionId: number) => {
    try {
      const response = await fetch(apiUrl(`/api/training/session/${sessionId}/next`));
      if (!response.ok) {
        let detail = "Training card failed.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // Ignore JSON parse errors and use default message.
        }
        throw new Error(`Training card failed (${response.status}). ${detail}`);
      }
      const data = (await response.json()) as TrainingCardResponse;
      setTrainingCard(data.card);
    } catch (err) {
      if (err instanceof TypeError) {
        const hint = API_BASE || "http://localhost:8000";
        setTrainingError(`Could not reach API. Is the backend running at ${hint}?`);
      } else {
        setTrainingError(err instanceof Error ? err.message : "Unexpected error.");
      }
    }
  };

  const fetchTrainingStats = async () => {
    try {
      const response = await fetch(apiUrl("/api/training/stats"));
      if (!response.ok) {
        return;
      }
      const data = (await response.json()) as TrainingStatsResponse;
      setTrainingStats(data);
    } catch {
      // Ignore stats errors to avoid blocking training flow.
    }
  };

  const handleTrainingLabel = async (vote: number) => {
    if (!trainingSession || !trainingCard) return;
    setTrainingLoading(true);
    setTrainingError(null);
    try {
      const response = await fetch(apiUrl("/api/training/session/vote"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: trainingSession.session_id,
          card_id: trainingCard.id,
          vote,
        }),
      });
      if (!response.ok) {
        let detail = "Label submission failed.";
        try {
          const payload = await response.json();
          if (typeof payload?.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // Ignore JSON parse errors and use default message.
        }
        throw new Error(`Label submission failed (${response.status}). ${detail}`);
      }
      await fetchTrainingCard(trainingSession.session_id);
      await fetchTrainingStats();
    } catch (err) {
      if (err instanceof TypeError) {
        setTrainingError("Could not reach API. Is the backend running at http://localhost:8000?");
      } else {
        setTrainingError(err instanceof Error ? err.message : "Unexpected error.");
      }
    } finally {
      setTrainingLoading(false);
    }
  };

  const visibleResults =
    stage === "wizard" && selectedCommander
      ? results.filter((card) => card.name === selectedCommander.name)
      : results;

  const deckRoles = useMemo(() => {
    if (!deckData) return [];
    const roleNames = Object.keys(deckData.cards_by_role);
    const ordered = ROLE_ORDER.filter((role) => roleNames.includes(role));
    const remaining = roleNames.filter((role) => !ROLE_ORDER.includes(role));
    return [...ordered, ...remaining];
  }, [deckData]);

  return (
    <div className="page">
      <header className="hero">
        <div key={stage} className="hero-copy">
          <p className="eyebrow">
            {stage === "search" && "Commander search"}
            {stage === "wizard" && "Deck wizard"}
            {stage === "training" && "Synergy training"}
          </p>
          <h1>
            {stage === "search" && "Find legal commanders fast."}
            {stage === "wizard" && "Shape a commander deck with intent."}
            {stage === "training" && "Train synergy by quick judgments."}
          </h1>
          <p className="subtitle">
            {stage === "search" &&
              "Search the local card database and see commander eligibility, colors, and rules hints at a glance."}
            {stage === "wizard" &&
              "Generate a deck, inspect card roles, and explore commander synergy signals."}
            {stage === "training" &&
              "Vote Potential or Pass to build real synergy data for future models."}
          </p>
        </div>
        <div className="hero-card">
          <div className="signal">
            <span>DB</span>
            <span>FastAPI</span>
            <span>Vite</span>
          </div>
          <p>
            Tip: Use populate only when you need to rebuild commander eligibility
            from the full card dataset.
          </p>
        </div>
      </header>

      <section className="panel">
        <div className="tabs">
          <button
            className={stage === "search" ? "tab active" : "tab"}
            onClick={() => setStage("search")}
          >
            Search
          </button>
          <button
            className={stage === "wizard" ? "tab active" : "tab"}
            onClick={() => setStage("wizard")}
            disabled={!selectedCommander}
          >
            Deck Wizard
          </button>
          <button
            className={stage === "training" ? "tab active" : "tab"}
            onClick={handleStartTraining}
          >
            Training
          </button>
        </div>
        <p className="muted">
          {stage === "search" &&
            "Search the card database to pick a commander and review eligibility."}
          {stage === "wizard" &&
            "Build a deck for the selected commander and explore synergy stats."}
          {stage === "training" &&
            "Label whether a card feels like a good fit for a random commander."}
        </p>

        {stage !== "training" && (
          <div className="controls">
            <label className="field">
              <span>Name</span>
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Atraxa, Sisay, Urza..."
              />
            </label>
            <label className="field">
              <span>Limit</span>
              <input
                type="number"
                min={1}
                max={50}
                value={limit}
                onChange={(event) => setLimit(event.target.value)}
              />
            </label>
            <label className="toggle">
              <input
                type="checkbox"
                checked={populate}
                onChange={(event) => setPopulate(event.target.checked)}
              />
              <span>Populate commanders first</span>
            </label>
            <button className="primary" onClick={handleSearch} disabled={loading}>
              {loading ? "Searching..." : "Search"}
            </button>
          </div>
        )}

        {error && <div className="notice error">{error}</div>}

        {lastQuery && !results.length && !error && !loading && (
          <div className="notice">No commanders found for “{lastQuery}”.</div>
        )}

        {stage !== "training" && results.length > 0 && (
          <div className="results">
            <div className="results-header">
              <div>
                <h2>{stage === "search" ? "Results" : "Selected Commander"}</h2>
                <p>{STAGE_LABELS[stage]}</p>
              </div>
              {lastQuery && <span className="badge">{lastQuery}</span>}
            </div>
            <div className="table">
              {visibleResults.map((card) => (
                <article key={card.name} className="row">
                  <CardDisplay
                    variant="compact"
                    faceLayout="row"
                    className="row-card"
                    card={{
                      name: card.name,
                      type_line: card.type_line,
                      mana_cost: card.mana_cost,
                      cmc: card.cmc,
                      image_url: card.image_url,
                      card_faces: card.card_faces,
                    }}
                    onImageClick={handleImageClick}
                  />
                  <div className="pill-group">
                    <span className="pill">{formatColors(card.color_identity)}</span>
                    <span className="pill">
                      {card.mana_cost ? `${card.mana_cost} (${card.cmc})` : card.cmc}
                    </span>
                    <span className="pill subtle">{card.commander_legal}</span>
                  </div>
                  <div className="eligibility">
                    {card.eligibility ? card.eligibility : "Unknown"}
                  </div>
                  {stage === "search" && (
                    <div className="row-actions">
                      <button
                        className="secondary"
                        onClick={() => handleSelectCommander(card)}
                      >
                        Select
                      </button>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </div>
        )}

        {stage === "wizard" && selectedCommander && (
          <div className="wizard">
            <div className="wizard-header">
              <div>
                <h2>Deck Wizard</h2>
                <p>Generate a 100-card Commander deck for {selectedCommander.name}.</p>
              </div>
              <button className="secondary" onClick={handleGenerateDeck} disabled={deckLoading}>
                {deckLoading ? "Building..." : "Generate deck"}
              </button>
            </div>
            <div className="council-toggle">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={useCouncil}
                  onChange={(event) => setUseCouncil(event.target.checked)}
                />
                <span>Use council mode</span>
              </label>
              <p className="muted">
                Council mode runs multiple agents (heuristic + LLM) and aggregates their
                ranked picks into a consensus list before selecting cards.
              </p>
            </div>

            <div className="synergy-search">
              <div className="synergy-search-header">
                <div>
                  <h3>Commander synergy lookup</h3>
                  <p>Search any card name and see community ratios.</p>
                </div>
              </div>
              <div className="synergy-search-controls">
                <input
                  type="text"
                  value={synergyQuery}
                  onChange={(event) => setSynergyQuery(event.target.value)}
                  placeholder="Search cards..."
                />
                <button
                  className="primary"
                  onClick={handleSynergySearch}
                  disabled={synergyLoading}
                >
                  {synergyLoading ? "Searching..." : "Search"}
                </button>
              </div>
              {topSynergyError && <div className="notice error">{topSynergyError}</div>}
              {topSynergyLoading && (
                <div className="notice">Loading top community synergies...</div>
              )}
              {!topSynergyLoading && topSynergies.length > 0 && (
                <div className="synergy-results">
                  <div className="results-header">
                    <div>
                      <h4>Top community synergies</h4>
                      <p>Cards with at least 50% yes votes.</p>
                    </div>
                  </div>
                  {topSynergies.map((card) => (
                    <CardDisplay
                      key={`top-${card.card_name}`}
                      variant="compact"
                      faceLayout="row"
                      className="synergy-card"
                      card={{
                        name: card.card_name,
                        type_line: card.type_line,
                        mana_cost: card.mana_cost,
                        cmc: card.cmc,
                        image_url: card.image_url,
                        card_faces: card.card_faces,
                      }}
                      onImageClick={handleImageClick}
                    >
                      <p className="meta">
                        Community Synergy Score: {card.yes} yes / {card.no} no (
                        {formatPercent(card.ratio)})
                      </p>
                      {!card.legal_for_commander && (
                        <p className="meta warning">Not legal for this commander.</p>
                      )}
                    </CardDisplay>
                  ))}
                </div>
              )}
              {synergyError && <div className="notice error">{synergyError}</div>}
              {synergyResults.length > 0 && (
                <div className="synergy-results">
                  {synergyResults.map((card) => (
                    <CardDisplay
                      key={card.card_name}
                      variant="compact"
                      faceLayout="row"
                      className="synergy-card"
                      card={{
                        name: card.card_name,
                        type_line: card.type_line,
                        mana_cost: card.mana_cost,
                        cmc: card.cmc,
                        image_url: card.image_url,
                        card_faces: card.card_faces,
                      }}
                      onImageClick={handleImageClick}
                    >
                      <p className="meta">
                        {card.total_votes === 0
                          ? "Community Synergy Score: Unrated"
                          : `Community Synergy Score: ${card.yes} yes / ${card.no} no (${formatPercent(card.ratio)})`}
                      </p>
                      {!card.legal_for_commander && (
                        <p className="meta warning">Not legal for this commander.</p>
                      )}
                    </CardDisplay>
                  ))}
                </div>
              )}
            </div>

            {deckError && <div className="notice error">{deckError}</div>}

            {deckData && (
              <div className="deck-output">
                <div className="deck-summary">
                  <span className="badge">Total cards: {deckData.total_cards}</span>
                  <span className={`pill ${deckData.is_valid ? "valid" : "invalid"}`}>
                    {deckData.is_valid ? "Valid deck" : "Needs fixes"}
                  </span>
                </div>

                <div className="deck-metrics">
                  <article className="metric-card">
                    <p>Archetype purity</p>
                    <strong>{formatPercent(deckData.metrics.archetype_purity)}</strong>
                  </article>
                  <article className="metric-card">
                    <p>Identity concentration</p>
                    <strong>{formatPercent(deckData.metrics.identity_concentration)}</strong>
                  </article>
                  <article className="metric-card">
                    <p>Synergy ratio</p>
                    <strong>{formatPercent(deckData.metrics.synergy_ratio)}</strong>
                  </article>
                </div>

                {deckData.validation_errors.length > 0 && (
                  <div className="validation">
                    <h3>Validation warnings</h3>
                    <ul>
                      {deckData.validation_errors.map((message) => (
                        <li key={message}>{message}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="deck-roles">
                  {deckRoles.map((role) => {
                    const cards = deckData.cards_by_role[role] ?? [];
                    const roleCount = cards.reduce((sum, card) => sum + card.quantity, 0);
                    return (
                      <section key={role} className="deck-role">
                        <div className="deck-role-header">
                          <h3>{role}</h3>
                          <span className="badge">{roleCount}</span>
                        </div>
                        <div className="deck-cards">
                          {cards.map((card) => (
                            <article key={`${role}-${card.name}`} className="deck-card">
                              {card.image_url ? (
                                <img
                                  src={card.image_url}
                                  alt={card.name}
                                  loading="lazy"
                                  onClick={(event) =>
                                    handleImageClick(event, card.image_url, card.name)
                                  }
                                />
                              ) : (
                                <div className="deck-card-placeholder">No image</div>
                              )}
                              <div>
                                <h4>{card.name}</h4>
                                <p className="muted">{card.type_line}</p>
                                <p className="meta">
                                  {card.quantity}x · {card.mana_cost ? `${card.mana_cost} (${card.cmc})` : card.cmc}
                                </p>
                                <p className="meta">
                                  Commander synergy: {formatPercent(card.commander_score)}
                                </p>
                                <p className="meta">
                                  Deck synergy: {formatPercent(card.deck_score)}
                                </p>
                              </div>
                            </article>
                          ))}
                        </div>
                      </section>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {stage === "training" && (
          <div className="training">
            <div className="training-header">
              <div>
                <h2>Synergy Training</h2>
                <p>Mark whether the card synergizes with the commander.</p>
              </div>
              <button
                className="secondary"
                onClick={startTrainingSession}
                disabled={trainingLoading}
              >
                {trainingLoading ? "Loading..." : "New session"}
              </button>
            </div>

            {trainingError && <div className="notice error">{trainingError}</div>}

            {trainingSession && trainingCard && (
              <div className="training-grid">
                {trainingStats && (
                  <div className="training-stats">
                    <div className="metric-card">
                      <p>Total votes</p>
                      <strong>{trainingStats.total_votes}</strong>
                    </div>
                  </div>
                )}
                {[trainingSession.commander, trainingCard].map((card) => (
                  <CardDisplay
                    key={card.id}
                    variant="detailed"
                    card={card}
                    showOracle
                    onImageClick={handleImageClick}
                  />
                ))}
                <div className="training-actions">
                  <button
                    className="primary"
                    onClick={() => handleTrainingLabel(1)}
                    disabled={trainingLoading}
                  >
                    Potential
                  </button>
                  <button
                    className="secondary"
                    onClick={() => handleTrainingLabel(0)}
                    disabled={trainingLoading}
                  >
                    No.
                  </button>
                </div>
                <CouncilLab
                  sessionId={trainingSession.session_id}
                  cardId={trainingCard.id}
                  apiBase={API_BASE}
                />
              </div>
            )}
          </div>
        )}
      </section>
      {zoomedImage && (
        <div
          className="image-modal"
          role="dialog"
          aria-modal="true"
          onClick={() => setZoomedImage(null)}
        >
          <button
            className="modal-close"
            type="button"
            aria-label="Close image"
            onClick={() => setZoomedImage(null)}
          >
            ×
          </button>
          <img src={zoomedImage.url} alt={zoomedImage.alt} />
        </div>
      )}
    </div>
  );
}
