# stanchart-gen
A web scraper and dataset generator for the Standard Chartered Nairobi Marathon.

## Py
- **Scraper (`scrape.py`)**: Fetches marathon results paginated in XML format from the official timing results endpoint.
- **XML-to-CSV Parser (`xmlparser.py`)**: Parses nested XML participant and split records into clean tabular CSV files.
- **Console Interface (`console.py`)**: Interactive entry point to scrape or parse data.

## CSV Outputs
The parser produces CSV datasets under `data/processing/output/`:
- **Long / Splits Format (`results_splits.csv` / `results.csv`)**:
  Each competitor split (time and speed) has its own row, ideal for time series and split-level analysis.
  **Columns**:
  - `overall_position`
  - `competitor_name`
  - `country`
  - `gender_position`
  - `gender`
  - `bib`
  - `event_name`
  - `gun_time`
  - `bib_time` (chip time)
  - `split_name`
  - `split_distance_meters`
  - `split_time` (segment duration)
  - `cumulative_split_time` (elapsed time from start)
  - `split_speed` (speed in km/h)

- **Wide Format (`results_wide.csv`)**:
  Each participant is a single row with dynamic columns for each split's duration, cumulative time, and speed.

- **Event-Specific Files**:
  Generated per race event (e.g. `full-marathon_splits.csv`, `wheelchair-half_splits.csv`, `full-marathon_wide.csv`, `wheelchair-half_wide.csv`).

## Usage

### 1. Run the Scraper
Fetch XML results from the official API:
```bash
python3 scrape.py                      # Scrape all events from page 0
python3 scrape.py -e full-marathon     # Scrape a specific event
python3 scrape.py -e 5K -p 10          # Start scraping from page 10
python3 scrape.py --start-from-page 5  # Alternative long flag for starting page
```

### 2. Run the XML Parser
Parse all XML files into CSVs (generates both split-row and wide formats):
```bash
python3 xmlparser.py
```

Options:
```bash
python3 xmlparser.py --format split   # Row-per-split format
python3 xmlparser.py --format wide    # Row-per-competitor format
python3 xmlparser.py --format both    # Generate both formats (default)
python3 xmlparser.py -e full-marathon # Specific event
python3 xmlparser.py -i data/processing/xml/wheelchair-half/page_0.xml # Single XML file
```

### 3. Run Tests
```bash
python3 -m unittest discover tests
```
