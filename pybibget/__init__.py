import argparse
import re
import sys
import pybtex.database
import pybibget.bibentry as bibentry


def pybibget() -> None:
    """
    Reads citation keys from command line and calls get_citations()
    """
    parser = argparse.ArgumentParser(prog='pybibget', description='Command line utility to automatically retrieve BibTeX citations from MathSciNet, arXiv and PubMed')

    parser.add_argument('keys', type=str, metavar='citekeys', nargs='*', help='MathSciNet (MRxxxxx), arXiv (xxxx.xxxxx), PubMed (PMID:xxxxxxxx) or DOI (10.xxx/xxxxx) citation keys (separated by spaces)')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose output')
    parser.add_argument('-f', action='store', dest='file_name', help='Append output to file (default: write output to stdout)')

    args = parser.parse_args()
    if not args.keys:
        parser.print_help()
        exit(1)
    get_citations(args.keys, verbose=args.verbose, file=args.file_name)


def pybibparse():
    """
    Reads latex file name from the command line, parses the .blg file and calls get_citations()
    """
    parser = argparse.ArgumentParser(prog='pybibget', description='Command line utility to automatically retrieve missing BibTeX citations from MathSciNet, arXiv and PubMed')

    parser.add_argument('file_name', type=str, metavar='file_name', nargs=1, help='base file name of main tex file (without .tex extension)')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose output')
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
        if args.write is None:
            get_citations(missing_cites, verbose=args.verbose)
        elif args.write != " ":
            get_citations(missing_cites, verbose=args.verbose, file=args.write)
        elif args.write == " " and bib_file_names:
            get_citations(missing_cites, verbose=args.verbose, file=bib_file_names[0])
        else:
            print("No .bib file found. Please specify the .bib file via '-w file_name.bib'")
    else:
        print("No missing citations found. Make sure that biber/bibtex is run '\
            'successfully before running pybibget.")


def get_citations(keys, verbose=False, file=None):
    """
    Retrieves BibTeX entries for given citation keys and writes them to file or stdout
    """
    bib_data = pybtex.database.BibliographyData()
    for key in keys:
        try:
            bib_data.entries[key] = bibentry.getbibentry(key, verbose=verbose)
        except ValueError as error:
            print(error)
    number_of_entries = len(bib_data.entries)
    bib_data = bib_data.to_string('bibtex')
    if file:
        with open(file, 'a') as file:
            file.write(bib_data)
            print(f"Successfully appended {number_of_entries} BibTeX entries to {file}.")
    else:
        if verbose:
            print("\n======================\n Output:\n======================")
        print("\n"+bib_data)


if __name__ == '__main__':
    sys.exit(pybibget())
