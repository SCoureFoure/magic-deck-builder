import { useEffect, useMemo, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";

type CommanderResult = {
  name: string;
  type_line: string;
  color_identity: string[];
  mana_cost: string | null;
  cmc: number;
  eligibility: string | null;
  commander_legal: string;
  image_url: string | null;
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
};

type DeckGenerationResponse = {
  commander_name: string;
  total_cards: number;
  is_valid: boolean;
  validation_errors: string[];
  cards_by_role: Record<string, DeckCardResult[]>;
};

const DEFAULT_LIMIT = 10;
const ROLE_ORDER = ["lands", "ramp", "draw", "removal", "synergy", "wincons", "flex"];
const STAGE_LABELS = {
  search: "Stage 1 — Search",
  wizard: "Stage 2 — Deck Wizard",
};
type Stage = keyof typeof STAGE_LABELS;

function formatColors(colors: string[]): string {
  if (!colors.length) return "C";
  return colors.join("");
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
  const [zoomedImage, setZoomedImage] = useState<{ url: string; alt: string } | null>(
    null
  );
  const normalizedLimit = useMemo(() => {
    const parsed = Number(limit);
    if (Number.isNaN(parsed) || parsed < 1) return DEFAULT_LIMIT;
    return Math.min(parsed, 50);
  }, [limit]);

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

      const response = await fetch(`/api/commanders?${params.toString()}`);
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
        setError("Could not reach API. Is the backend running at http://localhost:8000?");
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
  };

  const handleGenerateDeck = async () => {
    if (!selectedCommander) return;
    setDeckLoading(true);
    setDeckError(null);
    setDeckData(null);

    try {
      const response = await fetch("/api/decks/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ commander_name: selectedCommander.name }),
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
        setDeckError("Could not reach API. Is the backend running at http://localhost:8000?");
      } else {
        setDeckError(err instanceof Error ? err.message : "Unexpected error.");
      }
    } finally {
      setDeckLoading(false);
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
        <div>
          <p className="eyebrow">Commander search</p>
          <h1>Find legal commanders fast.</h1>
          <p className="subtitle">
            Search the local card database and see commander eligibility, colors, and
            rules hints at a glance.
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

        {error && <div className="notice error">{error}</div>}

        {lastQuery && !results.length && !error && !loading && (
          <div className="notice">No commanders found for “{lastQuery}”.</div>
        )}

        {results.length > 0 && (
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
                  <div className="card-info">
                    {card.image_url ? (
                      <img
                        className="card-image"
                        src={card.image_url}
                        alt={`${card.name} card art`}
                        loading="lazy"
                        onClick={(event) =>
                          handleImageClick(event, card.image_url, `${card.name} card art`)
                        }
                      />
                    ) : (
                      <div className="card-image placeholder">No image</div>
                    )}
                    <div>
                      <h3>{card.name}</h3>
                      <p className="muted">{card.type_line}</p>
                    </div>
                  </div>
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

            {deckError && <div className="notice error">{deckError}</div>}

            {deckData && (
              <div className="deck-output">
                <div className="deck-summary">
                  <span className="badge">Total cards: {deckData.total_cards}</span>
                  <span className={`pill ${deckData.is_valid ? "valid" : "invalid"}`}>
                    {deckData.is_valid ? "Valid deck" : "Needs fixes"}
                  </span>
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
