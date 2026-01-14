import { useMemo, useState } from "react";

type CommanderResult = {
  name: string;
  type_line: string;
  color_identity: string[];
  mana_cost: string | null;
  cmc: number;
  eligibility: string | null;
  commander_legal: string;
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

  const normalizedLimit = useMemo(() => {
    const parsed = Number(limit);
    if (Number.isNaN(parsed) || parsed < 1) return DEFAULT_LIMIT;
    return Math.min(parsed, 50);
  }, [limit]);

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
        if (response.status === 404) {
          setResults([]);
          setLastQuery(query.trim());
          return;
        }
        throw new Error("Search failed.");
      }

      const data = (await response.json()) as CommanderSearchResponse;
      setResults(data.results);
      setLastQuery(data.query);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error.");
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
                  <div>
                    <h3>{card.name}</h3>
                    <p className="muted">{card.type_line}</p>
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
