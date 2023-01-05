import argparse, re
import pybibget.bibentry
import pybtex.database

def pybibget():
    parser = argparse.ArgumentParser(prog ='pybibget',description ='Command line utility to automatically retrieve BibTeX citations from MathSciNet, arXiv and PubMed')
  
    parser.add_argument('keys', type = str, metavar ='citekeys', nargs='*',help ='MathSciNet (MRxxxxx), arXiv (xxxx.xxxxx), PubMed (PMID:xxxxxxxx) or DOI (10.xxx/xxxxx) citation keys (separated by spaces)')
    parser.add_argument('-v','--verbose',action='store_true',help='verbose output')
    parser.add_argument('-f', action='store',dest='file_name',help='Append output to file (default: write output to stdout)')

    args = parser.parse_args()
    if not args.keys:
        parser.print_help()
        exit(1)
    get_citations(args.keys,verbose=args.verbose,file=args.file_name)

def pybibparse():
    parser = argparse.ArgumentParser(prog ='pybibget',description ='Command line utility to automatically retrieve missing BibTeX citations from MathSciNet, arXiv and PubMed')
  
    parser.add_argument('file_name', type = str, metavar ='file name', nargs=1, help ='base file name of main tex file (without .tex extension)')
    parser.add_argument('-v','--verbose',action='store_true',help='verbose output')
    parser.add_argument('-w','--write',metavar="file_name",action='store', nargs='?', const=" ", type=str,help='Append output to .bib file (default: write output to stdout). The .bib file is automatically detected from the .blg file. If no .bib file is found, the .bib file has to be specified explicitly via "-w file_name.bib".')

    args = parser.parse_args()
    if not args.file_name:
        parser.print_help()
        exit(1)

    baseFileName = args.file_name[0]
    blgFile = open(baseFileName+".blg")
    blgFile = blgFile.read()
    missingCites = re.findall(r"I didn't find a database entry for '([A-Za-z0-9\.\-_ :\/]*)'", blgFile) + re.findall(r'I didn\'t find a database entry for "([A-Za-z0-9\.\-_ :\/]*)"', blgFile)
    bibFileNames = re.findall(r"Found BibTeX data source '([A-Za-z0-9.\-_\/]*)'", blgFile) + re.findall(r"Looking for bibtex file '([A-Za-z0-9.\-_\/]*)'", blgFile) + re.findall(r'Database file #\d: ([A-Za-z0-9.\-_\/]*)\n', blgFile) + re.findall(r'I couldn\'t open database file ([A-Za-z0-9.\-_\/]*)\n', blgFile)

    if missingCites:
        if args.write is None:
            get_citations(missingCites,verbose=args.verbose)
        elif args.write != " ":
            get_citations(missingCites,verbose=args.verbose,file=args.write)
        elif args.write == " " and bibFileNames:
            get_citations(missingCites,verbose=args.verbose,file=bibFileNames[0])
        else:
            print("No .bib file found. Please specify the .bib file explicitly via '-w file_name.bib'")
    else:
        print("No missing citations found. Make sure that biber/bibtex is run successfully before running pybibget.")
    
def get_citations(keys,verbose=False,file=None):
    bib_data = pybtex.database.BibliographyData()
    for key in keys:
        try:
            bib_data.entries[key] = bibentry.getbibentry(key,verbose=verbose)
        except ValueError as e:
            print(e)
    number_of_entries = len(bib_data.entries)
    bib_data = bib_data.to_string('bibtex')
    if file:
        with open(file,'a') as f:
            f.write(bib_data)
            print(f"Succesfully appended {number_of_entries} BibTeX entries to {file}.")
    else:
        if verbose:
            print("\n======================\n Output:\n======================")
        print("\n"+bib_data)

if __name__ == '__main__':
    pybibget()