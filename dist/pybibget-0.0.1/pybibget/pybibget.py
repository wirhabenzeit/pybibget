import argparse, re
import bibentry
import pybtex.database

def pybibget():
    parser = argparse.ArgumentParser(prog ='pybibget',description ='Command line utility to automatically retrieve BibTeX citations from MathSciNet, arXiv and PubMed')
  
    parser.add_argument('keys', type = str, metavar ='citekeys', nargs='*',help ='MathSciNet (MRxxxxx), arXiv (2301.xxxxx) or PubMed (PMID:xxxxxxxx) citation keys (separated by spaces)')
    parser.add_argument('-v','--verbose',action='store_true',help='verbose output' )
    
    args = parser.parse_args()
  
    if not args.keys:
        parser.print_help()
        exit(1)
    bib_data = pybtex.database.BibliographyData()
    for key in args.keys:
        try:
            bib_data.entries[key] = bibentry.getbibentry(key,verbose=args.verbose)
        except ValueError as e:
            print(e)
    print(bib_data.to_string('bibtex'))

if __name__ == '__main__':
    pybibget()