# Wayback Time Machine

Reconstructs what a website looked like on a specific past date using the Internet Archive's
Wayback Machine, then optionally runs an LLM (DeepSeek) over the captured snapshots to analyze
or summarize them. Built originally to study historical news coverage of a given day.

## Files
| File | Role |
|---|---|
| `Webscrape_From_A_Day.py` | Pull Wayback captures for a target date |
| `webscrape_with_wayback.py` | Crawl + collect snapshot content |
| `wayback_and_deepseek.py` | Analyze captured snapshots with an LLM |

## Setup
Set your key (see `.env.example`), then:
```bash
python -m pip install requests beautifulsoup4
export DEEPSEEK_API_KEY="sk-..."
python Webscrape_From_A_Day.py
```

Sample captured snapshots (JSON) are included as examples.
