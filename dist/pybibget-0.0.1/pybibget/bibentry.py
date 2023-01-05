from lxml import html, etree
import requests,re
from pybtex.database import Entry, Person, parse_string, parse_bytes
from pylatexenc.latexencode import unicode_to_latex
from pylatexenc.latex2text import LatexNodes2Text
atom_namespace = 'http://www.w3.org/2005/Atom'
arxiv_namespace = 'http://arxiv.org/schemas/atom'
re_mathscinet = r'MR\d{4,10}'
re_pubmed = r'PMID:\d{4,10}'
re_doi = r'10\.\d{4,9}\/[-._;()/:A-Za-z0-9]+'
re_arxiv_old = r'\b[a-zA-Z\-\.]{2,10}\/\d{7}(?:v\d)?\b'
re_arxiv_new = r'\b\d{4}\.\d{4,5}(?:v\d)?\b'


def getbibentry(id,verbose=False):
    if re.match(re_mathscinet,id):
        if verbose:
            print(f"Looking for MathSciNet key {id}...",end=" ")
        return get_mathscinet_bibentry(id=id,verbose=verbose)
    elif re.match(re_pubmed,id):
        if verbose:
            print(f"Looking for PubMed key {id}...",end=" ")
    elif re.match(re_arxiv_old, id) or re.match(re_arxiv_new, id):
        if verbose:
            print(f"Looking for arXiv key {id}...",end=" ")
        return get_arxiv_bibentry(id,verbose=verbose)
    elif re.match("",id):
        try:
            if verbose:
                print(f"Looking for {id} on MathSciNet...",end=" ")
            return get_mathscinet_bibentry(doi=id,verbose=verbose)
        except ValueError:
            if verbose:
                print(f"Looking for {id} on doi.org...",end=" ")
            return get_doi_bibentry(id,verbose=verbose)
    else:
        raise ValueError(f"Invalid citation key {id}!\n")

def get_mathscinet_bibentry(id=None,doi=None,verbose=False):
    if id:
        url = "https://mathscinet.ams.org/mathscinet/search/publications.html?fmt=bibtex&pg1=MR&s1=" + id[2:]
    elif doi:
        url = "https://mathscinet.ams.org/mathscinet/search/publications.html?fmt=bibtex&pg1=DOI&s1=" + doi
    page = requests.get(url)
    tree = html.fromstring(page.content)
    if bibstrings := tree.xpath('//pre/text()'):
        if verbose:
            print("Success!")
        bibstr=bibstrings[0]
    else:
        raise ValueError(f"Not found! Please check the citation key and whether you have access to MathSciNet.")
    entries = parse_string(bibstr,'bibtex').entries
    univ_id= list(entries.keys())[0]
    return entries[univ_id]

def get_doi_bibentry(id,verbose=False):
    url = "https://doi.org/" + id
    headers = { 'Accept': 'application/x-bibtex; charset=utf-8' }
    page = requests.get(url,headers=headers)
    entries = parse_bytes(page.content,'bibtex').entries
    if len(entries) == 1:
        if verbose:
            print("Success!")
        return sanitize_entry(list(entries.values())[0])
    else:
        raise ValueError(f"Not found! Please check the citation key and whether you have access to doi.org.")

def get_arxiv_bibentry(id,verbose=False):
    url = "http://export.arxiv.org/api/query?id_list=" + id
    page = requests.get(url)
    tree = etree.fromstring(page.content)
    if doi := tree.xpath("//a:entry/b:doi",namespaces={ 'a': atom_namespace,'b': arxiv_namespace }):
        if verbose:
            print("Detected DOI in arXiv record...",end=" ")
        bibentry = getbibentry(doi[0].text,verbose=verbose)
    elif title := tree.xpath("//a:entry/a:title",namespaces={ 'a': atom_namespace }):
        if verbose:
            print("Success!")
        fields = [("TITLE", title[0].text)]
        if journal := tree.xpath("//a:entry/a:journal",namespaces={ 'a': atom_namespace }):
            fields += [("JOURNAL",journal[0].text)]
        else:
            fields += [("JOURNAL","preprint")]
        fields += [("YEAR", tree.xpath("//a:entry/a:published",namespaces={ 'a':atom_namespace })[0].text[:4])]
        bibentry = Entry("article", fields=fields)
        bibentry.persons["AUTHOR"] = [Person(author.text) for author in tree.xpath("//a:entry/a:author/a:name",namespaces={ 'a': atom_namespace })]
        bibentry = sanitize_entry(bibentry)
    else:
        raise ValueError(f"Could not find citation for {id}. Please check the citation key and whether you have access to arXiv.")
    bibentry.fields["EPRINT"] = id
    bibentry.fields["ARCHIVEPREFIX"] = "arXiv"
    return bibentry 
 

def sanitize_entry(entry):
    entry.fields["TITLE"] = sanitize_string(entry.fields["TITLE"],title=True)
    for author in entry.persons["AUTHOR"]:
        author.first_names = [sanitize_string(name) for name in author.first_names]
        author.last_names = [sanitize_string(name) for name in author.last_names]
    if "month" in entry.fields:
        entry.fields.pop("month")
    return entry

def sanitize_string(string,title=False):
    string = string.replace("\n", "").replace("\t", "")
    string = LatexNodes2Text().latex_to_text(string)
    string=unicode_to_latex(string)
    if title:
        string = re.sub(r'\b([A-Z].*?)\b',r'{\1}',string)
    return string