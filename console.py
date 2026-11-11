"""
Console interface for Standard Chartered Marathon data pipeline.

Allows running the XML parser or scraper interactively or via CLI arguments.
"""

from __future__ import annotations

import sys


def interactive_menu() -> None:
    print("")
    print("Standard Chartered Marathon Data Tool")
    print("")
    print("1. Parse downloaded XML files to CSV")
    print("2. Scrape event XML results")
    print("3. Exit")

    choice = input("Select an option (1-3): ").strip()
    if choice == "1":
        import xmlparser
        xmlparser.main()
    elif choice == "2":
        import scrape
        scrape.main()
    elif choice == "3":
        print("Exiting.")
        sys.exit(0)
    else:
        print(f"Invalid option: {choice}")
        sys.exit(1)


def main() -> None:
    if len(sys.argv) > 1:
        # If arguments are passed, route directly to XML parser CLI
        import xmlparser
        xmlparser.main()
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
