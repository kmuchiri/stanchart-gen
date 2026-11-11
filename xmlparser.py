"""
XML Parser to CSV for Standard Chartered Marathon Results.

Extracts participant data including overall position, competitor name,
country, gender position, event name, gun time, bib time, and splits
(split times and split speeds).

Supports both:
- 'split' (long) format: each split time and speed has its own row
- 'wide' format: each participant is one row with dynamic split columns
- 'both' format: generates both long and wide CSVs
"""

from __future__ import annotations

import argparse
import csv
import datetime
import logging
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_XML_DIR = SCRIPT_DIR / "data" / "processing" / "xml"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "data" / "processing" / "output"
DEFAULT_EVENTS_FILE = SCRIPT_DIR / "events.json"
DEFAULT_LOG_FILE = SCRIPT_DIR / "logs" / "xmlparser.log"

logger = logging.getLogger("xmlparser")


def setup_logging(log_file_path: str | Path = DEFAULT_LOG_FILE) -> logging.Logger:
    """
    Configures logging to output to both a specified log file and stdout.
    """
    log_file = Path(log_file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    return logger


def natural_sort_key(s: Path | str) -> list[int | str]:
    """
    Splits string into numbers and text segments for natural / numerical sorting.
    e.g., page_2.xml comes before page_10.xml.
    """
    name = Path(s).name
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", name)]


def sort_participants_by_position(participants: list[dict]) -> list[dict]:
    """
    Sorts participant dictionaries by overall position numerically.
    Non-numeric or missing positions are placed at the end.
    """
    def pos_key(p: dict) -> tuple[int, int | str]:
        pos = str(p.get("overall_position", "")).strip()
        try:
            return (0, int(pos))
        except ValueError:
            return (1, pos)

    return sorted(participants, key=pos_key)


def _get_text(element: ET.Element, tag: str, default: str = "") -> str:
    """
    Safely retrieves stripped text from a child element if present.
    """
    elem = element.find(tag)
    if elem is not None and elem.text is not None:
        return elem.text.strip()
    return default


def parse_participant(element: ET.Element, event_name: str = "") -> dict:
    """
    Parses a single participant <content> XML element into a dictionary.

    Extracted fields:
    - overall_position
    - competitor_name
    - country
    - gender_position
    - gender
    - bib
    - event_name
    - gun_time
    - bib_time (chip time)
    - splits: list of individual split dictionaries
    """
    overall_position = _get_text(element, "overallPosition")
    competitor_name = _get_text(element, "name")
    country = _get_text(element, "country")
    gender_position = _get_text(element, "genderPosition")
    gender = _get_text(element, "gender")
    bib = _get_text(element, "bib")
    gun_time = _get_text(element, "gunTimeOfParticipant")
    bib_time = _get_text(element, "chipTimeOfParticipant")

    # If chip time is empty, attempt to fallback to legDuration if available
    if not bib_time:
        leg_duration = _get_text(element, ".//legs/legs/legDuration")
        if leg_duration:
            bib_time = leg_duration

    splits: list[dict] = []
    splits_elements = element.findall(".//participantSplits/participantSplits")
    for sp in splits_elements:
        split_dict = {
            "distance_in_meters": _get_text(sp, "distanceInMeters"),
            "split_name": _get_text(sp, "splitName"),
            "split_duration": _get_text(sp, "splitDuration"),
            "total_split_duration": _get_text(sp, "totalSplitDuration"),
            "personal_split_speed": _get_text(sp, "personalSplitSpeed"),
        }
        splits.append(split_dict)

    return {
        "overall_position": overall_position,
        "competitor_name": competitor_name,
        "country": country,
        "gender_position": gender_position,
        "gender": gender,
        "bib": bib,
        "event_name": event_name,
        "gun_time": gun_time,
        "bib_time": bib_time,
        "splits": splits,
    }


def parse_xml_file(file_path: str | Path, event_name: str = "") -> list[dict]:
    """
    Parses an XML file containing participant records.
    Returns a list of participant dictionaries.
    """
    path = Path(file_path)
    if not path.is_file():
        logger.error(f"File not found: {path}")
        return []

    # If event_name not passed, try inferring from parent directory name
    if not event_name:
        event_name = path.parent.name

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error(f"XML parse error in {path}: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to read file {path}: {e}")
        return []

    participants: list[dict] = []
    # Each participant entry is inside <content><content>...</content></content>
    content_elements = root.findall(".//content/content")
    for elem in content_elements:
        participant = parse_participant(elem, event_name=event_name)
        participants.append(participant)

    return participants


def parse_event_dir(event_dir: str | Path, event_name: str = "") -> list[dict]:
    """
    Parses all XML files in an event directory, sorted naturally by filename.
    """
    dir_path = Path(event_dir)
    if not dir_path.is_dir():
        logger.error(f"Directory not found: {dir_path}")
        return []

    resolved_event_name = event_name if event_name else dir_path.name
    xml_files = sorted(dir_path.glob("*.xml"), key=natural_sort_key)

    participants: list[dict] = []
    for xml_file in xml_files:
        page_participants = parse_xml_file(xml_file, event_name=resolved_event_name)
        participants.extend(page_participants)

    logger.info(f"Parsed {len(participants)} participants from {len(xml_files)} files in '{dir_path.name}'")
    return sort_participants_by_position(participants)


def parse_all_events(xml_root_dir: str | Path = DEFAULT_XML_DIR) -> dict[str, list[dict]]:
    """
    Discovers all event subdirectories under xml_root_dir and parses each.
    Returns a dictionary mapping event_name -> list of participant dicts.
    """
    root_path = Path(xml_root_dir)
    if not root_path.is_dir():
        logger.error(f"XML root directory not found: {root_path}")
        return {}

    events_data: dict[str, list[dict]] = {}
    subdirs = sorted([d for d in root_path.iterdir() if d.is_dir()], key=lambda d: d.name.lower())

    for subdir in subdirs:
        # Check if subdir contains any xml files
        xml_files = list(subdir.glob("*.xml"))
        if not xml_files:
            continue
        event_name = subdir.name
        events_data[event_name] = parse_event_dir(subdir, event_name=event_name)

    return events_data


SPLIT_CSV_COLUMNS = [
    "overall_position",
    "competitor_name",
    "country",
    "gender_position",
    "gender",
    "bib",
    "event_name",
    "gun_time",
    "bib_time",
    "split_name",
    "split_distance_meters",
    "split_time",
    "cumulative_split_time",
    "split_speed",
]


def participants_to_split_rows(participants: list[dict]) -> list[dict]:
    """
    Converts participants into normalized long-format rows, where each split
    time and split speed occupies its own row.

    Columns include:
    - overall_position
    - competitor_name
    - country
    - gender_position
    - gender
    - bib
    - event_name
    - gun_time
    - bib_time
    - split_name
    - split_distance_meters
    - split_time (segment duration)
    - cumulative_split_time (total duration from start)
    - split_speed (speed in km/h)
    """
    rows: list[dict] = []
    for p in participants:
        base = {
            "overall_position": p.get("overall_position", ""),
            "competitor_name": p.get("competitor_name", ""),
            "country": p.get("country", ""),
            "gender_position": p.get("gender_position", ""),
            "gender": p.get("gender", ""),
            "bib": p.get("bib", ""),
            "event_name": p.get("event_name", ""),
            "gun_time": p.get("gun_time", ""),
            "bib_time": p.get("bib_time", ""),
        }

        splits = p.get("splits", [])
        if not splits:
            # Participant has no splits, output 1 row with empty split fields
            row = dict(base)
            row.update({
                "split_name": "",
                "split_distance_meters": "",
                "split_time": "",
                "cumulative_split_time": "",
                "split_speed": "",
            })
            rows.append(row)
        else:
            for sp in splits:
                row = dict(base)
                row.update({
                    "split_name": sp.get("split_name", ""),
                    "split_distance_meters": sp.get("distance_in_meters", ""),
                    "split_time": sp.get("split_duration", ""),
                    "cumulative_split_time": sp.get("total_split_duration", ""),
                    "split_speed": sp.get("personal_split_speed", ""),
                })
                rows.append(row)

    return rows


def _clean_split_column_name(split_name: str, distance_meters: str = "") -> str:
    """
    Creates a valid CSV column identifier from split name or distance.
    e.g., '7.4 km' -> '7_4km', '10.0 km' -> '10_0km'
    """
    if split_name:
        clean = split_name.strip().lower()
        clean = clean.replace(" ", "")
        clean = re.sub(r"[^\w]", "_", clean)
        return clean
    if distance_meters:
        return f"{distance_meters}m"
    return "unknown"


def participants_to_wide_rows(participants: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Converts participants into wide-format rows, where each competitor has 1 row
    and split times and split speeds are represented in dedicated columns.

    Returns:
    - tuple: (rows, fieldnames)
    """
    # Collect all distinct splits preserving distance order
    splits_order: list[tuple[int, str]] = []
    seen_splits: set[str] = set()

    for p in participants:
        for sp in p.get("splits", []):
            sp_name = sp.get("split_name", "")
            if sp_name and sp_name not in seen_splits:
                dist_str = sp.get("distance_in_meters", "0")
                try:
                    dist_int = int(dist_str)
                except ValueError:
                    dist_int = 0
                splits_order.append((dist_int, sp_name))
                seen_splits.add(sp_name)

    # Sort splits by distance
    splits_order.sort(key=lambda x: x[0])
    ordered_split_names = [s[1] for s in splits_order]

    # Build fieldnames
    base_fields = [
        "overall_position",
        "competitor_name",
        "country",
        "gender_position",
        "gender",
        "bib",
        "event_name",
        "gun_time",
        "bib_time",
    ]

    split_fields: list[str] = []
    col_mapping: dict[str, dict[str, str]] = {}
    for sp_name in ordered_split_names:
        clean_name = _clean_split_column_name(sp_name)
        time_col = f"split_{clean_name}_time"
        cum_time_col = f"split_{clean_name}_cumulative_time"
        speed_col = f"split_{clean_name}_speed"
        split_fields.extend([time_col, cum_time_col, speed_col])
        col_mapping[sp_name] = {
            "time": time_col,
            "cum_time": cum_time_col,
            "speed": speed_col,
        }

    all_fieldnames = base_fields + split_fields

    rows: list[dict] = []
    for p in participants:
        row = {f: "" for f in all_fieldnames}
        row.update({
            "overall_position": p.get("overall_position", ""),
            "competitor_name": p.get("competitor_name", ""),
            "country": p.get("country", ""),
            "gender_position": p.get("gender_position", ""),
            "gender": p.get("gender", ""),
            "bib": p.get("bib", ""),
            "event_name": p.get("event_name", ""),
            "gun_time": p.get("gun_time", ""),
            "bib_time": p.get("bib_time", ""),
        })

        for sp in p.get("splits", []):
            sp_name = sp.get("split_name", "")
            if sp_name in col_mapping:
                cols = col_mapping[sp_name]
                row[cols["time"]] = sp.get("split_duration", "")
                row[cols["cum_time"]] = sp.get("total_split_duration", "")
                row[cols["speed"]] = sp.get("personal_split_speed", "")

        rows.append(row)

    return rows, all_fieldnames


def write_csv(rows: list[dict], fieldnames: list[str], output_path: str | Path) -> Path:
    """
    Writes a list of dictionary rows to a CSV file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Wrote {len(rows)} rows to CSV: {path}")
    return path


def export_event_csv(
    participants: list[dict],
    event_name: str,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    output_format: str = "both",
) -> dict[str, Path]:
    """
    Exports participants for a single event to CSV.
    Supports formats: 'split' (rows for splits), 'wide', or 'both'.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    created_files: dict[str, Path] = {}

    if output_format in ("split", "both"):
        split_rows = participants_to_split_rows(participants)
        split_csv_path = out_dir / f"{event_name}_splits.csv"
        write_csv(split_rows, SPLIT_CSV_COLUMNS, split_csv_path)
        created_files["split"] = split_csv_path

    if output_format in ("wide", "both"):
        wide_rows, wide_fieldnames = participants_to_wide_rows(participants)
        wide_csv_path = out_dir / f"{event_name}_wide.csv"
        write_csv(wide_rows, wide_fieldnames, wide_csv_path)
        created_files["wide"] = wide_csv_path

    return created_files


def export_all_csvs(
    events_data: dict[str, list[dict]],
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    output_format: str = "both",
) -> dict[str, list[Path]]:
    """
    Exports CSV files for all events, including individual event CSVs
    and combined all-events CSVs.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_participants: list[dict] = []
    generated_files: dict[str, list[Path]] = {
        "event_files": [],
        "combined_files": [],
    }

    # Export per-event CSVs
    for event_name, participants in events_data.items():
        all_participants.extend(participants)
        event_files = export_event_csv(
            participants=participants,
            event_name=event_name,
            output_dir=out_dir,
            output_format=output_format,
        )
        generated_files["event_files"].extend(event_files.values())

    # Export combined CSVs
    sorted_all = sort_participants_by_position(all_participants)

    if output_format in ("split", "both"):
        combined_split_rows = participants_to_split_rows(sorted_all)
        combined_split_path = out_dir / "results_splits.csv"
        write_csv(combined_split_rows, SPLIT_CSV_COLUMNS, combined_split_path)
        generated_files["combined_files"].append(combined_split_path)

        # Also write canonical results.csv as split format
        canonical_path = out_dir / "results.csv"
        write_csv(combined_split_rows, SPLIT_CSV_COLUMNS, canonical_path)
        generated_files["combined_files"].append(canonical_path)

    if output_format in ("wide", "both"):
        combined_wide_rows, wide_fieldnames = participants_to_wide_rows(sorted_all)
        combined_wide_path = out_dir / "results_wide.csv"
        write_csv(combined_wide_rows, wide_fieldnames, combined_wide_path)
        generated_files["combined_files"].append(combined_wide_path)

    return generated_files


def main() -> None:
    """
    Command-line interface for the XML-to-CSV parser.
    """
    parser = argparse.ArgumentParser(
        description="Parse Standard Chartered Marathon XML results into CSV format."
    )
    parser.add_argument(
        "-i", "--input",
        dest="input_path",
        default=str(DEFAULT_XML_DIR),
        help=f"Path to XML directory or specific XML file (default: {DEFAULT_XML_DIR})",
    )
    parser.add_argument(
        "-o", "--output-dir",
        dest="output_dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Path to directory where CSV files will be saved (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "-f", "--format",
        dest="format",
        choices=["split", "wide", "both"],
        default="both",
        help="CSV format: 'split' (row per split time/speed), 'wide' (columns for splits), or 'both' (default: both)",
    )
    parser.add_argument(
        "-e", "--event",
        dest="event_name",
        default=None,
        help="Optional specific event name filter",
    )
    parser.add_argument(
        "--log-file",
        dest="log_file",
        default=str(DEFAULT_LOG_FILE),
        help=f"Path to log file (default: {DEFAULT_LOG_FILE})",
    )

    args = parser.parse_args()

    setup_logging(args.log_file)
    logger.info("=" * 60)
    logger.info(f"XML Parser started at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Input: {args.input_path}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Format: {args.format}")
    if args.event_name:
        logger.info(f"Target event: {args.event_name}")
    logger.info("=" * 60)

    input_path = Path(args.input_path)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        logger.error(f"Input path does not exist: {input_path}")
        sys.exit(1)

    if input_path.is_file():
        # Parsing a single XML file
        event_name = args.event_name or input_path.parent.name
        participants = parse_xml_file(input_path, event_name=event_name)
        export_event_csv(
            participants=participants,
            event_name=event_name,
            output_dir=output_dir,
            output_format=args.format,
        )
    elif args.event_name:
        # User specified an event and input is a directory
        event_dir = input_path / args.event_name if (input_path / args.event_name).is_dir() else input_path
        participants = parse_event_dir(event_dir, event_name=args.event_name)
        export_event_csv(
            participants=participants,
            event_name=args.event_name,
            output_dir=output_dir,
            output_format=args.format,
        )
    else:
        # Check if input directory is directly an event directory (has XML files inside)
        xml_in_root = list(input_path.glob("*.xml"))
        if xml_in_root:
            event_name = input_path.name
            participants = parse_event_dir(input_path, event_name=event_name)
            export_event_csv(
                participants=participants,
                event_name=event_name,
                output_dir=output_dir,
                output_format=args.format,
            )
        else:
            # Parse all event subdirectories
            events_data = parse_all_events(input_path)
            if not events_data:
                logger.warning(f"No XML files found in {input_path}")
            else:
                export_all_csvs(events_data, output_dir=output_dir, output_format=args.format)

    logger.info("=" * 60)
    logger.info(f"XML Parser completed at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
