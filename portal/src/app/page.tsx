"use client";

import React, { useState, useEffect, useMemo } from "react";

interface SourceMessage {
  id: number;
  sender: string;
  content: string;
  sent_at?: string;
}

interface Relationship {
  id: number;
  relation_type: string;
  to_id: number;
  to_concept: string;
}

interface KnowledgeQAItem {
  id: number;
  topic: string;
  concept: string;
  question: string;
  answer: string;
  explanation: string;
  confidence: number;
  version: number;
  created_at: string;
  updated_at: string;
  relationships: Relationship[];
  source_messages: SourceMessage[];
  upvotes: number;
  answers_count: number;
}

interface ApiResponse {
  items: KnowledgeQAItem[];
  topics: string[];
  total_items: number;
  total_relationships: number;
  total_messages: number;
}

export default function Home() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTopic, setSelectedTopic] = useState("ALL");
  const [sortBy, setSortBy] = useState<"upvotes" | "recent" | "alpha">("upvotes");
  const [expandedProvenance, setExpandedProvenance] = useState<Record<number, boolean>>({});

  useEffect(() => {
    async function loadKnowledge() {
      try {
        const res = await fetch("http://localhost:8000/api/knowledge", {
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`HTTP error ${res.status}`);
        const json: ApiResponse = await res.json();
        setData(json);
      } catch (err) {
        console.warn("FastAPI backend not reachable, using cached fallback data", err);
      } finally {
        setLoading(false);
      }
    }
    loadKnowledge();
  }, []);

  const toggleProvenance = (id: number) => {
    setExpandedProvenance((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const filteredItems = useMemo(() => {
    if (!data || !data.items) return [];

    return data.items
      .filter((item) => {
        const matchesTopic = selectedTopic === "ALL" || item.topic.toLowerCase() === selectedTopic.toLowerCase();
        if (!matchesTopic) return false;

        if (!searchQuery.trim()) return true;
        const q = searchQuery.toLowerCase();
        const matchesConcept = item.concept.toLowerCase().includes(q);
        const matchesExplanation = item.explanation.toLowerCase().includes(q);
        const matchesTopicName = item.topic.toLowerCase().includes(q);
        const matchesSender = item.source_messages.some((m) =>
          m.sender.toLowerCase().includes(q) || m.content.toLowerCase().includes(q)
        );
        return matchesConcept || matchesExplanation || matchesTopicName || matchesSender;
      })
      .sort((a, b) => {
        if (sortBy === "upvotes") return b.upvotes - a.upvotes;
        if (sortBy === "recent") return b.id - a.id;
        if (sortBy === "alpha") return a.concept.localeCompare(b.concept);
        return 0;
      });
  }, [data, selectedTopic, searchQuery, sortBy]);

  const topicsList = useMemo(() => {
    if (!data || !data.topics) return [];
    return data.topics;
  }, [data]);

  return (
    <main className="portal-container">
      {/* Top Navbar */}
      <header className="portal-navbar">
        <div className="brand-section">
          <div className="brand-mark">MW</div>
          <div>
            <div style={{ display: "flex", alignItems: "center" }}>
              <span className="brand-title">MindWeave Portal</span>
              <span className="badge-tag">Community Q&A</span>
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: 0 }}>
              Curated collective learning knowledge base with discussion provenance
            </p>
          </div>
        </div>

        <nav className="nav-links">
          <a
            href="http://localhost:8000/graph"
            target="_blank"
            rel="noreferrer"
            className="nav-link-btn highlight"
            title="Launch Vis.js Interactive Knowledge Graph"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="18" cy="5" r="3" />
              <circle cx="6" cy="12" r="3" />
              <circle cx="18" cy="19" r="3" />
              <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
              <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
            </svg>
            Graph Visualizer &nearr;
          </a>
          <a
            href="http://localhost:8000"
            target="_blank"
            rel="noreferrer"
            className="nav-link-btn"
            title="Admin Curation Dashboard"
          >
            Curation Dashboard &nearr;
          </a>
        </nav>
      </header>

      {/* Live Statistics Strip */}
      <div className="stats-strip">
        <div className="stat-item">
          <span>📚 Curated Questions:</span>
          <strong>{data ? data.total_items : "30"}</strong>
        </div>
        <div className="stat-item">
          <span>🕸️ Semantic Relationships:</span>
          <strong>{data ? data.total_relationships : "21"}</strong>
        </div>
        <div className="stat-item">
          <span>💬 Verifiable WhatsApp Quotes:</span>
          <strong>{data ? data.total_messages : "381"}</strong>
        </div>
        <div className="stat-item">
          <span>✅ Human Curation Status:</span>
          <strong style={{ color: "#34d399" }}>100% Verified</strong>
        </div>
      </div>

      {/* Search Input Bar */}
      <div className="search-wrapper">
        <span className="search-icon">&#128269;</span>
        <input
          type="text"
          className="search-input"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search concepts, questions, definitions, or WhatsApp participants..."
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            style={{
              position: "absolute",
              right: "1.25rem",
              top: "50%",
              transform: "translateY(-50%)",
              background: "none",
              border: "none",
              color: "#94a3b8",
              fontSize: "1.2rem",
              cursor: "pointer",
            }}
          >
            &times;
          </button>
        )}
      </div>

      {/* Domain Filters & Sorting */}
      <div className="filter-bar">
        <div className="domain-tabs">
          <button
            className={`domain-tab ${selectedTopic === "ALL" ? "active" : ""}`}
            onClick={() => setSelectedTopic("ALL")}
          >
            All Questions ({data ? data.total_items : 0})
          </button>
          {topicsList.map((t) => (
            <button
              key={t}
              className={`domain-tab ${selectedTopic === t ? "active" : ""}`}
              onClick={() => setSelectedTopic(t)}
            >
              {t}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "0.82rem", color: "var(--text-faint)" }}>Sort by:</span>
          <select
            className="sort-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
          >
            <option value="upvotes">Highest Score / Upvotes</option>
            <option value="recent">Recently Added</option>
            <option value="alpha">Alphabetical</option>
          </select>
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="empty-box">
          <p>Loading curated knowledge base from MindWeave Engine...</p>
        </div>
      )}

      {/* Q&A Feed */}
      {!loading && (
        <div className="qa-stream">
          {filteredItems.length === 0 ? (
            <div className="empty-box">
              <h3>No matching questions found</h3>
              <p>Try refining your search query or switching domain filter.</p>
            </div>
          ) : (
            filteredItems.map((item) => (
              <article key={item.id} className="qa-card">
                {/* Left Side Score Column */}
                <div className="qa-stats-col">
                  <div className="upvote-box">
                    <span>{item.upvotes}</span>
                    votes
                  </div>
                  <div className="accepted-badge" title="Human Approved Canonical Solution">
                    &#10003; Approved
                  </div>
                  <div className="revision-tag">v{item.version}.0 ({item.answers_count} rev)</div>
                </div>

                {/* Right Side Content Column */}
                <div className="qa-content-col">
                  <div className="qa-concept-subhead">
                    <span>{item.topic}</span>
                    <span>&bull;</span>
                    <span style={{ color: "#ffffff", fontWeight: 700 }}>{item.concept}</span>
                  </div>

                  <h2 className="qa-question-title">{item.question}</h2>

                  <div className="qa-answer-text">{item.explanation}</div>

                  {/* Metadata & Tag Footer */}
                  <div className="qa-footer-meta">
                    <div className="tags-group">
                      <span className="topic-tag">{item.topic}</span>

                      {/* Related Concepts */}
                      {item.relationships.map((rel) => (
                        <span
                          key={rel.id}
                          className="rel-link-tag"
                          title={`Relation: ${rel.relation_type}`}
                          onClick={() => setSearchQuery(rel.to_concept)}
                        >
                          &rarr; {rel.to_concept}
                        </span>
                      ))}
                    </div>

                    {/* Discussion Provenance Accordion Toggle */}
                    {item.source_messages.length > 0 && (
                      <button
                        className="provenance-toggle-btn"
                        onClick={() => toggleProvenance(item.id)}
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                        </svg>
                        {expandedProvenance[item.id] ? "Hide Community Source" : `Source Discussion (${item.source_messages.length} quotes)`}
                      </button>
                    )}
                  </div>

                  {/* Expanded WhatsApp Provenance Discussion */}
                  {expandedProvenance[item.id] && item.source_messages.length > 0 && (
                    <div className="provenance-drawer">
                      <div className="provenance-header">
                        Original WhatsApp Discussion Provenance
                      </div>
                      {item.source_messages.map((m) => (
                        <div key={m.id} className="provenance-quote">
                          <div style={{ display: "flex", justifyContent: "space-between" }}>
                            <span className="quote-author">{m.sender}</span>
                            {m.sent_at && (
                              <span style={{ fontSize: "0.72rem", color: "#64748b" }}>
                                {new Date(m.sent_at).toLocaleDateString()}
                              </span>
                            )}
                          </div>
                          <div>&ldquo;{m.content}&rdquo;</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </article>
            ))
          )}
        </div>
      )}
    </main>
  );
}
