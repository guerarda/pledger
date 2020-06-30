import argparse
import csv
import json
import sys
import os
import logging
from datetime import date

from plaid import Client


def field_list(string):
    """Class so argparse can convert a csv string to a list."""
    return string.split(",")


def init_client(credentials):
    """Creates a plaid.Client object from the specified credentials."""

    logging.debug(
        "Creating Plaid Client with credentials %s",
        json.dumps(credentials, sort_keys=True, indent=4),
    )
    client = Client(
        client_id=credentials["client_id"],
        secret=credentials["secret"],
        public_key=credentials["public_key"],
        environment="development",
    )
    return client


def load_config_file(filename):
    path = os.getcwd() + "/.ledger-fetch/" + filename + ".json"

    with open(path) as cfile:
        logging.debug("Loading config file '%s' from %s", filename, path)
        return json.load(cfile)
    return None


def get_credentials():
    """Loads the credentials into a json object."""
    return load_config_file("credentials")


def get_accounts():
    """Loads the account config file."""
    return load_config_file("accounts")


def get_categories():
    """Loads the categories override file"""
    return load_config_file("categories")


def get_plaid_hierarchies(fetch=True):
    """Loads the default plaid categories from a file if present, otherwise
       if fetch is set, get them from Plaid"""

    try:
        f = load_config_file(".plaid-hierarchies")
        return f
    except:
        if fetch:
            client = init_client(get_credentials())
            categories = client.Categories.get()["categories"]
            f = {}

            for item in categories:
                f[item["category_id"]] = {
                    i: item[i] for i in item if i != "category_id"
                }

            # Write to file since it was not present
            path = os.getcwd() + "/.ledger-fetch/.plaid-hierarchies.json"
            with open(path, "w") as cfile:
                logging.debug("Creating default categories file at %s", path)
                json.dump(f, cfile, sort_keys=True, indent=4)
        return f


def get_payees():
    """Loads the payees override file"""
    return load_config_file("payees")


def account_configs(config):
    """Return the map from account id to their configuration."""

    m = {}
    for bank, account in config.items():
        for name, conf in account.items():
            m[conf["account_id"]] = {i: conf[i] for i in conf if i != "account_id"}
    return m


def map_category(cid, hierarchy, categories):
    """Returns a category hierarchy for the id"""

    if cid in categories:
        return [categories[cid]]

    prefix = cid[:5]
    if prefix in categories:
        sub = categories[prefix]

        if "000" not in sub:
            return hierarchy

        cname = sub["000"]
        c = cid[5:8]

        if c in sub:
            if c == "000":
                return [cname]
            return [cname, sub[c]]
        return [cname, hierarchy[-1]]

    prefix = cid[:2]
    if prefix in categories:
        sub = categories[prefix]

        if "000000" not in sub:
            return hierarchy

        cname = sub["000000"]
        c = cid[2:]
        if c in sub:
            if c == "000000":
                return [cname]
            return [cname, sub[c]]

        prefix = cid[2:5]
        if prefix in sub:
            subsub = sub[prefix]

            if "000" not in subsub:
                return hierarchy

            sname = subsub["000"]
            sc = cid[5:]

            if sc in subsub:
                if sc == "000":
                    return [cname, sname]
                return [cname, sname, subsub[sc]]
            return [cname, sname, hierarchy[-1]]

        return [cname] + hierarchy[1:]

    return hierarchy


def override_category(xact, categories):
    xact["category"] = map_category(xact["category_id"], xact["category"], categories)


def override_hierarchy(xact, hierarchy):
    xact["category"] = hierarchy[xact["category_id"]]["hierarchy"]


def override_payee(xact, payees):
    name = xact["name"]
    if payees:
        if name in payees:
            for k, v in payees[name].items():
                xact[k] = v


def override_xact_fields(xact, payees=None, categories=None, hierarchies=None):
    """Overrides fields according to user configuration and preferences"""

    if payees:
        override_payee(xact, payees)

    if hierarchies:
        override_hierarchy(xact, hierarchies)

    if categories:
        override_category(xact, categories)


def xact_amount(xact, negate, append_currency):
    """Returns a string with the formatted transaction amount"""

    v = -xact["amount"] if negate else xact["amount"]
    fmt_str = "{:.2f} {}" if append_currency else "{:.2f}"
    ccode = xact["iso_currency_code"]

    return fmt_str.format(v, ccode)


def xact_category(xact):
    """Format a category hierarchy adding a separator"""

    category = xact["category"]
    cname = category[0]

    if len(category) > 1:
        for c in category[1:]:
            if len(c) > 0:
                cname += "::" + c
    return cname


def xact_name(xact):
    """Returns the payee of a transaction"""
    return xact["name"]


def csv_converter(data, args):
    out = csv.writer(args.output)
    fields = args.fields

    for xact in data:
        row = []
        for f in fields:
            if f == "amount":
                row.append(xact_amount(xact, args.negate, args.currency))

            elif f == "category":
                row.append(xact_category(xact))
            else:
                row.append(xact[f])
        out.writerow(row)


def ledger_converter(
    data, args, configs=None, payees=None, categories=None, plaid_hierarchies=None
):
    output = args.output
    for xact in data:

        config = {}
        if configs:
            config = configs[xact["account_id"]]

        if "name" not in config:
            config["name"] = "Asset::Unknown"
        if "negate" not in config:
            config["negate"] = args.negate
        if "currency" not in config:
            config["currency"] = args.currency

        override_xact_fields(xact, payees, categories, plaid_hierarchies)

        hdr = "{date} * {name}\n".format(date=xact["date"], name=xact_name(xact))
        tid = "    ; xactid: {tid}\n".format(tid=xact["transaction_id"])
        cat = "    {category}          {amount}\n".format(
            category=xact_category(xact),
            amount=xact_amount(xact, config["negate"], config["currency"]),
        )
        acc = "    {account}\n\n".format(account=config["name"])
        output.write(hdr)
        output.write(tid)
        output.write(cat)
        output.write(acc)


def convert_fn(args):
    """Convert each entry of the transaction history to either csv or ledger format."""

    with open(args.file) as file:
        data = json.load(file)
        cfg = account_configs(get_accounts())

        if args.format == "csv":
            csv_converter(data, args)
        elif args.format == "ledger":
            ledger_converter(
                data,
                args,
                configs=cfg,
                payees=get_payees(),
                categories=get_categories(),
                plaid_hierarchies=get_plaid_hierarchies(fetch=True),
            )


def fetch_fn(args):
    """Fetch transaction history from the specified account and prints the result"""

    logging.info(
        "Fetching the transaction history from the account '%s'...", args.account
    )

    credentials = get_credentials()
    accounts = get_accounts()
    client = init_client(credentials)

    # Convert date to strings in ISO format
    start = args.start.isoformat()
    end = args.end.isoformat()

    token = credentials["banks"][args.bank]

    if not args.all:
        account_list = []
        if args.account:
            account_list.append(accounts[args.bank][args.account]["account_id"])
        else:
            for k, v in accounts[args.bank].items():
                account_list.append(v["account_id"])

    if len(account_list) > 0:
        response = client.Transactions.get(
            token, start_date=start, end_date=end, account_ids=account_list
        )
    else:
        response = client.Transactions.get(token, start_date=start, end_date=end)

    transactions = response["transactions"]

    logging.info("Fetched %d transactions", response["total_transactions"])

    while len(transactions) < response["total_transactions"]:
        response = client.Transactions.get(
            token, start_date=start, end_date=end, offset=len(transactions)
        )
        transactions.extend(response["transactions"])

    logging.info("Writing %d transactions to %s", len(transactions), args.output)
    json.dump(transactions, args.output, sort_keys=True, indent=4)


def list_fn(args):
    credentials = get_credentials()
    client = init_client(credentials)

    response = client.Auth.get(credentials["banks"][args.account])

    json.dump(response, args.output, sort_keys=True, indent=4)


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

    fetchp.set_defaults(func=fetch_fn)

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
    convertp.set_defaults(func=convert_fn)

    # Parser for the list command
    listp = subs.add_parser(
        "list", description="List account related information", parents=[commonp]
    )
    listp.add_argument(
        "account", help="The account to fetch the transaction history from."
    )
    listp.set_defaults(func=list_fn)

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