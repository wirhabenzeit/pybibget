from urllib import parse
import re
from lxml import html, etree
import requests
from pybtex.database import Entry, Person, parse_string, parse_bytes
from pylatexenc.latexencode import unicode_to_latex
from pylatexenc.latex2text import LatexNodes2Text
ATOM = 'http://www.w3.org/2005/Atom'
ARXIV = 'http://arxiv.org/schemas/atom'
RE_MSC = r'MR\d{4,10}'
RE_PMID = r'PMID:\d{4,10}'
RE_DOI = r'10\.\d{4,9}\/[-._;()/:A-Za-z0-9]+'
RE_ARXIV_OLD = r'\b[a-zA-Z\-\.]{2,10}\/\d{7}(?:v\d)?\b'
RE_ARXIV_NEW = r'\b\d{4}\.\d{4,5}(?:v\d)?\b'

def getbibentry(key,verbose=False):
    """
    Get a bibentry from a citation key.

    Parameters
    ----------
    key : str
        The citation key.
    verbose : bool, optional
        Whether to print the progress of the function. The default is False.

    Returns
    ---------
    bibentry : pybtex.database.Entry

    Raises
    ----------
    ValueError
        If the citation key is invalid or the entry is not found.
    """
    if re.match(RE_MSC,key):
        if verbose:
            print(f"Looking for {key} on MathSciNet...",end=" ")
        return get_mathscinet_bibentry(mrkey=key,verbose=verbose)
    if re.match(RE_PMID,key):
        if verbose:
            print(f"Looking for {key} on PubMed...",end=" ")
        return get_pubmed_bibentry(pmid=key,verbose=verbose)
    if re.match(RE_ARXIV_OLD, key) or re.match(RE_ARXIV_NEW, key):
        if verbose:
            print(f"Looking for arXiv:{key}...",end=" ")
        return get_arxiv_bibentry(key,verbose=verbose)
    if re.match(RE_DOI,key):
        try:
            if verbose:
                print(f"Looking for {key} on MathSciNet...",end=" ")
            return get_mathscinet_bibentry(doi=key,verbose=verbose)
        except ValueError:
            if verbose:
                print(f"Not found. Looking for {key} on doi.org...",end=" ")
            return get_doi_bibentry(key,verbose=verbose)
    else:
        raise ValueError(f"Invalid citation key {key}!\n")

def get_mathscinet_bibentry(mrkey=None,doi=None,verbose=False):
    """
    Get a bibentry from a MathSciNet citation key or DOI.

    Parameters
    ----------
    mrkey : str, optional
        The MathSciNet citation key. The default is None.
    doi : str, optional
        The DOI. The default is None.
    verbose : bool, optional
        Whether to print the progress of the function. The default is False.

    Returns
    ---------
    bibentry : pybtex.database.Entry

    Raises
    ----------
    ValueError
        If the neither mrnumber nor doi are provided, or the entry is not found.
    """
    if mrkey:
        url = "https://mathscinet.ams.org/mathscinet/search/publications.html?fmt=bibtex&pg1=MR&s1=" + mrkey[2:]
    elif doi:
        url = "https://mathscinet.ams.org/mathscinet/search/publications.html?fmt=bibtex&pg1=DOI&s1=" + doi
    else:
        raise ValueError("Either mrkey or doi must be specified.")
    if verbose:
        print(f"Connecting to {url}...",end=" ")
    page = requests.get(url,timeout=10)
    tree = html.fromstring(page.content)
    if bibstrings := tree.xpath('//pre/text()'):
        if verbose:
            print("Success!")
        bibstr=bibstrings[0]
    else:
        raise ValueError(f"{mrkey if mrkey else doi} not found! Please check the citation key and whether you have access to MathSciNet.")
    entries = parse_string(bibstr,'bibtex').entries
    univ_id= list(entries.keys())[0]
    return entries[univ_id]

def get_doi_bibentry(doi,verbose=False):
    """
    Get a bibentry from a DOI.

    Parameters
    ----------
    doi : str
        The DOI.
    verbose : bool, optional
        Whether to print the progress of the function. The default is False.

    Returns
    ---------
    bibentry : pybtex.database.Entry

    Raises
    ----------
    ValueError
        If the entry is not found.
    """
    url = "https://doi.org/" + doi
    headers = { 'Accept': 'application/x-bibtex; charset=utf-8' }
    page = requests.get(url,headers=headers,timeout=10)
    if page.status_code == 200:
        entries = parse_bytes(page.content,'bibtex').entries
        if verbose:
            print("Success!")
        return sanitize_entry(list(entries.values())[0])
    else:
        raise ValueError("Not found! Please check the citation key and whether you have access to doi.org.")

def get_arxiv_bibentry(arxiv_key,verbose=False):
    """
    Get a bibentry from an arXiv identifier.

    Parameters
    ----------
    arxiv_key : str
        The arXiv identifier.
    verbose : bool, optional
        Whether to print the progress of the function. The default is False.

    Returns
    ---------
    bibentry : pybtex.database.Entry

    Raises
    ----------
    ValueError
        If the entry is not found.
    """
    url = "http://export.arxiv.org/api/query?id_list=" + arxiv_key
    page = requests.get(url,timeout=10)
    tree = etree.fromstring(page.content)
    if doi := tree.xpath("//a:entry/b:doi",namespaces={ 'a': ATOM,'b': ARXIV }):
        if verbose:
            print("Detected DOI in arXiv record...",end=" ")
        bibentry = getbibentry(doi[0].text,verbose=verbose)
    elif title := tree.xpath("//a:entry/a:title",namespaces={ 'a': ATOM }):
        if verbose:
            print("Success!")
        fields = [("title", title[0].text)]
        if journal := tree.xpath("//a:entry/a:journal",namespaces={ 'a': ATOM }):
            fields += [("note",journal[0].text)]
        else:
            fields += [("note","Preprint")]
        fields += [("year", tree.xpath("//a:entry/a:published",namespaces={ 'a':ATOM })[0].text[:4])]
        bibentry = Entry("unpublished", fields=fields)
        bibentry.persons["author"] = [Person(author.text) for author in tree.xpath("//a:entry/a:author/a:name",namespaces={ 'a': ATOM })]
        bibentry = sanitize_entry(bibentry)
    else:
        raise ValueError(f"Could not find citation for {arxiv_key}. Please check the citation key and whether you have access to arXiv.")
    bibentry.fields["eprint"] = arxiv_key
    bibentry.fields["archiveprefix"] = "arXiv"
    return bibentry

def get_pubmed_bibentry(pmid, verbose=False):
    """
    Get a bibentry from Pubmed for a given PubMed ID.

    Parameters
    ----------
    pmid : str
        The PubMed ID. 
    verbose : bool, optional
        Whether to print the progress of the function. The default is False.

    Returns
    ---------
    bibentry : pybtex.database.Entry

    Raises
    ----------
    ValueError
        If the entry is not found.
    """
    url = f'https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={pmid[5:]}&idtype=pmid&format=json'
    req = requests.get(url, headers={'Accept': 'application/json'},timeout=10)
    if req.status_code == 200:
        data = req.json()
        try:
            doi = data['records'][0]['doi']
            if verbose:
                print(f"Detected doi.org/{doi} in PubMed record...",end=" ")
            bibentry = sanitize_entry(getbibentry(doi,verbose=verbose))
        except Exception as exc:
            raise ValueError(f'Could not find citation for {pmid}. Please check the citation key and whether you have access to PubMed.') from exc
        bibentry.fields["PMID"] = pmid[5:]
        return bibentry

def sanitize_entry(entry):
    """
    Sanitize a bibentry. Protects title capitalization, removes newlines and tabs, and converts unicode characters to LaTeX.
    """
    if "title" in entry.fields:
        entry.fields["title"] = sanitize_string(entry.fields["TITLE"],title=True)
    for author in entry.persons["AUTHOR"]:
        author.first_names = [sanitize_string(name) for name in author.first_names]
        author.last_names = [sanitize_string(name) for name in author.last_names]
    if "month" in entry.fields:
        entry.fields.pop("month")
    if "url" in entry.fields:
        entry.fields["url"] = parse.unquote(entry.fields["url"])
    return entry

def sanitize_string(string,title=False):
    """
    Sanitize a string: Removes newlines and tabs, and converts unicode characters to LaTeX. If title is True, also protects title capitalization.
    """
    string = string.replace("\n", "").replace("\t", "")
    string = LatexNodes2Text().latex_to_text(string)
    string = unicode_to_latex(string)
    if title:
        string = re.sub(r'\b([A-Z].*?)\b',r'{\1}',string)
    return string