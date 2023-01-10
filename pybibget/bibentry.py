from urllib import parse
import re
import asyncio
import logging as log
from lxml import html, etree
import os
import textwrap
import json
import os.path
import httpx
from appdirs import AppDirs
from itertools import zip_longest
from aiolimiter import AsyncLimiter
from pybtex.database import Entry, Person, BibliographyData, parse_string
from pylatexenc.latexencode import unicode_to_latex
from pylatexenc.latex2text import LatexNodes2Text
ATOM = 'http://www.w3.org/2005/Atom'
ARXIV = 'http://arxiv.org/schemas/atom'
RE_MSC = r'MR\d{4,10}'
RE_PMID = r'PMID:\d{4,10}'
RE_DOI = r'10\.\d{4,9}\/[-._;()\/:A-Za-z0-9]+'
RE_ARXIV_OLD = r'\b[a-zA-Z\-\.]{2,10}\/\d{7}(?:v\d)?\b'
RE_ARXIV_NEW = r'\b\d{4}\.\d{4,5}(?:v\d)?\b'

def column_print(str1,str2,maxwidth=80):
    width = min(os.get_terminal_size().columns//2 - 3,maxwidth)
    lines1, lines2 = str1.splitlines(), str2.splitlines()
    print("-"*(width*2+5))
    for line1, line2 in zip_longest(lines1, lines2, fillvalue=''):
        line1 = textwrap.shorten(line1, width=width, placeholder="...")
        line2 = textwrap.shorten(line2, width=width, placeholder="...")
        print(f"{line1:<{width}}  ->  {line2:<{width}}")
    print("-"*(width*2+5))

def nested_dict(dic, key):
    for ke, it in dic.items():
        if ke == key:
            yield it
        yield from [] if not isinstance(it, dict) else nested_dict(it, key)


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


def create_bibentry(entry_type,sanitize=True,author=None,key=None,**kwargs):
    """
    Create a bibentry from a dictionary.

    Parameters
    ----------
    entry_type : str
        The entry type.
    **kwargs : dict
        The entry fields.

    Returns
    ---------
    bibentry : pybtex.database.Entry
    """
    bibentry = Entry(entry_type)
    if author:
        bibentry.persons['author'] = [Person(sanitize_string(str(person))) for person in author]
    for key, value in kwargs.items():
        bibentry.fields[key] = sanitize_string(value, title = key in ['title','booktitle']) if sanitize and key in ["title","author","journal","booktitle","publisher"] else value
    bibentry.key = "" if key is None else key
    return bibentry


class Bibget():
    def __init__(self, mathscinet=True):
        self.mathscinet = mathscinet
        self.config_file = os.path.join(AppDirs("pybibget", "pybibget").user_data_dir, "config.json")
        if os.path.isfile(self.config_file):
            self.rate_limit = AsyncLimiter(int(json.load(open(self.config_file))["scopus_rate_limit"]), 1)
            self.api_key = json.load(open(self.config_file))["scopus_api_key"]
            self.scopus = len(self.api_key) > 0
        else:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, "w+") as file:
                file.write(json.dumps({"scopus_api_key": "", "scopus_rate_limit": 6}))
            self.scopus = False

    def setup_scopus(self,message):
        self.api_key = input(message)
        with open(self.config_file, "w+") as file:
            file.write(json.dumps({"scopus_api_key": self.api_key, "scopus_rate_limit": 6}))
        self.scopus = len(self.api_key) > 0

    async def citations(self,keys):
        if any(map(lambda key: re.match(RE_DOI, key) or re.match(RE_PMID, key), keys)) and not self.scopus:
            self.setup_scopus(f"Scopus can result in more reliable results than crossref.org, but requires an API key. If you want to use Scopus, please register at https://dev.elsevier.com/ and enter your API key below. If you don't want to use Scopus, just press [enter]. You can also enter your API key later in {self.config_file}\n")
        bibentries = await asyncio.gather(*[self.citation(key) for key in keys],return_exceptions=True)
        bib_data = BibliographyData()
        for entry_key in bibentries:
            if isinstance(entry_key, Exception):
                log.error(entry_key)
            else:
                entry,key = entry_key
                bib_data.entries[key] = entry
        return bib_data
    
    async def citation(self,key):
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
            return (await self.citation_msc(mrkey=key), key)
        elif re.match(RE_PMID, key):
            if self.scopus:
                log.info(msg_looking(key, "Scopus"))
                try:
                    return (await self.citation_scopus(pmid=key), key)
                except Exception as exc:
                    log.warning(exc) 
            log.info(msg_looking(key, "PubMed"))
            return (await self.citation_pubmed(key), key)
        elif re.match(RE_ARXIV_OLD, key) or re.match(RE_ARXIV_NEW, key):
            log.info(msg_looking(key, "arXiv"))
            return (await self.citation_arxiv(key), key)
        elif re.match(RE_DOI, key):
            if self.mathscinet:
                try:
                    log.info(msg_looking(key, "MathSciNet"))
                    return (await self.citation_msc(doi=key), key)
                except Exception as exc:
                    log.warning(exc)
            if self.scopus:
                try:
                    log.info(msg_looking(key, "Scopus"))
                    return (await self.citation_scopus(doi=key), key)
                except Exception as exc:
                    log.warning(exc)
            log.info(msg_looking(key, "Crossref"))
            return (await self.citation_crossref(key), key)
        else:
            raise ValueError(f"{key} = Invalid citation key")

    async def citation_msc(self,mrkey=None, doi=None):
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

    async def citation_crossref(self,doi):
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
            except Exception as exc:
                log.info(exc)
                reason = page.status_code
                entries = parse_string(page.text, 'bibtex').entries
                entry = list(entries.values())[0]
                raise ValueError(msg_not_found(doi, "crossref.org", reason=reason))

    async def citation_scopus(self,doi=None, pmid=None):
        """
        Get a bibentry from Scoups via DOI or PMID.

        Parameters
        ----------
        doi : str, optional
            The DOI, must start with 10.xxx/xxx. The default is None.
        pmid : str, optional    
            The PMID, must start with PMID:xxxx. The default is None.

        Returns
        ---------
        bibentry : pybtex.database.Entry

        Raises
        ----------
        ValueError
            If the entry is not found.
        """
        
        if doi:
            url = "https://api.elsevier.com/content/abstract/doi/" + doi
            key = doi
        elif pmid:
            url = "https://api.elsevier.com/content/abstract/pubmed_id/" + pmid[5:]
            key = pmid
        else:
            raise ValueError("Either doi or PMID must be specified.")
        url += "?view=FULL&apiKey=" + self.api_key
        headers = {'Accept': 'application/json; charset=utf-8'}
        async with httpx.AsyncClient() as client:
            async with self.rate_limit:
                page = await client.get(url, headers=headers, follow_redirects=True)
                if log.root.level == log.DEBUG:
                    with open("test"+key.replace("/","-")+".json","w+") as f:
                        f.writelines(page.text)
                try: 
                    results = page.json()
                    results_bib = results['abstracts-retrieval-response']['item']['bibrecord']['head']
                    fields = {}
                    citation_type = results_bib['source']['@type']
                    fields['title'] = results_bib['citation-title']
                    author_flat = []
                    author_groups = results_bib['author-group']
                    if type(author_groups) is not list:
                        author_groups = [author_groups]
                    for author_group in author_groups:
                        authors = author_group['author']
                        if type(authors) is not list:
                            authors = [authors]
                        for author in authors:
                            author_flat.append(f"{author['preferred-name']['ce:surname']}, {author['preferred-name']['ce:given-name']}")
                    fields['author'] = [Person(author) for author in author_flat]
                    try: 
                        fields['year'] = list(results_bib['source']['publicationyear'].values())[0]
                    except Exception as e:
                        log.warning(str(e))
                    if pmid:
                        doi = results['abstracts-retrieval-response']['coredata']['prism:doi']
                    fields['doi'] = doi
                    fields['url'] = "https://doi.org/" + doi
                    if citation_type == 'j':
                        citation_type = 'article'
                        fields['journal'] = results_bib['source']['sourcetitle-abbrev'] if 'sourcetitle-abbrev' in results_bib['source'] else results_bib['source']['sourcetitle']
                        try:
                            fields['volume'] = results_bib['source']['volisspag']['voliss']['@volume']
                            fields['number'] = results_bib['source']['volisspag']['voliss']['@issue']
                        except KeyError as e:
                            log.info(f"{key}: No volume or issue found on Scopus.")
                        try: 
                            fields['pages'] = '--'.join(results_bib['source']['volisspag']['pagerange'].values())
                        except KeyError as e:
                            log.info(f"{key}: No page range found on Scopus.")
                    elif citation_type in ['p','k']:
                        citation_type = 'inproceedings' if citation_type == 'p' else 'incollection'
                        fields['publisher'] = results_bib['source']['publisher']['publishername']
                        fields['booktitle'] = results_bib['source']['sourcetitle-abbrev']
                    elif citation_type == 'b':
                        citation_type = 'book'
                        fields['publisher'] = results_bib['source']['publisher']['publishername']
                        fields['title'] = results_bib['source']['sourcetitle']
                        try:
                            fields['pages'] = results_bib['source']['volisspag']['pagerange']['@last']
                        except:
                            log.warning(f"{key}: Number of pages not found on Scopus.") 
                    else:
                        raise ValueError("Unknown citation type: " + citation_type)
                    if pmid:
                        fields['pmid'] = pmid[5:]
                    else:
                        try: 
                            fields['pmid'] = results['abstracts-retrieval-response']['coredata']['pubmed-id']
                        except:
                            pass
                    bibentry = create_bibentry(citation_type ,**fields)
                    log.info(msg_found(key, "Scopus"))
                    return(bibentry)
                except Exception as exc:
                    reason = str(page.status_code)
                    if page.status_code == 401:
                        reason += "; Error 401 suggests that either the supplied API key is wrong, or requires a VPN connection"
                    raise ValueError(msg_not_found(key, "Scopus", reason=reason)) from exc

    async def citation_arxiv(self,arxiv_key):
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
                    bibentry, _ = await self.citation(doi[0].text)
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

    async def citation_pubmed(self,pmid):
        doi = await self.get_doi(pmid=pmid)
        log.info(msg_looking(doi, "Crossref (forwarded from PubMed)"))
        if self.scopus:
            try: 
                result = await self.citation_scopus(doi=doi)
                result.fields['pmid'] = pmid[5:]
                return result
            except Exception as exc:
                log.warning(msg_not_found(doi, "Scopus", reason=str(exc), continuation="Trying crossref.org"))
        result = await self.citation_crossref(doi=doi)
        result.fields['pmid'] = pmid[5:]
        return result 

    async def get_doi(self,pmid=None):
        """
        Get a DOI from a PubMed ID.

        Parameters
        ----------
        pmid : str, optional
            The PubMed ID. The default is None.

        Returns
        ---------
        doi : str

        Raises
        ----------
        ValueError
            If the PubMed ID is invalid or the DOI is not found.
        """
        if not pmid:
            raise ValueError("No PubMed ID provided.")
        if not re.match(RE_PMID, pmid):
            raise ValueError("Invalid PubMed ID.")
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid[5:]}/?format=pubmed"
        async with httpx.AsyncClient() as client:
            page = await client.get(url, follow_redirects=True)
            try:
                doi = re.search("AID - (10\.\d{4,9}\/[-._;()\/:A-Za-z0-9]+) \[doi\]", page.text)
                return doi.group(1)
            except Exception as exc:
                raise ValueError(f"DOI not found for PubMed ID {pmid}!") from exc
    
    async def prompt(self,entry,candidate=None,prefix=None):
        prompt = prefix + "Press"
        if candidate:
            prompt += " 'y' to replace,"
        ans = input(prompt + " [enter] to leave the old citation, or enter a DOI for a custom replacement: ")
        if ans == "":
            return entry
        elif ans == "y" and candidate:
            return candidate
        else:
            return await self.update(entry, candidate_doi=ans)

    async def update(self,entry,candidate=None,candidate_doi=None):
        title = LatexNodes2Text(math_mode='verbatim').latex_to_text(entry.fields["title"])
        if 'mrnumber' in entry.fields:
            log.info(f"MR{entry.fields['mrnumber']} ({title}): Skipping MR entry")
            return entry
        if candidate:
            candidate.key = entry.key    
            if 'eprint' in entry.fields:
                candidate.fields['eprint'] = entry.fields['eprint']
                candidate.fields['archiveprefix'] = entry.fields['archiveprefix']
            if 'pmid' in entry.fields and 'pmid' not in candidate.fields:
                candidate.fields['pmid'] = entry.fields['pmid']
            print("Found the following replacement:")
            column_print(entry.to_string('bibtex'), candidate.to_string('bibtex'))
            return await self.prompt(entry,candidate=candidate,prefix="Replace old citation? ")
        if candidate_doi:
            if not re.match(RE_DOI, candidate_doi):
                return await self.prompt(entry,prefix="Invalid DOI! ")
            try: 
                candidate,_ = await self.citation(candidate_doi)
                return await self.update(entry, candidate=candidate)
            except Exception as exc:
                print(f"{candidate_doi}: No citation found; leaving old citation")
                print(exc)
                return entry
        if 'doi' in entry.fields and 'mrnumber' not in entry.fields:
            try:
                updated_entry = await self.citation_msc(doi=entry.fields['doi'])
                return await self.update(entry,updated_entry)
            except:
                log.info(f"{entry.fields['doi']} ({title}): Not found on MathSciNet, leaving old citation")
                return entry
        try:
            log.info(f'"{title}": Checking for DOI on Scopus')
            updated_entry = await self.lookup_scopus(title)
            return await self.update(entry, candidate=updated_entry)
        except Exception as exc:
            log.debug(f'"{title}": {str(exc)}')
            return await self.prompt(entry, prefix=f'"{title}": No entry found on Scopus. ')

    async def update_all(self,bibliography):
        while not self.scopus:
            self.setup_scopus(f"Scopus is required for 'pybibupdate' and requires an API key. Please register at https://dev.elsevier.com/ and enter your API key below.\n")

        updated_bibliography = BibliographyData()
        for key,entry in bibliography.items():
            updated_bibliography.entries[key] = await self.update(entry)
        
        return updated_bibliography

    async def lookup_scopus(self,title):
        url = "https://api.elsevier.com/content/search/scopus?query=TITLE%28%22" + parse.quote(title,safe="") + "%22%29"
        url += "&apiKey=" + self.api_key
        headers = {'Accept': 'application/json; charset=utf-8'}
        async with httpx.AsyncClient() as client:
            async with self.rate_limit:
                page = await client.get(url, headers=headers, follow_redirects=True)
                try: 
                    results = page.json()
                    doi = results['search-results']['entry'][0]['prism:doi']
                    try:
                        return await self.citation_msc(doi)
                    except Exception as exc:
                        return await self.citation_scopus(doi=doi)
                except Exception as exc:   
                    raise ValueError(msg_not_found(title, "Scopus", reason=str(exc)))


def sanitize_entry(entry):
    """
    Sanitize a bibentry. Protects title capitalization, removes newlines and tabs, and converts unicode characters to LaTeX.
    """
    if "title" in entry.fields:
        entry.fields["title"] = sanitize_string(entry.fields["TITLE"],title=True)
    if "AUTHOR" in entry.persons:
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