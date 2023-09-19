==================
docker-migrid-docs
==================

---------------
Getting Started
---------------

To build the documentation for `docker-migrid` locally, the requirements defined in `requirements.txt` needs to be installed first.
This is achieved by running the following command::

    # Best practice, create a seperate virtual environment
    python3 -m virtualenv venv
    source venv

    # Install the requirements
    pip3 install -r requirements.txt

Afterwards, you can now build the docs, with one of the supported targets by executing::

    (venv) machine@distro:~/repos/docker-migrid/doc$ make
    Sphinx v4.1.2
    Please use 'make target' where target is one of
    html        to make standalone HTML files
    dirhtml     to make HTML files named index.html in directories
    singlehtml  to make a single large HTML file
    pickle      to make pickle files
    json        to make JSON files
    htmlhelp    to make HTML files and an HTML help project
    qthelp      to make HTML files and a qthelp project
    devhelp     to make HTML files and a Devhelp project
    epub        to make an epub
    latex       to make LaTeX files, you can set PAPER=a4 or PAPER=letter
    latexpdf    to make LaTeX and PDF files (default pdflatex)
    latexpdfja  to make LaTeX files and run them through platex/dvipdfmx
    text        to make text files
    man         to make manual pages
    texinfo     to make Texinfo files
    info        to make Texinfo files and run them through makeinfo
    gettext     to make PO message catalogs
    changes     to make an overview of all changed/added/deprecated items
    xml         to make Docutils-native XML files
    pseudoxml   to make pseudoxml-XML files for display purposes
    linkcheck   to check all external links for integrity
    doctest     to run all doctests embedded in the documentation (if enabled)
    coverage    to run coverage check of the documentation (if enabled)
    clean       to remove everything in the build directory

For development, we recommend to simply choose `html`.

---------------------
Publish Documentation
---------------------

To publish the defined documentation, simply push the applied change to the `master` branch.
Readthedocs will then take of rebuilding the `https://docker-migrid.readthedocs.io/` page.