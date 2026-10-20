"""Export the figures behind the web page from the World Bank x LinkedIn talent migration file.

Mirrors the logic in talent_migration_analysis.ipynb and writes site/data.js.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data/public_use-talent-migration.xlsx"
OUT = ROOT / "site/data.js"

YEARS = list(range(2015, 2020))
YCOLS = [f"net_per_10K_{y}" for y in YEARS]
INCOME_ORDER = ["High income", "Upper middle income", "Lower middle income", "Low income"]

xl = pd.ExcelFile(DATA)
country = xl.parse("Country Migration")
industry = xl.parse("Industry Migration")
skill = xl.parse("Skill Migration")
for col in ["base_country_wb_income", "target_country_wb_income"]:
    country[col] = country[col].str.capitalize()

# Country totals
totals = (country
          .groupby(["base_country_code", "base_country_name", "base_country_wb_income", "base_country_wb_region"])[YCOLS]
          .sum().reset_index()
          .rename(columns={"base_country_code": "code", "base_country_name": "country",
                           "base_country_wb_income": "income", "base_country_wb_region": "region"}))
totals["developing"] = totals.income != "High income"
dev_t = totals[totals.developing]

divergence = {inc: [round(v, 1) for v in totals[totals.income == inc][YCOLS].median()] for inc in INCOME_ORDER}
share_losing = {
    "developing": [round((dev_t[c] < 0).mean() * 100) for c in YCOLS],
    "high": [round((totals[~totals.developing][c] < 0).mean() * 100) for c in YCOLS],
}

# Skills: tech vs non-tech within country
skill["developing"] = skill.wb_income != "High income"
skill["is_tech"] = skill.skill_group_category.isin(["Tech Skills", "Disruptive Tech Skills"])
pair = (skill.groupby(["country_code", "country_name", "wb_income", "developing", "is_tech"])
        .net_per_10K_2019.median().unstack().dropna()
        .rename(columns={False: "non_tech", True: "tech"}).reset_index())
scatter = [dict(c=r.country_name, i=r.wb_income, d=bool(r.developing), x=round(r.non_tech), y=round(r.tech))
           for r in pair.itertuples()]
dev_pair = pair[pair.developing]
tech_faster = int((dev_pair.tech < dev_pair.non_tech).sum())

nontech_med = skill[~skill.is_tech].groupby("country_code").net_per_10K_2019.median()
FOCUS = ["Artificial Intelligence (AI)", "Software Testing", "Mobile Application Development",
         "Data Storage Technologies", "Robotics", "Data Science", "Web Development"]
skills_rows = []
for g in FOCUS:
    row = {"skill": g.replace(" (AI)", "")}
    for dev, key in [(True, "dev"), (False, "high")]:
        d = skill[(skill.skill_group_name == g) & (skill.developing == dev)]
        row[key] = round(d.net_per_10K_2019.median())
        row[key + "_n"] = int(len(d))
    skills_rows.append(row)
fam_nt = skill[~skill.is_tech].groupby(["developing", "country_code"]).net_per_10K_2019.median().groupby("developing").median()
skills_rows.append({"skill": "All non-tech skills", "dev": round(fam_nt[True]), "high": round(fam_nt[False]),
                    "dev_n": int(dev_pair.shape[0]), "high_n": int((~pair.developing).sum()), "ref": True})

ai_dev = skill[(skill.skill_group_name == "Artificial Intelligence (AI)") & skill.developing].set_index("country_code")
ai_faster = int((ai_dev.net_per_10K_2019 < nontech_med.reindex(ai_dev.index)).sum())
ai_losers = ai_dev[nontech_med.reindex(ai_dev.index) < 0]
ai_multiple = float((ai_losers.net_per_10K_2019 / nontech_med.reindex(ai_losers.index)).median())

# Industries
industry["developing"] = industry.wb_income != "High income"
sec = industry.groupby(["developing", "country_code", "isic_section_name"]).net_per_10K_2019.median().reset_index()
sec_sum = (sec.groupby(["isic_section_name", "developing"]).net_per_10K_2019
           .agg(["median", "count"]).unstack())
sec_sum = sec_sum[sec_sum[("count", True)] >= 20].sort_values(("median", True))
SHORT = {"Public administration and defence; compulsory social security": "Public administration",
         "Wholesale and retail trade; repair of motor vehicles and motorcycles": "Wholesale & retail trade",
         "Professional scientific and technical activities": "Professional & technical services",
         "Human health and social work activities": "Health & social work",
         "Administrative and support service activities": "Administrative & support",
         "Accommodation and food service activities": "Accommodation & food",
         "Information and communication": "Information & communication",
         "Financial and insurance activities": "Finance & insurance",
         "Transportation and storage": "Transport & storage",
         "Mining and quarrying": "Mining & quarrying",
         "Other service activities": "Other services",
         "Real estate activities": "Real estate"}
industries = [dict(s=SHORT.get(name, name), dev=round(r[("median", True)]), high=round(r[("median", False)]),
                   n=int(r[("count", True)]))
              for name, r in sec_sum.iterrows()]

# Destinations
dev_out = country[(country.base_country_wb_income != "High income") & (country.net_per_10K_2019 < 0)].copy()
dev_out["loss"] = -dev_out.net_per_10K_2019
dev_out["share"] = dev_out.loss / dev_out.groupby("base_country_code").loss.transform("sum")
n_base = dev_out.base_country_code.nunique()
top1 = dev_out.loc[dev_out.groupby("base_country_code").loss.idxmax(), "target_country_name"].value_counts()
dest = (dev_out.groupby(["target_country_name", "target_country_wb_income"])
        .agg(share=("share", lambda v: v.sum() / n_base * 100), senders=("base_country_code", "nunique"))
        .reset_index().sort_values("share", ascending=False).head(10))
destinations = [dict(c=r.target_country_name, share=round(r.share, 1), senders=int(r.senders),
                     top1=int(top1.get(r.target_country_name, 0)), high=r.target_country_wb_income == "High income")
                for r in dest.itertuples()]

payload = dict(
    years=YEARS, divergence=divergence, share_losing=share_losing, scatter=scatter,
    skills=skills_rows, industries=industries, destinations=destinations,
    stats=dict(n_dev=int(dev_t.shape[0]), n_high=int((~totals.developing).sum()),
               tech_faster=tech_faster, tech_n=int(dev_pair.shape[0]),
               ai_faster=ai_faster, ai_n=int(len(ai_dev)), ai_multiple=round(ai_multiple, 1),
               dest_bases=int(n_base)),
)
OUT.parent.mkdir(exist_ok=True)
OUT.write_text("window.TALENT = " + json.dumps(payload, separators=(",", ":")) + ";\n")
print(json.dumps(payload["stats"]), OUT.stat().st_size, "bytes")
print(json.dumps(payload["skills"]))
print(json.dumps(payload["industries"][:5]))
