import argparse
import datetime
import json
import logging
import os
from pathlib import Path
import signal
import sys
import time
import requests
import xml.etree.ElementTree as ET

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROCESS_FOLDER = SCRIPT_DIR / "data" / "processing" / "xml"
DEFAULT_EVENTS_FILE = SCRIPT_DIR / "events.json"
DEFAULT_LOG_FILE = SCRIPT_DIR / "logs" / "scraper.log"

process_folder = DEFAULT_PROCESS_FOLDER

logger = logging.getLogger("stanchart_scraper")


def setup_logging(log_file_path: str | Path = DEFAULT_LOG_FILE) -> None:
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
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler (logs all details to file)
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    # Console handler (outputs to terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # Suppress verbose HTTP logs from urllib3/requests
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def load_events(file_path: str | Path = DEFAULT_EVENTS_FILE) -> list[dict]:
    """
    Loads event configurations from a JSON file.
    """
    resolved_path = Path(file_path)
    if not resolved_path.is_file():
        resolved_path = SCRIPT_DIR / file_path
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Events file not found at: {file_path}")

    with open(resolved_path, "r", encoding="utf-8") as f:
        events_data = json.load(f)
    return events_data


try:
    events = load_events(DEFAULT_EVENTS_FILE)
except Exception:
    events = []


def validEvent(file: list[dict], eventName: str) -> str | None:
    """
    Validates if the event exists in the given events list (case-insensitive check).
    Parameters:
        file (list[dict]): loaded list of event dictionaries
        eventName (str): Name of the event
    Returns:
        eventURL (str) if the event is valid else None
    """
    cleaned = eventName.strip().lower()
    for e in file:
        if e.get("eventName", "").strip().lower() == cleaned:
            return e.get("eventURL")
    return None


def loadXML(link: str, filename: str, max_retries: int = 3, retry_backoff: float = 2.0) -> bool:
    """
    Dumps the XML file from a website into a file and checks if the current page is the last page.
    Parameters:
        link (str): the url of the xml file
        filename (str): filename / file path (without .xml extension)
        max_retries (int): maximum retry attempts on transient network errors
        retry_backoff (float): delay multiplier between retries
    Returns:
        bool: True if this is the last page, False otherwise
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/xml'
    }

    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(link, headers=headers, timeout=30)
            resp.raise_for_status()

            root = ET.fromstring(resp.content)

            # Check <last> tag
            is_last = False
            last_elem = root.find(".//last")
            if last_elem is not None and last_elem.text:
                if last_elem.text.strip().lower() == "true":
                    is_last = True

            # Also check if numberOfElements is 0
            num_elem = root.find(".//numberOfElements")
            if num_elem is not None and num_elem.text:
                try:
                    if int(num_elem.text.strip()) == 0:
                        is_last = True
                except ValueError:
                    pass

            # Write XML content to disk
            xml_file_path = f"{filename}.xml" if not filename.endswith(".xml") else filename
            os.makedirs(os.path.dirname(os.path.abspath(xml_file_path)), exist_ok=True)
            with open(xml_file_path, "wb") as f:
                f.write(resp.content)

            return is_last

        except requests.exceptions.RequestException as e:
            last_exception = e
            logger.error(f"Network error (attempt {attempt}/{max_retries}) fetching {link}: {e}")
            if attempt < max_retries:
                time.sleep(retry_backoff * attempt)
        except ET.ParseError as e:
            last_exception = e
            logger.error(f"Failed to parse XML response from {link}: {e}")
            raise e

    if last_exception:
        raise last_exception
    return False


def fetchEvent(
    eventName: str,
    eventURL: str,
    output_dir: Path | str = DEFAULT_PROCESS_FOLDER,
    delay: float = 2.0,
    start_page: int = 0,
) -> int:
    """
    Uses the provided event name and url to get xml data from website.
    Parameters:
        eventName (str): name of the event
        eventURL (str): base URL of the event
        output_dir (Path | str): base output directory for xml files
        delay (float): delay in seconds between consecutive requests
        start_page (int): page number to start scraping from (default: 0)
    Returns:
        int: total pages scraped
    """
    process_path = os.path.join(output_dir, eventName)
    os.makedirs(process_path, exist_ok=True)

    page_num = max(0, start_page)
    pages_scraped = 0
    last = False

    logger.info(f"Started fetching pages for event '{eventName}' from {eventURL} (starting at page {page_num})")

    while not last:
        url = f"{eventURL.rstrip('/')}/participants?page={page_num}&size=10&category=ALL_RESULTS"
        file_path = os.path.join(process_path, f"page_{page_num}")
        filename_str = str(file_path)

        logger.info(f"[{eventName}] Fetching page {page_num} -> {file_path}.xml")
        last = loadXML(url, filename_str)
        page_num += 1
        pages_scraped += 1

        if not last:
            time.sleep(delay)

    logger.info(f"Completed fetching for event '{eventName}' ({pages_scraped} pages saved to {process_path})")
    return pages_scraped


def getAllEvents(
    file: list[dict],
    output_dir: Path | str = DEFAULT_PROCESS_FOLDER,
    delay: float = 2.0,
    start_page: int = 0,
) -> None:
    """
    Gets all events from the provided list of event dictionaries.
    Parameters:
        file (list[dict]): loaded events data
        output_dir (Path | str): output directory
        delay (float): delay between requests
        start_page (int): page number to start scraping from (default: 0)
    """
    events_list = file
    total = len(events_list)
    logger.info(f"Starting scrape for all {total} events: {[e['eventName'] for e in events_list]}")

    for idx, event in enumerate(events_list, start=1):
        eventName = event["eventName"]
        eventURL = event["eventURL"]
        logger.info(f"--- Event {idx}/{total}: {eventName} ---")
        fetchEvent(
            eventName=eventName,
            eventURL=eventURL,
            output_dir=output_dir,
            delay=delay,
            start_page=start_page,
        )


def getEvent(
    eventName: str,
    events_list: list[dict] | None = None,
    output_dir: Path | str = DEFAULT_PROCESS_FOLDER,
    delay: float = 2.0,
    start_page: int = 0,
) -> None:
    """
    Fetches a specific event by name after validating its existence.
    """
    if events_list is None:
        events_list = events
    ev = validEvent(events_list, eventName=eventName)
    if ev is not None:
        # Find exact canonical name
        canonical_name = next(e["eventName"] for e in events_list if e.get("eventName", "").strip().lower() == eventName.strip().lower())
        fetchEvent(
            eventName=canonical_name,
            eventURL=ev,
            output_dir=output_dir,
            delay=delay,
            start_page=start_page,
        )
    else:
        available = [e.get("eventName") for e in events_list]
        err_msg = f"Could not retrieve valid event: '{eventName}'. Available events: {', '.join(available)}"
        logger.error(err_msg)
        raise ValueError(err_msg)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Standard Chartered Nairobi Marathon results scraper."
    )
    parser.add_argument(
        "-e", "--event",
        type=str,
        default=None,
        help="Specific event to scrape (e.g. '5K', '10K', 'half-marathon', 'wheelchair-half', 'full-marathon'). If not specified, all events will be scraped."
    )
    parser.add_argument(
        "event_positional",
        nargs="?",
        default=None,
        metavar="EVENT",
        help="Optional positional event argument (e.g. 'python scrape.py 5K')."
    )
    parser.add_argument(
        "--events-file",
        type=str,
        default=str(DEFAULT_EVENTS_FILE),
        help=f"Path to JSON file containing event URLs (default: {DEFAULT_EVENTS_FILE.name})."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_PROCESS_FOLDER),
        help=f"Directory to store downloaded XML files (default: {DEFAULT_PROCESS_FOLDER})."
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=str(DEFAULT_LOG_FILE),
        help=f"Path to log file (default: {DEFAULT_LOG_FILE})."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay in seconds between consecutive requests to avoid overwhelming the server (default: 2.0)."
    )
    parser.add_argument(
        "-p", "--start-page", "--start-from-page",
        dest="start_page",
        type=int,
        default=0,
        help="Page number to start scraping from (default: 0)."
    )
    parser.add_argument(
        "--list-events",
        action="store_true",
        help="List available events in the events file and exit."
    )
    args = parser.parse_args()
    if args.start_page < 0:
        parser.error("--start-page must be a non-negative integer (>= 0).")
    return args


def main():
    args = parse_args()

    # Initialize logging
    setup_logging(args.log_file)

    # Load events
    try:
        loaded_events = load_events(args.events_file)
    except Exception as e:
        logger.error(f"Failed to load events file from '{args.events_file}': {e}")
        print(f"Error loading events file: {e}", file=sys.stderr)
        sys.exit(1)

    if args.list_events:
        print("Available events in events.json:")
        for ev in loaded_events:
            print(f"  - {ev.get('eventName')}: {ev.get('eventURL')}")
        return

    # Target event
    target_event = args.event if args.event is not None else args.event_positional

    start_time = datetime.datetime.now()
    start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")

    if target_event:
        scrape_type = f"specific event '{target_event}'"
    else:
        scrape_type = f"all events ({len(loaded_events)} events: {', '.join(e.get('eventName', '') for e in loaded_events)})"

    logger.info("=" * 60)
    logger.info(f"Scraper started at: {start_time_str}")
    logger.info(f"Scrape target: {scrape_type}")
    if args.start_page > 0:
        logger.info(f"Start page: {args.start_page}")
    logger.info("=" * 60)

    # Handle SIGTERM by raising KeyboardInterrupt
    def sigterm_handler(signum, frame):
        raise KeyboardInterrupt("SIGTERM signal received")

    try:
        signal.signal(signal.SIGTERM, sigterm_handler)
    except (ValueError, AttributeError):
        pass

    try:
        if target_event:
            ev_url = validEvent(loaded_events, target_event)
            if not ev_url:
                available = [e.get("eventName") for e in loaded_events]
                err_msg = f"Invalid event specified: '{target_event}'. Available events: {', '.join(available)}"
                logger.error(err_msg)
                print(f"Error: {err_msg}", file=sys.stderr)
                sys.exit(1)

            canonical_name = next(e["eventName"] for e in loaded_events if e.get("eventName", "").strip().lower() == target_event.strip().lower())
            fetchEvent(
                eventName=canonical_name,
                eventURL=ev_url,
                output_dir=args.output_dir,
                delay=args.delay,
                start_page=args.start_page,
            )
        else:
            getAllEvents(
                file=loaded_events,
                output_dir=args.output_dir,
                delay=args.delay,
                start_page=args.start_page,
            )

        complete_time = datetime.datetime.now()
        complete_time_str = complete_time.strftime("%Y-%m-%d %H:%M:%S")
        elapsed = complete_time - start_time
        logger.info("=" * 60)
        logger.info(f"Scraper completed at: {complete_time_str} (Duration: {elapsed})")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        interrupted_time = datetime.datetime.now()
        interrupted_time_str = interrupted_time.strftime("%Y-%m-%d %H:%M:%S")
        elapsed = interrupted_time - start_time
        logger.warning("=" * 60)
        logger.warning(f"Scraper interrupted at: {interrupted_time_str} (Elapsed before interrupt: {elapsed})")
        logger.warning("=" * 60)
        sys.exit(130)

    except Exception as e:
        error_time = datetime.datetime.now()
        error_time_str = error_time.strftime("%Y-%m-%d %H:%M:%S")
        elapsed = error_time - start_time
        logger.error("=" * 60)
        logger.error(f"Scraper failed with error at: {error_time_str} (Elapsed before error: {elapsed})")
        logger.error(f"Error details: {e}", exc_info=True)
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
