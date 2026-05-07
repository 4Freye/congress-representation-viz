/* Congress representation deviation map. */

const TOPO_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json?v=2";
const DATA_URL = "data/data.json?v=2";

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
  return `${sign}${Math.abs(pp).toFixed(1)} pp`;
};

const colorScale = d3
  .scaleDiverging(d3.interpolateRdBu)
  .domain([-0.3, 0, 0.3])
  .clamp(true);

const svg = d3.select("#map");
const tooltip = d3.select("#tooltip");

let pinnedFips = null;

Promise.all([d3.json(TOPO_URL), d3.json(DATA_URL)])
  .then(([us, payload]) => {
   try {
    if (typeof topojson === "undefined") {
      throw new Error("topojson library not loaded");
    }
    const data = payload.states;
    const byFips = {};
    Object.values(data).forEach((d) => (byFips[d.fips] = d));

    document.getElementById("generated").textContent =
      `Generated ${payload.generated} · ${payload.congress}th Congress · ${payload.presidential_year} presidential vote share`;

    const path = d3.geoPath();
    const states = topojson.feature(us, us.objects.states).features;
    const toFips = (id) => String(id).padStart(2, "0");

    svg
      .selectAll("path.state")
      .data(states)
      .join("path")
      .attr("class", "state")
      .attr("d", path)
      .attr("fill", (f) => {
        const d = byFips[toFips(f.id)];
        if (!d || d.deviation === null) return "#ddd";
        return colorScale(d.deviation);
      })
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
          pinnedFips = null;
          svg.selectAll("path.state").classed("pinned", false);
          hideTooltip();
        } else {
          pinnedFips = f.id;
          svg.selectAll("path.state").classed("pinned", (ff) => ff.id === f.id);
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

    // click outside any state clears pin
    document.addEventListener("click", () => {
      if (pinnedFips !== null) {
        pinnedFips = null;
        svg.selectAll("path.state").classed("pinned", false);
        hideTooltip();
      }
    });
   } catch (err) {
     console.error(err);
     showError(err.message);
   }
  })
  .catch((err) => {
    console.error(err);
    showError(err.message);
  });

function showTooltip(event, d) {
  if (!d) return;
  const devClass = d.deviation > 0 ? "dev-pos" : d.deviation < 0 ? "dev-neg" : "";
  const note =
    d.house_total <= 2
      ? `<div class="note">Only ${d.house_total} House seat${d.house_total === 1 ? "" : "s"} — deviation is coarse.</div>`
      : "";
  const indNote =
    d.house_ind > 0
      ? `<div class="note">${d.house_ind} independent / unaffiliated seat${d.house_ind === 1 ? "" : "s"} excluded from share.</div>`
      : "";
  const expectedSeats = {
    AL:7,AK:1,AZ:9,AR:4,CA:52,CO:8,CT:5,DE:1,FL:28,GA:14,HI:2,ID:2,IL:17,IN:9,
    IA:4,KS:4,KY:6,LA:6,ME:2,MD:8,MA:9,MI:13,MN:8,MS:4,MO:8,MT:2,NE:3,NV:4,
    NH:2,NJ:12,NM:3,NY:26,NC:14,ND:1,OH:15,OK:5,OR:6,PA:17,RI:2,SC:7,SD:1,
    TN:9,TX:38,UT:4,VT:1,VA:11,WA:10,WV:2,WI:8,WY:1,
  };
  const usps = Object.keys(expectedSeats).find(
    (k) => d.name && expectedSeats[k] !== undefined && d.fips === fipsFor(k)
  );
  const expected = usps ? expectedSeats[usps] : null;
  const vacant = expected ? expected - d.house_total : 0;
  const vacantNote =
    vacant > 0
      ? `<div class="note">${vacant} vacant seat${vacant === 1 ? "" : "s"} (not counted).</div>`
      : "";

  tooltip
    .classed("hidden", false)
    .html(`
      <div class="ttl">${d.name}</div>
      <div class="row"><span>Voters (2024 pres):</span><span>${fmtPct(d.citizen_dem)} D / ${fmtPct(d.citizen_rep)} R</span></div>
      <div class="row"><span>House delegation:</span><span>${d.house_dem} D / ${d.house_rep} R${d.house_ind ? ` / ${d.house_ind} I` : ""}</span></div>
      <div class="row"><span>House share:</span><span>${d.house_dem_share !== null ? fmtPct(d.house_dem_share) + " D / " + fmtPct(d.house_rep_share) + " R" : "n/a"}</span></div>
      <div class="sep"></div>
      <div class="row"><span>Deviation:</span><span class="${devClass}">${d.deviation !== null ? fmtSignedPP(d.deviation) : "n/a"}</span></div>
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
function fipsFor(usps) { return FIPS[usps]; }
