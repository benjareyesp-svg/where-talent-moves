from pathlib import Path

import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md("""
# Where talent moves: net talent migration in developing economies

**Benjamin Reyes** · Data: World Bank Group × LinkedIn *Digital Data for Development: Talent Migration* (public use file)

Job openings and employment trends show where labour demand is going. This notebook adds the layer underneath: **worker reallocation across borders**. Which developing economies are losing LinkedIn talent, which skills and industries leave fastest, and where those workers go.

Scope: developing economies (World Bank low, lower middle and upper middle income) across LatAm, South Asia, East Asia & Pacific, Sub-Saharan Africa, MENA and Europe & Central Asia, with high-income economies as the reference group.

**Data vintage:** the dataset page lists a 2024 release, but the published public use file covers **2015 to 2019** (columns `net_per_10K_2015` … `net_per_10K_2019`). The catalog's blob storage link returns `AuthorizationFailure`; the same file is served at `datacatalogfiles.worldbank.org/ddh-published/0038044/3/DR0046256/…` (versions 1, 2 and 3 are byte identical). Everything below is pre-pandemic.
""")

md("## 0. Setup")
code("""
from pathlib import Path
from math import comb
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)
pd.set_option("display.float_format", "{:,.1f}".format)
pio.renderers.default = "plotly_mimetype+notebook_connected"

DATA = Path("data/public_use-talent-migration.xlsx")
OUT = Path("outputs"); OUT.mkdir(exist_ok=True)
SOURCE_URL = "https://datacatalogfiles.worldbank.org/ddh-published/0038044/3/DR0046256/public_use-talent-migration.xlsx"

if not DATA.exists():
    import urllib.request
    DATA.parent.mkdir(exist_ok=True)
    urllib.request.urlretrieve(SOURCE_URL, DATA)

YEARS = list(range(2015, 2020))
YCOLS = [f"net_per_10K_{y}" for y in YEARS]
""")

code("""
# Chart tokens (validated reference palette: blue/red diverging, gray neutral)
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
GAIN, LOSS, NEUTRAL = "#2a78d6", "#e34948", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # fixed categorical order
INCOME_ORDER = ["High income", "Upper middle income", "Lower middle income", "Low income"]
INCOME_COLOR = dict(zip(INCOME_ORDER, SERIES))

pio.templates["talent"] = go.layout.Template(layout=dict(
    font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", size=13, color=INK2),
    title=dict(font=dict(size=17, color=INK), x=0, xanchor="left"),
    paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
    xaxis=dict(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS, tickfont=dict(color=MUTED)),
    yaxis=dict(gridcolor=GRID, linecolor=AXIS, zerolinecolor=AXIS, zerolinewidth=1.5, tickfont=dict(color=MUTED)),
    legend=dict(orientation="h", y=-0.18, x=0, font=dict(color=INK2)),
    hoverlabel=dict(bgcolor="white", font=dict(color=INK, size=12), bordercolor=GRID),
    margin=dict(l=60, r=30, t=80, b=70),
))
pio.templates.default = "talent"

def save(fig, name):
    fig.write_html(OUT / f"{name}.html", include_plotlyjs="cdn")
    return fig
""")

md("""
## 1. What is in the file

Six sheets: `Cover`, `Notes`, `Variable List` (documentation) and three data sheets.

| Sheet | Grain | Rows | Metric |
|---|---|---|---|
| Country Migration | base country × partner country × year | 4,148 | net flow with that partner ÷ base country LinkedIn members × 10,000 |
| Industry Migration | country × LinkedIn industry (≈ ISIC 2-digit) × year | 5,295 | net flow in that industry ÷ country's members in that industry × 10,000 |
| Skill Migration | country × skill group × year | 17,617 | net flow of members holding that skill ÷ country's members with that skill × 10,000 |

Definitions that matter for the analysis (from the Cover and Notes text boxes):
- **Net** = arrivals minus departures. Negative means the country loses talent.
- Migration is detected when a member's **job location changes country**.
- Each year is reported as **an average of the last three years**, so the series is smoothed.
- Privacy threshold: **a flow only appears with at least 50 observations**. Blank pairs are dropped, so small corridors are missing.
- Countries need **100,000+ LinkedIn members**.
- LinkedIn over-represents white-collar workers in knowledge-intensive services.
""")

code("""
xl = pd.ExcelFile(DATA)
print(xl.sheet_names)
country = xl.parse("Country Migration")
industry = xl.parse("Industry Migration")
skill = xl.parse("Skill Migration")

# The country sheet capitalises income groups differently ("High Income" vs "High income"); harmonise
for col in ["base_country_wb_income", "target_country_wb_income"]:
    country[col] = country[col].str.capitalize()

for name, df in [("country", country), ("industry", industry), ("skill", skill)]:
    print(f"{name:9s} {df.shape}  missing values in year columns: {int(df[YCOLS].isna().sum().sum())}")
""")

code("""
print("Base countries:", country.base_country_code.nunique())
print("Industries:", industry.industry_name.nunique(), "| ISIC sections:", industry.isic_section_name.nunique())
print("Skill groups:", skill.skill_group_name.nunique())
print(skill.skill_group_category.value_counts().to_string())
print("\\nDisruptive tech skill groups:", sorted(skill.loc[skill.skill_group_category == "Disruptive Tech Skills", "skill_group_name"].unique()))
""")

md("""
## 2. Net talent flows by country

The bilateral rows for one base country share the same denominator (that country's members), so **summing across partners gives the country's total net migration per 10,000 members**. Because corridors under 50 observations are suppressed, the total is a lower bound on gross activity, but small corridors contribute little to the net.
""")

code("""
totals = (country
          .groupby(["base_country_code", "base_country_name", "base_country_wb_income", "base_country_wb_region"])[YCOLS]
          .sum().reset_index()
          .rename(columns={"base_country_code": "code", "base_country_name": "country",
                           "base_country_wb_income": "income", "base_country_wb_region": "region"}))
totals["developing"] = totals.income != "High income"
print(totals.income.value_counts().to_string())
""")

code("""
by_income = totals.groupby("income")[YCOLS].median().reindex(INCOME_ORDER)
by_income.columns = YEARS
share_neg = totals.groupby("developing")[YCOLS].agg(lambda v: (v < 0).mean())
share_neg.columns = YEARS
share_neg.index = share_neg.index.map({True: "Developing", False: "High income"})
display(by_income.round(1))
display((share_neg * 100).round(0).astype(int).astype(str) + "%")
""")

code("""
fig = go.Figure()
for inc in INCOME_ORDER:
    y = by_income.loc[inc]
    fig.add_trace(go.Scatter(x=YEARS, y=y, name=inc, mode="lines+markers",
                             line=dict(color=INCOME_COLOR[inc], width=2), marker=dict(size=8),
                             hovertemplate=f"<b>{inc}</b><br>%{{x}}: %{{y:.1f}} per 10k members<extra></extra>"))
    nudge = {"Lower middle income": 7, "Upper middle income": -7}.get(inc, 0)
    fig.add_annotation(x=2019, y=y.iloc[-1], text=inc, showarrow=False, xanchor="left", xshift=10, yshift=nudge,
                       font=dict(color=INK2, size=12))
fig.add_hline(y=0, line_color=AXIS)
fig.update_layout(title="The great divergence: median net talent migration by income group<br>"
                        "<sup>Net LinkedIn arrivals minus departures per 10,000 members, median country</sup>",
                  xaxis=dict(tickvals=YEARS, range=[2014.7, 2020.3]), yaxis_title="net per 10,000 members",
                  hovermode="x unified", height=480)
save(fig, "01_divergence")
""")

md("""
**Reading:** in 2015 the median country in every income group was a small net gainer. By 2019 the median high-income country gained about 11 per 10,000 members while the median upper and lower middle income countries lost about 12. The share of developing economies that are net losers went from about 4 in 10 to about 7 in 10.
""")

code("""
regional = (totals[totals.developing]
            .groupby("region")
            .agg(countries=("code", "size"),
                 median_2015=("net_per_10K_2015", "median"),
                 median_2019=("net_per_10K_2019", "median"),
                 share_losing_2019=("net_per_10K_2019", lambda v: (v < 0).mean() * 100))
            .sort_values("median_2019"))
regional
""")

code("""
import pycountry
totals["iso3"] = totals.code.str.upper().map(lambda c: getattr(pycountry.countries.get(alpha_2=c), "alpha_3", None))
print("unmapped:", totals.loc[totals.iso3.isna(), "country"].tolist())
fig = px.choropleth(totals, locations="iso3",
                    color="net_per_10K_2019", hover_name="country",
                    hover_data={"country": False, "income": True, "net_per_10K_2019": ":.1f"},
                    color_continuous_scale=[[0, LOSS], [0.5, "#f0efec"], [1, GAIN]],
                    range_color=[-60, 60], labels={"net_per_10K_2019": "net per 10k"})
fig.update_geos(showframe=False, showcoastlines=False, projection_type="natural earth", bgcolor=SURFACE,
                showcountries=True, countrycolor="white", landcolor="#ebeae6")
fig.update_layout(title="Net talent migration, 2019<br><sup>Per 10,000 LinkedIn members; scale clipped at ±60 "
                        "(Venezuela −132, Luxembourg +221)</sup>", height=480, margin=dict(l=0, r=0, t=80, b=0))
save(fig, "02_map")
""")

code("""
cols = ["country", "income", "region", "net_per_10K_2015", "net_per_10K_2019"]
print("Largest developing-economy losses, 2019")
display(totals[totals.developing].nsmallest(15, "net_per_10K_2019")[cols])
print("Developing economies that gained talent, 2019")
display(totals[totals.developing].nlargest(10, "net_per_10K_2019")[cols])
""")

md("""
## 3. Which skills leave: is tech, data and AI talent draining faster?

**Comparability caveat.** Skill rates are normalised by the members *holding that skill*, so they are an order of magnitude larger than the country totals above and should not be compared to them directly. The valid comparison is **within a country, across skill groups**: does tech talent leave at a higher rate than non-tech talent from the same country?

Tech = LinkedIn's *Tech Skills* and *Disruptive Tech Skills* categories (the latter includes AI, Data Science, Robotics, FinTech).
""")

code("""
skill["income"] = skill.wb_income
skill["developing"] = skill.income != "High income"
skill["family"] = np.select(
    [skill.skill_group_category == "Disruptive Tech Skills", skill.skill_group_category == "Tech Skills"],
    ["Disruptive tech", "Tech"], "Non-tech")
skill["is_tech"] = skill.family != "Non-tech"

def sign_test_p(k, n):
    # two-sided exact binomial test against p = 0.5
    tail = sum(comb(n, i) for i in range(min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * tail)

pair = (skill.groupby(["country_code", "country_name", "income", "developing", "is_tech"])
        .net_per_10K_2019.median().unstack().dropna()
        .rename(columns={False: "non_tech", True: "tech"}).reset_index())
pair["gap"] = pair.tech - pair.non_tech

for dev, d in pair.groupby("developing"):
    k, n = int((d.tech < d.non_tech).sum()), len(d)
    label = "Developing" if dev else "High income"
    print(f"{label:12s} n={n:3d}  median non-tech {d.non_tech.median():7.1f}  median tech {d.tech.median():7.1f}  "
          f"tech more negative in {k}/{n} = {k/n:.0%}  (sign test p = {sign_test_p(k, n):.2g})")
""")

code("""
fig = go.Figure()
lim = 650
fig.add_shape(type="line", x0=-lim, y0=-lim, x1=lim, y1=lim, line=dict(color=AXIS, dash="dot"))
for dev, color, label in [(False, SERIES[1], "High income"), (True, SERIES[0], "Developing")]:
    d = pair[pair.developing == dev]
    fig.add_trace(go.Scatter(x=d.non_tech, y=d.tech, mode="markers", name=label, text=d.country_name,
                             marker=dict(color=color, size=9, opacity=0.85, line=dict(color="white", width=1)),
                             hovertemplate="<b>%{text}</b><br>non-tech %{x:.0f} · tech %{y:.0f}<extra></extra>"))
fig.add_annotation(x=-480, y=-560, text="below the line: tech talent<br>leaves faster", showarrow=False,
                   font=dict(color=INK2, size=12), align="left")
fig.add_annotation(x=420, y=560, text="above the line: tech talent<br>arrives faster", showarrow=False,
                   font=dict(color=INK2, size=12), align="right")
fig.update_layout(title="Tech skills amplify the flow in both directions<br><sup>Median net migration per 10,000 "
                        "skill holders, 2019, one dot per country</sup>",
                  xaxis=dict(title="non-tech skill groups", range=[-lim, lim], zeroline=True),
                  yaxis=dict(title="tech skill groups", range=[-lim, lim], zeroline=True),
                  height=600)
save(fig, "03_tech_vs_nontech")
""")

md("""
**Reading:** dots sit on a line steeper than 45°. Countries that lose talent lose their tech talent faster; countries that gain talent gain tech talent faster. Tech skills act as an amplifier of whatever reallocation is already happening, which is exactly the sorting-of-workers-across-locations story.
""")

code("""
fam = (skill.groupby(["developing", "country_code", "family"]).net_per_10K_2019.median()
       .unstack().groupby("developing").median().T)
fam.columns = ["High income", "Developing"]
fam
""")

md("""
### AI specifically

AI skills only clear the 50-observation threshold in 25 developing countries (and 36 high-income ones), so a cross-country median would mix different country sets. Below, each country's AI rate is compared against **its own** non-tech median.
""")

code("""
FOCUS = ["Artificial Intelligence (AI)", "Data Science", "Robotics", "Data Storage Technologies",
         "Web Development", "Software Testing", "Mobile Application Development", "FinTech"]
nontech_med = skill[~skill.is_tech].groupby("country_code").net_per_10K_2019.median().rename("non_tech")
focus = skill[skill.skill_group_name.isin(FOCUS)].join(nontech_med, on="country_code")
focus["multiple"] = focus.net_per_10K_2019 / focus.non_tech

rows = []
for (grp, dev), d in focus.groupby(["skill_group_name", "developing"]):
    losers = d[d.non_tech < 0]
    rows.append(dict(skill_group=grp, group="Developing" if dev else "High income", countries=len(d),
                     median_rate=d.net_per_10K_2019.median(),
                     pct_faster_than_nontech=(d.net_per_10K_2019 < d.non_tech).mean() * 100,
                     median_multiple_in_losing_countries=losers.multiple.median()))
ai_table = pd.DataFrame(rows).sort_values(["group", "median_rate"])
ai_table
""")

code("""
dev_rows = ai_table[ai_table.group == "Developing"].set_index("skill_group")
hi_rows = ai_table[ai_table.group == "High income"].set_index("skill_group")
order = dev_rows.sort_values("median_rate", ascending=False).index
nt = fam.loc["Non-tech"]

fig = go.Figure()
for label, src, color in [("High income", hi_rows, SERIES[1]), ("Developing", dev_rows, SERIES[0])]:
    fig.add_trace(go.Bar(y=list(order) + ["All non-tech skills"], x=list(src.reindex(order).median_rate) + [nt[label]],
                         name=label, orientation="h", marker=dict(color=color, cornerradius=4),
                         customdata=list(src.reindex(order).countries) + [None],
                         hovertemplate="<b>%{y}</b><br>" + label + ": %{x:.0f} per 10k<br>countries: %{customdata}<extra></extra>"))
fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08, height=560,
                  title="AI talent leaves developing economies fastest<br><sup>Median net migration per 10,000 "
                        "skill holders, 2019</sup>",
                  xaxis_title="net per 10,000 skill holders", margin=dict(l=210))
save(fig, "04_ai_skills")
""")

md("""
**Robustness: is this a selection artefact?** Skill groups only appear above 50 observations, which favours large flows. Restricting to a balanced set of skill groups present in at least 80% of developing countries keeps the comparison on the same skills everywhere.
""")

code("""
dev_skill = skill[skill.developing]
n_dev = dev_skill.country_code.nunique()
coverage = dev_skill.groupby("skill_group_name").country_code.nunique() / n_dev
common = coverage[coverage >= 0.8].index
bal = (dev_skill[dev_skill.skill_group_name.isin(common)]
       .groupby(["country_code", "is_tech"]).net_per_10K_2019.median().unstack().dropna())
k, n = int((bal[True] < bal[False]).sum()), len(bal)
print(f"{len(common)} common skill groups ({dev_skill[dev_skill.skill_group_name.isin(common)].drop_duplicates('skill_group_name').is_tech.sum()} tech)")
print(f"Tech more negative than non-tech in {k}/{n} developing countries ({k/n:.0%}), sign test p = {sign_test_p(k, n):.2g}")
""")

md("""
## 4. Which industries bleed

Industry rates are normalised by members in that industry within the country, so again the clean comparison is across industries for the same set of countries. Detailed LinkedIn industries are rolled up to ISIC Rev. 4 sections by taking the median across industries within each country, then the median across developing countries.
""")

code("""
industry["developing"] = industry.wb_income != "High income"
sec = (industry.groupby(["developing", "country_code", "isic_section_name"]).net_per_10K_2019.median()
       .reset_index())
sec_summary = (sec.groupby(["isic_section_name", "developing"])
               .agg(median=("net_per_10K_2019", "median"), countries=("country_code", "nunique"))
               .unstack())
sec_summary.columns = [f"{a}_{'dev' if b else 'high'}" for a, b in sec_summary.columns]
sec_summary = sec_summary[sec_summary.countries_dev >= 20].sort_values("median_dev")
sec_summary
""")

code("""
SHORT = {"Public administration and defence; compulsory social security": "Public administration & defence",
         "Wholesale and retail trade; repair of motor vehicles and motorcycles": "Wholesale & retail trade",
         "Professional scientific and technical activities": "Professional & technical services",
         "Human health and social work activities": "Health & social work",
         "Administrative and support service activities": "Administrative & support services",
         "Accommodation and food service activities": "Accommodation & food"}
d = sec_summary.reset_index().sort_values("median_dev", ascending=False)
d["isic_section_name"] = d.isic_section_name.replace(SHORT)
fig = go.Figure(go.Bar(
    y=d.isic_section_name, x=d.median_dev, orientation="h",
    marker=dict(color=np.where(d.median_dev < 0, LOSS, GAIN), cornerradius=4),
    customdata=np.stack([d.countries_dev, d.median_high], axis=1),
    hovertemplate="<b>%{y}</b><br>developing median: %{x:.0f} per 10k<br>countries: %{customdata[0]}"
                  "<br>high-income median: %{customdata[1]:.0f}<extra></extra>"))
fig.update_layout(title="Which industries lose talent in developing economies<br><sup>Median net migration per "
                        "10,000 industry members, 2019, ISIC Rev. 4 sections in 20+ developing countries</sup>",
                  xaxis_title="net per 10,000 industry members", height=600, margin=dict(l=240), showlegend=False)
save(fig, "05_industries")
""")

code("""
top_ind = (industry[industry.developing]
           .groupby(["industry_name", "isic_section_name"])
           .agg(median_2019=("net_per_10K_2019", "median"), countries=("country_code", "nunique"))
           .query("countries >= 25").sort_values("median_2019"))
print("Detailed industries losing talent fastest (present in 25+ developing countries)")
display(top_ind.head(12))
print("Detailed industries losing talent slowest / gaining")
display(top_ind.tail(8))
""")

md("""
## 5. Where they go

For each developing base country, take partners with a **negative** bilateral net flow (the country loses talent to them) and compute each destination's share of the country's total net loss. Absolute member counts are not published, so destinations are ranked by the **average share across countries** (each country weighted equally) and by how often a destination is a country's **#1** sink. This answers "which destinations dominate the typical developing country's outflow", not "which destination receives the most people".
""")

code("""
dev_out = country[(country.base_country_wb_income != "High income") & (country.net_per_10K_2019 < 0)].copy()
dev_out["loss"] = -dev_out.net_per_10K_2019
dev_out["share"] = dev_out.loss / dev_out.groupby("base_country_code").loss.transform("sum")
n_base = dev_out.base_country_code.nunique()

top1 = dev_out.loc[dev_out.groupby("base_country_code").loss.idxmax(), "target_country_name"].value_counts()
dest = (dev_out.groupby(["target_country_name", "target_country_wb_income"])
        .agg(avg_share=("share", lambda v: v.sum() / n_base * 100), senders=("base_country_code", "nunique"))
        .reset_index().assign(top1=lambda d: d.target_country_name.map(top1).fillna(0).astype(int))
        .sort_values("avg_share", ascending=False))
print(f"{n_base} developing countries with net outflows to at least one partner")
dest.head(15)
""")

code("""
d = dest.head(12).iloc[::-1]
fig = go.Figure(go.Bar(
    y=d.target_country_name, x=d.avg_share, orientation="h",
    marker=dict(color=np.where(d.target_country_wb_income == "High income", SERIES[1], SERIES[0]), cornerradius=4),
    text=[f"#1 for {t}" if t else "" for t in d.top1], textposition="outside", textfont=dict(color=INK2, size=11),
    customdata=np.stack([d.senders, d.top1, d.target_country_wb_income], axis=1),
    hovertemplate="<b>%{y}</b> (%{customdata[2]})<br>avg share of net outflow: %{x:.1f}%"
                  "<br>receives from %{customdata[0]} countries · top destination for %{customdata[1]}<extra></extra>"))
fig.update_layout(title="Where developing-economy talent goes<br><sup>Average share of each developing country's "
                        "net talent loss, 2019 (orange = high income, blue = developing)</sup>",
                  xaxis=dict(title="% of net outflow (country-average)", range=[0, d.avg_share.max() * 1.25]),
                  height=520, margin=dict(l=140), showlegend=False)
save(fig, "06_destinations")
""")

code("""
dev_out["base_region"] = dev_out.base_country_wb_region
reg_dest = (dev_out.groupby(["base_region", "target_country_name"]).share.sum()
            / dev_out.groupby("base_region").base_country_code.nunique() * 100).rename("avg_share").reset_index()
top_by_region = (reg_dest.sort_values("avg_share", ascending=False).groupby("base_region").head(4)
                 .sort_values(["base_region", "avg_share"], ascending=[True, False]))
top_by_region.assign(avg_share=top_by_region.avg_share.round(1)).pivot_table(
    index="base_region", columns=top_by_region.groupby("base_region").cumcount() + 1,
    values="target_country_name", aggfunc="first").rename(columns=lambda c: f"#{c}")
""")

md("""
**South-South corridors.** Not all developing-economy talent goes North. Developing economies that net *gain* from other developing economies:
""")

code("""
ss = country[(country.base_country_wb_income != "High income") & (country.target_country_wb_income != "High income")
             & (country.net_per_10K_2019 > 0)]
ss.nlargest(12, "net_per_10K_2019")[["base_country_name", "target_country_name", "net_per_10K_2015", "net_per_10K_2019"]] \\
  .rename(columns={"base_country_name": "receiver", "target_country_name": "sender"})
""")

md("""
## 6. Colombia close-up

A short look at the country I know best, as a worked example of the reallocation story.
""")

code("""
co = country[country.base_country_code == "co"].set_index("target_country_name")[YCOLS]
co.columns = YEARS
print("Colombia total net per 10k:", totals.set_index("code").loc["co", YCOLS].round(1).tolist())
display(pd.concat([co.nsmallest(6, 2019), co.nlargest(3, 2019)]))
co_sk = skill[skill.country_code == "co"].groupby("family").net_per_10K_2019.median()
print("Colombia median skill-group rate by family, 2019:"); print(co_sk.round(1).to_string())
""")

md("""
## 7. Caveats

1. **Time window.** Data ends in 2019 and each year is a trailing three-year average. Pandemic-era remote work, the post-2022 tech layoffs and the GenAI wave are not in this file.
2. **Coverage bias.** LinkedIn over-represents urban, white-collar, English-speaking and knowledge-intensive workers. These are flows of *LinkedIn-visible* talent, not total migration.
3. **Selection.** Countries need 100k+ members; corridors, industries and skill groups need 50+ observations. Small countries and rare skills are under-represented. The balanced-panel check in §3 suggests the tech result is not driven by this.
4. **Normalisation differs by sheet.** Country, industry and skill rates have different denominators; compare within a sheet, not across.
5. **Location is self-reported.** A changed job location counts as a move, so remote workers who relabel location and late profile updates add noise.
6. **No absolute counts.** Destinations are ranked by country-average shares, so a destination that dominates many small senders ranks above one that receives many people from one large sender (for example India to the US or UAE).
7. **Income classification** is the file's snapshot (e.g. Argentina is listed as high income), not today's.
""")

code("""
dev_t = totals[totals.developing]
k, n = int((pair[pair.developing].tech < pair[pair.developing].non_tech).sum()), int(pair.developing.sum())
ai_dev = ai_table.query("group == 'Developing' and skill_group == 'Artificial Intelligence (AI)'").iloc[0]
ai_hi = ai_table.query("group == 'High income' and skill_group == 'Artificial Intelligence (AI)'").iloc[0]
print(f"Developing economies losing talent: {(dev_t.net_per_10K_2015 < 0).mean():.0%} in 2015 -> {(dev_t.net_per_10K_2019 < 0).mean():.0%} in 2019")
print(f"Tech skills leave faster than non-tech in {k}/{n} developing economies ({k/n:.0%})")
print(f"AI skills: median {ai_dev.median_rate:.0f} per 10k in developing ({int(ai_dev.countries)} countries) vs {ai_hi.median_rate:+.0f} in high income ({int(ai_hi.countries)})")
print(f"Top destination by country-average share: {dest.iloc[0].target_country_name} ({dest.iloc[0].avg_share:.1f}%)")
""")

md("""
## 8. Findings, in one place

Lead finding for the page: **AI talent is the fastest-leaving talent in developing economies.** Where AI skills are measurable, the median developing country loses about 3 out of every 100 AI-skilled members per year on net, and in countries that are net losers the typical AI outflow rate is 2.9x the same country's non-tech rate, while the median high-income country gains about 1.7 per 100. AI leaves faster than non-tech talent in 23 of the 25 developing economies where it is measurable. The same pattern holds more broadly: in about three quarters of developing economies, tech skill holders leave faster than non-tech workers.

Supporting findings:
- **Divergence over 2015 to 2019:** the median developing economy went from a small net gain to a net loss of about 10 per 10,000 members, while the median high-income economy roughly doubled its gain.
- **Tech as an amplifier:** tech skills move more in *both* directions. It is a sorting story (skilled workers reallocating toward high-return locations), not just a drain story.
- **Industries:** the sections losing talent fastest are human-capital-heavy public goods and knowledge services: health (−106), education (−103), professional and technical services (−95) and ICT (−89). At the detailed level, Research (−211), Accounting, Internet and Higher Education top the list, while banking, consumer goods and mining lose least. These are the sectors to watch alongside employment and job-postings trends.
- **Destinations:** the US (14.9% of the typical developing country's net loss), Canada (13.7%) and France (10.8%, driven by francophone Africa and the Maghreb) lead; Canada is a net sink for 67 of 87 developing economies. Regional patterns follow language and geography: LatAm to the US and Spain, MENA to Canada and the UAE, Sub-Saharan Africa to France. South-South corridors exist too: Venezuelan talent to Ecuador, Colombia and Peru, and Indian talent to Nepal, Rwanda and Sudan.
- **Colombia** is a mild net loser (−3.9), losing to Spain, Canada and Australia while absorbing Venezuelan talent. Unusually, its tech skills leave *slower* than non-tech, though AI-type skills still leave fastest.

Interactive versions of every chart are saved in `outputs/` for the web page.
""")

nb["cells"] = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parent.parent / "talent_migration_analysis.ipynb")
