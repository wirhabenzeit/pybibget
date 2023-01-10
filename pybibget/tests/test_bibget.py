import pybibget
from pybibget.bibentry import Bibget
import asyncio
import logging as log

def test_scopus():
    keys = ["MR0026286","10.1109/TIT.2006.885507","math/0211159","PMID:271968","10.1109/CVPR.2016.90","10.4310/ATMP.1998.v2.n2.a1","10.1016/C2016-0-01168-3","10.3322/caac.21492","10.3322/caac.20107","10.1073/pnas.0506580102","10.1002/ijc.29210","10.1016/j.ejca.2008.10.026","10.1056/NEJMoa043330","10.1001/jama.288.3.321","10.1038/nbt.1754","10.1038/s41588-018-0312-8","10.1056/NEJMc1713444","10.1038/cr.2015.82","10.1038/nature11606","10.1038/s41588-018-0183-z","10.1016/B978-0-12-800100-4.00003-9"]
    assert pybibget.get_citations(keys, verbose=log.DEBUG, file="test.bib") == 21