# Where Talent Moves

Net talent migration in developing economies, 2015 to 2019, using the World Bank Group and LinkedIn public talent migration data.

**Live page:** https://where-talent-moves.vercel.app

## Findings

- **AI talent leaves developing economies fastest.** The median developing economy loses 308 net AI-skilled members per 10,000 per year, while the median high-income economy gains 174.
- **Tech skills amplify reallocation.** Tech talent leaves faster than non-tech talent in 65 of 88 developing economies, and arrives faster in high-income ones.
- **Divergence.** The share of developing economies with net talent outflows rose from 39% in 2015 to 73% in 2019.
- **Industries.** Health, education, professional services and ICT lose talent fastest.
- **Destinations.** The United States, Canada and France take the largest average shares of developing-economy net outflows.

## Contents

| Path | What it is |
|---|---|
| `talent_migration_analysis.ipynb` | Full analysis with outputs, robustness checks and caveats |
| `site/` | Static web page (hand-built SVG charts, no framework) |
| `scripts/export_site_data.py` | Rebuilds `site/data.js` from the source file |
| `scripts/build_notebook.py` | Generates the notebook |
| `data/` | Source files from the World Bank data catalog |
| `outputs/` | Interactive Plotly versions of the notebook charts |

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/jupyter execute --inplace talent_migration_analysis.ipynb
.venv/bin/python scripts/export_site_data.py
```

## Data

World Bank Group and LinkedIn, *Digital Data for Development: Talent Migration* ([dataset 0038044](https://datacatalog.worldbank.org/search/dataset/0038044)), licensed CC BY 3.0 IGO. The public use file covers 2015 to 2019; each year is a trailing three-year average. LinkedIn coverage skews toward urban, white-collar workers, and flows under 50 observations are suppressed.

Analysis by Benjamin Reyes.
