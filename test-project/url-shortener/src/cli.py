import argparse
import sys
from storage import URLStorage
from analytics import Analytics


def main():
    parser = argparse.ArgumentParser(description="URL Shortener CLI")
    subparsers = parser.add_subparsers(dest="command")

    shorten_parser = subparsers.add_parser("shorten", help="Create a short URL")
    shorten_parser.add_argument("url", help="Long URL to shorten")
    shorten_parser.add_argument("--ttl", type=int, default=None, help="Time to live in seconds")

    stats_parser = subparsers.add_parser("stats", help="Get click statistics")
    stats_parser.add_argument("short_code", help="Short code to query")

    delete_parser = subparsers.add_parser("delete", help="Delete a short URL")
    delete_parser.add_argument("short_code", help="Short code to delete")
    delete_parser.add_argument("--force", action="store_true", help="Skip confirmation")

    args = parser.parse_args()

    storage = URLStorage()
    analytics = Analytics()

    if args.command == "shorten":
        from encoder import URLEncoder
        encoder = URLEncoder()

        max_retries = 3
        for attempt in range(max_retries):
            short_code = encoder.encode(args.url)
            if storage.save_mapping(short_code, args.url, args.ttl):
                print(f"Short URL: http://localhost:8000/{short_code}")
                return

        print("Error: Failed to generate unique short code", file=sys.stderr)
        sys.exit(1)

    elif args.command == "stats":
        long_url = storage.get_long_url(args.short_code)
        if not long_url:
            print(f"Error: Short code '{args.short_code}' not found", file=sys.stderr)
            sys.exit(1)

        stats = analytics.get_stats(args.short_code)
        print(f"Short code: {args.short_code}")
        print(f"Clicks: {stats['clicks']}")
        if stats['last_click']:
            print(f"Last click: {stats['last_click']}")
        else:
            print("Last click: Never")

    elif args.command == "delete":
        long_url = storage.get_long_url(args.short_code)
        if not long_url:
            print(f"Error: Short code '{args.short_code}' not found", file=sys.stderr)
            sys.exit(1)

        if not args.force:
            confirm = input(f"Delete {args.short_code}? [y/N]: ")
            if confirm.lower() != "y":
                print("Cancelled")
                return

        storage.delete_mapping(args.short_code)
        print(f"Deleted: {args.short_code}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
