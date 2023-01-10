import argparse
import asyncio
import re
import sys
import logging as log
log.getLogger('asyncio').setLevel(log.WARNING)
from pybibget.bibentry import Bibget
from pybtex.database import parse_string

def add_optional_args(parser):
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose output')
    parser.add_argument('-d', '--debug', action='store_true', help='debug output')
    parser.add_argument('--skip-doi-msc', action='store_true', help='skip MathSciNet lookup for DOIs')
    

def pybibget():
    """
    Reads citation keys from command line and calls get_citations()
    """
    parser = argparse.ArgumentParser(prog='pybibget', description='Command line utility to automatically retrieve BibTeX citations from MathSciNet, arXiv and PubMed')
    parser.add_argument('keys', type=str, metavar='citekeys', nargs='*', help='MathSciNet (MRxxxxx), arXiv (xxxx.xxxxx), PubMed (PMID:xxxxxxxx) or DOI (10.xxx/xxxxx) citation keys (separated by spaces)')
    parser.add_argument('-w', action='store', dest='file_name', help='Append output to file (default: write output to stdout)')
    add_optional_args(parser)
    args = parser.parse_args()
    kwargs = {'file': args.file_name }
    if args.debug:
        kwargs['verbose'] = log.DEBUG
    elif args.verbose:
        kwargs['verbose'] = log.INFO
    if not args.keys:
        parser.print_help()
        exit(1)
    
    get_citations(args.keys, **kwargs)


def pybibparse():
    """
    Reads latex file name from the command line, parses the .blg file and calls get_citations()
    """
    parser = argparse.ArgumentParser(prog='pybibget', description='Command line utility to automatically retrieve BibTeX citations from MathSciNet, arXiv and PubMed')
    parser.add_argument('file_name', type=str, metavar='tex_file(.tex)', nargs=1, help='LaTeX file to be parsed for missing citations')
    parser.add_argument('-w', action='store', dest='write', metavar="output.bib", nargs='?', const=" ", help='Append output to file (default: write output to stdout). A bib file name can be specified via "-w file_name.bib" but usually the .bib file is found automatically.')
    add_optional_args(parser)
    args = parser.parse_args()
    if not args.file_name:
        parser.print_help()
        sys.exit()
    if args.file_name[0].endswith(".tex"):
        base_file_name = args.file_name[0][:-4]
    else:
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
        get_citations(missing_cites, **kwargs)        
    else:
        print("No missing citations found. Make sure that biber/bibtex is run successfully before running pybibget.")

def pybibupdate():
    parser = argparse.ArgumentParser(prog='pybibget', description='Command line utility to update BibTeX citations from MathSciNet and Scopus')
    parser.add_argument('file_name', type=str, metavar='bib_file(.bib)', help='bib file to be parsed for citations')
    args = parser.parse_args()
    if not args.file_name:
        parser.print_help()
        sys.exit()
    if not args.file_name.endswith(".bib"):
        args.file_name += ".bib"
    with open(args.file_name) as file:
        bib_file = file.read()
    bibliography = parse_string(bib_file, 'bibtex').entries

    log.basicConfig(format="%(levelname)s: %(message)s", level=log.WARNING)

    bibget = Bibget(mathscinet=True)
    updated_bibliography = asyncio.run(bibget.update_all(bibliography))
    with open(args.file_name, 'w') as file:
        file.write(updated_bibliography.to_string('bibtex'))
        print(f"Wrote the updated bibliography to {args.file_name}.")

def get_citations(keys, verbose=log.WARNING, file=None):
    """
    Retrieves BibTeX entries for given citation keys and writes them to file or stdout
    """
    log.basicConfig(format="%(levelname)s: %(message)s", level=verbose)

    bibget = Bibget(mathscinet=True)
    bib_data = asyncio.run(bibget.citations(keys))
    number_of_entries = len(bib_data.entries)
    bib_data = bib_data.to_string('bibtex')
    if file:
        with open(file, 'a') as obj:
            obj.write(bib_data)
            print(f"Successfully appended {number_of_entries} BibTeX entries to {file}.")
    else:
        print("\n"+bib_data)
    return number_of_entries


if __name__ == '__main__':
    sys.exit(pybibget())
