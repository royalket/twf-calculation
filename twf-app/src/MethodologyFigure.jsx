import React, { useRef } from "react";

// ─── Colour palette (colorblind-safe, journal-quality) ──────────────────────
const PHASE_STYLES = [
  { bg: "#D6EAF8", border: "#1A5276", label: "#1A5276", rowBg: "#EBF5FB" },  // Blue   – Data Sources
  { bg: "#D5F5E3", border: "#1E8449", label: "#1E8449", rowBg: "#EAFAF1" },  // Green  – Data Preparation
  { bg: "#FDEBD0", border: "#A04000", label: "#A04000", rowBg: "#FEF9E7" },  // Amber  – EEIO Core
  { bg: "#E8DAEF", border: "#6C3483", label: "#6C3483", rowBg: "#F5EEF8" },  // Purple – Extensions
  { bg: "#FADBD8", border: "#922B21", label: "#922B21", rowBg: "#FDEDEC" },  // Red    – Validation
  { bg: "#D0ECE7", border: "#0E6655", label: "#0E6655", rowBg: "#E8F8F5" },  // Teal   – Outputs
];

// ─── Data ───────────────────────────────────────────────────────────────────
const ROWS = [
  {
    phase: "① Data Sources",
    gist: ["Raw inputs", "6 data streams", "Multi-source"],
    boxes: [
      { title: "TSA 2015–16", lines: ["MoT India", "25 categories", "Inbound · Domestic", "₹ crore base"] },
      { title: "NAS Stmt 6.1", lines: ["MoSPI 2024", "Real GVA growth", "2011-12 prices", "12 sector keys"] },
      { title: "India SUT Tables", lines: ["MoSPI · 3 years", "140×140 matrix", "2015-16·19-20·21-22", "Nominal ₹ crore"] },
      { title: "EXIOBASE v3.8", lines: ["163-sector MRIO", "Blue water W (m³/₹)", "Green water", "India concordance"] },
      { title: "CPI · USD/INR", lines: ["MoSPI · RBI", "Year deflators", "Nominal → real", "Cross-currency"] },
      { title: "WRI Aqueduct 4.0", lines: ["Kuzma et al. 2023", "Sector WSI weights", "Agr=0.827  Ind=0.814", "Services=0.000"] },
    ],
  },
  {
    phase: "② Data Preparation",
    gist: ["Pre-processing", "3 operations", "Temurshoev 2011"],
    boxes: [
      { title: "TSA Extrapolation", lines: ["NAS GVA growth × CPI ratio", "nom_factor = GVA_growth × CPI(t)/CPI₀", "→ TSA₂₀₁₅  TSA₂₀₁₉  TSA₂₀₂₂", "Nominal + real ₹ crore"] },
      { title: "IO Table Construction", lines: ["SUT → Product Tech. Assumption", "140-product → 140×140 symmetric IO", "L = (I − A)⁻¹  per study year", "Balance error < 1.0% verified"] },
      { title: "Tourism Demand Vectors Y", lines: ["25 TSA categories → 163 EXIOBASE codes", "Shares normalised per category (Σ=1)", "Y_total  ·  Y_inbound  ·  Y_domestic", "163 sectors × 3 years = 489 vectors"] },
    ],
  },
  {
    phase: "③ EEIO Core Model",
    gist: ["Core equations", "W · L · Y", "Blue + Scarce"],
    boxes: [
      { title: "Water Vector (W)", lines: ["EXIOBASE → SUT-140 concordance", "m³ per ₹ crore  [shape: 163]", "Blue water only in multiplier", "Green water: parallel disclosure"] },
      { title: "Indirect TWF", lines: ["TWF = W · L · Y", "163 sectors × 3 yrs × 2 types", "Inbound TWF = W·L·Y_inbound", "Domestic TWF = W·L·Y_domestic"] },
      { title: "Scarce TWF", lines: ["Scarce = TWF × WSI_sector", "Sector-level Aqueduct 4.0 weights", "Advance over Lee et al. 2021:", "Country-level → sector-level WSI"] },
      { title: "Direct TWF", lines: ["Activity-based (bottom-up)", "Tourist-days × sector coefficients", "Hotel · Restaurant · Transport", "Direct TWF ≪ Indirect TWF"] },
      { title: "Water Multiplier Ratio", lines: ["MR[j] = WL[j] / WL̄_economy", "MR > 1 → water-intensive sector", "Policy hotspot identification", "Per sector × per year"] },
    ],
  },
  {
    phase: "④ Analytical Extensions",
    gist: ["Novel contributions", "★ Not in", "Lee et al. 2021"],
    boxes: [
      { title: "Structural Decomposition (SDA)", lines: ["ΔTWF = ΔW·eff + ΔL·eff + ΔY·eff", "Six-polar decomposition", "Residual < 0.1%", "2015→19  ·  2019→22"] },
      { title: "Monte Carlo  n=10,000", lines: ["Uncertain: W_agr · W_hotel · volumes", "Output: P5–P95 bounds per year", "Rank-correlation variance decomp.", "Dominant uncertainty sources ranked"] },
      { title: "Supply-Chain Path (HEM)", lines: ["pull[i,j] = W[i]·L[i,j]·Y[j]", "Top-50 dominant pathways ranked", "Hypothetical Extraction Method", "Tourism-dependency index/sector"] },
      { title: "Outbound TWF & Net Balance", lines: ["TWF = N × days × WF_local/365 × 1.5", "Net = Outbound TWF − Inbound TWF", "1.5× tourist multiplier (Lee 2021)", "India: net importer or exporter?"] },
    ],
  },
  {
    phase: "⑤ Validation",
    gist: ["9 assertions", "Sensitivity ±20%", "Error < 1%"],
    boxes: [
      { title: "① Scarce/Blue ∈ [0.30–0.95]", lines: ["Physical plausibility check"] },
      { title: "② Sensitivity: LOW<BASE<HIGH", lines: ["Monotonicity of ±20% bounds"] },
      { title: "③ Inbound > Domestic intensity", lines: ["L/tourist-day ordering check"] },
      { title: "④⑤ Ratios & Green/Blue bounds", lines: ["Inb/Dom ∈[5,30]  Green/Blue ∈[0,10]"] },
      { title: "⑥ YoY Δintensity ∈[−60,+30%]", lines: ["Catches data or scaling errors"] },
      { title: "⑦⑧⑨ IO · SDA · W+L+Y checks", lines: ["Balance<1%  Residual<0.1%  Sum≈ΔTWF"] },
    ],
  },
  {
    phase: "⑥ Outputs",
    gist: ["5 result sets", "Policy-ready", "Journal figures"],
    boxes: [
      { title: "TWF Totals", lines: ["bn m³ · L/tourist/day", "Blue + Scarce + Green", "Inbound vs. Domestic", "2015 · 2019 · 2022"] },
      { title: "Temporal & SDA Drivers", lines: ["ΔW · ΔL · ΔY effects", "COVID structural break", "Technology efficiency Δ", "CAGR by component"] },
      { title: "Net Water Balance", lines: ["Outbound TWF total", "Virtual water transfer", "WSI-weighted scarce", "India net position"] },
      { title: "Uncertainty Bounds", lines: ["MC P5–P95 range", "Sensitivity half-range", "Dominant inputs ranked", "Reproducible (seed=42)"] },
    ],
  },
];

// ─── Sub-components ──────────────────────────────────────────────────────────

function GistBox({ text, style }) {
  return (
    <div style={{
      backgroundColor: style.bg,
      border: `2px solid ${style.border}`,
      borderRadius: 6,
      padding: "10px 8px",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      minHeight: 80,
      gap: 3,
    }}>
      {text.map((line, i) => (
        <div key={i} style={{
          fontSize: i === 0 ? 11 : 9.5,
          fontWeight: i === 0 ? 700 : 400,
          color: style.border,
          textAlign: "center",
          lineHeight: 1.35,
          fontStyle: i === 2 ? "italic" : "normal",
        }}>{line}</div>
      ))}
    </div>
  );
}

function DetailBox({ title, lines, style }) {
  return (
    <div style={{
      backgroundColor: "#fff",
      border: `1.5px solid ${style.border}`,
      borderRadius: 5,
      padding: "7px 8px",
      flex: 1,
      minWidth: 0,
    }}>
      <div style={{
        fontSize: 9.5,
        fontWeight: 700,
        color: style.border,
        borderBottom: `1px solid ${style.border}30`,
        paddingBottom: 4,
        marginBottom: 4,
        lineHeight: 1.3,
      }}>{title}</div>
      {lines.map((line, i) => (
        <div key={i} style={{
          fontSize: 8.5,
          color: "#2c3e50",
          lineHeight: 1.45,
          fontFamily: line.includes("=") || line.includes("·") || line.includes("×") ? "monospace" : "inherit",
        }}>
          {line.includes("=") || line.includes("·") || line.includes("L =") || line.includes("TWF") || line.includes("MR") || line.includes("pull")
            ? <span style={{ color: "#1a3a5c", fontWeight: 600 }}>{line}</span>
            : line}
        </div>
      ))}
    </div>
  );
}

function Arrow() {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      height: 22,
      margin: "0 0",
    }}>
      <svg width="16" height="22" viewBox="0 0 16 22" fill="none">
        <line x1="8" y1="0" x2="8" y2="16" stroke="#5d7a8c" strokeWidth="1.8"/>
        <polygon points="3,13 8,22 13,13" fill="#5d7a8c"/>
      </svg>
    </div>
  );
}

function Row({ data, styleObj, isLast }) {
  return (
    <>
      <div style={{
        display: "grid",
        gridTemplateColumns: "110px 1fr",
        gap: 8,
        backgroundColor: styleObj.rowBg,
        border: `1.8px solid ${styleObj.border}`,
        borderRadius: 7,
        padding: 8,
        alignItems: "stretch",
      }}>
        {/* LEFT: Phase gist */}
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{
            fontSize: 9,
            fontWeight: 800,
            color: "#fff",
            backgroundColor: styleObj.border,
            borderRadius: 4,
            padding: "3px 6px",
            textAlign: "center",
            letterSpacing: "0.03em",
            textTransform: "uppercase",
          }}>
            {data.phase}
          </div>
          <GistBox text={data.gist} style={styleObj} />
        </div>

        {/* RIGHT: Detail boxes */}
        <div style={{ display: "flex", gap: 6, alignItems: "stretch" }}>
          {data.boxes.map((box, i) => (
            <DetailBox key={i} title={box.title} lines={box.lines} style={styleObj} />
          ))}
        </div>
      </div>

      {!isLast && <Arrow />}
    </>
  );
}

// ─── Main figure ─────────────────────────────────────────────────────────────

export default function MethodologyFigure() {
  const figRef = useRef(null);

  // Export as PNG using html2canvas (loaded from CDN when first used)
  const handleExport = async () => {
    if (!figRef.current) return;
    try {
      if (!window.html2canvas) {
        await new Promise((resolve, reject) => {
          const s = document.createElement("script");
          s.src = "https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js";
          s.onload = () => resolve();
          s.onerror = (e) => reject(e);
          document.head.appendChild(s);
        });
      }
      const canvas = await window.html2canvas(figRef.current, { useCORS: true, scale: 2 });
      const link = document.createElement("a");
      link.download = "methodology-figure.png";
      link.href = canvas.toDataURL("image/png");
      link.click();
    } catch (err) {
      console.error("Export failed:", err);
      handleCopy();
      alert("Export failed — figure copied to clipboard as fallback.");
    }
  };

  const handleCopy = () => {
    if (!figRef.current) return;
    const range = document.createRange();
    range.selectNode(figRef.current);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    document.execCommand("copy");
    window.getSelection().removeAllRanges();
  };

  return (
    <div style={{
      fontFamily: "'Arial', 'Helvetica Neue', sans-serif",
      backgroundColor: "#f4f6f9",
      minHeight: "100vh",
      padding: "20px 16px 40px",
    }}>


      {/* Toolbar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#1a2638" }}>
            Fig. 1 — India Tourism Water Footprint: Analytical Framework
          </div>
          <div style={{ fontSize: 10, color: "#607080", marginTop: 2 }}>
            Multi-year EEIO · 163-sector EXIOBASE · SUT-140 · SDA + Monte Carlo · Outbound net balance
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleCopy} style={{
            backgroundColor: "#1A5276", color: "#fff", border: "none",
            borderRadius: 5, padding: "6px 14px", fontSize: 11, fontWeight: 600,
            cursor: "pointer",
          }}>
            Select Figure
          </button>
          <button onClick={handleExport} style={{
            backgroundColor: "#0E6655", color: "#fff", border: "none",
            borderRadius: 5, padding: "6px 14px", fontSize: 11, fontWeight: 600,
            cursor: "pointer",
          }}>
            Export PNG
          </button>
        </div>
      </div>

      {/* Figure */}
      <div ref={figRef} style={{
        backgroundColor: "#ffffff",
        border: "1.5px solid #bcc8d4",
        borderRadius: 8,
        padding: "14px 14px 12px",
        boxShadow: "0 2px 10px rgba(0,0,0,0.07)",
      }}>

        {/* Title */}
        <div style={{ textAlign: "center", marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#1a2638", lineHeight: 1.4 }}>
            Fig. 1. Analytical framework for estimating India's tourism water footprint (TWF) across three study years
          </div>
          <div style={{ fontSize: 9.5, color: "#5a6a7a", marginTop: 3, fontStyle: "italic" }}>
            Study years: 2015–16 · 2019–20 · 2021–22 &nbsp;|&nbsp; EEIO = Environmentally Extended Input–Output &nbsp;|&nbsp; SDA = Structural Decomposition Analysis
          </div>
        </div>

        {/* Rows */}
        <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
          {ROWS.map((row, i) => (
            <Row
              key={i}
              data={row}
              styleObj={PHASE_STYLES[i]}
              isLast={i === ROWS.length - 1}
            />
          ))}
        </div>

        {/* Legend */}
        <div style={{
          marginTop: 12,
          padding: "8px 12px",
          backgroundColor: "#f8f9fa",
          border: "1px solid #dce3ea",
          borderRadius: 5,
          display: "flex",
          gap: 16,
          flexWrap: "wrap",
          alignItems: "center",
        }}>
          <span style={{ fontSize: 9, fontWeight: 700, color: "#333", marginRight: 4 }}>KEY EQUATIONS:</span>
          {[
            "TWF_indirect = W · L · Y",
            "Scarce_TWF = TWF × WSI_sector",
            "L = (I − A)⁻¹",
            "ΔTWF = ΔW·eff + ΔL·eff + ΔY·eff",
            "MR[j] = WL[j] / WL̄",
          ].map((eq, i) => (
            <span key={i} style={{
              fontSize: 9,
              fontFamily: "monospace",
              fontWeight: 600,
              color: "#1a3a5c",
              backgroundColor: "#e8f0f8",
              padding: "2px 7px",
              borderRadius: 3,
              border: "1px solid #b8ccde",
            }}>{eq}</span>
          ))}
          <span style={{ marginLeft: "auto", fontSize: 8.5, color: "#888", fontStyle: "italic" }}>
            ★ Phase ④ extensions absent in Lee et al. (2021)
          </span>
        </div>
      </div>

      {/* Usage note */}
      <div style={{ marginTop: 10, fontSize: 9.5, color: "#7a8a9a", textAlign: "center" }}>
        Right-click → "Save as image" or use browser print (Ctrl+P → Save as PDF) for journal submission · Recommended: landscape A4
      </div>
    </div>
  );
}
