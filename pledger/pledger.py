from . import xact

import argparse
import logging
import sys
from datetime import date


def field_list(string):
    """Class so argparse can convert a csv string to a list."""
    return string.split(",")


def main():
    parser = argparse.ArgumentParser(
        description="Pull transactions information and format it to csv or ledger format.",
        add_help=False,
    )
    subs = parser.add_subparsers(title="actions")

    # Parser for the verbosity, common to all subparsers
    commonp = argparse.ArgumentParser(add_help=False)
    commonp.add_argument("--verbose", "-v", action="count", default=0)
    commonp.add_argument(
        "--output",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="File to wite the transaction data to. Default to stdout.",
    )

    # Parser for the fetch command
    fetchp = subs.add_parser(
        "fetch",
        description="fetch the transaction history from the specified account.",
        parents=[commonp],
    )
    fetchp.add_argument(
        "bank", help="The institution to fetch the transaction history from."
    )
    fetchp.add_argument(
        "--start",
        help="Starting date, should be formatted as YYYY-MM-DD.",
        type=date.fromisoformat,
        default=date.min,
    )
    fetchp.add_argument(
        "--end",
        help="Ending date, should be formatted as YYYY-MM-DD.",
        type=date.fromisoformat,
        default=date.today(),
    )

    # We can either pick one account or all fo them. If no option selected
    # picks all the account listed for that institution in the account file.
    group = fetchp.add_mutually_exclusive_group()
    group.add_argument(
        "--account", help="If only interested in one specific account.",
    )
    group.add_argument(
        "--all",
        nargs="?",
        default=False,
        const=True,
        help="Fetches transactions for every account at the institution.",
    )

    fetchp.set_defaults(func=xact.fetch_fn)

    # Parser for the convert command
    convertp = subs.add_parser(
        "convert",
        description="Converts transaction data to csv or ledger format.",
        parents=[commonp],
    )
    convertp.add_argument(
        "file", help="The file containing the transaction history, in json format.",
    )

    convertp.add_argument(
        "--format",
        choices=["csv", "ledger"],
        required=True,
        help="The format of the exported data.",
    )
    convertp.add_argument(
        "--currency",
        "-c",
        nargs="?",
        default=False,
        const=True,
        help="If set, appends the currency iso code after the transaction amount",
    )
    convertp.add_argument(
        "--fields",
        default=["date", "amount", "name"],
        type=field_list,
        help="The fields of the transaction data the are to be exported.",
    )
    convertp.add_argument(
        "--negate",
        "-n",
        nargs="?",
        default=False,
        const=True,
        help="Flip the sign of the transaction amount.",
    )
    convertp.set_defaults(func=xact.convert_fn)

    # Parser for the list command
    listp = subs.add_parser(
        "list", description="List account related information", parents=[commonp]
    )
    listp.add_argument(
        "account", help="The account to fetch the transaction history from."
    )
    listp.set_defaults(func=xact.list_fn)

    args = parser.parse_args()

    if args == argparse.Namespace():
        parser.print_help()
        return

    # Set verbosity
    if args.verbose > 1:
        verbosity = logging.DEBUG
    elif args.verbose > 0:
        verbosity = logging.INFO
    else:
        verbosity = logging.WARNING

    logging.basicConfig(level=verbosity)
    args.func(args)


if __name__ == "__main__":
    main()
