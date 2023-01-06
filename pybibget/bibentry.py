from urllib import parse
import re
import logging as log
from lxml import html, etree
import httpx
from pybtex.database import Entry, Person, parse_string
from pylatexenc.latexencode import unicode_to_latex
from pylatexenc.latex2text import LatexNodes2Text
ATOM = 'http://www.w3.org/2005/Atom'
ARXIV = 'http://arxiv.org/schemas/atom'
RE_MSC = r'MR\d{4,10}'
RE_PMID = r'PMID:\d{4,10}'
RE_DOI = r'10\.\d{4,9}\/[-._;()\/:A-Za-z0-9]+'
RE_ARXIV_OLD = r'\b[a-zA-Z\-\.]{2,10}\/\d{7}(?:v\d)?\b'
RE_ARXIV_NEW = r'\b\d{4}\.\d{4,5}(?:v\d)?\b'


def msg_looking(key, service):
    return f"Looking for {key} on {service}"


def msg_found(key, service, continuation=None):
    ret_str = f"{key} found on {service}"
    if continuation:
        ret_str += f". {continuation}"
    return ret_str


def msg_not_found(key, service, continuation=None, reason=None):
    ret_str = f"{key} not found on {service}"
    if reason:
        ret_str += f" ({reason})"
    if continuation:
        ret_str += f". {continuation}"   
    return ret_str


async def getbibentry(key):
    """
    Get a bibentry from a citation key.

    Parameters
    ----------
    key : str
        The citation key.

    Returns
    ---------
    bibentry : pybtex.database.Entry

    Raises
    ----------
    ValueError
        If the citation key is invalid or the entry is not found.
    """
    if re.match(RE_MSC, key):
        log.info(msg_looking(key, "MathSciNet"))
        result = await get_mathscinet_bibentry(mrkey=key)
    elif re.match(RE_PMID, key):
        log.info(msg_looking(key, "PubMed"))
        result = await get_pubmed_bibentry(pmid=key)
    elif re.match(RE_ARXIV_OLD, key) or re.match(RE_ARXIV_NEW, key):
        log.info(msg_looking(key, "arXiv"))
        result = await get_arxiv_bibentry(key)
    elif re.match(RE_DOI, key):
        try:
            log.info(msg_looking(key, "MathSciNet"))
            result = await get_mathscinet_bibentry(doi=key)
        except Exception as exc:
            log.info(exc)
            result = await get_doi_bibentry(key)
    else:
        raise ValueError(f"Invalid citation key {key}!\n")
    return (result, key)


async def get_mathscinet_bibentry(mrkey=None, doi=None):
    """
    Get a bibentry from a MathSciNet citation key or DOI.

    Parameters
    ----------
    mrkey : str, optional
        The MathSciNet citation key, must start with MRxxx. The default is None.
    doi : str, optional
        The DOI, must start with 10.xxx/xxx. The default is None.

    Returns
    ---------
    bibentry : pybtex.database.Entry

    Raises
    ----------
    ValueError
        If the neither mrnumber nor doi are provided, or the entry is not found.
    """
    if not mrkey and not doi:
        raise ValueError("Either MRnumber or doi must be specified.")
    base_url = "https://mathscinet.ams.org/mathscinet/search/publications.html?fmt=bibtex&pg1="
    url = base_url + "MR&s1=" + mrkey[2:] if mrkey else base_url + "DOI&s1=" + doi
    async with httpx.AsyncClient() as client:
        page = await client.get(url)
        try:
            tree = html.fromstring(page.text)
            bibstrings = tree.xpath('//pre/text()')
            bibstr = bibstrings[0]
            if len(bibstrings)>1:
                log.warn(f"MathSciNet returned more than one entry for {mrkey if mrkey else doi}. Using the first one but this may be wrong.")
            entries = parse_string(bibstr, 'bibtex').entries
            log.info(msg_found(mrkey if mrkey else doi, "MathSciNet"))
            return list(entries.values())[0]
        except:
            reason = str(page.status_code)
            if page.status_code == 200:
                reason += "; " + tree.xpath('//head/title/text()')[0].replace("\n", "")
            raise ValueError(msg_not_found(mrkey if mrkey else doi, "MathSciNet", reason=reason, continuation="Trying crossref.org" if doi else None))

            
async def get_doi_bibentry(doi):
    """
    Get a bibentry from a DOI.

    Parameters
    ----------
    doi : str
        The DOI, must start with 10.xxx/xxx

    Returns
    ---------
    bibentry : pybtex.database.Entry

    Raises
    ----------
    ValueError
        If the entry is not found.
    """
    url = "https://api.crossref.org/v1/works/" + doi + "/transform"
    headers = {'Accept': 'application/x-bibtex; charset=utf-8'}
    async with httpx.AsyncClient() as client:
        page = await client.get(url, headers=headers, follow_redirects=True)
        try:
            entries = parse_string(page.text, 'bibtex').entries
            entry = sanitize_entry(list(entries.values())[0])
            log.info(msg_found(doi, "crossref.org"))
            return entry
        except:
            reason = page.status_code
            raise ValueError(msg_not_found(doi, "crossref.org", reason=reason))


async def get_arxiv_bibentry(arxiv_key):
    """
    Get a bibentry from an arXiv identifier.

    Parameters
    ----------
    arxiv_key : str
        The arXiv identifier. Can be either the old (hep-th/xxxxx) or the new (2201.xxxx) format.

    Returns
    ---------
    bibentry : pybtex.database.Entry

    Raises
    ----------
    ValueError
        If the entry is not found.
    """
    url = "http://export.arxiv.org/api/query?id_list=" + arxiv_key
    async with httpx.AsyncClient() as client:
        page = await client.get(url, follow_redirects=True)
        try:
            tree = etree.fromstring(page.text.encode())
            if doi := tree.xpath("//a:entry/b:doi", namespaces={'a': ATOM, 'b': ARXIV}):
                log.info(msg_found(arxiv_key, "arXiv", continuation=f"Detected {doi[0].text}"))
                bibentry, _ = await getbibentry(doi[0].text)
            elif title := tree.xpath("//a:entry/a:title", namespaces={'a': ATOM}):
                fields = [("title", title[0].text)]
                if journal := tree.xpath("//a:entry/a:journal", namespaces={'a': ATOM}):
                    fields += [("note", journal[0].text)]
                else:
                    fields += [("note", "Preprint")]
                fields += [("year", tree.xpath("//a:entry/a:published",namespaces={'a': ATOM})[0].text[:4])]
                bibentry = Entry("unpublished", fields=fields)
                bibentry.persons["author"] = [Person(author.text) for author in tree.xpath("//a:entry/a:author/a:name", namespaces={'a': ATOM})]
                bibentry = sanitize_entry(bibentry)
                log.info(msg_found(arxiv_key, "arXiv", continuation="No DOI found, using title and authors"))
            else:
                raise ValueError(f"empty arXiv entry returned")
            bibentry.fields["eprint"] = arxiv_key
            bibentry.fields["archiveprefix"] = "arXiv"
            return bibentry
        except Exception as exc:
            reason = str(page.status_code) + "; " + exc.args[0]
            raise ValueError(msg_not_found(arxiv_key, "arXiv", reason=reason))
        


async def get_pubmed_bibentry(pmid):
    """
    Get a bibentry from Pubmed for a given PubMed ID.

    Parameters
    ----------
    pmid : str
        The PubMed ID, must start with "PMID:".

    Returns
    ---------
    bibentry : pybtex.database.Entry

    Raises
    ----------
    ValueError
        If the entry is not found.
    """
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid[5:]}/?format=pubmed"
    async with httpx.AsyncClient() as client:
        page = await client.get(url, follow_redirects=True)
        try:
            doi = re.search("AID - (10\.\d{4,9}\/[-._;()\/:A-Za-z0-9]+) \[doi\]", page.text)
            doi = doi.group(1)
            log.info(msg_found(pmid, "PubMed", continuation=f"Detected {doi}"))
            doi_entry, _ = await getbibentry(doi)
            bibentry = sanitize_entry(doi_entry)
            bibentry.fields["PMID"] = pmid[5:]
            return bibentry
        except Exception as exc:
            reason = str(page.status_code)
            if page.status_code == 200:
                reason += "; " + data['records'][0]['errmsg']
            raise ValueError(msg_not_found(pmid, "PubMed", reason=reason)) from exc


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


def sanitize_string(string, title=False):
    """
    Sanitize a string: Removes newlines and tabs, and converts unicode characters to LaTeX. If title is True, also protects title capitalization.
    """
    string = string.replace("\n", "").replace("\t", "").replace("\\\\","\\")
    string = LatexNodes2Text(math_mode='verbatim').latex_to_text(string)
    string = unicode_to_latex(string,non_ascii_only=True)
    if title:
        string = re.sub(r'\b([A-Z].*?)\b',r'{\1}',string)
    return string