# pybibget

Command line utility to automatically retrieve BibTeX citations from MathSciNet, arXiv, PubMed and doi.org

## Installation

```bash
$ pip install pybibget
```

## Usage

### Citation Keys

`pybibget` provides a command line interface to obtain BibTeX entries from citation keys of the form 
| Citation key         | Format                        |
|----------------------|-------------------------------|
| MR0026286            | MathSciNet (requires subscription)                    |
| 1512.03385           | arXiv identifier (new format) |
| hep-th/9711200       | arXiv identifier (old format) |
| PMID:271968          | PubMed                        |
| 10.1109/CVPR.2016.90 | DOI                           |

`pybibget key1 key2 ...` prints the BibTeX entries `stdout`:
```console
% pybibget MR0026286 10.1109/TIT.2006.885507 math/0211159 PMID:271968 10.1109/CVPR.2016.90 hep-th/9711200

@article{MR0026286,
    AUTHOR = "Shannon, C. E.",
    TITLE = "A mathematical theory of communication",
    JOURNAL = "Bell System Tech. J.",
    FJOURNAL = "The Bell System Technical Journal",
    VOLUME = "27",
    YEAR = "1948",
    PAGES = "379--423, 623--656",
    ISSN = "0005-8580",
    MRCLASS = "60.0X",
    MRNUMBER = "26286",
    MRREVIEWER = "J. L. Doob",
    DOI = "10.1002/j.1538-7305.1948.tb01338.x",
    URL = "https://doi.org/10.1002/j.1538-7305.1948.tb01338.x"
}

@article{10.1109/TIT.2006.885507,
    AUTHOR = "Candes, Emmanuel J. and Tao, Terence",
    TITLE = "Near-optimal signal recovery from random projections: universal encoding strategies?",
    JOURNAL = "IEEE Trans. Inform. Theory",
    FJOURNAL = "Institute of Electrical and Electronics Engineers. Transactions on Information Theory",
    VOLUME = "52",
    YEAR = "2006",
    NUMBER = "12",
    PAGES = "5406--5425",
    ISSN = "0018-9448",
    MRCLASS = "94A12 (41A25 94A13)",
    MRNUMBER = "2300700",
    MRREVIEWER = "L. L. Campbell",
    DOI = "10.1109/TIT.2006.885507",
    URL = "https://doi.org/10.1109/TIT.2006.885507"
}

@unpublished{math/0211159,
    author = "Perelman, Grisha",
    title = "{The} entropy formula for the {Ricci} flow and its geometric applications",
    note = "Preprint",
    year = "2002",
    eprint = "math/0211159",
    archiveprefix = "arXiv"
}

@article{PMID:271968,
    author = "Sanger, F. and Nicklen, S. and Coulson, A. R.",
    doi = "10.1073/pnas.74.12.5463",
    url = "https://doi.org/10.1073/pnas.74.12.5463",
    year = "1977",
    publisher = "Proceedings of the National Academy of Sciences",
    volume = "74",
    number = "12",
    pages = "5463--5467",
    title = "{DNA} sequencing with chain-terminating inhibitors",
    journal = "Proceedings of the National Academy of Sciences",
    PMID = "271968"
}

@inproceedings{10.1109/CVPR.2016.90,
    author = "He, Kaiming and Zhang, Xiangyu and Ren, Shaoqing and Sun, Jian",
    doi = "10.1109/cvpr.2016.90",
    url = "https://doi.org/10.1109/cvpr.2016.90",
    year = "2016",
    publisher = "{IEEE}",
    title = "{Deep} {Residual} {Learning} for {Image} {Recognition}",
    booktitle = "2016 {IEEE} Conference on Computer Vision and Pattern Recognition ({CVPR})"
}

@article{hep-th/9711200,
    AUTHOR = "Phan, Trung V. and Doan, Anh",
    TITLE = "A curious use of extra dimension in classical mechanics: geometrization of potential",
    JOURNAL = "J. Geom. Graph.",
    FJOURNAL = "Journal for Geometry and Graphics",
    VOLUME = "25",
    YEAR = "2021",
    NUMBER = "2",
    PAGES = "265--270",
    ISSN = "1433-8157",
    MRCLASS = "70B05",
    MRNUMBER = "4394144",
    DOI = "10.1023/a:1026654312961",
    URL = "https://doi.org/10.1023/a:1026654312961",
    eprint = "hep-th/9711200",
    archiveprefix = "arXiv"
}
```
With the option `-f filename` the result can be *appended* to any given file directly:
```console
% pybibget MR0026286 10.1109/TIT.2006.885507 math/0211159 PMID:271968 10.1109/CVPR.2016.90 hep-th/9711200 -f bibliography.bib
Succesfully appended 6 BibTeX entries to bibliography.bib
``` 

### TeX File Parsing

`pybibparse` automatically parses missing citations from the `biber` or `bibtex` log for a given `TeX` file
```console
% pybibparse example 

@article{math/0211159,
    author = "Perelman, Grisha",
    title = "{The} entropy formula for the {Ricci} flow and its geometric applications",
    journal = "preprint",
    year = "2002",
    eprint = "math/0211159",
    archiveprefix = "arXiv"
}

@article{PMID:271968,
    author = "Sanger, F. and Nicklen, S. and Coulson, A. R.",
    doi = "10.1073/pnas.74.12.5463",
    url = "https://doi.org/10.1073/pnas.74.12.5463",
    year = "1977",
    publisher = "Proceedings of the National Academy of Sciences",
    volume = "74",
    number = "12",
    pages = "5463--5467",
    title = "{DNA} sequencing with chain-terminating inhibitors",
    journal = "Proceedings of the National Academy of Sciences",
    PMID = "271968"
}
```

With the option `-w [file_name]` the obtained citations are automatically appended to the `.bib` file. `[file_name]` is optional if the `.bib` file has been specified in the `TeX` file.
```console
% pybibparse example -w
Succesfully appended 2 BibTeX entries to bibliography.bib
```

## Data Sources

### MathSciNet
Directly accesses [MathSciNet](https://mathscinet.ams.org/mathscinet/index.html) and uses the provided citation unmodified

### DOI
First searches for the DOI on [MathSciNet](https://mathscinet.ams.org/mathscinet/index.html). If successful, uses the MathSciNet strategy, otherwise uses the citation from [doi.org](https://doi.org) with the following modifications:
- Author names and title are converted to TeX form (special characters like `ö` are converted to `"{o}`)
- Capital words in the title are surrounded by `{...}`to ensure capitalization
- Publication month data is removed

### PubMed
Searches for the DOI on [PubMed](https://pubmed.ncbi.nlm.nih.gov), then uses the DOI strategy and appends `pmid = [PMID]` to the resulting citation.

### arXiv 
Uses DOI strategy if metadata contains `doi`. 
Otherwise creates an `unpublished` bib-entry with `note = "Preprint"` or `note = [Journal Metadata]` (if provided). In any-case appends `eprint = [arXiv identifier]` to the citation.