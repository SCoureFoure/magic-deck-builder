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

const DEFAULT_LIMIT = 10;

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
  const [zoomedCardName, setZoomedCardName] = useState<string | null>(null);
  const normalizedLimit = useMemo(() => {
    const parsed = Number(limit);
    if (Number.isNaN(parsed) || parsed < 1) return DEFAULT_LIMIT;
    return Math.min(parsed, 50);
  }, [limit]);

  useEffect(() => {
    if (!zoomedCardName) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest(".card-image")) return;
      setZoomedCardName(null);
    };

    document.addEventListener("pointerdown", handlePointerDown, true);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
    };
  }, [zoomedCardName]);

  const handleImageClick = (
    event: ReactMouseEvent<HTMLImageElement>,
    cardName: string
  ) => {
    event.stopPropagation();
    setZoomedCardName((previous) => (previous === cardName ? null : cardName));
  };

  const handleImageMouseLeave = (cardName: string) => {
    if (zoomedCardName === cardName) {
      setZoomedCardName(null);
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) {
      setError("Enter a commander name to search.");
      return;
    }

    setLoading(true);
    setError(null);
    setResults([]);

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
                <h2>Results</h2>
                <p>{results.length} commander(s) found</p>
              </div>
              <span className="badge">{lastQuery}</span>
            </div>
            <div className="table">
              {results.map((card) => (
                <article key={card.name} className="row">
                  <div className="card-info">
                    {card.image_url ? (
                      <img
                        className={`card-image${zoomedCardName === card.name ? " zoomed" : ""}`}
                        src={card.image_url}
                        alt={`${card.name} card art`}
                        loading="lazy"
                        onClick={(event) => handleImageClick(event, card.name)}
                        onMouseLeave={() => handleImageMouseLeave(card.name)}
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
                </article>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
