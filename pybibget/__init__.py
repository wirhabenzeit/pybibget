import argparse
import asyncio
import re
import sys
import logging as log
from enum import Enum
import pybtex.database
import pybibget.bibentry as bibentry


def pybibget() -> None:
    """
    Reads citation keys from command line and calls get_citations()
    """
    parser = argparse.ArgumentParser(prog='pybibget', description='Command line utility to automatically retrieve BibTeX citations from MathSciNet, arXiv and PubMed')

    parser.add_argument('keys', type=str, metavar='citekeys', nargs='*', help='MathSciNet (MRxxxxx), arXiv (xxxx.xxxxx), PubMed (PMID:xxxxxxxx) or DOI (10.xxx/xxxxx) citation keys (separated by spaces)')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose output')
    parser.add_argument('-d', '--debug', action='store_true', help='debug output')
    parser.add_argument('-f', action='store', dest='file_name', help='Append output to file (default: write output to stdout)')

    args = parser.parse_args()
    kwargs = {'file': args.file_name}
    if args.debug:
        kwargs['verbose'] = log.DEBUG
    elif args.verbose:
        kwargs['verbose'] = log.INFO
    if not args.keys:
        parser.print_help()
        exit(1)
    asyncio.run(get_citations(args.keys, **kwargs))


def pybibparse():
    """
    Reads latex file name from the command line, parses the .blg file and calls get_citations()
    """
    parser = argparse.ArgumentParser(prog='pybibget', description='Command line utility to automatically retrieve missing BibTeX citations from MathSciNet, arXiv and PubMed')

    parser.add_argument('file_name', type=str, metavar='file_name', nargs=1, help='base file name of main tex file (without .tex extension)')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose output')
    parser.add_argument('-d', '--debug', action='store_true', help='debug output')
    parser.add_argument('-w', '--write', metavar="file_name", action='store', nargs='?', const=" ", type=str, help='Append output to .bib file (default: write output to stdout). The .bib file is automatically detected from the .blg file. If no .bib file is found, the .bib file has to be specified explicitly via "-w file_name.bib".')

    args = parser.parse_args()
    if not args.file_name:
        parser.print_help()
        sys.exit()

    base_file_name = args.file_name[0]
    with open(base_file_name+".blg") as file:
        blg_file = file.read()
    missing_cites = re.findall(r"I didn't find a database entry for '([A-Za-z0-9\.\-_ :\/]*)'", blg_file) \
        + re.findall(r'I didn\'t find a database entry for "([A-Za-z0-9\.\-_ :\/]*)"', blg_file)
    bib_file_names = re.findall(r"Found BibTeX data source '([A-Za-z0-9.\-_\/]*)'", blg_file) \
        + re.findall(r"Looking for bibtex file '([A-Za-z0-9.\-_\/]*)'", blg_file) \
        + re.findall(r'Database file #\d: ([A-Za-z0-9.\-_\/]*)\n', blg_file) \
        + re.findall(r'I couldn\'t open database file ([A-Za-z0-9.\-_\/]*)\n', blg_file)

    if missing_cites:
        kwargs = {}
        if args.debug:
            kwargs['verbose'] = log.DEBUG
        elif args.verbose:
            kwargs['verbose'] = log.INFO
        if args.write:
            if args.write == " " and not bib_file_names:
                print("No .bib file found. Please specify the .bib file via '-w file_name.bib'")
                sys.exit()
            kwargs['file'] = bib_file_names[0] if args.write == " " else args.write
        asyncio.run(get_citations(missing_cites, **kwargs))        
    else:
        print("No missing citations found. Make sure that biber/bibtex is run successfully before running pybibget.")


async def get_citations(keys, verbose=log.WARN, file=None):
    """
    Retrieves BibTeX entries for given citation keys and writes them to file or stdout
    """
    log.basicConfig(format="%(levelname)s: %(message)s", level=verbose)

    bibentries = await asyncio.gather(*[bibentry.getbibentry(key) for key in keys],return_exceptions=True)
    bib_data = pybtex.database.BibliographyData()
    for entry_key in bibentries:
        if type(entry_key) in [ValueError, TypeError]:
            log.error(entry_key)
        else:
            entry,key = entry_key
            bib_data.entries[key] = entry
        
    number_of_entries = len(bib_data.entries)
    bib_data = bib_data.to_string('bibtex')
    if file:
        with open(file, 'a') as obj:
            obj.write(bib_data)
            print(f"Successfully appended {number_of_entries} BibTeX entries to {file}.")
    else:
        print("\n"+bib_data)


if __name__ == '__main__':
    sys.exit(pybibget())
