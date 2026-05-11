/* Congress representation deviation map. */

const TOPO_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3/states-albers-10m.json?v=2";
const DATA_URL = "data/data.json?v=3";

function showError(msg) {
  let banner = document.getElementById("error-banner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "error-banner";
    banner.style.cssText =
      "margin:1rem 1.5rem;padding:0.75rem 1rem;border:1px solid #a00;background:#fff0f0;color:#a00;border-radius:6px;font-size:0.9rem;";
    const main = document.querySelector("main");
    main.insertBefore(banner, main.firstChild);
  }
  banner.textContent = `Map failed to render: ${msg}`;
}

const fmtPct = d3.format(".1%");
const fmtSignedPP = (v) => {
  const pp = v * 100;
  const sign = pp > 0 ? "+" : pp < 0 ? "−" : "";
  return `${sign}${Math.abs(pp).toFixed(1)}%`;
};
const fmtFit = (v) => v.toFixed(3);

const biasColor = d3
  .scaleDiverging(d3.interpolateRdBu)
  .domain([-0.3, 0, 0.3])
  .clamp(true);

const fitColor = d3
  .scaleSequential(d3.interpolateRdYlGn)
  .domain([0.7, 1.0])
  .clamp(true);

// Gallagher index: 0 = perfect, higher = worse. Reverse interpolator so green=low, red=high.
const gallagherColor = d3
  .scaleSequential((t) => d3.interpolateRdYlGn(1 - t))
  .domain([0, 0.3])
  .clamp(true);

const MODES = {
  bias: {
    label: "Party bias",
    color: biasColor,
    domain: [-0.3, 0.3],
    yLabel: "House Dem share − citizen Dem share (pp)",
    legendClass: "",
    legendLabels: ["−30% (more Republican than voters)", "0", "+30% (more Democratic than voters)"],
    fmt: fmtSignedPP,
  },
  abs: {
    label: "Absolute fit",
    color: fitColor,
    domain: [0.7, 1.0],
    yLabel: "Absolute fit  (1 − |seat − vote| share gap)",
    legendClass: "fit-scale",
    legendLabels: ["0.70 (poor)", "0.85", "1.00 (perfect)"],
    fmt: fmtFit,
  },
  gallagher: {
    label: "Gallagher index",
    color: gallagherColor,
    domain: [0, 0.3],
    yLabel: "Gallagher index  (0 = perfect, higher = worse)",
    legendClass: "fit-scale-rev",
    legendLabels: ["0.00 (perfect)", "0.15", "0.30+ (worse)"],
    fmt: fmtFit,
  },
};

function metric(d, mode) {
  if (!d || d.house_dem_share === null) return null;
  if (mode === "bias") return d.deviation;

  // 2-party House Dem vote share, parity with the 2-party house_dem_share.
  const cd2 = d.house_vote_dem / (d.house_vote_dem + d.house_vote_rep);
  if (mode === "abs") return 1 - Math.abs(d.house_dem_share - cd2);

  // Gallagher: 3 categories. Voters: dem/rep/other (sum to 1).
  // House: dem/rep/ind shares of total seats (sum to 1).
  const total = d.house_total || 1;
  const hd = d.house_dem / total;
  const hr = d.house_rep / total;
  const hi = d.house_ind / total;
  const diffs = [
    hd - d.house_vote_dem,
    hr - d.house_vote_rep,
    hi - d.house_vote_other,
  ];
  return Math.sqrt(0.5 * d3.sum(diffs, (x) => x * x));
}

const svg = d3.select("#map");
const tooltip = d3.select("#tooltip");

let pinnedFips = null;
let mode = "bias";
let seatThreshold = 1;
let states = []; // array of state data records
let byFips = {};

Promise.all([d3.json(TOPO_URL), d3.json(DATA_URL)])
  .then(([us, payload]) => {
   try {
    if (typeof topojson === "undefined") {
      throw new Error("topojson library not loaded");
    }
    const data = payload.states;
    states = Object.values(data);
    states.forEach((d) => (byFips[d.fips] = d));

    document.getElementById("generated").textContent =
      `Generated ${payload.generated} · ${payload.congress}th Congress · ${payload.house_election_year} U.S. House vote share`;

    const path = d3.geoPath();
    const geoStates = topojson.feature(us, us.objects.states).features;
    const toFips = (id) => String(id).padStart(2, "0");

    svg
      .selectAll("path.state")
      .data(geoStates)
      .join("path")
      .attr("class", "state")
      .attr("d", path)
      .attr("data-fips", (f) => toFips(f.id))
      .on("mousemove", (event, f) => {
        if (pinnedFips) return;
        showTooltip(event, byFips[toFips(f.id)]);
      })
      .on("mouseleave", () => {
        if (pinnedFips) return;
        hideTooltip();
      })
      .on("click", (event, f) => {
        const d = byFips[toFips(f.id)];
        if (!d) return;
        if (pinnedFips === f.id) {
          clearPin();
        } else {
          pinnedFips = f.id;
          svg.selectAll("path.state").classed("pinned", (ff) => ff.id === f.id);
          d3.selectAll("#scatter circle.dot").classed("pinned", (dd) => dd.fips === d.fips);
          showTooltip(event, d);
        }
        event.stopPropagation();
      });

    // mesh for clean inter-state borders
    svg
      .append("path")
      .datum(topojson.mesh(us, us.objects.states, (a, b) => a !== b))
      .attr("fill", "none")
      .attr("stroke", "#fff")
      .attr("stroke-width", 0.75)
      .attr("stroke-linejoin", "round")
      .attr("d", path)
      .style("pointer-events", "none");

    // click outside any state/dot clears pin
    document.addEventListener("click", () => {
      if (pinnedFips !== null) clearPin();
    });

    wireControls();
    renderNationalBar();
    renderAll();
   } catch (err) {
     console.error(err);
     showError(err.message);
   }
  })
  .catch((err) => {
    console.error(err);
    showError(err.message);
  });

function clearPin() {
  pinnedFips = null;
  svg.selectAll("path.state").classed("pinned", false);
  d3.selectAll("#scatter circle.dot").classed("pinned", false);
  hideTooltip();
}

function renderAll() {
  renderMap();
  renderScatter();
  renderLegend();
}

function renderMap() {
  const cfg = MODES[mode];
  svg.selectAll("path.state")
    .attr("fill", function () {
      const d = byFips[this.getAttribute("data-fips")];
      const v = metric(d, mode);
      if (v === null || v === undefined || Number.isNaN(v)) return "#ddd";
      return cfg.color(v);
    })
    .classed("muted", function () {
      const d = byFips[this.getAttribute("data-fips")];
      return d ? d.house_total < seatThreshold : false;
    });
}

function renderLegend() {
  const cfg = MODES[mode];
  const bar = d3.select(".legend-bar");
  bar.classed("fit-scale", cfg.legendClass === "fit-scale");
  bar.classed("fit-scale-rev", cfg.legendClass === "fit-scale-rev");
  const labels = d3.select(".legend-labels").selectAll("span").nodes();
  if (labels.length === 3) {
    labels[0].textContent = cfg.legendLabels[0];
    labels[1].textContent = cfg.legendLabels[1];
    labels[2].textContent = cfg.legendLabels[2];
  }
}

function renderScatter() {
  const cfg = MODES[mode];
  const root = d3.select("#scatter");
  root.selectAll("*").remove();

  const W = 700, H = 380;
  const margin = { top: 20, right: 20, bottom: 50, left: 60 };
  const innerW = W - margin.left - margin.right;
  const innerH = H - margin.top - margin.bottom;

  const g = root.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

  const maxSeats = d3.max(states, (s) => s.house_total) || 52;
  const x = d3.scaleLinear().domain([0, maxSeats]).nice().range([0, innerW]);

  // Data-driven y domain so dots aren't clipped by the map's color-scale clamp.
  const vals = states.map((s) => metric(s, mode)).filter((v) => v !== null && !Number.isNaN(v));
  let yDomain;
  if (mode === "bias") {
    const m = Math.max(Math.abs(d3.min(vals)), Math.abs(d3.max(vals)), 0.05);
    const pad = m * 0.1;
    yDomain = [-m - pad, m + pad];
  } else if (mode === "gallagher") {
    const hi = d3.max(vals);
    const pad = Math.max(hi * 0.08, 0.02);
    yDomain = [0, hi + pad];
  } else {
    const lo = d3.min(vals);
    const pad = Math.max((1 - lo) * 0.08, 0.02);
    yDomain = [Math.max(0, lo - pad), 1 + pad * 0.4];
  }
  const y = d3.scaleLinear().domain(yDomain).nice().range([innerH, 0]);

  // axes
  g.append("g")
    .attr("class", "axis")
    .attr("transform", `translate(0,${innerH})`)
    .call(d3.axisBottom(x).ticks(8));
  g.append("g")
    .attr("class", "axis")
    .call(d3.axisLeft(y).ticks(6).tickFormat(mode === "bias" ? (v) => `${(v*100).toFixed(0)}pp` : d3.format(".2f")));

  // axis labels
  g.append("text")
    .attr("class", "axis-label")
    .attr("x", innerW / 2)
    .attr("y", innerH + 38)
    .attr("text-anchor", "middle")
    .text("House delegation size (seats)");
  g.append("text")
    .attr("class", "axis-label")
    .attr("transform", "rotate(-90)")
    .attr("x", -innerH / 2)
    .attr("y", -45)
    .attr("text-anchor", "middle")
    .text(cfg.yLabel);

  // zero / target reference line: bias=0, abs=1 (perfect), gallagher=0 (perfect)
  const refY = mode === "abs" ? 1 : 0;
  g.append("line")
    .attr("x1", 0).attr("x2", innerW)
    .attr("y1", y(refY)).attr("y2", y(refY))
    .attr("stroke", "#aaa").attr("stroke-dasharray", "2,3");

  // dots
  const plottable = states.filter((d) => metric(d, mode) !== null);
  g.selectAll("circle.dot")
    .data(plottable, (d) => d.fips)
    .join("circle")
    .attr("class", "dot")
    .classed("muted", (d) => d.house_total < seatThreshold)
    .classed("pinned", (d) => pinnedFips && byFips[pinnedFips.toString().padStart(2, "0")] && d.fips === byFips[pinnedFips.toString().padStart(2, "0")].fips)
    .attr("cx", (d) => x(d.house_total))
    .attr("cy", (d) => y(metric(d, mode)))
    .attr("r", 5)
    .attr("fill", (d) => cfg.color(metric(d, mode)))
    .on("mousemove", (event, d) => {
      if (pinnedFips) return;
      showTooltip(event, d);
    })
    .on("mouseleave", () => {
      if (pinnedFips) return;
      hideTooltip();
    })
    .on("click", (event, d) => {
      const fipsNum = +d.fips;
      if (pinnedFips === fipsNum) {
        clearPin();
      } else {
        pinnedFips = fipsNum;
        svg.selectAll("path.state").classed("pinned", function () {
          return this.getAttribute("data-fips") === d.fips;
        });
        d3.selectAll("#scatter circle.dot").classed("pinned", (dd) => dd.fips === d.fips);
        showTooltip(event, d);
      }
      event.stopPropagation();
    });
}

function renderNationalBar() {
  const root = d3.select("#national-bar");
  root.selectAll("*").remove();

  const W = 600, H = 90;
  const margin = { top: 8, right: 12, bottom: 8, left: 90 };
  const barH = 26;
  const gap = 10;
  const innerW = W - margin.left - margin.right;

  const totals = states.reduce(
    (acc, s) => {
      acc.dem_v += s.house_vote_dem_votes || 0;
      acc.rep_v += s.house_vote_rep_votes || 0;
      acc.oth_v += s.house_vote_other_votes || 0;
      acc.dem_s += s.house_dem || 0;
      acc.rep_s += s.house_rep || 0;
      acc.ind_s += s.house_ind || 0;
      return acc;
    },
    { dem_v: 0, rep_v: 0, oth_v: 0, dem_s: 0, rep_s: 0, ind_s: 0 }
  );

  const totalV = totals.dem_v + totals.rep_v + totals.oth_v;
  const totalS = totals.dem_s + totals.rep_s + totals.ind_s;

  const rows = [
    {
      label: "House vote",
      segs: [
        { share: totals.dem_v / totalV, color: "var(--dem)", letter: "D" },
        { share: totals.rep_v / totalV, color: "var(--rep)", letter: "R" },
        { share: totals.oth_v / totalV, color: "var(--ind)", letter: "O" },
      ],
    },
    {
      label: "House seats",
      segs: [
        { share: totals.dem_s / totalS, color: "var(--dem)", letter: "D" },
        { share: totals.rep_s / totalS, color: "var(--rep)", letter: "R" },
        { share: totals.ind_s / totalS, color: "var(--ind)", letter: "I" },
      ],
    },
  ];

  const g = root.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

  rows.forEach((row, i) => {
    const yTop = i * (barH + gap);
    g.append("text")
      .attr("class", "label")
      .attr("x", -8)
      .attr("y", yTop + barH / 2)
      .attr("text-anchor", "end")
      .attr("dominant-baseline", "central")
      .text(row.label);

    let xCursor = 0;
    row.segs.forEach((seg) => {
      const w = seg.share * innerW;
      if (w <= 0) return;
      g.append("rect")
        .attr("x", xCursor)
        .attr("y", yTop)
        .attr("width", w)
        .attr("height", barH)
        .attr("fill", seg.color);
      if (w > 32) {
        g.append("text")
          .attr("x", xCursor + w / 2)
          .attr("y", yTop + barH / 2)
          .attr("text-anchor", "middle")
          .attr("dominant-baseline", "central")
          .text(`${seg.letter} ${fmtPct(seg.share)}`);
      }
      xCursor += w;
    });
  });
}

function wireControls() {
  d3.selectAll(".mode-btn").on("click", function () {
    const m = this.getAttribute("data-mode");
    if (!MODES[m] || m === mode) return;
    mode = m;
    d3.selectAll(".mode-btn").classed("is-active", function () {
      return this.getAttribute("data-mode") === mode;
    });
    if (pinnedFips !== null) clearPin();
    renderAll();
  });

  // Threshold values that actually change the picture: each distinct seat count
  // present in the data (so dragging from 35 -> 36 with no 35-seat state is a no-op).
  // Append max+1 so the user can fade every state.
  const seatCounts = Array.from(new Set(states.map((s) => s.house_total))).sort((a, b) => a - b);
  const breakpoints = [...seatCounts, seatCounts[seatCounts.length - 1] + 1];

  const slider = document.getElementById("seats-slider");
  const numberInput = document.getElementById("seats-number");

  slider.min = 0;
  slider.max = breakpoints.length - 1;
  slider.step = 1;
  slider.value = 0;
  numberInput.min = 1;
  numberInput.max = breakpoints[breakpoints.length - 1];

  function applyThreshold() {
    svg.selectAll("path.state").classed("muted", function () {
      const d = byFips[this.getAttribute("data-fips")];
      return d ? d.house_total < seatThreshold : false;
    });
    renderScatter();
  }

  function setThreshold(v, source) {
    seatThreshold = v;
    if (source !== "slider") {
      // Snap slider to nearest breakpoint at or below v.
      let idx = 0;
      for (let i = 0; i < breakpoints.length; i++) {
        if (breakpoints[i] <= v) idx = i;
      }
      slider.value = idx;
    }
    if (source !== "number") numberInput.value = v;
    applyThreshold();
  }

  slider.addEventListener("input", () => {
    const idx = +slider.value;
    setThreshold(breakpoints[idx], "slider");
  });
  numberInput.addEventListener("input", () => {
    const raw = +numberInput.value;
    if (!Number.isFinite(raw)) return;
    const clamped = Math.max(1, Math.min(breakpoints[breakpoints.length - 1], Math.round(raw)));
    setThreshold(clamped, "number");
  });
}

function showTooltip(event, d) {
  if (!d) return;
  const cfg = MODES[mode];
  const v = metric(d, mode);
  const devClass = mode === "bias"
    ? (v > 0 ? "dev-pos" : v < 0 ? "dev-neg" : "")
    : "";

  const note =
    d.house_total <= 2
      ? `<div class="note">Only ${d.house_total} House seat${d.house_total === 1 ? "" : "s"} — fit is coarse.</div>`
      : "";
  const indNote =
    d.house_ind > 0
      ? `<div class="note">${d.house_ind} independent / unaffiliated seat${d.house_ind === 1 ? "" : "s"}.</div>`
      : "";
  const expectedSeats = {
    AL:7,AK:1,AZ:9,AR:4,CA:52,CO:8,CT:5,DE:1,FL:28,GA:14,HI:2,ID:2,IL:17,IN:9,
    IA:4,KS:4,KY:6,LA:6,ME:2,MD:8,MA:9,MI:13,MN:8,MS:4,MO:8,MT:2,NE:3,NV:4,
    NH:2,NJ:12,NM:3,NY:26,NC:14,ND:1,OH:15,OK:5,OR:6,PA:17,RI:2,SC:7,SD:1,
    TN:9,TX:38,UT:4,VT:1,VA:11,WA:10,WV:2,WI:8,WY:1,
  };
  const usps = Object.keys(expectedSeats).find((k) => d.fips === FIPS[k]);
  const expected = usps ? expectedSeats[usps] : null;
  const vacant = expected ? expected - d.house_total : 0;
  const vacantNote =
    vacant > 0
      ? `<div class="note">${vacant} vacant seat${vacant === 1 ? "" : "s"} (not counted).</div>`
      : "";

  const otherStr = d.house_vote_other > 0.005
    ? ` / ${fmtPct(d.house_vote_other)} O`
    : "";

  const metricRow = v === null
    ? `<div class="row"><span>${cfg.label}:</span><span>n/a</span></div>`
    : `<div class="row"><span>${cfg.label}:</span><span class="${devClass}">${cfg.fmt(v)}</span></div>`;

  tooltip
    .classed("hidden", false)
    .html(`
      <div class="ttl">${d.name}</div>
      <div class="row"><span>Voters (2024 House):</span><span>${fmtPct(d.house_vote_dem)} D / ${fmtPct(d.house_vote_rep)} R${otherStr}</span></div>
      <div class="row"><span>House delegation:</span><span>${d.house_dem} D / ${d.house_rep} R${d.house_ind ? ` / ${d.house_ind} I` : ""} (${d.house_total})</span></div>
      <div class="row"><span>House share:</span><span>${d.house_dem_share !== null ? fmtPct(d.house_dem_share) + " D / " + fmtPct(d.house_rep_share) + " R" : "n/a"}</span></div>
      <div class="sep"></div>
      ${metricRow}
      ${note}${indNote}${vacantNote}
    `);

  positionTooltip(event);
}

function positionTooltip(event) {
  const pad = 14;
  const node = tooltip.node();
  const w = node.offsetWidth;
  const h = node.offsetHeight;
  let x = event.clientX + pad;
  let y = event.clientY + pad;
  if (x + w > window.innerWidth - 8) x = event.clientX - w - pad;
  if (y + h > window.innerHeight - 8) y = event.clientY - h - pad;
  tooltip.style("left", `${x}px`).style("top", `${y}px`);
}

function hideTooltip() {
  tooltip.classed("hidden", true);
}

const FIPS = {
  AL:"01",AK:"02",AZ:"04",AR:"05",CA:"06",CO:"08",CT:"09",DE:"10",DC:"11",
  FL:"12",GA:"13",HI:"15",ID:"16",IL:"17",IN:"18",IA:"19",KS:"20",KY:"21",
  LA:"22",ME:"23",MD:"24",MA:"25",MI:"26",MN:"27",MS:"28",MO:"29",MT:"30",
  NE:"31",NV:"32",NH:"33",NJ:"34",NM:"35",NY:"36",NC:"37",ND:"38",OH:"39",
  OK:"40",OR:"41",PA:"42",RI:"44",SC:"45",SD:"46",TN:"47",TX:"48",UT:"49",
  VT:"50",VA:"51",WA:"53",WV:"54",WI:"55",WY:"56",
};
